# -*- coding: utf-8 -*-
"""常见/历史操作与消息导出测试。"""

from datetime import timedelta
from unittest import mock

from django.utils import timezone

from services.web.ai_assistant.constants import ExecutionStatus, MessageType
from services.web.ai_assistant.exceptions import (
    InvalidMessageSnapshot,
    InvalidMessageState,
    LogExportFailed,
    LogExportPermissionDenied,
    MessageNotFound,
)
from services.web.ai_assistant.models import Message
from services.web.ai_assistant.schemas.audit_search import CommonQuerySchema
from services.web.ai_assistant.services.log_export import MessageExportService
from services.web.ai_assistant.services.operation import (
    CommonQueryStore,
    OperationContextService,
)
from services.web.query.ai_assistant.constants import SNAPSHOT_DEFAULT_COLUMNS
from services.web.query.ai_assistant.exceptions import (
    AIAssistantError as QueryAIAssistantError,
)
from services.web.query.ai_assistant.exceptions import AIPermissionDeniedError
from services.web.query.ai_assistant.services.export import PreviewExportFile
from tests.test_ai_assistant.base import (
    TARGET_SYSTEM_ID,
    AIAssistantPlatformTestCase,
    make_selection_output,
)


class TestCommonQueryStore(AIAssistantPlatformTestCase):
    def _make_store(self, **client_behavior):
        store = CommonQueryStore(redis_client=mock.MagicMock(**client_behavior))
        return store

    def test_replace_today_rebuilds_bucket_atomically(self):
        """当天桶原子重建：delete + zadd（当日计数，频次降序）+ expire（窗口+2 天）一次 MULTI 执行"""

        store = self._make_store()
        store.replace_today(system_id=TARGET_SYSTEM_ID, username=self.user, counts={"q1": 3, "q2": 1}, window_days=14)
        pipeline = store.redis_client.pipeline.return_value
        pipeline.delete.assert_called_once()
        zadd_key, mapping = pipeline.zadd.call_args[0]
        self.assertEqual(mapping, {"q1": 3.0, "q2": 1.0})
        self.assertEqual(
            zadd_key,
            f"bk_audit:ai_assistant:common_queries_v2:{TARGET_SYSTEM_ID}:{self.user}:d"
            f"{timezone.localdate().strftime('%Y%m%d')}",
        )
        pipeline.expire.assert_called_once_with(zadd_key, 16 * 86400)
        pipeline.execute.assert_called_once()

    def test_replace_today_truncates_to_store_limit(self):
        """单天桶容量截断：按频次降序仅保留 STORE_LIMIT 条（防单日异常刷量撑爆内存）"""

        store = self._make_store()
        store.replace_today(
            system_id=TARGET_SYSTEM_ID,
            username=self.user,
            counts={"a": 5, "b": 9, "c": 1},
            window_days=14,
        )
        with mock.patch("django.conf.settings.AI_ASSISTANT_COMMON_QUERY_STORE_LIMIT", 2):
            store.replace_today(
                system_id=TARGET_SYSTEM_ID,
                username=self.user,
                counts={"a": 5, "b": 9, "c": 1},
                window_days=14,
            )
        pipeline = store.redis_client.pipeline.return_value
        mapping = pipeline.zadd.call_args[0][1]
        self.assertEqual(mapping, {"b": 9.0, "a": 5.0})

    def test_replace_today_empty_counts_keeps_deleted(self):
        """当日无计数：仅清空当天桶（delete），不写 zadd/expire（空桶自然不占内存）"""

        store = self._make_store()
        store.replace_today(system_id=TARGET_SYSTEM_ID, username=self.user, counts={}, window_days=14)
        pipeline = store.redis_client.pipeline.return_value
        pipeline.delete.assert_called_once()
        pipeline.zadd.assert_not_called()
        pipeline.expire.assert_not_called()
        pipeline.execute.assert_called_once()

    def test_list_top_merges_with_decay(self):
        """读路径：窗口内天桶线性衰减加权合并——高频在前，历史高频被衰减压低"""

        store = self._make_store()
        pipeline = store.redis_client.pipeline.return_value
        # 单系统 14 天窗口 → 14 个 zrange 结果（顺序：今天 → 13 天前）
        #   今天桶：today-q ×1（权重 1.0 → 1.0）
        #   昨天桶：yesterday-q ×3（权重 13/14 → 2.786，频次胜出）
        #   13 天前桶：old-q ×5（权重 1/14 → 0.357，历史高频被衰减压低）
        pipeline.execute.return_value = (
            [
                [("today-q", 1.0)],
                [("yesterday-q", 3.0)],
            ]
            + [[]] * 11
            + [[("old-q", 5.0)]]
        )
        items = store.list_top(system_ids=[TARGET_SYSTEM_ID], username=self.user, window_days=14, limit=10)
        self.assertEqual([item.query_text for item in items], ["yesterday-q", "today-q", "old-q"])

    def test_list_top_merges_across_systems(self):
        """跨系统同句合并频次（多系统查过 = 更常用），top K 截断"""

        store = self._make_store()
        pipeline = store.redis_client.pipeline.return_value
        # 两系统 × 今天桶（第 1、2 个 zrange），第 3 个起为今天之后的天（昨天）
        pipeline.execute.return_value = [[("q1", 1.0)], [("q1", 2.0)], []] + [[]] * 25
        items = store.list_top(
            system_ids=[TARGET_SYSTEM_ID, "other_system"], username=self.user, window_days=14, limit=10
        )
        self.assertEqual([item.query_text for item in items], ["q1"])
        pipeline.zrange.assert_called_with(mock.ANY, 0, -1, withscores=True)
        self.assertEqual(pipeline.zrange.call_count, 28)  # 2 系统 × 14 天

    def test_list_top_redis_error_returns_empty(self):
        """Redis 异常降级：返回空列表，不抛出（次要功能不阻断主流程）"""

        import redis

        store = self._make_store(**{"pipeline.return_value.execute.side_effect": redis.RedisError("down")})
        self.assertEqual(
            store.list_top(system_ids=[TARGET_SYSTEM_ID], username=self.user, window_days=14, limit=10), []
        )


class TestOperationContext(AIAssistantPlatformTestCase):
    def test_build_disabled_returns_empty(self):
        """总闸关闭：操作上下文返回空（设计稿确认后默认开启，开关保留作一键总闸）。"""

        with mock.patch("django.conf.settings.AI_ASSISTANT_OPERATION_RANKING_ENABLED", False):
            common, historical = OperationContextService.build(system_ids=[TARGET_SYSTEM_ID], username=self.user)
        self.assertEqual(common, [])
        self.assertEqual(historical, [])

    def test_build_enabled_by_default(self):
        """默认开启：走真实实现（Redis 未预热/无历史消息时自然为空，不报错）。"""

        common, historical = OperationContextService.build(system_ids=[TARGET_SYSTEM_ID], username=self.user)
        self.assertEqual(common, [])
        self.assertEqual(historical, [])

    def test_build_historical_filters_by_system_and_deduplicates(self):
        """历史操作：按系统过滤 + 去重 + 上限。"""

        selection = self.create_selection_message()
        self.create_nl_message(query_text="查 admin 的日志", parent=selection)
        self.create_nl_message(query_text="查 admin 的日志", parent=selection)  # 重复
        self.create_nl_message(query_text="查导出失败的记录", parent=selection)
        # 其他系统的消息不进入结果
        other_message = self.create_nl_message(
            query_text="other system query",
            selection=make_selection_output(system_id="other_system"),
        )
        other_message.context_data["system_selection"]["systems"][0]["system_id"] = "other_system"
        other_message.save(update_record=False, update_fields=["context_data"])
        # 失败消息不进入结果
        self.create_nl_message(query_text="失败的不算", parent=selection, status=ExecutionStatus.FAILED)

        historical = OperationContextService.build_historical(system_ids=[TARGET_SYSTEM_ID], username=self.user)
        query_texts = [item.query_text for item in historical]
        self.assertEqual(query_texts, ["查导出失败的记录", "查 admin 的日志"])
        self.assertNotIn("other system query", query_texts)
        self.assertNotIn("失败的不算", query_texts)

    def test_build_common_reads_only_current_user(self):
        """常见操作：仅读取当前用户 × 系统的高频缓存，不串看其他用户样例。"""

        with mock.patch.object(
            CommonQueryStore,
            "list_top",
            return_value=[CommonQuerySchema(query_text=f"{self.user}-q")],
        ) as mock_list_top:
            common = OperationContextService.build_common(system_ids=[TARGET_SYSTEM_ID], username=self.user)
        self.assertEqual([item.query_text for item in common], [f"{self.user}-q"])
        mock_list_top.assert_called_once_with(
            system_ids=[TARGET_SYSTEM_ID], username=self.user, window_days=mock.ANY, limit=mock.ANY
        )

    def test_refresh_common_queries_aggregates_today_counts(self):
        """定时刷新：只聚合当天成功检索，按用户 × 系统计数重建当天桶（重复语句累计频次）。"""

        selection = self.create_selection_message()
        self.create_nl_message(query_text="q1", parent=selection)
        self.create_nl_message(query_text="q1", parent=selection)  # 重复 → 当日频次 2
        self.create_nl_message(query_text="q2", parent=selection)
        # 其他用户的样例进入独立缓存，不与当前用户混合
        other_message = self.create_nl_message(query_text="other-q", parent=selection)
        other_message.created_by = "other_user"
        other_message.save(update_record=False, update_fields=["created_by"])
        # 昨天的消息不进当天桶（滑动窗口由历史天桶承载，当天桶只算当天）
        yesterday_message = self.create_nl_message(query_text="yesterday-q", parent=selection)
        Message.objects.filter(id=yesterday_message.id).update(
            created_at=timezone.localtime() - timedelta(days=1, hours=1)
        )
        with mock.patch.object(CommonQueryStore, "replace_today") as mock_replace:
            result = OperationContextService.refresh_common_queries()
        replace_calls = {
            (call.kwargs["system_id"], call.kwargs["username"]): call.kwargs["counts"]
            for call in mock_replace.call_args_list
        }
        self.assertEqual(replace_calls.get((TARGET_SYSTEM_ID, self.user)), {"q1": 2, "q2": 1})
        self.assertEqual(replace_calls.get((TARGET_SYSTEM_ID, "other_user")), {"other-q": 1})
        self.assertEqual(result, {"refreshed_systems": 2, "scanned_messages": 4})

    def _create_intent_message(self, *, query_text: str, output: dict, status: str = ExecutionStatus.SUCCESS):
        """构造 USER_INTENT 消息（统一入口链路，成功检索输出含 condition + system_id）。"""
        from services.web.ai_assistant.constants import MessageType
        from services.web.ai_assistant.models import Message

        return Message.objects.create(
            conversation=self.conversation,
            parent_message=None,
            message_type=MessageType.USER_INTENT,
            status=status,
            task_id="" if status == ExecutionStatus.SUCCESS else "task-1",
            input_data={"query_text": query_text, "auto_execute": True, "scope_type": "cross_system"},
            context_data={"username": self.user, "namespace": "bkaudit", "scope_type": "cross_system"},
            output_data=output,
            created_by=self.user,
            updated_by=self.user,
        )

    def test_build_historical_includes_user_intent_queries(self):
        """历史操作：USER_INTENT 统一入口的成功检索（output 带 condition + system_id）进榜单。"""

        from services.web.query.ai_assistant.schemas import SearchCondition

        condition = SearchCondition(
            scope_type="system",
            scope_id=TARGET_SYSTEM_ID,
            start_time="2026-09-01T00:00:00+08:00",
            end_time="2026-09-09T00:00:00+08:00",
        ).model_dump(mode="json")
        # 意图识别成功检索（select_system + condition）
        self._create_intent_message(
            query_text="查一下审计中心近七天的操作记录",
            output={"intent": "select_system", "system_id": TARGET_SYSTEM_ID, "condition": condition},
        )
        # 引导性输出（SYSTEM_REQUIRED 无 condition）不是检索，不进榜单
        self._create_intent_message(
            query_text="查下最近七天的日志",
            output={
                "intent": "log_search",
                "error": {"error_code": "SYSTEM_REQUIRED", "error_message": "x", "candidates": []},
            },
        )
        # unrecognized 闲聊不进榜单
        self._create_intent_message(
            query_text="今天天气怎么样",
            output={"intent": "unrecognized", "error": {"error_code": "UNRECOGNIZED_INTENT", "error_message": "x"}},
        )

        historical = OperationContextService.build_historical(system_ids=[TARGET_SYSTEM_ID], username=self.user)
        query_texts = [item.query_text for item in historical]
        self.assertEqual(query_texts, ["查一下审计中心近七天的操作记录"])
        self.assertNotIn("查下最近七天的日志", query_texts)
        self.assertNotIn("今天天气怎么样", query_texts)

    def test_refresh_common_queries_includes_user_intent(self):
        """定时刷新：USER_INTENT 成功检索同样聚合进用户 × 系统缓存。"""

        self._create_intent_message(
            query_text="intent-q1",
            output={
                "intent": "log_search",
                "system_id": TARGET_SYSTEM_ID,
                "condition": {"scope_type": "system", "scope_id": TARGET_SYSTEM_ID, "conditions": []},
            },
        )
        self._create_intent_message(
            query_text="intent-guidance",
            output={
                "intent": "log_search",
                "error": {"error_code": "SYSTEM_REQUIRED", "error_message": "x", "candidates": []},
            },
        )
        with mock.patch.object(CommonQueryStore, "replace_today") as mock_replace:
            result = OperationContextService.refresh_common_queries()
        replace_calls = {
            (call.kwargs["system_id"], call.kwargs["username"]): call.kwargs["counts"]
            for call in mock_replace.call_args_list
        }
        # 仅成功检索的意图消息进当天桶（引导性输出不计）
        self.assertEqual(replace_calls.get((TARGET_SYSTEM_ID, self.user)), {"intent-q1": 1})
        self.assertEqual(result["scanned_messages"], 1)


class TestMessageExport(AIAssistantPlatformTestCase):
    def setUp(self):
        super().setUp()
        self.service = MessageExportService(user=self.user)

    def test_preview_export_returns_file(self):
        message = self.create_log_search_message()
        export_file = PreviewExportFile(content=b"xlsx-bytes", file_name="AI助手检索导出-abc12345.xlsx")
        with mock.patch(
            "services.web.ai_assistant.services.log_export.PreviewExportService.export",
            return_value=export_file,
        ) as mock_export:
            result = self.service.preview_export(message_uid=str(message.uid))
        mock_export.assert_called_once()
        self.assertEqual(result.content, b"xlsx-bytes")
        self.assertEqual(result.file_name, "AI助手检索导出-abc12345.xlsx")

    def test_preview_export_failure_converted(self):
        """query 侧异常统一转换为平台稳定错误码。"""

        message = self.create_log_search_message()
        with mock.patch(
            "services.web.ai_assistant.services.log_export.PreviewExportService.export",
            side_effect=QueryAIAssistantError(message="快照无样例数据"),
        ):
            with self.assertRaises(LogExportFailed):
                self.service.preview_export(message_uid=str(message.uid))

    def test_full_export_rebuilds_from_snapshot(self):
        """全量导出：条件来自消息输入快照，export_config 仅控制输出列。"""

        message = self.create_log_search_message()
        # 真实形态：bk_resource 序列化后返回 dict（ReturnDict），不支持属性访问
        fake_task = {"id": 123, "status": "PENDING"}
        with mock.patch(
            "services.web.ai_assistant.services.log_export.FullExportService.create_task",
            return_value=fake_task,
        ) as mock_create:
            result = self.service.create_full_export(
                message_uid=str(message.uid),
                export_config={"field_scope": "specified", "fields": [{"raw_name": "username"}]},
            )
        _, kwargs = mock_create.call_args
        self.assertEqual(kwargs["condition"].scope_id, TARGET_SYSTEM_ID)
        self.assertEqual(kwargs["username"], self.user)
        self.assertEqual(kwargs["export_config"]["field_scope"], "specified")
        self.assertTrue(kwargs["task_name"].startswith("AI助手检索导出-"))
        self.assertEqual(result, {"export_task_id": 123, "status": "PENDING"})

    def test_full_export_permission_denied_converted(self):
        message = self.create_log_search_message()
        with mock.patch(
            "services.web.ai_assistant.services.log_export.FullExportService.create_task",
            side_effect=AIPermissionDeniedError(),
        ):
            with self.assertRaises(LogExportPermissionDenied):
                self.service.create_full_export(message_uid=str(message.uid), export_config={})

    def _make_nl_parent_with_extension_fields(self, extension_fields):
        from tests.test_ai_assistant.base import make_selection_output

        selection = self.create_selection_message(output=make_selection_output())
        nl_message = self.create_nl_message(parent=selection)
        nl_message.context_data["system_selection"]["systems"][0]["extension_fields"] = extension_fields
        nl_message.save(update_record=False, update_fields=["context_data"])
        return nl_message

    def test_full_export_auto_injects_extension_keys(self):
        """flatten 开启且未传 extension_keys：从 NL 父消息的系统选择快照自动聚合（前端只传开关）"""

        nl_parent = self._make_nl_parent_with_extension_fields(
            [
                {"raw_name": "extend_data", "keys": ["ticket_id"], "display_name": "工单ID"},
                {"raw_name": "extend_data", "keys": ["operator"], "display_name": "经办人"},
                {"raw_name": "extend_data", "keys": ["ticket_id"], "display_name": "重复子键去重"},
                {"raw_name": "instance_data", "keys": ["name"], "display_name": "非 extend_data 容器忽略"},
                {"raw_name": "extend_data", "keys": [], "display_name": "无子键忽略"},
            ]
        )
        message = self.create_log_search_message(parent=nl_parent)
        fake_task = {"id": 123, "status": "PENDING"}
        with mock.patch(
            "services.web.ai_assistant.services.log_export.FullExportService.create_task",
            return_value=fake_task,
        ) as mock_create:
            self.service.create_full_export(
                message_uid=str(message.uid),
                export_config={"field_scope": "all", "flatten_extension": True, "fields": []},
            )
        _, kwargs = mock_create.call_args
        self.assertEqual(kwargs["export_config"]["extension_keys"], ["ticket_id", "operator"])

    def _make_intent_parent_with_selection(self, selection_output):
        """构造意图链路消息树：系统选择（兄弟消息）→ USER_INTENT 父消息，返回父消息。"""

        from tests.test_ai_assistant.base import make_selection_output as _make

        self.create_selection_message(output=selection_output or _make())
        return Message.objects.create(
            conversation=self.conversation,
            parent_message=None,
            message_type=MessageType.USER_INTENT,
            status=ExecutionStatus.SUCCESS,
            input_data={"query_text": "查一下最近日志", "auto_execute": True},
            context_data={"username": self.user, "namespace": "bkaudit", "scope_type": "cross_system"},
            output_data={"intent": "log_search", "system_id": TARGET_SYSTEM_ID, "selection_message_uid": ""},
            created_by=self.user,
        )

    def test_full_export_auto_injects_extension_keys_from_intent_parent(self):
        """回归：意图链路（一期主链路）父消息为 USER_INTENT 时同样自动聚合注入。

        08-28 实现仅覆盖 NL/SELECTION 两种父消息；09 月 USER_INTENT 上线后 LOG_SEARCH
        父消息变为 USER_INTENT（output 无 systems 快照）→ extension_keys 注入为空
        → 全量导出回退 extend_data 单列 JSON（线上报障"扩展字段不展开"）。修复后
        取检索时点的最新成功系统选择（SELECTION 为兄弟消息）聚合。
        """

        from services.web.query.ai_assistant.schemas import SelectionFieldMeta

        selection_output = make_selection_output()
        selection_output.systems[0].extension_fields = [
            SelectionFieldMeta(raw_name="extend_data", keys=["ticket_id"], display_name="工单ID"),
            SelectionFieldMeta(raw_name="extend_data", keys=["operator"], display_name="经办人"),
        ]
        intent_parent = self._make_intent_parent_with_selection(selection_output)
        message = self.create_log_search_message(parent=intent_parent)
        with mock.patch(
            "services.web.ai_assistant.services.log_export.FullExportService.create_task",
            return_value={"id": 1, "status": "PENDING"},
        ) as mock_create:
            self.service.create_full_export(
                message_uid=str(message.uid),
                export_config={"field_scope": "all", "flatten_extension": True, "fields": []},
            )
        _, kwargs = mock_create.call_args
        self.assertEqual(kwargs["export_config"]["extension_keys"], ["ticket_id", "operator"])

    def test_extract_intent_parent_uses_selection_at_search_time(self):
        """意图父消息：取检索消息创建时点的系统选择，导出前用户已切换系统不受影响（id 上界）。"""

        from services.web.query.ai_assistant.schemas import SelectionFieldMeta

        selection_output = make_selection_output()
        selection_output.systems[0].extension_fields = [
            SelectionFieldMeta(raw_name="extend_data", keys=["ticket_id"], display_name="工单ID"),
        ]
        intent_parent = self._make_intent_parent_with_selection(selection_output)
        message = self.create_log_search_message(parent=intent_parent)
        # 检索完成后用户切换到其他系统（id 更大的新选择）：导出取值不得被后续切换污染
        later_output = make_selection_output(system_id="other-system")
        later_output.systems[0].extension_fields = [
            SelectionFieldMeta(raw_name="extend_data", keys=["strategy_id"], display_name="策略ID"),
        ]
        self.create_selection_message(output=later_output)

        keys = MessageExportService._extract_extension_keys(message)
        self.assertEqual(keys, ["ticket_id"])

    def test_full_export_explicit_extension_keys_not_overridden(self):
        """显式传 extension_keys：后端不覆盖调用方清单"""

        nl_parent = self._make_nl_parent_with_extension_fields(
            [{"raw_name": "extend_data", "keys": ["ticket_id"], "display_name": "工单ID"}]
        )
        message = self.create_log_search_message(parent=nl_parent)
        with mock.patch(
            "services.web.ai_assistant.services.log_export.FullExportService.create_task",
            return_value={"id": 1, "status": "PENDING"},
        ) as mock_create:
            self.service.create_full_export(
                message_uid=str(message.uid),
                export_config={
                    "field_scope": "all",
                    "flatten_extension": True,
                    "extension_keys": ["custom_key"],
                    "fields": [],
                },
            )
        _, kwargs = mock_create.call_args
        self.assertEqual(kwargs["export_config"]["extension_keys"], ["custom_key"])

    def test_full_export_ai_standard_scope_translated(self):
        """ai_standard scope：翻译为 SPECIFIED + 快照默认展示列（与预览导出字段一致），flatten 照常注入"""

        nl_parent = self._make_nl_parent_with_extension_fields(
            [{"raw_name": "extend_data", "keys": ["ticket_id"], "display_name": "工单ID"}]
        )
        message = self.create_log_search_message(parent=nl_parent)
        with mock.patch(
            "services.web.ai_assistant.services.log_export.FullExportService.create_task",
            return_value={"id": 1, "status": "PENDING"},
        ) as mock_create:
            self.service.create_full_export(
                message_uid=str(message.uid),
                export_config={"field_scope": "ai_standard", "flatten_extension": True, "fields": []},
            )
        _, kwargs = mock_create.call_args
        export_config = kwargs["export_config"]
        # ① 翻译为 SPECIFIED：fields = 快照默认展示列（raw_name + 产品文案），与预览导出同构
        self.assertEqual(export_config["field_scope"], "specified")
        self.assertEqual(
            export_config["fields"],
            [
                {"raw_name": raw_name, "display_name": display_name, "keys": []}
                for raw_name, display_name in SNAPSHOT_DEFAULT_COLUMNS
            ],
        )
        # ② flatten 开启：extension_keys 从父消息自动聚合注入（平铺列替换 extend_data 单列）
        self.assertEqual(export_config["extension_keys"], ["ticket_id"])

    def test_full_export_no_flatten_no_injection(self):
        """flatten 未开启：不聚合不注入（原检索页语义零变化）"""

        nl_parent = self._make_nl_parent_with_extension_fields(
            [{"raw_name": "extend_data", "keys": ["ticket_id"], "display_name": "工单ID"}]
        )
        message = self.create_log_search_message(parent=nl_parent)
        with mock.patch(
            "services.web.ai_assistant.services.log_export.FullExportService.create_task",
            return_value={"id": 1, "status": "PENDING"},
        ) as mock_create:
            self.service.create_full_export(
                message_uid=str(message.uid),
                export_config={"field_scope": "all", "fields": []},
            )
        _, kwargs = mock_create.call_args
        self.assertNotIn("extension_keys", kwargs["export_config"])

    def test_extract_extension_keys_from_selection_parent(self):
        """父为系统选择消息：走 output_data.systems 路径同样聚合"""

        from services.web.query.ai_assistant.schemas import SelectionFieldMeta
        from tests.test_ai_assistant.base import make_selection_output

        selection_output = make_selection_output()
        selection_output.systems[0].extension_fields = [
            SelectionFieldMeta(raw_name="extend_data", keys=["ticket_id"], display_name="工单ID")
        ]
        selection_message = self.create_selection_message(output=selection_output)
        message = self.create_log_search_message(parent=selection_message)

        keys = MessageExportService._extract_extension_keys(message)
        self.assertEqual(keys, ["ticket_id"])

    def test_extract_extension_keys_no_parent(self):
        """无父消息（如历史数据）：返回空清单（平铺退化不生效，不报错）"""

        message = self.create_log_search_message()
        self.assertEqual(MessageExportService._extract_extension_keys(message), [])

    def test_export_rejects_non_success_message(self):
        """仅成功的日志检索消息支持导出。"""

        processing_message = self.create_log_search_message()
        processing_message.status = ExecutionStatus.PROCESSING
        processing_message.save(update_record=False, update_fields=["status"])
        with self.assertRaises(InvalidMessageState):
            self.service.preview_export(message_uid=str(processing_message.uid))

    def test_export_rejects_corrupted_output_snapshot(self):
        """输出快照损坏（非法结构）返回稳定错误而非 500。"""

        message = self.create_log_search_message()
        message.output_data = {"total": "not-an-int"}
        message.save(update_record=False, update_fields=["output_data"])
        with self.assertRaises(InvalidMessageSnapshot):
            self.service.preview_export(message_uid=str(message.uid))

    def test_export_rejects_other_users_message(self):
        message = self.create_log_search_message()
        other_service = MessageExportService(user="other_user")
        with self.assertRaises(MessageNotFound):
            other_service.preview_export(message_uid=str(message.uid))

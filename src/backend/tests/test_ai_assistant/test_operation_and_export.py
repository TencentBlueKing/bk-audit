# -*- coding: utf-8 -*-
"""常见/历史操作与消息导出测试。"""

from unittest import mock

from services.web.ai_assistant.constants import ExecutionStatus
from services.web.ai_assistant.exceptions import (
    InvalidMessageSnapshot,
    InvalidMessageState,
    LogExportFailed,
    LogExportPermissionDenied,
    MessageNotFound,
)
from services.web.ai_assistant.schemas.audit_search import CommonQuerySchema
from services.web.ai_assistant.services.log_export import MessageExportService
from services.web.ai_assistant.services.operation import (
    CommonQueryStore,
    OperationContextService,
)
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

    def test_list_reads_lrange(self):
        store = self._make_store(**{"lrange.return_value": ["查登录失败", "查导出记录"]})
        items = store.list(TARGET_SYSTEM_ID, self.user, limit=10)
        self.assertEqual([item.query_text for item in items], ["查登录失败", "查导出记录"])
        store.redis_client.lrange.assert_called_once_with(
            f"bk_audit:ai_assistant:common_queries:{TARGET_SYSTEM_ID}:{self.user}", 0, 9
        )

    def test_list_redis_error_returns_empty(self):
        import redis

        store = self._make_store(**{"lrange.side_effect": redis.RedisError("down")})
        self.assertEqual(store.list(TARGET_SYSTEM_ID, self.user, limit=10), [])

    def test_replace_deletes_and_pushes(self):
        store = self._make_store()
        store.replace(TARGET_SYSTEM_ID, self.user, ["q1", "q2", ""])
        pipeline = store.redis_client.pipeline.return_value
        pipeline.delete.assert_called_once()
        pipeline.rpush.assert_called_once_with(
            f"bk_audit:ai_assistant:common_queries:{TARGET_SYSTEM_ID}:{self.user}", "q1", "q2"
        )
        pipeline.execute.assert_called_once()


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
        """常见操作：仅读取当前用户 × 系统的缓存，不串看其他用户样例。"""

        with mock.patch.object(
            CommonQueryStore,
            "list",
            side_effect=lambda system_id, username, limit: (
                [CommonQuerySchema(query_text=f"{username}-q")] if username == self.user else []
            ),
        ) as mock_list:
            common = OperationContextService.build_common(system_ids=[TARGET_SYSTEM_ID], username=self.user)
        self.assertEqual([item.query_text for item in common], [f"{self.user}-q"])
        mock_list.assert_called_once_with(TARGET_SYSTEM_ID, self.user, limit=mock.ANY)

    def test_refresh_common_queries_aggregates(self):
        """定时刷新：按用户 × 系统聚合最近样例并整表替换（用户间隔离）。"""

        selection = self.create_selection_message()
        self.create_nl_message(query_text="q1", parent=selection)
        self.create_nl_message(query_text="q2", parent=selection)
        # 其他用户的样例进入独立缓存，不与当前用户混合
        other_message = self.create_nl_message(query_text="other-q", parent=selection)
        other_message.created_by = "other_user"
        other_message.save(update_record=False, update_fields=["created_by"])
        with mock.patch.object(CommonQueryStore, "replace") as mock_replace:
            result = OperationContextService.refresh_common_queries()
        replace_calls = {call.args[:2]: call.args[2] for call in mock_replace.call_args_list}
        self.assertEqual(
            replace_calls.get((TARGET_SYSTEM_ID, self.user)),
            ["q2", "q1"],  # 最近在前
        )
        self.assertEqual(replace_calls.get((TARGET_SYSTEM_ID, "other_user")), ["other-q"])
        self.assertEqual(result, {"refreshed_systems": 2, "scanned_messages": 3})


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

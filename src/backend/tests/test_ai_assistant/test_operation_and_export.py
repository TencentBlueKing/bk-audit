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
        items = store.list(TARGET_SYSTEM_ID, limit=10)
        self.assertEqual([item.query_text for item in items], ["查登录失败", "查导出记录"])
        store.redis_client.lrange.assert_called_once_with(
            f"bk_audit:ai_assistant:common_queries:{TARGET_SYSTEM_ID}", 0, 9
        )

    def test_list_redis_error_returns_empty(self):
        import redis

        store = self._make_store(**{"lrange.side_effect": redis.RedisError("down")})
        self.assertEqual(store.list(TARGET_SYSTEM_ID, limit=10), [])

    def test_replace_deletes_and_pushes(self):
        store = self._make_store()
        store.replace(TARGET_SYSTEM_ID, ["q1", "q2", ""])
        pipeline = store.redis_client.pipeline.return_value
        pipeline.delete.assert_called_once()
        pipeline.rpush.assert_called_once_with(f"bk_audit:ai_assistant:common_queries:{TARGET_SYSTEM_ID}", "q1", "q2")
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

    def test_refresh_common_queries_aggregates(self):
        """定时刷新：按系统聚合最近样例并整表替换。"""

        selection = self.create_selection_message()
        self.create_nl_message(query_text="q1", parent=selection)
        self.create_nl_message(query_text="q2", parent=selection)
        with mock.patch.object(CommonQueryStore, "replace") as mock_replace:
            result = OperationContextService.refresh_common_queries()
        mock_replace.assert_called_once()
        args = mock_replace.call_args[0]
        self.assertEqual(args[0], TARGET_SYSTEM_ID)
        self.assertEqual(args[1], ["q2", "q1"])  # 最近在前
        self.assertEqual(result, {"refreshed_systems": 1, "scanned_messages": 2})


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

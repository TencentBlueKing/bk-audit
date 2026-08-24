# -*- coding: utf-8 -*-
"""三类消息 Handler 测试：prepare 校验、parent 兜底解析、执行模式。"""

from unittest import mock

from services.web.ai_assistant.constants import ExecutionStatus, MessageType
from services.web.ai_assistant.exceptions import (
    InvalidMessageSnapshot,
    InvalidParentMessage,
    SystemSelectionRequired,
)
from services.web.ai_assistant.handlers.audit_search import (
    LogSearchHandler,
    NaturalLanguageSearchHandler,
    SystemSelectionHandler,
)
from services.web.ai_assistant.schemas.audit_search import (
    LogSearchInputSchema,
    NLSearchInputSchema,
    SystemSelectionInputSchema,
)
from tests.test_ai_assistant.base import (
    TARGET_SYSTEM_ID,
    AIAssistantPlatformTestCase,
    make_condition,
    make_log_search_output,
    make_selection_output,
)


class TestSystemSelectionHandler(AIAssistantPlatformTestCase):
    def setUp(self):
        super().setUp()
        self.handler = SystemSelectionHandler()

    def test_prepare_rejects_parent(self):
        """系统选择是根消息，不允许携带父消息。"""

        parent = self.create_selection_message()
        with self.assertRaises(InvalidParentMessage):
            self.handler.prepare(
                user=self.user,
                conversation=self.conversation,
                parent_message=parent,
                input_data=SystemSelectionInputSchema(system_ids=[TARGET_SYSTEM_ID]),
            )

    def test_prepare_builds_server_context(self):
        preparation = self.handler.prepare(
            user=self.user,
            conversation=self.conversation,
            parent_message=None,
            input_data=SystemSelectionInputSchema(system_ids=[TARGET_SYSTEM_ID]),
        )
        self.assertIsNone(preparation.parent_message)
        self.assertEqual(preparation.context_data.username, self.user)
        self.assertTrue(preparation.context_data.namespace)

    def test_execute_assembles_fields_and_operations(self):
        """execute 组装字段上下文 + 常见/历史操作。"""

        from services.web.ai_assistant.schemas.audit_search import CommonQuerySchema

        with self.patch_field_context() as mock_build, self.patch_operation_context(
            return_common=[CommonQuerySchema(query_text="查登录失败")],
            return_historical=[CommonQuerySchema(query_text="查 admin 删除")],
        ):
            output = self.handler.execute(
                input_data=SystemSelectionInputSchema(system_ids=[TARGET_SYSTEM_ID]),
                context_data=SystemSelectionHandler.context_model(username=self.user, namespace="bkaudit"),
            )
        mock_build.assert_called_once()
        self.assertEqual(output.systems[0].system_id, TARGET_SYSTEM_ID)
        self.assertEqual(output.common_operations[0].query_text, "查登录失败")
        self.assertEqual(output.historical_operations[0].query_text, "查 admin 删除")


class TestNaturalLanguageSearchHandler(AIAssistantPlatformTestCase):
    def setUp(self):
        super().setUp()
        self.handler = NaturalLanguageSearchHandler()
        self.input = NLSearchInputSchema(query_text="查一下 admin 的日志")

    def test_prepare_resolves_latest_selection_without_parent(self):
        """前端不传 parent 时，后端绑定最新成功系统选择消息。"""

        old_selection = self.create_selection_message()
        latest_selection = self.create_selection_message()
        self.assertGreater(latest_selection.id, old_selection.id)
        preparation = self.handler.prepare(
            user=self.user,
            conversation=self.conversation,
            parent_message=None,
            input_data=self.input,
        )
        self.assertEqual(preparation.parent_message.id, latest_selection.id)

    def test_prepare_without_selection_raises(self):
        """当前会话无成功选择时返回稳定错误。"""

        with self.assertRaises(SystemSelectionRequired):
            self.handler.prepare(
                user=self.user,
                conversation=self.conversation,
                parent_message=None,
                input_data=self.input,
            )

    def test_prepare_with_explicit_invalid_parent_rejected(self):
        """显式传入的父消息类型错误时拒绝。"""

        nl_parent = self.create_nl_message()
        with self.assertRaises(InvalidParentMessage):
            self.handler.prepare(
                user=self.user,
                conversation=self.conversation,
                parent_message=nl_parent,
                input_data=self.input,
            )

    def test_prepare_copies_context_snapshot(self):
        """上下文从父消息复制最小充分字段上下文（协议 §7.2）。"""

        selection = make_selection_output()
        self.create_selection_message(output=selection)
        preparation = self.handler.prepare(
            user=self.user,
            conversation=self.conversation,
            parent_message=None,
            input_data=self.input,
        )
        context = preparation.context_data
        self.assertEqual(context.scope_id, TARGET_SYSTEM_ID)
        self.assertEqual(context.system_selection.systems[0].system_id, TARGET_SYSTEM_ID)
        self.assertEqual(len(context.system_selection.systems[0].extension_fields), 1)

    def test_prepare_with_empty_output_snapshot_rejected(self):
        """父选择消息输出缺失时拒绝（快照损坏防御）。"""

        selection_message = self.create_selection_message()
        selection_message.output_data = {}
        selection_message.save(update_record=False, update_fields=["output_data"])
        with self.assertRaises(InvalidMessageSnapshot):
            self.handler.prepare(
                user=self.user,
                conversation=self.conversation,
                parent_message=None,
                input_data=self.input,
            )


class TestLogSearchHandler(AIAssistantPlatformTestCase):
    def setUp(self):
        super().setUp()
        self.handler = LogSearchHandler()

    def _prepare(self, parent=None, condition=None):
        return self.handler.prepare(
            user=self.user,
            conversation=self.conversation,
            parent_message=parent,
            input_data=LogSearchInputSchema(condition=condition or make_condition()),
        )

    def test_prepare_with_selection_parent(self):
        """字段条件检索：显式系统选择父消息，source=field_condition。"""

        selection = self.create_selection_message()
        preparation = self._prepare(parent=selection)
        self.assertEqual(preparation.parent_message.id, selection.id)
        self.assertEqual(preparation.context_data.source, "field_condition")
        self.assertEqual(preparation.context_data.system_id, TARGET_SYSTEM_ID)

    def test_prepare_with_nl_parent(self):
        """NL 续链：自然语言父消息，source=natural_language。"""

        selection = self.create_selection_message()
        nl_message = self.create_nl_message(parent=selection, condition=make_condition())
        preparation = self._prepare(parent=nl_message)
        self.assertEqual(preparation.parent_message.id, nl_message.id)
        self.assertEqual(preparation.context_data.source, "natural_language")

    def test_prepare_resolves_latest_selection_fallback(self):
        """未传 parent 时兜底解析最新成功系统选择。"""

        self.create_selection_message()
        latest = self.create_selection_message()
        preparation = self._prepare(parent=None)
        self.assertEqual(preparation.parent_message.id, latest.id)

    def test_prepare_rejects_scope_mismatch(self):
        """检索系统与所选系统不一致时拒绝（防构造未选择系统的条件）。"""

        self.create_selection_message()
        with self.assertRaises(InvalidParentMessage):
            self._prepare(condition=make_condition(system_id="other_system"))

    def test_prepare_rejects_invalid_parent_type(self):
        """父消息类型非法时拒绝。"""

        selection = self.create_selection_message()
        log_message = self.create_log_search_message(parent=selection)
        with self.assertRaises(InvalidParentMessage):
            self._prepare(parent=log_message)

    def test_execute_calls_search_service(self):
        """execute 同步调 LogSearchService 并零转换组装平台快照。"""

        query_output = make_log_search_output(total=3)
        with mock.patch(
            "services.web.ai_assistant.handlers.audit_search.LogSearchService.search",
            return_value=query_output,
        ) as mock_search:
            output = self.handler.execute(
                input_data=LogSearchInputSchema(condition=make_condition()),
                context_data=LogSearchHandler.context_model(
                    username=self.user,
                    namespace="bkaudit",
                    system_id=TARGET_SYSTEM_ID,
                    source="field_condition",
                ),
            )
        mock_search.assert_called_once()
        _, kwargs = mock_search.call_args
        self.assertEqual(kwargs["source"], "field_condition")
        self.assertEqual(kwargs["username"], self.user)
        self.assertEqual(output.total, 3)
        self.assertEqual(len(output.samples), 3)

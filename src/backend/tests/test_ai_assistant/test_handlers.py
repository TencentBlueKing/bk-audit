# -*- coding: utf-8 -*-
"""三类消息 Handler 测试：prepare 校验、parent 兜底解析、执行模式。"""

from unittest import mock

from services.web.ai_assistant.exceptions import (
    InvalidParentMessage,
    SystemSelectionPermissionDenied,
)
from services.web.ai_assistant.handlers.audit_search import (
    LogSearchHandler,
    SystemSelectionHandler,
)
from services.web.ai_assistant.schemas.audit_search import (
    LogSearchInputSchema,
    SystemSelectionInputSchema,
)
from tests.test_ai_assistant.base import (
    TARGET_SYSTEM_ID,
    AIAssistantPlatformTestCase,
    make_condition,
    make_log_search_output,
    make_selection_output,
)

# 测试默认 scope：cross_system 是宽松语义，单元测试不关心具体场景，
# 仅校验 SystemSelectionInputSchema 的协议形态（scope 必填校验）
DEFAULT_SCOPE_TYPE = "cross_system"
DEFAULT_SCOPE_ID = ""


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
                input_data=SystemSelectionInputSchema(
                    system_ids=[TARGET_SYSTEM_ID],
                    scope_type=DEFAULT_SCOPE_TYPE,
                ),
            )

    def test_prepare_builds_server_context(self):
        preparation = self.handler.prepare(
            user=self.user,
            conversation=self.conversation,
            parent_message=None,
            input_data=SystemSelectionInputSchema(
                system_ids=[TARGET_SYSTEM_ID],
                scope_type=DEFAULT_SCOPE_TYPE,
            ),
        )
        self.assertIsNone(preparation.parent_message)
        self.assertEqual(preparation.context_data.username, self.user)
        self.assertTrue(preparation.context_data.namespace)
        # session scope 随消息快照固化
        self.assertEqual(preparation.context_data.scope_type, DEFAULT_SCOPE_TYPE)

    def test_execute_assembles_fields_and_operations(self):
        """execute 组装字段上下文 + 常见/历史操作。"""

        from services.web.ai_assistant.schemas.audit_search import CommonQuerySchema

        with self.patch_field_context() as mock_build, self.patch_operation_context(
            return_common=[CommonQuerySchema(query_text="查登录失败")],
            return_historical=[CommonQuerySchema(query_text="查 admin 删除")],
        ), mock.patch(
            "services.web.ai_assistant.handlers.audit_search.SearchLogPermission.get_scope_auth_systems",
            return_value=[TARGET_SYSTEM_ID],
        ):
            output = self.handler.execute(
                input_data=SystemSelectionInputSchema(
                    system_ids=[TARGET_SYSTEM_ID],
                    scope_type=DEFAULT_SCOPE_TYPE,
                ),
                context_data=SystemSelectionHandler.context_model(
                    username=self.user,
                    namespace="bkaudit",
                    scope_type=DEFAULT_SCOPE_TYPE,
                ),
            )
        mock_build.assert_called_once()
        self.assertEqual(output.systems[0].system_id, TARGET_SYSTEM_ID)
        self.assertEqual(output.common_operations[0].query_text, "查登录失败")
        self.assertEqual(output.historical_operations[0].query_text, "查 admin 删除")

    def test_execute_scope_rejects_out_of_scope_system(self):
        """session scope 校验：system_ids 不在 scope 候选内时拒绝（防 AI 跨场景越权）"""

        with self.assertRaises(SystemSelectionPermissionDenied):
            self.handler.execute(
                input_data=SystemSelectionInputSchema(
                    system_ids=["other_system"],
                    scope_type="scene",
                    scope_id="1",
                ),
                context_data=SystemSelectionHandler.context_model(
                    username=self.user,
                    namespace="bkaudit",
                    scope_type="scene",
                    scope_id="1",
                ),
            )

    def test_execute_operation_ranking_filtered_by_scope(self):
        """操作榜单按 session scope 候选系统集过滤（切换场景榜单随场景变化）"""

        with self.patch_field_context(), self.patch_operation_context() as mock_build, mock.patch(
            "services.web.ai_assistant.handlers.audit_search.SearchLogPermission.get_scope_auth_systems",
            # scope 候选含所选系统（校验通过）+ 场景内其他系统 + ES 兜底空串
            return_value=["sys_b", TARGET_SYSTEM_ID, "sys_a", ""],
        ):
            self.handler.execute(
                input_data=SystemSelectionInputSchema(
                    system_ids=[TARGET_SYSTEM_ID],
                    scope_type="scene",
                    scope_id="1",
                ),
                context_data=SystemSelectionHandler.context_model(
                    username=self.user,
                    namespace="bkaudit",
                    scope_type="scene",
                    scope_id="1",
                ),
            )
        # 榜单收到的是 scope 候选系统集（排序去空串），而非仅所选系统
        _, build_kwargs = mock_build.call_args
        self.assertEqual(build_kwargs["system_ids"], ["bk_log", "sys_a", "sys_b"])

    def test_execute_operation_ranking_falls_back_without_scope(self):
        """无 scope（历史消息兜底）：榜单沿用所选系统（原行为）"""

        with self.patch_field_context(), self.patch_operation_context() as mock_build:
            self.handler.execute(
                input_data=SystemSelectionInputSchema(
                    system_ids=[TARGET_SYSTEM_ID],
                    scope_type="cross_system",
                ),
                context_data=SystemSelectionHandler.context_model(
                    username=self.user,
                    namespace="bkaudit",
                    scope_type="",
                    scope_id="",
                ),
            )
        _, build_kwargs = mock_build.call_args
        self.assertEqual(build_kwargs["system_ids"], [TARGET_SYSTEM_ID])

    def test_execute_permission_denied_converted(self):
        """所选系统均无检索权限时转为平台稳定错误（403），不误报为 AI 识别失败。"""

        from services.web.query.ai_assistant.exceptions import AIPermissionDeniedError

        with mock.patch(
            # scope 校验放行（system_ids 在 scope 候选内），让执行到达 build_selection；
            # 不 mock 会真实调用 IAM 策略接口，CI 无外网时连接失败（AuthAPIError）
            "services.web.ai_assistant.handlers.audit_search.SearchLogPermission.get_scope_auth_systems",
            return_value=["no_perm_system"],
        ), mock.patch(
            "services.web.ai_assistant.handlers.audit_search.FieldContextService.build_selection",
            side_effect=AIPermissionDeniedError(),
        ):
            with self.assertRaises(SystemSelectionPermissionDenied):
                self.handler.execute(
                    input_data=SystemSelectionInputSchema(
                        system_ids=["no_perm_system"],
                        scope_type=DEFAULT_SCOPE_TYPE,
                    ),
                    context_data=SystemSelectionHandler.context_model(
                        username=self.user,
                        namespace="bkaudit",
                        scope_type=DEFAULT_SCOPE_TYPE,
                    ),
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
        # session scope 从父消息继承（场景内工具链路一致性）
        self.assertEqual(preparation.context_data.session_scope_type, self.default_scope_type)

    def test_prepare_with_nl_parent(self):
        """用户意图续链：父消息为 USER_INTENT，source=natural_language。"""

        selection = self.create_selection_message()
        nl_message = self.create_nl_message(parent=selection, condition=make_condition())
        with mock.patch(
            "services.web.ai_assistant.handlers.audit_search.FieldContextService.build_selection",
            return_value=make_selection_output(),
        ):
            preparation = self._prepare(parent=nl_message)
        self.assertEqual(preparation.parent_message.id, nl_message.id)
        self.assertEqual(preparation.context_data.source, "natural_language")

    def test_prepare_inherits_session_scope_from_nl_parent(self):
        """用户意图父消息的 session scope 取上下文 scope_type/scope_id。"""

        selection = self.create_selection_message()
        nl_message = self.create_nl_message(parent=selection, condition=make_condition())
        with mock.patch(
            "services.web.ai_assistant.handlers.audit_search.FieldContextService.build_selection",
            return_value=make_selection_output(),
        ):
            preparation = self._prepare(parent=nl_message)
        self.assertEqual(preparation.context_data.session_scope_type, self.default_scope_type)
        self.assertEqual(preparation.context_data.session_scope_id, self.default_scope_id)

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
                    # session scope 从父消息继承（场景内工具的强约束）
                    session_scope_type="scene",
                    session_scope_id="1",
                ),
            )
        mock_search.assert_called_once()
        _, kwargs = mock_search.call_args
        self.assertEqual(kwargs["source"], "field_condition")
        self.assertEqual(kwargs["username"], self.user)
        self.assertEqual(kwargs["session_scope_type"], "scene")
        self.assertEqual(kwargs["session_scope_id"], "1")
        self.assertEqual(output.total, 3)
        self.assertEqual(len(output.samples), 3)

# -*- coding: utf-8 -*-
"""日志工具严格查询上下文测试。"""

from unittest import mock

from core.exceptions import PermissionException
from services.web.query.ai_assistant.exceptions import InvalidLogCondition
from services.web.query.ai_assistant.log_tools.context import LogQueryContextService
from services.web.query.serializers import CollectorSearchAllReqSerializer
from tests.test_query.test_ai_assistant.base import AIAssistantTestCase

CONTEXT_MODULE = "services.web.query.ai_assistant.log_tools.context"


class TestLogQueryContextService(AIAssistantTestCase):
    """Context 只完成鉴权、DRF 条件校验和服务端表解析。"""

    def _permission_exception(self):
        return PermissionException(action_name="view_system", permission={}, apply_url="")

    def test_denied_scope_raises_before_condition_validation(self):
        with (
            mock.patch(
                f"{CONTEXT_MODULE}.SearchLogPermission._get_system_scope_system_ids",
                return_value=set(),
            ),
            mock.patch(
                f"{CONTEXT_MODULE}.SearchLogPermission._get_scene_scope_system_ids",
                return_value=set(),
            ),
            mock.patch(
                f"{CONTEXT_MODULE}.SearchLogPermission.raise_system_view_permission_exception",
                side_effect=self._permission_exception(),
            ) as raise_permission,
            mock.patch.object(CollectorSearchAllReqSerializer, "is_valid") as validate,
        ):
            with self.assertRaises(PermissionException):
                LogQueryContextService.build(
                    username=self.username,
                    namespace=self.namespace,
                    condition=self.make_condition(),
                )

        raise_permission.assert_called_once_with(username=self.username)
        validate.assert_not_called()

    def test_scene_granted_system_scope_filters_the_requested_system(self):
        condition = self.make_condition(
            conditions=[self.make_field_condition(raw_name="username", operator="eq", filters=["alice"])]
        )
        with (
            mock.patch(
                f"{CONTEXT_MODULE}.SearchLogPermission._get_system_scope_system_ids",
                return_value=set(),
            ),
            mock.patch(
                f"{CONTEXT_MODULE}.SearchLogPermission._get_scene_scope_system_ids",
                return_value={self.target_system_id},
            ),
            mock.patch(
                f"{CONTEXT_MODULE}.SearchLogPermission.get_scope_auth_systems",
                side_effect=AssertionError("strict context must not perform a second scope authorization lookup"),
            ),
            mock.patch(
                f"{CONTEXT_MODULE}.CollectorPlugin.build_collector_rt", return_value="server_rt.doris"
            ) as build_rt,
        ):
            context = LogQueryContextService.build(
                username=self.username,
                namespace=self.namespace,
                condition=condition,
            )

        self.assertEqual(context.username, self.username)
        self.assertEqual(context.namespace, self.namespace)
        self.assertEqual(context.condition, condition)
        self.assertEqual(context.table, "server_rt.doris")
        self.assertEqual(context.conditions[0]["field"]["raw_name"], "system_id")
        self.assertEqual(context.conditions[0]["filters"], [self.target_system_id])
        self.assertEqual(
            [item["field"]["raw_name"] for item in context.conditions[1:5]],
            [
                "thedate",
                "thedate",
                "dtEventTimeStamp",
                "dtEventTimeStamp",
            ],
        )
        self.assertEqual(context.conditions[-1]["field"]["raw_name"], "username")
        build_rt.assert_called_once_with(self.namespace)

    def test_context_snapshots_the_original_condition(self):
        condition = self.make_condition(
            conditions=[self.make_field_condition(raw_name="username", operator="eq", filters=["alice"])]
        )
        with (
            mock.patch(
                f"{CONTEXT_MODULE}.SearchLogPermission._get_system_scope_system_ids",
                return_value={self.target_system_id},
            ),
            mock.patch(
                f"{CONTEXT_MODULE}.SearchLogPermission._get_scene_scope_system_ids",
                return_value=set(),
            ),
            mock.patch(
                f"{CONTEXT_MODULE}.SearchLogPermission.get_scope_auth_systems",
                side_effect=AssertionError("strict context must not perform a second scope authorization lookup"),
            ),
            mock.patch(f"{CONTEXT_MODULE}.CollectorPlugin.build_collector_rt", return_value="server_rt.doris"),
        ):
            context = LogQueryContextService.build(
                username=self.username,
                namespace=self.namespace,
                condition=condition,
            )

        condition.conditions[0].field.raw_name = "system_id"
        condition.conditions[0].filters[:] = ["changed"]
        condition.conditions.append(self.make_field_condition(raw_name="action_id", filters=["delete"]))

        self.assertEqual(context.condition.conditions[0].field.raw_name, "username")
        self.assertEqual(context.condition.conditions[0].filters, ["alice"])
        self.assertEqual(len(context.condition.conditions), 1)
        self.assertEqual(context.conditions[-1]["field"]["raw_name"], "username")
        self.assertEqual(context.conditions[-1]["filters"], ["alice"])

    def test_invalid_operator_is_mapped_to_fixed_log_tool_exception(self):
        condition = self.make_condition(
            conditions=[self.make_field_condition(raw_name="username", operator="like", filters=["alice"])]
        )
        with mock.patch(f"{CONTEXT_MODULE}.SearchLogPermission.has_system_search_permission", return_value=True):
            with self.assertRaises(InvalidLogCondition) as raised:
                LogQueryContextService.build(
                    username=self.username,
                    namespace=self.namespace,
                    condition=condition,
                )

        self.assertEqual(raised.exception.message, str(InvalidLogCondition.MESSAGE))

    def test_reversed_time_range_is_rejected_after_authorization(self):
        condition = self.make_condition(
            start_time="2026-08-14T00:00:00+08:00",
            end_time="2026-08-13T00:00:00+08:00",
        )
        with mock.patch(f"{CONTEXT_MODULE}.SearchLogPermission.has_system_search_permission", return_value=True):
            with self.assertRaises(InvalidLogCondition):
                LogQueryContextService.build(
                    username=self.username,
                    namespace=self.namespace,
                    condition=condition,
                )

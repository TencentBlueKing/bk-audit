# -*- coding: utf-8 -*-
"""日志工具严格查询上下文测试。"""

from unittest import mock

from core.exceptions import PermissionException
from services.web.query.ai_assistant.exceptions import (
    InvalidLogCondition,
    LogQueryFailed,
)
from services.web.query.ai_assistant.log_tools.context import LogQueryContextService
from services.web.query.ai_assistant.log_tools.schemas import LogFieldRef
from services.web.query.ai_assistant.log_tools.sql import ProjectedLogSQLBuilder
from services.web.query.serializers import CollectorSearchAllReqSerializer
from tests.test_query.test_ai_assistant.base import AIAssistantTestCase

CONTEXT_MODULE = "services.web.query.ai_assistant.log_tools.context"


class TestLogQueryContextService(AIAssistantTestCase):
    """Context 只完成鉴权、DRF 条件校验和服务端表解析。"""

    def setUp(self):
        super().setUp()
        systems = self.enterContext(mock.patch(f"{CONTEXT_MODULE}.System.objects.filter"))
        systems.return_value.exists.return_value = True

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
        # 使用真实 Collector 规范化结果验证完整 SQL，防止只验证字段存在而漏掉条件组合。
        builder = ProjectedLogSQLBuilder(
            table=context.table, conditions=list(context.conditions), sort_list=[], page=2, page_size=20
        )
        where = (
            " FROM server_rt.doris WHERE `system_id` IN ('bk_log')"
            " AND `thedate`>='20260813' AND `thedate`<='20260814'"
            " AND `dtEventTimeStamp`>=1786550400000 AND `dtEventTimeStamp`<=1786636800000"
            " AND `username`='alice'"
        )
        self.assertEqual(
            builder.build_data_sql([LogFieldRef(raw_name="username")]),
            "SELECT `username`" + where + " LIMIT 20 OFFSET 20",
        )
        self.assertEqual(builder.build_count_sql(), "SELECT COUNT(*) `count`" + where + " LIMIT 1")

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

    def test_json_keys_keep_whitespace_without_changing_web_validation(self):
        """JSON key 是精确名称；工具校验不得裁剪它，也不能改变 Web 序列化器默认行为。"""

        for key in (" token ", " ", " 中文 "):
            with self.subTest(key=key):
                condition = self.make_condition(
                    conditions=[self.make_field_condition(raw_name="extend_data", keys=[key])]
                )
                with (
                    mock.patch(f"{CONTEXT_MODULE}.SearchLogPermission.has_system_search_permission", return_value=True),
                    mock.patch(f"{CONTEXT_MODULE}.CollectorPlugin.build_collector_rt", return_value="test_table"),
                ):
                    context = LogQueryContextService.build(
                        username=self.username, namespace=self.namespace, condition=condition
                    )
                self.assertEqual(context.condition.conditions[0].field.keys, [key])
                self.assertEqual(context.conditions[-1]["field"]["keys"], [key])
                sql = ProjectedLogSQLBuilder(
                    table=context.table, conditions=list(context.conditions), sort_list=[], page=1, page_size=1
                ).build_data_sql([LogFieldRef(raw_name="extend_data", keys=[key])])
                # 投影和过滤都使用同一个原始 JSON key，而不是只在上下文中保留。
                self.assertEqual(sql.count(f'$."{key}"'), 2, sql)

        web_serializer = CollectorSearchAllReqSerializer(
            data={
                "namespace": self.namespace,
                "start_time": self.start_time,
                "end_time": self.end_time,
                "page": 1,
                "page_size": 1,
                "conditions": [self.make_field_condition(raw_name="extend_data", keys=[" token "]).model_dump()],
            }
        )
        self.assertTrue(web_serializer.is_valid(), web_serializer.errors)
        self.assertEqual(web_serializer.validated_data["conditions"][-1]["field"]["keys"], ["token"])

    def test_table_resolution_failure_is_mapped_without_leaking_namespace_details(self):
        internal_error = RuntimeError("collector_plugin_id for secret-namespace is missing")
        with (
            mock.patch(f"{CONTEXT_MODULE}.SearchLogPermission.has_system_search_permission", return_value=True),
            mock.patch(f"{CONTEXT_MODULE}.CollectorPlugin.build_collector_rt", side_effect=internal_error),
        ):
            with self.assertRaises(LogQueryFailed) as raised:
                LogQueryContextService.build(
                    username=self.username,
                    namespace=self.namespace,
                    condition=self.make_condition(),
                )

        self.assertNotIn("secret-namespace", raised.exception.message)

    def test_scope_outside_namespace_is_rejected_before_table_resolution(self):
        with (
            mock.patch(f"{CONTEXT_MODULE}.SearchLogPermission.has_system_search_permission", return_value=True),
            mock.patch(f"{CONTEXT_MODULE}.System.objects.filter") as systems,
            mock.patch(f"{CONTEXT_MODULE}.CollectorPlugin.build_collector_rt") as build_rt,
        ):
            systems.return_value.exists.return_value = False
            with self.assertRaises(InvalidLogCondition):
                LogQueryContextService.build(
                    username=self.username,
                    namespace="other-namespace",
                    condition=self.make_condition(),
                )

        build_rt.assert_not_called()

    def test_context_keeps_authorized_system_condition_ahead_of_user_conditions(self):
        condition = self.make_condition(
            conditions=[self.make_field_condition(raw_name="username", operator="eq", filters=["alice"])]
        )
        with (
            mock.patch(
                f"{CONTEXT_MODULE}.SearchLogPermission.has_system_search_permission",
                return_value=True,
            ),
            mock.patch(f"{CONTEXT_MODULE}.CollectorPlugin.build_collector_rt", return_value="server_rt.doris"),
        ):
            context = LogQueryContextService.build(
                username=self.username,
                namespace=self.namespace,
                condition=condition,
            )

        self.assertEqual(context.conditions[0]["field"]["raw_name"], "system_id")
        self.assertEqual(context.conditions[0]["filters"], [self.target_system_id])
        self.assertEqual(context.conditions[-1]["field"]["raw_name"], "username")

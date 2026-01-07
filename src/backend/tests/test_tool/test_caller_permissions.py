# -*- coding: utf-8 -*-
from unittest import mock

from core.exceptions import PermissionException
from core.models import get_request_username
from services.web.tool.constants import ToolTypeEnum
from services.web.tool.exceptions import BkVisionSearchPermissionProhibited
from services.web.tool.models import BkVisionToolConfig, Tool
from services.web.vision.models import Scenario, VisionPanel

from ..base import TestCase


class TestToolViewPermissions(TestCase):
    def setUp(self):
        self.current_user = get_request_username() or "admin"

        # 创建两个 BK Vision 工具：一个归当前用户所有，一个归他人所有
        self.owner_tool = Tool.objects.create(
            namespace="ns",
            name="owner_vision_tool",
            uid="owner_vision_tool_uid",
            version=1,
            tool_type=ToolTypeEnum.BK_VISION.value,
            config={"uid": "owner_panel_uid", "input_variable": []},
            updated_by=self.current_user,
        )
        self.owner_panel = VisionPanel.objects.create(
            id="owner_panel_id",
            vision_id="owner_panel_uid",
            scenario=Scenario.TOOL.value,
            handler="VisionHandler",
        )
        BkVisionToolConfig.objects.create(tool=self.owner_tool, panel=self.owner_panel)

        self.other_tool = Tool.objects.create(
            namespace="ns",
            name="other_vision_tool",
            uid="other_vision_tool_uid",
            version=1,
            tool_type=ToolTypeEnum.BK_VISION.value,
            config={"uid": "other_panel_uid", "input_variable": []},
            updated_by="someone_else",
        )
        self.other_panel = VisionPanel.objects.create(
            id="other_panel_id",
            vision_id="other_panel_uid",
            scenario=Scenario.TOOL.value,
            handler="VisionHandler",
        )
        BkVisionToolConfig.objects.create(tool=self.other_tool, panel=self.other_panel)

    def tearDown(self):
        mock.patch.stopall()

    def test_execute_with_caller_context_allowed(self):
        # 调用方上下文有权限，应放行（即使非创建/更新者）
        with (
            mock.patch("services.web.common.caller_permission.RiskCallerPermission.has_permission", return_value=True),
            mock.patch(
                "services.web.tool.permissions.api.bk_vision.check_share_auth", return_value={"check_result": True}
            ),
            mock.patch(
                "services.web.tool.executor.tool.api.bk_base.user_auth_batch_check",
                return_value=[{"result": True, "user_id": "test_user", "object_id": "mocked_table"}],
            ),
        ):
            result = self.resource.tool.execute_tool(
                {
                    "uid": self.other_tool.uid,
                    "params": {},
                    "caller_resource_type": "risk",
                    "caller_resource_id": "RID-1",
                }
            )
        self.assertEqual(result["tool_type"], ToolTypeEnum.BK_VISION.value)
        self.assertEqual(result["data"]["panel_id"], self.other_panel.id)

    def test_execute_with_caller_context_denied_raises(self):
        # 调用方上下文无权限，应抛权限异常
        with mock.patch(
            "services.web.common.caller_permission.RiskCallerPermission.has_permission",
            return_value=False,
            side_effect=PermissionException(action_name="list_risk", permission={}, apply_url=""),
        ):
            with self.assertRaises(PermissionException):
                self.resource.tool.execute_tool(
                    {
                        "uid": self.other_tool.uid,
                        "params": {},
                        "caller_resource_type": "risk",
                        "caller_resource_id": "RID-2",
                    }
                )

    def test_execute_as_owner_allowed(self):
        # 工具更新者应始终放行
        with mock.patch(
            "services.web.tool.permissions.api.bk_vision.check_share_auth", return_value={"check_result": True}
        ):
            result = self.resource.tool.execute_tool({"uid": self.owner_tool.uid, "params": {}})
        self.assertEqual(result["tool_type"], ToolTypeEnum.BK_VISION.value)
        self.assertEqual(result["data"]["panel_id"], self.owner_panel.id)

    def test_execute_without_caller_and_not_owner_denied(self):
        # 非调用方上下文，且无图标使用权限 -> 应抛权限异常
        with mock.patch(
            "services.web.tool.permissions.api.bk_vision.check_share_auth", return_value={"check_result": False}
        ):
            with self.assertRaises(BkVisionSearchPermissionProhibited):
                self.resource.tool.execute_tool({"uid": self.other_tool.uid, "params": {}})

    def test_execute_with_caller_and_drill_basic_field(self):
        # 构造策略+风险+SQL 工具关联，并通过 drill_field 指定 basic 字段 operator 映射，变量校验通过
        from django.utils import timezone

        from services.web.risk.models import Risk
        from services.web.strategy_v2.constants import StrategyFieldSourceEnum
        from services.web.strategy_v2.models import Strategy, StrategyTool
        from services.web.tool.models import DataSearchToolConfig

        # 0) 创建一个 SQL 工具（不影响其他用例使用的 Vision 工具）
        sql_tool = Tool.objects.create(
            namespace="ns",
            name="caller_sql_tool",
            uid="caller_sql_tool_uid",
            version=1,
            tool_type=ToolTypeEnum.DATA_SEARCH.value,
            config={
                "sql": "SELECT 1 as a",
                "referenced_tables": [{"table_name": "t"}],
                "input_variable": [
                    {
                        "raw_name": "ctx",
                        "display_name": "ctx",
                        "description": "",
                        "field_category": "input",
                        "required": True,
                        "default_value": None,
                    }
                ],
                "output_fields": [],
            },
            updated_by="someone_else",
        )
        DataSearchToolConfig.objects.create(tool=sql_tool, data_search_config_type="sql", sql="SELECT 1")

        # 1) 创建策略字段映射（operator basic 字段）并与 sql_tool 建立关联
        strategy = Strategy.objects.create(
            namespace="ns",
            strategy_name="s_for_execute",
            event_basic_field_configs=[
                {
                    "field_name": "operator",
                    "display_name": "责任人",
                    "is_priority": True,
                    "duplicate_field": False,
                    "drill_config": [
                        {
                            "tool": {"uid": sql_tool.uid, "version": 1},
                            "config": [
                                {
                                    "source_field": "ctx",
                                    "target_value_type": "field",
                                    "target_field_type": "basic",
                                    "target_value": "operator",
                                }
                            ],
                        }
                    ],
                }
            ],
        )
        StrategyTool.objects.create(
            strategy=strategy,
            tool_uid=sql_tool.uid,
            tool_version=sql_tool.version,
            field_name="operator",
            field_source=StrategyFieldSourceEnum.BASIC.value,
        )
        # 2) 创建归属于该策略的风险
        risk = Risk.objects.create(
            raw_event_id="e-for-execute",
            strategy=strategy,
            event_time=timezone.now(),
            event_data={},
        )
        # 3) mock list_event 顶层字段 operator=admin；以及 BKBASE 查询
        mocked_event = {
            "operator": self.current_user,
            "event_time": "2025-08-06 17:00:00",
            "event_data": {},
        }
        with (
            mock.patch(
                "services.web.common.caller_permission.resource.risk.list_event",
                return_value={"page": 1, "num_pages": 1, "total": 1, "results": [mocked_event]},
            ),
            mock.patch(
                "services.web.tool.executor.tool.api.bk_base.query_sync.bulk_request",
                return_value=({"list": [{"a": 1}]}, {"list": [{"count": 1}]}),
            ),
            mock.patch(
                "services.web.tool.executor.tool.api.bk_base.user_auth_batch_check",
                return_value=[{"result": True, "user_id": "test_user", "object_id": "mocked_table"}],
            ),
            mock.patch("services.web.risk.permissions.RiskViewPermission.has_risk_permission", return_value=True),
        ):
            block_params = {
                "uid": sql_tool.uid,
                "drill_field": "operator",
                "event_start_time": "2025-08-06 00:00:00",
                "event_end_time": "2025-08-07 00:00:00",
                "caller_resource_type": "risk",
                "caller_resource_id": risk.risk_id,
                "params": {"tool_variables": [{"raw_name": "ctx", "value": 'xx'}]},
            }
            pass_params = {
                "uid": sql_tool.uid,
                "drill_field": "operator",
                "event_start_time": "2025-08-06 00:00:00",
                "event_end_time": "2025-08-07 00:00:00",
                "caller_resource_type": "risk",
                "caller_resource_id": risk.risk_id,
                "params": {"tool_variables": [{"raw_name": "ctx", "value": self.current_user}]},
            }

            result = self.resource.tool.execute_tool(pass_params)
            self.assertEqual(result["tool_type"], ToolTypeEnum.DATA_SEARCH.value)
            self.assertEqual(result["data"]["total"], 1)
            with self.assertRaises(PermissionException):
                self.resource.tool.execute_tool(block_params)

    def test_execute_with_caller_and_drill_fixed_value(self):
        # 构造策略+风险+SQL 工具关联，并通过 drill_field 指定 fixed_value 校验，变量符合期望 -> 放行
        from django.utils import timezone

        from services.web.risk.models import Risk
        from services.web.strategy_v2.constants import StrategyFieldSourceEnum
        from services.web.strategy_v2.models import Strategy, StrategyTool
        from services.web.tool.models import DataSearchToolConfig

        # 0) 创建 SQL 工具
        sql_tool = Tool.objects.create(
            namespace="ns",
            name="caller_sql_tool_fixed",
            uid="caller_sql_tool_fixed_uid",
            version=1,
            tool_type=ToolTypeEnum.DATA_SEARCH.value,
            config={
                "sql": "SELECT 1 as a",
                "referenced_tables": [{"table_name": "t"}],
                "input_variable": [
                    {
                        "raw_name": "env",
                        "display_name": "env",
                        "description": "",
                        "field_category": "input",
                        "required": True,
                        "default_value": None,
                    }
                ],
                "output_fields": [],
            },
            updated_by="someone_else",
        )
        DataSearchToolConfig.objects.create(tool=sql_tool, data_search_config_type="sql", sql="SELECT 1")

        # 1) drill_config 配置 fixed_value
        strategy = Strategy.objects.create(
            namespace="ns",
            strategy_name="s_for_execute_fixed",
            event_basic_field_configs=[
                {
                    "field_name": "env",
                    "display_name": "环境",
                    "is_priority": True,
                    "duplicate_field": False,
                    "drill_config": [
                        {
                            "tool": {"uid": sql_tool.uid, "version": 1},
                            "config": [
                                {
                                    "source_field": "env",
                                    "target_value_type": "fixed_value",
                                    "target_field_type": "basic",
                                    "target_value": "prod",
                                }
                            ],
                        }
                    ],
                }
            ],
        )
        StrategyTool.objects.create(
            strategy=strategy,
            tool_uid=sql_tool.uid,
            tool_version=sql_tool.version,
            field_name="env",
            field_source=StrategyFieldSourceEnum.BASIC.value,
        )

        risk = Risk.objects.create(
            raw_event_id="e-for-execute-fixed",
            strategy=strategy,
            event_time=timezone.now(),
            event_data={},
        )

        with (
            mock.patch(
                "services.web.risk.permissions.RiskViewPermission.has_risk_permission",
                return_value=True,
            ),
            mock.patch(
                "services.web.tool.executor.tool.api.bk_base.query_sync.bulk_request",
                return_value=({"list": [{"a": 1}]}, {"list": [{"count": 1}]}),
            ),
            mock.patch(
                "services.web.common.caller_permission.resource.risk.list_event",
                return_value={"page": 1, "num_pages": 1, "total": 1, "results": []},
            ),
            mock.patch(
                "services.web.tool.executor.tool.api.bk_base.user_auth_batch_check",
                return_value=[{"result": True, "user_id": "test_user", "object_id": "mocked_table"}],
            ),
        ):
            result = self.resource.tool.execute_tool(
                {
                    "uid": sql_tool.uid,
                    "drill_field": "env",
                    "caller_resource_type": "risk",
                    "caller_resource_id": risk.risk_id,
                    "event_start_time": "2025-08-06 00:00:00",
                    "event_end_time": "2025-08-07 00:00:00",
                    "params": {"tool_variables": [{"raw_name": "env", "value": "prod"}]},
                }
            )
            self.assertEqual(result["tool_type"], ToolTypeEnum.DATA_SEARCH.value)
            self.assertEqual(result["data"]["total"], 1)

            with self.assertRaises(PermissionException):
                self.resource.tool.execute_tool(
                    {
                        "uid": sql_tool.uid,
                        "drill_field": "env",
                        "caller_resource_type": "risk",
                        "caller_resource_id": risk.risk_id,
                        "event_start_time": "2025-08-06 00:00:00",
                        "event_end_time": "2025-08-07 00:00:00",
                        "params": {"tool_variables": [{"raw_name": "env", "value": "dev"}]},
                    }
                )

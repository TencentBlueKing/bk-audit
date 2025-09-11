# -*- coding: utf-8 -*-
from unittest import mock

from core.exceptions import PermissionException
from services.web.common.caller_permission import (
    extract_extra_variables,
    is_tool_related_to_risk,
    should_skip_permission,
    should_skip_permission_from,
)
from services.web.tool.serializers import ExecuteToolReqSerializer
from tests.base import TestCase


class TestCallerPermission(TestCase):
    def test_should_skip_permission_risk_allowed(self):
        # 不再直接 mock RiskCallerPermission，改为模拟风险查看权限通过
        with mock.patch("services.web.risk.permissions.RiskViewPermission.has_risk_permission", return_value=True):
            # 仅携带 risk 上下文（不带 current_type/current_object_id），命中则应放行
            self.assertTrue(should_skip_permission("risk", "R123", username="u1"))

    def test_should_skip_permission_risk_denied(self):
        # 不再直接 mock RiskCallerPermission，改为模拟风险查看权限不通过
        with mock.patch(
            "services.web.risk.permissions.RiskViewPermission.has_risk_permission",
            side_effect=PermissionException(action_name="list_risk", permission={}, apply_url=""),
        ):
            with self.assertRaises(PermissionException):
                should_skip_permission("risk", "R123", username="u1")

    def test_should_skip_permission_unsupported_type(self):
        with self.assertRaises(PermissionException):
            self.assertFalse(should_skip_permission("unknown", "RID", username="u1"))

    def test_serializer_choice_validation(self):
        # 非法的 caller_resource_type 应校验失败
        s = ExecuteToolReqSerializer(
            data={"uid": "u", "params": {}, "caller_resource_type": "unsupported", "caller_resource_id": "1"}
        )
        self.assertFalse(s.is_valid())
        self.assertIn("caller_resource_type", s.errors)

    @mock.patch("services.web.risk.permissions.RiskViewPermission.has_risk_permission", return_value=True)
    def test_skip_when_tool_related_to_risk(self, _):
        # 构造策略、风险与工具关联
        from django.utils import timezone

        from services.web.risk.models import Risk
        from services.web.strategy_v2.constants import StrategyFieldSourceEnum
        from services.web.strategy_v2.models import Strategy, StrategyTool

        strategy = Strategy.objects.create(namespace="ns", strategy_name="s1")
        # 风险关联到策略
        risk = Risk.objects.create(
            raw_event_id="e1",
            strategy=strategy,
            event_time=timezone.now(),
        )
        # 策略与工具建立关联
        StrategyTool.objects.create(
            strategy=strategy,
            tool_uid="T1",
            tool_version=1,
            field_name="f1",
            field_source=StrategyFieldSourceEnum.BASIC.value,
        )

        data = {
            "caller_resource_type": "risk",
            "caller_resource_id": risk.risk_id,
            "current_type": "tool",
            "current_object_id": "T1",
        }
        self.assertTrue(should_skip_permission_from(data, username="u1"))

    @mock.patch("services.web.risk.permissions.RiskViewPermission.has_risk_permission", return_value=True)
    def test_no_skip_when_tool_not_related(self, _):
        # 构造策略、风险，但不建立指定工具关联
        from django.utils import timezone

        from services.web.risk.models import Risk
        from services.web.strategy_v2.models import Strategy

        strategy = Strategy.objects.create(namespace="ns", strategy_name="s2")
        risk = Risk.objects.create(
            raw_event_id="e2",
            strategy=strategy,
            event_time=timezone.now(),
        )

        data = {
            "caller_resource_type": "risk",
            "caller_resource_id": risk.risk_id,
            "current_type": "tool",
            "current_object_id": "UnRelatedTool",
        }
        with self.assertRaises(PermissionException):
            self.assertFalse(should_skip_permission_from(data, username="u1"))

    def test_is_tool_related_to_risk_edge_cases(self):
        # 风险不存在
        self.assertFalse(is_tool_related_to_risk("R-not-exist", "T1"))

    def test_extract_extra_variables(self):
        # 读取 current_type / current_object_id
        data = {"current_type": "tool", "current_object_id": "T2"}
        extras = extract_extra_variables(data)
        self.assertEqual(extras.get("current_type"), "tool")
        self.assertEqual(extras.get("current_object_id"), "T2")

    @mock.patch("services.web.risk.permissions.RiskViewPermission.has_risk_permission", return_value=True)
    def test_skip_when_tool_variables_match_mapping_field(self, _):
        # 通过策略字段drill_config建立映射：变量username 对应 event_data.username
        from django.utils import timezone

        from services.web.risk.models import Risk
        from services.web.strategy_v2.constants import StrategyFieldSourceEnum
        from services.web.strategy_v2.models import Strategy, StrategyTool

        strategy = Strategy.objects.create(
            namespace="ns",
            strategy_name="s3",
            event_basic_field_configs=[
                {
                    "field_name": "username",
                    "display_name": "用户名",
                    "is_priority": True,
                    "drill_config": {
                        "tool": {"uid": "T1", "version": 1},
                        "config": [
                            {
                                "source_field": "username",
                                "target_value_type": "field",
                                "target_value": "username",
                            }
                        ],
                    },
                }
            ],
        )
        risk = Risk.objects.create(
            raw_event_id="e3",
            strategy=strategy,
            event_time=timezone.now(),
            event_data={"ip": "1.1.1.1", "event_data": {"username": "admin"}},
        )
        StrategyTool.objects.create(
            strategy=strategy,
            tool_uid="T1",
            tool_version=1,
            field_name="username",
            field_source=StrategyFieldSourceEnum.BASIC.value,
        )

        # 使用嵌套 event_data 校验（不依赖 list_event）
        data = {
            "caller_resource_type": "risk",
            "caller_resource_id": risk.risk_id,
            "current_type": "tool",
            "current_object_id": "T1",
            "drill_field": "username",
            "event_start_time": "2025-08-06 00:00:00",
            "event_end_time": "2025-08-07 00:00:00",
            "tool_variables": [
                {"raw_name": "username", "value": "admin"},
            ],
        }
        self.assertTrue(should_skip_permission_from(data, username="u1"))

    @mock.patch("services.web.risk.permissions.RiskViewPermission.has_risk_permission", return_value=True)
    def test_skip_when_tool_variables_match_basic_field(self, _):
        # 通过 drill_config 将变量 ctx 映射到顶层 basic 字段 operator，镜像校验一致
        from django.utils import timezone

        from services.web.risk.models import Risk
        from services.web.strategy_v2.constants import StrategyFieldSourceEnum
        from services.web.strategy_v2.models import Strategy, StrategyTool

        strategy = Strategy.objects.create(
            namespace="ns",
            strategy_name="s_basic",
            event_basic_field_configs=[
                {
                    "field_name": "operator",
                    "display_name": "责任人",
                    "is_priority": True,
                    "drill_config": {
                        "tool": {"uid": "T1", "version": 1},
                        "config": [
                            {
                                "source_field": "ctx",
                                "target_value_type": "field",
                                "target_field_type": "basic",
                                "target_value": "operator",
                            }
                        ],
                    },
                }
            ],
        )
        risk = Risk.objects.create(
            raw_event_id="e_basic",
            strategy=strategy,
            event_time=timezone.now(),
            event_data={},
        )
        StrategyTool.objects.create(
            strategy=strategy,
            tool_uid="T1",
            tool_version=1,
            field_name="operator",
            field_source=StrategyFieldSourceEnum.BASIC.value,
        )

        mocked_event = {
            "operator": "admin",
            "event_time": "2025-08-06 17:00:00",
            "event_data": {"ip": "1.1.1.1"},
        }
        with mock.patch(
            "services.web.common.caller_permission.resource.risk.list_event",
            return_value={"page": 1, "num_pages": 1, "total": 1, "results": [mocked_event]},
        ):
            data = {
                "caller_resource_type": "risk",
                "caller_resource_id": risk.risk_id,
                "current_type": "tool",
                "current_object_id": "T1",
                "drill_field": "operator",
                "event_start_time": "2025-08-06 00:00:00",
                "event_end_time": "2025-08-07 00:00:00",
                "tool_variables": [
                    {"raw_name": "ctx", "value": "admin"},
                ],
            }
            self.assertTrue(should_skip_permission_from(data, username="u1"))

    @mock.patch("services.web.risk.permissions.RiskViewPermission.has_risk_permission", return_value=True)
    def test_no_skip_when_tool_variable_not_match_fixed_value(self, _):
        # 通过策略字段drill_config建立映射：变量env 对应固定值 'prod'，传入 'dev' 应拒绝
        from django.utils import timezone

        from services.web.risk.models import Risk
        from services.web.strategy_v2.constants import StrategyFieldSourceEnum
        from services.web.strategy_v2.models import Strategy, StrategyTool

        strategy = Strategy.objects.create(
            namespace="ns",
            strategy_name="s4",
            event_basic_field_configs=[
                {
                    "field_name": "env",
                    "display_name": "环境",
                    "is_priority": True,
                    "drill_config": {
                        "tool": {"uid": "T1", "version": 1},
                        "config": [
                            {
                                "source_field": "env",
                                "target_value_type": "fixed_value",
                                "target_value": "prod",
                            }
                        ],
                    },
                }
            ],
        )
        risk = Risk.objects.create(
            raw_event_id="e4",
            strategy=strategy,
            event_time=timezone.now(),
            event_data={},  # 确保不使用 model 中的 event_data
        )
        StrategyTool.objects.create(
            strategy=strategy,
            tool_uid="T1",
            tool_version=1,
            field_name="env",
            field_source=StrategyFieldSourceEnum.BASIC.value,
        )

        # mock list_event 接口返回，事件数据仅来源于接口
        mocked_event = {
            "operator": "someone",
            "event_time": "2025-08-06 17:00:00",
            "event_data": {"ip": "1.1.1.1"},
        }
        with mock.patch(
            "services.web.common.caller_permission.resource.risk.list_event",
            return_value={"page": 1, "num_pages": 1, "total": 1, "results": [mocked_event]},
        ):
            data = {
                "caller_resource_type": "risk",
                "caller_resource_id": risk.risk_id,
                "current_type": "tool",
                "current_object_id": "T1",
                "drill_field": "env",
                "event_start_time": "2025-08-06 00:00:00",
                "event_end_time": "2025-08-07 00:00:00",
                "tool_variables": [
                    {"raw_name": "env", "value": "dev"},
                ],
            }
            with self.assertRaises(PermissionException):
                should_skip_permission_from(data, username="u1")

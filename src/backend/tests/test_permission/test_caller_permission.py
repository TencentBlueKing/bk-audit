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
        from services.web.scene.constants import (
            BindingType,
            PanelStatus,
            ResourceVisibilityType,
            SceneStatus,
        )
        from services.web.scene.models import (
            ResourceBinding,
            ResourceBindingScene,
            Scene,
        )
        from services.web.strategy_v2.constants import StrategyFieldSourceEnum
        from services.web.strategy_v2.models import Strategy, StrategyTool
        from services.web.tool.models import Tool

        strategy = Strategy.objects.create(namespace="ns", strategy_name="s1")
        scene = Scene.objects.create(name="scene_s1", status=SceneStatus.ENABLED)
        strategy_binding = ResourceBinding.objects.create(
            resource_type=ResourceVisibilityType.STRATEGY,
            resource_id=str(strategy.strategy_id),
            binding_type=BindingType.SCENE_BINDING,
        )
        ResourceBindingScene.objects.create(binding=strategy_binding, scene=scene)
        Tool.objects.create(
            namespace="ns",
            uid="T1",
            version=1,
            name="tool-t1",
            tool_type="data_search",
            config={"input_variable": [], "output_fields": [], "referenced_tables": [], "sql": "select 1"},
            permission_owner="admin",
            status=PanelStatus.PUBLISHED,
        )
        tool_binding = ResourceBinding.objects.create(
            resource_type=ResourceVisibilityType.TOOL,
            resource_id="T1",
            binding_type=BindingType.SCENE_BINDING,
        )
        ResourceBindingScene.objects.create(binding=tool_binding, scene=scene)
        # 风险关联到策略
        risk = Risk.objects.create(
            raw_event_id="e1",
            strategy=strategy,
            event_time=timezone.now(),
            scene_id=scene.scene_id,
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

    def test_is_tool_related_to_risk_when_tool_not_visible_in_scene(self):
        from django.utils import timezone

        from services.web.risk.models import Risk
        from services.web.scene.constants import (
            BindingType,
            PanelStatus,
            ResourceVisibilityType,
            SceneStatus,
        )
        from services.web.scene.models import (
            ResourceBinding,
            ResourceBindingScene,
            Scene,
        )
        from services.web.strategy_v2.constants import StrategyFieldSourceEnum
        from services.web.strategy_v2.models import Strategy, StrategyTool
        from services.web.tool.models import Tool

        scene_1 = Scene.objects.create(name="scene-1", status=SceneStatus.ENABLED)
        scene_2 = Scene.objects.create(name="scene-2", status=SceneStatus.ENABLED)

        strategy = Strategy.objects.create(namespace="ns", strategy_name="s_scene")
        strategy_binding = ResourceBinding.objects.create(
            resource_type=ResourceVisibilityType.STRATEGY,
            resource_id=str(strategy.strategy_id),
            binding_type=BindingType.SCENE_BINDING,
        )
        ResourceBindingScene.objects.create(binding=strategy_binding, scene=scene_1)

        risk = Risk.objects.create(raw_event_id="e_scene", strategy=strategy, event_time=timezone.now())
        Tool.objects.create(
            namespace="ns",
            uid="T_SCENE",
            version=1,
            name="tool-scene",
            tool_type="data_search",
            config={"input_variable": [], "output_fields": [], "referenced_tables": [], "sql": "select 1"},
            permission_owner="admin",
            status=PanelStatus.PUBLISHED,
        )
        tool_binding = ResourceBinding.objects.create(
            resource_type=ResourceVisibilityType.TOOL,
            resource_id="T_SCENE",
            binding_type=BindingType.SCENE_BINDING,
        )
        ResourceBindingScene.objects.create(binding=tool_binding, scene=scene_2)
        StrategyTool.objects.create(
            strategy=strategy,
            tool_uid="T_SCENE",
            tool_version=1,
            field_name="f1",
            field_source=StrategyFieldSourceEnum.BASIC.value,
        )

        self.assertFalse(is_tool_related_to_risk(risk.risk_id, "T_SCENE"))

    def test_is_tool_related_to_risk_uses_risk_own_scene(self):
        """按风险自身归属场景校验工具可见性（策略多场景绑定时结果确定）"""
        from django.utils import timezone

        from services.web.risk.models import Risk
        from services.web.scene.constants import (
            BindingType,
            PanelStatus,
            ResourceVisibilityType,
            SceneStatus,
        )
        from services.web.scene.models import (
            ResourceBinding,
            ResourceBindingScene,
            Scene,
        )
        from services.web.strategy_v2.constants import StrategyFieldSourceEnum
        from services.web.strategy_v2.models import Strategy, StrategyTool
        from services.web.tool.models import Tool

        scene_risk = Scene.objects.create(name="scene-risk-own", status=SceneStatus.ENABLED)
        scene_other = Scene.objects.create(name="scene-other-own", status=SceneStatus.ENABLED)

        # 策略绑定多个场景（模拟全局策略的分派目标场景并集）
        strategy = Strategy.objects.create(namespace="ns", strategy_name="s_multi_scene")
        strategy_binding = ResourceBinding.objects.create(
            resource_type=ResourceVisibilityType.STRATEGY,
            resource_id=str(strategy.strategy_id),
            binding_type=BindingType.SCENE_BINDING,
        )
        ResourceBindingScene.objects.create(binding=strategy_binding, scene=scene_risk)
        ResourceBindingScene.objects.create(binding=strategy_binding, scene=scene_other)

        def _make_tool(uid, scene, field_name):
            Tool.objects.create(
                namespace="ns",
                uid=uid,
                version=1,
                name=f"tool-{uid}",
                tool_type="data_search",
                config={"input_variable": [], "output_fields": [], "referenced_tables": [], "sql": "select 1"},
                permission_owner="admin",
                status=PanelStatus.PUBLISHED,
            )
            tool_binding = ResourceBinding.objects.create(
                resource_type=ResourceVisibilityType.TOOL,
                resource_id=uid,
                binding_type=BindingType.SCENE_BINDING,
            )
            ResourceBindingScene.objects.create(binding=tool_binding, scene=scene)
            StrategyTool.objects.create(
                strategy=strategy,
                tool_uid=uid,
                tool_version=1,
                field_name=field_name,
                field_source=StrategyFieldSourceEnum.BASIC.value,
            )

        # 工具A 只在风险归属场景可见；工具B 只在其他场景可见
        _make_tool("T_RISK_SCENE", scene_risk, "f_a")
        _make_tool("T_OTHER_SCENE", scene_other, "f_b")

        # 风险固化归属场景 scene_risk（全局策略建单时=分派目标场景）
        risk = Risk.objects.create(
            raw_event_id="e_risk_own_scene",
            strategy=strategy,
            event_time=timezone.now(),
            scene_id=scene_risk.scene_id,
        )

        # 按风险自身场景判定，与策略绑定场景的顺序无关，结果确定
        self.assertTrue(is_tool_related_to_risk(risk.risk_id, "T_RISK_SCENE"))
        self.assertFalse(is_tool_related_to_risk(risk.risk_id, "T_OTHER_SCENE"))

    def test_is_tool_related_to_risk_ignores_square_display_status(self):
        """广场展示关闭（unpublished）的工具不影响下钻权限判定"""
        from django.utils import timezone

        from services.web.risk.models import Risk
        from services.web.scene.constants import (
            BindingType,
            PanelStatus,
            ResourceVisibilityType,
            SceneStatus,
        )
        from services.web.scene.models import (
            ResourceBinding,
            ResourceBindingScene,
            Scene,
        )
        from services.web.strategy_v2.constants import StrategyFieldSourceEnum
        from services.web.strategy_v2.models import Strategy, StrategyTool
        from services.web.tool.models import Tool

        scene = Scene.objects.create(name="scene-hidden-tool", status=SceneStatus.ENABLED)
        strategy = Strategy.objects.create(namespace="ns", strategy_name="s_hidden_tool")
        strategy_binding = ResourceBinding.objects.create(
            resource_type=ResourceVisibilityType.STRATEGY,
            resource_id=str(strategy.strategy_id),
            binding_type=BindingType.SCENE_BINDING,
        )
        ResourceBindingScene.objects.create(binding=strategy_binding, scene=scene)

        # 广场展示关闭的工具：仍与策略关联且场景可见，下钻权限应通过
        Tool.objects.create(
            namespace="ns",
            uid="T_HIDDEN",
            version=1,
            name="tool-hidden",
            tool_type="data_search",
            config={"input_variable": [], "output_fields": [], "referenced_tables": [], "sql": "select 1"},
            permission_owner="admin",
            status=PanelStatus.UNPUBLISHED,
        )
        tool_binding = ResourceBinding.objects.create(
            resource_type=ResourceVisibilityType.TOOL,
            resource_id="T_HIDDEN",
            binding_type=BindingType.SCENE_BINDING,
        )
        ResourceBindingScene.objects.create(binding=tool_binding, scene=scene)
        StrategyTool.objects.create(
            strategy=strategy,
            tool_uid="T_HIDDEN",
            tool_version=1,
            field_name="f1",
            field_source=StrategyFieldSourceEnum.BASIC.value,
        )
        risk = Risk.objects.create(
            raw_event_id="e_hidden_tool",
            strategy=strategy,
            event_time=timezone.now(),
            scene_id=scene.scene_id,
        )

        self.assertTrue(is_tool_related_to_risk(risk.risk_id, "T_HIDDEN"))

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
        from services.web.scene.constants import (
            BindingType,
            PanelStatus,
            ResourceVisibilityType,
            SceneStatus,
        )
        from services.web.scene.models import (
            ResourceBinding,
            ResourceBindingScene,
            Scene,
        )
        from services.web.strategy_v2.constants import StrategyFieldSourceEnum
        from services.web.strategy_v2.models import Strategy, StrategyTool
        from services.web.tool.models import Tool

        strategy = Strategy.objects.create(
            namespace="ns",
            strategy_name="s3",
            event_basic_field_configs=[
                {
                    "field_name": "username",
                    "display_name": "用户名",
                    "is_priority": True,
                    "duplicate_field": False,
                    "drill_config": [
                        {
                            "tool": {"uid": "T1", "version": 1},
                            "config": [
                                {
                                    "source_field": "username",
                                    "target_value_type": "field",
                                    "target_value": "username",
                                }
                            ],
                        }
                    ],
                }
            ],
        )
        scene = Scene.objects.create(name="scene_s3", status=SceneStatus.ENABLED)
        strategy_binding = ResourceBinding.objects.create(
            resource_type=ResourceVisibilityType.STRATEGY,
            resource_id=str(strategy.strategy_id),
            binding_type=BindingType.SCENE_BINDING,
        )
        ResourceBindingScene.objects.create(binding=strategy_binding, scene=scene)
        Tool.objects.create(
            namespace="ns",
            uid="T1",
            version=1,
            name="tool-t1-s3",
            tool_type="data_search",
            config={"input_variable": [], "output_fields": [], "referenced_tables": [], "sql": "select 1"},
            permission_owner="admin",
            status=PanelStatus.PUBLISHED,
        )
        tool_binding = ResourceBinding.objects.create(
            resource_type=ResourceVisibilityType.TOOL,
            resource_id="T1",
            binding_type=BindingType.SCENE_BINDING,
        )
        ResourceBindingScene.objects.create(binding=tool_binding, scene=scene)

        risk = Risk.objects.create(
            raw_event_id="e3",
            strategy=strategy,
            event_time=timezone.now(),
            event_data={"ip": "1.1.1.1", "event_data": {"username": "admin"}},
            scene_id=scene.scene_id,
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
        from services.web.scene.constants import (
            BindingType,
            PanelStatus,
            ResourceVisibilityType,
            SceneStatus,
        )
        from services.web.scene.models import (
            ResourceBinding,
            ResourceBindingScene,
            Scene,
        )
        from services.web.strategy_v2.constants import StrategyFieldSourceEnum
        from services.web.strategy_v2.models import Strategy, StrategyTool
        from services.web.tool.models import Tool

        strategy = Strategy.objects.create(
            namespace="ns",
            strategy_name="s_basic",
            event_basic_field_configs=[
                {
                    "field_name": "operator",
                    "display_name": "责任人",
                    "is_priority": True,
                    "duplicate_field": False,
                    "drill_config": [
                        {
                            "tool": {"uid": "T1", "version": 1},
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
        scene = Scene.objects.create(name="scene_basic", status=SceneStatus.ENABLED)
        strategy_binding = ResourceBinding.objects.create(
            resource_type=ResourceVisibilityType.STRATEGY,
            resource_id=str(strategy.strategy_id),
            binding_type=BindingType.SCENE_BINDING,
        )
        ResourceBindingScene.objects.create(binding=strategy_binding, scene=scene)
        Tool.objects.create(
            namespace="ns",
            uid="T1",
            version=1,
            name="tool-t1-basic",
            tool_type="data_search",
            config={"input_variable": [], "output_fields": [], "referenced_tables": [], "sql": "select 1"},
            permission_owner="admin",
            status=PanelStatus.PUBLISHED,
        )
        tool_binding = ResourceBinding.objects.create(
            resource_type=ResourceVisibilityType.TOOL,
            resource_id="T1",
            binding_type=BindingType.SCENE_BINDING,
        )
        ResourceBindingScene.objects.create(binding=tool_binding, scene=scene)

        risk = Risk.objects.create(
            raw_event_id="e_basic",
            strategy=strategy,
            event_time=timezone.now(),
            event_data={},
            scene_id=scene.scene_id,
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
                    "duplicate_field": False,
                    "drill_config": [
                        {
                            "tool": {"uid": "T1", "version": 1},
                            "config": [
                                {
                                    "source_field": "env",
                                    "target_value_type": "fixed_value",
                                    "target_value": "prod",
                                }
                            ],
                        },
                    ],
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


class TestDrillSourceValidation(TestCase):
    """下钻值校验的配置溯源：风险元字段配置参与规则收集 + 溯源失败即拒绝 + FIELD 引用风险对象兜底"""

    TOOL_UID = "T_DRILL"

    @staticmethod
    def _field_config(field_name: str, tool_uid: str, config: list) -> dict:
        return {
            "field_name": field_name,
            "display_name": field_name,
            "drill_config": [{"tool": {"uid": tool_uid, "version": 1}, "config": config}],
        }

    def _create_drill_env(self, *, strategy_configs: dict, risk_kwargs: dict = None):
        """构造完整的下钻校验环境（策略/场景/工具绑定/风险/策略工具关联），返回 (strategy, risk)"""
        from django.utils import timezone

        from services.web.risk.models import Risk
        from services.web.scene.constants import (
            BindingType,
            PanelStatus,
            ResourceVisibilityType,
            SceneStatus,
        )
        from services.web.scene.models import (
            ResourceBinding,
            ResourceBindingScene,
            Scene,
        )
        from services.web.strategy_v2.constants import StrategyFieldSourceEnum
        from services.web.strategy_v2.models import Strategy, StrategyTool
        from services.web.tool.models import Tool

        strategy = Strategy.objects.create(namespace="ns", strategy_name="s_drill", **strategy_configs)
        scene = Scene.objects.create(name="scene_drill", status=SceneStatus.ENABLED)
        strategy_binding = ResourceBinding.objects.create(
            resource_type=ResourceVisibilityType.STRATEGY,
            resource_id=str(strategy.strategy_id),
            binding_type=BindingType.SCENE_BINDING,
        )
        ResourceBindingScene.objects.create(binding=strategy_binding, scene=scene)
        Tool.objects.create(
            namespace="ns",
            uid=self.TOOL_UID,
            version=1,
            name="tool-drill",
            tool_type="data_search",
            config={"input_variable": [], "output_fields": [], "referenced_tables": [], "sql": "select 1"},
            permission_owner="admin",
            status=PanelStatus.PUBLISHED,
        )
        tool_binding = ResourceBinding.objects.create(
            resource_type=ResourceVisibilityType.TOOL,
            resource_id=self.TOOL_UID,
            binding_type=BindingType.SCENE_BINDING,
        )
        ResourceBindingScene.objects.create(binding=tool_binding, scene=scene)
        risk = Risk.objects.create(
            raw_event_id="e_drill",
            strategy=strategy,
            scene_id=scene.scene_id,
            **{"event_time": timezone.now(), "event_data": {}, **(risk_kwargs or {})},
        )
        StrategyTool.objects.create(
            strategy=strategy,
            tool_uid=self.TOOL_UID,
            tool_version=1,
            field_name="f_any",
            field_source=StrategyFieldSourceEnum.BASIC.value,
        )
        return strategy, risk

    def _build_request(self, risk, drill_field: str, tool_variables: list) -> dict:
        return {
            "caller_resource_type": "risk",
            "caller_resource_id": risk.risk_id,
            "current_type": "tool",
            "current_object_id": self.TOOL_UID,
            "drill_field": drill_field,
            "event_start_time": "2026-01-01 00:00:00",
            "event_end_time": "2026-01-02 00:00:00",
            "tool_variables": tool_variables,
        }

    @mock.patch("services.web.risk.permissions.RiskViewPermission.has_risk_permission", return_value=True)
    def test_risk_meta_fixed_value_match(self, _):
        """风险详情字段配置固定值、事件字段无同名字段：传配置值放行（修复误拒+漏校验）"""
        _, risk = self._create_drill_env(
            strategy_configs={
                "risk_meta_field_config": [
                    self._field_config(
                        "operator",
                        self.TOOL_UID,
                        [{"source_field": "username", "target_value_type": "fixed_value", "target_value": "zhangsan"}],
                    )
                ]
            }
        )
        data = self._build_request(risk, "operator", [{"raw_name": "username", "value": "zhangsan"}])
        self.assertTrue(should_skip_permission_from(data, username="u1"))

    @mock.patch("services.web.risk.permissions.RiskViewPermission.has_risk_permission", return_value=True)
    def test_risk_meta_fixed_value_tampered_rejected(self, _):
        """风险详情字段固定值被篡改：拒绝"""
        _, risk = self._create_drill_env(
            strategy_configs={
                "risk_meta_field_config": [
                    self._field_config(
                        "operator",
                        self.TOOL_UID,
                        [{"source_field": "username", "target_value_type": "fixed_value", "target_value": "zhangsan"}],
                    )
                ]
            }
        )
        data = self._build_request(risk, "operator", [{"raw_name": "username", "value": "wangwu"}])
        with self.assertRaises(PermissionException):
            should_skip_permission_from(data, username="u1")

    @mock.patch("services.web.risk.permissions.RiskViewPermission.has_risk_permission", return_value=True)
    def test_drill_field_not_bound_rejected(self, _):
        """溯源失败即拒绝：工具关联策略且场景可见，但 drill_field 未绑定该工具（编造字段名），携带变量值应拒绝"""
        _, risk = self._create_drill_env(
            strategy_configs={
                "event_basic_field_configs": [
                    self._field_config(
                        "operator",
                        self.TOOL_UID,
                        [{"source_field": "username", "target_value_type": "fixed_value", "target_value": "zhangsan"}],
                    )
                ]
            }
        )
        # drill_field 传四份配置中都不存在的字段名（修复前此请求被静默放行）
        data = self._build_request(risk, "nonexistent_field", [{"raw_name": "username", "value": "anything"}])
        with self.assertRaises(PermissionException):
            should_skip_permission_from(data, username="u1")

    @mock.patch("services.web.risk.permissions.RiskViewPermission.has_risk_permission", return_value=True)
    def test_same_field_dual_config_both_values_pass(self, _):
        """同名字段双配置（risk_meta + event_basic）绑同一工具不同固定值：任一入口配置的合法值均放行"""
        _, risk = self._create_drill_env(
            strategy_configs={
                "risk_meta_field_config": [
                    self._field_config(
                        "operator",
                        self.TOOL_UID,
                        [{"source_field": "username", "target_value_type": "fixed_value", "target_value": "zhangsan"}],
                    )
                ],
                "event_basic_field_configs": [
                    self._field_config(
                        "operator",
                        self.TOOL_UID,
                        [{"source_field": "username", "target_value_type": "fixed_value", "target_value": "lisi"}],
                    )
                ],
            }
        )
        # 风险详情入口配置的值
        data = self._build_request(risk, "operator", [{"raw_name": "username", "value": "zhangsan"}])
        self.assertTrue(should_skip_permission_from(data, username="u1"))
        # 事件入口配置的值
        data = self._build_request(risk, "operator", [{"raw_name": "username", "value": "lisi"}])
        self.assertTrue(should_skip_permission_from(data, username="u1"))
        # 两个配置之外的值：拒绝
        data = self._build_request(risk, "operator", [{"raw_name": "username", "value": "wangwu"}])
        with self.assertRaises(PermissionException):
            should_skip_permission_from(data, username="u1")

    @mock.patch("services.web.risk.permissions.RiskViewPermission.has_risk_permission", return_value=True)
    def test_field_ref_risk_meta_field_from_risk_object(self, _):
        """FIELD 引用风险元字段（risk_level，不在事件记录中）：从风险对象兜底取值校验"""
        _, risk = self._create_drill_env(
            strategy_configs={
                "risk_meta_field_config": [
                    self._field_config(
                        "risk_level",
                        self.TOOL_UID,
                        [
                            {
                                "source_field": "level",
                                "target_value_type": "field",
                                "target_field_type": "basic",
                                "target_value": "risk_level",
                            }
                        ],
                    )
                ]
            },
            risk_kwargs={"risk_level": "HIGH"},
        )
        data = self._build_request(risk, "risk_level", [{"raw_name": "level", "value": "HIGH"}])
        self.assertTrue(should_skip_permission_from(data, username="u1"))

    @mock.patch("services.web.risk.permissions.RiskViewPermission.has_risk_permission", return_value=True)
    def test_field_ref_strategy_name_from_relation(self, _):
        """FIELD 引用 strategy_name（非直接列）：经关联取值校验"""
        strategy, risk = self._create_drill_env(
            strategy_configs={
                "risk_meta_field_config": [
                    self._field_config(
                        "strategy_name",
                        self.TOOL_UID,
                        [
                            {
                                "source_field": "sname",
                                "target_value_type": "field",
                                "target_field_type": "basic",
                                "target_value": "strategy_name",
                            }
                        ],
                    )
                ]
            }
        )
        data = self._build_request(risk, "strategy_name", [{"raw_name": "sname", "value": strategy.strategy_name}])
        self.assertTrue(should_skip_permission_from(data, username="u1"))

    @mock.patch("services.web.risk.permissions.RiskViewPermission.has_risk_permission", return_value=True)
    def test_bound_without_variable_mapping_passes(self, _):
        """绑定工具但未配置变量映射：无值约束，携带变量放行（保持现状语义）"""
        _, risk = self._create_drill_env(
            strategy_configs={
                "risk_meta_field_config": [
                    self._field_config("operator", self.TOOL_UID, []),
                ]
            }
        )
        data = self._build_request(risk, "operator", [{"raw_name": "username", "value": "anything"}])
        self.assertTrue(should_skip_permission_from(data, username="u1"))

    @mock.patch("services.web.risk.permissions.RiskViewPermission.has_risk_permission", return_value=True)
    def test_event_only_config_unchanged(self, _):
        """仅事件字段配置绑定（无同名风险元配置）：行为与修复前一致"""
        _, risk = self._create_drill_env(
            strategy_configs={
                "event_basic_field_configs": [
                    self._field_config(
                        "env",
                        self.TOOL_UID,
                        [{"source_field": "env", "target_value_type": "fixed_value", "target_value": "prod"}],
                    )
                ]
            }
        )
        data = self._build_request(risk, "env", [{"raw_name": "env", "value": "prod"}])
        self.assertTrue(should_skip_permission_from(data, username="u1"))
        data = self._build_request(risk, "env", [{"raw_name": "env", "value": "dev"}])
        with self.assertRaises(PermissionException):
            should_skip_permission_from(data, username="u1")

    @mock.patch("services.web.risk.permissions.RiskViewPermission.has_risk_permission", return_value=True)
    def test_time_field_reference_epoch_millis(self, _):
        """FIELD 引用时间字段（datetime 列）：多格式候选兼容前端传值（epoch 毫秒）"""
        from django.utils import timezone

        event_time = timezone.now()
        _, risk = self._create_drill_env(
            strategy_configs={
                "risk_meta_field_config": [
                    self._field_config(
                        "event_time",
                        self.TOOL_UID,
                        [
                            {
                                "source_field": "ets",
                                "target_value_type": "field",
                                "target_field_type": "basic",
                                "target_value": "event_time",
                            }
                        ],
                    )
                ]
            },
            risk_kwargs={"event_time": event_time},
        )
        # RiskMetaFields 声明的时间格式为 epoch_millis
        data = self._build_request(
            risk, "event_time", [{"raw_name": "ets", "value": str(int(event_time.timestamp() * 1000))}]
        )
        self.assertTrue(should_skip_permission_from(data, username="u1"))

    @mock.patch("services.web.risk.permissions.RiskViewPermission.has_risk_permission", return_value=True)
    def test_no_variables_skips_value_check(self, _):
        """不携带变量值的请求不进值校验：即使无字段绑定也放行（行为不变）"""
        _, risk = self._create_drill_env(strategy_configs={})
        data = {
            "caller_resource_type": "risk",
            "caller_resource_id": risk.risk_id,
            "current_type": "tool",
            "current_object_id": self.TOOL_UID,
        }
        self.assertTrue(should_skip_permission_from(data, username="u1"))

    @mock.patch("services.web.risk.permissions.RiskViewPermission.has_risk_permission", return_value=True)
    def test_time_field_reference_local_time_string(self, _):
        """FIELD 引用时间字段：前端传本地时区字符串（USE_TZ=True 下与 UTC 表示差 8 小时）应放行"""
        from django.utils import timezone

        event_time = timezone.now()
        _, risk = self._create_drill_env(
            strategy_configs={
                "risk_meta_field_config": [
                    self._field_config(
                        "event_time",
                        self.TOOL_UID,
                        [
                            {
                                "source_field": "ets",
                                "target_value_type": "field",
                                "target_field_type": "basic",
                                "target_value": "event_time",
                            }
                        ],
                    )
                ]
            },
            risk_kwargs={"event_time": event_time},
        )
        # 模拟前端序列化口径：本地时区（Asia/Shanghai）常规字符串
        local_time_str = timezone.localtime(event_time).strftime("%Y-%m-%d %H:%M:%S")
        data = self._build_request(risk, "event_time", [{"raw_name": "ets", "value": local_time_str}])
        self.assertTrue(should_skip_permission_from(data, username="u1"))

    @mock.patch("services.web.risk.permissions.RiskViewPermission.has_risk_permission", return_value=True)
    def test_field_ref_nested_single_layer_snapshot(self, _):
        """FIELD 嵌套引用（event_data 字段）：事件记录缺失时从风险快照兜底（真实单层存储结构）

        建单时 gen_risk_create_params 将 event.get("event_data")（事件扩展字段字典）原样
        写入 Risk.event_data，业务字段直接位于快照顶层，风险详情按 row.event_data[field] 取值。
        """
        _, risk = self._create_drill_env(
            strategy_configs={
                "risk_meta_field_config": [
                    self._field_config(
                        "client_ip",
                        self.TOOL_UID,
                        [
                            {
                                "source_field": "ip",
                                "target_value_type": "field",
                                # target_field_type 不传（非 basic）→ 嵌套引用
                                "target_value": "client_ip",
                            }
                        ],
                    )
                ]
            },
            risk_kwargs={"event_data": {"client_ip": "snap-mock"}},
        )
        # list_event 返回的事件不含该嵌套字段 → 触发风险快照兜底
        mocked_event = {"operator": "someone", "event_time": "2026-11-26 10:00:00", "event_data": {"other": "x"}}
        with mock.patch(
            "services.web.common.caller_permission.resource.risk.list_event",
            return_value={"page": 1, "num_pages": 1, "total": 1, "results": [mocked_event]},
        ):
            data = self._build_request(risk, "client_ip", [{"raw_name": "ip", "value": "snap-mock"}])
            self.assertTrue(should_skip_permission_from(data, username="u1"))

    @mock.patch("services.web.risk.permissions.RiskViewPermission.has_risk_permission", return_value=True)
    def test_field_ref_nested_legacy_double_layer_snapshot(self, _):
        """FIELD 嵌套引用：兼容含 event_data 嵌套键的双层构造（历史数据/存量测试结构）"""
        _, risk = self._create_drill_env(
            strategy_configs={
                "risk_meta_field_config": [
                    self._field_config(
                        "client_ip",
                        self.TOOL_UID,
                        [{"source_field": "ip", "target_value_type": "field", "target_value": "client_ip"}],
                    )
                ]
            },
            risk_kwargs={"event_data": {"event_data": {"client_ip": "inner-mock"}}},
        )
        mocked_event = {"operator": "someone", "event_time": "2026-11-26 10:00:00", "event_data": {"other": "x"}}
        with mock.patch(
            "services.web.common.caller_permission.resource.risk.list_event",
            return_value={"page": 1, "num_pages": 1, "total": 1, "results": [mocked_event]},
        ):
            data = self._build_request(risk, "client_ip", [{"raw_name": "ip", "value": "inner-mock"}])
            self.assertTrue(should_skip_permission_from(data, username="u1"))

    @mock.patch("services.web.risk.permissions.RiskViewPermission.has_risk_permission", return_value=True)
    def test_field_ref_missing_value_rejected_not_500(self, _):
        """FIELD 引用的字段在事件记录与风险快照均无值：正常拒绝（而非 expected=None 遍历 TypeError）"""
        _, risk = self._create_drill_env(
            strategy_configs={
                "risk_meta_field_config": [
                    self._field_config(
                        "client_ip",
                        self.TOOL_UID,
                        [{"source_field": "ip", "target_value_type": "field", "target_value": "client_ip"}],
                    )
                ]
            },
            risk_kwargs={"event_data": {"other_field": "x"}},
        )
        mocked_event = {"operator": "someone", "event_time": "2026-11-26 10:00:00", "event_data": {"other": "x"}}
        with mock.patch(
            "services.web.common.caller_permission.resource.risk.list_event",
            return_value={"page": 1, "num_pages": 1, "total": 1, "results": [mocked_event]},
        ):
            data = self._build_request(risk, "client_ip", [{"raw_name": "ip", "value": "anything"}])
            with self.assertRaises(PermissionException):
                should_skip_permission_from(data, username="u1")

    @mock.patch("services.web.risk.permissions.RiskViewPermission.has_risk_permission", return_value=True)
    def test_time_field_reference_ceil_seconds(self, _):
        """FIELD 引用最后发现时间（带微秒）：详情序列化向上取整到下一秒，传取整后的值应放行"""
        import datetime as dt_module

        from django.utils import timezone

        # 本地时区 10:00:00.500 → 详情序列化输出 "10:00:01"（RiskInfoSerializer.get_event_end_time）
        event_end_time = timezone.make_aware(
            dt_module.datetime(2026, 11, 26, 10, 0, 0, 500000), timezone.get_current_timezone()
        )
        _, risk = self._create_drill_env(
            strategy_configs={
                "risk_meta_field_config": [
                    self._field_config(
                        "event_end_time",
                        self.TOOL_UID,
                        [
                            {
                                "source_field": "eets",
                                "target_value_type": "field",
                                "target_field_type": "basic",
                                "target_value": "event_end_time",
                            }
                        ],
                    )
                ]
            },
            risk_kwargs={"event_end_time": event_end_time},
        )
        ceil_value = timezone.localtime(event_end_time).replace(microsecond=0) + dt_module.timedelta(seconds=1)
        ceil_str = ceil_value.strftime("%Y-%m-%d %H:%M:%S")
        data = self._build_request(risk, "event_end_time", [{"raw_name": "eets", "value": ceil_str}])
        self.assertTrue(should_skip_permission_from(data, username="u1"))

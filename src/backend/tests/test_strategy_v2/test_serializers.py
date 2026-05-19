# -*- coding: utf-8 -*-
"""
strategy_v2 serializers 单测：覆盖复杂策略校验逻辑
"""
import unittest.mock

from rest_framework import serializers

from services.web.analyze.constants import ControlTypeChoices
from services.web.analyze.models import Control, ControlVersion
from services.web.scene.constants import (
    BindingType,
    ResourceVisibilityType,
    VisibilityScope,
)
from services.web.scene.filters import BindingMetadataHelper
from services.web.scene.models import ResourceBinding
from services.web.strategy_v2.constants import LinkTableTableType  # 添加导入
from services.web.strategy_v2.constants import (
    RiskLevel,
    RuleAuditSourceType,
    StrategyAlgorithmOperator,
    StrategyOperator,
    StrategyType,
)
from services.web.strategy_v2.models import LinkTable
from services.web.strategy_v2.serializers import (
    CreateStrategyRequestSerializer,
    RuleAuditSerializer,
    UpdateStrategyRequestSerializer,
)
from services.web.tool.constants import ToolTypeEnum
from services.web.tool.models import Tool
from tests.base import TestCase


class StrategySerializersTest(TestCase):
    def setUp(self):
        super().setUp()
        self.control = Control.objects.create(
            control_id="control-bkm",
            control_name="BKM Control",
            control_type_id=ControlTypeChoices.BKM.value,
        )
        ControlVersion.objects.create(control_id=self.control.control_id, control_version=1)
        # 创建场景用于 ResourceBinding
        from services.web.scene.models import Scene

        self.scene = Scene.objects.create(name="test_scene_serializer", description="test")
        self.another_scene = Scene.objects.create(name="another_scene_serializer", description="test")
        self.scene_id = self.scene.scene_id
        self.notice_group = self._create_notice_group("same-scene-group", self.scene_id)
        self.another_notice_group = self._create_notice_group("another-scene-group", self.another_scene.scene_id)
        self.tool = self._create_tool("same-scene-tool", self.scene_id)
        self.another_tool = self._create_tool("another-scene-tool", self.another_scene.scene_id)
        self.link_table = self._create_link_table("same-scene-link-table", self.scene_id)
        self.another_link_table = self._create_link_table("another-scene-link-table", self.another_scene.scene_id)

    def _create_notice_group(self, group_name, scene_id):
        from apps.notice.models import NoticeGroup

        notice_group = NoticeGroup.objects.create(
            group_name=group_name,
            group_member=["admin"],
            notice_config=[{"msg_type": "mail"}],
        )
        BindingMetadataHelper.create_resource_binding(
            resource_id=str(notice_group.group_id),
            resource_type=ResourceVisibilityType.NOTICE_GROUP,
            scene_id=scene_id,
        )
        return notice_group

    def _create_tool(self, name, scene_id):
        tool = Tool.objects.create(
            namespace=self.namespace,
            name=name,
            version=1,
            tool_type=ToolTypeEnum.API.value,
            config={},
            permission_owner="admin",
        )
        BindingMetadataHelper.create_resource_binding(
            resource_id=str(tool.uid),
            resource_type=ResourceVisibilityType.TOOL,
            scene_id=scene_id,
        )
        return tool

    def _create_platform_tool(self, name, visibility_type):
        tool = Tool.objects.create(
            namespace=self.namespace,
            name=name,
            version=1,
            tool_type=ToolTypeEnum.API.value,
            config={},
            permission_owner="admin",
        )
        ResourceBinding.objects.create(
            resource_id=str(tool.uid),
            resource_type=ResourceVisibilityType.TOOL,
            binding_type=BindingType.PLATFORM_BINDING,
            visibility_type=visibility_type,
        )
        return tool

    def _create_link_table(self, name, scene_id):
        link_table = LinkTable.objects.create(
            namespace=self.namespace,
            version=1,
            name=name,
            config={"links": []},
        )
        BindingMetadataHelper.create_resource_binding(
            resource_id=str(link_table.uid),
            resource_type=ResourceVisibilityType.LINK_TABLE,
            scene_id=scene_id,
        )
        return link_table

    def _build_model_strategy_payload(self):
        return {
            "namespace": self.namespace,
            "strategy_name": "model_strategy",
            "scene_id": self.scene_id,
            "control_id": self.control.control_id,
            "control_version": 1,
            "strategy_type": StrategyType.MODEL.value,
            "configs": {
                "agg_condition": [
                    {
                        "key": "username",
                        "value": ["admin"],
                        "method": StrategyOperator.EQ.value,
                        "condition": "and",
                    }
                ],
                "agg_dimension": ["username"],
                "agg_interval": 60,
                "algorithms": [{"method": StrategyAlgorithmOperator.GT.value, "threshold": 1}],
                "detects": {"count": 1, "alert_window": 1},
            },
            "tags": ["test"],
            "notice_groups": [],
            "description": "",
            "risk_level": RiskLevel.HIGH.value,
            "risk_hazard": "",
            "risk_guidance": "",
            "risk_title": "risk",
            "processor_groups": [self.notice_group.group_id],
            "event_basic_field_configs": [],
            "event_data_field_configs": [],
            "event_evidence_field_configs": [],
            "risk_meta_field_config": [],
        }

    def _build_rule_strategy_payload(self):
        return {
            "namespace": self.namespace,
            "strategy_name": "rule_strategy",
            "scene_id": self.scene_id,
            "strategy_type": StrategyType.RULE.value,
            "configs": {
                "config_type": "LinkTable",
                "data_source": {
                    "source_type": RuleAuditSourceType.REALTIME.value,
                    "link_table": {
                        "uid": str(self.link_table.uid),
                        "version": self.link_table.version,
                    },
                },
                "select": [
                    {
                        "table": "table",
                        "raw_name": "field",
                        "display_name": "field",
                        "field_type": "string",
                        "aggregate": None,
                    }
                ],
                "where": None,
            },
            "tags": [],
            "notice_groups": [],
            "description": "",
            "risk_level": RiskLevel.HIGH.value,
            "risk_hazard": "",
            "risk_guidance": "",
            "risk_title": "risk",
            "processor_groups": [self.notice_group.group_id],
            "event_basic_field_configs": [
                {
                    "field_name": "raw_event_id",
                    "display_name": "raw_event_id",
                    "is_priority": False,
                    "description": "",
                    "map_config": {"target_value": "event-1"},
                },
                {
                    "field_name": "event_source",
                    "display_name": "event_source",
                    "is_priority": False,
                    "description": "",
                    "map_config": {"target_value": "bk_audit"},
                },
                {
                    "field_name": "operator",
                    "display_name": "operator",
                    "is_priority": False,
                    "description": "",
                    "map_config": {"target_value": "admin"},
                },
            ],
            "event_data_field_configs": [
                {
                    "field_name": "field",
                    "display_name": "field",
                    "is_priority": False,
                    "description": "",
                    "drill_config": [
                        {
                            "tool": {"uid": str(self.tool.uid), "version": self.tool.version},
                            "config": [],
                            "drill_name": "tool",
                        }
                    ],
                }
            ],
            "event_evidence_field_configs": [],
            "risk_meta_field_config": [],
        }

    def test_create_strategy_serializer_valid_model_strategy(self):
        serializer = CreateStrategyRequestSerializer(data=self._build_model_strategy_payload())
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["control_id"], self.control.control_id)
        # 模型策略不应强制配置联表字段
        self.assertIsNone(serializer.validated_data.get("link_table_uid"))

    def test_create_strategy_serializer_requires_control_version(self):
        payload = self._build_model_strategy_payload()
        payload.pop("control_version")
        serializer = CreateStrategyRequestSerializer(data=payload)
        self.assertFalse(serializer.is_valid())
        self.assertIn("params_error", serializer.errors)

    def test_create_strategy_serializer_rejects_sql_for_model_strategy(self):
        payload = self._build_model_strategy_payload()
        payload["sql"] = "SELECT 1"
        serializer = CreateStrategyRequestSerializer(data=payload)
        self.assertFalse(serializer.is_valid())
        self.assertIn("params_error", serializer.errors)

    def test_rule_audit_serializer_requires_schedule_for_batch_source(self):
        rule_data = {
            "config_type": "EventLog",
            "data_source": {
                "source_type": "batch",
                "rt_id": "table",
                "system_ids": ["bklog"],
            },
            "select": [
                {
                    "table": "table",
                    "raw_name": "field",
                    "display_name": "field",
                    "field_type": "string",
                    "aggregate": None,
                }
            ],
            "where": None,
        }
        serializer = RuleAuditSerializer(data=rule_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("batch", str(serializer.errors).lower())

    def test_rule_audit_serializer_normalizes_empty_where(self):
        rule_data = {
            "config_type": "EventLog",
            "data_source": {
                "source_type": RuleAuditSourceType.REALTIME.value,
                "rt_id": "table",
                "system_ids": ["bklog"],
            },
            "select": [
                {
                    "table": "table",
                    "raw_name": "field",
                    "display_name": "field",
                    "field_type": "string",
                    "aggregate": None,
                }
            ],
            "where": {"conditions": []},
        }
        serializer = RuleAuditSerializer(data=rule_data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertIsNone(serializer.validated_data["where"])

    def test_create_strategy_serializer_rejects_cross_scene_notice_group(self):
        payload = self._build_model_strategy_payload()
        payload["notice_groups"] = [self.another_notice_group.group_id]

        serializer = CreateStrategyRequestSerializer(data=payload)

        self.assertFalse(serializer.is_valid())
        self.assertIn("notice_groups", str(serializer.errors))

    def test_create_strategy_serializer_rejects_cross_scene_tool(self):
        payload = self._build_rule_strategy_payload()
        payload["event_data_field_configs"][0]["drill_config"][0]["tool"] = {
            "uid": str(self.another_tool.uid),
            "version": self.another_tool.version,
        }

        serializer = CreateStrategyRequestSerializer(data=payload)

        self.assertFalse(serializer.is_valid())
        self.assertIn("tool", str(serializer.errors))

    def test_create_strategy_serializer_allows_platform_visible_tool(self):
        platform_tool = self._create_platform_tool("platform-visible-tool", VisibilityScope.ALL_SCENES)
        payload = self._build_rule_strategy_payload()
        payload["event_data_field_configs"][0]["drill_config"][0]["tool"] = {
            "uid": str(platform_tool.uid),
            "version": platform_tool.version,
        }

        serializer = CreateStrategyRequestSerializer(data=payload)

        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_create_strategy_serializer_checks_tool_visibility_by_latest_tool_uid(self):
        Tool.objects.create(
            namespace=self.namespace,
            uid=self.tool.uid,
            name="same-scene-tool-v2",
            version=2,
            tool_type=ToolTypeEnum.API.value,
            config={},
            permission_owner="admin",
        )
        payload = self._build_rule_strategy_payload()
        payload["event_data_field_configs"][0]["drill_config"][0]["tool"] = {
            "uid": str(self.tool.uid),
            "version": 1,
        }

        serializer = CreateStrategyRequestSerializer(data=payload)

        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_create_strategy_serializer_rejects_cross_scene_link_table(self):
        payload = self._build_rule_strategy_payload()
        payload["configs"]["data_source"]["link_table"] = {
            "uid": str(self.another_link_table.uid),
            "version": self.another_link_table.version,
        }

        serializer = CreateStrategyRequestSerializer(data=payload)

        self.assertFalse(serializer.is_valid())
        self.assertIn("link_table", str(serializer.errors))


class TestReportConfigValidation(TestCase):
    def setUp(self):
        super().setUp()
        self.control = Control.objects.create(
            control_id="control-bkm",
            control_name="BKM Control",
            control_type_id=ControlTypeChoices.BKM.value,
        )
        ControlVersion.objects.create(control_id=self.control.control_id, control_version=1)
        # 创建场景用于 ResourceBinding
        from services.web.scene.models import Scene

        self.scene = Scene.objects.create(name="test_scene_report", description="test")
        self.scene_id = self.scene.scene_id
        self.another_scene = Scene.objects.create(name="another_scene_report", description="test")
        self.notice_group = self._create_notice_group("report-same-scene-group", self.scene_id)
        self.another_notice_group = self._create_notice_group("report-another-scene-group", self.another_scene.scene_id)

    def _create_notice_group(self, group_name, scene_id):
        from apps.notice.models import NoticeGroup

        notice_group = NoticeGroup.objects.create(
            group_name=group_name,
            group_member=["admin"],
            notice_config=[{"msg_type": "mail"}],
        )
        BindingMetadataHelper.create_resource_binding(
            resource_id=str(notice_group.group_id),
            resource_type=ResourceVisibilityType.NOTICE_GROUP,
            scene_id=scene_id,
        )
        return notice_group

    def _build_base_payload(self):
        """构建基础策略 payload"""
        return {
            "namespace": self.namespace,
            "strategy_name": "test-strategy",
            "scene_id": self.scene_id,
            "control_id": self.control.control_id,
            "control_version": 1,
            "strategy_type": StrategyType.MODEL.value,
            "configs": {
                "agg_condition": [
                    {
                        "key": "username",
                        "value": ["admin"],
                        "method": StrategyOperator.EQ.value,
                        "condition": "and",
                    }
                ],
                "agg_dimension": ["username"],
                "agg_interval": 60,
                "algorithms": [{"method": StrategyAlgorithmOperator.GT.value, "threshold": 1}],
                "detects": {"count": 1, "alert_window": 1},
            },
            "tags": [],
            "notice_groups": [],
            "description": "",
            "risk_level": RiskLevel.HIGH.value,
            "risk_hazard": "",
            "risk_guidance": "",
            "risk_title": "risk",
            "processor_groups": [self.notice_group.group_id],
            "event_basic_field_configs": [],
            "event_data_field_configs": [],
            "event_evidence_field_configs": [],
            "risk_meta_field_config": [],
        }

    def test_create_strategy_report_enabled_with_config(self):
        """测试创建策略：report_enabled=True 且有 report_config -> 通过"""
        payload = self._build_base_payload()
        payload["report_enabled"] = True
        payload["report_config"] = {
            "template": "Test template {{ risk.title }}",
            "ai_variables": [
                {
                    "name": "ai.summary",
                    "prompt_template": "请总结风险",
                }
            ],
        }

        serializer = CreateStrategyRequestSerializer(data=payload)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_create_strategy_report_invalid_ai_variable_name(self):
        """测试创建策略：report_config AI 变量名不符合规范 -> 失败"""
        payload = self._build_base_payload()
        payload["report_enabled"] = True
        payload["report_config"] = {
            "template": "Test template {{ risk.title }}",
            "ai_variables": [
                {
                    "name": "ai.1summary",
                    "prompt_template": "请总结风险",
                }
            ],
        }

        serializer = CreateStrategyRequestSerializer(data=payload)
        self.assertFalse(serializer.is_valid())
        self.assertIn("report_config", str(serializer.errors).lower())

    def test_create_strategy_report_enabled_without_config(self):
        """测试创建策略：report_enabled=True 但 report_config 为空 -> 失败"""
        payload = self._build_base_payload()
        payload["report_enabled"] = True
        payload["report_config"] = None

        serializer = CreateStrategyRequestSerializer(data=payload)
        self.assertFalse(serializer.is_valid())
        self.assertIn("params_error", serializer.errors)
        # 检查错误信息包含 report_config
        error_msg = str(serializer.errors)
        self.assertIn("report_config", error_msg.lower())

    def test_create_strategy_report_disabled_without_config(self):
        """测试创建策略：report_enabled=False 且 report_config 为空 -> 通过"""
        payload = self._build_base_payload()
        payload["report_enabled"] = False
        payload["report_config"] = None

        serializer = CreateStrategyRequestSerializer(data=payload)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_create_strategy_report_disabled_with_config(self):
        """测试创建策略：report_enabled=False 但有 report_config -> 通过（允许这种情况）"""
        payload = self._build_base_payload()
        payload["report_enabled"] = False
        payload["report_config"] = {
            "template": "Test template",
            "ai_variables": [],
        }

        serializer = CreateStrategyRequestSerializer(data=payload)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_update_strategy_report_enabled_with_config(self):
        """测试更新策略：report_enabled=True 且有 report_config -> 通过"""
        from services.web.strategy_v2.models import Strategy

        strategy = Strategy.objects.create(
            namespace=self.namespace,
            strategy_name="existing-strategy",
            control_id=self.control.control_id,
            control_version=1,
            strategy_type=StrategyType.MODEL.value,
            risk_level=RiskLevel.HIGH.value,
            risk_title="risk",
        )

        payload = self._build_base_payload()
        payload["strategy_id"] = strategy.strategy_id
        payload["strategy_name"] = "updated-strategy"
        payload["report_enabled"] = True
        payload["report_config"] = {
            "template": "Updated template {{ risk.title }}",
            "ai_variables": [
                {
                    "name": "ai.summary",
                    "prompt_template": "请总结风险",
                }
            ],
        }

        serializer = UpdateStrategyRequestSerializer(data=payload)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_update_strategy_report_enabled_without_config(self):
        """测试更新策略：report_enabled=True 但 report_config 为空 -> 失败"""
        from services.web.strategy_v2.models import Strategy

        strategy = Strategy.objects.create(
            namespace=self.namespace,
            strategy_name="existing-strategy",
            control_id=self.control.control_id,
            control_version=1,
            strategy_type=StrategyType.MODEL.value,
            risk_level=RiskLevel.HIGH.value,
            risk_title="risk",
        )

        payload = self._build_base_payload()
        payload["strategy_id"] = strategy.strategy_id
        payload["strategy_name"] = "updated-strategy"
        payload["report_enabled"] = True
        payload["report_config"] = None

        serializer = UpdateStrategyRequestSerializer(data=payload)
        self.assertFalse(serializer.is_valid())
        self.assertIn("params_error", serializer.errors)
        # 检查错误信息包含 report_config
        error_msg = str(serializer.errors)
        self.assertIn("report_config", error_msg.lower())

    def test_update_strategy_serializer_rejects_cross_scene_processor_group(self):
        """测试更新策略：processor_groups 引用其他场景通知组 -> 失败"""
        from services.web.strategy_v2.models import Strategy

        strategy = Strategy.objects.create(
            namespace=self.namespace,
            strategy_name="existing-strategy",
            control_id=self.control.control_id,
            control_version=1,
            strategy_type=StrategyType.MODEL.value,
            risk_level=RiskLevel.HIGH.value,
            risk_title="risk",
        )
        BindingMetadataHelper.create_resource_binding(
            resource_id=str(strategy.strategy_id),
            resource_type=ResourceVisibilityType.STRATEGY,
            scene_id=self.scene_id,
        )

        payload = self._build_base_payload()
        payload["strategy_id"] = strategy.strategy_id
        payload["strategy_name"] = "updated-strategy"
        payload["processor_groups"] = [self.another_notice_group.group_id]

        serializer = UpdateStrategyRequestSerializer(data=payload)

        self.assertFalse(serializer.is_valid())
        self.assertIn("processor_groups", str(serializer.errors))


class TestLinkTableDataPermissionMixin(TestCase):
    """LinkTableDataPermissionMixin 权限验证测试"""

    def setUp(self):
        super().setUp()
        # 创建场景用于测试
        from services.web.scene.models import Scene

        self.scene = Scene.objects.create(name="test_permission_scene", description="test")
        self.scene_id = self.scene.scene_id

        # 创建用于测试的 LinkTableDataPermissionMixin 实例
        from services.web.strategy_v2.serializers import (
            CreateLinkTableRequestSerializer,
        )

        self.mixin_instance = CreateLinkTableRequestSerializer()

    def _create_mock_link_table_config(self, system_ids=None, rt_ids=None):
        """创建模拟的联表配置"""
        config = {"links": []}

        if system_ids or rt_ids:
            link = {}
            if system_ids:
                link["left_table"] = {
                    "system_ids": system_ids[:1] if system_ids else [],
                    "table_type": LinkTableTableType.EVENT_LOG.value,  # 使用正确的枚举值
                }
                if len(system_ids) > 1:
                    link["right_table"] = {
                        "system_ids": system_ids[1:],
                        "table_type": LinkTableTableType.EVENT_LOG.value,  # 使用正确的枚举值
                    }
            if rt_ids:
                link["left_table"] = link.get("left_table", {})
                link["left_table"]["rt_id"] = rt_ids[0] if rt_ids else None
                link["left_table"]["table_type"] = LinkTableTableType.BIZ_RT.value  # 使用正确的枚举值
                if len(rt_ids) > 1:
                    link["right_table"] = link.get("right_table", {})
                    link["right_table"]["rt_id"] = rt_ids[1]
                    link["right_table"]["table_type"] = LinkTableTableType.BIZ_RT.value  # 使用正确的枚举值

            config["links"].append(link)

        return config

    @unittest.mock.patch('apps.meta.resources.SystemListAllResource')
    @unittest.mock.patch('services.web.scene.data_filter.SceneDataFilter')
    def test_validate_link_table_data_permission_no_scene_id(self, mock_scene_data_filter, mock_system_resource):
        """测试没有场景ID时不进行权限验证"""
        # 创建没有场景ID的联表配置数据
        data = {
            "namespace": "test_namespace",
            "name": "test_link_table",
            "config": self._create_mock_link_table_config(["system1"], ["rt1"]),
        }

        # 使用序列化器进行验证
        serializer = self.mixin_instance
        serializer.initial_data = data

        # 应该跳过权限验证，不抛出异常
        serializer._validate_link_table_data_permission(data)

        # 不应该调用权限检查方法
        mock_system_resource.return_value.request.assert_not_called()
        mock_scene_data_filter.get_table_ids.assert_not_called()

    @unittest.mock.patch('apps.meta.resources.SystemListAllResource')
    @unittest.mock.patch('services.web.scene.data_filter.SceneDataFilter')
    def test_validate_link_table_data_permission_no_config(self, mock_scene_data_filter, mock_system_resource):
        """测试没有配置时不进行权限验证"""
        # 创建没有配置的数据
        data = {"namespace": "test_namespace", "name": "test_link_table", "scene_id": self.scene_id}

        # 使用序列化器进行验证
        serializer = self.mixin_instance
        serializer.initial_data = data

        serializer._validate_link_table_data_permission(data)

        # 不应该调用权限检查方法
        mock_system_resource.return_value.request.assert_not_called()
        mock_scene_data_filter.get_table_ids.assert_not_called()

    @unittest.mock.patch('apps.meta.resources.SystemListAllResource')
    @unittest.mock.patch('services.web.scene.data_filter.SceneDataFilter')
    def test_validate_link_table_data_permission_no_links(self, mock_scene_data_filter, mock_system_resource):
        """测试没有联表时不进行权限验证"""
        # 创建没有联表的配置数据
        data = {
            "namespace": "test_namespace",
            "name": "test_link_table",
            "scene_id": self.scene_id,
            "config": {"links": []},
        }

        # 使用序列化器进行验证
        serializer = self.mixin_instance
        serializer.initial_data = data

        serializer._validate_link_table_data_permission(data)

        # 不应该调用权限检查方法
        mock_system_resource.return_value.request.assert_not_called()
        mock_scene_data_filter.get_table_ids.assert_not_called()

    @unittest.mock.patch('apps.meta.resources.SystemListAllResource')
    @unittest.mock.patch('services.web.scene.data_filter.SceneDataFilter')
    def test_validate_link_table_data_permission_system_success(self, mock_scene_data_filter, mock_system_resource):
        """测试系统权限验证成功"""
        # 模拟授权的系统
        mock_system_resource.return_value.request.return_value = [{"system_id": "system1"}, {"system_id": "system2"}]

        # 创建完整的联表配置数据
        data = {
            "namespace": "test_namespace",
            "name": "test_link_table",
            "scene_id": self.scene_id,
            "config": self._create_mock_link_table_config(["system1", "system2"]),
        }

        # 使用序列化器进行验证
        serializer = self.mixin_instance

        # 应该正常通过，不抛出异常
        serializer.validate(data)

        # 验证权限检查被调用
        mock_system_resource.return_value.request.assert_called_once()

    @unittest.mock.patch('apps.meta.resources.SystemListAllResource')
    @unittest.mock.patch('services.web.scene.data_filter.SceneDataFilter')
    def test_validate_link_table_data_permission_system_unauthorized(
        self, mock_scene_data_filter, mock_system_resource
    ):
        """测试系统权限验证失败"""
        # 模拟授权的系统
        mock_system_resource.return_value.request.return_value = [{"system_id": "system1"}]

        # 创建完整的联表配置数据
        data = {
            "namespace": "test_namespace",
            "name": "test_link_table",
            "scene_id": self.scene_id,
            "config": self._create_mock_link_table_config(["system1", "system2"]),
        }

        # 使用序列化器进行验证
        serializer = self.mixin_instance

        # 应该抛出验证错误
        with self.assertRaises(serializers.ValidationError) as cm:
            serializer.validate(data)

        self.assertIn("系统[system2]不在场景", str(cm.exception))

    @unittest.mock.patch('apps.meta.resources.SystemListAllResource')
    @unittest.mock.patch('services.web.scene.data_filter.SceneDataFilter')
    def test_validate_link_table_data_permission_system_permission_check_failed(
        self, mock_scene_data_filter, mock_system_resource
    ):
        """测试系统权限检查服务异常"""
        # 模拟权限检查抛出异常
        mock_system_resource.return_value.request.side_effect = Exception("Permission check failed")

        # 创建完整的联表配置数据
        data = {
            "namespace": "test_namespace",
            "name": "test_link_table",
            "scene_id": self.scene_id,
            "config": self._create_mock_link_table_config(["system1"]),
        }

        # 使用序列化器进行验证
        serializer = self.mixin_instance

        # 应该抛出验证错误
        with self.assertRaises(serializers.ValidationError) as cm:
            serializer.validate(data)

        self.assertIn("权限检查失败", str(cm.exception))

    @unittest.mock.patch('apps.meta.resources.SystemListAllResource')
    @unittest.mock.patch('services.web.scene.data_filter.SceneDataFilter.get_table_ids')
    def test_validate_link_table_data_permission_table_success(self, mock_get_table_ids, mock_system_resource):
        """测试数据表权限验证成功"""
        # 模拟授权的数据表
        mock_get_table_ids.return_value = ["rt1", "rt2"]

        # 创建完整的联表配置数据
        data = {
            "namespace": "test_namespace",
            "name": "test_link_table",
            "scene_id": self.scene_id,
            "config": self._create_mock_link_table_config(rt_ids=["rt1", "rt2"]),
        }

        # 使用序列化器进行验证
        serializer = self.mixin_instance

        # 应该正常通过，不抛出异常
        serializer.validate(data)

        # 验证权限检查被调用
        mock_get_table_ids.assert_called_once_with(self.scene_id)

    @unittest.mock.patch('apps.meta.resources.SystemListAllResource')
    @unittest.mock.patch('services.web.scene.data_filter.SceneDataFilter.get_table_ids')
    def test_validate_link_table_data_permission_table_unauthorized(self, mock_get_table_ids, mock_system_resource):
        """测试数据表权限验证失败"""
        # 模拟授权的数据表
        mock_get_table_ids.return_value = ["rt1"]

        # 创建完整的联表配置数据
        data = {
            "namespace": "test_namespace",
            "name": "test_link_table",
            "scene_id": self.scene_id,
            "config": self._create_mock_link_table_config(rt_ids=["rt1", "rt2"]),
        }

        # 使用序列化器进行验证
        serializer = self.mixin_instance

        # 应该抛出验证错误
        with self.assertRaises(serializers.ValidationError) as cm:
            serializer.validate(data)

        self.assertIn("数据表[rt2]不在场景", str(cm.exception))


class TestStrategyDataPermissionValidation(TestCase):
    """StrategySerializer 数据权限验证测试"""

    def setUp(self):
        super().setUp()
        # 创建场景用于测试
        from services.web.scene.models import Scene

        self.scene = Scene.objects.create(name="test_strategy_permission_scene", description="test")
        self.scene_id = self.scene.scene_id

        # 创建用于测试的 StrategySerializer 实例
        from services.web.strategy_v2.serializers import StrategySerializer

        self.serializer = StrategySerializer()

    def _create_mock_strategy_data(self, strategy_type, config_type=None, system_ids=None, rt_id=None):
        """创建模拟策略数据"""
        data = {
            "scene_id": self.scene_id,
            "strategy_type": strategy_type,
            "configs": {"config_type": config_type, "data_source": {}},
        }

        if system_ids:
            data["configs"]["data_source"]["system_ids"] = system_ids
        if rt_id:
            data["configs"]["data_source"]["rt_id"] = rt_id

        return data

    @unittest.mock.patch('apps.meta.resources.SystemListAllResource')
    @unittest.mock.patch('services.web.scene.data_filter.SceneDataFilter')
    def test_validate_strategy_data_permission_event_log_success(self, mock_scene_data_filter, mock_system_resource):
        """测试事件日志策略系统权限验证成功"""
        # 模拟授权的系统
        mock_system_resource.return_value.request.return_value = [{"system_id": "bklog"}, {"system_id": "bkssm"}]

        data = self._create_mock_strategy_data(
            strategy_type="rule", config_type="EventLog", system_ids=["bklog", "bkssm"]
        )

        # 应该正常通过，不抛出异常
        self.serializer._validate_strategy_data_permission(data)

        # 验证权限检查被调用
        mock_system_resource.return_value.request.assert_called_once()

    @unittest.mock.patch('apps.meta.resources.SystemListAllResource')
    @unittest.mock.patch('services.web.scene.data_filter.SceneDataFilter')
    def test_validate_strategy_data_permission_event_log_unauthorized_system(
        self, mock_scene_data_filter, mock_system_resource
    ):
        """测试事件日志策略系统权限验证失败"""
        # 模拟授权的系统
        mock_system_resource.return_value.request.return_value = [{"system_id": "bklog"}]

        data = self._create_mock_strategy_data(
            strategy_type="rule", config_type="EventLog", system_ids=["bklog", "bkssm"]  # bkssm 未授权
        )

        # 应该抛出验证错误
        with self.assertRaises(serializers.ValidationError) as cm:
            self.serializer._validate_strategy_data_permission(data)

        self.assertIn("系统[bkssm]不在场景", str(cm.exception))

    @unittest.mock.patch('apps.meta.resources.SystemListAllResource')
    @unittest.mock.patch('services.web.scene.data_filter.SceneDataFilter.get_table_ids')
    def test_validate_strategy_data_permission_biz_rt_success(self, mock_get_table_ids, mock_system_resource):
        """测试业务RT策略数据表权限验证成功"""
        # 模拟授权的数据表
        mock_get_table_ids.return_value = ["rt_table_1", "rt_table_2"]

        data = self._create_mock_strategy_data(strategy_type="rule", config_type="BizRt", rt_id="rt_table_1")

        # 应该正常通过，不抛出异常
        self.serializer._validate_strategy_data_permission(data)

        # 验证权限检查被调用
        mock_get_table_ids.assert_called_once_with(self.scene_id)

    @unittest.mock.patch('apps.meta.resources.SystemListAllResource')
    @unittest.mock.patch('services.web.scene.data_filter.SceneDataFilter.get_table_ids')
    def test_validate_strategy_data_permission_biz_rt_unauthorized_table(
        self, mock_get_table_ids, mock_system_resource
    ):
        """测试业务RT策略数据表权限验证失败"""
        # 模拟授权的数据表
        mock_get_table_ids.return_value = ["rt_table_1"]

        data = self._create_mock_strategy_data(strategy_type="rule", config_type="BizRt", rt_id="rt_table_2")  # 未授权的表

        # 应该抛出验证错误
        with self.assertRaises(serializers.ValidationError) as cm:
            self.serializer._validate_strategy_data_permission(data)

        self.assertIn("数据表[rt_table_2]不在场景", str(cm.exception))

    @unittest.mock.patch('apps.meta.resources.SystemListAllResource')
    @unittest.mock.patch('services.web.scene.data_filter.SceneDataFilter')
    def test_validate_strategy_data_permission_model_strategy_skip(self, mock_scene_data_filter, mock_system_resource):
        """测试模型策略跳过权限验证"""
        data = self._create_mock_strategy_data(strategy_type="model")

        # 模型策略不应该进行权限验证
        self.serializer._validate_strategy_data_permission(data)

        # 验证权限检查没有被调用
        mock_system_resource.return_value.request.assert_not_called()
        mock_scene_data_filter.get_table_ids.assert_not_called()

    @unittest.mock.patch('apps.meta.resources.SystemListAllResource')
    @unittest.mock.patch('services.web.scene.data_filter.SceneDataFilter')
    def test_validate_strategy_data_permission_system_permission_check_failed(
        self, mock_scene_data_filter, mock_system_resource
    ):
        """测试系统权限检查服务异常"""
        # 模拟权限检查抛出异常
        mock_system_resource.return_value.request.side_effect = Exception("Permission check failed")

        data = self._create_mock_strategy_data(strategy_type="rule", config_type="EventLog", system_ids=["bklog"])

        # 应该抛出验证错误
        with self.assertRaises(serializers.ValidationError) as cm:
            self.serializer._validate_strategy_data_permission(data)

        self.assertIn("权限检查失败", str(cm.exception))

    @unittest.mock.patch('apps.meta.resources.SystemListAllResource')
    @unittest.mock.patch('services.web.scene.data_filter.SceneDataFilter')
    def test_validate_strategy_data_permission_no_scene_id_skip(self, mock_scene_data_filter, mock_system_resource):
        """测试没有场景ID时跳过权限验证"""
        data = {
            "strategy_type": "rule",
            "configs": {"config_type": "EventLog", "data_source": {"system_ids": ["bklog"]}},
        }

        # 没有scene_id时应该跳过验证
        self.serializer._validate_strategy_data_permission(data)

        # 验证权限检查没有被调用
        mock_system_resource.return_value.request.assert_not_called()
        mock_scene_data_filter.get_table_ids.assert_not_called()

    @unittest.mock.patch('apps.meta.resources.SystemListAllResource')
    @unittest.mock.patch('services.web.scene.data_filter.SceneDataFilter')
    def test_validate_strategy_data_permission_empty_system_ids_skip(
        self, mock_scene_data_filter, mock_system_resource
    ):
        """测试空系统ID列表时跳过验证"""
        data = self._create_mock_strategy_data(strategy_type="rule", config_type="EventLog", system_ids=[])

        # 空系统ID列表应该跳过验证
        self.serializer._validate_strategy_data_permission(data)

        # 验证权限检查没有被调用
        mock_system_resource.return_value.request.assert_not_called()

    @unittest.mock.patch('apps.meta.resources.SystemListAllResource')
    @unittest.mock.patch('services.web.scene.data_filter.SceneDataFilter.get_table_ids')
    def test_validate_strategy_data_permission_empty_rt_id(self, mock_get_table_ids, mock_system_resource):
        """测试空RT ID跳过权限验证"""
        data = self._create_mock_strategy_data(strategy_type="rule", config_type="BizRT", rt_id="")

        # 空RT ID应该跳过验证
        self.serializer._validate_strategy_data_permission(data)

        # 验证权限检查没有被调用
        mock_get_table_ids.assert_not_called()

    @unittest.mock.patch('apps.meta.resources.SystemListAllResource')
    @unittest.mock.patch('services.web.scene.data_filter.SceneDataFilter.get_table_ids')
    def test_validate_strategy_data_permission_build_id_asset_config_type(
        self, mock_get_table_ids, mock_system_resource
    ):
        """测试BuildID Asset配置类型的权限验证"""
        # 模拟授权的数据表
        mock_get_table_ids.return_value = ["asset_table"]

        data = self._create_mock_strategy_data(strategy_type="rule", config_type="BuildIn", rt_id="asset_table")

        # 应该正常通过，不抛出异常
        self.serializer._validate_strategy_data_permission(data)

        # 验证权限检查被调用
        mock_get_table_ids.assert_called_once_with(self.scene_id)

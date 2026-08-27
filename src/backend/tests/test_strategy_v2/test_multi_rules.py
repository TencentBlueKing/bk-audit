# -*- coding: utf-8 -*-
"""
策略多规则校验与分派规则校验单元测试

覆盖：
- MultiRuleValidateMixin._check_rules: 发现规则校验
- MultiRuleValidateMixin._check_dispatch_rules: 分派规则校验
- 全局策略与场景策略区分逻辑
"""


from rest_framework import serializers

from services.web.analyze.constants import ControlTypeChoices
from services.web.analyze.models import Control, ControlVersion
from services.web.scene.constants import BindingType, ResourceVisibilityType
from services.web.scene.filters import BindingMetadataHelper
from services.web.scene.models import Scene
from services.web.strategy_v2.constants import RiskLevel, StrategyType
from services.web.strategy_v2.serializers import (
    CreateStrategyRequestSerializer,
    MultiRuleValidateMixin,
)
from tests.base import TestCase


class MultiRuleValidateMixinTest(TestCase):
    """MultiRuleValidateMixin 基础测试"""

    def setUp(self):
        super().setUp()
        self.mixin = MultiRuleValidateMixin()

    def test_condition_tree_is_empty_with_none(self):
        self.assertTrue(self.mixin._condition_tree_is_empty(None))

    def test_condition_tree_is_empty_with_empty_dict(self):
        self.assertTrue(self.mixin._condition_tree_is_empty({}))

    def test_condition_tree_is_empty_with_condition(self):
        self.assertFalse(self.mixin._condition_tree_is_empty({"condition": {"field": "test"}}))

    def test_condition_tree_is_empty_with_nested_empty(self):
        self.assertTrue(self.mixin._condition_tree_is_empty({"conditions": [{"conditions": []}]}))

    def test_walk_tree_leaves_with_none(self):
        """遍历 None 应该不产生任何结果"""
        leaves = list(self.mixin._walk_tree_leaves(None))
        self.assertEqual(leaves, [])

    def test_walk_tree_leaves_with_single_leaf(self):
        """遍历单个叶子节点"""
        leaf = {"field": "status", "operator": "eq"}
        node = {"condition": leaf}
        leaves = list(self.mixin._walk_tree_leaves(node))
        self.assertEqual(len(leaves), 1)
        self.assertEqual(leaves[0], leaf)

    def test_walk_tree_leaves_with_nested_tree(self):
        """遍历嵌套条件树"""
        leaf1 = {"field": "status", "operator": "eq"}
        leaf2 = {"field": "level", "operator": "eq"}
        node = {
            "connector": "and",
            "conditions": [
                {"condition": leaf1},
                {"condition": leaf2},
            ],
        }
        leaves = list(self.mixin._walk_tree_leaves(node))
        self.assertEqual(len(leaves), 2)


class CheckRulesTest(TestCase):
    """_check_rules: 发现规则校验测试"""

    def setUp(self):
        super().setUp()
        self.mixin = MultiRuleValidateMixin()
        self.valid_where = {
            "condition": {
                "field": {"table": "t", "raw_name": "f", "display_name": "f", "field_type": "string"},
                "operator": "eq",
                "filters": ["v"],
            }
        }
        self.valid_configs = {
            "select": [
                {
                    "table": "t",
                    "raw_name": "field1",
                    "display_name": "field1",
                    "field_type": "string",
                    "aggregate": None,
                },
                {
                    "table": "t",
                    "raw_name": "count",
                    "display_name": "count",
                    "field_type": "long",
                    "aggregate": "count",
                },
            ]
        }

    def test_model_strategy_rejects_rules(self):
        """模型策略不允许有发现规则"""
        attrs = {
            "strategy_type": StrategyType.MODEL.value,
            "rules": [{"rule_name": "r1", "conditions": {"where": self.valid_where}}],
        }
        with self.assertRaises(serializers.ValidationError) as cm:
            self.mixin._check_rules(attrs)
        self.assertIn("模型策略", str(cm.exception))

    def test_rule_strategy_requires_at_least_one_rule(self):
        """规则策略必须至少有一条发现规则"""
        attrs = {
            "strategy_type": StrategyType.RULE.value,
            "rules": [],
        }
        with self.assertRaises(serializers.ValidationError) as cm:
            self.mixin._check_rules(attrs)
        self.assertIn("至少配置一条", str(cm.exception))

    def test_rule_name_must_be_unique(self):
        """规则名称策略内唯一"""
        attrs = {
            "strategy_type": StrategyType.RULE.value,
            "configs": self.valid_configs,
            "rules": [
                {"rule_name": "same_name", "conditions": {"where": self.valid_where}},
                {"rule_name": "same_name", "conditions": {"where": self.valid_where}},
            ],
        }
        with self.assertRaises(serializers.ValidationError) as cm:
            self.mixin._check_rules(attrs)
        self.assertIn("唯一", str(cm.exception))

    def test_rule_requires_where_condition(self):
        """规则 where 必填"""
        attrs = {
            "strategy_type": StrategyType.RULE.value,
            "configs": self.valid_configs,
            "rules": [
                {"rule_name": "r1", "conditions": {"where": None}},
            ],
        }
        with self.assertRaises(serializers.ValidationError) as cm:
            self.mixin._check_rules(attrs)
        self.assertIn("where", str(cm.exception))

    def test_having_field_must_be_aggregate(self):
        """having 条件字段必须为聚合字段"""
        attrs = {
            "strategy_type": StrategyType.RULE.value,
            "configs": self.valid_configs,
            "rules": [
                {
                    "rule_name": "r1",
                    "conditions": {
                        "where": self.valid_where,
                        "having": {
                            "condition": {
                                "field": {
                                    "table": "t",
                                    "raw_name": "field1",
                                    "display_name": "field1",
                                    "field_type": "string",
                                },
                                "operator": "gt",
                                "filters": ["0"],
                            }
                        },
                    },
                },
            ],
        }
        with self.assertRaises(serializers.ValidationError) as cm:
            self.mixin._check_rules(attrs)
        self.assertIn("聚合字段", str(cm.exception))

    def test_having_field_must_exist_in_select(self):
        """having 条件字段必须存在于策略级 select 聚合字段中"""
        attrs = {
            "strategy_type": StrategyType.RULE.value,
            "configs": self.valid_configs,
            "rules": [
                {
                    "rule_name": "r1",
                    "conditions": {
                        "where": self.valid_where,
                        "having": {
                            "condition": {
                                "field": {
                                    "table": "t",
                                    "raw_name": "nonexistent",
                                    "display_name": "nonexistent",
                                    "field_type": "long",
                                    "aggregate": "count",
                                },
                                "operator": "gt",
                                "filters": ["0"],
                            }
                        },
                    },
                },
            ],
        }
        with self.assertRaises(serializers.ValidationError) as cm:
            self.mixin._check_rules(attrs)
        self.assertIn("不存在于", str(cm.exception))

    def test_no_aggregate_fields_disallows_having(self):
        """行级配置（无聚合字段）时禁 having"""
        configs_no_agg = {
            "select": [
                {
                    "table": "t",
                    "raw_name": "field1",
                    "display_name": "field1",
                    "field_type": "string",
                    "aggregate": None,
                }
            ]
        }
        attrs = {
            "strategy_type": StrategyType.RULE.value,
            "configs": configs_no_agg,
            "rules": [
                {
                    "rule_name": "r1",
                    "conditions": {
                        "where": self.valid_where,
                        "having": {
                            "condition": {
                                "field": {
                                    "table": "t",
                                    "raw_name": "field1",
                                    "display_name": "field1",
                                    "field_type": "string",
                                    "aggregate": None,
                                },
                                "operator": "gt",
                                "filters": ["0"],
                            }
                        },
                    },
                },
            ],
        }
        with self.assertRaises(serializers.ValidationError) as cm:
            self.mixin._check_rules(attrs)
        self.assertIn("having", str(cm.exception))

    def test_valid_multi_rules(self):
        """多规则校验通过"""
        attrs = {
            "strategy_type": StrategyType.RULE.value,
            "configs": self.valid_configs,
            "rules": [
                {
                    "rule_name": "rule_high",
                    "conditions": {"where": self.valid_where},
                    "risk_level": RiskLevel.HIGH.value,
                },
                {"rule_name": "rule_low", "conditions": {"where": self.valid_where}, "risk_level": RiskLevel.LOW.value},
            ],
        }
        # 应该不抛异常
        result = self.mixin._check_rules(attrs)
        self.assertEqual(result, attrs)


class CheckDispatchRulesTest(TestCase):
    """_check_dispatch_rules: 分派规则校验测试"""

    def setUp(self):
        super().setUp()
        self.scene = Scene.objects.create(name="test_dispatch_scene", description="test")
        self.other_scene = Scene.objects.create(name="test_dispatch_other_scene", description="test")
        from apps.notice.models import NoticeGroup

        self.notice_group = NoticeGroup.objects.create(
            group_name="test_dispatch_group",
            group_member=["admin"],
            notice_config=[{"msg_type": "mail"}],
        )
        BindingMetadataHelper.create_resource_binding(
            resource_id=str(self.notice_group.group_id),
            resource_type=ResourceVisibilityType.NOTICE_GROUP,
            scene_id=self.scene.scene_id,
        )
        # 使用完整的序列化器实例，因为它包含了 _validate_notice_groups 方法
        self.mixin = CreateStrategyRequestSerializer()

    def test_non_platform_binding_rejects_dispatch_rules(self):
        """非全局策略不允许配置分派规则"""
        attrs = {
            "binding_type": BindingType.SCENE_BINDING,
            "dispatch_rules": [
                {
                    "rule_name": "r1",
                    "conditions": {},
                    "target_scene_id": self.scene.scene_id,
                    "processor": [self.notice_group.group_id],
                    "follower": [self.notice_group.group_id],
                    "confirmer": [self.notice_group.group_id],
                }
            ],
        }
        with self.assertRaises(serializers.ValidationError) as cm:
            self.mixin._check_dispatch_rules(attrs)
        self.assertIn("仅全局策略", str(cm.exception))

    def test_platform_binding_requires_dispatch_rules(self):
        """全局策略必须至少配置一条分派规则"""
        attrs = {
            "binding_type": BindingType.PLATFORM_BINDING,
            "dispatch_rules": [],
        }
        with self.assertRaises(serializers.ValidationError) as cm:
            self.mixin._check_dispatch_rules(attrs)
        self.assertIn("至少配置一条", str(cm.exception))

    def test_dispatch_rule_name_must_be_unique(self):
        """分派规则名称策略内唯一"""
        attrs = {
            "binding_type": BindingType.PLATFORM_BINDING,
            "dispatch_rules": [
                {
                    "rule_name": "same_name",
                    "conditions": {"condition": {"field": "f", "operator": "eq", "filters": ["v"]}},
                    "target_scene_id": self.scene.scene_id,
                    "processor": [self.notice_group.group_id],
                    "follower": [self.notice_group.group_id],
                    "confirmer": [self.notice_group.group_id],
                },
                {
                    "rule_name": "same_name",
                    "conditions": {},
                    "target_scene_id": self.scene.scene_id,
                    "processor": [self.notice_group.group_id],
                    "follower": [self.notice_group.group_id],
                    "confirmer": [self.notice_group.group_id],
                },
            ],
        }
        with self.assertRaises(serializers.ValidationError) as cm:
            self.mixin._check_dispatch_rules(attrs)
        self.assertIn("唯一", str(cm.exception))

    def test_must_have_exactly_one_default_rule(self):
        """必须且仅能有一条默认分派规则"""
        # 无默认规则
        attrs = {
            "binding_type": BindingType.PLATFORM_BINDING,
            "dispatch_rules": [
                {
                    "rule_name": "r1",
                    "conditions": {"condition": {"field": "f", "operator": "eq", "filters": ["v"]}},
                    "target_scene_id": self.scene.scene_id,
                    "processor": [self.notice_group.group_id],
                    "follower": [self.notice_group.group_id],
                    "confirmer": [self.notice_group.group_id],
                },
            ],
        }
        with self.assertRaises(serializers.ValidationError) as cm:
            self.mixin._check_dispatch_rules(attrs)
        self.assertIn("默认分派规则", str(cm.exception))

    def test_multiple_default_rules_rejected(self):
        """多条默认规则被拒绝"""
        attrs = {
            "binding_type": BindingType.PLATFORM_BINDING,
            "dispatch_rules": [
                {
                    "rule_name": "default1",
                    "conditions": {},
                    "target_scene_id": self.scene.scene_id,
                    "processor": [self.notice_group.group_id],
                    "follower": [self.notice_group.group_id],
                    "confirmer": [self.notice_group.group_id],
                },
                {
                    "rule_name": "default2",
                    "conditions": {},
                    "target_scene_id": self.scene.scene_id,
                    "processor": [self.notice_group.group_id],
                    "follower": [self.notice_group.group_id],
                    "confirmer": [self.notice_group.group_id],
                },
            ],
        }
        with self.assertRaises(serializers.ValidationError) as cm:
            self.mixin._check_dispatch_rules(attrs)
        self.assertIn("默认分派规则", str(cm.exception))

    def test_processor_cannot_be_empty(self):
        """处理人不能为空"""
        attrs = {
            "binding_type": BindingType.PLATFORM_BINDING,
            "dispatch_rules": [
                {
                    "rule_name": "default",
                    "conditions": {},
                    "target_scene_id": self.scene.scene_id,
                    "processor": [],
                    "follower": [self.notice_group.group_id],
                    "confirmer": [self.notice_group.group_id],
                },
            ],
        }
        with self.assertRaises(serializers.ValidationError) as cm:
            self.mixin._check_dispatch_rules(attrs)
        self.assertIn("processor", str(cm.exception))

    def test_target_scene_must_exist(self):
        """目标场景必须存在"""
        attrs = {
            "binding_type": BindingType.PLATFORM_BINDING,
            "dispatch_rules": [
                {
                    "rule_name": "default",
                    "conditions": {},
                    "target_scene_id": 99999,
                    "processor": [self.notice_group.group_id],
                    "follower": [self.notice_group.group_id],
                    "confirmer": [self.notice_group.group_id],
                },
            ],
        }
        with self.assertRaises(serializers.ValidationError) as cm:
            self.mixin._check_dispatch_rules(attrs)
        self.assertIn("目标场景", str(cm.exception))

    def test_notice_group_must_belong_to_target_scene(self):
        """通知组必须属于目标场景"""
        # 创建另一个场景的通知组
        from apps.notice.models import NoticeGroup

        other_group = NoticeGroup.objects.create(
            group_name="other_scene_group",
            group_member=["admin"],
            notice_config=[{"msg_type": "mail"}],
        )
        BindingMetadataHelper.create_resource_binding(
            resource_id=str(other_group.group_id),
            resource_type=ResourceVisibilityType.NOTICE_GROUP,
            scene_id=self.other_scene.scene_id,
        )
        attrs = {
            "binding_type": BindingType.PLATFORM_BINDING,
            "dispatch_rules": [
                {
                    "rule_name": "default",
                    "conditions": {},
                    "target_scene_id": self.scene.scene_id,
                    "processor": [other_group.group_id],
                    "follower": [self.notice_group.group_id],
                    "confirmer": [self.notice_group.group_id],
                },
            ],
        }
        with self.assertRaises(serializers.ValidationError) as cm:
            self.mixin._check_dispatch_rules(attrs)
        self.assertIn("通知组", str(cm.exception))

    def test_valid_dispatch_rules(self):
        """有效的分派规则配置"""
        attrs = {
            "binding_type": BindingType.PLATFORM_BINDING,
            "dispatch_rules": [
                {
                    "rule_name": "high_risk",
                    "conditions": {"condition": {"field": "risk_level", "operator": "eq", "filters": ["HIGH"]}},
                    "target_scene_id": self.scene.scene_id,
                    "processor": [self.notice_group.group_id],
                    "follower": [self.notice_group.group_id],
                    "confirmer": [self.notice_group.group_id],
                },
                {
                    "rule_name": "default",
                    "conditions": {},
                    "target_scene_id": self.scene.scene_id,
                    "processor": [self.notice_group.group_id],
                    "follower": [self.notice_group.group_id],
                    "confirmer": [self.notice_group.group_id],
                },
            ],
        }
        result = self.mixin._check_dispatch_rules(attrs)
        self.assertEqual(result, attrs)
        # 验证 is_default 被自动设置
        self.assertFalse(result["dispatch_rules"][0]["is_default"])
        self.assertTrue(result["dispatch_rules"][1]["is_default"])


class PlatformVsSceneBindingTest(TestCase):
    """全局策略与场景策略区分逻辑测试"""

    def setUp(self):
        super().setUp()
        self.control = Control.objects.create(
            control_id="control-bkm",
            control_name="BKM Control",
            control_type_id=ControlTypeChoices.BKM.value,
        )
        ControlVersion.objects.create(control_id=self.control.control_id, control_version=1)
        self.scene = Scene.objects.create(name="test_binding_scene", description="test")
        from apps.notice.models import NoticeGroup

        self.notice_group = NoticeGroup.objects.create(
            group_name="test_binding_group",
            group_member=["admin"],
            notice_config=[{"msg_type": "mail"}],
        )
        BindingMetadataHelper.create_resource_binding(
            resource_id=str(self.notice_group.group_id),
            resource_type=ResourceVisibilityType.NOTICE_GROUP,
            scene_id=self.scene.scene_id,
        )

    def _build_platform_strategy_payload(self):
        """构建全局策略 payload"""
        return {
            "namespace": self.namespace,
            "strategy_name": "platform_strategy",
            "binding_type": BindingType.PLATFORM_BINDING,
            "control_id": self.control.control_id,
            "control_version": 1,
            "strategy_type": StrategyType.MODEL.value,
            "configs": {
                "agg_condition": [],
                "agg_dimension": [],
                "agg_interval": 60,
                "algorithms": [{"method": "gt", "threshold": 1}],
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
            "dispatch_rules": [
                {
                    "rule_name": "default",
                    "conditions": {},
                    "target_scene_id": self.scene.scene_id,
                    "processor": [self.notice_group.group_id],
                    "follower": [self.notice_group.group_id],
                    "confirmer": [self.notice_group.group_id],
                },
            ],
        }

    def _build_scene_strategy_payload(self):
        """构建场景策略 payload"""
        return {
            "namespace": self.namespace,
            "strategy_name": "scene_strategy",
            "scene_id": self.scene.scene_id,
            "binding_type": BindingType.SCENE_BINDING,
            "control_id": self.control.control_id,
            "control_version": 1,
            "strategy_type": StrategyType.MODEL.value,
            "configs": {
                "agg_condition": [],
                "agg_dimension": [],
                "agg_interval": 60,
                "algorithms": [{"method": "gt", "threshold": 1}],
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

    def test_platform_binding_requires_dispatch_rules(self):
        """全局策略必须有分派规则"""
        payload = self._build_platform_strategy_payload()
        payload["dispatch_rules"] = []
        serializer = CreateStrategyRequestSerializer(data=payload)
        self.assertFalse(serializer.is_valid())
        self.assertIn("分派规则", str(serializer.errors))

    def test_platform_binding_rejects_scene_id(self):
        """全局策略不允许携带 scene_id"""
        payload = self._build_platform_strategy_payload()
        payload["scene_id"] = self.scene.scene_id
        serializer = CreateStrategyRequestSerializer(data=payload)
        self.assertFalse(serializer.is_valid())
        self.assertIn("scene_id", str(serializer.errors))

    def test_scene_binding_requires_scene_id(self):
        """场景策略必须携带 scene_id"""
        payload = self._build_scene_strategy_payload()
        payload.pop("scene_id")
        serializer = CreateStrategyRequestSerializer(data=payload)
        self.assertFalse(serializer.is_valid())
        self.assertIn("scene_id", str(serializer.errors))

    def test_scene_binding_rejects_dispatch_rules(self):
        """场景策略不允许配置分派规则"""
        payload = self._build_scene_strategy_payload()
        payload["dispatch_rules"] = [
            {
                "rule_name": "default",
                "conditions": {},
                "target_scene_id": self.scene.scene_id,
                "processor": [self.notice_group.group_id],
                "follower": [self.notice_group.group_id],
                "confirmer": [self.notice_group.group_id],
            }
        ]
        serializer = CreateStrategyRequestSerializer(data=payload)
        self.assertFalse(serializer.is_valid())
        self.assertIn("分派规则", str(serializer.errors))

    def test_valid_platform_binding(self):
        """有效的全局策略配置"""
        payload = self._build_platform_strategy_payload()
        serializer = CreateStrategyRequestSerializer(data=payload)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["binding_type"], BindingType.PLATFORM_BINDING)

    def test_valid_scene_binding(self):
        """有效的场景策略配置"""
        payload = self._build_scene_strategy_payload()
        serializer = CreateStrategyRequestSerializer(data=payload)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["binding_type"], BindingType.SCENE_BINDING)
        self.assertEqual(serializer.validated_data["scene_id"], self.scene.scene_id)

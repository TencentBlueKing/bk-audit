# -*- coding: utf-8 -*-
from django.test import TestCase

from core.testing import assert_dict_contains
from services.web.scene.constants import VisibilityScope
from services.web.scene.models import Scene
from services.web.vision.constants import ReportGroupType
from services.web.vision.models import SceneReportGroup, VisionPanel
from services.web.vision.resources import (
    CreatePlatformPanel,
    CreateScenePanel,
    ListPlatformPanels,
    ListScenePanels,
    UpdatePlatformPanel,
    UpdateScenePanel,
)


class TestVisionPanelDefaultValueOverrides(TestCase):
    """测试 VisionPanel.default_value_overrides 字段"""

    def test_default_value_is_empty_dict(self):
        """未传配置时默认为空字典"""
        panel = VisionPanel.objects.create(
            id="test_panel_default_001",
            name="测试报表",
            scenario="default",
        )
        self.assertEqual(panel.default_value_overrides, {})

    def test_default_field_only_config(self):
        """测试只有 default 字段的配置（场景报表）"""
        config = {
            "default": {"time_filter_panel_uid": ["now-7d/d", "now"]},
        }
        panel = VisionPanel.objects.create(
            id="test_panel_default_only_001",
            name="只有 default 配置的报表",
            default_value_overrides=config,
        )
        self.assertEqual(
            panel.default_value_overrides["default"],
            {"time_filter_panel_uid": ["now-7d/d", "now"]},
        )
        self.assertNotIn("scenes", panel.default_value_overrides)
        self.assertNotIn("systems", panel.default_value_overrides)

    def test_valid_json_structure(self):
        """合法 JSON 结构可正常保存"""
        config = {
            "default": {"time_filter_panel_uid": ["now-7d/d", "now"]},
            "scenes": {
                "1001": {"time_filter_panel_uid": ["now-7d/d", "now"]},
                "1002": {"time_filter_panel_uid": ["now-1d/d", "now"]},
            },
            "systems": {
                "bk_cmdb": {"time_filter_panel_uid": ["now-30d/d", "now"]},
            },
        }
        panel = VisionPanel.objects.create(
            id="test_panel_valid_002",
            name="带配置报表",
            default_value_overrides=config,
        )
        self.assertEqual(
            panel.default_value_overrides["default"],
            {"time_filter_panel_uid": ["now-7d/d", "now"]},
        )
        self.assertEqual(
            panel.default_value_overrides["scenes"]["1001"],
            {"time_filter_panel_uid": ["now-7d/d", "now"]},
        )

    def test_invalid_structure_validation(self):
        """非法结构在 serializer 层校验失败"""
        from services.web.vision.serializers import CreatePlatformPanelRequestSerializer

        # 测试传入列表而非字典，应该校验失败
        data = {
            "name": "非法配置报表",
            "default_value_overrides": ["not", "a", "dict"],  # 应该是 dict
        }
        serializer = CreatePlatformPanelRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("default_value_overrides", serializer.errors)

        # 测试传入字符串而非字典，应该校验失败
        data = {
            "name": "非法配置报表",
            "default_value_overrides": "invalid_string",
        }
        serializer = CreatePlatformPanelRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("default_value_overrides", serializer.errors)

        # 测试传入数字而非字典，应该校验失败
        data = {
            "name": "非法配置报表",
            "default_value_overrides": 12345,
        }
        serializer = CreatePlatformPanelRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("default_value_overrides", serializer.errors)


class TestPanelCreationWithDefaultValueOverrides(TestCase):
    """测试创建报表时 default_value_overrides 的行为"""

    def setUp(self):
        self.scene1 = Scene.objects.create(name="场景 A")
        self.scene_group = SceneReportGroup.objects.create(
            scene=self.scene1,
            name="默认分组",
            group_type=ReportGroupType.CUSTOM,
            priority_index=1,
        )

    def test_create_platform_panel_default_empty_config(self):
        """平台报表创建时未传配置，默认为空"""
        resp = CreatePlatformPanel().request(
            {
                "name": "平台报表",
                "visibility": {"visibility_type": VisibilityScope.ALL_VISIBLE},
            }
        )
        panel = VisionPanel.objects.get(id=resp["id"])
        self.assertEqual(panel.default_value_overrides, {})

    def test_create_platform_panel_explicit_config(self):
        """平台报表创建时传入显式配置"""
        config = {
            "scenes": {"1001": {"time_filter": ["now-7d", "now"]}},
            "systems": {"bk_cmdb": {"time_filter": ["now-30d", "now"]}},
        }
        resp = CreatePlatformPanel().request(
            {
                "name": "带配置平台报表",
                "default_value_overrides": config,
                "visibility": {"visibility_type": VisibilityScope.ALL_VISIBLE},
            }
        )
        panel = VisionPanel.objects.get(id=resp["id"])
        self.assertEqual(panel.default_value_overrides, config)

    def test_create_scene_panel_default_empty_config(self):
        """场景报表创建时未传配置，默认为空"""
        resp = CreateScenePanel().request(
            {
                "scene_id": self.scene1.scene_id,
                "group_id": self.scene_group.id,
                "name": "场景报表",
            }
        )
        panel = VisionPanel.objects.get(id=resp["id"])
        self.assertEqual(panel.default_value_overrides, {})

    def test_create_scene_panel_explicit_config(self):
        """场景报表创建时传入显式配置"""
        config = {"scenes": {str(self.scene1.scene_id): {"time_filter": ["now-7d", "now"]}}}
        resp = CreateScenePanel().request(
            {
                "scene_id": self.scene1.scene_id,
                "group_id": self.scene_group.id,
                "name": "带配置场景报表",
                "default_value_overrides": config,
            }
        )
        panel = VisionPanel.objects.get(id=resp["id"])
        self.assertEqual(panel.default_value_overrides, config)


class TestPanelUpdateDefaultValueOverrides(TestCase):
    """测试更新报表时 default_value_overrides 的行为"""

    def setUp(self):
        self.scene1 = Scene.objects.create(name="场景 A")
        self.scene_group = SceneReportGroup.objects.create(
            scene=self.scene1,
            name="默认分组",
            group_type=ReportGroupType.CUSTOM,
            priority_index=1,
        )
        self.config = {
            "scenes": {"1001": {"time_filter": ["old"]}},
        }

    def test_update_without_field_keeps_original(self):
        """更新未传该字段时保持原值"""
        # 通过资源类创建报表，确保有 binding
        resp = CreatePlatformPanel().request(
            {
                "name": "平台报表",
                "default_value_overrides": self.config,
                "visibility": {"visibility_type": VisibilityScope.ALL_VISIBLE},
            }
        )
        panel = VisionPanel.objects.get(id=resp["id"])

        UpdatePlatformPanel().request(
            {
                "panel_id": panel.id,
                "name": "新名称",
            }
        )
        panel.refresh_from_db()
        self.assertEqual(
            panel.default_value_overrides["scenes"]["1001"],
            {"time_filter": ["old"]},
        )

    def test_update_explicit_empty_dict_clears_config(self):
        """显式传入 {} 清空配置"""
        resp = CreatePlatformPanel().request(
            {
                "name": "平台报表",
                "default_value_overrides": self.config,
                "visibility": {"visibility_type": VisibilityScope.ALL_VISIBLE},
            }
        )
        panel = VisionPanel.objects.get(id=resp["id"])

        UpdatePlatformPanel().request(
            {
                "panel_id": panel.id,
                "default_value_overrides": {},
            }
        )
        panel.refresh_from_db()
        self.assertEqual(panel.default_value_overrides, {})

    def test_update_partial_merge_not_supported(self):
        """更新为部分配置时是覆盖而非合并"""
        resp = CreatePlatformPanel().request(
            {
                "name": "平台报表",
                "default_value_overrides": self.config,
                "visibility": {"visibility_type": VisibilityScope.ALL_VISIBLE},
            }
        )
        panel = VisionPanel.objects.get(id=resp["id"])

        new_config = {"systems": {"bk_cmdb": {"time_filter": ["new"]}}}
        UpdatePlatformPanel().request(
            {
                "panel_id": panel.id,
                "default_value_overrides": new_config,
            }
        )
        panel.refresh_from_db()
        # 应该是完全覆盖，scenes 配置被清除
        self.assertNotIn("scenes", panel.default_value_overrides)
        self.assertIn("systems", panel.default_value_overrides)

    def test_update_scene_panel_keeps_config(self):
        """场景报表更新未传配置时保持原值"""
        resp = CreateScenePanel().request(
            {
                "scene_id": self.scene1.scene_id,
                "group_id": self.scene_group.id,
                "name": "场景报表",
                "default_value_overrides": self.config,
            }
        )
        panel = VisionPanel.objects.get(id=resp["id"])

        UpdateScenePanel().request(
            {
                "scene_id": self.scene1.scene_id,
                "group_id": self.scene_group.id,
                "panel_id": panel.id,
                "name": "新名称",
            }
        )
        panel.refresh_from_db()
        self.assertEqual(
            panel.default_value_overrides["scenes"]["1001"],
            {"time_filter": ["old"]},
        )

    def test_update_scene_panel_clears_config(self):
        """场景报表显式清空配置"""
        resp = CreateScenePanel().request(
            {
                "scene_id": self.scene1.scene_id,
                "group_id": self.scene_group.id,
                "name": "场景报表",
                "default_value_overrides": self.config,
            }
        )
        panel = VisionPanel.objects.get(id=resp["id"])

        UpdateScenePanel().request(
            {
                "scene_id": self.scene1.scene_id,
                "group_id": self.scene_group.id,
                "panel_id": panel.id,
                "default_value_overrides": {},
            }
        )
        panel.refresh_from_db()
        self.assertEqual(panel.default_value_overrides, {})


class TestManagementListReturnsConfig(TestCase):
    """测试管理列表接口完整返回配置"""

    def setUp(self):
        self.scene1 = Scene.objects.create(name="场景 A")
        self.scene_group = SceneReportGroup.objects.create(
            scene=self.scene1,
            name="默认分组",
            group_type=ReportGroupType.CUSTOM,
            priority_index=1,
        )
        self.config = {
            "scenes": {"1001": {"time_filter": ["now-7d", "now"]}},
            "systems": {"bk_cmdb": {"time_filter": ["now-30d", "now"]}},
        }

    def test_platform_list_returns_full_config(self):
        """平台管理列表完整返回配置"""
        CreatePlatformPanel().request(
            {
                "name": "平台报表",
                "default_value_overrides": self.config,
                "visibility": {"visibility_type": VisibilityScope.ALL_VISIBLE},
            }
        )

        data = ListPlatformPanels().request({"enable_paginate": False})
        self.assertEqual(len(data), 1)
        assert_dict_contains(data[0], {"default_value_overrides": self.config})

    def test_scene_list_returns_full_config(self):
        """场景管理列表完整返回配置"""
        CreateScenePanel().request(
            {
                "scene_id": self.scene1.scene_id,
                "group_id": self.scene_group.id,
                "name": "场景报表",
                "default_value_overrides": self.config,
            }
        )

        data = ListScenePanels().request({"scene_id": self.scene1.scene_id})
        self.assertEqual(len(data), 1)
        assert_dict_contains(data[0], {"default_value_overrides": self.config})


class TestInvalidStructureRejection(TestCase):
    """测试非法结构在 create/update/detail 接口被拒绝"""

    def setUp(self):
        self.scene1 = Scene.objects.create(name="场景 A")
        self.scene_group = SceneReportGroup.objects.create(
            scene=self.scene1,
            name="默认分组",
            group_type=ReportGroupType.CUSTOM,
            priority_index=1,
        )

    def test_create_platform_panel_rejects_list(self):
        """创建平台报表时拒绝 list 类型"""
        from bk_resource.exceptions import ValidateException

        with self.assertRaises(ValidateException):
            CreatePlatformPanel().request(
                {
                    "name": "非法配置报表",
                    "default_value_overrides": ["not", "a", "dict"],
                    "visibility": {"visibility_type": VisibilityScope.ALL_VISIBLE},
                }
            )

    def test_create_scene_panel_rejects_list(self):
        """创建场景报表时拒绝 list 类型"""
        from bk_resource.exceptions import ValidateException

        with self.assertRaises(ValidateException):
            CreateScenePanel().request(
                {
                    "scene_id": self.scene1.scene_id,
                    "group_id": self.scene_group.id,
                    "name": "非法配置报表",
                    "default_value_overrides": ["not", "a", "dict"],
                }
            )

    def test_update_platform_panel_rejects_list(self):
        """更新平台报表时拒绝 list 类型"""
        from bk_resource.exceptions import ValidateException

        # 先创建合法报表
        resp = CreatePlatformPanel().request(
            {
                "name": "平台报表",
                "visibility": {"visibility_type": VisibilityScope.ALL_VISIBLE},
            }
        )

        # 更新时传入非法结构
        with self.assertRaises(ValidateException):
            UpdatePlatformPanel().request(
                {
                    "panel_id": resp["id"],
                    "default_value_overrides": ["not", "a", "dict"],
                }
            )

    def test_update_scene_panel_rejects_list(self):
        """更新场景报表时拒绝 list 类型"""
        from bk_resource.exceptions import ValidateException

        # 先创建合法报表
        resp = CreateScenePanel().request(
            {
                "scene_id": self.scene1.scene_id,
                "group_id": self.scene_group.id,
                "name": "场景报表",
            }
        )

        # 更新时传入非法结构
        with self.assertRaises(ValidateException):
            UpdateScenePanel().request(
                {
                    "scene_id": self.scene1.scene_id,
                    "group_id": self.scene_group.id,
                    "panel_id": resp["id"],
                    "default_value_overrides": ["not", "a", "dict"],
                }
            )

    def test_detail_rejects_invalid_data(self):
        """详情接口对非法数据进行 defensive 校验"""
        from unittest.mock import patch

        from rest_framework.exceptions import ValidationError

        from services.web.common.constants import ScopeType
        from services.web.scene.constants import BindingType, ResourceVisibilityType
        from services.web.scene.models import ResourceBinding
        from services.web.vision.models import VisionPanel
        from services.web.vision.resources import GetPanelDetail

        # 直接写入非法数据到数据库（绕过 serializer）
        panel = VisionPanel.objects.create(
            id="test_panel_invalid_001",
            name="非法数据报表",
            default_value_overrides=["invalid", "list"],  # 非法数据
        )
        ResourceBinding.objects.create(
            resource_type=ResourceVisibilityType.PANEL,
            resource_id=str(panel.id),
            binding_type=BindingType.PLATFORM_BINDING,
            visibility_type=VisibilityScope.ALL_VISIBLE,
        )

        # 详情接口应该抛出 ValidationError
        with patch("services.web.vision.resources.ScopePermission.check_resource_permission", return_value=True):
            with self.assertRaises(ValidationError):
                GetPanelDetail().request(
                    {
                        "panel_id": panel.id,
                        "scope_type": ScopeType.SCENE,
                        "scope_id": str(self.scene1.scene_id),
                    }
                )

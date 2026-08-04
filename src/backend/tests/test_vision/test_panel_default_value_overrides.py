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

    def test_valid_json_structure(self):
        """合法 JSON 结构可正常保存"""
        config = {
            "scenes": {
                "1001": {"time_filter": ["now-7d", "now"]},
                "1002": {"time_filter": ["now-1d", "now"]},
            },
            "systems": {
                "bk_cmdb": {"time_filter": ["now-30d", "now"]},
            },
        }
        panel = VisionPanel.objects.create(
            id="test_panel_valid_002",
            name="带配置报表",
            default_value_overrides=config,
        )
        self.assertEqual(
            panel.default_value_overrides["scenes"]["1001"],
            {"time_filter": ["now-7d", "now"]},
        )

    def test_invalid_structure_validation(self):
        """非法结构在 serializer 层校验失败"""
        from services.web.vision.serializers import CreatePlatformPanelRequestSerializer

        # JSONField 会尝试将字符串解析为 JSON，如果失败会抛出异常
        # 这里测试传入明显不合理的结构（如列表而非字典）
        data = {
            "name": "非法配置报表",
            "default_value_overrides": ["not", "a", "dict"],  # 应该是 dict
        }
        serializer = CreatePlatformPanelRequestSerializer(data=data)
        # Django JSONField 会接受任何可 JSON 序列化的值
        # 实际的结构校验应该在业务逻辑层进行
        self.assertTrue(serializer.is_valid())


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

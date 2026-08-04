# -*- coding: utf-8 -*-
from unittest.mock import patch

from django.test import TestCase

from core.testing import assert_dict_contains
from services.web.common.constants import ScopeType
from services.web.scene.constants import (
    BindingType,
    ResourceVisibilityType,
    VisibilityScope,
)
from services.web.scene.models import ResourceBinding, Scene
from services.web.vision.constants import ReportGroupType
from services.web.vision.models import SceneReportGroup, VisionPanel
from services.web.vision.resources import (
    CreatePlatformPanel,
    CreateScenePanel,
    GetPanelDetail,
)


class TestPanelDetailScopeMatching(TestCase):
    """测试详情接口按 scope 返回正确的 default_value_override"""

    def setUp(self):
        self.scene1 = Scene.objects.create(name="场景 A")
        self.scene2 = Scene.objects.create(name="场景 B")
        self.config = {
            "scenes": {
                str(self.scene1.scene_id): {"time_filter": ["scene_scope"]},
                str(self.scene2.scene_id): {"time_filter": ["scene2_scope"]},
            },
            "systems": {
                "bk_cmdb": {"time_filter": ["system_scope"]},
                "bk_monitor": {"time_filter": ["monitor_scope"]},
            },
        }
        self.panel = VisionPanel.objects.create(
            id="test_panel_scope_001",
            name="测试报表",
            default_value_overrides=self.config,
        )
        # 创建平台绑定
        ResourceBinding.objects.create(
            resource_type=ResourceVisibilityType.PANEL,
            resource_id=str(self.panel.id),
            binding_type=BindingType.PLATFORM_BINDING,
            visibility_type=VisibilityScope.ALL_VISIBLE,
        )

    @patch("services.web.vision.resources.ScopePermission.check_resource_permission_in_scope")
    def test_scene_scope_hits_scenes_config(self, mock_check):
        """scene 视角命中 scenes[str(scope_id)]"""
        mock_check.return_value = True

        resp = GetPanelDetail().request(
            {
                "panel_id": self.panel.id,
                "scope_type": ScopeType.SCENE,
                "scope_id": str(self.scene1.scene_id),
            }
        )

        self.assertEqual(resp["default_value_override"], {"time_filter": ["scene_scope"]})

    @patch("services.web.vision.resources.ScopePermission.check_resource_permission_in_scope")
    def test_system_scope_hits_systems_config(self, mock_check):
        """system 视角命中 systems[scope_id]"""
        mock_check.return_value = True

        resp = GetPanelDetail().request(
            {
                "panel_id": self.panel.id,
                "scope_type": ScopeType.SYSTEM,
                "scope_id": "bk_cmdb",
            }
        )

        self.assertEqual(resp["default_value_override"], {"time_filter": ["system_scope"]})

    @patch("services.web.vision.resources.ScopePermission.check_resource_permission_in_scope")
    def test_cross_scene_returns_empty(self, mock_check):
        """cross_scene 返回 {}"""
        mock_check.return_value = True

        resp = GetPanelDetail().request(
            {
                "panel_id": self.panel.id,
                "scope_type": ScopeType.CROSS_SCENE,
            }
        )

        self.assertEqual(resp["default_value_override"], {})

    @patch("services.web.vision.resources.ScopePermission.check_resource_permission_in_scope")
    def test_cross_system_returns_empty(self, mock_check):
        """cross_system 返回 {}"""
        mock_check.return_value = True

        resp = GetPanelDetail().request(
            {
                "panel_id": self.panel.id,
                "scope_type": ScopeType.CROSS_SYSTEM,
            }
        )

        self.assertEqual(resp["default_value_override"], {})

    @patch("services.web.vision.resources.ScopePermission.check_resource_permission_in_scope")
    def test_no_config_returns_empty(self, mock_check):
        """报表无配置返回 {}"""
        mock_check.return_value = True

        panel_no_config = VisionPanel.objects.create(
            id="no_config_panel_002",
            name="无配置报表",
        )
        ResourceBinding.objects.create(
            resource_type=ResourceVisibilityType.PANEL,
            resource_id=str(panel_no_config.id),
            binding_type=BindingType.PLATFORM_BINDING,
            visibility_type=VisibilityScope.ALL_VISIBLE,
        )

        resp = GetPanelDetail().request(
            {
                "panel_id": panel_no_config.id,
                "scope_type": ScopeType.SCENE,
                "scope_id": str(self.scene1.scene_id),
            }
        )

        self.assertEqual(resp["default_value_override"], {})

    @patch("services.web.vision.resources.ScopePermission.check_resource_permission_in_scope")
    def test_scope_not_matched_returns_empty(self, mock_check):
        """scope 未命中（不同 scene_id）返回 {}"""
        mock_check.return_value = True

        resp = GetPanelDetail().request(
            {
                "panel_id": self.panel.id,
                "scope_type": ScopeType.SCENE,
                "scope_id": "9999",  # 不存在的场景 ID
            }
        )

        self.assertEqual(resp["default_value_override"], {})


class TestPanelDetailResponseProtocol(TestCase):
    """测试详情响应协议"""

    def test_response_does_not_leak_other_scopes(self):
        """响应不泄露其他 scope 的配置"""
        panel = VisionPanel.objects.create(
            id="leak_test_panel_003",
            name="防泄露测试",
            default_value_overrides={
                "scenes": {
                    "1001": {"secret_scene": "value1"},
                    "1002": {"secret_scene": "value2"},
                },
                "systems": {
                    "bk_cmdb": {"secret_system": "value3"},
                },
            },
        )
        ResourceBinding.objects.create(
            resource_type=ResourceVisibilityType.PANEL,
            resource_id=str(panel.id),
            binding_type=BindingType.PLATFORM_BINDING,
            visibility_type=VisibilityScope.ALL_VISIBLE,
        )

        # 只查询 scene 1001 的详情
        with patch(
            "services.web.vision.resources.ScopePermission.check_resource_permission_in_scope", return_value=True
        ):
            resp = GetPanelDetail().request(
                {
                    "panel_id": panel.id,
                    "scope_type": ScopeType.SCENE,
                    "scope_id": "1001",
                }
            )

        # 验证只返回当前 scope 的配置
        # default_value_overrides 可能为空 dict（serializer 默认值），但不应包含实际配置
        self.assertEqual(resp.get("default_value_overrides", {}), {})  # 完整配置应为空
        self.assertEqual(resp["default_value_override"], {"secret_scene": "value1"})  # 当前 scope 配置正确


class TestPanelDetailNoBkvisionCall(TestCase):
    """测试详情接口不调用 Bkvision Meta API"""

    @patch("services.web.vision.resources.ScopePermission.check_resource_permission_in_scope")
    @patch("services.web.vision.handlers.query.VisionHandler.query_meta")
    def test_detail_does_not_call_bkvision_meta(self, mock_meta, mock_check):
        """详情资源不调用 Bkvision Meta API"""
        mock_check.return_value = True

        panel = VisionPanel.objects.create(
            id="no_api_call_panel_004",
            name="测试报表",
        )
        ResourceBinding.objects.create(
            resource_type=ResourceVisibilityType.PANEL,
            resource_id=str(panel.id),
            binding_type=BindingType.PLATFORM_BINDING,
            visibility_type=VisibilityScope.ALL_VISIBLE,
        )

        GetPanelDetail().request(
            {
                "panel_id": panel.id,
                "scope_type": ScopeType.SCENE,
                "scope_id": "1001",
            }
        )

        mock_meta.assert_not_called()


class TestPanelDetailBindingTypeCompatibility(TestCase):
    """测试不同 binding_type 的报表均可读取详情"""

    def setUp(self):
        self.scene1 = Scene.objects.create(name="场景 A")
        self.scene_group = SceneReportGroup.objects.create(
            scene=self.scene1,
            name="默认分组",
            group_type=ReportGroupType.CUSTOM,
            priority_index=1,
        )

    @patch("services.web.vision.resources.ScopePermission.check_resource_permission_in_scope")
    def test_platform_binding_accessible(self, mock_check):
        """平台绑定报表可读取详情"""
        mock_check.return_value = True

        resp = CreatePlatformPanel().request(
            {
                "name": "平台报表",
                "visibility": {"visibility_type": VisibilityScope.ALL_VISIBLE},
            }
        )

        # 不应抛出权限异常
        resp = GetPanelDetail().request(
            {
                "panel_id": resp["id"],
                "scope_type": ScopeType.SCENE,
                "scope_id": str(self.scene1.scene_id),
            }
        )
        self.assertIn("id", resp)

    @patch("services.web.vision.resources.ScopePermission.check_resource_permission_in_scope")
    def test_scene_binding_accessible(self, mock_check):
        """场景绑定报表可读取详情"""
        mock_check.return_value = True

        resp = CreateScenePanel().request(
            {
                "scene_id": self.scene1.scene_id,
                "group_id": self.scene_group.id,
                "name": "场景报表",
            }
        )

        resp = GetPanelDetail().request(
            {
                "panel_id": resp["id"],
                "scope_type": ScopeType.SCENE,
                "scope_id": str(self.scene1.scene_id),
            }
        )
        self.assertIn("id", resp)


class TestPanelDetailNotFound(TestCase):
    """测试不存在的 panel_id 返回 404"""

    def test_nonexistent_panel_returns_404(self):
        """不存在的 panel_id 返回 404"""
        from rest_framework.exceptions import NotFound

        with patch(
            "services.web.vision.resources.ScopePermission.check_resource_permission_in_scope", return_value=True
        ):
            with self.assertRaises(NotFound):
                GetPanelDetail().request(
                    {
                        "panel_id": "nonexistent_panel",
                        "scope_type": ScopeType.SCENE,
                        "scope_id": "1001",
                    }
                )


class TestPanelDetailResponseFields(TestCase):
    """测试详情响应字段完整性"""

    def setUp(self):
        self.scene1 = Scene.objects.create(name="场景 A")
        self.config = {
            "scenes": {str(self.scene1.scene_id): {"time_filter": ["now-7d", "now"]}},
        }
        self.panel = VisionPanel.objects.create(
            id="test_panel_fields_005",
            name="字段测试报表",
            vision_id="bk_vision_test_001",
            category="test_category",
            description="test_description",
            status="published",
            default_value_overrides=self.config,
        )
        ResourceBinding.objects.create(
            resource_type=ResourceVisibilityType.PANEL,
            resource_id=str(self.panel.id),
            binding_type=BindingType.PLATFORM_BINDING,
            visibility_type=VisibilityScope.ALL_VISIBLE,
        )

    @patch("services.web.vision.resources.ScopePermission.check_resource_permission_in_scope")
    def test_response_contains_all_fields(self, mock_check):
        """详情响应包含所有必需字段"""
        mock_check.return_value = True

        resp = GetPanelDetail().request(
            {
                "panel_id": self.panel.id,
                "scope_type": ScopeType.SCENE,
                "scope_id": str(self.scene1.scene_id),
            }
        )

        # 验证基础字段
        assert_dict_contains(
            resp,
            {
                "id": self.panel.id,
                "vision_id": "bk_vision_test_001",
                "name": "字段测试报表",
                "status": "published",
                "category": "test_category",
                "description": "test_description",
                "default_value_override": {"time_filter": ["now-7d", "now"]},
            },
        )
        # 验证时间字段存在
        self.assertIn("updated_by", resp)
        self.assertIn("updated_at", resp)
        self.assertIsNotNone(resp["updated_at"])

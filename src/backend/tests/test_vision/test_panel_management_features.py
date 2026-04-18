# -*- coding: utf-8 -*-
from unittest.mock import patch

from django.test import TestCase

from core.testing import assert_dict_contains
from services.web.common.constants import ScopeType
from services.web.scene.constants import VisibilityScope
from services.web.scene.models import ResourceBinding, ResourceBindingSystem, Scene
from services.web.vision.constants import ReportGroupType
from services.web.vision.models import (
    ReportUserPreference,
    Scenario,
    SceneReportGroup,
    SceneReportGroupItem,
    UserPanelFavorite,
    VisionPanel,
)
from services.web.vision.resources import (
    CreatePlatformPanel,
    CreateScenePanel,
    DeleteSceneReportGroup,
    ListPanels,
    ListPlatformPanels,
    ListScenePanels,
    ListSceneReportGroup,
    PublishScenePanel,
    TogglePanelFavorite,
    UpdatePanelPreference,
    UpdateScenePanel,
    UpdateSceneReportGroupOrder,
    UpdateSceneReportGroupPanelOrder,
)
from services.web.vision.views import PanelsViewSet, ScenePanelManageViewSet


class TestPanelManagementFeatures(TestCase):
    def setUp(self):
        self.scene1 = Scene.objects.create(name="场景A", managers=["admin"], users=["u1"])
        self.scene2 = Scene.objects.create(name="场景B", managers=["admin"], users=["u2"])
        self.scene_group = SceneReportGroup.objects.create(
            scene=self.scene1,
            name="自定义分组",
            group_type=ReportGroupType.CUSTOM,
            priority_index=1,
        )

    def test_create_scene_panel_auto_group(self):
        resp = CreateScenePanel().request(
            {"scene_id": self.scene1.scene_id, "group_id": self.scene_group.id, "name": "场景报表1"}
        )
        assert_dict_contains(resp, {"name": "场景报表1"})
        panel = VisionPanel.objects.get(id=resp["id"])
        self.assertTrue(SceneReportGroupItem.objects.filter(group=self.scene_group, panel=panel).exists())

    def test_list_platform_panels_with_visibility(self):
        CreatePlatformPanel().request(
            {
                "name": "平台报表1",
                "status": "published",
                "visibility": {
                    "visibility_type": VisibilityScope.SPECIFIC_SCENES,
                    "scene_ids": [self.scene1.scene_id],
                    "system_ids": [],
                },
            }
        )
        data = ListPlatformPanels().request({"enable_paginate": False})
        self.assertEqual(len(data), 1)
        self.assertIn("visibility_type", data[0])
        self.assertEqual(data[0]["scene_ids"], [self.scene1.scene_id])

    def test_scene_group_item_bulk_order(self):
        p1 = CreateScenePanel().request(
            {"scene_id": self.scene1.scene_id, "group_id": self.scene_group.id, "name": "报表A"}
        )
        p2 = CreateScenePanel().request(
            {"scene_id": self.scene1.scene_id, "group_id": self.scene_group.id, "name": "报表B"}
        )

        target_group = SceneReportGroup.objects.create(
            scene_id=self.scene1.scene_id,
            name="自定义组",
            group_type=ReportGroupType.CUSTOM,
            priority_index=2,
        )
        UpdateSceneReportGroupPanelOrder().request(
            {
                "scene_id": self.scene1.scene_id,
                "items": [
                    {"panel_id": p1["id"], "group_id": target_group.id, "priority_index": 10},
                    {"panel_id": p2["id"], "group_id": target_group.id, "priority_index": 9},
                ],
            }
        )
        self.assertEqual(SceneReportGroupItem.objects.filter(group=target_group).count(), 2)

    @patch("services.web.vision.resources.get_request_username", return_value="tester")
    def test_favorite_and_preference(self, _):
        panel = VisionPanel.objects.create(id="fav_p1", name="fav", scenario=Scenario.DEFAULT)
        TogglePanelFavorite().request({"panel_id": panel.id, "favorite": True})
        self.assertTrue(UserPanelFavorite.objects.filter(username="tester", panel=panel).exists())

        UpdatePanelPreference().request({"config": {"collapsed": [1, 2]}})
        pref = ReportUserPreference.objects.get(username="tester")
        self.assertEqual(pref.config, {"collapsed": [1, 2]})

    def test_list_scene_panels_flat_without_side_effect_write(self):
        panel_data = CreatePlatformPanel().request(
            {
                "name": "平台报表2",
                "status": "published",
                "visibility": {
                    "visibility_type": VisibilityScope.SPECIFIC_SCENES,
                    "scene_ids": [self.scene1.scene_id],
                    "system_ids": [],
                },
            }
        )
        platform_group = SceneReportGroup.objects.get(
            scene_id=self.scene1.scene_id, group_type=ReportGroupType.PLATFORM
        )
        SceneReportGroupItem.objects.filter(group=platform_group, panel_id=panel_data["id"]).delete()

        data = ListScenePanels().request({"scene_id": self.scene1.scene_id})
        self.assertGreaterEqual(len(data), 1)
        self.assertIn("group_id", data[0])
        self.assertIn("binding_type", data[0])
        self.assertFalse(SceneReportGroupItem.objects.filter(group=platform_group, panel_id=panel_data["id"]).exists())

    def test_delete_platform_group_is_forbidden(self):
        group = SceneReportGroup.objects.create(
            scene=self.scene1,
            name="平台报表",
            group_type=ReportGroupType.PLATFORM,
            priority_index=-1,
        )
        with self.assertRaisesMessage(Exception, "平台报表分组不支持删除"):
            DeleteSceneReportGroup().request({"scene_id": self.scene1.scene_id, "group_id": group.id})

    def test_delete_non_empty_group_is_forbidden(self):
        panel_resp = CreateScenePanel().request(
            {"scene_id": self.scene1.scene_id, "group_id": self.scene_group.id, "name": "待保护报表"}
        )
        with self.assertRaisesMessage(Exception, "分组下仍有报表，无法删除"):
            DeleteSceneReportGroup().request({"scene_id": self.scene1.scene_id, "group_id": self.scene_group.id})

        self.assertTrue(SceneReportGroup.objects.filter(id=self.scene_group.id).exists())
        self.assertTrue(
            SceneReportGroupItem.objects.filter(group_id=self.scene_group.id, panel_id=panel_resp["id"]).exists()
        )

    def test_publish_scene_panel(self):
        scene_panel = CreateScenePanel().request(
            {"scene_id": self.scene1.scene_id, "group_id": self.scene_group.id, "name": "场景可启停报表"}
        )
        panel = VisionPanel.objects.get(id=scene_panel["id"])
        self.assertEqual(panel.status, "unpublished")

        publish_resp = PublishScenePanel().request({"scene_id": self.scene1.scene_id, "panel_id": panel.id})
        assert_dict_contains(
            publish_resp,
            {
                "id": panel.id,
                "name": "场景可启停报表",
                "status": "published",
            },
        )
        panel.refresh_from_db()
        self.assertEqual(panel.status, "published")

        unpublish_resp = PublishScenePanel().request({"scene_id": self.scene1.scene_id, "panel_id": panel.id})
        assert_dict_contains(
            unpublish_resp,
            {
                "id": panel.id,
                "name": "场景可启停报表",
                "status": "unpublished",
            },
        )
        panel.refresh_from_db()
        self.assertEqual(panel.status, "unpublished")

    @patch("services.web.vision.resources.get_request_username", return_value="tester")
    @patch("services.web.vision.resources.ScopePermission.get_scene_ids", return_value=[])
    @patch("services.web.vision.resources.ScopePermission.get_system_ids", return_value=["bk_cmdb"])
    def test_square_system_scope_without_group(self, *_):
        panel = VisionPanel.objects.create(
            id="square_sys_p1", name="系统报表", scenario=Scenario.DEFAULT, status="published"
        )
        binding = ResourceBinding.objects.create(
            resource_type="panel",
            resource_id=panel.id,
            binding_type="platform_binding",
            visibility_type=VisibilityScope.SPECIFIC_SYSTEMS,
        )
        ResourceBindingSystem.objects.create(binding=binding, system_id="bk_cmdb")

        data = ListPanels().request({"scope_type": ScopeType.CROSS_SYSTEM})
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["group_ids"], [])

    @patch("services.web.vision.resources.get_request_username", return_value="tester")
    @patch("services.web.vision.resources.ScopePermission.get_scene_ids")
    @patch("services.web.vision.resources.ScopePermission.get_system_ids")
    def test_list_panels_returns_group_ids_and_favorite_time(self, mock_system_ids, mock_scene_ids, _):
        mock_scene_ids.return_value = [self.scene1.scene_id, self.scene2.scene_id]
        mock_system_ids.return_value = []

        panel_info = CreatePlatformPanel().request(
            {
                "name": "平台报表3",
                "status": "published",
                "visibility": {
                    "visibility_type": VisibilityScope.SPECIFIC_SCENES,
                    "scene_ids": [self.scene1.scene_id, self.scene2.scene_id],
                    "system_ids": [],
                },
            }
        )
        panel = VisionPanel.objects.get(id=panel_info["id"])
        TogglePanelFavorite().request({"panel_id": panel.id, "favorite": True})

        data = ListPanels().request({"scope_type": ScopeType.CROSS_SCENE})
        self.assertEqual(len(data), 1)
        self.assertEqual(len(data[0]["group_ids"]), 2)
        self.assertIsNotNone(data[0]["favorite_created_at"])

    def test_group_order_updates_with_scene_isolation(self):
        group2 = SceneReportGroup.objects.create(
            scene=self.scene1,
            name="分组2",
            group_type=ReportGroupType.CUSTOM,
            priority_index=0,
        )
        other_scene_group = SceneReportGroup.objects.create(
            scene=self.scene2,
            name="他场景分组",
            group_type=ReportGroupType.CUSTOM,
            priority_index=0,
        )

        with self.assertRaisesMessage(Exception, "group not found"):
            UpdateSceneReportGroupOrder().request(
                {
                    "scene_id": self.scene1.scene_id,
                    "groups": [
                        {"group_id": self.scene_group.id, "priority_index": 10},
                        {"group_id": other_scene_group.id, "priority_index": 9},
                    ],
                }
            )

        UpdateSceneReportGroupOrder().request(
            {
                "scene_id": self.scene1.scene_id,
                "groups": [
                    {"group_id": self.scene_group.id, "priority_index": 10},
                    {"group_id": group2.id, "priority_index": 9},
                ],
            }
        )
        self.scene_group.refresh_from_db()
        group2.refresh_from_db()
        self.assertEqual(self.scene_group.priority_index, 10)
        self.assertEqual(group2.priority_index, 9)

    def test_scene_manage_viewset_has_publish_route(self):
        publish_routes = [route for route in ScenePanelManageViewSet.resource_routes if route.endpoint == "publish"]
        self.assertEqual(len(publish_routes), 1)

    def test_panels_viewset_has_group_list_route(self):
        group_routes = [
            route
            for route in PanelsViewSet.resource_routes
            if route.endpoint == "group" and route.method.lower() == "get"
        ]
        self.assertEqual(len(group_routes), 1)

    def test_update_scene_panel_keeps_single_group_item_per_scene(self):
        another_group = SceneReportGroup.objects.create(
            scene=self.scene1,
            name="新分组",
            group_type=ReportGroupType.CUSTOM,
            priority_index=2,
        )
        created = CreateScenePanel().request(
            {"scene_id": self.scene1.scene_id, "group_id": self.scene_group.id, "name": "可迁移报表"}
        )

        UpdateScenePanel().request(
            {
                "scene_id": self.scene1.scene_id,
                "group_id": another_group.id,
                "panel_id": created["id"],
                "name": "可迁移报表",
            }
        )

        items = SceneReportGroupItem.objects.filter(panel_id=created["id"], group__scene_id=self.scene1.scene_id)
        self.assertEqual(items.count(), 1)
        self.assertEqual(items.first().group_id, another_group.id)

    @patch("services.web.vision.resources.ScopePermission.get_scene_ids", return_value=[100001])
    @patch("services.web.vision.resources.ScopePermission.get_system_ids", return_value=["bk_cmdb"])
    def test_list_group_returns_empty_in_system_scope(self, *_):
        data = ListSceneReportGroup().request({"scope_type": ScopeType.CROSS_SYSTEM})
        self.assertEqual(data, [])

    @patch("services.web.vision.resources.get_request_username", return_value="tester")
    @patch("services.web.vision.resources.ScopePermission.get_scene_ids")
    def test_list_group_returns_complete_fields_in_scene_scope(self, mock_scene_ids, _):
        mock_scene_ids.return_value = [self.scene1.scene_id]
        group = SceneReportGroup.objects.create(
            scene=self.scene1,
            name="响应校验分组",
            group_type=ReportGroupType.CUSTOM,
            priority_index=99,
        )

        data = ListSceneReportGroup().request({"scope_type": ScopeType.CROSS_SCENE})
        self.assertEqual(len(data), 2)
        group_map = {item.get("name"): item for item in data}

        assert_dict_contains(
            group_map["响应校验分组"],
            {
                "id": group.id,
                "scene_id": self.scene1.scene_id,
                "name": "响应校验分组",
                "group_type": ReportGroupType.CUSTOM,
                "priority_index": 99,
            },
        )
        assert_dict_contains(
            group_map["自定义分组"],
            {
                "id": self.scene_group.id,
                "scene_id": self.scene1.scene_id,
                "name": "自定义分组",
                "group_type": ReportGroupType.CUSTOM,
                "priority_index": 1,
            },
        )

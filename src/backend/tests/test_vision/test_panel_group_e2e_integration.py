# -*- coding: utf-8 -*-
from unittest.mock import patch

from django.test import TestCase

from core.testing import assert_dict_contains
from services.web.common.constants import ScopeType
from services.web.scene.constants import VisibilityScope
from services.web.scene.models import Scene
from services.web.vision.constants import ReportGroupType
from services.web.vision.models import SceneReportGroup, SceneReportGroupItem
from services.web.vision.resources import (
    CreatePlatformPanel,
    CreateScenePanel,
    CreateSceneReportGroup,
    DeleteSceneReportGroup,
    ListPanels,
    ListScenePanels,
    ListSceneReportGroup,
    TogglePanelFavorite,
    UpdatePlatformPanel,
    UpdateSceneReportGroup,
    UpdateSceneReportGroupOrder,
    UpdateSceneReportGroupPanelOrder,
)


class TestPanelGroupE2EIntegration(TestCase):
    def setUp(self):
        self.scene1 = Scene.objects.create(name="链路场景A", managers=["admin"], users=["u1"])
        self.scene2 = Scene.objects.create(name="链路场景B", managers=["admin"], users=["u2"])

    @patch("services.web.vision.resources.get_request_username", return_value="tester")
    @patch("services.web.vision.resources.ScopePermission.get_scene_ids")
    @patch("services.web.vision.resources.ScopePermission.get_system_ids")
    def test_scene_group_manage_and_square_display_full_chain(self, mock_system_ids, mock_scene_ids, _):
        mock_scene_ids.return_value = [self.scene1.scene_id]
        mock_system_ids.return_value = []

        group_a = CreateSceneReportGroup().request(
            {"scene_id": self.scene1.scene_id, "name": "分组A", "priority_index": 1}
        )
        group_b = CreateSceneReportGroup().request(
            {"scene_id": self.scene1.scene_id, "name": "分组B", "priority_index": 2}
        )

        renamed_a = UpdateSceneReportGroup().request(
            {
                "scene_id": self.scene1.scene_id,
                "group_id": group_a["id"],
                "name": "分组A-重命名",
                "priority_index": 3,
            }
        )
        assert_dict_contains(renamed_a, {"id": group_a["id"], "name": "分组A-重命名"})

        panel = CreateScenePanel().request(
            {
                "scene_id": self.scene1.scene_id,
                "group_id": group_a["id"],
                "name": "链路报表1",
            }
        )

        scene_list_before = ListScenePanels().request({"scene_id": self.scene1.scene_id})
        self.assertEqual(len(scene_list_before), 1)
        self.assertEqual(scene_list_before[0]["group_id"], group_a["id"])

        UpdateSceneReportGroupOrder().request(
            {
                "scene_id": self.scene1.scene_id,
                "groups": [
                    {"group_id": group_a["id"], "priority_index": 8},
                    {"group_id": group_b["id"], "priority_index": 9},
                ],
            }
        )

        group_a_obj = SceneReportGroup.objects.get(id=group_a["id"])
        group_b_obj = SceneReportGroup.objects.get(id=group_b["id"])
        self.assertEqual(group_a_obj.priority_index, 8)
        self.assertEqual(group_b_obj.priority_index, 9)

        UpdateSceneReportGroupPanelOrder().request(
            {
                "scene_id": self.scene1.scene_id,
                "items": [
                    {
                        "panel_id": panel["id"],
                        "group_id": group_b["id"],
                        "priority_index": 99,
                    }
                ],
            }
        )

        scene_list_after = ListScenePanels().request({"scene_id": self.scene1.scene_id})
        self.assertEqual(len(scene_list_after), 1)
        self.assertEqual(scene_list_after[0]["group_id"], group_b["id"])
        self.assertEqual(scene_list_after[0]["group_name"], "分组B")

        TogglePanelFavorite().request({"panel_id": panel["id"], "favorite": True})

        group_display = ListSceneReportGroup().request({"scope_type": ScopeType.CROSS_SCENE})
        group_map = {item["id"]: item for item in group_display}
        self.assertIn(group_a["id"], group_map)
        self.assertIn(group_b["id"], group_map)
        self.assertEqual(group_map[group_a["id"]]["name"], "分组A-重命名")

        square_data = ListPanels().request({"scope_type": ScopeType.CROSS_SCENE})
        self.assertEqual(len(square_data), 1)
        self.assertEqual(square_data[0]["id"], panel["id"])
        self.assertIn(group_b["id"], square_data[0]["group_ids"])
        self.assertIsNotNone(square_data[0]["favorite_created_at"])

        with self.assertRaisesMessage(Exception, "分组下仍有报表，无法删除"):
            DeleteSceneReportGroup().request({"scene_id": self.scene1.scene_id, "group_id": group_b["id"]})

        UpdateSceneReportGroupPanelOrder().request(
            {
                "scene_id": self.scene1.scene_id,
                "items": [
                    {
                        "panel_id": panel["id"],
                        "group_id": group_a["id"],
                        "priority_index": 1,
                    }
                ],
            }
        )
        DeleteSceneReportGroup().request({"scene_id": self.scene1.scene_id, "group_id": group_b["id"]})
        self.assertFalse(SceneReportGroup.objects.filter(id=group_b["id"]).exists())

    @patch("services.web.vision.resources.get_request_username", return_value="tester")
    @patch("services.web.vision.resources.ScopePermission.get_scene_ids")
    @patch("services.web.vision.resources.ScopePermission.get_system_ids")
    def test_platform_group_delete_and_recreate_by_authorization_chain(
        self,
        mock_system_ids,
        mock_scene_ids,
        _,
    ):
        mock_scene_ids.return_value = [self.scene1.scene_id, self.scene2.scene_id]
        mock_system_ids.return_value = []

        panel = CreatePlatformPanel().request(
            {
                "name": "平台链路报表",
                "status": "published",
                "visibility": {
                    "visibility_type": VisibilityScope.SPECIFIC_SCENES,
                    "scene_ids": [self.scene1.scene_id],
                    "system_ids": [],
                },
            }
        )

        scene1_platform_group = SceneReportGroup.objects.get(
            scene_id=self.scene1.scene_id,
            group_type=ReportGroupType.PLATFORM,
        )
        self.assertTrue(
            SceneReportGroupItem.objects.filter(
                group=scene1_platform_group,
                panel_id=panel["id"],
            ).exists()
        )

        with self.assertRaisesMessage(Exception, "平台报表分组不支持重命名"):
            UpdateSceneReportGroup().request(
                {
                    "scene_id": self.scene1.scene_id,
                    "group_id": scene1_platform_group.id,
                    "name": "改名应失败",
                }
            )

        UpdatePlatformPanel().request(
            {
                "panel_id": panel["id"],
                "visibility": {
                    "visibility_type": VisibilityScope.SPECIFIC_SCENES,
                    "scene_ids": [self.scene2.scene_id],
                    "system_ids": [],
                },
            }
        )

        self.assertFalse(
            SceneReportGroupItem.objects.filter(
                group=scene1_platform_group,
                panel_id=panel["id"],
            ).exists()
        )

        DeleteSceneReportGroup().request(
            {
                "scene_id": self.scene1.scene_id,
                "group_id": scene1_platform_group.id,
            }
        )
        self.assertFalse(SceneReportGroup.objects.filter(id=scene1_platform_group.id).exists())

        UpdatePlatformPanel().request(
            {
                "panel_id": panel["id"],
                "visibility": {
                    "visibility_type": VisibilityScope.SPECIFIC_SCENES,
                    "scene_ids": [self.scene1.scene_id, self.scene2.scene_id],
                    "system_ids": [],
                },
            }
        )

        recreated_group = SceneReportGroup.objects.get(
            scene_id=self.scene1.scene_id,
            group_type=ReportGroupType.PLATFORM,
        )
        self.assertTrue(
            SceneReportGroupItem.objects.filter(
                group=recreated_group,
                panel_id=panel["id"],
            ).exists()
        )

        square_data = ListPanels().request({"scope_type": ScopeType.CROSS_SCENE})
        panel_data = next(item for item in square_data if item["id"] == panel["id"])
        self.assertIn(recreated_group.id, panel_data["group_ids"])

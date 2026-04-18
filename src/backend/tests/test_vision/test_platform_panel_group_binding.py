# -*- coding: utf-8 -*-
from django.test import TestCase

from services.web.scene.constants import VisibilityScope
from services.web.scene.models import Scene
from services.web.vision.constants import ReportGroupType
from services.web.vision.models import SceneReportGroup, SceneReportGroupItem
from services.web.vision.resources import CreatePlatformPanel, UpdatePlatformPanel


class TestPlatformPanelGroupBinding(TestCase):
    def setUp(self):
        self.scene1 = Scene.objects.create(name="s1", managers=["admin"], users=["u1"])
        self.scene2 = Scene.objects.create(name="s2", managers=["admin"], users=["u2"])

    def test_create_platform_panel_auto_create_group_item(self):
        resp = CreatePlatformPanel().request(
            {
                "name": "平台报表A",
                "status": "published",
                "visibility": {
                    "visibility_type": VisibilityScope.SPECIFIC_SCENES,
                    "scene_ids": [self.scene1.scene_id],
                    "system_ids": [],
                },
            }
        )

        group = SceneReportGroup.objects.get(scene_id=self.scene1.scene_id, group_type=ReportGroupType.PLATFORM)
        self.assertEqual(group.name, "平台报表")
        self.assertTrue(SceneReportGroupItem.objects.filter(group=group, panel_id=resp["id"]).exists())

    def test_update_platform_panel_auto_sync_new_scene(self):
        resp = CreatePlatformPanel().request(
            {
                "name": "平台报表B",
                "status": "published",
                "visibility": {
                    "visibility_type": VisibilityScope.SPECIFIC_SCENES,
                    "scene_ids": [self.scene1.scene_id],
                    "system_ids": [],
                },
            }
        )

        UpdatePlatformPanel().request(
            {
                "panel_id": resp["id"],
                "visibility": {
                    "visibility_type": VisibilityScope.SPECIFIC_SCENES,
                    "scene_ids": [self.scene1.scene_id, self.scene2.scene_id],
                    "system_ids": [],
                },
            }
        )

        group2 = SceneReportGroup.objects.get(scene_id=self.scene2.scene_id, group_type=ReportGroupType.PLATFORM)
        self.assertTrue(SceneReportGroupItem.objects.filter(group=group2, panel_id=resp["id"]).exists())

    def test_update_platform_panel_not_create_duplicate_group(self):
        resp = CreatePlatformPanel().request(
            {
                "name": "平台报表C",
                "status": "published",
                "visibility": {
                    "visibility_type": VisibilityScope.SPECIFIC_SCENES,
                    "scene_ids": [self.scene1.scene_id],
                    "system_ids": [],
                },
            }
        )

        UpdatePlatformPanel().request(
            {
                "panel_id": resp["id"],
                "visibility": {
                    "visibility_type": VisibilityScope.SPECIFIC_SCENES,
                    "scene_ids": [self.scene1.scene_id],
                    "system_ids": [],
                },
            }
        )

        self.assertEqual(
            SceneReportGroup.objects.filter(scene_id=self.scene1.scene_id, group_type=ReportGroupType.PLATFORM).count(),
            1,
        )

    def test_update_platform_panel_prune_stale_scene_group_item(self):
        resp = CreatePlatformPanel().request(
            {
                "name": "平台报表D",
                "status": "published",
                "visibility": {
                    "visibility_type": VisibilityScope.SPECIFIC_SCENES,
                    "scene_ids": [self.scene1.scene_id, self.scene2.scene_id],
                    "system_ids": [],
                },
            }
        )

        group2 = SceneReportGroup.objects.get(scene_id=self.scene2.scene_id, group_type=ReportGroupType.PLATFORM)
        self.assertTrue(SceneReportGroupItem.objects.filter(group=group2, panel_id=resp["id"]).exists())

        UpdatePlatformPanel().request(
            {
                "panel_id": resp["id"],
                "visibility": {
                    "visibility_type": VisibilityScope.SPECIFIC_SCENES,
                    "scene_ids": [self.scene1.scene_id],
                    "system_ids": [],
                },
            }
        )

        self.assertFalse(SceneReportGroupItem.objects.filter(group=group2, panel_id=resp["id"]).exists())

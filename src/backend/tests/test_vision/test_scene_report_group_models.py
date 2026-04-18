# -*- coding: utf-8 -*-
from django.db import IntegrityError
from django.test import TestCase

from services.web.scene.models import Scene
from services.web.vision.constants import ReportGroupType
from services.web.vision.models import (
    Scenario,
    SceneReportGroup,
    SceneReportGroupItem,
    VisionPanel,
)


class TestSceneReportGroupModels(TestCase):
    def setUp(self):
        self.scene = Scene.objects.create(name="s1", managers=["admin"], users=["u1"])
        self.panel = VisionPanel.objects.create(id="p1", name="p1", scenario=Scenario.DEFAULT)

    def test_create_group(self):
        group = SceneReportGroup.objects.create(
            scene=self.scene,
            name="平台报表",
            group_type=ReportGroupType.PLATFORM,
            priority_index=0,
        )
        self.assertEqual(group.name, "平台报表")

    def test_unique_group_name_in_same_scene(self):
        SceneReportGroup.objects.create(
            scene=self.scene,
            name="分组A",
            group_type=ReportGroupType.CUSTOM,
            priority_index=1,
        )
        with self.assertRaises(IntegrityError):
            SceneReportGroup.objects.create(
                scene=self.scene,
                name="分组A",
                group_type=ReportGroupType.CUSTOM,
                priority_index=2,
            )

    def test_panel_can_exist_in_multiple_groups_without_scene_unique_constraint(self):
        g1 = SceneReportGroup.objects.create(
            scene=self.scene,
            name="A",
            group_type=ReportGroupType.CUSTOM,
            priority_index=2,
        )
        g2 = SceneReportGroup.objects.create(
            scene=self.scene,
            name="B",
            group_type=ReportGroupType.CUSTOM,
            priority_index=1,
        )
        SceneReportGroupItem.objects.create(
            group=g1,
            panel=self.panel,
            priority_index=10,
        )
        SceneReportGroupItem.objects.create(
            group=g2,
            panel=self.panel,
            priority_index=5,
        )
        self.assertEqual(SceneReportGroupItem.objects.filter(panel=self.panel).count(), 2)

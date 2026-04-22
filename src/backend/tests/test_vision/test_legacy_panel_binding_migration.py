# -*- coding: utf-8 -*-
import importlib

from django.apps import apps
from django.test import TestCase

from services.web.scene.models import ResourceBinding, ResourceBindingScene, Scene
from services.web.vision.constants import (
    DEFAULT_SCENE_REPORT_GROUP_NAME,
    ReportGroupType,
)
from services.web.vision.models import (
    Scenario,
    SceneReportGroup,
    SceneReportGroupItem,
    VisionPanel,
)

DEFAULT_SCENE_NAME = "system_default"


class TestLegacyPanelBindingMigration(TestCase):
    def setUp(self):
        self.legacy_scene, _ = Scene.objects.get_or_create(
            name=DEFAULT_SCENE_NAME,
            defaults={
                "description": "系统默认场景（存量资源迁移生成）",
                "managers": [],
                "users": [],
            },
        )

    def test_cleanup_non_default_panel_scene_binding(self):
        tool_panel = VisionPanel.objects.create(
            id="legacy_tool_panel",
            name="历史工具报表",
            scenario=Scenario.TOOL,
            status="published",
        )
        per_app_panel = VisionPanel.objects.create(
            id="legacy_per_app_panel",
            name="历史应用报表",
            scenario=Scenario.PER_APP,
            status="published",
        )
        for panel in [tool_panel, per_app_panel]:
            binding = ResourceBinding.objects.create(
                resource_type="panel",
                resource_id=panel.id,
                binding_type="scene_binding",
                visibility_type="specific_scenes",
            )
            ResourceBindingScene.objects.create(binding=binding, scene=self.legacy_scene)

        migration = importlib.import_module(
            "services.web.vision.migrations.0013_cleanup_legacy_non_default_panel_scene_bindings"
        )
        migration.forwards(apps, None)

        self.assertFalse(ResourceBinding.objects.filter(resource_type="panel", resource_id=tool_panel.id).exists())
        self.assertFalse(ResourceBinding.objects.filter(resource_type="panel", resource_id=per_app_panel.id).exists())

    def test_backfill_default_group_skips_when_default_scene_absent(self):
        default_panel = VisionPanel.objects.create(
            id="legacy_default_panel_without_target_scene",
            name="历史默认报表",
            scenario=Scenario.DEFAULT,
            status="published",
        )
        binding = ResourceBinding.objects.create(
            resource_type="panel",
            resource_id=default_panel.id,
            binding_type="scene_binding",
            visibility_type="specific_scenes",
        )
        ResourceBindingScene.objects.create(binding=binding, scene=self.legacy_scene)
        self.legacy_scene.delete()

        migration = importlib.import_module("services.web.vision.migrations.0014_backfill_default_scene_panel_group")
        migration.forwards(apps, None)

        binding.refresh_from_db()
        self.assertFalse(Scene.objects.filter(name=DEFAULT_SCENE_NAME).exists())
        self.assertFalse(
            SceneReportGroupItem.objects.filter(
                panel_id=default_panel.id, group__name=DEFAULT_SCENE_REPORT_GROUP_NAME
            ).exists()
        )

    def test_backfill_default_group_adds_group_item_on_default_scene(self):
        default_panel = VisionPanel.objects.create(
            id="legacy_default_panel",
            name="历史默认报表",
            scenario=Scenario.DEFAULT,
            status="published",
        )
        binding = ResourceBinding.objects.create(
            resource_type="panel",
            resource_id=default_panel.id,
            binding_type="scene_binding",
            visibility_type="specific_scenes",
        )
        ResourceBindingScene.objects.create(binding=binding, scene=self.legacy_scene)

        migration = importlib.import_module("services.web.vision.migrations.0014_backfill_default_scene_panel_group")
        migration.forwards(apps, None)

        binding.refresh_from_db()
        self.assertEqual(list(binding.binding_scenes.values_list("scene_id", flat=True)), [self.legacy_scene.scene_id])

        group = SceneReportGroup.objects.get(scene=self.legacy_scene, name=DEFAULT_SCENE_REPORT_GROUP_NAME)
        self.assertEqual(group.group_type, ReportGroupType.CUSTOM)
        self.assertTrue(SceneReportGroupItem.objects.filter(group=group, panel_id=default_panel.id).exists())

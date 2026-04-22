# -*- coding: utf-8 -*-
import importlib

from django.apps import apps
from django.test import TestCase

from services.web.scene.constants import PanelStatus
from services.web.vision.models import VisionPanel


class TestVisionPanelStatusBackfillMigration(TestCase):
    def test_forwards_backfills_blank_status_to_published(self):
        panel = VisionPanel.objects.create(
            id="migration_status_panel",
            name="存量空状态报表",
            status="",
        )

        migration = importlib.import_module("services.web.vision.migrations.0012_backfill_visionpanel_status")
        migration.forwards(apps, None)

        panel.refresh_from_db()
        self.assertEqual(panel.status, PanelStatus.PUBLISHED)

    def test_forwards_keeps_non_blank_status_unchanged(self):
        panel = VisionPanel.objects.create(
            id="migration_published_panel",
            name="已发布报表",
            status=PanelStatus.PUBLISHED,
        )

        migration = importlib.import_module("services.web.vision.migrations.0012_backfill_visionpanel_status")
        migration.forwards(apps, None)

        panel.refresh_from_db()
        self.assertEqual(panel.status, PanelStatus.PUBLISHED)

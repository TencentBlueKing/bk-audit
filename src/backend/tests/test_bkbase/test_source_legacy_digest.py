"""旧在途 Source 摘要只能在原输入确实一致时继续。"""
from copy import deepcopy
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from services.web.bkbase import source


class SourceLegacyDigestTests(SimpleTestCase):
    def test_old_provision_digest_does_not_bypass_changed_input(self):
        snapshot = SimpleNamespace(
            system_id="synthetic",
            resource_type_id="asset",
            pull_config={"sensitivity": "private"},
            pull_type="http",
            join_data_type="asset",
        )
        params = {"access_raw_data": {"sensitivity": "private"}, "url": "/original"}
        context = {"tenant": "default", "namespace": "audit"}
        with mock.patch.object(source.System.objects, "filter") as system, mock.patch.object(
            source.ResourceType.objects, "filter"
        ) as resource:
            system.return_value.values.return_value.first.return_value = {"namespace": "audit"}
            resource.return_value.values.return_value.first.return_value = {"path": "/original"}
            legacy = source._provision_digest(snapshot, params, context, legacy=True)
            self.assertTrue(source._provision_input_matches(snapshot, params, context, legacy))
            changed = deepcopy(params)
            changed["url"] = "/changed"
            self.assertFalse(source._provision_input_matches(snapshot, changed, context, legacy))
            changed = deepcopy(params)
            changed["access_raw_data"]["sensitivity"] = "public"
            self.assertFalse(source._provision_input_matches(snapshot, changed, context, legacy))
            normalized = source._provision_digest(snapshot, params, context)
            self.assertTrue(source._provision_input_matches(snapshot, changed, context, normalized))

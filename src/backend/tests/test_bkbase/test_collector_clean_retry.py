"""验证采集项清洗在用户重新提交后能继续被轮询。"""
from copy import deepcopy
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase, override_settings

from services.web.bkbase import clean
from services.web.bkbase.constants import BKBASE_V4_MAX_POLLS
from services.web.bkbase.exceptions import BKBaseResourceMappingError


@override_settings(BKBASE_API_VERSION="v4")
class CollectorCleanRetryTests(SimpleTestCase):
    def test_resubmitted_clean_is_unblocked_and_gets_fresh_poll_budget(self):
        context = {"version": "v4", "tenant": "tenant_a", "namespace": "audit"}
        data_id = {"kind": "DataId", "tenant": "tenant_a", "namespace": "audit", "name": "data_a"}
        clean_ref = {"kind": "Clean", "tenant": "tenant_a", "namespace": "audit", "name": "clean_a"}
        rt_ref = {"kind": "ResultTable", "tenant": "tenant_a", "namespace": "audit", "name": "rt_a"}
        collector = SimpleNamespace(
            pk=1,
            collector_plugin_id=7,
            processing_id=None,
            bkbase_v4_resources={
                "data_id": data_id,
                "clean": clean_ref,
                "clean_role": "existing",
                "result_table": rt_ref,
                "clean_ready": False,
                "blocked": True,
                "poll_count": BKBASE_V4_MAX_POLLS,
                "clean_message": "previous timeout",
            },
        )
        params = {"raw_data_id": 11, "clean_config_name": "source", "json_config": {"extract": None}}
        old = {
            "kind": "Clean",
            "metadata": {"tenant": "tenant_a", "namespace": "audit", "name": "clean_a"},
            "spec": {
                "alias": "source",
                "description": "",
                "data_id": data_id,
                "raw_data_id": 11,
                "result_table_source": "existing",
                "result_table_id": "rt_a",
                "result_table_alias": "",
                "rules": [],
                "config_revision": 1,
                "deploy_revision": 1,
                "desired_status": "Running",
            },
            "status": {"phase": "Pending"},
        }

        def save_binding(owner, patch, *, remove=()):
            owner.bkbase_v4_resources.update(deepcopy(patch))
            for key in remove:
                owner.bkbase_v4_resources.pop(key, None)

        with mock.patch("requests.sessions.Session.request", side_effect=AssertionError("Unexpected HTTP")), mock.patch(
            "services.web.bkbase.clean.get_bkbase_context", return_value=context
        ), mock.patch(
            "services.web.bkbase.clean.CollectorPlugin.objects.get",
            return_value=SimpleNamespace(),
        ), mock.patch.object(
            clean, "_shared_plugin_table", return_value=("rt_a", rt_ref)
        ), mock.patch(
            "services.web.bkbase.clean.update_owner_binding", side_effect=save_binding
        ), mock.patch(
            "services.web.bkbase.clean.resource_lock"
        ), mock.patch(
            "services.web.bkbase.clean.get_resource_or_none", return_value=old
        ) as fetch:
            result = clean.configure_clean(collector, params, rt_owner=False)
            self.assertIsNone(result["task_state"])
            self.assertFalse(collector.bkbase_v4_resources["blocked"])
            self.assertEqual(collector.bkbase_v4_resources["poll_count"], 0)
            self.assertEqual(collector.bkbase_v4_resources["clean_message"], "")
            self.assertFalse(collector.bkbase_v4_resources["clean_ready"])

            old["status"] = {"phase": "Failed", "message": "clean failed"}
            result = clean.configure_clean(collector, params, rt_owner=False)
            self.assertEqual(result["task_state"], "failed")
            self.assertTrue(collector.bkbase_v4_resources["blocked"])
            self.assertEqual(collector.bkbase_v4_resources["clean_message"], "clean failed")

            collector.bkbase_v4_resources["poll_count"] = BKBASE_V4_MAX_POLLS
            fetch.side_effect = BKBaseResourceMappingError(message="unavailable")
            with self.assertRaises(BKBaseResourceMappingError):
                clean.configure_clean(collector, params, rt_owner=False)
            self.assertTrue(collector.bkbase_v4_resources["blocked"])
            self.assertEqual(collector.bkbase_v4_resources["poll_count"], BKBASE_V4_MAX_POLLS)

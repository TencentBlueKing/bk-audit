"""验证快照停止的持久意图、实际状态和过期回包保护。"""
import json
from copy import deepcopy
from types import SimpleNamespace
from unittest import mock

import requests
from django.test import TestCase, override_settings

from services.web.bkbase import source
from services.web.bkbase.constants import BKBASE_V4_MAX_POLLS
from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.databus.constants import SnapshotRunningStatus
from services.web.databus.models import Snapshot


@override_settings(BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="default", BKBASE_V4_NAMESPACE="audit")
class SnapshotStopStateTests(TestCase):
    def setUp(self):
        self.ref = {"kind": "DataSource", "tenant": "default", "namespace": "default_47", "name": "source_a"}
        self.snapshot = Snapshot.objects.create(
            system_id="synthetic",
            resource_type_id="asset",
            status=SnapshotRunningStatus.RUNNING,
            bkbase_v4_resources={"data_source": self.ref},
        )
        self.enterContext(mock.patch.object(source, "snapshot_lock"))
        self.enterContext(mock.patch.object(source, "resource_lock"))

    def test_stop_uses_persisted_business_source_ref_through_resource_request(self):
        calls = []
        current = {
            "metadata": {**self.ref, "labels": {"retain": "label"}},
            "spec": {"desired_status": "Running", "current_status": "Running", "retained": 1},
            "status": {"phase": "Ok"},
        }

        def transport(method, url, **kwargs):
            calls.append((method, url, deepcopy(kwargs)))
            self.assertTrue(url.endswith("/tenants/default/namespaces/default_47/datasources/source_a/"), url)
            if method == "PUT":
                self.assertEqual(kwargs["json"]["spec"], {**current["spec"], "desired_status": "Stopped"})
                self.assertEqual(kwargs["json"]["metadata"], current["metadata"])
                self.assertIsNone(kwargs["json"]["status"])
            response = requests.Response()
            response.status_code = 200
            response._content = json.dumps({"result": True, "code": "00", "data": current}).encode()
            return response

        with mock.patch("requests.sessions.Session.request", side_effect=transport):
            self.assertFalse(source.stop_snapshot(self.snapshot, {"bkbase_data_id": 11}))
        self.snapshot.refresh_from_db()
        self.assertEqual([call[0] for call in calls], ["GET", "PUT"])
        self.assertEqual(self.snapshot.bkbase_v4_resources["pending_action"], "stop")
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.RUNNING)

    def test_stop_without_complete_trusted_ref_fails_before_lookup(self):
        for ref in ({}, {**self.ref, "kind": "DataId"}, {**self.ref, "tenant": "other"}):
            snapshot = SimpleNamespace(bkbase_v4_resources={"data_source": ref})
            with self.subTest(ref=ref), mock.patch(
                "requests.sessions.Session.request", side_effect=AssertionError("HTTP")
            ):
                with self.assertRaises(BKBaseResourceMappingError):
                    source.stop_snapshot(snapshot, {})

    def test_pending_stop_waits_for_stopped_observation(self):
        old = {
            "metadata": {"name": "source_a"},
            "spec": {"desired_status": "Running", "current_status": "Stopped"},
            "status": {"phase": "Ok"},
        }
        accepted = deepcopy(old)
        accepted["spec"]["desired_status"] = "Stopped"
        with mock.patch.object(
            source.api.bk_base_v4, "data_source_get", side_effect=[old, accepted]
        ), mock.patch.object(source.api.bk_base_v4, "data_source_update", return_value=accepted):
            self.assertFalse(source.stop_snapshot(self.snapshot, {}, multiple_storage=True))
            source.poll_source_operations()
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.CLOSED)
        self.assertIsNone(self.snapshot.bkbase_v4_resources["pending_action"])

    def test_poll_does_not_close_when_desired_state_is_running(self):
        self.snapshot.bkbase_v4_resources["pending_action"] = "stop"
        self.snapshot.save(update_fields=["bkbase_v4_resources"])
        observed = {"spec": {"desired_status": "Running", "current_status": "Stopped"}, "status": {"phase": "Ok"}}
        with mock.patch.object(source.api.bk_base_v4, "data_source_get", return_value=observed):
            source.poll_source_operations()
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.RUNNING)
        self.assertEqual(self.snapshot.bkbase_v4_resources["pending_action"], "stop")

    def test_failed_or_timed_out_stop_marks_snapshot_failed(self):
        for phase, count in (("Failed", 0), ("Pending", BKBASE_V4_MAX_POLLS - 1)):
            with self.subTest(phase=phase):
                self.snapshot.status = SnapshotRunningStatus.RUNNING
                self.snapshot.bkbase_v4_resources = {
                    "data_source": self.ref,
                    "pending_action": "stop",
                    "source_poll_count": count,
                }
                self.snapshot.save(update_fields=["status", "bkbase_v4_resources"])
                observed = {
                    "spec": {"desired_status": "Stopped", "current_status": "Running"},
                    "status": {"phase": phase, "message": "source failed"},
                }
                with mock.patch.object(source.api.bk_base_v4, "data_source_get", return_value=observed):
                    source.poll_source_operations()
                self.snapshot.refresh_from_db()
                self.assertEqual(self.snapshot.status, SnapshotRunningStatus.FAILED)
                self.assertIsNone(self.snapshot.bkbase_v4_resources["pending_action"])
                self.assertIn("source failed", self.snapshot.status_msg)

    def test_poll_old_response_cannot_override_new_stop_token(self):
        self.snapshot.bkbase_v4_resources.update(pending_action="stop", source_stop_token="old")
        self.snapshot.save(update_fields=["bkbase_v4_resources"])

        def response(**kwargs):
            latest = Snapshot.objects.get(pk=self.snapshot.pk)
            latest.bkbase_v4_resources["source_stop_token"] = "new"
            latest.save(update_fields=["bkbase_v4_resources"])
            return {"spec": {"desired_status": "Stopped", "current_status": "Stopped"}, "status": {"phase": "Ok"}}

        with mock.patch.object(source.api.bk_base_v4, "data_source_get", side_effect=response):
            source.poll_source_operations()
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.RUNNING)
        self.assertEqual(self.snapshot.bkbase_v4_resources["source_stop_token"], "new")

    def test_unknown_stop_result_does_not_automatically_send_again(self):
        with mock.patch.object(source, "stop_source", side_effect=requests.Timeout("synthetic")) as stop:
            with self.assertRaises(requests.Timeout):
                source.stop_snapshot(self.snapshot, {})
            self.snapshot.refresh_from_db()
            token = self.snapshot.bkbase_v4_resources["source_stop_token"]
            self.assertFalse(source.stop_snapshot(self.snapshot, {}))
            self.snapshot.refresh_from_db()
            self.assertEqual(self.snapshot.bkbase_v4_resources["source_stop_token"], token)
            stop.assert_called_once()

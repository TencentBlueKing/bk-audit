"""验证采集项补提规则时的重试授权与轮询行为。"""
import json
from copy import deepcopy
from types import SimpleNamespace
from unittest import mock

import requests
from bk_resource.base import run_perform_request
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import resolve
from django.utils.module_loading import import_string
from rest_framework.test import APIRequestFactory, force_authenticate

from api.bk_base_v4.default import BkBaseV4Resource, CleanCreateRejected
from apps.meta.models import System
from apps.meta.utils.fields import STANDARD_FIELDS
from services.web.bkbase import clean
from services.web.bkbase.constants import BKBASE_V4_MAX_POLLS
from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.databus import tasks
from services.web.databus.collector.etl.etl_config_handler import base as config_base
from services.web.databus.collector.resources import CollectorEtlResource
from services.web.databus.constants import EtlConfigEnum
from services.web.databus.models import CollectorConfig, CollectorPlugin


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


@override_settings(BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="default", BKBASE_V4_NAMESPACE="audit")
class CollectorCleanHttpRetryTests(TestCase):
    def setUp(self):
        self.user = get_user_model()(username="etl_editor")
        system = System.objects.create(
            system_id="etl_retry_system",
            instance_id="etl_retry_system",
            namespace="audit",
            managers=[self.user.username],
        )
        plugin = CollectorPlugin.objects.create(
            namespace="audit",
            collector_plugin_id=92,
            collector_plugin_name="shared",
            collector_plugin_name_en="shared",
            bkdata_biz_id=47,
            table_id=910,
            index_set_id=920,
        )
        self.collector = CollectorConfig.objects.create(
            system_id=system.system_id,
            bk_biz_id=47,
            bk_data_id=93,
            collector_plugin_id=plugin.collector_plugin_id,
            collector_config_id=94,
            collector_config_name="collector",
            collector_config_name_en="collector",
            bkbase_v4_resources={"data_id": self.ref("DataId", "collector_data"), "source_raw_data_id": 93},
        )
        self.url = f"/api/v1/databus/namespaces/audit/collectors/{self.collector.collector_config_id}/collector_etl/"
        self.clean_get = 404
        self.create_outcome = "rejected"
        self.calls = []
        shared_table = ("47_shared", self.ref("ResultTable", "shared_rt"))
        self.enterContext(mock.patch.object(clean, "_shared_plugin_table", return_value=shared_table))
        self.enterContext(mock.patch.object(BkBaseV4Resource, "build_header", return_value={}))
        self.enterContext(mock.patch.object(config_base, "system_snapshot_table", return_value=None))
        self.enterContext(mock.patch("requests.sessions.Session.request", side_effect=self.transport))

    @staticmethod
    def ref(kind, name):
        return {"kind": kind, "tenant": "default", "namespace": "audit", "name": name}

    def transport(self, method, url, **kwargs):
        self.assertIn("/cleans/", url)
        self.calls.append((method, url, deepcopy(kwargs.get("json"))))
        if method == "GET":
            status, payload = self.clean_get, {}
            if status == 200:
                payload = self.posts[0]
        else:
            self.assertEqual(method, "POST")
            status, payload = 200, {**kwargs["json"], "status": {"phase": "Pending"}}
            if self.create_outcome == "timeout":
                raise requests.Timeout()
        body = {"result": status == 200, "code": "00", "data": payload}
        if method == "POST" and self.create_outcome == "rejected":
            body.update(
                result=False,
                code="1500102",
                data=None,
                messages={"details": [{"key": "error_detail", "value": "invalid old field mapping"}]},
            )
        response = requests.Response()
        response.status_code = status
        response.url = url
        response.request = requests.Request(method, url).prepare()
        response._content = json.dumps(body).encode()
        return response

    @property
    def posts(self):
        return [payload for method, _, payload in self.calls if method == "POST"]

    def payload(self, field_prefix="old"):
        return {
            "namespace": "audit",
            "collector_config_id": self.collector.collector_config_id,
            "etl_config": EtlConfigEnum.BK_LOG_JSON.value,
            "etl_params": {"retain_original_text": True},
            "fields": [
                {**field.to_json(), "option": {"path": f"attributes/{field_prefix}_{field.field_name}"}}
                for field in STANDARD_FIELDS
                if field.is_display
            ],
        }

    def save(self, payload, **headers):
        request = APIRequestFactory().post(self.url, payload, format="json", **headers)
        force_authenticate(request, self.user)
        match = resolve(self.url)
        with mock.patch("apps.meta.permissions.get_request_username", return_value=self.user.username):
            return match.func(request, **match.kwargs)

    def reject_first_create(self):
        response = self.save(self.payload())
        self.assertIn("invalid old field mapping", str(response.data))
        self.assertEqual(len(self.posts), 1)
        self.collector.refresh_from_db()
        binding = self.collector.bkbase_v4_resources
        self.assertIs(binding["clean_pending_create"], True)
        self.assertEqual(binding["clean_create_rejection"]["code"], "1500102")
        return deepcopy(binding)

    def test_authenticated_etl_save_retries_rejected_create_on_same_ref_with_new_rules(self):
        original = self.reject_first_create()
        self.create_outcome = "accepted"

        response = self.save(self.payload("fixed"))

        self.assertEqual(response.status_code, 200, response.data)
        self.assertIsNone(response.data)
        self.assertEqual(len(self.posts), 2)
        first, second = self.posts
        self.assertEqual(first["metadata"], second["metadata"])
        self.assertNotEqual(first["spec"]["rules"], second["spec"]["rules"])
        self.assertEqual(second["spec"]["result_table_source"], "existing")
        self.assertEqual(second["spec"]["result_table_id"], "47_shared")
        self.collector.refresh_from_db()
        binding = self.collector.bkbase_v4_resources
        self.assertEqual(binding["clean"], original["clean"])
        self.assertNotIn("clean_pending_create", binding)
        self.assertNotIn("clean_create_rejection", binding)
        self.assertEqual(self.collector.fields[0]["option"], self.payload("fixed")["fields"][0]["option"])

    def test_worker_and_direct_resource_cannot_retry_the_rejection(self):
        original = self.reject_first_create()
        self.create_outcome = "accepted"
        self.calls.clear()
        with mock.patch.object(tasks.time, "sleep"), mock.patch.object(
            tasks.resource.meta, "get_standard_fields", return_value=self.payload()["fields"]
        ), mock.patch.object(tasks, "API_PUSH_ETL_RETRY_TIMES", 2):
            tasks.create_api_push_etl.run(self.collector.collector_config_id)
        with self.assertRaises(CleanCreateRejected):
            CollectorEtlResource().request({**self.payload("fixed"), "retry_rejected_create": True})

        self.assertEqual(self.calls, [])
        self.collector.refresh_from_db()
        self.assertEqual(self.collector.bkbase_v4_resources, original)

    def test_async_http_payload_cannot_grant_retry_to_the_worker(self):
        original = self.reject_first_create()
        self.create_outcome = "accepted"
        self.calls.clear()
        payload = {**self.payload("fixed"), "retry_rejected_create": True, "_request": {"user": "etl_editor"}}
        with mock.patch.object(run_perform_request, "apply_async", return_value=SimpleNamespace(id="queued")) as launch:
            response = self.save(payload, HTTP_X_ASYNC_TASK="1")

        self.assertEqual(response.data, {"task_id": "queued"})
        resource_name, _, queued_payload = launch.call_args.kwargs["args"]
        with self.assertRaises(CleanCreateRejected):
            import_string(resource_name)().request(request_data=queued_payload)
        self.assertEqual(self.calls, [])
        self.collector.refresh_from_db()
        self.assertEqual(self.collector.bkbase_v4_resources, original)

    def test_unknown_outcome_is_observed_at_the_claim_and_never_reposted(self):
        self.create_outcome = "timeout"
        self.save(self.payload())
        self.collector.refresh_from_db()
        original = deepcopy(self.collector.bkbase_v4_resources)
        self.assertIs(original["clean_pending_create"], True)
        self.assertNotIn("clean_create_rejection", original)
        self.create_outcome = "accepted"

        response = self.save(self.payload("fixed"))

        self.assertIn("Previous Clean creation is still unconfirmed", str(response.data))
        self.assertEqual([method for method, _, _ in self.calls], ["GET", "POST", "GET"])
        self.collector.refresh_from_db()
        self.assertEqual(self.collector.bkbase_v4_resources, original)

    def test_existing_or_unreadable_clean_is_not_reposted_or_overwritten(self):
        original = self.reject_first_create()
        self.create_outcome = "accepted"
        for read_status in (200, 403):
            with self.subTest(read_status=read_status):
                self.clean_get = read_status
                before = len(self.calls)
                response = self.save(self.payload("fixed"))
                self.assertNotEqual(response.status_code, 200)
                ((method, url, _),) = self.calls[before:]
                self.assertEqual(method, "GET")
                self.assertTrue(url.rstrip("/").endswith(original["clean"]["name"]))
                self.collector.refresh_from_db()
                self.assertEqual(self.collector.bkbase_v4_resources, original)

    def test_retry_timeout_consumes_rejection_and_leaves_only_observation(self):
        original = self.reject_first_create()
        self.create_outcome = "timeout"
        self.save(self.payload("fixed"))
        self.collector.refresh_from_db()
        binding = self.collector.bkbase_v4_resources
        self.assertEqual(binding["clean"], original["clean"])
        self.assertIs(binding["clean_pending_create"], True)
        self.assertNotIn("clean_create_rejection", binding)
        self.create_outcome = "accepted"

        response = self.save(self.payload("fixed"))

        self.assertIn("Previous Clean creation is still unconfirmed", str(response.data))
        self.assertEqual([method for method, _, _ in self.calls], ["GET", "POST", "GET", "POST", "GET"])

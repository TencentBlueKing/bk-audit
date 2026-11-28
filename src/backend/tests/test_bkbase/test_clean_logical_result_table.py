"""从 Clean 和插件入口验证逻辑结果表名与正式引用各自的来源。"""
import json
from copy import deepcopy
from io import StringIO
from types import SimpleNamespace
from unittest import mock

import requests
from bk_resource.exceptions import APIRequestError
from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, TestCase, override_settings

from api.bk_base_v4.default import BkBaseV4Resource
from apps.meta.utils.fields import STANDARD_FIELDS
from services.web.bkbase import clean
from services.web.bkbase.constants import CleanRole, TaskState
from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.databus import tasks
from services.web.databus.collector.etl import base as etl_base
from services.web.databus.collector.resources import DataIdEtlStorage, EtlClean
from services.web.databus.collector.serializers import GetCollectorsResponseSerializer
from services.web.databus.collector_plugin.serializers import (
    PluginListResponseSerializer,
)
from services.web.databus.constants import (
    DORIS_EVENT_BKBASE_RT_ID_KEY,
    DORIS_EVENT_PHYSICAL_TABLE_NAME_KEY,
    EtlConfigEnum,
    PluginSceneChoices,
)
from services.web.databus.models import CollectorConfig, CollectorPlugin


@override_settings(
    BKBASE_API_VERSION="v4",
    BKBASE_V4_TENANT="default",
    BKBASE_V4_NAMESPACE="audit",
    BKBASE_V4_RESULT_TABLE_NAMESPACES={"47_logical": "audit"},
)
class CleanLogicalResultTableTests(SimpleTestCase):
    def setUp(self):
        self.logical_id = "47_logical"
        self.rt_ref = self.ref("ResultTable", "c_47_different_actual")
        self.clean_ref = self.ref("Clean", "owner_clean")
        self.data_id = self.ref("DataId", "source_data")
        self.owner = SimpleNamespace(
            pk=1,
            bkbase_processing_id=None,
            namespace="audit",
            plugin_scene=PluginSceneChoices.EVENT,
            has_storage=False,
            has_replica_storage=False,
            save=mock.Mock(),
            bkbase_v4_resources={
                "clean": self.clean_ref,
                "data_id": self.data_id,
                "source_raw_data_id": 91,
                "clean_role": CleanRole.OWNER,
                "result_table_id": self.logical_id,
            },
        )
        self.params = {
            "raw_data_id": 91,
            "bk_biz_id": 47,
            "result_table_name": "logical",
            "result_table_name_alias": "Synthetic",
            "json_config": {"extract": None},
        }
        self.remote_clean = self.remote(
            self.clean_ref,
            {
                "raw_data_id": 91,
                "data_id": self.data_id,
                "result_table_id": self.logical_id,
                "result_table_source": "new",
                "desired_status": "Running",
                "current_status": "Running",
                "config_revision": 17,
                "deploy_revision": 17,
            },
        )
        self.remote_rt = self.remote(
            self.rt_ref, {"predefiendResultTableId": self.logical_id, "bizId": 47}, result_table_id=self.logical_id
        )
        self.source_ref = self.ref("DataSource", "owner_source")
        self.remote_source = self.remote(self.source_ref, {"data_id": self.data_id}, raw_data_id="91")
        self.owner.bkbase_v4_resources["data_source"] = self.source_ref
        self.owner_found = True
        self.collector = SimpleNamespace(
            pk=2,
            processing_id=None,
            collector_plugin_id=9,
            bkbase_v4_resources={"data_id": self.ref("DataId", "child_data")},
        )
        self.handler = SimpleNamespace(
            plugin=self.owner,
            build_clean_config=lambda: self.params,
            build_event_storage_config=lambda: {
                "storage_type": "doris",
                "physical_table_name": "audit_events.synthetic",
            },
        )
        self.calls = []
        self.created = None
        self.clean_create_response = None
        self.enterContext(mock.patch.object(BkBaseV4Resource, "build_header", return_value={}))
        self.enterContext(mock.patch("requests.sessions.Session.request", side_effect=self.transport))
        self.enterContext(mock.patch.object(clean, "resource_lock"))
        self.enterContext(mock.patch.object(clean, "update_owner_binding", side_effect=self.save_binding))
        self.enterContext(mock.patch.object(clean.CollectorPlugin.objects, "get", return_value=self.owner))
        self.storage = self.enterContext(
            mock.patch.object(
                clean.storage_service,
                "configure_storage",
                return_value={"task_state": TaskState.RUNNING},
            )
        )
        self.global_config = self.enterContext(mock.patch.object(clean.GlobalMetaConfig, "set"))

    @staticmethod
    def ref(kind, name):
        return {"kind": kind, "tenant": "default", "namespace": "audit", "name": name}

    def remote(self, ref, spec, **labels):
        return {
            "kind": ref["kind"],
            "metadata": {key: ref[key] for key in ("tenant", "namespace", "name")} | {"labels": labels},
            "spec": spec,
            "status": {"phase": "Ok"},
        }

    @staticmethod
    def save_binding(owner, patch, *, remove=()):
        owner.bkbase_v4_resources.update(deepcopy(patch))
        for key in remove:
            owner.bkbase_v4_resources.pop(key, None)

    def transport(self, method, url, **kwargs):
        self.calls.append((method, url, deepcopy(kwargs.get("json"))))
        status_code = 200
        if "/cleans/" in url and method == "POST":
            self.created = deepcopy(kwargs["json"]["spec"])
            payload = {
                "metadata": deepcopy(kwargs["json"]["metadata"]),
                "spec": self.created,
                "status": {"phase": "Pending"},
            }
        elif "/cleans/owner_clean/" in url:
            if not self.owner_found:
                status_code = 404
            if method == "PUT":
                spec = deepcopy(kwargs["json"]["spec"])
                spec["current_status"] = "Running"
                self.remote_clean["spec"] = spec
            payload = self.remote_clean
        elif "/cleans/" in url and method == "GET":
            status_code, payload = 404, {}
        elif "/datasources/owner_source/" in url:
            self.assertEqual(method, "GET")
            payload = self.remote_source
        elif "/v4/result_tables/" in url:
            self.assertEqual(method, "GET")
            self.assertEqual(kwargs["headers"]["X-Bk-Tenant-Id"], "default")
            payload = self.remote_rt
        elif "/dataset/" in url:
            self.assertEqual(method, "GET")
            self.assertEqual(kwargs["headers"]["X-Bk-Tenant-Id"], "default")
            if "/dataset_list/" in url:
                self.assertEqual(kwargs["params"]["dataset_name"], self.logical_id)
            row = {"dataset_name": self.logical_id, "storage_type": "doris"}
            payload = row if "/detail/" in url else {"list": [row], "total": 1}
        else:
            self.fail(f"Unexpected endpoint {method} {url}")
        response = requests.Response()
        response.status_code = status_code
        response.url = url
        response.request = requests.Request(method, url).prepare()
        body = {"result": status_code == 200, "code": "00", "data": payload}
        if "/cleans/" in url and method == "POST" and self.clean_create_response is not None:
            body = self.clean_create_response
        response._content = json.dumps(body).encode()
        return response

    def test_owner_can_declare_logical_id_without_inventing_a_result_table_ref(self):
        self.owner.bkbase_v4_resources.pop("clean")
        self.owner.bkbase_v4_resources.pop("result_table_id")
        with mock.patch.object(clean, "get_resource_or_none", return_value=None):
            clean.configure_clean(self.owner, self.params, rt_owner=True)
        self.assertEqual(self.created["result_table_id"], self.logical_id)
        self.assertEqual(self.owner.bkbase_v4_resources["clean"]["name"], f"c_{self.logical_id}")
        self.assertEqual(self.owner.bkbase_v4_resources["result_table_id"], self.logical_id)
        self.assertNotIn("result_table", self.owner.bkbase_v4_resources)

    def test_old_unknown_owner_claim_does_not_post_under_a_new_or_old_name(self):
        self.owner.bkbase_v4_resources["clean_pending_create"] = True
        self.owner_found = False
        with self.assertRaises(BKBaseResourceMappingError):
            clean.configure_clean(self.owner, self.params, rt_owner=True)
        self.assertEqual(self.owner.bkbase_v4_resources["clean"], self.clean_ref)
        self.assertIs(self.owner.bkbase_v4_resources["clean_pending_create"], True)
        self.assertFalse(any(method == "POST" for method, _, _ in self.calls))

    def test_plugin_create_rejected_without_details_blocks_and_keeps_gateway_code(self):
        self.owner.bkbase_v4_resources.pop("clean")
        self.owner.bkbase_v4_resources.pop("result_table_id")
        self.clean_create_response = {"result": False, "code": "1500113", "data": None}

        clean.configure_plugin(self.handler)
        clean.configure_plugin(self.handler)

        binding = self.owner.bkbase_v4_resources
        self.assertTrue(binding["blocked"])
        self.assertTrue(binding["clean_pending_create"])
        self.assertEqual(binding["clean_create_rejection"]["code"], "1500113")
        self.assertIn("[1500113]", binding["message"])
        self.assertEqual(sum(method == "POST" for method, _, _ in self.calls), 1)

    def test_plugin_explicit_save_can_retry_definite_rejection_once_at_same_ref(self):
        for retry_failed in (False, True):
            with self.subTest(retry_failed=retry_failed):
                self.calls.clear()
                self.owner.bkbase_v4_resources.pop("clean", None)
                self.owner.bkbase_v4_resources.pop("result_table_id", None)
                self.owner.bkbase_v4_resources.pop(clean.PLUGIN_RETRY_STEPS, None)
                self.clean_create_response = {"result": False, "code": "1500113", "data": None}
                clean.configure_plugin(self.handler)
                claimed = deepcopy(self.owner.bkbase_v4_resources["clean"])
                clean.reset_plugin_operation(self.owner, retry_failed=retry_failed)
                self.clean_create_response = None

                with mock.patch.object(clean, "get_resource_or_none", return_value=self.remote_clean):
                    clean.configure_plugin(self.handler)
                self.assertIn("clean_create_rejection", self.owner.bkbase_v4_resources)
                self.assertEqual(sum(method == "POST" for method, _, _ in self.calls), 1)

                clean.configure_plugin(self.handler)

                binding = self.owner.bkbase_v4_resources
                self.assertEqual(binding["clean"], claimed)
                self.assertNotIn("clean_create_rejection", binding)
                self.assertNotIn("clean_pending_create", binding)
                self.assertEqual(binding[clean.PLUGIN_RETRY_STEPS], ["main", "replica"])
                writes = [payload["metadata"]["name"] for method, _, payload in self.calls if method == "POST"]
                self.assertEqual(writes, [claimed["name"], claimed["name"]])

    def test_plugin_retry_with_malformed_receipt_does_not_reuse_consumed_qualification(self):
        self.owner.bkbase_v4_resources.pop("clean")
        self.owner.bkbase_v4_resources.pop("result_table_id")
        self.clean_create_response = {"result": False, "code": "1500102", "data": None}
        clean.configure_plugin(self.handler)
        clean.reset_plugin_operation(self.owner, retry_failed=True)
        self.clean_create_response = {"result": True, "code": "00", "data": {"status": {"phase": "Pending"}}}

        clean.configure_plugin(self.handler)
        clean.configure_plugin(self.handler)

        binding = self.owner.bkbase_v4_resources
        self.assertTrue(binding["clean_pending_create"])
        self.assertNotIn("clean_create_rejection", binding)
        self.assertNotIn("clean", binding[clean.PLUGIN_RETRY_STEPS])
        self.assertEqual(sum(method == "POST" for method, _, _ in self.calls), 2)

    def test_malformed_clean_success_cannot_clear_claim_or_cause_another_post(self):
        self.owner.bkbase_v4_resources.pop("clean")
        self.owner.bkbase_v4_resources.pop("result_table_id")
        self.clean_create_response = {"result": True, "code": "00", "data": {"status": {"phase": "Pending"}}}
        for _ in range(2):
            with self.assertRaises(BKBaseResourceMappingError):
                clean.configure_clean(self.owner, self.params, rt_owner=True)
        self.assertTrue(self.owner.bkbase_v4_resources["clean_pending_create"])
        self.assertNotIn("clean_create_rejection", self.owner.bkbase_v4_resources)
        self.assertEqual(sum(method == "POST" for method, _, _ in self.calls), 1)

    def test_known_owner_clean_and_distinct_table_ref_can_be_reused_by_collector(self):
        self.owner.bkbase_v4_resources["result_table"] = self.rt_ref
        with mock.patch.object(clean, "ensure_clean") as ensure:
            clean.configure_clean(self.collector, {"raw_data_id": 92, "json_config": {"extract": None}}, rt_owner=False)
        spec = ensure.call_args.kwargs["rules"]
        self.assertEqual(spec["result_table_id"], self.logical_id)
        self.assertEqual(ensure.call_args.kwargs["rt_ref"], self.rt_ref)
        self.assertEqual(self.owner.bkbase_v4_resources["result_table_id"], self.logical_id)

    def test_owner_clean_identity_or_target_conflict_is_rejected(self):
        self.owner.bkbase_v4_resources["result_table"] = self.rt_ref
        baseline = deepcopy(self.remote_clean["spec"])
        for changed in (
            {"raw_data_id": 999},
            {"result_table_source": "existing"},
            {"data_id": self.collector.bkbase_v4_resources["data_id"]},
        ):
            with self.subTest(changed=changed), mock.patch.object(clean, "ensure_clean") as ensure:
                self.remote_clean["spec"] = {**baseline, **changed}
                with self.assertRaises(BKBaseResourceMappingError):
                    clean.configure_clean(self.collector, {"raw_data_id": 92, "json_config": {"extract": None}})
                ensure.assert_not_called()
                self.assertEqual(self.owner.bkbase_v4_resources["result_table_id"], self.logical_id)
        self.remote_clean["spec"] = baseline
        self.owner.bkbase_v4_resources["result_table_id"] = "47_conflict"
        with self.assertRaises(BKBaseResourceMappingError):
            clean.configure_clean(self.owner, self.params, rt_owner=True)

    def test_saved_logical_intent_never_authorizes_an_unready_owner(self):
        self.owner.bkbase_v4_resources.update(result_table_id=self.logical_id, result_table=self.rt_ref)
        current = self.remote_clean["spec"]
        for condition in (
            "pending_marker",
            "missing",
            "pending",
            "revision",
            "desired",
            "role",
            "raw",
            "data",
            "logical",
        ):
            with self.subTest(condition=condition):
                self.owner.bkbase_v4_resources.pop("clean_pending_create", None)
                self.owner_found = condition != "missing"
                self.remote_clean["spec"] = deepcopy(current)
                self.remote_clean["status"]["phase"] = "Pending" if condition == "pending" else "Ok"
                if condition == "pending_marker":
                    self.owner.bkbase_v4_resources["clean_pending_create"] = True
                if condition == "revision":
                    self.remote_clean["spec"]["deploy_revision"] = 16
                if condition == "desired":
                    self.remote_clean["spec"]["desired_status"] = "Stopped"
                if condition == "role":
                    self.remote_clean["spec"]["result_table_source"] = "existing"
                if condition == "raw":
                    self.remote_clean["spec"]["raw_data_id"] = 99
                if condition == "data":
                    self.remote_clean["spec"]["data_id"] = self.collector.bkbase_v4_resources["data_id"]
                if condition == "logical":
                    self.remote_clean["spec"]["result_table_id"] = "47_other"
                with self.assertRaises((APIRequestError, BKBaseResourceMappingError)):
                    clean.configure_clean(self.collector, {"raw_data_id": 92, "json_config": {"extract": None}})
        self.assertFalse(any(method != "GET" for method, _, _ in self.calls))

    def test_old_source_binding_can_verify_raw_id_before_existing_clean_write(self):
        self.owner.bkbase_v4_resources.update(result_table_id=self.logical_id, result_table=self.rt_ref)
        self.owner.bkbase_v4_resources.pop("source_raw_data_id")
        with mock.patch.object(clean, "get_resource_or_none", return_value=None):
            clean.configure_clean(self.collector, {"raw_data_id": 92, "json_config": {"extract": None}})
        self.assertTrue(any("/datasources/owner_source/" in url for _, url, _ in self.calls))
        self.assertEqual(self.owner.bkbase_v4_resources["source_raw_data_id"], 91)
        self.assertEqual(self.created["result_table_id"], self.logical_id)
        self.assertEqual(self.created["result_table_source"], "existing")
        self.assertEqual(
            self.collector.bkbase_v4_resources["clean"]["name"],
            clean.stable_name("c", self.collector.__class__.__name__, self.collector.pk),
        )

    def test_missing_ref_is_resolved_and_persisted_before_actual_storage_consumer(self):
        info = {
            "metadata": {key: self.rt_ref[key] for key in ("tenant", "namespace", "name")},
            "spec": {"predefiendResultTableId": self.logical_id, "bizId": 47},
            "status": {"related": []},
        }

        def storage_with_verified_ref(*args, **kwargs):
            self.assertEqual(self.owner.bkbase_v4_resources["result_table"], self.rt_ref)
            return {"task_state": TaskState.RUNNING}

        self.storage.side_effect = storage_with_verified_ref
        with mock.patch.object(clean.api.bk_base_v4, "result_table_info", return_value=info) as lookup:
            clean.configure_plugin(self.handler)
        self.assertEqual(lookup.call_args_list, [mock.call(tenant="default", result_table_id=self.logical_id)] * 2)
        self.storage.assert_called_once()
        self.assertFalse(any("/resulttables/" in url for _, url, _ in self.calls))

    def test_shared_owner_missing_ref_is_resolved_and_persisted_after_clean_verification(self):
        self.owner.bkbase_v4_resources["result_table_id"] = self.logical_id
        info = {
            "metadata": {key: self.rt_ref[key] for key in ("tenant", "namespace", "name")},
            "spec": {"predefiendResultTableId": self.logical_id},
        }
        with mock.patch.object(clean.api.bk_base_v4, "result_table_info", return_value=info) as lookup:
            logical, ref = clean._shared_plugin_table(clean.get_bkbase_context(), self.owner)
        self.assertEqual((logical, ref), (self.logical_id, self.rt_ref))
        self.assertEqual(self.owner.bkbase_v4_resources["result_table"], self.rt_ref)
        lookup.assert_called_once_with(tenant="default", result_table_id=self.logical_id)
        self.assertIsNone(self.created)

    def test_failed_logical_lookup_does_not_attach_ref_or_write_storage(self):
        error = APIRequestError(module_name="bkbase_v4", url="/v4/result_tables/", result="synthetic lookup failed")
        with mock.patch.object(clean.api.bk_base_v4, "result_table_info", side_effect=error):
            clean.configure_plugin(self.handler)
        self.storage.assert_not_called()
        self.assertNotIn("result_table", self.owner.bkbase_v4_resources)
        self.assertFalse(self.owner.bkbase_v4_resources["ready"])

    def test_storage_does_not_use_conflicting_historical_ref_or_logical_identity(self):
        self.owner.bkbase_v4_resources["result_table"] = self.ref("ResultTable", self.logical_id)
        clean.configure_plugin(self.handler)
        self.assertTrue(any(f"/v4/result_tables/{self.logical_id}/" in url for _, url, _ in self.calls))
        self.owner.bkbase_v4_resources["result_table"] = self.rt_ref
        self.remote_rt["metadata"]["labels"]["result_table_id"] = "47_other"
        clean.configure_plugin(self.handler)
        self.storage.assert_not_called()
        self.assertFalse(self.owner.bkbase_v4_resources["ready"])

    def test_event_plugin_completes_without_rt_metadata_physical_name(self):
        self.owner.bkbase_v4_resources["result_table"] = self.rt_ref
        clean.configure_plugin(self.handler)
        self.storage.assert_called_once()
        self.assertEqual(self.owner.bkbase_v4_resources["result_table"], self.rt_ref)
        self.assertFalse(any("/detail/" in url for _, url, _ in self.calls))
        values = dict(call.args for call in self.global_config.call_args_list)
        self.assertEqual(values[DORIS_EVENT_PHYSICAL_TABLE_NAME_KEY], "audit_events.synthetic")
        self.assertEqual(values[DORIS_EVENT_BKBASE_RT_ID_KEY], self.logical_id)
        self.assertTrue(self.owner.bkbase_v4_resources["ready"])

    def test_event_config_uses_logical_id_when_physical_mapping_is_explicit(self):
        self.owner.bkbase_v4_resources["result_table"] = self.rt_ref
        with mock.patch.object(
            clean.metadata_service,
            "get_result_table",
            return_value={"storages": {"doris": {"physical_table_name": "platform_confirmed_table"}}},
        ):
            clean.configure_plugin(self.handler)
        values = dict(call.args for call in self.global_config.call_args_list)
        self.assertEqual(values[DORIS_EVENT_BKBASE_RT_ID_KEY], self.logical_id)
        self.assertEqual(values[DORIS_EVENT_PHYSICAL_TABLE_NAME_KEY], "audit_events.synthetic")

    def test_public_result_table_projection_never_uses_ref_name(self):
        self.owner.bkbase_v4_resources.pop("result_table_id")
        self.owner.bkbase_v4_resources.update(result_table=self.rt_ref, ready=True)
        self.assertIsNone(clean.result_table_id(self.owner))
        self.owner.bkbase_v4_resources["result_table_id"] = self.logical_id
        self.assertEqual(clean.result_table_id(self.owner), self.logical_id)


@override_settings(
    BKBASE_API_VERSION="v4",
    BKBASE_V4_TENANT="default",
    BKBASE_V4_NAMESPACE="audit",
)
class ReadyCleanLogicalBackfillTests(TestCase):
    def setUp(self):
        self.enterContext(mock.patch.object(BkBaseV4Resource, "build_header", return_value={}))
        self.enterContext(mock.patch("requests.sessions.Session.request", side_effect=self.transport))
        self.enterContext(mock.patch.object(clean, "resource_lock"))
        self.responses = {}
        self.calls = []
        self.on_read = None

    def binding(self, name, raw_id, role, *, ready_field):
        ref = CleanLogicalResultTableTests.ref
        clean_ref = ref("Clean", f"clean_{name}")
        source_ref = ref("DataSource", f"source_{name}")
        data_id = ref("DataId", f"data_{name}")
        logical = f"47_{name}"
        self.responses[clean_ref["name"]] = {
            "kind": "Clean",
            "metadata": {key: clean_ref[key] for key in ("tenant", "namespace", "name")},
            "spec": {
                "data_id": data_id,
                "raw_data_id": raw_id,
                "result_table_id": logical,
                "result_table_source": "new" if role == "owner" else "existing",
                "desired_status": "Running",
                "current_status": "Running",
                "config_revision": 42,
                "deploy_revision": 42,
            },
            "status": {"phase": "Ok"},
        }
        self.responses[source_ref["name"]] = {
            "kind": "DataSource",
            "metadata": {
                **{key: source_ref[key] for key in ("tenant", "namespace", "name")},
                "labels": {"raw_data_id": str(raw_id)},
            },
            "spec": {"data_id": data_id},
        }
        return {
            "clean": clean_ref,
            "clean_role": role,
            "data_source": source_ref,
            "data_id": data_id,
            "result_table": ref("ResultTable", f"actual_{name}"),
            ready_field: True,
        }

    def transport(self, method, url, **kwargs):
        self.assertEqual(method, "GET")
        name = url.rstrip("/").rsplit("/", 1)[-1]
        self.calls.append(name)
        if self.on_read:
            self.on_read(name)
        response = requests.Response()
        response.status_code = 200
        response.url = url
        response._content = json.dumps({"result": True, "code": "00", "data": self.responses[name]}).encode()
        return response

    def plugin(self, name, raw_id):
        return CollectorPlugin.objects.create(
            namespace="audit",
            collector_plugin_id=raw_id,
            collector_plugin_name=name,
            collector_plugin_name_en=name,
            bkdata_biz_id=47,
            table_id=raw_id,
            index_set_id=raw_id,
            bkbase_v4_resources=self.binding(name, raw_id, "owner", ready_field="ready"),
        )

    def run_backfill(self, owner, **options):
        output, errors = StringIO(), StringIO()
        call_command("backfill_bkbase_clean_result_table_ids", owner=owner, stdout=output, stderr=errors, **options)
        return output.getvalue(), errors.getvalue()

    def test_explicit_backfill_restores_legacy_plugin_and_collector_projection(self):
        plugin = self.plugin("plugin", 91)
        collector = CollectorConfig.objects.create(
            system_id="synthetic",
            bk_biz_id=47,
            bk_data_id=92,
            collector_plugin_id=91,
            collector_config_id=-92,
            collector_config_name="collector",
            bkbase_v4_resources=self.binding("collector", 92, "existing", ready_field="clean_ready"),
        )
        self.assertIsNone(PluginListResponseSerializer(plugin).data["bkbase_table_id"])
        self.assertIsNone(GetCollectorsResponseSerializer(collector).data["bkbase_table_id"])
        self.assertEqual(self.calls, [])
        with mock.patch("core.lock.CacheLock._init", return_value=True), mock.patch(
            "core.lock.CacheLock.release", return_value=True
        ):
            tasks.poll_bkbase_v4_clean_operations.run()
        self.assertEqual(self.calls, [], "periodic Clean/Source observation must not backfill")
        self.run_backfill("plugin")
        self.run_backfill("collector")
        plugin.refresh_from_db()
        collector.refresh_from_db()
        self.assertEqual(PluginListResponseSerializer(plugin).data["bkbase_table_id"], "47_plugin")
        self.assertEqual(GetCollectorsResponseSerializer(collector).data["bkbase_table_id"], "47_collector")
        self.assertEqual(plugin.bkbase_v4_resources["source_raw_data_id"], 91)
        self.assertEqual(collector.bkbase_v4_resources["source_raw_data_id"], 92)
        self.assertEqual(set(self.calls), {"clean_plugin", "clean_collector", "source_plugin", "source_collector"})
        self.calls.clear()
        self.run_backfill("plugin")
        self.run_backfill("collector")
        self.assertEqual(self.calls, [])

    def test_invalid_sdk_payload_does_not_starve_next_record_or_window(self):
        first = self.plugin("invalid", 91)
        second = self.plugin("later", 92)
        third = self.plugin("next_window", 93)
        self.responses["clean_invalid"] = ["invalid_response_object"]
        output, errors = self.run_backfill("plugin", limit=2)
        first.refresh_from_db()
        second.refresh_from_db()
        third.refresh_from_db()
        self.assertIn(f"pk={first.pk} ValidateException", errors)
        self.assertIn(f"next_after_pk={second.pk}", output)
        self.assertNotIn("result_table_id", first.bkbase_v4_resources)
        self.assertEqual(second.bkbase_v4_resources["result_table_id"], "47_later")
        self.assertNotIn("result_table_id", third.bkbase_v4_resources)
        self.run_backfill("plugin", after_pk=second.pk)
        third.refresh_from_db()
        self.assertEqual(third.bkbase_v4_resources["result_table_id"], "47_next_window")

    def test_backfill_does_not_replace_newer_local_binding(self):
        plugin = self.plugin("concurrent", 91)

        def change_binding(name):
            if name == "clean_concurrent":
                CollectorPlugin.objects.filter(pk=plugin.pk).update(
                    bkbase_v4_resources={**plugin.bkbase_v4_resources, "retained": "newer"}
                )

        self.on_read = change_binding
        _, errors = self.run_backfill("plugin")
        plugin.refresh_from_db()
        self.assertIn("changed", errors)
        self.assertEqual(plugin.bkbase_v4_resources["retained"], "newer")
        self.assertNotIn("result_table_id", plugin.bkbase_v4_resources)

    def test_backfill_does_not_attach_old_clean_after_collector_numeric_id_changes(self):
        binding = self.binding("concurrent_collector", 92, "existing", ready_field="clean_ready")
        owner = CollectorConfig.objects.create(
            system_id="synthetic",
            bk_biz_id=47,
            bk_data_id=92,
            collector_plugin_id=91,
            collector_config_id=-92,
            collector_config_name="collector",
            bkbase_v4_resources=binding,
        )
        for old_raw_id, new_raw_id in ((92, 93), (None, 93), (92, None)):
            with self.subTest(old_raw_id=old_raw_id, new_raw_id=new_raw_id):
                CollectorConfig.objects.filter(pk=owner.pk).update(bk_data_id=old_raw_id, bkbase_v4_resources=binding)

                def change_raw_id(name):
                    if name == "clean_concurrent_collector":
                        CollectorConfig.objects.filter(pk=owner.pk).update(bk_data_id=new_raw_id)

                self.on_read = change_raw_id
                _, errors = self.run_backfill("collector")
                owner.refresh_from_db()
                self.assertIn("binding changed", errors)
                self.assertEqual(owner.bk_data_id, new_raw_id)
                self.assertEqual(owner.bkbase_v4_resources, binding)

    def test_invalid_window_is_rejected_before_reading_platform(self):
        with self.assertRaises(CommandError):
            self.run_backfill("plugin", limit=0)
        self.assertEqual(self.calls, [])

    def test_collector_etl_request_does_not_write_if_bound_plugin_clean_is_pending(self):
        plugin = self.plugin("plugin", 91)
        plugin.bkbase_v4_resources.update(result_table_id="47_plugin", source_raw_data_id=91)
        plugin.save(update_fields=["bkbase_v4_resources"])
        self.responses["clean_plugin"]["status"]["phase"] = "Pending"
        owner = CollectorConfig.objects.create(
            system_id="synthetic",
            bk_biz_id=47,
            bk_data_id=92,
            collector_plugin_id=91,
            collector_config_id=-92,
            collector_config_name="collector",
            bkbase_v4_resources={"data_id": CleanLogicalResultTableTests.ref("DataId", "collector_input")},
        )
        before = deepcopy(owner.bkbase_v4_resources)
        handler = EtlClean.get_instance(EtlConfigEnum.BK_BASE_JSON)
        fields = [
            {**field.to_json(), "option": {"path": [field.field_name]}}
            for field in STANDARD_FIELDS
            if field.is_required and field.is_display
        ]
        with mock.patch.object(etl_base, "resource_lock"), mock.patch.object(
            type(handler),
            "get_bkbase_etl_config",
            return_value={"raw_data_id": 92, "json_config": {"extract": None}},
        ):
            with self.assertRaises(BKBaseResourceMappingError):
                DataIdEtlStorage().request({"namespace": "audit", "bk_data_id": 92, "fields": fields})
        owner.refresh_from_db()
        self.assertEqual(owner.bkbase_v4_resources, before)
        self.assertEqual(self.calls, ["clean_plugin"])

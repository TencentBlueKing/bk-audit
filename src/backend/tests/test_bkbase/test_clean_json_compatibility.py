"""真实生成器与维护 Service 保留同一绑定的旧显式 null 解码语义，不采纳旧 string 输出。"""

import json
from copy import deepcopy
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase, override_settings

from services.web.bkbase import clean
from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.databus.collector_plugin.handlers import PluginEtlHandler
from tests.test_bkbase import test_pull_clean_rows as pull_fixtures

JSON_COLUMNS = (
    "instance_data",
    "instance_origin_data",
    "extend_data",
    "snapshot_user_info",
    "snapshot_resource_type_info",
    "snapshot_action_info",
    "__ext",
)


@override_settings(BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="tenant_a", BKBASE_V4_NAMESPACE="audit")
class CleanJsonCompatibilityTests(SimpleTestCase):
    def setUp(self):
        self.clean_ref = self.ref("Clean", "clean_a")
        self.data_ref = self.ref("DataId", "data_a")
        self.rt_ref = self.ref("ResultTable", "actual_output")
        self.owner = SimpleNamespace(
            pk=7,
            bkbase_processing_id="legacy_processing",
            bkbase_table_id="1_output",
            bkbase_v4_resources={
                "clean": self.clean_ref,
                "data_id": self.data_ref,
                "source_raw_data_id": 11,
                "clean_role": "owner",
                "result_table_id": "1_output",
                "result_table": self.rt_ref,
            },
        )
        handler = PluginEtlHandler.__new__(PluginEtlHandler)
        handler.bkbase_labels = []
        self.params = {
            "raw_data_id": 11,
            "bk_biz_id": 1,
            "result_table_name": "output",
            "result_table_name_alias": "Synthetic",
            "fields": handler.get_fields(),
            "json_config": json.loads(handler.get_clean_json_config()),
        }
        self.context = {"version": "v4", "tenant": "tenant_a", "namespace": "audit"}
        self.spec = clean.build_clean_spec(self.params, data_ref=self.data_ref, logical_id="1_output", rt_owner=True)
        self.remote = {
            "kind": "Clean",
            "metadata": {key: self.clean_ref[key] for key in ("tenant", "namespace", "name")},
            "spec": {
                **deepcopy(self.spec),
                "config_revision": 10,
                "deploy_revision": 10,
                "desired_status": "Running",
                "current_status": "Running",
            },
            "status": {"phase": "Ok"},
        }
        self.remote["spec"]["rules"][0]["operator"]["error_strategy"] = "null"
        self.sdk = mock.Mock()
        self.legacy = mock.Mock()
        self.enterContext(mock.patch.object(clean.api, "bk_base_v4", self.sdk))
        self.enterContext(mock.patch.object(clean.api, "bk_base", self.legacy))
        self.enterContext(mock.patch.object(clean, "resource_lock"))
        self.enterContext(mock.patch.object(clean, "update_owner_binding", side_effect=self.save_binding))
        self.enterContext(
            mock.patch("requests.sessions.Session.request", side_effect=AssertionError("Unexpected real HTTP"))
        )
        self.sdk.clean_get.return_value = self.remote
        self.sdk.result_table_info.return_value = {
            "metadata": {key: self.rt_ref[key] for key in ("tenant", "namespace", "name")},
            "spec": {"predefiendResultTableId": "1_output"},
        }
        self.sdk.clean_update.side_effect = self.accept
        self.sdk.clean_create.side_effect = self.accept

    @staticmethod
    def ref(kind, name):
        """合成同租户的显式资源引用。"""
        return {"kind": kind, "tenant": "tenant_a", "namespace": "audit", "name": name}

    @staticmethod
    def save_binding(owner, patch, *, remove=()):
        """在测试对象中隔离原本的 ORM 持久化边界。"""
        owner.bkbase_v4_resources.update(deepcopy(patch))
        for key in remove:
            owner.bkbase_v4_resources.pop(key, None)

    @staticmethod
    def accept(**payload):
        """仅表示接口受理，不模拟控制器运行或 RT schema 更新。"""
        return {"metadata": payload["metadata"], "spec": payload["spec"], "status": {"phase": "Pending"}}

    def maintain(self, **params):
        """通过原业务 Service 请求已绑定 owner 的维护。"""
        return clean.configure_clean(self.owner, {**self.params, **params}, rt_owner=True)

    def sent_assigns(self):
        """读取隔离 API 边界实际收到的声明。"""
        return {
            rule["output_id"]: rule["operator"]
            for rule in self.sdk.clean_update.call_args.kwargs["spec"]["rules"]
            if rule["operator"]["type"] == "assign"
        }

    def test_same_binding_text_columns_and_null_decode_do_not_republish(self):
        before = deepcopy(self.remote)
        result = self.maintain()
        self.assertEqual(result["task_state"], "running")
        self.sdk.clean_update.assert_not_called()
        self.sdk.clean_create.assert_not_called()
        self.assertEqual(self.remote, before)

    def test_null_decode_is_preserved_independently_of_output_column_types(self):
        before = deepcopy(self.remote)
        self.maintain(description="Changed description")
        sent = self.sdk.clean_update.call_args.kwargs["spec"]
        self.assertEqual(sent["rules"][0], before["spec"]["rules"][0])
        self.assertEqual(sent["description"], "Changed description")
        for name in JSON_COLUMNS:
            self.assertEqual(self.sent_assigns()[name]["output_type"], "text")
            self.assertNotIn("input_type", self.sent_assigns()[name])
        self.assertEqual(self.remote, before)

    def test_old_string_assignments_are_not_adopted(self):
        for rule in self.remote["spec"]["rules"]:
            if rule["output_id"] in JSON_COLUMNS:
                rule["operator"].update(input_type="text", output_type="string")
        self.maintain(description="Changed")
        for name in JSON_COLUMNS:
            self.assertEqual(self.sent_assigns()[name]["output_type"], "text")
            self.assertNotIn("input_type", self.sent_assigns()[name])
        self.assertEqual(
            self.sdk.clean_update.call_args.kwargs["spec"]["rules"][0]["operator"]["error_strategy"], "null"
        )

    def test_explicit_policy_changed_path_or_branch_is_not_overridden(self):
        for change in ("drop", "null", "explicit_none", "path", "branch", "output"):
            with self.subTest(change=change):
                self.sdk.clean_update.reset_mock()
                origins = set()
                spec = clean.build_clean_spec(
                    self.params,
                    data_ref=self.data_ref,
                    logical_id="1_output",
                    rt_owner=True,
                    _legacy_json_decoders=origins,
                )
                spec["description"] = "Changed"
                decoder = spec["rules"][0]
                if change in ("drop", "null", "explicit_none"):
                    decoder["operator"]["error_strategy"] = None if change == "explicit_none" else change
                elif change == "path":
                    decoder["input_id"] = "other_raw"
                elif change == "branch":
                    decoder["branch_id"] = "requested_branch"
                else:
                    decoder["output_id"] = "other_json"
                expected = deepcopy(decoder)
                clean.ensure_clean(
                    self.context,
                    self.owner,
                    rules=spec,
                    rt_ref=self.rt_ref,
                    _require_existing=True,
                    _legacy_json_decoders=origins,
                )
                self.assertEqual(self.sdk.clean_update.call_args.kwargs["spec"]["rules"][0], expected)
                self.assertEqual(spec["rules"][0], expected)

    def test_only_explicit_old_string_null_is_preserved(self):
        for policy in (None, "drop", "other", 0):
            with self.subTest(policy=policy):
                self.remote["spec"]["rules"][0]["operator"]["error_strategy"] = policy
                self.maintain(description="Changed")
                self.assertEqual(
                    self.sdk.clean_update.call_args.kwargs["spec"]["rules"][0]["operator"], {"type": "json_de"}
                )

    def test_duplicate_or_changed_old_decoder_is_not_adopted(self):
        for change in ("duplicate", "path", "branch", "extra_operator_setting"):
            with self.subTest(change=change):
                old = deepcopy(self.remote)
                decoder = self.remote["spec"]["rules"][0]
                if change == "duplicate":
                    self.remote["spec"]["rules"].append(deepcopy(decoder))
                elif change == "path":
                    decoder["input_id"] = "other_raw"
                elif change == "branch":
                    decoder["branch_id"] = "old_branch"
                else:
                    decoder["operator"]["custom"] = True
                self.maintain(description="Changed")
                self.assertNotIn(
                    "error_strategy", self.sdk.clean_update.call_args.kwargs["spec"]["rules"][0]["operator"]
                )
                self.remote.clear()
                self.remote.update(old)

    def test_arbitrary_v4_rules_without_conversion_provenance_are_unchanged(self):
        clean.ensure_clean(self.context, self.owner, rules=self.spec, rt_ref=self.rt_ref, _require_existing=True)
        self.assertNotIn("error_strategy", self.sdk.clean_update.call_args.kwargs["spec"]["rules"][0]["operator"])

    def test_new_owner_keeps_generator_defaults(self):
        self.owner.bkbase_processing_id = None
        self.owner.bkbase_v4_resources = {"data_id": self.data_ref, "source_raw_data_id": 11}
        self.sdk.clean_get.return_value = None
        self.maintain()
        spec = self.sdk.clean_create.call_args.kwargs["spec"]
        self.assertEqual(spec["rules"][0]["operator"], {"type": "json_de"})
        for rule in spec["rules"]:
            if rule["output_id"] in JSON_COLUMNS:
                self.assertEqual(rule["operator"]["output_type"], "text")
                self.assertNotIn("input_type", rule["operator"])
        self.sdk.clean_update.assert_not_called()

    def test_mismatched_source_or_rt_binding_is_rejected_before_write(self):
        for change in ("raw", "data", "role", "logical", "rt"):
            with self.subTest(change=change):
                remote, binding = deepcopy(self.remote), deepcopy(self.owner.bkbase_v4_resources)
                if change == "raw":
                    self.remote["spec"]["raw_data_id"] = 12
                elif change == "data":
                    self.remote["spec"]["data_id"] = self.ref("DataId", "other_data")
                elif change == "role":
                    self.remote["spec"]["result_table_source"] = "existing"
                elif change == "logical":
                    self.remote["spec"]["result_table_id"] = "1_other"
                else:
                    self.owner.bkbase_v4_resources["result_table"] = self.ref("ResultTable", "other_rt")
                with self.assertRaises(BKBaseResourceMappingError):
                    self.maintain()
                self.sdk.clean_update.assert_not_called()
                self.sdk.clean_create.assert_not_called()
                self.remote.clear()
                self.remote.update(remote)
                self.owner.bkbase_v4_resources = binding

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_keeps_legacy_payload_and_update_stop_start(self):
        params = deepcopy(self.params)
        result = self.maintain()
        self.legacy.databus_cleans_put.assert_called_once_with(**params, processing_id="legacy_processing")
        self.assertEqual(self.legacy.databus_tasks_delete.call_args.kwargs["processing_id"], "legacy_processing")
        self.assertEqual(self.legacy.databus_tasks_post.call_args.kwargs["result_table_id"], "1_output")
        self.assertEqual(result, {"result_table_id": "1_output", "processing_id": "legacy_processing"})
        self.sdk.clean_get.assert_not_called()
        self.assertEqual(self.params, params)

    def test_platform_text_to_text_readback_preserves_null_without_importing_assignments(self):
        for rule in self.remote["spec"]["rules"]:
            if rule["output_id"] in JSON_COLUMNS:
                rule["operator"].update(
                    input_type="text",
                    output_type="text",
                    is_time_field=False,
                    fixed_value=None,
                    time_format=None,
                    time_fallback=None,
                    in_place_time_parsing=None,
                    desc=None,
                )
        self.maintain(description="Changed")
        spec = self.sdk.clean_update.call_args.kwargs["spec"]
        self.assertEqual(spec["rules"][0]["operator"], {"type": "json_de", "error_strategy": "null"})
        for name in JSON_COLUMNS:
            self.assertEqual(self.sent_assigns()[name]["output_type"], "text")
            self.assertNotIn("input_type", self.sent_assigns()[name])

    def test_duplicate_new_decoder_is_not_adopted(self):
        params = deepcopy(self.params)
        decoder = params["json_config"]["extract"]
        original_next = decoder.pop("next")
        repeated = deepcopy(decoder)
        params["json_config"]["extract"] = [decoder, repeated, original_next]
        self.maintain(**params, description="Changed")
        spec = self.sdk.clean_update.call_args.kwargs["spec"]
        for rule in spec["rules"]:
            if rule["operator"]["type"] == "json_de":
                self.assertNotIn("error_strategy", rule["operator"])

    def test_failed_established_update_retry_preserves_null_without_creation_marker(self):
        self.sdk.clean_update.side_effect = RuntimeError("update not accepted")
        with self.assertRaises(RuntimeError):
            self.maintain(description="Changed")
        first = deepcopy(self.sdk.clean_update.call_args.kwargs["spec"])
        self.assertEqual(first["rules"][0]["operator"]["error_strategy"], "null")
        self.sdk.clean_update.side_effect = self.accept
        self.maintain(description="Changed")
        self.assertEqual(
            self.sdk.clean_update.call_args.kwargs["spec"]["rules"][0]["operator"],
            {"type": "json_de", "error_strategy": "null"},
        )
        self.assertNotIn("clean_pending_create", self.owner.bkbase_v4_resources)
        self.sdk.clean_create.assert_not_called()

    def test_accepted_update_with_lost_response_retry_is_idempotent_and_keeps_null(self):
        def accepted_but_response_lost(**payload):
            self.remote["spec"] = deepcopy(payload["spec"])
            raise RuntimeError("response lost after update acceptance")

        self.sdk.clean_update.side_effect = accepted_but_response_lost
        with self.assertRaises(RuntimeError):
            self.maintain(description="Changed")
        self.assertEqual(self.remote["spec"]["rules"][0]["operator"]["error_strategy"], "null")
        self.sdk.clean_update.side_effect = self.accept
        self.maintain(description="Changed")
        self.assertEqual(self.sdk.clean_update.call_count, 1)
        self.assertEqual(self.remote["spec"]["rules"][0]["operator"]["error_strategy"], "null")
        self.assertNotIn("clean_pending_create", self.owner.bkbase_v4_resources)
        self.sdk.clean_create.assert_not_called()

    def test_failed_established_update_does_not_allow_recreation_if_remote_disappears(self):
        self.sdk.clean_update.side_effect = RuntimeError("update failed")
        with self.assertRaises(RuntimeError):
            self.maintain(description="Changed")
        self.sdk.clean_get.return_value = None
        with self.assertRaises(BKBaseResourceMappingError):
            self.maintain(description="Changed")
        self.sdk.clean_create.assert_not_called()

    def test_uncertain_first_create_is_not_treated_as_established_null_policy(self):
        self.owner.bkbase_processing_id = None
        self.owner.bkbase_v4_resources = {"data_id": self.data_ref, "source_raw_data_id": 11}
        self.sdk.clean_get.return_value = None

        def lost_create(**payload):
            remote = self.accept(**payload)
            remote["kind"] = "Clean"
            remote["spec"]["rules"][0]["operator"]["error_strategy"] = "null"
            self.sdk.clean_get.return_value = remote
            raise RuntimeError("first creation response lost")

        self.sdk.clean_create.side_effect = lost_create
        with self.assertRaises(RuntimeError):
            self.maintain()
        self.assertTrue(self.owner.bkbase_v4_resources["clean_pending_create"])
        self.maintain()
        sent = self.sdk.clean_update.call_args.kwargs["spec"]
        self.assertEqual(sent["rules"][0]["operator"], {"type": "json_de"})
        self.assertNotIn("clean_pending_create", self.owner.bkbase_v4_resources)
        self.assertEqual(self.sdk.clean_create.call_count, 1)

    def prepare_full_response_pull(self):
        """采用已支持的普通PULL模板，而非直接编写V4规则。"""
        config, fields = pull_fixtures.PullCleanRowsTests.template("action", {"data_path": None})
        self.params.update(json_config=config, fields=fields)
        provenance = set()
        spec = clean.build_clean_spec(
            self.params, data_ref=self.data_ref, logical_id="1_output", rt_owner=True, _legacy_json_decoders=provenance
        )
        self.remote["spec"].update(deepcopy(spec))
        decoders = [r for r in self.remote["spec"]["rules"] if r["operator"]["type"] == "json_de"]
        self.assertEqual(len(decoders), 2)
        for decoder in decoders:
            decoder["operator"]["error_strategy"] = "null"
        return spec, provenance, decoders[1]["output_id"]

    def test_supported_pull_preserves_both_same_path_json_decoder_null_policies(self):
        self.prepare_full_response_pull()
        self.maintain(description="Changed")
        decoders = [
            r for r in self.sdk.clean_update.call_args.kwargs["spec"]["rules"] if r["operator"]["type"] == "json_de"
        ]
        self.assertEqual([r["operator"].get("error_strategy") for r in decoders], ["null", "null"])

    def test_nested_decoder_requires_complete_unique_unchanged_ancestor_chain(self):
        spec, provenance, inner_id = self.prepare_full_response_pull()
        original_remote = deepcopy(self.remote)
        for change in (
            "key",
            "index",
            "default",
            "branch",
            "duplicate_old",
            "duplicate_new",
            "cycle",
            "missing_old",
            "explicit_root_drop",
        ):
            with self.subTest(change=change):
                self.remote.clear()
                self.remote.update(deepcopy(original_remote))
                wanted = deepcopy(spec)
                wanted["description"] = "Changed"
                inner = next(r for r in wanted["rules"] if r["output_id"] == inner_id)
                producer = next(r for r in wanted["rules"] if r["output_id"] == inner["input_id"])
                old_producer = next(r for r in self.remote["spec"]["rules"] if r["output_id"] == inner["input_id"])
                self.assertEqual(producer["operator"]["type"], "get")
                if change == "key":
                    producer["operator"]["key_index"][0]["value"] = "other_key"
                elif change == "index":
                    producer["operator"]["key_index"] = [{"type": "index", "value": 0}]
                elif change == "default":
                    producer["operator"]["default"] = "other_default"
                elif change == "branch":
                    producer["branch_id"] = "other_branch"
                elif change == "duplicate_old":
                    self.remote["spec"]["rules"].append(deepcopy(old_producer))
                elif change == "duplicate_new":
                    wanted["rules"].append(deepcopy(producer))
                elif change == "cycle":
                    producer["input_id"] = old_producer["input_id"] = inner_id
                elif change == "missing_old":
                    self.remote["spec"]["rules"].remove(old_producer)
                else:
                    wanted["rules"][0]["operator"]["error_strategy"] = "drop"
                clean.ensure_clean(
                    self.context,
                    self.owner,
                    rules=wanted,
                    rt_ref=self.rt_ref,
                    _require_existing=True,
                    _legacy_json_decoders=provenance,
                )
                sent = self.sdk.clean_update.call_args.kwargs["spec"]
                sent_inner = next(r for r in sent["rules"] if r["output_id"] == inner_id)
                self.assertNotIn("error_strategy", sent_inner["operator"])
                self.assertEqual(next(r for r in sent["rules"] if r["output_id"] == producer["output_id"]), producer)

    def test_nested_explicit_policy_and_custom_v4_rules_are_not_overridden(self):
        spec, provenance, inner_id = self.prepare_full_response_pull()
        for policy in ("drop", "null", None):
            with self.subTest(policy=policy):
                wanted = deepcopy(spec)
                wanted["description"] = "Changed"
                inner = next(r for r in wanted["rules"] if r["output_id"] == inner_id)
                inner["operator"]["error_strategy"] = policy
                clean.ensure_clean(
                    self.context,
                    self.owner,
                    rules=wanted,
                    rt_ref=self.rt_ref,
                    _require_existing=True,
                    _legacy_json_decoders=provenance,
                )
                actual = next(
                    r for r in self.sdk.clean_update.call_args.kwargs["spec"]["rules"] if r["output_id"] == inner_id
                )
                self.assertEqual(actual, inner)
        clean.ensure_clean(
            self.context,
            self.owner,
            rules={**spec, "description": "Changed"},
            rt_ref=self.rt_ref,
            _require_existing=True,
        )
        for rule in self.sdk.clean_update.call_args.kwargs["spec"]["rules"]:
            if rule["operator"]["type"] == "json_de":
                self.assertNotIn("error_strategy", rule["operator"])

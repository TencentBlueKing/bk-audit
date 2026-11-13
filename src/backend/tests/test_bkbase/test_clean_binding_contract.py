"""验证普通清洗发布复用资源时的输入身份与共享表角色。

保留真实 Service 调用链，只模拟持久化及上游传输边界。
错误绑定不得覆盖远端配置，也不得污染本地清洗生命周期记录。
"""

from copy import deepcopy
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase, override_settings

from services.web.bkbase import clean
from services.web.bkbase.constants import CleanRole
from services.web.bkbase.exceptions import BKBaseResourceMappingError


@override_settings(BKBASE_API_VERSION="v4")
class CleanBindingContractTests(SimpleTestCase):
    def setUp(self):
        self.context = {"version": "v4", "tenant": "tenant_a", "namespace": "audit"}
        self.clean_ref = self.ref("Clean", "clean_a")
        self.data_ref = self.ref("DataId", "data_a")
        self.rt_ref = self.ref("ResultTable", "actual_output")
        self.rules = {
            "data_id": self.data_ref,
            "raw_data_id": 11,
            "result_table_source": "existing",
            "result_table_id": "1_output",
            "rules": [],
        }
        self.owner = SimpleNamespace(
            pk=1,
            processing_id="legacy_processing",
            bkbase_table_id="legacy_table",
            collector_plugin_id=7,
            bkbase_v4_resources={
                "data_id": self.data_ref,
                "clean": self.clean_ref,
                "clean_role": CleanRole.EXISTING,
                "result_table": self.rt_ref,
            },
        )
        self.remote = {
            "kind": "Clean",
            "metadata": {key: self.clean_ref[key] for key in ("tenant", "namespace", "name")},
            "spec": {
                **deepcopy(self.rules),
                "config_revision": 10,
                "deploy_revision": 9,
                "desired_status": "Stopped",
                "current_status": "Stopped",
                "consumer_group": "retained_group",
            },
            "status": {"phase": "Ok"},
        }
        self.enterContext(
            mock.patch("requests.sessions.Session.request", side_effect=AssertionError("Unexpected HTTP"))
        )
        self.enterContext(mock.patch.object(clean, "resource_lock"))
        self.fetch = self.enterContext(mock.patch.object(clean, "get_resource_or_none", return_value=self.remote))
        self.save = self.enterContext(mock.patch.object(clean, "update_owner_binding", side_effect=self.save_binding))
        self.create = self.enterContext(mock.patch.object(clean.api.bk_base_v4, "clean_create"))
        self.update = self.enterContext(
            mock.patch.object(
                clean.api.bk_base_v4,
                "clean_update",
                side_effect=lambda **payload: {
                    "metadata": payload["metadata"],
                    "spec": payload["spec"],
                    "status": {"phase": "Pending"},
                },
            )
        )

    def ref(self, kind, name):
        return {"kind": kind, "tenant": "tenant_a", "namespace": "audit", "name": name}

    def save_binding(self, owner, patch, *, remove=()):
        owner.bkbase_v4_resources.update(deepcopy(patch))
        for key in remove:
            owner.bkbase_v4_resources.pop(key, None)

    def ready_rules_with_server_defaults(self):
        self.rules["rules"] = [
            {"input_id": "input", "output_id": "decoded", "operator": {"type": "json_de"}},
            {"input_id": "decoded", "output_id": "event", "operator": {"type": "assign", "key_index": "event"}},
        ]
        self.remote["spec"].update(
            **deepcopy(self.rules), deploy_revision=10, desired_status="Running", current_status="Running"
        )
        self.remote["spec"]["rules"][0]["operator"]["error_strategy"] = "drop"
        self.remote["spec"]["rules"][1]["operator"].update(
            time_fallback=None,
            fixed_value=None,
            time_format=None,
            desc=None,
            in_place_time_parsing=None,
            input_type=None,
            is_time_field=None,
        )

    def test_server_default_rule_fields_do_not_republish_unchanged_clean(self):
        self.ready_rules_with_server_defaults()
        original, desired = deepcopy(self.remote), deepcopy(self.rules)
        result = clean.ensure_clean(self.context, self.owner, rules=self.rules, rt_ref=self.rt_ref)
        self.update.assert_not_called()
        self.assertEqual(result["task_state"], "running")
        self.assertEqual(self.remote, original)
        self.assertEqual(self.rules, desired)

    def test_iter_false_matches_only_the_documented_missing_response_key(self):
        wanted = [
            {
                "input_id": "items",
                "output_id": "row",
                "operator": {
                    "type": "iter",
                    "reserve_index": False,
                    "iteration_index_field": "_iteration_idx",
                },
            }
        ]
        actual = [
            {
                "input_id": "items",
                "output_id": "row",
                "operator": {
                    "type": "iter",
                    "iteration_index_field": "_iteration_idx",
                },
            }
        ]
        original = deepcopy((wanted, actual))
        self.assertTrue(clean._same_clean_rules(wanted, actual))
        self.assertEqual((wanted, actual), original)
        self.assertFalse(clean._same_clean_rules(actual, wanted))
        for value in (True, None, 0, "false"):
            with self.subTest(value=value):
                changed = deepcopy(wanted)
                changed[0]["operator"]["reserve_index"] = value
                self.assertFalse(clean._same_clean_rules(changed, actual))
        for section, key, value in (
            ("operator", "iteration_index_field", "other"),
            (None, "input_id", "other"),
            (None, "output_id", "other"),
        ):
            changed = deepcopy(actual)
            (changed[0][section] if section else changed[0])[key] = value
            self.assertFalse(clean._same_clean_rules(wanted, changed))
        different_kind_wanted, different_kind_actual = deepcopy(wanted), deepcopy(actual)
        different_kind_wanted[0]["operator"]["type"] = "assign"
        different_kind_actual[0]["operator"]["type"] = "assign"
        self.assertFalse(clean._same_clean_rules(different_kind_wanted, different_kind_actual))

    def test_iter_default_comparison_does_not_publish_or_change_the_declared_rules(self):
        self.ready_rules_with_server_defaults()
        self.rules["rules"].append(
            {
                "input_id": "decoded",
                "output_id": "row",
                "operator": {
                    "type": "iter",
                    "reserve_index": False,
                    "iteration_index_field": "_iteration_idx",
                },
            }
        )
        self.remote["spec"]["rules"].append(
            {
                "input_id": "decoded",
                "output_id": "row",
                "operator": {
                    "type": "iter",
                    "iteration_index_field": "_iteration_idx",
                },
            }
        )
        original = deepcopy(self.rules)
        result = clean.ensure_clean(self.context, self.owner, rules=self.rules, rt_ref=self.rt_ref)
        self.assertEqual(result["task_state"], "running")
        self.update.assert_not_called()
        self.assertEqual(self.rules, original)
        self.remote["spec"]["desired_status"] = "Stopped"
        clean.ensure_clean(self.context, self.owner, rules=self.rules, rt_ref=self.rt_ref)
        self.assertEqual(self.update.call_args.kwargs["spec"]["rules"], original["rules"])
        self.assertIs(self.update.call_args.kwargs["spec"]["rules"][-1]["operator"]["reserve_index"], False)

    def test_iter_reserve_index_does_not_equate_boolean_and_numeric_values_in_either_direction(self):
        for boolean, number in ((False, 0), (True, 1), (False, 0.0), (True, 1.0)):
            for wanted_value, observed_value in ((boolean, number), (number, boolean)):
                with self.subTest(wanted=wanted_value, observed=observed_value):
                    wanted = [
                        {
                            "input_id": "items",
                            "output_id": "row",
                            "operator": {
                                "type": "iter",
                                "reserve_index": wanted_value,
                            },
                        }
                    ]
                    actual = deepcopy(wanted)
                    actual[0]["operator"]["reserve_index"] = observed_value
                    self.assertFalse(clean._same_clean_rules(wanted, actual))
            same = [
                {
                    "input_id": "items",
                    "output_id": "row",
                    "operator": {
                        "type": "iter",
                        "reserve_index": boolean,
                    },
                }
            ]
            self.assertTrue(clean._same_clean_rules(same, deepcopy(same)))

    def test_nondefault_or_unknown_operator_fields_remain_changes(self):
        for field, value in (
            ("desc", "description"),
            ("input_type", "string"),
            ("is_time_field", False),
            ("fixed_value", ""),
            ("unknown", None),
            ("default_value", None),
        ):
            with self.subTest(field=field):
                self.ready_rules_with_server_defaults()
                self.update.reset_mock()
                self.remote["spec"]["rules"][1]["operator"][field] = value
                clean.ensure_clean(self.context, self.owner, rules=self.rules, rt_ref=self.rt_ref)
                self.update.assert_called_once()

    def test_explicit_null_and_missing_default_value_are_distinct(self):
        self.ready_rules_with_server_defaults()
        self.rules["rules"][1]["operator"]["default_value"] = None
        clean.ensure_clean(self.context, self.owner, rules=self.rules, rt_ref=self.rt_ref)
        self.update.assert_called_once()
        self.assertIsNone(self.update.call_args.kwargs["spec"]["rules"][1]["operator"]["default_value"])

    def test_rule_order_and_input_output_changes_still_publish_original_body(self):
        for change in ("order", "input_id", "output_id", "json_default", "explicit_json_null"):
            with self.subTest(change=change):
                self.ready_rules_with_server_defaults()
                self.update.reset_mock()
                if change == "order":
                    self.rules["rules"].reverse()
                elif change == "json_default":
                    self.remote["spec"]["rules"][0]["operator"]["error_strategy"] = None
                elif change == "explicit_json_null":
                    self.rules["rules"][0]["operator"]["error_strategy"] = None
                else:
                    self.remote["spec"]["rules"][1][change] = "changed"
                original_rules = deepcopy(self.rules["rules"])
                clean.ensure_clean(self.context, self.owner, rules=self.rules, rt_ref=self.rt_ref)
                self.update.assert_called_once()
                self.assertEqual(self.update.call_args.kwargs["spec"]["rules"], original_rules)

    def test_rule_equivalence_does_not_bypass_publish_or_other_spec_changes(self):
        for change in ("draft", "stopped", "alias"):
            with self.subTest(change=change):
                self.ready_rules_with_server_defaults()
                self.update.reset_mock()
                if change == "draft":
                    self.remote["spec"]["deploy_revision"] = 9
                elif change == "stopped":
                    self.remote["spec"]["desired_status"] = "Stopped"
                else:
                    self.rules["alias"] = "new alias"
                clean.ensure_clean(self.context, self.owner, rules=self.rules, rt_ref=self.rt_ref)
                self.update.assert_called_once()

    def test_invalid_data_id_reference_is_rejected_before_binding_or_upstream_access(self):
        for patch in ({"kind": "DataSource"}, {"tenant": "tenant_b"}, {"namespace": ""}, {"name": ""}):
            with self.subTest(patch=patch):
                rules = {**self.rules, "data_id": {**self.data_ref, **patch}}
                before = deepcopy(self.owner.bkbase_v4_resources)
                with self.assertRaises(BKBaseResourceMappingError):
                    clean.ensure_clean(self.context, self.owner, rules=rules, rt_ref=self.rt_ref)
                self.assertEqual(self.owner.bkbase_v4_resources, before)
                self.fetch.assert_not_called()
                self.save.assert_not_called()
                self.create.assert_not_called()
                self.update.assert_not_called()

    def test_remote_identity_mismatch_cannot_be_adopted_or_published(self):
        for patch in (
            {"data_id": self.ref("DataId", "other_data")},
            {"raw_data_id": 12},
            {"result_table_id": "1_other_output"},
            {"result_table_source": "new"},
        ):
            with self.subTest(patch=patch):
                self.remote["spec"] = {**deepcopy(self.rules), **patch}
                before = deepcopy(self.owner.bkbase_v4_resources)
                with self.assertRaises(BKBaseResourceMappingError):
                    clean.ensure_clean(self.context, self.owner, rules=self.rules, rt_ref=self.rt_ref)
                self.assertEqual(self.owner.bkbase_v4_resources, before)
                self.save.assert_not_called()
                self.create.assert_not_called()
                self.update.assert_not_called()

    def test_omitted_remote_role_means_new_and_cannot_be_adopted_as_existing(self):
        self.remote["spec"].pop("result_table_source")
        with self.assertRaises(BKBaseResourceMappingError):
            clean.ensure_clean(self.context, self.owner, rules=self.rules, rt_ref=self.rt_ref)
        self.save.assert_not_called()
        self.update.assert_not_called()

    def test_ordinary_collector_publish_preserves_identity_old_ids_and_remote_options(self):
        before = deepcopy(self.remote)
        with mock.patch.object(clean, "get_bkbase_context", return_value=self.context), mock.patch.object(
            clean.CollectorPlugin.objects,
            "get",
            return_value=SimpleNamespace(),
        ), mock.patch.object(clean, "_shared_plugin_table", return_value=("1_output", self.rt_ref)):
            result = clean.configure_clean(
                self.owner,
                {"raw_data_id": 11, "clean_config_name": "source", "json_config": {"extract": None}},
                rt_owner=False,
            )
        self.create.assert_not_called()
        self.update.assert_called_once()
        spec = self.update.call_args.kwargs["spec"]
        for key in ("data_id", "raw_data_id", "result_table_id", "result_table_source", "consumer_group"):
            self.assertEqual(spec[key], before["spec"][key])
        self.assertGreater(spec["config_revision"], 10)
        self.assertEqual(spec["deploy_revision"], spec["config_revision"])
        self.assertEqual(spec["desired_status"], "Running")
        self.assertIsNone(result["task_state"])
        self.assertFalse(self.owner.bkbase_v4_resources["clean_ready"])
        self.assertEqual((self.owner.processing_id, self.owner.bkbase_table_id), ("legacy_processing", "legacy_table"))
        self.assertEqual(self.remote, before)

    def test_creator_can_publish_existing_default_new_role(self):
        self.owner.bkbase_v4_resources["clean_role"] = CleanRole.OWNER
        self.remote["spec"].pop("result_table_source")
        rules = {**self.rules, "result_table_source": "new"}
        result = clean.ensure_clean(self.context, self.owner, rules=rules, rt_ref=self.rt_ref)
        self.assertTrue(result["accepted"])
        self.assertEqual(self.update.call_args.kwargs["spec"]["result_table_source"], "new")
        self.assertEqual(self.owner.bkbase_v4_resources["clean_role"], CleanRole.OWNER)

    def test_save_keeps_deployed_revision_and_stopped_intent(self):
        result = clean.ensure_clean(
            self.context, self.owner, rules={**self.rules, "alias": "saved"}, rt_ref=self.rt_ref, publish=False
        )
        spec = self.update.call_args.kwargs["spec"]
        self.assertGreater(spec["config_revision"], 10)
        self.assertEqual(spec["deploy_revision"], 9)
        self.assertEqual(spec["desired_status"], "Stopped")
        self.assertIsNone(result["task_state"])

    def test_uncertain_create_keeps_binding_and_retry_reuses_compatible_clean(self):
        self.fetch.return_value = None
        self.create.side_effect = RuntimeError("response lost after remote acceptance")
        with self.assertRaises(RuntimeError):
            clean.ensure_clean(self.context, self.owner, rules=self.rules, rt_ref=self.rt_ref)
        self.assertEqual(self.owner.bkbase_v4_resources["clean"], self.clean_ref)
        self.assertTrue(self.owner.bkbase_v4_resources["clean_pending_create"])
        self.fetch.return_value = self.remote
        result = clean.ensure_clean(self.context, self.owner, rules=self.rules, rt_ref=self.rt_ref)
        self.create.assert_called_once()
        self.update.assert_called_once()
        self.assertTrue(result["accepted"])
        self.assertNotIn("clean_pending_create", self.owner.bkbase_v4_resources)

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_keeps_legacy_update_stop_and_start_sequence(self):
        with mock.patch.object(clean.api.bk_base, "databus_cleans_put") as update, mock.patch.object(
            clean.api.bk_base, "databus_tasks_delete"
        ) as stop, mock.patch.object(clean.api.bk_base, "databus_tasks_post") as start:
            result = clean.configure_clean(self.owner, {"raw_data_id": 11})
        update.assert_called_once_with(raw_data_id=11, processing_id="legacy_processing")
        self.assertEqual(stop.call_args.kwargs["processing_id"], "legacy_processing")
        self.assertEqual(start.call_args.kwargs["result_table_id"], "legacy_table")
        self.assertEqual(result, {"result_table_id": "legacy_table", "processing_id": "legacy_processing"})
        self.fetch.assert_not_called()
        self.save.assert_not_called()

"""已确认的Clean算子回显不能终止新快照，未知语义仍严格拒绝。"""
import json
from copy import deepcopy

import requests
from django.conf import settings
from django.test import SimpleTestCase, TransactionTestCase, override_settings

from apps.meta.constants import ConfigLevelChoices
from apps.meta.models import GlobalMetaConfig
from services.web.bkbase import snapshot_clean_provision as provision
from services.web.bkbase import source
from services.web.bkbase.constants import BKBASE_V4_STORAGE_CLUSTER_MAP
from services.web.databus import tasks
from services.web.databus.constants import (
    DEFAULT_REPLICA_WRITE_STORAGE_CONFIG_KEY,
    SnapshotRunningStatus,
)
from tests.test_bkbase.test_snapshot_clean_provision import (
    SnapshotCleanProvisionFixture,
)


class CleanTargetComparisonTests(SimpleTestCase):
    def target(self, operator):
        spec = {"raw_data_id": 71, "rules": [{"input_id": "a", "output_id": "b", "operator": operator}]}
        return {"target_spec": spec, "target_keys": sorted(spec), "target_digest": source._replay_digest(spec)}

    def test_reserve_true_omission_and_nonboolean_values_are_not_false_default(self):
        for declared, actual in ((True, None), (True, False), (False, 0), (True, 1)):
            with self.subTest(declared=declared, actual=actual):
                step = self.target({"type": "iter", "reserve_index": declared})
                observed = deepcopy(step["target_spec"])
                if actual is None:
                    observed["rules"][0]["operator"].pop("reserve_index")
                else:
                    observed["rules"][0]["operator"]["reserve_index"] = actual
                self.assertFalse(provision._matches_clean_target(step, observed))

    def test_unknown_operator_fields_and_explicit_values_remain_strict(self):
        step = self.target({"type": "assign", "key_index": "id", "desc": "declared"})
        for patch in ({"future_option": None}, {"desc": None}, {"key_index": "another"}):
            with self.subTest(patch=patch):
                observed = deepcopy(step["target_spec"])
                observed["rules"][0]["operator"].update(patch)
                self.assertFalse(provision._matches_clean_target(step, observed))

    def test_non_rule_fields_are_compared_exactly(self):
        step = self.target({"type": "assign", "key_index": "id"})
        observed = deepcopy(step["target_spec"])
        observed["raw_data_id"] = "71"
        self.assertFalse(provision._matches_clean_target(step, observed))

    def test_explicit_assign_scalars_remain_type_sensitive_after_default_normalization(self):
        for field, wanted, returned in (
            ("is_dimension", False, 0),
            ("is_time_field", True, 1),
            ("fixed_value", False, 0.0),
            ("fixed_value", 1, 1.0),
        ):
            for declared, actual in ((wanted, returned), (returned, wanted)):
                with self.subTest(field=field, declared=declared, actual=actual):
                    step = self.target({"type": "assign", field: declared})
                    observed = deepcopy(step["target_spec"])
                    observed["rules"][0]["operator"].update({field: actual, "desc": None})
                    self.assertFalse(provision._matches_clean_target(step, observed))

    def test_nested_default_json_values_are_type_sensitive(self):
        for declared, actual in ((False, 0), (True, 1), (0, 0.0), (None, False)):
            with self.subTest(declared=declared, actual=actual):
                step = self.target({"type": "get", "default": {"rows": [{"value": declared}]}})
                observed = deepcopy(step["target_spec"])
                observed["rules"][0]["operator"]["default"]["rows"][0]["value"] = actual
                self.assertFalse(provision._matches_clean_target(step, observed))

    def test_normalized_defaults_preserve_explicit_types_rule_order_and_inputs(self):
        step = self.target({"type": "assign", "is_dimension": False, "fixed_value": {"a": [True, 1]}})
        step["target_spec"]["rules"].append(
            {"input_id": "b", "output_id": "c", "operator": {"type": "iter", "reserve_index": False}}
        )
        step["target_digest"] = source._replay_digest(step["target_spec"])
        observed = deepcopy(step["target_spec"])
        observed["rules"][0]["operator"].update(desc=None, input_type=None)
        observed["rules"][1]["operator"].pop("reserve_index")
        original = deepcopy((step, observed))
        self.assertTrue(provision._matches_clean_target(step, observed))
        self.assertEqual((step, observed), original)
        observed["rules"].reverse()
        self.assertFalse(provision._matches_clean_target(step, observed))

    def test_old_claim_without_declared_copy_keeps_exact_hash_and_is_not_redeclared(self):
        step = self.target({"type": "iter", "reserve_index": False})
        observed = step.pop("target_spec")
        self.assertTrue(provision._matches_clean_target(step, observed))
        echoed = deepcopy(observed)
        echoed["rules"][0]["operator"].pop("reserve_index")
        self.assertFalse(provision._matches_clean_target(step, echoed))


@override_settings(
    BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="default", BKBASE_V4_NAMESPACE="project_a", HIGH_RISK_PORTS=[]
)
class SnapshotCleanRuleEchoTests(SnapshotCleanProvisionFixture, TransactionTestCase):
    def setUp(self):
        SnapshotCleanProvisionFixture.setUp(self)
        cluster = {"kind": "Doris", "tenant": "default", "namespace": "clusters", "name": "doris_a"}
        GlobalMetaConfig.set(
            BKBASE_V4_STORAGE_CLUSTER_MAP,
            {"doris": {"legacy_doris": cluster}},
            config_level=ConfigLevelChoices.NAMESPACE.value,
            instance_key="audit",
        )
        GlobalMetaConfig.set(
            DEFAULT_REPLICA_WRITE_STORAGE_CONFIG_KEY,
            {"bkbase_cluster_id": "legacy_doris"},
            config_level=ConfigLevelChoices.NAMESPACE.value,
            instance_key=settings.DEFAULT_NAMESPACE,
        )

    def transport(self, method, url, **kwargs):
        if method == "POST" and "/datastorages/" in url:
            payload = deepcopy(kwargs["json"])
            self.requests.append((method, url, payload))
            value = self.remote(payload["metadata"], "DataStorage", payload["spec"], phase="Pending")
            self.resources[value["metadata"]["name"]] = value
            response = requests.Response()
            response.status_code = 200
            response.url = url
            response.request = requests.Request(method, url).prepare()
            response._content = json.dumps({"result": True, "code": "00", "data": value}).encode()
            return response
        response = SnapshotCleanProvisionFixture.transport(self, method, url, **kwargs)
        if method == "GET" and "/v4/result_tables/" in url:
            value = response.json()["data"]
            value["kind"] = "ResultTable"
            value["status"]["phase"] = "Ok"
            self.resources[value["metadata"]["name"]] = value
        return response

    def declare(self):
        self.start()
        tasks.start_snapshot.run()
        (post,) = self.clean_posts()
        return post, self.resources[post["metadata"]["name"]]

    def echo(self, rules):
        for rule in rules:
            operator = rule.get("operator", {})
            if operator.get("type") == "json_de":
                operator.setdefault("error_strategy", "drop")
            elif operator.get("type") == "assign":
                for key in (
                    "desc",
                    "fixed_value",
                    "input_type",
                    "is_time_field",
                    "time_format",
                    "time_fallback",
                    "in_place_time_parsing",
                ):
                    operator.setdefault(key, None)
            elif operator.get("type") == "iter" and operator.get("reserve_index") is False:
                operator.pop("reserve_index")

    def test_pending_known_operator_echo_waits_without_failure_or_duplicate_create(self):
        post, remote = self.declare()
        self.echo(remote["spec"]["rules"])
        tasks.start_snapshot.run()
        snapshot = self.snapshot()
        self.assertEqual(snapshot.status, SnapshotRunningStatus.PREPARING, snapshot.status_msg)
        self.assertFalse(snapshot.bkbase_v4_resources.get("clean_ready"))
        self.assertEqual(snapshot.bkbase_v4_resources["source_provision"]["clean_step"]["target_spec"], post["spec"])
        self.assertEqual(len(self.clean_posts()), 1)
        self.assert_no_storage_or_source_update()

    def test_running_echo_confirms_clean_and_passes_the_storage_precheck(self):
        post, remote = self.declare()
        self.echo(remote["spec"]["rules"])
        remote["status"]["phase"] = "Ok"
        remote["spec"]["current_status"] = "Running"
        tasks.start_snapshot.run()
        snapshot = self.snapshot()
        self.assertEqual(snapshot.status, SnapshotRunningStatus.PREPARING, snapshot.status_msg)
        self.assertTrue(snapshot.bkbase_v4_resources["clean_ready"])
        self.assertEqual(snapshot.bkbase_table_id, post["spec"]["result_table_id"])
        tasks.start_snapshot.run()
        stores = [payload for method, url, payload in self.requests if method == "POST" and "/datastorages/" in url]
        self.assertEqual(len(stores), 1, self.snapshot().status_msg)
        self.assertEqual(stores[0]["spec"]["tableInfo"]["source"], snapshot.bkbase_v4_resources["result_table"])
        self.assertEqual(self.snapshot().status, SnapshotRunningStatus.PREPARING, self.snapshot().status_msg)
        self.assertFalse(any(method == "PUT" and "/datasources/" in url for method, url, _ in self.requests))
        self.assertEqual(len(self.clean_posts()), 1)

"""正式身份字段在首次解析、Clean 恢复与 Flow 发布时保持一致。"""
from copy import deepcopy
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from services.web.bkbase import clean, flow, metadata
from services.web.bkbase.common import stable_name
from services.web.bkbase.exceptions import BKBaseResourceMappingError


class ResultTableIdentityReuseTests(SimpleTestCase):
    def setUp(self):
        self.context = {"version": "v4", "tenant": "tenant_a", "namespace": "audit"}
        self.ref = {"kind": "ResultTable", "tenant": "tenant_a", "namespace": "inputs", "name": "actual-name"}
        self.remote = {
            "kind": "ResultTable",
            "metadata": {**{k: self.ref[k] for k in ("tenant", "namespace", "name")}, "labels": {}},
            "spec": {"predefiendResultTableId": "11_logical", "bizId": 11},
            "status": {"phase": "Ok", "related": []},
        }
        self.enterContext(
            mock.patch("requests.sessions.Session.request", side_effect=AssertionError("unexpected HTTP"))
        )
        self.lookup = self.enterContext(
            mock.patch.object(metadata.api.bk_base_v4, "result_table_info", return_value=self.remote)
        )
        self.by_ref = self.enterContext(
            mock.patch.object(flow.api.bk_base_v4, "result_table_resource_get", return_value=self.remote)
        )

    def test_clean_first_lookup_and_second_bound_ref_check_accept_the_same_empty_labels(self):
        binding = {}
        first = clean._verified_result_table_ref(self.context, binding, "11_logical")
        binding["result_table"] = first
        second = clean._verified_result_table_ref(self.context, binding, "11_logical")
        self.assertEqual(first, self.ref)
        self.assertEqual(second, self.ref)
        self.assertEqual(
            self.lookup.call_args_list,
            [mock.call(tenant="tenant_a", result_table_id="11_logical")] * 2,
        )
        self.by_ref.assert_not_called()

    def test_clean_reuses_actual_ref_when_explicit_id_and_business_prefix_differ(self):
        self.remote["spec"]["bizId"] = 2
        first = clean._verified_result_table_ref(self.context, {}, "11_logical")
        self.assertEqual(first, self.ref)
        self.assertEqual(
            clean._verified_result_table_ref(self.context, {"result_table": first}, "11_logical"), self.ref
        )

    def test_flow_actual_apply_validates_formal_identity_before_create(self):
        self._assert_flow_apply_keeps_actual_ref()

    def test_flow_actual_apply_accepts_explicit_id_with_different_business_prefix(self):
        self.remote["spec"]["bizId"] = 2
        self._assert_flow_apply_keeps_actual_ref()

    def _assert_flow_apply_keeps_actual_ref(self):
        """在真实Flow发布入口校验输入身份，外部写入与持久化在边界替换。"""
        strategy = SimpleNamespace(strategy_id=13, namespace="audit", backend_data={})
        spec = {"nodes": [{"name": stable_name("src", "11_logical"), "kind": "StreamSourceNode", "data": self.ref}]}

        def save(context, owner, patch, *, remove=()):
            binding = owner.backend_data.setdefault("bkbase_v4", {})
            binding.update(deepcopy(patch))
            for key in remove:
                binding.pop(key, None)
            return binding

        def create(**params):
            return {"metadata": params["metadata"], "spec": params["spec"], "status": {"phase": "Pending"}}

        with mock.patch.object(flow.flow_operation, "assert_detached"), mock.patch.object(
            flow, "_save_operation_binding", side_effect=save
        ), mock.patch.object(flow, "resource_lock"), mock.patch.object(
            flow, "get_resource_or_none", return_value=None
        ), mock.patch.object(
            flow.flow_operation, "write_guard"
        ), mock.patch.object(
            flow.api.bk_base_v4, "flow_create", side_effect=create
        ) as post:
            observed = flow.apply_rule_flow(self.context, strategy, spec)
        post.assert_called_once()
        self.assertEqual(post.call_args.kwargs["spec"]["nodes"][0]["data"], self.ref)
        self.assertEqual(observed["resource_phase"], "Pending")
        self.assertNotIn("managed_nodes", strategy.backend_data["bkbase_v4"])

    def test_documented_fallback_is_reusable_by_clean_and_flow(self):
        self.remote["spec"] = {"bizId": 11}
        self.assertEqual(
            clean._verified_result_table_ref(self.context, {"result_table": self.ref}, "11_actual_name"), self.ref
        )
        self.assertEqual(flow._verified_input_ref(self.context, self.ref), (self.ref, "11_actual_name"))

    def test_conflicting_or_absent_identity_cannot_pass_either_bound_consumer(self):
        baseline = deepcopy(self.remote)
        cases = [
            ({"predefiendResultTableId": "11_other"}, {}),
            ({"predefiendResultTableId": "11_logical"}, {"result_table_id": "11_other"}),
            ({"predefiendResultTableId": "11_bad/path", "bizId": 12}, {}),
            ({}, {}),
        ]
        for spec, labels in cases:
            self.remote.clear()
            self.remote.update(deepcopy(baseline))
            self.remote["spec"] = spec
            self.remote["metadata"]["labels"] = labels
            with self.subTest(spec=spec, labels=labels), self.assertRaises(BKBaseResourceMappingError):
                clean._verified_result_table_ref(self.context, {"result_table": self.ref}, "11_logical")
            if spec == {"predefiendResultTableId": "11_other"}:
                # Ref内正式身份有效时，任意节点名不能作为另一个预期逻辑表的证明。
                with self.subTest(flow=True, spec=spec):
                    flow._validate_flow_inputs(
                        self.context,
                        {
                            "nodes": [
                                {
                                    "name": stable_name("src", "11_logical"),
                                    "kind": "StreamSourceNode",
                                    "data": self.ref,
                                }
                            ]
                        },
                    )
            else:
                with self.subTest(flow=True, spec=spec), self.assertRaises(BKBaseResourceMappingError):
                    flow._verified_input_ref(self.context, self.ref)

    def test_different_business_prefix_does_not_bypass_tenant_kind_or_ref_checks(self):
        self.remote["spec"]["bizId"] = 2
        baseline = deepcopy(self.remote)
        for key, value in (("tenant", "tenant_b"), ("namespace", ""), ("name", ""), ("name", "other-name")):
            self.remote.clear()
            self.remote.update(deepcopy(baseline))
            self.remote["metadata"][key] = value
            with self.subTest(clean=True, key=key, value=value), self.assertRaises(BKBaseResourceMappingError):
                clean._verified_result_table_ref(self.context, {"result_table": self.ref}, "11_logical")
            with self.subTest(flow=True, key=key, value=value), self.assertRaises(BKBaseResourceMappingError):
                flow._verified_input_ref(self.context, self.ref)
        self.remote.clear()
        self.remote.update(baseline)
        self.remote["kind"] = "DataStorage"
        with self.assertRaises(BKBaseResourceMappingError):
            clean._verified_result_table_ref(self.context, {"result_table": self.ref}, "11_logical")
        with self.assertRaises(BKBaseResourceMappingError):
            flow._verified_input_ref(self.context, self.ref)

    def test_legacy_explicit_label_remains_valid_when_formal_fields_are_absent(self):
        self.remote["spec"] = {}
        self.remote["metadata"]["labels"] = {"result_table_id": "11_logical"}
        self.assertEqual(flow._verified_input_ref(self.context, self.ref), (self.ref, "11_logical"))

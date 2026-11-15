"""逻辑结果表查询的正式传输契约与跨项目引用校验。

只保存权威身份，不从存储绑定、名称前缀或默认项目猜测引用。
平台请求在 HTTP 边界替换，错误不得转换成可创建资源。
"""
from copy import deepcopy
from unittest import mock

from bk_resource.exceptions import APIRequestError
from django.test import SimpleTestCase

from api.bk_base_v4 import default as sdk
from services.web.bkbase import metadata
from services.web.bkbase.common import get_resource_or_none
from services.web.bkbase.exceptions import BKBaseResourceMappingError


class ResultTableInfoTests(SimpleTestCase):
    def setUp(self):
        self.context = {"version": "v4", "tenant": "tenant_a", "namespace": "audit"}
        self.ref = {"kind": "ResultTable", "tenant": "tenant_a", "namespace": "other_project", "name": "actual-name"}
        self.resource = {
            "metadata": {key: self.ref[key] for key in ("tenant", "namespace", "name")},
            "spec": {"predefiendResultTableId": "11_logical", "bizId": 11},
            "status": {"related": []},
        }
        self.enterContext(
            mock.patch("requests.sessions.Session.request", side_effect=AssertionError("unexpected HTTP"))
        )

    def call_sdk(self, payload):
        resource = sdk.ResultTableInfo()
        response = mock.Mock(status_code=200)
        response.raise_for_status.return_value = None
        response.json.return_value = payload
        with mock.patch.object(resource.session, "request", return_value=response) as transport, mock.patch.object(
            sdk.BkBaseV4Resource, "build_header", return_value={}
        ), mock.patch.object(resource, "add_esb_info_before_request", side_effect=lambda data: data):
            value = resource.request({"tenant": "tenant_a", "result_table_id": "11_logical"})
        return value, transport.call_args

    def test_sdk_moves_tenant_to_header_and_only_logical_id_to_path(self):
        result, sent = self.call_sdk({"result": True, "code": "00", "data": self.resource})
        self.assertEqual(result, self.resource)
        self.assertEqual(sent.args[0], "GET")
        self.assertTrue(sent.args[1].endswith("/v4/result_tables/11_logical/"))
        self.assertEqual(sent.kwargs["headers"]["X-Bk-Tenant-Id"], "tenant_a")
        self.assertEqual(sent.kwargs.get("params", {}), {})
        self.assertNotIn("json", sent.kwargs)

    def test_ambiguous_missing_code_and_other_failures_propagate(self):
        for code in ("1558025", "1500111", "1500113"):
            with self.subTest(code=code), self.assertRaises(APIRequestError) as raised:
                get_resource_or_none(lambda: self.call_sdk({"result": False, "code": code, "data": None}))
            self.assertFalse(getattr(raised.exception, "resource_not_found", False))

    def resolve(self, payload=None, logical="11_logical"):
        with mock.patch.object(
            metadata.api.bk_base_v4, "result_table_info", return_value=payload or self.resource
        ) as get:
            result = metadata.get_result_table_ref(self.context, logical)
        get.assert_called_once_with(tenant="tenant_a", result_table_id=logical)
        return result

    def test_metadata_ref_without_kind_or_storage_keeps_actual_project_and_name(self):
        self.assertEqual(self.resolve(), self.ref)
        self.assertNotIn("status", self.resolve())

    def test_explicit_logical_id_resolves_actual_ref_when_business_prefix_differs(self):
        self.resource["spec"]["bizId"] = 2
        self.assertEqual(self.resolve(), self.ref)
        self.assertEqual(metadata.result_table_identity(self.context, self.resource), (self.ref, "11_logical"))

    def test_documented_fallback_uses_business_and_hyphen_replacement_without_prefix_guessing(self):
        payload = deepcopy(self.resource)
        payload["metadata"]["name"] = "c_actual-name"
        payload["spec"] = {"predefiendResultTableId": None, "bizId": 11}
        result = self.resolve(payload, logical="11_c_actual_name")
        self.assertEqual(result["name"], "c_actual-name")
        with self.assertRaises(BKBaseResourceMappingError):
            self.resolve(payload, logical="11_actual_name")

    def test_mismatched_or_missing_authoritative_identity_is_rejected(self):
        for key, value in (("tenant", "tenant_b"), ("tenant", ""), ("namespace", None), ("name", "")):
            payload = deepcopy(self.resource)
            payload["metadata"][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(BKBaseResourceMappingError):
                self.resolve(payload)
        for spec in (
            {},
            {"predefiendResultTableId": "11_other"},
            {"predefiendResultTableId": "11_bad/path", "bizId": 12},
            {"predefiendResultTableId": "11_logical", "bizId": True},
            {"predefiendResultTableId": "11_logical", "bizId": "invalid"},
        ):
            payload = deepcopy(self.resource)
            payload["spec"] = spec
            with self.subTest(spec=spec), self.assertRaises(BKBaseResourceMappingError):
                self.resolve(payload)
        with self.assertRaises(BKBaseResourceMappingError):
            self.resolve({**self.resource, "kind": "DataStorage"})

    def test_explicit_id_must_still_match_requested_id_and_label(self):
        self.resource["spec"]["bizId"] = 2
        with self.assertRaises(BKBaseResourceMappingError):
            self.resolve(logical="2_logical")
        self.resource["metadata"]["labels"] = {"result_table_id": "2_logical"}
        with self.assertRaises(BKBaseResourceMappingError):
            self.resolve()

    def test_invalid_logical_id_or_missing_tenant_does_not_make_a_request(self):
        with mock.patch.object(metadata.api.bk_base_v4, "result_table_info") as get:
            for logical in ("missing", "11_", "11_bad/path", "11_x?y", "１１_name", None):
                with self.subTest(logical=logical), self.assertRaises(BKBaseResourceMappingError):
                    metadata.get_result_table_ref(self.context, logical)
            with self.assertRaises(BKBaseResourceMappingError):
                metadata.get_result_table_ref({**self.context, "tenant": ""}, "11_logical")
        get.assert_not_called()

    def test_dataset_and_sensitivity_use_resolved_project_without_local_mapping(self):
        detail = {"dataset_name": "11_logical", "fields": [], "sensitivity": "private"}
        with mock.patch.object(
            metadata.api.bk_base_v4, "result_table_info", return_value=self.resource
        ), mock.patch.object(metadata.api.bk_base_v4, "dataset_detail", return_value=detail) as get:
            self.assertEqual(metadata.get_rt_fields("11_logical", context=self.context), [])
            self.assertEqual(metadata.get_rt_sensitivity(self.context, "11_logical"), {"level": "private"})
        self.assertEqual(get.call_count, 2)
        self.assertTrue(all(call.kwargs["namespace"] == "other_project" for call in get.call_args_list))

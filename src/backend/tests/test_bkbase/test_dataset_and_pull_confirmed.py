"""正式 Dataset 元数据及 V4 PULL 忽略源敏感级别的契约。"""
from copy import deepcopy
from unittest import mock

from django.test import SimpleTestCase, override_settings

from api.bk_base_v4.default import DatasetDetail
from services.web.analyze.utils import is_asset
from services.web.bkbase import metadata, source
from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.strategy_v2.resources import GetRTFields


@override_settings(
    BKBASE_API_VERSION="v4",
    BKBASE_V4_TENANT="tenant_a",
    BKBASE_V4_NAMESPACE="audit",
    BKBASE_V4_RESULT_TABLE_NAMESPACES={"11_test": "other_project"},
)
class DatasetAndPullConfirmedTests(SimpleTestCase):
    def setUp(self):
        self.enterContext(
            mock.patch("requests.sessions.Session.request", side_effect=AssertionError("unexpected HTTP"))
        )
        self.context = {
            "version": "v4",
            "tenant": "tenant_a",
            "namespace": "audit",
            "rt_namespaces": {"11_test": "other_project"},
        }
        self.detail = {
            "dataset_name": "11_test",
            "dataset_alias": "Synthetic",
            "id": "other_project/DorisBinding/x",
            "kind": "DorisBinding",
            "storage_type": "doris",
            "data_set_type": "compute_result_table",
            "fields": [
                {
                    "field_name": "value",
                    "field_alias": "Value",
                    "field_type": "string",
                    "category": "metric",
                    "description": "",
                }
            ],
        }
        self.pages = [
            {
                "pages_num": 2,
                "total": 101,
                "list": [
                    {"dataset_name": "11_test", "storage_type": "doris"},
                    {"dataset_name": "11_test_suffix", "storage_type": "hdfs"},
                ]
                + [{"dataset_name": f"11_test_suffix_{index}", "storage_type": "hdfs"} for index in range(98)],
            },
            {
                "pages_num": 2,
                "total": 101,
                "list": [
                    {"dataset_name": "11_test", "storage_type": "channel"},
                ],
            },
        ]

    def test_metadata_uses_formal_detail_and_paged_storages_without_binding_ref(self):
        with mock.patch.object(
            metadata.api.bk_base_v4, "dataset_detail", return_value=self.detail
        ) as detail, mock.patch.object(
            metadata.api.bk_base_v4, "dataset_list", side_effect=self.pages
        ) as listing, mock.patch.object(
            metadata.api.bk_base_v4, "result_table", side_effect=AssertionError("mcp called")
        ):
            result = metadata.get_result_table("11_test", related=["fields", "storages"], context=self.context)
        self.assertEqual(result["result_table_id"], "11_test")
        self.assertEqual(result["bk_biz_id"], 11)
        self.assertEqual(set(result["storages"]), {"doris", "channel"})
        self.assertEqual(result["fields"], self.detail["fields"])
        self.assertNotIn("id", result)
        self.assertNotIn("kind", result)
        self.assertEqual(detail.call_args.kwargs["namespace"], "other_project")
        self.assertEqual([c.kwargs["page"] for c in listing.call_args_list], [1, 2])

    def test_fields_business_resource_uses_formal_dataset_request(self):
        detail_resource = DatasetDetail()
        response = mock.Mock()
        response.status_code = 200
        response.raise_for_status.return_value = None
        response.json.return_value = {"result": True, "code": "00", "data": self.detail}
        detail_resource.session.request = mock.Mock(return_value=response)
        with mock.patch.object(detail_resource, "build_header", return_value={}), mock.patch.object(
            metadata.api.bk_base_v4, "dataset_detail", detail_resource.request
        ), mock.patch("services.web.strategy_v2.utils.table.GlobalMetaConfig.get", return_value=None):
            response = GetRTFields().request({"table_id": "11_test"})
        self.assertEqual(response[0]["value"], "value")
        url = detail_resource.session.request.call_args.args[1]
        self.assertIn("/v4/databus/dataset/other_project/detail/11_test/", url)

    def test_missing_authoritative_identity_or_wrong_dataset_is_rejected(self):
        with mock.patch.object(metadata.api.bk_base_v4, "result_table_info", return_value={}) as lookup:
            with self.assertRaises(BKBaseResourceMappingError):
                metadata.get_result_table("11_unknown", context=self.context)
        lookup.assert_called_once_with(tenant="tenant_a", result_table_id="11_unknown")
        with mock.patch.object(
            metadata.api.bk_base_v4, "dataset_detail", return_value={**self.detail, "dataset_name": "11_other"}
        ):
            with self.assertRaises(BKBaseResourceMappingError):
                metadata.get_result_table("11_test", context=self.context)

    def test_missing_fields_are_not_treated_as_empty_fields(self):
        detail = {key: value for key, value in self.detail.items() if key != "fields"}
        with mock.patch.object(metadata.api.bk_base_v4, "dataset_detail", return_value=detail):
            result = metadata.get_result_table("11_test", related=["fields"], context=self.context)
            self.assertNotIn("fields", result)
            with self.assertRaises(BKBaseResourceMappingError):
                metadata.get_rt_fields("11_test", context=self.context)
        with mock.patch.object(metadata.api.bk_base_v4, "dataset_detail", return_value={**detail, "fields": []}):
            self.assertEqual(metadata.get_rt_fields("11_test", context=self.context), [])

    def test_v4_ignores_source_sensitivity_but_not_other_inputs(self):
        left = {"access_raw_data": {"sensitivity": "private", "raw_data_alias": "Synthetic"}, "scope": {"url": "/one"}}
        right = deepcopy(left)
        right["access_raw_data"]["sensitivity"] = "public"
        self.assertEqual(source._source_intent_inputs(left), source._source_intent_inputs(right))
        right["scope"]["url"] = "/two"
        self.assertNotEqual(source._source_intent_inputs(left), source._source_intent_inputs(right))

    def test_unavailable_asset_classification_is_not_treated_as_non_asset(self):
        with mock.patch.object(
            metadata,
            "get_source_capabilities",
            return_value={"channel": False, "redis": False, "hdfs_dimensions": [], "hdfs_unknown": True},
        ), self.assertRaises(BKBaseResourceMappingError):
            is_asset({"result_table_id": "11_test", "data_set_type": "compute_result_table"})

"""PULL 已抽取列表的 V4 输入与原 V3 完整响应分别使用正确的清洗路径。"""
import json
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase, override_settings

from services.web.bkbase import clean
from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.databus.collector.snapshot.join.etl_storage import (
    AssetEtlStorageHandler,
    JoinDataEtlStorageHandler,
)
from services.web.databus.collector.snapshot.system.clean import PullCleanHandler


class PullCleanRowsTests(SimpleTestCase):
    @staticmethod
    def template(kind, report_config=None):
        if kind in ("action", "resource_type", "user"):
            params = PullCleanHandler(11, "iam_snapshot", kind, pull_report_config=report_config).config
            return json.loads(params["json_config"]), params["fields"]
        handler_cls = AssetEtlStorageHandler if kind == "asset" else JoinDataEtlStorageHandler
        handler = handler_cls(
            11,
            SimpleNamespace(system_id="synthetic_system"),
            SimpleNamespace(resource_type_id="synthetic_resource"),
            "redis",
            pull_report_config=report_config,
        )
        if kind == "asset":
            handler.__dict__["schema_fields"] = [
                {
                    "field_name": "extra",
                    "field_type": "string",
                    "field_alias": "Synthetic",
                    "is_dimension": False,
                    "is_key": False,
                    "field_index": 1,
                    "is_json": False,
                    "is_original_json": False,
                    "is_index": False,
                }
            ]
        return json.loads(handler.json_config), handler.result_table_fields

    @staticmethod
    def assignments(rules):
        return [(rule["output_id"], rule["operator"]) for rule in rules if rule["operator"]["type"] == "assign"]

    def test_v4_iterates_the_extracted_list_without_decoding_it_as_json(self):
        rows = [
            {"id": "one", "display_name": "First", "created_at": 1700000000000, "data": {"extra": "a"}},
            {"id": "two", "display_name": "Second", "created_at": 1700000001000, "data": {"extra": "b"}},
        ]
        message = json.dumps({"data": rows, "utctime": "2026-11-11 00:00:00", "type": "custom"})
        for kind in ("asset", "basic", "action", "resource_type", "user"):
            with self.subTest(kind=kind), override_settings(BKBASE_API_VERSION="v4"):
                config, fields = self.template(kind, {"data_path": ".data.results"})
                rules = clean.convert_rules(config, fields=fields)
                decoders = [rule for rule in rules if rule["operator"]["type"] == "json_de"]
                self.assertEqual(len(decoders), 1)
                self.assertEqual(decoders[0]["input_id"], "__raw_data")
                [iteration] = [rule for rule in rules if rule["operator"]["type"] == "iter"]
                [rows_rule] = [rule for rule in rules if rule["output_id"] == iteration["input_id"]]
                self.assertEqual(rows_rule["input_id"], decoders[0]["output_id"])
                self.assertEqual(rows_rule["operator"]["type"], "get")
                self.assertEqual(rows_rule["operator"]["key_index"], [{"type": "key", "value": "data"}])
                self.assertEqual(json.loads(message)[rows_rule["operator"]["key_index"][0]["value"]], rows)

    def test_v3_keeps_full_response_path_and_v4_keeps_business_assignments(self):
        for kind in ("asset", "basic", "action", "resource_type", "user"):
            with self.subTest(kind=kind):
                with override_settings(BKBASE_API_VERSION="v3"):
                    legacy, fields = self.template(kind)
                legacy_data = next(node for node in legacy["extract"]["next"]["next"] if node.get("key") == "data")
                self.assertEqual(legacy_data["next"]["method"], "from_json")
                self.assertEqual(legacy_data["next"]["next"]["key"], "data")
                self.assertEqual(legacy_data["next"]["next"]["next"]["key"], "results")
                legacy_rules = clean.convert_rules(legacy, fields=fields)
                with override_settings(BKBASE_API_VERSION="v4"):
                    current, fields = self.template(kind, {"data_path": ".data.results"})
                    current_rules = clean.convert_rules(current, fields=fields)
                self.assertEqual(self.assignments(current_rules), self.assignments(legacy_rules))
                self.assertEqual(current["conf"], legacy["conf"])

    @override_settings(BKBASE_API_VERSION="v4")
    def test_null_source_keeps_full_response_json_decode_and_results_path(self):
        rows = [
            {
                "id": "one",
                "created_at": None,
                "updated_at": 1700000000123,
                "creator": None,
                "data": {},
                "is_deleted": False,
            }
        ]
        message = json.dumps(
            {"data": json.dumps({"data": {"count": 1, "results": rows}}), "utctime": "2026-11-12 00:00:00"}
        )
        for kind in ("asset", "basic", "action", "resource_type", "user"):
            with self.subTest(kind=kind):
                config, fields = self.template(kind, {"data_path": None})
                rules = clean.convert_rules(config, fields=fields)
                self.assertEqual(len([r for r in rules if r["operator"]["type"] == "json_de"]), 2)
                [iteration] = [r for r in rules if r["operator"]["type"] == "iter"]
                [extract_rows] = [r for r in rules if r["output_id"] == iteration["input_id"]]
                self.assertEqual(extract_rows["operator"]["key_index"], [{"type": "key", "value": "results"}])
                self.assertEqual(json.loads(json.loads(message)["data"])["data"]["results"], rows)
                with override_settings(BKBASE_API_VERSION="v3"):
                    legacy, _ = self.template(kind)
                self.assertEqual(config, legacy)

    @override_settings(BKBASE_API_VERSION="v4")
    def test_unknown_source_shape_is_not_inferred_from_version(self):
        for report in (None, {}, {"data_path": ""}, {"data_path": ".custom"}):
            with self.subTest(report=report), self.assertRaises(BKBaseResourceMappingError):
                self.template("basic", report)

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_does_not_resolve_v4_shape_or_add_platform_requests(self):
        with mock.patch.object(
            clean.source, "pull_report_data_path", side_effect=AssertionError("V4 lookup")
        ), mock.patch("requests.Session.request", side_effect=AssertionError("HTTP")):
            for kind in ("asset", "basic", "action", "resource_type", "user"):
                self.template(kind)

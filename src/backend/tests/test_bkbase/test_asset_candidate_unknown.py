"""资产候选跳过未知分类，具体表校验和上游失败仍保持拒绝语义。"""
from copy import deepcopy
from types import SimpleNamespace
from unittest import mock

from bk_resource.exceptions import APIRequestError
from django.core.exceptions import PermissionDenied
from django.test import SimpleTestCase, override_settings

from services.web.analyze.constants import FlowDataSourceNodeType
from services.web.analyze.controls.rule_audit import RuleAuditController
from services.web.analyze.exceptions import NotSupportDataSource
from services.web.analyze.utils import is_asset
from services.web.bkbase import table_capabilities
from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.strategy_v2.constants import RuleAuditConfigType
from services.web.strategy_v2.utils import table


@override_settings(BKBASE_API_VERSION="v4")
class AssetCandidateUnknownTests(SimpleTestCase):
    def setUp(self):
        self.handler = table.BizAssetTableHandler("BizAsset")
        self.rows = [
            {"result_table_id": "11_unknown", "bk_biz_id": 11, "result_table_name": "Unknown"},
            {"result_table_id": "11_redis", "bk_biz_id": 11, "result_table_name": "Redis asset"},
            {"result_table_id": "11_flow", "bk_biz_id": 11, "result_table_name": "Flow"},
            {"result_table_id": "11_untyped", "bk_biz_id": 11, "result_table_name": "Unknown dimensions"},
            {"result_table_id": "11_hdfs", "bk_biz_id": 11, "result_table_name": "HDFS asset"},
        ]
        empty = {"channel": False, "redis": False, "hdfs_dimensions": [], "hdfs_unknown": False}
        self.capabilities = {
            "11_unknown": {**empty},
            "11_untyped": {**empty, "hdfs_unknown": True},
            "11_redis": {**empty, "redis": True},
            "11_flow": {**empty, "hdfs_dimensions": [False]},
            "11_hdfs": {**empty, "hdfs_dimensions": [True]},
        }
        self.project_data = self.enterContext(
            mock.patch.object(table.bkbase_permissions, "get_project_data", return_value=self.rows)
        )
        self.enterContext(
            mock.patch.object(
                table.bkbase_metadata,
                "get_result_table",
                side_effect=lambda rt_id, **kwargs: next(row for row in self.rows if row["result_table_id"] == rt_id),
            )
        )
        self.lookup = self.enterContext(
            mock.patch.object(
                table.bkbase_metadata,
                "get_source_capabilities",
                side_effect=lambda rt_id, **kwargs: self.capabilities[rt_id],
            )
        )
        self.enterContext(
            mock.patch.object(
                table.resource.meta,
                "get_spaces_mine",
                return_value=[{"id": "11", "name": "Synthetic", "space_type_id": table.SpaceType.BIZ.value}],
            )
        )
        self.enterContext(
            mock.patch("requests.sessions.Session.request", side_effect=AssertionError("unexpected HTTP"))
        )

    def test_actual_list_and_formatter_keep_known_assets_with_false_and_unknown_rows(self):
        before = deepcopy(self.capabilities)
        result = self.handler.list_tables()
        self.assertEqual(
            result,
            [
                {
                    "label": "Synthetic(11)",
                    "value": "11",
                    "children": [
                        {"label": "Redis asset", "value": "11_redis"},
                        {"label": "HDFS asset", "value": "11_hdfs"},
                    ],
                }
            ],
        )
        self.assertCountEqual(
            [call.args[0] for call in self.lookup.call_args_list], [row["result_table_id"] for row in self.rows]
        )
        self.assertIsNone(table_capabilities.asset_status(self.capabilities["11_unknown"]))
        self.assertEqual(self.capabilities, before)

    def test_only_unknown_candidates_produce_no_selected_asset(self):
        self.lookup.side_effect = lambda rt_id, **kwargs: self.capabilities["11_unknown"]
        result = self.handler.list_tables()
        self.assertEqual(result, [{"label": "Synthetic(11)", "value": "11", "children": []}])
        self.assertIsNone(table_capabilities.asset_status(self.capabilities["11_unknown"]))

    def test_ref_conflict_and_http_failure_are_not_treated_as_unknown_classification(self):
        errors = (
            BKBaseResourceMappingError(message="synthetic RT Ref conflict"),
            APIRequestError(module_name="bkbase_v4", url="/v4/result_tables/", result="synthetic failure"),
            PermissionDenied("synthetic access denied"),
        )
        for error in errors:
            self.lookup.side_effect = error
            with self.subTest(error=type(error).__name__), self.assertRaises(type(error)) as raised:
                self.handler.list_tables()
            self.assertIs(raised.exception, error)

    def test_project_permission_failure_is_not_swallowed(self):
        self.project_data.side_effect = PermissionDenied("synthetic project denied")
        with self.assertRaises(PermissionDenied):
            self.handler.list_tables()
        self.lookup.assert_not_called()

    def test_unknown_selected_table_still_fails_asset_and_node_validation(self):
        self.lookup.side_effect = lambda rt_id: self.capabilities["11_unknown"]
        with self.assertRaises(BKBaseResourceMappingError):
            is_asset(self.rows[0])
        controller = SimpleNamespace(
            event_log_rt_id="11_log",
            strategy=SimpleNamespace(
                configs={
                    "config_type": RuleAuditConfigType.BIZ_RT,
                    "data_source": {"source_type": FlowDataSourceNodeType.REALTIME},
                }
            ),
        )
        with self.assertRaises(NotSupportDataSource):
            RuleAuditController.check_source_type(controller, "11_unknown")
        self.assertEqual(table.RuleAuditSourceTypeChecker("audit").rt_support_source_types("11_unknown"), [])

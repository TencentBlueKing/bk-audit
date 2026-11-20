"""保存入口只核验本次提交的个人 RT。"""
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase, override_settings
from rest_framework import serializers

from services.web.bkbase import metadata, permissions
from services.web.strategy_v2 import serializers as strategy
from services.web.strategy_v2.constants import (
    LinkTableTableType,
    RuleAuditConfigType,
    StrategyType,
)


@override_settings(BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="tenant_a")
class MineSavePermissionTests(SimpleTestCase):
    def setUp(self):
        self.user = SimpleNamespace(username="actual_user", is_authenticated=True)
        self.enterContext(
            mock.patch("services.web.bkbase.common.get_local_request", return_value=SimpleNamespace(user=self.user))
        )
        self.enterContext(mock.patch.object(strategy, "get_request_username", return_value="actual_user"))
        self.enterContext(mock.patch.object(permissions, "get_request_username", return_value="actual_user"))
        self.enterContext(
            mock.patch.object(permissions, "list_user_rts", side_effect=AssertionError("Full user RT scan"))
        )
        self.scene_tables = self.enterContext(
            mock.patch.object(strategy.SceneDataFilter, "get_table_ids", return_value=["7_scene"])
        )
        self.auth = self.enterContext(mock.patch.object(permissions.api.bk_base_v4, "direct_auth_by_resources"))
        self.info = self.enterContext(
            mock.patch.object(metadata.api.bk_base_v4, "result_table_info", side_effect=self.result_table)
        )
        self.auth.side_effect = lambda **kwargs: [{"resource_id": rt, "allowed": True} for rt in kwargs["resource_ids"]]

    @staticmethod
    def result_table(tenant, result_table_id):
        return {
            "kind": "ResultTable",
            "metadata": {"tenant": tenant, "namespace": "actual_project", "name": "physical"},
            "spec": {"predefiendResultTableId": result_table_id},
        }

    def validate_strategy(self, rt_id):
        handler = strategy.StrategySerializer()
        with mock.patch.object(handler, "get_scene_id", return_value=8):
            handler._validate_strategy_data_permission(
                {
                    "strategy_type": StrategyType.RULE,
                    "configs": {"config_type": RuleAuditConfigType.MINE_BIZ_RT, "data_source": {"rt_id": rt_id}},
                    "user_id": "spoofed",
                }
            )

    def links(self):
        tables = [
            {"table_type": LinkTableTableType.MINE_BIZ_RT, "rt_id": rt} for rt in ("7_a", "7_b", "7_a", "7_scene")
        ]
        return [{"left_table": a, "right_table": b} for a, b in zip(tables[::2], tables[1::2])]

    def test_strategy_save_rechecks_actual_user_and_explicit_rt(self):
        self.validate_strategy("7_scene")
        self.auth.assert_not_called()
        self.validate_strategy("7_a")
        self.assert_batch(["7_a"])

    def test_link_save_batches_deduplicated_non_scene_inputs(self):
        strategy.LinkTableDataPermissionMixin()._validate_link_table_data_permission(
            {"scene_id": 8, "config": {"links": self.links()}, "user_id": "spoofed"}
        )
        self.assert_batch(["7_a", "7_b"])

    def test_strategy_with_saved_link_rechecks_all_non_scene_inputs_once(self):
        with mock.patch.object(strategy.LinkTable.objects, "filter") as query:
            query.return_value.first.return_value = SimpleNamespace(config={"links": self.links()})
            strategy.StrategySerializer()._validate_link_table_data_permission("link", 1, 8)
        self.assert_batch(["7_a", "7_b"])

    def assert_batch(self, ids):
        self.auth.assert_called_once()
        self.assertEqual(self.auth.call_args.kwargs["user_id"], "actual_user")
        self.assertEqual(self.auth.call_args.kwargs["action_id"], "query_dataset")
        self.assertEqual(self.auth.call_args.kwargs["resource_ids"], ids)
        self.assertEqual(self.info.call_args_list, [mock.call(tenant="tenant_a", result_table_id=rt) for rt in ids])

    def test_empty_denied_duplicate_and_non_boolean_permission_never_allow(self):
        self.auth.side_effect = None
        for rows in (
            [],
            [{"resource_id": "7_a", "allowed": False}],
            [{"resource_id": "7_a", "allowed": "true"}],
            [{"resource_id": "7_a", "allowed": True}] * 2,
            [{"resource_id": "7_other", "allowed": True}],
        ):
            self.auth.return_value = rows
            with self.subTest(rows=rows), self.assertRaises(serializers.ValidationError) as error:
                self.validate_strategy("7_a")
            self.assertIn("rt_id", error.exception.detail)
        self.info.assert_not_called()

    def test_admin_allow_without_a_formal_matching_table_is_rejected_in_link_error_field(self):
        self.info.side_effect = None
        for response in ({}, self.result_table("other_tenant", "7_a"), self.result_table("tenant_a", "7_other")):
            self.info.return_value = response
            with self.subTest(response=response), self.assertRaises(serializers.ValidationError) as error:
                strategy.LinkTableDataPermissionMixin()._validate_link_table_data_permission(
                    {"scene_id": 8, "config": {"links": self.links()}}
                )
            self.assertIn("config", error.exception.detail)

    def test_unauthenticated_current_user_cannot_use_application_identity(self):
        self.user.is_authenticated = False
        with self.assertRaises(serializers.ValidationError):
            self.validate_strategy("7_a")
        self.auth.assert_not_called()
        self.info.assert_not_called()

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_preserves_existing_per_table_api(self):
        with mock.patch.object(permissions.api.bk_base, "user_auth_check", return_value=True) as v3, mock.patch.object(
            permissions, "project_data_batch_check", return_value=[{"result_table_id": "7_a", "result": True}]
        ):
            self.validate_strategy("7_a")
        v3.assert_called_once_with(user_id="actual_user", action_id="result_table.query_data", object_id="7_a")
        self.auth.assert_not_called()
        self.info.assert_not_called()

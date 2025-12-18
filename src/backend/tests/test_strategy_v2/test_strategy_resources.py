# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
"""
import datetime
from types import SimpleNamespace
from unittest import mock

from django.test import override_settings

from apps.meta.constants import ConfigLevelChoices
from apps.meta.models import GlobalMetaConfig, Tag
from apps.meta.utils.fields import EXTEND_DATA, SNAPSHOT_USER_INFO
from services.web.databus.constants import COLLECTOR_PLUGIN_ID
from services.web.databus.models import CollectorPlugin
from services.web.strategy_v2.constants import (
    HAS_UPDATE_TAG_ID,
    HAS_UPDATE_TAG_NAME,
    StrategyType,
)
from services.web.strategy_v2.models import Strategy, StrategyTag
from services.web.strategy_v2.resources import ListStrategyFields, ListTables
from tests.base import TestCase


class StrategyResourcesTest(TestCase):
    def setUp(self):
        super().setUp()
        self.strategy = Strategy.objects.create(
            namespace=self.namespace,
            strategy_name="example",
            strategy_type=StrategyType.MODEL.value,
        )
        self.collector_plugin = CollectorPlugin.objects.create(
            namespace=self.namespace,
            collector_plugin_id=321,
            collector_plugin_name="Default Collector",
            collector_plugin_name_en="default_collector",
            bkdata_biz_id=1,
            table_id=1,
            index_set_id=1,
        )
        GlobalMetaConfig.set(
            COLLECTOR_PLUGIN_ID,
            self.collector_plugin.collector_plugin_id,
            config_level=ConfigLevelChoices.NAMESPACE.value,
            instance_key=self.namespace,
        )

    @mock.patch("services.web.strategy_v2.resources.get_local_request")
    @mock.patch("services.web.strategy_v2.resources.ActionPermission")
    @mock.patch.object(ListStrategyFields, "load_action_fields")
    def test_list_strategy_fields_sort_and_permission(
        self,
        mock_load_action_fields,
        mock_action_permission,
        mock_get_local_request,
    ):
        mock_load_action_fields.return_value = [
            {"field_name": "b_field", "priority_index": 0},
            {"field_name": "a_field", "priority_index": 1},
        ]
        mock_action_permission.return_value.has_permission.return_value = True
        mock_get_local_request.return_value = SimpleNamespace(
            COOKIES={"bk_token": "fake"},
            user=SimpleNamespace(username="tester"),
        )

        result = ListStrategyFields().perform_request(
            {
                "namespace": self.namespace,
                "system_id": "bk_a",
                "action_id": "view",
            }
        )

        self.assertEqual(
            result,
            [
                {"field_name": "a_field", "priority_index": 1},
                {"field_name": "b_field", "priority_index": 0},
            ],
        )
        mock_load_action_fields.assert_called_once()

    @mock.patch("services.web.strategy_v2.resources.get_local_request")
    @mock.patch("services.web.strategy_v2.resources.ActionPermission")
    @mock.patch.object(ListStrategyFields, "load_action_fields")
    @mock.patch.object(ListStrategyFields, "load_public_fields")
    def test_list_strategy_fields_permission_denied(
        self,
        mock_load_public_fields,
        mock_load_action_fields,
        mock_action_permission,
        mock_get_local_request,
    ):
        mock_action_permission.return_value.has_permission.return_value = False
        mock_get_local_request.return_value = SimpleNamespace(
            COOKIES={"bk_token": "fake"},
            user=SimpleNamespace(username="tester"),
        )
        result = ListStrategyFields().perform_request({"namespace": self.namespace})
        self.assertEqual(result, [])
        mock_load_action_fields.assert_not_called()
        mock_load_public_fields.assert_not_called()

    @mock.patch("services.web.strategy_v2.resources.FeatureHandler")
    @mock.patch("services.web.strategy_v2.resources.resource.query.search_all")
    def test_load_action_fields_uses_search_all(self, mock_search_all, mock_feature_handler):
        mock_feature_handler.return_value.check.return_value = False
        mock_search_all.return_value = {"results": [{"extend_data": {"target": "value"}}]}

        data = ListStrategyFields.load_action_fields(self.namespace, "bk_a", "view")

        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["field_name"], f"{EXTEND_DATA.field_name}.target")

    @mock.patch("services.web.strategy_v2.resources.FeatureHandler")
    @mock.patch("services.web.strategy_v2.resources.resource.query.collector_search_all")
    def test_load_action_fields_uses_collector_when_doris_enabled(self, mock_collector_search, mock_feature_handler):
        mock_feature_handler.return_value.check.return_value = True
        mock_collector_search.return_value = {"results": [{"extend_data": {"target": "value"}}]}

        data = ListStrategyFields.load_action_fields(self.namespace, "bk_a", "view")

        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["field_name"], f"{EXTEND_DATA.field_name}.target")

    @override_settings(SNAPSHOT_USERINFO_RESOURCE_URL="https://snapshot.example.com")
    @mock.patch("services.web.strategy_v2.resources.api.user_manage.get_snapshot_schema")
    def test_load_public_fields_append_snapshot_schema(self, mock_get_schema):
        mock_get_schema.return_value = {"email": {"description": "邮箱", "type": "string"}}
        fields = ListStrategyFields().load_public_fields()
        snapshot_fields = [field for field in fields if field["field_name"] == f"{SNAPSHOT_USER_INFO.field_name}.email"]
        self.assertTrue(snapshot_fields)

    @mock.patch("strategy_v2.resources.resource.strategy_v2.list_has_update_strategy")
    def test_list_strategy_tags_contains_aggregated_counts(self, mock_list_updates):
        mock_list_updates.return_value = [self.strategy]
        tag = Tag.objects.create(tag_name="Beta")
        StrategyTag.objects.create(strategy=self.strategy, tag=tag)

        tags = self.resource.strategy_v2.list_strategy_tags()

        self.assertEqual(tags[0]["tag_id"], HAS_UPDATE_TAG_ID)
        self.assertEqual(tags[0]["strategy_count"], len(mock_list_updates.return_value))
        tag_entry = next(item for item in tags if str(item.get("tag_id")) == str(tag.tag_id))
        self.assertEqual(tag_entry["tag_name"], tag.tag_name)
        self.assertEqual(tag_entry["strategy_count"], 1)
        self.assertEqual(tags[0]["tag_name"], str(HAS_UPDATE_TAG_NAME))

    @mock.patch("strategy_v2.resources.enhance_rt_fields")
    @mock.patch("strategy_v2.resources.api.bk_base.get_sensitivity_info_via_dataset")
    @mock.patch("strategy_v2.resources.api.bk_base.get_role_users_list")
    @mock.patch("strategy_v2.resources.api.bk_base.get_result_table")
    def test_get_rt_meta_merges_concurrent_results(
        self,
        mock_get_result_table,
        mock_get_role_users_list,
        mock_get_sensitivity_info,
        mock_enhance_fields,
    ):
        mock_get_result_table.return_value = {
            "fields": [{"field_name": "raw", "field_alias": "RAW", "field_type": "string"}]
        }
        mock_get_role_users_list.side_effect = [["tom"], ["jerry"]]
        mock_get_sensitivity_info.return_value = {"level": "private"}
        mock_enhance_fields.return_value = [{"field_name": "formatted"}]

        result = self.resource.strategy_v2.get_rt_meta(table_id="1")

        self.assertEqual(
            result["fields"],
            [{"field_name": "raw", "field_alias": "RAW", "field_type": "string"}],
        )
        self.assertEqual(result["managers"], ["tom"])
        self.assertEqual(result["formatted_fields"], [{"field_name": "formatted"}])

    @mock.patch("strategy_v2.resources.resource.strategy_v2.get_rt_fields.bulk_request")
    def test_bulk_get_rt_fields_aligns_results(self, mock_bulk_request):
        mock_bulk_request.return_value = [
            [
                {
                    "label": "field_1",
                    "value": "field_1",
                    "alias": "field_1",
                    "field_type": "string",
                    "spec_field_type": "keyword",
                    "property": {},
                }
            ],
            [
                {
                    "label": "field_2",
                    "value": "field_2",
                    "alias": "field_2",
                    "field_type": "string",
                    "spec_field_type": "keyword",
                    "property": {},
                }
            ],
        ]

        result = self.resource.strategy_v2.bulk_get_rt_fields(table_ids="1,2")

        self.assertEqual(
            result,
            [
                {
                    "table_id": "1",
                    "fields": [
                        {
                            "label": "field_1",
                            "value": "field_1",
                            "alias": "field_1",
                            "field_type": "string",
                            "spec_field_type": "keyword",
                            "property": {},
                        }
                    ],
                },
                {
                    "table_id": "2",
                    "fields": [
                        {
                            "label": "field_2",
                            "value": "field_2",
                            "alias": "field_2",
                            "field_type": "string",
                            "spec_field_type": "keyword",
                            "property": {},
                        }
                    ],
                },
            ],
        )

    @mock.patch("services.web.strategy_v2.resources.TableHandler")
    def test_list_tables_invokes_handler(self, mock_table_handler):
        handler_instance = mock_table_handler.return_value
        handler_instance.list_tables.return_value = [{"label": "biz", "value": "rt"}]

        result = ListTables().perform_request({"table_type": "BizRt", "namespace": self.namespace})

        mock_table_handler.assert_called_once_with(table_type="BizRt", namespace=self.namespace)
        self.assertEqual(result, [{"label": "biz", "value": "rt"}])

    @mock.patch("services.web.strategy_v2.resources.api.bk_base.query_sync")
    @mock.patch("services.web.strategy_v2.resources.api.bk_base.get_result_table")
    @mock.patch("services.web.strategy_v2.resources.is_asset")
    def test_get_rt_last_data_adds_date_filter(self, mock_is_asset, mock_get_result_table, mock_query_sync):
        mock_is_asset.return_value = False
        mock_get_result_table.return_value = {}
        mock_query_sync.return_value = {"list": [{"k": "v"}]}

        result = self.resource.strategy_v2.get_rt_last_data(table_id="1", limit=5)

        today = datetime.datetime.now().strftime('%Y%m%d')
        expected_sql = f"SELECT * FROM 1 WHERE thedate = {today} ORDER BY dteventtimestamp DESC LIMIT 5"
        mock_query_sync.assert_called_once_with(sql=expected_sql)
        self.assertEqual(result["last_data"], [{"k": "v"}])

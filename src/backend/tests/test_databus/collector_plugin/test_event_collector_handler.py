import json
from unittest.mock import patch

from bk_resource.settings import bk_resource_settings
from django.conf import settings
from django.test import TestCase

from services.web.databus.collector_plugin.handlers import EventCollectorEtlHandler
from services.web.databus.constants import PluginSceneChoices
from services.web.databus.models import CollectorPlugin
from tests.test_databus.collector_plugin.constants import (
    EXPECTED_CLEAN_CONFIG_NAME,
    EXPECTED_CLEAN_JSON_CONFIG,
    EXPECTED_DORIS_FIELDS,
    EXPECTED_EVENT_FIELDS,
    EXPECTED_PHYSICAL_TABLE_NAME,
    EXPECTED_RESULT_TABLE_NAME,
)


class EventCollectorEtlHandlerTestCase(TestCase):
    def setUp(self) -> None:
        self.plugin = CollectorPlugin.objects.create(
            namespace=settings.DEFAULT_NAMESPACE,
            collector_plugin_id=1001,
            collector_plugin_name="event plugin",
            collector_plugin_name_en="event_plugin",
            bkdata_biz_id=settings.DEFAULT_BK_BIZ_ID,
            table_id=0,
            index_set_id=0,
            plugin_scene=PluginSceneChoices.EVENT.value,
        )

    def test_get_fields(self):
        handler = EventCollectorEtlHandler(plugin=self.plugin)
        actual = handler.get_fields()

        self.assertJSONEqual(
            json.dumps(actual, ensure_ascii=False),
            json.dumps(EXPECTED_EVENT_FIELDS, ensure_ascii=False),
        )

    def test_build_clean_config(self):
        handler = EventCollectorEtlHandler(plugin=self.plugin)

        with patch.object(EventCollectorEtlHandler, "get_bk_data_id", return_value=123), patch(
            "services.web.databus.collector_plugin.handlers.uniqid",
            side_effect=["abcde12345", "fghij67890", "klmno24680"],
        ):
            config = handler.build_clean_config()

        base_config = {
            "bk_biz_id": settings.DEFAULT_BK_BIZ_ID,
            "bk_username": bk_resource_settings.PLATFORM_AUTH_ACCESS_USERNAME,
            "clean_config_name": EXPECTED_CLEAN_CONFIG_NAME,
            "description": EXPECTED_CLEAN_CONFIG_NAME,
            "fields": EXPECTED_EVENT_FIELDS,
            "raw_data_id": 123,
            "result_table_name": EXPECTED_RESULT_TABLE_NAME,
            "result_table_name_alias": EXPECTED_RESULT_TABLE_NAME,
        }

        actual_json_config = json.loads(config.pop("json_config"))

        self.assertJSONEqual(
            json.dumps(config, ensure_ascii=False),
            json.dumps(base_config, ensure_ascii=False),
        )
        self.assertJSONEqual(
            json.dumps(actual_json_config, ensure_ascii=False),
            json.dumps(EXPECTED_CLEAN_JSON_CONFIG, ensure_ascii=False),
        )

    def test_build_event_storage_config(self):
        handler = EventCollectorEtlHandler(plugin=self.plugin)
        storage_cluster_config = {"bkbase_cluster_id": 200}

        with patch.object(EventCollectorEtlHandler, "get_bk_data_id", return_value=123), patch(
            "services.web.databus.collector_plugin.handlers.GlobalMetaConfig.get",
            return_value=storage_cluster_config,
        ):
            config = handler.build_event_storage_config()

        expected = {
            "bk_biz_id": settings.DEFAULT_BK_BIZ_ID,
            "raw_data_id": 123,
            "data_type": "clean",
            "result_table_name": EXPECTED_RESULT_TABLE_NAME,
            "result_table_name_alias": EXPECTED_RESULT_TABLE_NAME,
            "storage_type": "doris",
            "storage_cluster": storage_cluster_config["bkbase_cluster_id"],
            "expires": settings.EVENT_DORIS_EXPIRES,
            "fields": EXPECTED_DORIS_FIELDS,
            "config": {"dimension_table": False, "data_model": "duplicate_table", "is_profiling": False},
            "physical_table_name": EXPECTED_PHYSICAL_TABLE_NAME,
        }

        self.assertJSONEqual(
            json.dumps(config, ensure_ascii=False),
            json.dumps(expected, ensure_ascii=False),
        )

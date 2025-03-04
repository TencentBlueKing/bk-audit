# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
Copyright (C) 2023 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

from unittest import mock

from apps.meta.constants import ConfigLevelChoices
from apps.meta.models import GlobalMetaConfig
from core.utils.tools import ordered_dict_to_json
from services.web.databus.constants import (
    DEFAULT_REPLICA_WRITE_STORAGE_CONFIG_KEY,
    DEFAULT_STORAGE_CONFIG_KEY,
    INDEX_SET_CONFIG_KEY,
)
from services.web.databus.models import CollectorPlugin
from services.web.databus.tasks import create_or_update_plugin_etl
from services.web.entry.init.base import SystemInitHandler
from tests.base import TestCase
from tests.test_databus.collector_plugin.constants import (
    BATCH_CONNECTIVITY_DETECT_API_RESP,
    CREATE_COLLECTOR_PLUGIN_API_RESP,
    CREATE_PLUGIN_DATA,
    CREATE_PLUGIN_PARAMS,
    DATACLEAN_RESULT,
    GET_PLUGIN_LIST_DATA,
    GET_STORAGES_API_RESP,
    INDEX_SET_REPLACE_API_RESP,
    PLUGIN_DATA,
    RAW_DATA_LIST,
    REPLICA_STORAGE_CLUSTER_CONFIG,
    STORAGE_CLUSTER_ID,
    UPDATE_COLLECTOR_PLUGIN_API_RESP,
    UPDATE_PLUGIN_DATA,
    UPDATE_PLUGIN_PARAMS,
)


class CollectorPluginTest(TestCase):
    """
    Test BkLog CollectorPlugin
    """

    def setUp(self) -> None:
        GlobalMetaConfig.set(
            DEFAULT_STORAGE_CONFIG_KEY,
            STORAGE_CLUSTER_ID,
            config_level=ConfigLevelChoices.NAMESPACE.value,
            instance_key=self.namespace,
        )
        GlobalMetaConfig.set(
            DEFAULT_REPLICA_WRITE_STORAGE_CONFIG_KEY,
            REPLICA_STORAGE_CLUSTER_CONFIG,
            config_level=ConfigLevelChoices.NAMESPACE.value,
            instance_key=self.namespace,
        )
        CollectorPlugin.objects.create(**PLUGIN_DATA)
        SystemInitHandler().init_standard_fields()

    @mock.patch(
        "databus.collector_plugin.resources.api.bk_log.index_set_replace",
        mock.Mock(return_value=INDEX_SET_REPLACE_API_RESP),
    )
    @mock.patch("databus.storage.handler.es.api.bk_log.get_storages", mock.Mock(return_value=GET_STORAGES_API_RESP))
    @mock.patch(
        "databus.collector_plugin.resources.api.bk_log.create_collector_plugin",
        mock.Mock(return_value=CREATE_COLLECTOR_PLUGIN_API_RESP),
    )
    @mock.patch(
        "databus.storage.handler.es.api.bk_log.batch_connectivity_detect",
        mock.Mock(return_value=BATCH_CONNECTIVITY_DETECT_API_RESP),
    )
    def test_creat_plugin(self):
        """CreatePluginResource"""
        result = self.resource.databus.collector_plugin.create_plugin(**CREATE_PLUGIN_PARAMS)
        self.assertEqual(result, CREATE_PLUGIN_DATA)

    @mock.patch(
        "databus.collector_plugin.resources.api.bk_log.index_set_replace",
        mock.Mock(return_value=INDEX_SET_REPLACE_API_RESP),
    )
    @mock.patch("databus.storage.handler.es.api.bk_log.get_storages", mock.Mock(return_value=GET_STORAGES_API_RESP))
    @mock.patch(
        "databus.collector_plugin.resources.api.bk_log.create_collector_plugin",
        mock.Mock(return_value=CREATE_COLLECTOR_PLUGIN_API_RESP),
    )
    @mock.patch(
        "databus.storage.handler.es.api.bk_log.batch_connectivity_detect",
        mock.Mock(return_value=BATCH_CONNECTIVITY_DETECT_API_RESP),
    )
    def test_creat_plugin_of_except(self):
        """CreatePluginResource"""
        self.resource.databus.collector_plugin.create_plugin(**CREATE_PLUGIN_PARAMS)
        GlobalMetaConfig.set(
            INDEX_SET_CONFIG_KEY,
            {"indexes": []},
            config_level=ConfigLevelChoices.NAMESPACE.value,
            instance_key=self.namespace,
        )
        self.resource.databus.collector_plugin.create_plugin(**CREATE_PLUGIN_PARAMS)

    @mock.patch("databus.storage.handler.es.api.bk_log.get_storages", mock.Mock(return_value=GET_STORAGES_API_RESP))
    @mock.patch(
        "databus.storage.handler.es.api.bk_log.batch_connectivity_detect",
        mock.Mock(return_value=BATCH_CONNECTIVITY_DETECT_API_RESP),
    )
    @mock.patch(
        "databus.collector_plugin.resources.api.bk_log.update_collector_plugin",
        mock.Mock(return_value=UPDATE_COLLECTOR_PLUGIN_API_RESP),
    )
    @mock.patch("databus.collector_plugin.resources.create_or_update_plugin_etl", mock.Mock(return_value=None))
    def test_update_plugin(self):
        """UpdatePluginResource"""
        result = self.resource.databus.collector_plugin.update_plugin(**UPDATE_PLUGIN_PARAMS)
        self.assertEqual(result, UPDATE_PLUGIN_DATA)

    def test_get_plugin_list(self):
        """GetPluginListResource"""
        result = []
        for item in self.resource.databus.collector_plugin.get_plugin_list():
            item.pop("id", None)
            item.pop("created_at", None)
            item.pop("created_by", None)
            item.pop("updated_at", None)
            item.pop("updated_by", None)
            result.append(item)
        self.assertEqual(ordered_dict_to_json(result), GET_PLUGIN_LIST_DATA)

    @mock.patch(
        "services.web.databus.collector_plugin.handlers.api.bk_base.get_rawdata_list",
        mock.Mock(return_value=RAW_DATA_LIST),
    )
    @mock.patch(
        "services.web.databus.collector_plugin.handlers.api.bk_base.databus_cleans_post",
        mock.Mock(return_value=DATACLEAN_RESULT),
    )
    @mock.patch("databus.collector.etl.base.api.bk_base.databus_tasks_post", mock.Mock())
    @mock.patch("databus.collector.etl.base.api.bk_base.databus_storages_post", mock.Mock())
    @mock.patch("databus.storage.resources.api.bk_log.get_storages", mock.Mock(return_value=GET_STORAGES_API_RESP))
    def test_create_or_update_plugin_etl(self):
        """CreateOrUpdatePluginEtlResource"""
        create_or_update_plugin_etl.__wrapped__.__wrapped__()

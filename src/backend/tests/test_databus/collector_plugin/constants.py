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

import copy

from django.conf import settings

from services.web.databus.constants import (
    DEFAULT_ALLOCATION_MIN_DAYS,
    DEFAULT_RETENTION,
    DEFAULT_STORAGE_REPLIES,
    DEFAULT_STORAGE_SHARD_SIZE,
    DEFAULT_STORAGE_SHARDS,
    EtlConfigEnum,
    PluginSceneChoices,
)
from tests.test_databus.storage.constants import CLUSTER_ID as _CLUSTER_ID
from tests.test_databus.storage.constants import (
    GET_STORAGES_API_RESP as _GET_STORAGES_API_RESP,
)
from tests.test_databus.storage.constants import (
    REPLICA_WRITE_CLUSTER_ID as _REPLICA_WRITE_CLUSTER_ID,
)

# Base
PLUGIN_ID = 1
PLUGIN_NAME = "test_plugin"
INDEX_SET_ID = 2
STORAGE_CLUSTER_ID = _CLUSTER_ID
REPLICA_STORAGE_CLUSTER_CONFIG = {
    "cluster_id": _REPLICA_WRITE_CLUSTER_ID,
    "bkbase_cluster_id": _REPLICA_WRITE_CLUSTER_ID,
}
PLUGIN_DATA = {
    "namespace": settings.DEFAULT_NAMESPACE,
    "collector_plugin_id": PLUGIN_ID,
    "collector_plugin_name": PLUGIN_NAME,
    "collector_plugin_name_en": PLUGIN_NAME,
    "bkdata_biz_id": int(settings.DEFAULT_BK_BIZ_ID),
    "table_id": 0,
    "index_set_id": INDEX_SET_ID,
    "extra_fields": [],
    "plugin_scene": PluginSceneChoices.COLLECTOR.value,
    "bkbase_processing_id": None,
    "bkbase_table_id": None,
    "has_storage": False,
    "auth_rt": False,
}

PLUGIN_RESULT_TABLE = f"{settings.DEFAULT_BK_BIZ_ID}_bklog_{PLUGIN_NAME}"

# Create Plugin
INDEX_SET_REPLACE_API_RESP = {"index_set_id": INDEX_SET_ID}
GET_STORAGES_API_RESP = copy.deepcopy(_GET_STORAGES_API_RESP)
CREATE_COLLECTOR_PLUGIN_API_RESP = {
    **PLUGIN_DATA,
    "etl_config": None,
    "etl_params": {},
    "storage_changed": False,
    "retention": DEFAULT_RETENTION,
    "allocation_min_days": DEFAULT_ALLOCATION_MIN_DAYS,
    "storage_replies": DEFAULT_STORAGE_REPLIES,
    "storage_shards_nums": DEFAULT_STORAGE_SHARDS,
    "storage_shards_size": DEFAULT_STORAGE_SHARD_SIZE,
}
BATCH_CONNECTIVITY_DETECT_API_RESP = {
    str(STORAGE_CLUSTER_ID): {
        "cluster_stats": {"data_node_count": 0},
    }
}
CREATE_PLUGIN_PARAMS = {
    "namespace": settings.DEFAULT_NAMESPACE,
    "etl_config": EtlConfigEnum.BK_LOG_JSON.value,
    "etl_params": {},
    "is_default": True,
}
CREATE_PLUGIN_DATA = CREATE_COLLECTOR_PLUGIN_API_RESP

# Update Plugin
UPDATE_COLLECTOR_PLUGIN_API_RESP = CREATE_COLLECTOR_PLUGIN_API_RESP
UPDATE_PLUGIN_PARAMS = {**CREATE_PLUGIN_PARAMS, "collector_plugin_id": PLUGIN_ID}
UPDATE_PLUGIN_DATA = CREATE_COLLECTOR_PLUGIN_API_RESP

# Get Plugin List
GET_PLUGIN_LIST_DATA = [CREATE_COLLECTOR_PLUGIN_API_RESP]

# Mock raw data list
RAW_DATA_LIST = [{'id': 121}]

DATACLEAN_RESULT = {"result_table_id": "mock_result_table_id", "processing_id": "mock_processing_id"}

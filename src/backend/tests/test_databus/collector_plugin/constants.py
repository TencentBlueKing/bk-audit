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
    "bkbase_cluster_id": str(_REPLICA_WRITE_CLUSTER_ID),
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
    "has_replica_storage": False,
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

EXPECTED_EVENT_FIELDS = [
    {
        "field_name": "event_id",
        "field_type": "string",
        "field_alias": "事件ID",
        "is_dimension": False,
        "is_json": False,
        "field_index": 1,
        "is_index": True,
        "__field_type": "string",
    },
    {
        "field_name": "event_content",
        "field_type": "text",
        "field_alias": "事件描述",
        "is_dimension": False,
        "is_json": False,
        "field_index": 2,
        "is_index": False,
        "__field_type": "text",
    },
    {
        "field_name": "raw_event_id",
        "field_type": "string",
        "field_alias": "原始事件ID",
        "is_dimension": False,
        "is_json": False,
        "field_index": 3,
        "is_index": True,
        "__field_type": "string",
    },
    {
        "field_name": "strategy_id",
        "field_type": "long",
        "field_alias": "命中策略(ID)",
        "is_dimension": False,
        "is_json": False,
        "field_index": 4,
        "is_index": True,
        "__field_type": "long",
    },
    {
        "field_name": "event_evidence",
        "field_type": "text",
        "field_alias": "事件证据",
        "is_dimension": False,
        "is_json": True,
        "field_index": 5,
        "is_index": False,
        "__field_type": "object",
    },
    {
        "field_name": "event_type",
        "field_type": "text",
        "field_alias": "事件类型",
        "is_dimension": False,
        "is_json": False,
        "field_index": 6,
        "is_index": False,
        "__field_type": "text",
    },
    {
        "field_name": "event_data",
        "field_type": "text",
        "field_alias": "事件拓展数据",
        "is_dimension": False,
        "is_json": True,
        "field_index": 7,
        "is_index": False,
        "__field_type": "object",
    },
    {
        "field_name": "event_time",
        "field_type": "long",
        "field_alias": "事件发生时间",
        "is_dimension": False,
        "is_json": False,
        "field_index": 8,
        "is_index": False,
        "__field_type": "long",
    },
    {
        "field_name": "event_source",
        "field_type": "string",
        "field_alias": "事件来源",
        "is_dimension": False,
        "is_json": False,
        "field_index": 9,
        "is_index": False,
        "__field_type": "string",
    },
    {
        "field_name": "operator",
        "field_type": "text",
        "field_alias": "责任人",
        "is_dimension": False,
        "is_json": False,
        "field_index": 10,
        "is_index": False,
        "__field_type": "text",
    },
]

EXPECTED_ASSIGN_NORMAL = [
    {"type": "string", "assign_to": "event_id", "key": "event_id"},
    {"type": "text", "assign_to": "event_content", "key": "event_content"},
    {"type": "string", "assign_to": "raw_event_id", "key": "raw_event_id"},
    {"type": "long", "assign_to": "strategy_id", "key": "strategy_id"},
    {"type": "text", "assign_to": "event_type", "key": "event_type"},
    {"type": "long", "assign_to": "event_time", "key": "event_time"},
    {"type": "string", "assign_to": "event_source", "key": "event_source"},
    {"type": "text", "assign_to": "operator", "key": "operator"},
]

EXPECTED_ASSIGN_JSON = [
    {"type": "text", "assign_to": "event_evidence", "key": "event_evidence"},
    {"type": "text", "assign_to": "event_data", "key": "event_data"},
]

EXPECTED_CLEAN_JSON_CONFIG = {
    "extract": {
        "type": "fun",
        "method": "from_json",
        "result": "json_data",
        "label": "labelabcde",
        "args": [],
        "next": {
            "type": "branch",
            "name": "",
            "label": None,
            "next": [
                {
                    "type": "assign",
                    "subtype": "assign_obj",
                    "label": "labelfghij",
                    "assign": EXPECTED_ASSIGN_NORMAL,
                    "next": None,
                },
                {
                    "type": "assign",
                    "subtype": "assign_json",
                    "label": "labelklmno",
                    "assign": EXPECTED_ASSIGN_JSON,
                    "next": None,
                },
            ],
        },
    },
    "conf": {
        "time_format": "Unix Time Stamp(milliseconds)",
        "timezone": 0,
        "time_field_name": "event_time",
        "output_field_name": "timestamp",
        "timestamp_len": 13,
        "encoding": "UTF-8",
    },
}

EXPECTED_RESULT_TABLE_NAME = "bklog_event_plugin"
EXPECTED_CLEAN_CONFIG_NAME = "event_plugin"
EXPECTED_PHYSICAL_TABLE_NAME = f"mapleleaf_{settings.DEFAULT_BK_BIZ_ID}_bklog.event_plugin"

_DYNAMIC_JSON_FIELDS = {"event_evidence", "event_data"}

# Doris fields follow handler logic:
# - add physical_field and is_doc_values
# - dynamic JSON fields should not be marked as is_json; instead set is_original_json
EXPECTED_DORIS_FIELDS = []
for field in EXPECTED_EVENT_FIELDS:
    item = {
        "field_name": field["field_name"],
        "field_type": field["field_type"],
        "field_alias": field["field_alias"],
        "is_dimension": field["is_dimension"],
        "is_json": field["is_json"],
        "field_index": field["field_index"],
        "is_index": field["is_index"],
        "physical_field": field["field_name"],
        "is_doc_values": field["is_dimension"],
    }
    if field["field_name"] in _DYNAMIC_JSON_FIELDS:
        item["is_json"] = False
        item["is_original_json"] = True
    EXPECTED_DORIS_FIELDS.append(item)

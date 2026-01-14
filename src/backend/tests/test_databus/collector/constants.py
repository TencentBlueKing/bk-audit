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
import json
from unittest import mock

from django.conf import settings
from django.utils.translation import gettext_lazy

from apps.meta.utils.fields import STANDARD_FIELDS
from services.web.databus.constants import (
    DEFAULT_TARGET_OBJECT_TYPE,
    CollectorParamConditionMatchType,
    CollectorParamConditionTypeEnum,
    CustomTypeEnum,
    EtlConfigEnum,
    TargetNodeTypeChoices,
)
from tests.test_databus.collector_plugin.constants import PLUGIN_DATA as _PLUGIN_DATA
from tests.test_databus.collector_plugin.constants import PLUGIN_ID as _PLUGIN_ID
from tests.test_databus.collector_plugin.constants import PLUGIN_NAME as _PLUGIN_NAME
from tests.test_databus.collector_plugin.constants import (
    REPLICA_STORAGE_CLUSTER_CONFIG as _REPLICA_STORAGE_CLUSTER_CONFIG,
)
from tests.test_databus.storage.constants import CLUSTER_ID as _CLUSTER_ID
from tests.test_databus.storage.constants import CLUSTER_NAME as _CLUSTER_NAME
from tests.test_databus.storage.constants import PORT as _PORT
from tests.test_databus.storage.constants import SCHEMA as _SCHEMA

# CollectorPlugin
PLUGIN_ID = _PLUGIN_ID
PLUGIN_NAME = _PLUGIN_NAME
PLUGIN_DATA = copy.deepcopy(_PLUGIN_DATA)
REPLICA_STORAGE_CLUSTER_CONFIG = _REPLICA_STORAGE_CLUSTER_CONFIG

# Base
COLLECTOR_ID = 1
COLLECTOR_NAME = "test_collector"
COLLECTOR_DATA = {
    "system_id": settings.BK_IAM_SYSTEM_ID,
    "bk_biz_id": int(settings.DEFAULT_BK_BIZ_ID),
    "collector_plugin_id": PLUGIN_ID,
    "collector_config_id": COLLECTOR_ID,
    "collector_config_name": COLLECTOR_NAME,
    "collector_config_name_en": COLLECTOR_NAME,
    "record_log_type": "SDK",
    "select_sdk_type": "PYTHON_SDK",
}
RESULT_TABLE = f"{settings.DEFAULT_BK_BIZ_ID}_bklog_{COLLECTOR_NAME}"

# Get Collector
GET_COLLECTOR_RESULT_DATA = {
    **COLLECTOR_DATA,
    "bk_data_id": None,
    "custom_type": CustomTypeEnum.LOG.value,
    "bkbase_table_id": None,
    "processing_id": None,
    "has_storage": False,
    "description": None,
    "etl_config": None,
    "etl_params": {},
    "join_data_rt": None,
    "tail_log_time": None,
    "storage_changed": False,
    "auth_rt": False,
    "source_platform": "bk_log",
}

# Get Collector Info
API_BK_LOG_GET_COLLECTOR_DATA = {
    "created_at": "2022-01-01 00:00:00",
    "updated_at": "2022-12-31 00:00:00",
}
GET_COLLECTOR_INFO_DATA = {
    **GET_COLLECTOR_RESULT_DATA,
    **API_BK_LOG_GET_COLLECTOR_DATA,
    "fields": [],
}

CREATE_API_PUSH_DATA = {
    "namespace": settings.DEFAULT_NAMESPACE,
    "system_id": COLLECTOR_DATA.get("system_id"),
}
CREATE_API_PUSH_RESP = {"bk_data_id": None, "collector_config_id": COLLECTOR_ID + 1}
GET_API_PUSH_DATA = {
    "system_id": COLLECTOR_DATA.get("system_id"),
}
GET_API_PUSH_RESP = {
    "bk_data_token": "gjqguan_test_token",
    "bk_data_id": None,
    "collector_config_id": None,
    "collector_config_name": None,
    "collector_config_name_en": None,
}

# Create Collector
CREATE_COLLECTOR_DATA = {
    **COLLECTOR_DATA,
    "namespace": settings.DEFAULT_NAMESPACE,
    "target_object_type": DEFAULT_TARGET_OBJECT_TYPE,
    "target_node_type": TargetNodeTypeChoices.INSTANCE.value,
    "target_nodes": [{"id": 1, "bk_inst_id": 1, "bk_obj_id": 1, "ip": "127.0.0.1", "bk_cloud_id": 0}],
    "data_encoding": "UTF-8",
    "params": {
        "paths": ["/data/logs/test.log"],
        "conditions": {
            "type": CollectorParamConditionTypeEnum.MATCH.value,
            "match_type": CollectorParamConditionMatchType.INCLUDE.value,
            "match_content": "",
        },
    },
}
CREATE_COLLECTOR_RESULT = {
    **GET_COLLECTOR_RESULT_DATA,
    "description": COLLECTOR_NAME,
    "fields": [],
    "task_id_list": [],
    "collector_config_id": 3,
}
CREATE_COLLECTOR_API_RESP = {**GET_COLLECTOR_INFO_DATA, "collector_config_id": 3}

# Update Collector
UPDATE_COLLECTOR_DATA = {
    **CREATE_COLLECTOR_DATA,
    "collector_config_name": f"{COLLECTOR_NAME}_update_config",
    "collector_config_id": COLLECTOR_ID,
}
UPDATE_COLLECTOR_RESULT = {
    **CREATE_COLLECTOR_RESULT,
    "collector_config_name": UPDATE_COLLECTOR_DATA["collector_config_name"],
    "description": UPDATE_COLLECTOR_DATA["collector_config_name"],
    "collector_config_id": 1,
}
UPDATE_COLLECTOR_API_RESP = {
    **GET_COLLECTOR_INFO_DATA,
    "collector_config_name": UPDATE_COLLECTOR_DATA["collector_config_name"],
    "description": UPDATE_COLLECTOR_DATA["collector_config_name"],
    "collector_config_id": COLLECTOR_ID,
}

# Get BCS Yaml Template
GET_BCS_YAML_TEMPLATE_RESULT = {
    "yaml_config": (
        "IyDml6Xlv5fnsbvlnosKbG9nQ29uZmlnVHlwZTogY29udGFpbmVyX2xvZ19jb25maWcKIyDlkb3lkI3nqbrpl7TljLnphY0KbmFtZXNwYWNlU2"
        "VsZWN0b3I6CiAgIyDmmK/lkKbmiYDmnInnmoTlkb3lkI3nqbrpl7QKICBhbnk6IGZhbHNlCiAgIyDoi6Vhbnk9ZmFsc2XvvIzliJnpnIDopoHm"
        "j5Dkvpvlkb3lkI3nqbrpl7QKICBtYXRjaE5hbWVzOiAgW10KIyDlkb3lkI3nqbrpl7TkuIvmiYDmnInlrrnlmagKYWxsQ29udGFpbmVyOiBmYW"
        "xzZQojIOWuueWZqOWQjeWMuemFjQpjb250YWluZXJOYW1lTWF0Y2g6ICBbXQojIHdvcmtsb2FkIOWMuemFjQp3b3JrbG9hZE5hbWU6ICcnCndv"
        "cmtsb2FkVHlwZTogJycKIyBsYWJlbCDljLnphY0KbGFiZWxTZWxlY3RvcjoKICAjIGxhYmVsIOihqOi+vuW8j+WMuemFjQogIG1hdGNoRXhwcm"
        "Vzc2lvbnM6ICBbXQogICMgbGFiZWwg5YC85Yy56YWNCiAgbWF0Y2hMYWJlbHM6IHt9CiMg5pel5b+X6Lev5b6ECnBhdGg6CiAgLSAnJwojIOaX"
        "peW/l+Wtl+espumbhgplbmNvZGluZzogVVRGLTgKIyDliIbpmpTnrKbov4fmu6QKZGVsaW1pdGVyOiBudWxsCiMg6L+H5ruk5YaF5a65CmZpbH"
        "RlcnM6ICBbXQ=="
    )
}

# Create BCS Collector
BCS_COLLECTOR_ID = 2
CREATE_BCS_COLLECTOR_DATA = {
    **COLLECTOR_DATA,
    "collector_config_id": BCS_COLLECTOR_ID,
    "namespace": settings.DEFAULT_NAMESPACE,
    "bcs_cluster_id": 1,
    "yaml_config": GET_BCS_YAML_TEMPLATE_RESULT["yaml_config"],
}
CREATE_BCS_COLLECTOR_API_RESP = {**GET_COLLECTOR_INFO_DATA, "collector_config_id": BCS_COLLECTOR_ID}
CREATE_BCS_COLLECTOR_RESULT = {
    **GET_COLLECTOR_RESULT_DATA,
    "description": COLLECTOR_NAME,
    "fields": [],
    "collector_config_id": BCS_COLLECTOR_ID,
}

# Update BCS Collector
UPDATE_BCS_COLLECTOR_API_RESP = {**GET_COLLECTOR_INFO_DATA, "collector_config_id": BCS_COLLECTOR_ID}
UPDATE_BCS_COLLECTOR_DATA = {
    **CREATE_BCS_COLLECTOR_DATA,
    "collector_config_name": f"{COLLECTOR_NAME}_updated",
    "collector_config_id": COLLECTOR_ID,
}
UPDATE_BCS_COLLECTOR_RESULT = {
    **GET_COLLECTOR_RESULT_DATA,
    "collector_config_name": UPDATE_BCS_COLLECTOR_DATA["collector_config_name"],
    "description": UPDATE_BCS_COLLECTOR_DATA["collector_config_name"],
    "fields": [],
}

# Collector Status
COLLECTOR_STATUS_RESULT = {
    "last_time": "",
    "status": "nodata",
    "status_msg": gettext_lazy("无数据"),
    "system_id": "bk-audit",
    "collector_count": 1,
}
COLLECTOR_STATUS_RESULT_NODATA = {
    "last_time": "",
    "status": "unset",
    "status_msg": gettext_lazy("未配置"),
    "system_id": "bk-audittest",
    "collector_count": 0,
}
COLLECTOR_STATUS_RESULT_NORMAL = {
    "last_time": "2022-01-01 00:00:00",
    "status": "normal",
    "status_msg": gettext_lazy("正常"),
    "system_id": "bk-audit",
    "collector_count": 1,
}

# Collector Etl
COLLECTOR_ETL_FIELDS = [
    {
        "field_name": field.field_name,
        "field_type": field.field_type,
        "alias_name": field.alias_name,
        "is_text": field.is_text,
        "is_time": field.is_time,
        "is_json": field.is_json,
        "is_analyzed": field.is_analyzed,
        "is_dimension": field.is_dimension,
        "is_delete": field.is_delete,
        "is_required": field.is_required,
        "is_display": field.is_display,
        "is_built_in": field.is_built_in,
        "option": {"key": field.field_name, "path": field.field_name},
        "description": str(field.description),
        "priority_index": field.priority_index,
    }
    for field in STANDARD_FIELDS
    if field.is_required and field.is_display
]
CREATE_COLLECTOR_ETL_DATA = {
    "collector_config_id": COLLECTOR_ID,
    "namespace": settings.DEFAULT_NAMESPACE,
    "etl_config": EtlConfigEnum.BK_LOG_JSON.value,
    "etl_params": {},
    "fields": COLLECTOR_ETL_FIELDS,
}
CREATE_COLLECTOR_ETL_API_RESP = {"result_table_id": RESULT_TABLE, "processing_id": RESULT_TABLE}
STORAGE_CLUSTER_ID = _CLUSTER_ID
STORAGE_CLUSTER_NAME = _CLUSTER_NAME
STORAGE_CLUSTER_DEMAIN = _CLUSTER_NAME
STORAGE_CLUSTER_PORT = _PORT
STORAGE_CLUSTER_SCHEMA = _SCHEMA
STORAGE_LIST = [
    {
        "cluster_config": {
            "cluster_id": STORAGE_CLUSTER_ID,
            "cluster_name": STORAGE_CLUSTER_NAME,
            "domain_name": STORAGE_CLUSTER_DEMAIN,
            "port": STORAGE_CLUSTER_PORT,
            "schema": STORAGE_CLUSTER_SCHEMA,
            "custom_option": {
                "bk_biz_id": settings.DEFAULT_BK_BIZ_ID,
                "hot_warm_config": {"is_enabled": False},
                "source_type": "custom",
                "setup_config": {},
                "admin": [],
                "description": STORAGE_CLUSTER_NAME,
                "bkbase_cluster_id": STORAGE_CLUSTER_ID,
                "visible_config": {},
                "cluster_namespace": settings.DEFAULT_NAMESPACE,
            },
            "creator": "admin",
            "create_time": "2022-01-01 00:00:00",
        },
        "auth_info": {"username": "admin", "password": ""},
        "bk_biz_id": settings.DEFAULT_BK_BIZ_ID,
    }
]

# ETL Preview
ETL_PREVIEW_DATA = {
    "data": '{"date": "2022-01-01 00:00:00"}',
    "etl_config": EtlConfigEnum.BK_LOG_JSON.value,
    "etl_params": {},
}
ETL_PREVIEW_RESULT = [{"key": "date", "path": "date", "val": "2022-01-01 00:00:00"}]

# Toggle Join Data
SYSTEM_HOST = "https://bk.tencent.com"
SYSTEM_TOKEN = "1234567890"
RESOURCE_TYPE_ID = "system"
TOGGLE_JOIN_DATA = {"is_enabled": True, "system_id": settings.BK_IAM_SYSTEM_ID, "resource_type_id": RESOURCE_TYPE_ID}
RAW_DATA_ID = 121
CREATE_DEPLOY_PLAN_RESULT = {'raw_data_id': RAW_DATA_ID}
RESOURCE_TYPE_SCHEMA = [
    {"id": "id", "type": "string", "description_en": "id", "description": "敏感ID"},
    {"id": "created_at", "type": "string", "description_en": "created_at", "description": "创建时间"},
    {"id": "created_by", "type": "string", "description_en": "created_by", "description": "创建者"},
    {"id": "updated_at", "type": "string", "description_en": "updated_at", "description": "更新时间"},
    {"id": "updated_by", "type": "string", "description_en": "updated_by", "description": "修改者"},
    {"id": "is_deleted", "type": "boolean", "description_en": "is_deleted", "description": "是否删除"},
    {"id": "name", "type": "string", "description_en": "name", "description": "名称"},
    {"id": "system_id", "type": "string", "description_en": "system_id", "description": "系统ID"},
    {"id": "resource_type", "type": "string", "description_en": "resource_type", "description": "资源类型"},
    {"id": "resource_id", "type": "string", "description_en": "resource_id", "description": "资源ID"},
    {"id": "fields", "type": "string", "description_en": "fields", "description": "关联字段"},
    {"id": "priority_index", "type": "integer", "description_en": "priority_index", "description": "优先指数"},
    {"id": "is_private", "type": "boolean", "description_en": "is_private", "description": "是否隐藏"},
]


class SessionMock(mock.MagicMock):
    status_code = 200

    def __call__(self, *args, **kwargs):
        return self

    def post(self, *args, **kwargs):
        return self

    def json(self):
        return {"result": True}

    def content(self):
        return json.dumps(self.json())


class ErrorSessionMock(SessionMock):
    status_code = 500


# Etl Field History
ETL_FIELD_HISTORY_RESULT = {}

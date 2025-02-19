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

import datetime
from copy import deepcopy

from django.conf import settings

from core.models import get_request_username
from services.web.databus.constants import (
    DEFAULT_ALLOCATION_MIN_DAYS,
    DEFAULT_RETENTION,
    DEFAULT_STORAGE_REPLIES,
)

# Base
CLUSTER_ID = 1
REPLICA_WRITE_CLUSTER_ID = 2
CLUSTER_NAME = "test_storage"
USERNAME = get_request_username()
PORT = 9200
SCHEMA = "http"
SOURCE_TYPE = "custom"
AUTH_INFO = {"username": USERNAME, "password": ""}
ENABLE_HOT_WARM = False
ALLOCATION_MIN_DAYS = DEFAULT_ALLOCATION_MIN_DAYS
STORAGE_DATA = {
    "cluster_config": {
        "cluster_id": CLUSTER_ID,
        "cluster_name": CLUSTER_NAME,
        "domain_name": CLUSTER_NAME,
        "port": PORT,
        "schema": SCHEMA,
        "enable_hot_warm": ENABLE_HOT_WARM,
        "custom_option": {
            "bk_biz_id": int(settings.DEFAULT_BK_BIZ_ID),
            "hot_warm_config": {
                "is_enabled": False,
                "hot_attr_name": "",
                "hot_attr_value": "",
                "warm_attr_name": "",
                "warm_attr_value": "",
            },
            "bkbase_cluster_id": "2",
            "source_type": SOURCE_TYPE,
            "setup_config": {
                "retention_days_default": DEFAULT_RETENTION,
                "number_of_replicas_default": DEFAULT_STORAGE_REPLIES,
                "retention_days_max": DEFAULT_RETENTION,
                "number_of_replicas_max": DEFAULT_STORAGE_REPLIES,
            },
            "admin": [USERNAME],
            "description": CLUSTER_NAME,
            "option": {},
            "cluster_namespace": settings.DEFAULT_NAMESPACE,
            "visible_config": {},
        },
        "creator": USERNAME,
        "create_time": "2022-01-01 00:00:00",
    },
    "auth_info": AUTH_INFO,
    "bk_biz_id": int(settings.DEFAULT_BK_BIZ_ID),
}

# Storage Activate
CACHE_API_RESP = {"change_storage_cluster_running_key": None}
STORAGE_ACTIVATE_PARAMS = {"namespace": settings.DEFAULT_NAMESPACE, "cluster_id": CLUSTER_ID}
REPLICA_STORAGE_ACTIVATE_PARAMS = {
    "namespace": settings.DEFAULT_NAMESPACE,
    "cluster_id": REPLICA_WRITE_CLUSTER_ID,
    'cluster_mode': 'replica',
}

# Storage List
GET_STORAGES_API_RESP = [STORAGE_DATA]
STORAGE_LIST_PARAMS = {"namespace": settings.DEFAULT_NAMESPACE, "keyword": CLUSTER_NAME}
STORAGE_OPERATE_LOG_DATA = {
    "cluster_id": CLUSTER_ID,
    "operator": USERNAME,
    "operate_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "request_id": "",
}
STORAGE_LIST_DATA = []
for item in GET_STORAGES_API_RESP:
    item["cluster_config"]["custom_option"]["option"].update(
        {
            "is_default": False,
            "updater": STORAGE_OPERATE_LOG_DATA["operator"],
            "update_at": STORAGE_OPERATE_LOG_DATA["operate_at"],
            "creator": STORAGE_OPERATE_LOG_DATA["operator"],
            "create_at": STORAGE_OPERATE_LOG_DATA["operate_at"],
        }
    )
    item["cluster_config"]["custom_option"]["allocation_min_days"] = ALLOCATION_MIN_DAYS
    STORAGE_LIST_DATA.append(item)

# Create Storage
STORAGE_ACTIVATE_API_RESP = CLUSTER_ID
CREATE_STORAGE_API_RESP = STORAGE_DATA
CREATE_STORAGE_PARAMS = {
    "namespace": settings.DEFAULT_NAMESPACE,
    "cluster_name": CLUSTER_NAME,
    "bkbase_cluster_en_name": CLUSTER_NAME,
    "domain_name": CLUSTER_NAME,
    "port": PORT,
    "schema": SCHEMA,
    "source_type": SOURCE_TYPE,
    "auth_info": AUTH_INFO,
    "enable_hot_warm": ENABLE_HOT_WARM,
    "allocation_min_days": ALLOCATION_MIN_DAYS,
    "hot_attr_name": "",
    "hot_attr_value": "",
    "warm_attr_name": "",
    "warm_attr_value": "",
    "setup_config": {
        "retention_days_default": DEFAULT_RETENTION,
        "number_of_replicas_default": DEFAULT_STORAGE_REPLIES,
        "retention_days_max": DEFAULT_RETENTION,
        "number_of_replicas_max": DEFAULT_STORAGE_REPLIES,
    },
    "admin": [USERNAME],
    "description": CLUSTER_NAME,
}
CREATE_REPLICA_STORAGE_PARAMS = deepcopy(CREATE_STORAGE_PARAMS)
CREATE_REPLICA_STORAGE_PARAMS["pre_defined_extra_config"] = {
    "cluster_id": REPLICA_WRITE_CLUSTER_ID,
    "bkbase_cluster_id": REPLICA_WRITE_CLUSTER_ID,
}

CREATE_STORAGE_DATA = CREATE_STORAGE_API_RESP

# Create Or Update Redis
CREATE_OR_UPDATE_REDIS_PARAMS = {
    "namespace": settings.DEFAULT_NAMESPACE,
    "redis_name_en": "1",
    "redis_name": "redis_name",
    "connection_info": {
        "enable_sentinel": False,
        "name_sentinel": "name_sentinel",
        "host_sentinel": "host_sentinel",
        "port_sentinel": 0,
        "host": "host",
        "port": 0,
        "password": "password",
    },
    "version": "V1.0.0",
}
CREATE_OR_UPDATE_REDIS_DATA = {
    "namespace": settings.DEFAULT_NAMESPACE,
    "redis_name_en": "1",
    "redis_name": "redis_name",
    "admin": [USERNAME],
    "connection_info": {
        "enable_sentinel": False,
        "name_sentinel": "name_sentinel",
        "host_sentinel": "host_sentinel",
        "port_sentinel": 0,
        "host": "host",
        "port": 0,
        "password": "password",
    },
    "version": "V1.0.0",
    "extra": {},
}

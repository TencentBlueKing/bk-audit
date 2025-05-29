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

from apps.meta.utils.fields import (
    ACCESS_SOURCE_IP,
    ACCESS_TYPE,
    ACCESS_USER_AGENT,
    ACTION_ID,
    BK_APP_CODE,
    CLOUD_ID,
    COLLECTOR_CONFIG_ID,
    END_TIME,
    EVENT_CONTENT,
    EVENT_ID,
    EXT_FIELD_CONFIG,
    EXTEND_DATA,
    GSE_INDEX,
    INSTANCE_DATA,
    INSTANCE_ID,
    INSTANCE_NAME,
    INSTANCE_ORIGIN_DATA,
    ITERATION_INDEX,
    LOG,
    PATH,
    REQUEST_ID,
    RESOURCE_TYPE_ID,
    RESULT_CODE,
    RESULT_CONTENT,
    SCOPE_ID,
    SCOPE_TYPE,
    SERVER_IP,
    SNAPSHOT_ACTION_INFO,
    SNAPSHOT_INSTANCE_DATA,
    SNAPSHOT_INSTANCE_NAME,
    SNAPSHOT_RESOURCE_TYPE_INFO,
    SNAPSHOT_USER_INFO,
    START_TIME,
    SYSTEM_ID,
    USER_IDENTIFY_SRC,
    USER_IDENTIFY_SRC_USERNAME,
    USER_IDENTIFY_TENANT_ID,
    USER_IDENTIFY_TYPE,
    USERNAME,
    get_field_map,
)

# 日志检索标准字段
LOG_SEARCH_STANDARD_FIELDS = [
    START_TIME,
    END_TIME,
    EVENT_ID,
    USERNAME,
    ACTION_ID,
    RESOURCE_TYPE_ID,
    INSTANCE_ID,
    INSTANCE_NAME,
    RESULT_CODE,
    SCOPE_TYPE,
    SCOPE_ID,
    REQUEST_ID,
    EVENT_CONTENT,
    USER_IDENTIFY_TYPE,
    USER_IDENTIFY_TENANT_ID,
    USER_IDENTIFY_SRC,
    USER_IDENTIFY_SRC_USERNAME,
    ACCESS_TYPE,
    ACCESS_SOURCE_IP,
    ACCESS_USER_AGENT,
    INSTANCE_DATA,
    INSTANCE_ORIGIN_DATA,
    RESULT_CONTENT,
    EXTEND_DATA,
    BK_APP_CODE,
]
LOG_SEARCH_STANDARD_FIELDS_MAP = get_field_map(LOG_SEARCH_STANDARD_FIELDS)

# 日志检索快照字段
LOG_SEARCH_SNAPSHOT_FIELDS = [
    SNAPSHOT_RESOURCE_TYPE_INFO,
    SNAPSHOT_ACTION_INFO,
    SNAPSHOT_USER_INFO,
    SNAPSHOT_INSTANCE_NAME,
    SNAPSHOT_INSTANCE_DATA,
]
LOG_SEARCH_SNAPSHOT_FIELDS_MAP = get_field_map(LOG_SEARCH_SNAPSHOT_FIELDS)

# 日志检索系统字段
LOG_SEARCH_SYSTEM_FIELDS = [
    SYSTEM_ID,
    COLLECTOR_CONFIG_ID,
    LOG,
    CLOUD_ID,
    SERVER_IP,
    PATH,
    GSE_INDEX,
    ITERATION_INDEX,
    EXT_FIELD_CONFIG,
]
LOG_SEARCH_SYSTEM_FIELDS_MAP = get_field_map(LOG_SEARCH_SYSTEM_FIELDS)

# 所有日志检索字段
LOG_SEARCH_ALL_FIELDS = LOG_SEARCH_STANDARD_FIELDS + LOG_SEARCH_SNAPSHOT_FIELDS + LOG_SEARCH_SYSTEM_FIELDS
LOG_SEARCH_ALL_FIELDS_MAP = (
    LOG_SEARCH_STANDARD_FIELDS_MAP | LOG_SEARCH_SNAPSHOT_FIELDS_MAP | LOG_SEARCH_SYSTEM_FIELDS_MAP
)

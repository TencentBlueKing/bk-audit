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

from typing import Union

from django.conf import settings
from django.utils.translation import gettext_lazy

from apps.meta.models import Field

FIELD_TYPE_STRING = "string"
FIELD_TYPE_OBJECT = "object"
FIELD_TYPE_TEXT = "text"
FIELD_TYPE_INT = "int"
FIELD_TYPE_LONG = "long"
FIELD_TYPE_DOUBLE = "double"
FIELD_TYPE_KEYWORD = "keyword"
FIELD_TYPE_NESTED = "nested"

SPEC_FIELD_TYPE_TIMESTAMP = "timestamp"
SPEC_FIELD_TYPE_USER = "user"

BKDATA_ES_TYPE_MAP = {
    FIELD_TYPE_INT: FIELD_TYPE_INT,
    FIELD_TYPE_LONG: FIELD_TYPE_LONG,
    FIELD_TYPE_KEYWORD: FIELD_TYPE_STRING,
    FIELD_TYPE_TEXT: FIELD_TYPE_TEXT,
    FIELD_TYPE_DOUBLE: FIELD_TYPE_DOUBLE,
    FIELD_TYPE_OBJECT: FIELD_TYPE_TEXT,
    FIELD_TYPE_NESTED: FIELD_TYPE_TEXT,
    FIELD_TYPE_STRING: FIELD_TYPE_STRING,
}

PY_FIELD_TYPE_STR = Union[int, float, bool, str, list, dict, tuple, None]
PY_FIELD_TYPE_INT = Union[int, None]
PY_FIELD_TYPE_FLOAT = Union[int, float, None]
PY_FIELD_TYPE_OBJ = Union[list, dict, str, None]
PYTHON_FIELD_TYPE_MAP = {
    FIELD_TYPE_INT: PY_FIELD_TYPE_INT,
    FIELD_TYPE_LONG: PY_FIELD_TYPE_INT,
    FIELD_TYPE_KEYWORD: PY_FIELD_TYPE_STR,
    FIELD_TYPE_TEXT: PY_FIELD_TYPE_STR,
    FIELD_TYPE_DOUBLE: PY_FIELD_TYPE_FLOAT,
    FIELD_TYPE_OBJECT: PY_FIELD_TYPE_OBJ,
    FIELD_TYPE_NESTED: PY_FIELD_TYPE_STR,
    FIELD_TYPE_STRING: PY_FIELD_TYPE_STR,
}
PYTHON_TO_ES = {
    str: FIELD_TYPE_STRING,
    int: FIELD_TYPE_INT,
    list: FIELD_TYPE_OBJECT,
    dict: FIELD_TYPE_OBJECT,
    float: FIELD_TYPE_DOUBLE,
}

EVENT_ID = Field(
    field_name="event_id",
    alias_name="event_id",
    field_type=FIELD_TYPE_STRING,
    description=gettext_lazy("事件ID"),
    option=dict(),
    priority_index=100,
    is_index=True,
)

EVENT_CONTENT = Field(
    field_name="event_content",
    alias_name="event_content",
    field_type=FIELD_TYPE_TEXT,
    description=gettext_lazy("事件描述"),
    is_analyzed=True,
    is_zh_analyzed=True,
    option=dict(),
    is_required=False,
    priority_index=99,
)

ACTION_ID = Field(
    field_name="action_id",
    alias_name="action_id",
    field_type=FIELD_TYPE_STRING,
    description=gettext_lazy("操作ID"),
    option=dict(),
    priority_index=98,
    is_index=True,
)

REQUEST_ID = Field(
    field_name="request_id",
    alias_name="request_id",
    field_type=FIELD_TYPE_STRING,
    description=gettext_lazy("请求ID"),
    option=dict(),
    is_required=False,
    priority_index=97,
)

USERNAME = Field(
    field_name="username",
    alias_name="username",
    field_type=FIELD_TYPE_STRING,
    description=gettext_lazy("操作人"),
    option=dict(),
    priority_index=96,
    is_index=True,
    property={'spec_field_type': SPEC_FIELD_TYPE_USER},
)

USER_IDENTIFY_TYPE = Field(
    field_name="user_identify_type",
    alias_name="user_identify_type",
    field_type=FIELD_TYPE_INT,
    description=gettext_lazy("操作人账号类型"),
    option=dict(),
    is_required=False,
    priority_index=95,
)

USER_IDENTIFY_TENANT_ID = Field(
    field_name="user_identify_tenant_id",
    alias_name="user_identify_tenant_id",
    field_type=FIELD_TYPE_STRING,
    description=gettext_lazy("操作人租户ID"),
    option=dict(),
    is_required=False,
    priority_index=94,
)

USER_IDENTIFY_SRC = Field(
    field_name="user_identify_src",
    alias_name="user_identify_src",
    field_type=FIELD_TYPE_STRING,
    description=gettext_lazy("操作人账号来源"),
    option=dict(),
    is_required=False,
    priority_index=93,
)

USER_IDENTIFY_SRC_USERNAME = Field(
    field_name="user_identify_src_username",
    alias_name="user_identify_src_username",
    field_type=FIELD_TYPE_STRING,
    description=gettext_lazy("操作人账号"),
    option=dict(),
    is_required=False,
    priority_index=92,
)

START_TIME = Field(
    field_name="start_time",
    alias_name="start_time",
    field_type=FIELD_TYPE_LONG,
    description=gettext_lazy("操作起始时间"),
    is_time=True,
    option=dict(),
    priority_index=91,
    property={'spec_field_type': SPEC_FIELD_TYPE_TIMESTAMP},
)

END_TIME = Field(
    field_name="end_time",
    alias_name="end_time",
    field_type=FIELD_TYPE_LONG,
    description=gettext_lazy("操作结束时间"),
    is_time=False,
    option=dict(),
    is_required=False,
    priority_index=90,
    property={'spec_field_type': SPEC_FIELD_TYPE_TIMESTAMP},
)

BK_APP_CODE = Field(
    field_name="bk_app_code",
    alias_name="bk_app_code",
    field_type=FIELD_TYPE_STRING,
    description=gettext_lazy("事件上报模块"),
    option=dict(),
    is_required=False,
    priority_index=89,
)

SCOPE_TYPE = Field(
    field_name="scope_type",
    alias_name="scope_type",
    field_type=FIELD_TYPE_STRING,
    description=gettext_lazy("管理空间类型"),
    option=dict(),
    is_required=False,
    is_display=True,
    priority_index=88,
    is_index=True,
)

SCOPE_ID = Field(
    field_name="scope_id",
    alias_name="scope_id",
    field_type=FIELD_TYPE_STRING,
    description=gettext_lazy("管理空间ID"),
    option=dict(),
    is_required=False,
    is_display=True,
    priority_index=87,
    is_index=True,
)

ACCESS_TYPE = Field(
    field_name="access_type",
    alias_name="access_type",
    field_type=FIELD_TYPE_INT,
    description=gettext_lazy("操作途径"),
    option=dict(),
    priority_index=86,
)

ACCESS_SOURCE_IP = Field(
    field_name="access_source_ip",
    alias_name="access_source_ip",
    field_type=FIELD_TYPE_STRING,
    description=gettext_lazy("来源IP"),
    option=dict(),
    is_required=False,
    priority_index=85,
)

ACCESS_USER_AGENT = Field(
    field_name="access_user_agent",
    alias_name="access_user_agent",
    field_type=FIELD_TYPE_TEXT,
    description=gettext_lazy("客户端类型"),
    is_analyzed=True,
    is_zh_analyzed=True,
    option=dict(),
    is_required=False,
    priority_index=84,
)

RESOURCE_TYPE_ID = Field(
    field_name="resource_type_id",
    alias_name="resource_type_id",
    field_type=FIELD_TYPE_STRING,
    description=gettext_lazy("资源类型ID"),
    option=dict(),
    is_required=False,
    priority_index=83,
)

INSTANCE_ID = Field(
    field_name="instance_id",
    alias_name="instance_id",
    field_type=FIELD_TYPE_TEXT,
    description=gettext_lazy("资源实例ID"),
    is_analyzed=True,
    option={"es_analyzer": "delimiter_analyzer"},
    is_required=False,
    priority_index=82,
)

INSTANCE_NAME = Field(
    field_name="instance_name",
    alias_name="instance_name",
    field_type=FIELD_TYPE_TEXT,
    description=gettext_lazy("资源实例名"),
    is_analyzed=True,
    is_zh_analyzed=True,
    option=dict(),
    is_required=False,
    priority_index=81,
)

INSTANCE_DATA = Field(
    field_name="instance_data",
    alias_name="instance_data",
    field_type=FIELD_TYPE_OBJECT,
    description=gettext_lazy("实例当前内容"),
    is_analyzed=True,
    is_json=True,
    option={"meta_field_type": FIELD_TYPE_TEXT},
    is_required=False,
    priority_index=80,
)

INSTANCE_ORIGIN_DATA = Field(
    field_name="instance_origin_data",
    alias_name="instance_origin_data",
    field_type=FIELD_TYPE_OBJECT,
    description=gettext_lazy("实例变更前内容"),
    is_analyzed=True,
    is_json=True,
    option={"meta_field_type": FIELD_TYPE_TEXT},
    is_required=False,
    priority_index=79,
)

RESULT_CODE = Field(
    field_name="result_code",
    alias_name="result_code",
    field_type=FIELD_TYPE_INT,
    description=gettext_lazy("操作结果"),
    option=dict(),
    is_required=False,
    priority_index=78,
)

RESULT_CONTENT = Field(
    field_name="result_content",
    alias_name="result_content",
    field_type=FIELD_TYPE_TEXT,
    description=gettext_lazy("操作结果描述"),
    is_analyzed=True,
    is_zh_analyzed=True,
    option=dict(),
    is_required=False,
    priority_index=77,
)

EXTEND_DATA = Field(
    field_name="extend_data",
    alias_name="extend_data",
    field_type=FIELD_TYPE_OBJECT,
    description=gettext_lazy("拓展数据"),
    is_analyzed=True,
    is_json=True,
    option={"meta_field_type": FIELD_TYPE_TEXT},
    is_required=False,
    priority_index=76,
)

SNAPSHOT_USER_INFO = Field(
    field_name="snapshot_user_info",
    alias_name="snapshot_user_info",
    field_type=FIELD_TYPE_OBJECT,
    description=gettext_lazy("用户信息快照"),
    option=dict(),
    is_required=False,
    is_display=False,
    is_json=True,
)

SNAPSHOT_RESOURCE_TYPE_INFO = Field(
    field_name="snapshot_resource_type_info",
    alias_name="snapshot_resource_type_info",
    field_type=FIELD_TYPE_OBJECT,
    description=gettext_lazy("资源类型快照"),
    option=dict(),
    is_required=False,
    is_display=False,
    is_json=True,
)

SNAPSHOT_ACTION_INFO = Field(
    field_name="snapshot_action_info",
    alias_name="snapshot_action_info",
    field_type=FIELD_TYPE_OBJECT,
    description=gettext_lazy("操作快照"),
    option=dict(),
    is_required=False,
    is_display=False,
    is_json=True,
    priority_index=USERNAME.priority_index,
)

SNAPSHOT_INSTANCE_NAME = Field(
    field_name="snapshot_instance_name",
    alias_name="snapshot_instance_name",
    field_type=FIELD_TYPE_TEXT,
    description=gettext_lazy("实例名称快照"),
    is_analyzed=True,
    is_zh_analyzed=True,
    option=dict(),
    is_required=False,
    is_display=False,
)

SNAPSHOT_INSTANCE_DATA = Field(
    field_name="snapshot_instance_data",
    alias_name="snapshot_instance_data",
    field_type=FIELD_TYPE_TEXT,
    description=gettext_lazy("实例信息快照"),
    is_analyzed=False,
    is_zh_analyzed=False,
    option=dict(),
    is_required=False,
    is_display=False,
    is_json=True,
)

SYSTEM_ID = Field(
    field_name="system_id",
    alias_name="system_id",
    field_type=FIELD_TYPE_STRING,
    description=gettext_lazy("来源系统"),
    option=dict(),
    is_required=True,
    is_display=False,
    is_index=True,
)

LOG = Field(
    field_name="log",
    alias_name="log",
    field_type=FIELD_TYPE_TEXT,
    description=gettext_lazy("原始数据内容"),
    option=dict(),
    is_required=False,
    is_display=False,
    is_analyzed=True,
)

COLLECTOR_CONFIG_ID = Field(
    field_name="collector_config_id",
    alias_name="collector_config_id",
    field_type=FIELD_TYPE_INT,
    description=gettext_lazy("采集项ID"),
    option=dict(),
    is_required=True,
    is_display=False,
)

BK_DATA_ID = Field(
    field_name="bk_data_id",
    alias_name="bk_data_id",
    field_type=FIELD_TYPE_INT,
    description=gettext_lazy("数据源ID"),
    option=dict(),
    is_required=True,
    is_display=False,
)

VERSION_ID = Field(
    field_name=f"version_{settings.INDEX_VERSION_NUMBER}",
    alias_name=f"version_{settings.INDEX_VERSION_NUMBER}",
    field_type=FIELD_TYPE_STRING,
    description=gettext_lazy("索引版本号"),
    option=dict(),
    is_required=False,
    is_display=False,
)

REPORT_TIME = Field(
    field_name="bk_receive_time",
    alias_name="bk_receive_time",
    field_type=FIELD_TYPE_LONG,
    description=gettext_lazy("上报时间"),
    option=dict(),
    is_required=True,
    is_display=False,
    property={'spec_field_type': SPEC_FIELD_TYPE_TIMESTAMP},
)

STORAGE_TIME = Field(
    field_name="bk_storage_time",
    alias_name="bk_storage_time",
    field_type=FIELD_TYPE_LONG,
    description=gettext_lazy("入库时间"),
    option=dict(),
    is_required=True,
    is_display=False,
    property={'spec_field_type': SPEC_FIELD_TYPE_TIMESTAMP},
)

STANDARD_FIELDS = [
    EVENT_ID,
    EVENT_CONTENT,
    ACTION_ID,
    REQUEST_ID,
    USERNAME,
    USER_IDENTIFY_TYPE,
    USER_IDENTIFY_TENANT_ID,
    USER_IDENTIFY_SRC,
    USER_IDENTIFY_SRC_USERNAME,
    START_TIME,
    END_TIME,
    BK_APP_CODE,
    SCOPE_TYPE,
    SCOPE_ID,
    ACCESS_TYPE,
    ACCESS_SOURCE_IP,
    ACCESS_USER_AGENT,
    RESOURCE_TYPE_ID,
    INSTANCE_ID,
    INSTANCE_NAME,
    INSTANCE_DATA,
    INSTANCE_ORIGIN_DATA,
    RESULT_CODE,
    RESULT_CONTENT,
    EXTEND_DATA,
    SNAPSHOT_USER_INFO,
    SNAPSHOT_RESOURCE_TYPE_INFO,
    SNAPSHOT_ACTION_INFO,
    SNAPSHOT_INSTANCE_NAME,
    SNAPSHOT_INSTANCE_DATA,
    SYSTEM_ID,
    COLLECTOR_CONFIG_ID,
    BK_DATA_ID,
    VERSION_ID,
    REPORT_TIME,
    STORAGE_TIME,
]

# 这些字段 key 非固定，无法在 ES 中作为 json 字段
DYNAMIC_JSON_FIELDS = [
    INSTANCE_DATA,
    INSTANCE_ORIGIN_DATA,
    EXTEND_DATA,
    SNAPSHOT_INSTANCE_DATA,
]

BKAUDIT_BUILD_IN_FIELDS = {
    SYSTEM_ID,
    COLLECTOR_CONFIG_ID,
    BK_DATA_ID,
}

EXT_FIELD_CONFIG = Field(
    field_name="__ext",
    alias_name="__ext",
    field_type=FIELD_TYPE_OBJECT,
    description=gettext_lazy("拓展字段"),
    option={"path": "ext"},
    is_json=True,
    is_dimension=False,
    is_display=False,
)

FLOW_MD5 = Field(
    field_name="flow_md5",
    alias_name="flow_md5",
    field_type=FIELD_TYPE_STRING,
    description=gettext_lazy("数据开发任务MD5"),
    option={},
    is_dimension=True,
    is_display=False,
)

AIOPS_START_TIME = Field(
    field_name="_startTime_",
    alias_name="_startTime_",
    field_type=FIELD_TYPE_STRING,
    description=gettext_lazy("AIOPS开始时间"),
    option={},
    is_dimension=False,
    is_display=False,
)

AIOPS_END_TIME = Field(
    field_name="_endTime_",
    alias_name="_endTime_",
    field_type=FIELD_TYPE_STRING,
    description=gettext_lazy("AIOPS结束时间"),
    option={},
    is_dimension=False,
    is_display=False,
)

GROUP_ID = Field(
    field_name="__group_id__",
    alias_name="__group_id__",
    field_type=FIELD_TYPE_STRING,
    description=gettext_lazy("分组ID"),
    option={},
    is_dimension=True,
    is_display=False,
)

BUILD_IN_ID = Field(
    field_name="__id__",
    alias_name="__id__",
    field_type=FIELD_TYPE_STRING,
    description=gettext_lazy("ID"),
    option={},
    is_dimension=True,
    is_display=False,
)

BUILD_IN_INDEX = Field(
    field_name="__index__",
    alias_name="__index__",
    field_type=FIELD_TYPE_STRING,
    description=gettext_lazy("Index"),
    option={},
    is_dimension=True,
    is_display=False,
)

BUILD_IN_COPY = Field(
    field_name="_copy",
    alias_name="_copy",
    field_type=FIELD_TYPE_STRING,
    description=gettext_lazy("Copy"),
    option={},
    is_dimension=True,
    is_display=False,
)

TIMESTAMP = Field(
    field_name="timestamp",
    alias_name="timestamp",
    field_type=FIELD_TYPE_LONG,
    description=gettext_lazy("Timestamp"),
    option={},
    is_dimension=False,
    is_display=False,
)

AIOPS_EXTRA_INFO = Field(
    field_name="__extra_info__",
    alias_name="__extra_info__",
    field_type=FIELD_TYPE_STRING,
    description=gettext_lazy("AIOPS拓展信息"),
    option={},
    is_dimension=False,
    is_display=False,
)

DT_EVENT_TIME = Field(
    field_name="dtEventTime",
    alias_name="dtEventTime",
    field_type=FIELD_TYPE_STRING,
    description=gettext_lazy("AIOPS内置数据时间"),
    option={},
    is_dimension=False,
    is_display=False,
)

LOCAL_TIME = Field(
    field_name="localTime",
    alias_name="localTime",
    field_type=FIELD_TYPE_STRING,
    description=gettext_lazy("AIOPS内置处理时间"),
    option={},
    is_dimension=False,
    is_display=False,
)

TIME = Field(
    field_name="time",
    alias_name="time",
    field_type=FIELD_TYPE_LONG,
    description=gettext_lazy("日志系统时间字段"),
    option={},
    is_dimension=False,
    is_display=False,
    property={'spec_field_type': SPEC_FIELD_TYPE_USER},
)

CLOUD_ID = Field(
    field_name="cloudId",
    alias_name="cloudId",
    field_type=FIELD_TYPE_INT,
    description=gettext_lazy("云区域ID"),
    option={},
    is_dimension=False,
    is_display=False,
)

SERVER_IP = Field(
    field_name="serverIp",
    alias_name="serverIp",
    field_type=FIELD_TYPE_STRING,
    description=gettext_lazy("主机IP"),
    option={},
    is_dimension=False,
    is_display=False,
)

PATH = Field(
    field_name="path",
    alias_name="path",
    field_type=FIELD_TYPE_STRING,
    description=gettext_lazy("采集路径"),
    option={},
    is_dimension=False,
    is_display=False,
)

GSE_INDEX = Field(
    field_name="gseIndex",
    alias_name="gseIndex",
    field_type=FIELD_TYPE_INT,
    description=gettext_lazy("上报包序号"),
    option={},
    is_dimension=False,
    is_display=False,
)

ITERATION_INDEX = Field(
    field_name="iterationIndex",
    alias_name="iterationIndex",
    field_type=FIELD_TYPE_INT,
    description=gettext_lazy("上报包内位置"),
    option={},
    is_dimension=False,
    is_display=False,
)

BKLOG_BUILD_IN_FIELDS = [TIME, EXT_FIELD_CONFIG, CLOUD_ID, SERVER_IP, PATH, GSE_INDEX, ITERATION_INDEX]
BKBASE_STORAGE_UNIQUE_KEYS = [SYSTEM_ID.field_name, ACTION_ID.field_name, EVENT_ID.field_name, START_TIME.field_name]

FILED_DISPLAY_NAME_ALIAS_KEY = "field_display_name_alias"
FILED_DISPLAY_NAME_ALIAS_MAP = {
    ACTION_ID.field_name: gettext_lazy("操作事件名称"),
    RESOURCE_TYPE_ID.field_name: gettext_lazy("资源类型名称"),
    SNAPSHOT_USER_INFO.field_name: gettext_lazy("用户信息"),
}

SNAPSHOT_USER_INFO_HIDE_FIELDS = ["id", "display_name", "username"]
STRATEGY_DISPLAY_FIELDS = [
    EVENT_ID,
    EVENT_CONTENT,
    ACTION_ID,
    REQUEST_ID,
    USERNAME,
    USER_IDENTIFY_TYPE,
    USER_IDENTIFY_TENANT_ID,
    USER_IDENTIFY_SRC,
    USER_IDENTIFY_SRC_USERNAME,
    START_TIME,
    END_TIME,
    BK_APP_CODE,
    SCOPE_TYPE,
    SCOPE_ID,
    ACCESS_TYPE,
    ACCESS_SOURCE_IP,
    ACCESS_USER_AGENT,
    RESOURCE_TYPE_ID,
    INSTANCE_ID,
    INSTANCE_NAME,
    INSTANCE_DATA,
    INSTANCE_ORIGIN_DATA,
    RESULT_CODE,
    RESULT_CONTENT,
    EXTEND_DATA,
    SYSTEM_ID,
]

DIMENSION_FIELD_TYPES = [FIELD_TYPE_STRING, FIELD_TYPE_INT, FIELD_TYPE_LONG, FIELD_TYPE_KEYWORD]

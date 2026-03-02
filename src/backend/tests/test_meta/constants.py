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
from unittest import mock

from django.conf import settings
from django.utils.translation import gettext_lazy

from apps.meta.constants import DEFAULT_DATA_DELIMITER as _DEFAULT_DATA_DELIMITER
from apps.meta.constants import DEFAULT_DATA_ENCODING as _DEFAULT_DATA_ENCODING
from apps.meta.constants import DEFAULT_DURATION_TIME as _DEFAULT_DURATION_TIME
from apps.meta.constants import DEFAULT_ES_SOURCE_TYPE as _DEFAULT_ES_SOURCE_TYPE
from apps.meta.constants import (
    GLOBAL_CONFIG_LEVEL_INSTANCE,
    IAM_MANAGER_ROLE,
    LIST_USER_FIELDS,
    LIST_USER_PAGE,
    LIST_USER_PAGE_SIZE,
    LIST_USERS_LOOKUP_FIELD,
    RETRIEVE_USER_FIELDS,
    CollectorParamConditionMatchType,
    CollectorParamConditionTypeEnum,
    ConfigLevelChoices,
    SpaceType,
    SystemSourceTypeEnum,
)
from apps.meta.models import System
from apps.meta.utils.fields import EVENT_ID
from apps.permission.constants import IAMSystems
from apps.permission.handlers.actions import ActionEnum
from core.choices import TextChoices
from core.utils.data import choices_to_dict, trans_object_local
from services.web.databus.constants import JoinDataPullType, SystemStatusDetailEnum
from tests.test_databus.collector.constants import (
    COLLECTOR_STATUS_RESULT as _COLLECTOR_STATUS_RESULT,
)
from tests.test_databus.collector.constants import (
    COLLECTOR_STATUS_RESULT_NODATA as _COLLECTOR_STATUS_RESULT_NODATA,
)
from tests.test_databus.collector.constants import (
    COLLECTOR_STATUS_RESULT_NORMAL as _COLLECTOR_STATUS_RESULT_NORMAL,
)
from tests.test_databus.collector.constants import SYSTEM_HOST as _SYSTEM_HOST
from tests.test_databus.collector.constants import SYSTEM_TOKEN as _SYSTEM_TOKEN
from tests.test_databus.storage.constants import USERNAME
from tests.test_query.constants import (
    GET_AUTH_SYSTEMS_API_RESP as _GET_AUTH_SYSTEMS_API_RESP,
)


class PermissionMock(mock.MagicMock):
    @classmethod
    def wrapper_permission_field(cls, systems, *args, **kwargs):
        return systems

    @classmethod
    def batch_make_resource(cls, resources):
        return []

    @staticmethod
    def is_allowed(self, action):
        return False


# Base
RESOURCE_TYPE_ID = "biz"
SYSTEM_DATA1 = {
    "instance_id": settings.BK_IAM_SYSTEM_ID + "test",
    "source_type": SystemSourceTypeEnum.IAM_V3.value,
    "system_id": settings.BK_IAM_SYSTEM_ID + "test",
    "namespace": settings.DEFAULT_NAMESPACE,
    "name": settings.BK_IAM_SYSTEM_ID + "test",
    "name_en": settings.BK_IAM_SYSTEM_ID + "test",
    "clients": None,
    "provider_config": None,
    "callback_url": "",
    "logo_url": "",
    "system_url": None,
    "description": None,
    "enable_system_diagnosis_push": False,
    "system_diagnosis_extra": {},
    "permission_type": "complex",
}
SYSTEM_DATA2 = {
    "instance_id": settings.BK_IAM_SYSTEM_ID,
    "source_type": SystemSourceTypeEnum.IAM_V3.value,
    "system_id": settings.BK_IAM_SYSTEM_ID,
    "namespace": settings.DEFAULT_NAMESPACE,
    "name": settings.BK_IAM_SYSTEM_ID,
    "name_en": settings.BK_IAM_SYSTEM_ID,
    "clients": None,
    "provider_config": {"host": _SYSTEM_HOST},
    "callback_url": _SYSTEM_HOST,
    "logo_url": "https://bk.tencent.com",
    "system_url": None,
    "description": None,
    "enable_system_diagnosis_push": False,
    "system_diagnosis_extra": {},
    "permission_type": "complex",
}
SYSTEM_BULK_DATA = list()
SYSTEM_BULK_DATA.append(
    System(
        instance_id=SYSTEM_DATA1["instance_id"],
        system_id=SYSTEM_DATA1["system_id"],
        namespace=SYSTEM_DATA1["namespace"],
        name=SYSTEM_DATA1["name"],
        name_en=SYSTEM_DATA1["name_en"],
        clients=SYSTEM_DATA1["clients"],
        provider_config=SYSTEM_DATA1["provider_config"],
        callback_url=SYSTEM_DATA1["callback_url"],
        logo_url=SYSTEM_DATA1["logo_url"],
        system_url=SYSTEM_DATA1["system_url"],
        description=SYSTEM_DATA1["description"],
    )
)
SYSTEM_BULK_DATA.append(
    System(
        instance_id=SYSTEM_DATA2["instance_id"],
        system_id=SYSTEM_DATA2["system_id"],
        namespace=SYSTEM_DATA2["namespace"],
        name=SYSTEM_DATA2["name"],
        name_en=SYSTEM_DATA2["name_en"],
        clients=SYSTEM_DATA2["clients"],
        provider_config=SYSTEM_DATA2["provider_config"],
        callback_url=SYSTEM_DATA2["callback_url"],
        logo_url=SYSTEM_DATA2["logo_url"],
        system_url=SYSTEM_DATA2["system_url"],
        description=SYSTEM_DATA2["description"],
    )
)

SYSTEM_ROLE_DATA = {
    "system_id": settings.BK_IAM_SYSTEM_ID,
    "role": IAM_MANAGER_ROLE,
    "username": USERNAME,
}
RESOURCE_TYPE_DATA = {
    "system_id": settings.BK_IAM_SYSTEM_ID,
    "resource_type_id": RESOURCE_TYPE_ID,
    "name": "业务",
    "name_en": "business",
    "sensitivity": 0,
    "provider_config": {"path": "/api/v1/iam/resources"},
    "path": "/api/v1/iam/resources",
    "version": 1,
    "description": None,
    "ancestors": [],
    "ancestor": [],
}

RESOURCE_TYPE_SON_DATA = copy.deepcopy(RESOURCE_TYPE_DATA)
RESOURCE_TYPE_SON_DATA["ancestor"] = [RESOURCE_TYPE_ID]
RESOURCE_TYPE_SON_DATA["resource_type_id"] = RESOURCE_TYPE_ID + "_son"

RESOURCE_TYPE_SON_SON_DATA = copy.deepcopy(RESOURCE_TYPE_SON_DATA)
RESOURCE_TYPE_SON_SON_DATA["ancestor"] = [RESOURCE_TYPE_ID + "_son"]
RESOURCE_TYPE_SON_SON_DATA["resource_type_id"] = RESOURCE_TYPE_ID + "_son_son"

RESOURCE_TYPE_SON_SON2_DATA = copy.deepcopy(RESOURCE_TYPE_SON_DATA)
RESOURCE_TYPE_SON_SON2_DATA["ancestor"] = [RESOURCE_TYPE_ID + "_son"]
RESOURCE_TYPE_SON_SON2_DATA["resource_type_id"] = RESOURCE_TYPE_ID + "_son_son2"

RESOURCE_TYPE_TREE_DATA = [
    {
        'system_id': 'bk-audit',
        'resource_type_id': 'biz',
        'unique_id': 'bk-audit:biz',
        'name': '业务',
        'name_en': 'business',
        'description': None,
        'children': [
            {
                'system_id': 'bk-audit',
                'resource_type_id': 'biz_son',
                'unique_id': 'bk-audit:biz_son',
                'name': '业务',
                'name_en': 'business',
                'description': None,
                'children': [
                    {
                        'system_id': 'bk-audit',
                        'resource_type_id': 'biz_son_son',
                        'unique_id': 'bk-audit:biz_son_son',
                        'name': '业务',
                        'name_en': 'business',
                        'description': None,
                        'children': [],
                    },
                    {
                        'system_id': 'bk-audit',
                        'resource_type_id': 'biz_son_son2',
                        'unique_id': 'bk-audit:biz_son_son2',
                        'name': '业务',
                        'name_en': 'business',
                        'description': None,
                        'children': [],
                    },
                ],
            }
        ],
    }
]

SNAPSHOT_RUNNING_STATUS_CLOSED = "closed"
SNAPSHOT_DATA = {
    "system_id": settings.BK_IAM_SYSTEM_ID,
    "resource_type_id": RESOURCE_TYPE_ID,
    "bkbase_data_id": 1,
    "bkbase_processing_id": None,
    "bkbase_table_id": "2",
    "is_public": False,
    "status": SNAPSHOT_RUNNING_STATUS_CLOSED,
}
FIELDS_DATA = {
    "field_name": EVENT_ID.field_name,
    "field_type": EVENT_ID.field_type,
    "alias_name": EVENT_ID.alias_name,
    "is_text": EVENT_ID.is_text,
    "is_time": EVENT_ID.is_time,
    "is_json": EVENT_ID.is_json,
    "is_analyzed": EVENT_ID.is_analyzed,
    "is_zh_analyzed": EVENT_ID.is_zh_analyzed,
    "is_index": EVENT_ID.is_index,
    "is_dimension": EVENT_ID.is_dimension,
    "is_delete": EVENT_ID.is_delete,
    "is_required": EVENT_ID.is_required,
    "is_display": EVENT_ID.is_display,
    "is_built_in": EVENT_ID.is_built_in,
    "option": EVENT_ID.option,
    "description": str(EVENT_ID.description),
    "priority_index": EVENT_ID.priority_index,
    "property": {},
}
CUSTOM_FIELD_DATA = {
    "username": USERNAME,
    "route_path": "/",
    "fields": {"key": "value"},
}
GLOBAL_META_CONFIG_DATA = {
    "config_level": ConfigLevelChoices.GLOBAL.value,
    "instance_key": GLOBAL_CONFIG_LEVEL_INSTANCE,
    "config_key": "config_test_key",
    "config_value": "config_test_value",
}

# System List
STATUS_NODATA_COPY = copy.deepcopy(_COLLECTOR_STATUS_RESULT)
STATUS_ABNORMAL_COPY = copy.deepcopy(_COLLECTOR_STATUS_RESULT_NODATA)
STATUS_NORMAL_COPY = copy.deepcopy(_COLLECTOR_STATUS_RESULT_NORMAL)
SYSTEM_LIST_OF_NOT_SORT_PARAMS = {
    "namespace": settings.DEFAULT_NAMESPACE,
    "status": STATUS_ABNORMAL_COPY["status"] + "," + "test",
}
SYSTEM_LIST_OF_NOT_SORT_DATA = [
    {
        **SYSTEM_DATA1,
        "managers": [],
        "last_time": STATUS_ABNORMAL_COPY["last_time"],
        "status": STATUS_ABNORMAL_COPY["status"],
        "status_msg": STATUS_ABNORMAL_COPY["status_msg"],
        "resource_type_count": 0,
        "action_count": 0,
        "system_status": "pending",
        "system_status_msg": str(SystemStatusDetailEnum.PENDING.label),
    },
]
BULK_SYSTEM_COLLECTORS_STATUS_API_RESP = {
    SYSTEM_DATA1["system_id"]: STATUS_ABNORMAL_COPY,
    SYSTEM_DATA2["system_id"]: STATUS_NORMAL_COPY,
}
SYSTEM_LIST_PARAMS = {
    "namespace": settings.DEFAULT_NAMESPACE,
    "status": STATUS_ABNORMAL_COPY["status"] + "," + STATUS_NORMAL_COPY["status"],
    "order_field": "-system_id",
}
SYSTEM_LIST_DATA = [
    {
        **SYSTEM_DATA1,
        "managers": [],
        "last_time": STATUS_ABNORMAL_COPY["last_time"],
        "status": STATUS_ABNORMAL_COPY["status"],
        "status_msg": STATUS_ABNORMAL_COPY["status_msg"],
        "resource_type_count": 0,
        "action_count": 0,
        "system_status": "pending",
        "system_status_msg": str(SystemStatusDetailEnum.PENDING.label),
    },
    {
        **SYSTEM_DATA2,
        "managers": [USERNAME],
        "last_time": STATUS_NORMAL_COPY["last_time"],
        "status": STATUS_NORMAL_COPY["status"],
        "status_msg": STATUS_NORMAL_COPY["status_msg"],
        "resource_type_count": 1,
        "action_count": 0,
        "system_status": "pending",
        "system_status_msg": str(SystemStatusDetailEnum.PENDING.label),
    },
]
SYSTEM_LIST_OF_NOT_SYSTEMS_PARAMS = {
    "namespace": settings.DEFAULT_NAMESPACE,
    "keyword": settings.DEFAULT_NAMESPACE,
}
SYSTEM_LIST_OF_SORT_EQ_PARAMS = {
    "namespace": settings.DEFAULT_NAMESPACE,
    "order_field": "namespace",
}
SYSTEM_LIST_OF_SORT_EQ_DATA = [
    {
        **SYSTEM_DATA2,
        "managers": [USERNAME],
        "last_time": STATUS_NORMAL_COPY["last_time"],
        "status": STATUS_NORMAL_COPY["status"],
        "status_msg": STATUS_NORMAL_COPY["status_msg"],
        "resource_type_count": 1,
        "action_count": 0,
        "system_status": "pending",
        "system_status_msg": str(SystemStatusDetailEnum.PENDING.label),
    },
    {
        **SYSTEM_DATA1,
        "managers": [],
        "last_time": STATUS_ABNORMAL_COPY["last_time"],
        "status": STATUS_ABNORMAL_COPY["status"],
        "status_msg": STATUS_ABNORMAL_COPY["status_msg"],
        "resource_type_count": 0,
        "action_count": 0,
        "system_status": "pending",
        "system_status_msg": str(SystemStatusDetailEnum.PENDING.label),
    },
]
SYSTEM_LIST_OF_SORT_GT_PARAMS = {
    "namespace": settings.DEFAULT_NAMESPACE,
    "order_field": "logo_url",
}
SYSTEM_LIST_OF_SORT_GT_DATA = SYSTEM_LIST_DATA

# System List All
SYSTEM_LIST_ALL_PARAMS = {
    "namespace": settings.DEFAULT_NAMESPACE,
    "action_ids": ActionEnum.SEARCH_REGULAR_EVENT.id,
}
SYSTEM_LIST_ALL_DATA = [
    {
        "id": SYSTEM_DATA2["system_id"],
        "name": SYSTEM_DATA2["name"],
        "name_en": SYSTEM_DATA2["name_en"],
        "source_type": SYSTEM_DATA2['source_type'],
        "audit_status": "pending",
        "system_id": SYSTEM_DATA2["system_id"],
        "instance_id": SYSTEM_DATA2["instance_id"],
        "permission_type": "complex",
    },
    {
        "id": SYSTEM_DATA1["system_id"],
        "name": SYSTEM_DATA1["name"],
        "name_en": SYSTEM_DATA1["name_en"],
        "source_type": SYSTEM_DATA1["source_type"],
        "audit_status": "pending",
        "system_id": SYSTEM_DATA1["system_id"],
        "instance_id": SYSTEM_DATA1["instance_id"],
        "permission_type": "complex",
    },
]
SYSTEM_LIST_ALL_OF_ACTION_IDS_PARAMS = {"namespace": settings.DEFAULT_NAMESPACE}
SYSTEM_LIST_ALL_OF_ACTION_IDS_DATA = [
    {
        "id": settings.BK_IAM_SYSTEM_ID,
        "name": settings.BK_IAM_SYSTEM_ID,
        "name_en": settings.BK_IAM_SYSTEM_ID,
        "source_type": SYSTEM_DATA2['source_type'],
        "audit_status": "pending",
        "system_id": SYSTEM_DATA2["system_id"],
        "instance_id": SYSTEM_DATA2["instance_id"],
        "permission_type": "complex",
    }
]

# System Info
SYSTEM_INFO_PARAMS = {"system_id": settings.BK_IAM_SYSTEM_ID}
SYSTEM_DATA_COPY = copy.deepcopy(SYSTEM_DATA2)
SYSTEM_DATA_COPY.update({"managers": [USERNAME]})
SYSTEM_INFO_DATA = {
    **SYSTEM_DATA_COPY,
    "status": 'unset',
    "status_msg": '未配置',
    "last_time": "",
    "resource_type_count": 1,
    "action_count": 0,
    "system_status": "pending",
    "system_stage": "pending",
    "system_status_msg": str(SystemStatusDetailEnum.PENDING.label),
}

# Resource Type List
RESOURCE_TYPE_LIST_PARAMS = {"system_id": settings.BK_IAM_SYSTEM_ID}
RESOURCE_TYPE_LIST_DATA = copy.deepcopy(RESOURCE_TYPE_DATA)
RESOURCE_TYPE_LIST_DATA['unique_id'] = 'bk-audit:biz'
RESOURCE_TYPE_LIST_DATA['actions'] = []
RESOURCE_TYPE_LIST_DATA.update(
    {
        "status": SNAPSHOT_DATA["status"],
        "bkbase_url": None,
        "pull_type": "partial",
        "status_msg": None,
    }
)
RESOURCE_TYPE_LIST_DATA2 = copy.deepcopy(RESOURCE_TYPE_DATA)
RESOURCE_TYPE_LIST_DATA2['unique_id'] = 'bk-audit:biz'
RESOURCE_TYPE_LIST_DATA2['actions'] = []
RESOURCE_TYPE_LIST_DATA2.update(
    {
        "status": SNAPSHOT_RUNNING_STATUS_CLOSED,
        "bkbase_url": None,
        "pull_type": JoinDataPullType.PARTIAL,
        "status_msg": "",
    }
)

# System Filter
GET_AUTH_SYSTEMS_API_RESP = copy.deepcopy(_GET_AUTH_SYSTEMS_API_RESP)
SYSTEM_FILTER_PARAMS = {
    "namespace": settings.DEFAULT_NAMESPACE,
    "system_ids": settings.BK_IAM_SYSTEM_ID,
}
SYSTEM_FILTER_OF_NOT_SYSTEM_IDS_PARAMS = {
    "namespace": settings.DEFAULT_NAMESPACE,
}
RESOURCE_TYPE_NAME = RESOURCE_TYPE_DATA["name"]
SYSTEM_FILTER_DATA = [
    {
        "id": RESOURCE_TYPE_ID,
        "name": f"{RESOURCE_TYPE_NAME} ({RESOURCE_TYPE_ID})",
    }
]

# Get Globals
GET_GLOBALS_API_RESP = {
    "es_source_type": copy.deepcopy(_DEFAULT_ES_SOURCE_TYPE),
    "storage_duration_time": trans_object_local(copy.deepcopy(_DEFAULT_DURATION_TIME), ["name"]),
    "data_delimiter": copy.deepcopy(_DEFAULT_DATA_DELIMITER),
    "data_encoding": copy.deepcopy(_DEFAULT_DATA_ENCODING),
}


class ContainerCollectorType(TextChoices):
    CONTAINER = "container_log_config", gettext_lazy("Container")
    NODE = "node_log_config", gettext_lazy("Node")
    STDOUT = "std_log_config", gettext_lazy("标准输出")


class EtlConfigEnum(TextChoices):
    BK_LOG_JSON = "bk_log_json", gettext_lazy("JSON")
    BK_LOG_DELIMITER = "bk_log_delimiter", gettext_lazy("分隔符")
    BK_LOG_REGEXP = "bk_log_regexp", gettext_lazy("正则")


GET_GLOBALS_DATA = {
    **GET_GLOBALS_API_RESP,
    "app_info": {"app_code": settings.APP_CODE},
    "param_conditions_type": choices_to_dict(CollectorParamConditionTypeEnum),
    "param_conditions_match": choices_to_dict(CollectorParamConditionMatchType),
    "etl_config": choices_to_dict(EtlConfigEnum),
    "bcs_log_type": choices_to_dict(ContainerCollectorType),
}

# Get Standard Fields
GET_STANDARD_FIELDS_PARAMS = {"is_etl": True}
GET_STANDARD_FIELDS_DATA = [FIELDS_DATA]

# Get Custom Fields
GET_CUSTOM_FIELDS_PARAMS = {"route_path": CUSTOM_FIELD_DATA["route_path"]}
GET_CUSTOM_FIELDS_DATA = CUSTOM_FIELD_DATA["fields"]
GET_CUSTOM_FIELDS_EXCEPT_PARAMS = {"route_path": CUSTOM_FIELD_DATA["route_path"] + CUSTOM_FIELD_DATA["route_path"]}

# Update Custom Fields
UPDATE_CUSTOM_FIELDS_PARAMS = {
    "route_path": CUSTOM_FIELD_DATA["route_path"],
    "fields": {list(CUSTOM_FIELD_DATA["fields"])[0]: "value2"},
}

# Get App Info
GET_APP_INFO_PARAMS = {
    "namespace": settings.DEFAULT_NAMESPACE,
    "app_code": settings.APP_CODE,
}
GET_CACHE_OF_APP_INFO_API_RESP = {
    "app_code": settings.APP_CODE,
    "app_name": settings.APP_CODE,
    "developers": [USERNAME],
    "status": False,
    "status_msg": "未找到",
    "system_url": "",
}
UNI_APPS_QUERY_API_RESP = [
    {
        "name": settings.APP_CODE,
        "code": settings.APP_CODE,
        "developers": [USERNAME],
        "deploy_info": {},
    }
]
GET_APP_INFO_DATA = {
    "app_code": settings.APP_CODE,
    "app_name": UNI_APPS_QUERY_API_RESP[0]["name"],
    "developers": UNI_APPS_QUERY_API_RESP[0]["developers"],
    "status": True,
    "status_msg": gettext_lazy("未部署"),
    "system_url": "",
}

# Resource Type Schema
SYSTEM_DATA_COPY = copy.deepcopy(SYSTEM_DATA2)
SYSTEM_DATA_COPY["provider_config"].update({"token": _SYSTEM_TOKEN})
SYSTEM_DATA_COPY.update({"auth_token": _SYSTEM_TOKEN})
SYSTEM_OF_SCHEMA_DATA = SYSTEM_DATA_COPY
GET_CACHE_OF_RESOURCE_TYPE_API_RESP = [
    {
        "id": settings.APP_CODE,
        "type": "string",
        "description_en": RESOURCE_TYPE_DATA["description"],
        "description": RESOURCE_TYPE_DATA["description"],
    }
]
RESOURCE_TYPE_SCHEMA_PARAMS = {
    "system_id": settings.BK_IAM_SYSTEM_ID,
    "resource_type_id": RESOURCE_TYPE_ID,
}

# Set Global Meta Config
SET_GLOBAL_META_CONFIG_PARAMS = {
    "config_value": GLOBAL_META_CONFIG_DATA["config_value"],
    "config_level": GLOBAL_META_CONFIG_DATA["config_level"],
    "instance_key": GLOBAL_META_CONFIG_DATA["instance_key"],
    "config_key": GLOBAL_META_CONFIG_DATA["config_key"],
}
SET_GLOBAL_META_CONFIG_DATA = GLOBAL_META_CONFIG_DATA

# Get Global Meta Config Info
GET_GLOBAL_META_CONFIG_INFO_PARAMS = SET_GLOBAL_META_CONFIG_PARAMS
GET_GLOBAL_META_CONFIG_INFO_DATA = GLOBAL_META_CONFIG_DATA

# Get Spaces Mine
BKLOG_PERMISSION_VERSION_API_RESP = "1"
BIZS_LIST_API_RESP = [
    {
        "bk_biz_id": settings.APP_CODE,
        "space_name": "test",
        "permission": {"view_business_v1_bk_log": True},
    }
]
GET_SPACES_MINE_DATA = [
    {
        "id": BIZS_LIST_API_RESP[0]["bk_biz_id"],
        "name": BIZS_LIST_API_RESP[0]["space_name"],
        "space_type_id": SpaceType.BIZ.value,
        "space_type_name": str(SpaceType.BIZ.label),
        "permission": {"view_business_v1_bk_log" + "_" + IAMSystems.BK_LOG.value: True},
    }
]
GET_SPACES_MINE_API_RESP = [
    {
        "bk_biz_id": settings.APP_CODE,
        "space_name": "test",
        "permission": {"view_business_v2_bk_log": True},
    }
]
GET_SPACES_MINE_OF_V2_DATA = [
    {
        "id": GET_SPACES_MINE_API_RESP[0]["bk_biz_id"],
        "name": GET_SPACES_MINE_API_RESP[0]["space_name"],
        "space_type_id": SpaceType.UNKNOWN.value,
        "space_type_name": str(SpaceType.UNKNOWN.label),
        "permission": {"view_business_v2_bk_log" + "_" + IAMSystems.BK_LOG.value: True},
    }
]

# List Users
LIST_USERS_API_RESP = {
    "id": 1,
    "name": USERNAME,
    "display_name": "管理员",
}
LIST_USERS_PARAMS = {
    "page": LIST_USER_PAGE,
    "page_size": LIST_USER_PAGE_SIZE,
    "fields": LIST_USER_FIELDS,
    "lookup_field": "display_name",
    "fuzzy_lookups": "name",
    "exact_lookups": "display_name",
}
LIST_USERS_DATA = LIST_USERS_API_RESP

# Retrieve User
RETRIEVE_USER_API_RESP = {
    "username": USERNAME,
    "status": "NORMAL",
    "display_name": "管理员",
    "staff_status": "IN",
    "departments": [{"order": 2, "id": 2872, "full_name": "虚拟账号", "name": "虚拟账号"}],
    "leader": [],
    "extras": {"virtualapi": 1, "postname": None},
    "id": 1,
}
RETRIEVE_USER_PARAMS = {
    "id": USERNAME,
    "lookup_field": LIST_USERS_LOOKUP_FIELD,
    "fields": RETRIEVE_USER_FIELDS,
}
RETRIEVE_USER_DATA = RETRIEVE_USER_API_RESP

GLOBAL_CHOICES = {
    'BKVisionFieldCategory': [
        {'id': 'button', 'name': '按钮'},
        {'id': 'cascader', 'name': '级联选择器'},
        {'id': 'inputer', 'name': '输入框'},
        {'id': 'radios', 'name': '单选按钮组'},
        {'id': 'selector', 'name': '选择器'},
        {'id': 'time-picker', 'name': '时间选择器'},
        {'id': 'time-ranger', 'name': '时间范围选择器'},
        {'id': 'variable', 'name': '变量'},
    ],
    'DataSearchConfigType': [{'id': 'simple', 'name': '简易模式'}, {'id': 'sql', 'name': 'SQL模式'}],
    'FieldCategory': [
        {'id': 'input', 'name': '输入框'},
        {'id': 'number_input', 'name': '数字输入框'},
        {'id': 'time_range_select', 'name': '时间范围选择器'},
        {'id': 'time_select', 'name': '时间选择器'},
        {'id': 'person_select', 'name': '人员选择器'},
        {'id': 'multiselect', 'name': '下拉列表'},
    ],
    'TargetValueType': [{'id': 'fixed_value', 'name': '固定值'}, {'id': 'field', 'name': '字段'}],
    'ToolType': [
        {'id': 'data_search', 'name': '数据查询'},
        {'id': 'api', 'name': 'API'},
        {'id': 'bk_vision', 'name': 'BK Vision'},
    ],
    'api_variable_position': [
        {'id': 'query', 'name': '查询参数'},
        {'id': 'path', 'name': '路径参数'},
        {'id': 'body', 'name': '请求体'},
    ],
    'core_sql_field_type': [
        {'id': 'string', 'name': '字符串'},
        {'id': 'double', 'name': '双精度浮点数'},
        {'id': 'int', 'name': '整数'},
        {'id': 'long', 'name': '长整数'},
        {'id': 'text', 'name': '文本'},
        {'id': 'timestamp', 'name': '时间戳'},
        {'id': 'float', 'name': '浮点数'},
    ],
    'event_filter_operator': [
        {'id': '=', 'name': '=  等于'},
        {'id': 'CONTAINS', 'name': '包含'},
        {'id': 'IN', 'name': 'IN'},
        {'id': '!=', 'name': '!=  不等于'},
        {'id': 'NOT CONTAINS', 'name': '不包含'},
        {'id': 'NOT IN', 'name': 'NOT IN'},
        {'id': '>=', 'name': '>=  大于等于'},
        {'id': '<=', 'name': '<=  小于等于'},
        {'id': '>', 'name': '>  大于'},
        {'id': '<', 'name': '<  小于'},
    ],
    'log_export_task': [
        {'id': 'READY', 'name': '就绪'},
        {'id': 'RUNNING', 'name': '执行中'},
        {'id': 'SUCCESS', 'name': '成功'},
        {'id': 'FAILURE', 'name': '失败'},
        {'id': 'EXPIRED', 'name': '已过期'},
    ],
    'meta_system_audit_status': [{'id': 'pending', 'name': '待接入'}, {'id': 'accessed', 'name': '已接入'}],
    'meta_system_permission_type': [{'id': 'simple', 'name': '简单权限'}, {'id': 'complex', 'name': '复杂权限'}],
    'meta_system_sensitivity': [
        {'id': 0, 'name': '无'},
        {'id': 1, 'name': '不敏感'},
        {'id': 2, 'name': '低'},
        {'id': 3, 'name': '中'},
        {'id': 4, 'name': '高'},
    ],
    'meta_system_source_type': [
        {'id': 'iam_v3', 'name': '权限中心V3'},
        {'id': 'iam_v4', 'name': '权限中心V4'},
        {'id': 'bk_audit', 'name': '审计中心'},
    ],
    'meta_system_stage': [
        {'id': 'pending', 'name': '待接入'},
        {'id': 'permission_model', 'name': '权限模型'},
        {'id': 'collector', 'name': '日志采集'},
        {'id': 'completed', 'name': '已完成'},
    ],
    'meta_system_status': [
        {'id': 'pending', 'name': '待接入'},
        {'id': 'incomplete', 'name': '待完善'},
        {'id': 'abnormal', 'name': '数据异常'},
        {'id': 'normal', 'name': '正常'},
    ],
    'query_condition_operator': [
        {'id': 'eq', 'name': '=  等于'},
        {'id': 'neq', 'name': '!=  不等于'},
        {'id': 'gt', 'name': '>  大于'},
        {'id': 'lt', 'name': '<  小于'},
        {'id': 'gte', 'name': '>=  大于等于'},
        {'id': 'lte', 'name': '<=  小于等于'},
        {'id': 'include', 'name': 'in  属于'},
        {'id': 'exclude', 'name': 'not in  不属于'},
        {'id': 'like', 'name': 'like  包含(模糊匹配)'},
        {'id': 'not_like', 'name': 'not like  不包含(模糊匹配)'},
        {'id': 'isnull', 'name': 'is null  为空'},
        {'id': 'notnull', 'name': 'is not null  不为空'},
        {'id': 'match_all', 'name': '匹配全部'},
        {'id': 'match_any', 'name': '匹配任意'},
        {'id': 'json_contains', 'name': 'json 包含'},
        {'id': 'between', 'name': '在之间'},
    ],
    'query_field_category': [
        {'id': 'standard', 'name': '标准字段'},
        {'id': 'snapshot', 'name': '快照字段'},
        {'id': 'system', 'name': '系统字段'},
        {'id': 'custom', 'name': '自定义字段'},
    ],
    'strategy_field_source': [
        {'id': 'basic', 'name': '基本字段'},
        {'id': 'data', 'name': '数据字段'},
        {'id': 'evidence', 'name': '证据字段'},
        {'id': 'risk_meta', 'name': '风险元字段'},
    ],
}

SYSTEM_DIAGNOSIS_PUSH_TEMPLATE = """{
        "title": "【BKAudit】{{ system_name }}系统审计巡检报告",
        "status": "push",
        "recipient": {{ recipient|tojson }},
        "wechat_receivers": [],
        "cycle_type": "period",
        "crontab": "0 8 * * *",
        "time_range": "Today",
        "filters": {
            "EZKZbYEhgroF8TgoAk4FVE": [
                "now-24h",
                "now"
            ],
            "tHHFiZQIxJiCtPhXPwkfAB": "{{ system_id }}",
            "yplkBhNKbuaiCdwPmIwY1K": [
                "now-1d/d",
                "now-1d/d"
            ]
        },
        "constants": {},
        "space_uid": "xxx",
        "dashboard_uid": "xxx",
        "version": "latest",
        "dashboard_title": "系统诊断",
        "dashboard_width": 1920,
        "modes": [
            "mail"
        ],
        "advanced_setting": {
            "dashboard_width": 1366
        },
        "topic": "【BKAudit】审计中心系统审计巡检报告",
        "wechat_extra_info": "",
        "webhook": "",
        "cc_recipient": [],
        "hyperlink": "https://xxx/{{ system_id }}",
        "hyperlink_required": true
    }"""

SYSTEM_DIAGNOSIS_PUSH_ENABLE = {
    'advanced_setting': {'dashboard_width': 1366},
    'cc_recipient': [],
    'constants': {},
    'crontab': '0 8 * * *',
    'cycle_type': 'period',
    'dashboard_title': '系统诊断',
    'dashboard_uid': 'xxx',
    'dashboard_width': 1920,
    'filters': {
        'EZKZbYEhgroF8TgoAk4FVE': ['now-24h', 'now'],
        'tHHFiZQIxJiCtPhXPwkfAB': 'test_system',
        'yplkBhNKbuaiCdwPmIwY1K': ['now-1d/d', 'now-1d/d'],
    },
    'hyperlink': 'https://xxx/test_system',
    'hyperlink_required': True,
    'modes': ['mail'],
    'recipient': ['test_user'],
    'space_uid': 'xxx',
    'status': 'push',
    'time_range': 'Today',
    'title': '【BKAudit】Test System系统审计巡检报告',
    'topic': '【BKAudit】审计中心系统审计巡检报告',
    'version': 'latest',
    'webhook': '',
    'wechat_extra_info': '',
    'wechat_receivers': [],
}

SYSTEM_DIAGNOSIS_PUSH_DISABLE = {
    'advanced_setting': {'dashboard_width': 1366},
    'cc_recipient': [],
    'constants': {},
    'crontab': '0 8 * * *',
    'cycle_type': 'period',
    'dashboard_title': '系统诊断',
    'dashboard_uid': 'xxx',
    'dashboard_width': 1920,
    'filters': {
        'EZKZbYEhgroF8TgoAk4FVE': ['now-24h', 'now'],
        'tHHFiZQIxJiCtPhXPwkfAB': 'test_system',
        'yplkBhNKbuaiCdwPmIwY1K': ['now-1d/d', 'now-1d/d'],
    },
    'hyperlink': 'https://xxx/test_system',
    'hyperlink_required': True,
    'modes': ['mail'],
    'recipient': ['test_user'],
    'space_uid': 'xxx',
    'status': 'pause',
    'time_range': 'Today',
    'title': '【BKAudit】Test System系统审计巡检报告',
    'topic': '【BKAudit】审计中心系统审计巡检报告',
    'uid': 'test_uid',
    'version': 'latest',
    'webhook': '',
    'wechat_extra_info': '',
    'wechat_receivers': [],
}

TEST_SYSTEM_ID = settings.BK_IAM_SYSTEM_ID

EXPECT_IAM_SYSTEMS = [
    {
        'auth_token': 'xxx',
        'callback_url': 'https://xxx.com',
        'clients': ['xxx'],
        'description': 'IAM V3测试系统',
        'enable_system_diagnosis_push': False,
        'instance_id': 'test_system',
        'logo_url': "https://xxx.logo",
        'managers': [],
        'name': 'IAM V3测试系统',
        'name_en': 'IAM V3测试系统',
        'namespace': 'default',
        'provider_config': {'auth': 'basic', 'healthz': '', 'host': 'https://xxx.com', 'token': 'xxx'},
        'source_type': 'iam_v3',
        'system_diagnosis_extra': {},
        'system_id': 'test_system',
        'system_url': "https://xxx.system",
    },
    {
        'auth_token': 'xxx',
        'callback_url': 'https://xxx.com/api/resource/',
        'clients': ['app_code1', 'app_code2'],
        'description': 'IAM V4 测试系统',
        'enable_system_diagnosis_push': False,
        'instance_id': 'test_system',
        'logo_url': "https://app_code1.logo",
        'managers': ['admin'],
        'name': 'IAM V4 测试系统',
        'name_en': 'IAM V4 测试系统',
        'namespace': 'default',
        'provider_config': {},
        'source_type': 'iam_v4',
        'system_diagnosis_extra': {},
        'system_id': 'iam_v4_test_system',
        'system_url': "https://app_code1.system",
    },
]

AUDIT_CUSTOM_SYSTEM = {
    'auth_token': 'xxx',
    'callback_url': 'https://xxx.com/api/resource/',
    'clients': ['app_code1', 'app_code2'],
    'description': '审计自定义系统',
    'enable_system_diagnosis_push': False,
    'instance_id': 'audit_custom_system',
    'logo_url': "https://app_code1.logo",
    'managers': ['admin'],
    'name': '审计自定义系统',
    'name_en': '审计自定义系统',
    'namespace': 'default',
    'provider_config': {},
    'source_type': 'bk_audit',
    'system_diagnosis_extra': {},
    'system_url': "https://app_code1.system",
}

ADD_CUSTOM_SYSTEMS = [*EXPECT_IAM_SYSTEMS, AUDIT_CUSTOM_SYSTEM]

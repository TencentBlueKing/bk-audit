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
    ConfigLevelChoices,
    SpaceType,
)
from apps.meta.models import System
from apps.meta.utils.fields import EVENT_ID
from apps.meta.utils.saas import get_saas_url
from apps.permission.constants import IAMSystems
from apps.permission.handlers.actions import ActionEnum
from core.choices import TextChoices
from core.utils.tools import choices_to_dict, trans_object_local
from tests.databus.collector.constants import (
    COLLECTOR_STATUS_RESULT as _COLLECTOR_STATUS_RESULT,
)
from tests.databus.collector.constants import (
    COLLECTOR_STATUS_RESULT_NODATA as _COLLECTOR_STATUS_RESULT_NODATA,
)
from tests.databus.collector.constants import (
    COLLECTOR_STATUS_RESULT_NORMAL as _COLLECTOR_STATUS_RESULT_NORMAL,
)
from tests.databus.collector.constants import SYSTEM_HOST as _SYSTEM_HOST
from tests.databus.collector.constants import SYSTEM_TOKEN as _SYSTEM_TOKEN
from tests.databus.storage.constants import USERNAME
from tests.esquery.constants import (
    GET_AUTH_SYSTEMS_API_RESP as _GET_AUTH_SYSTEMS_API_RESP,
)


class PermissionMock(mock.MagicMock):
    @classmethod
    def wrapper_permission_field(cls, systems, *args, **kwargs):
        return systems


# Base
RESOURCE_TYPE_ID = "biz"
SYSTEM_DATA1 = {
    "system_id": settings.APP_CODE + "test",
    "namespace": settings.DEFAULT_NAMESPACE,
    "name": settings.APP_CODE + "test",
    "name_en": settings.APP_CODE + "test",
    "clients": None,
    "provider_config": None,
    "logo_url": "",
    "system_url": None,
    "description": None,
}
SYSTEM_DATA2 = {
    "system_id": settings.APP_CODE,
    "namespace": settings.DEFAULT_NAMESPACE,
    "name": settings.APP_CODE,
    "name_en": settings.APP_CODE,
    "clients": None,
    "provider_config": {"host": _SYSTEM_HOST},
    "logo_url": "https://bk.tencent.com",
    "system_url": None,
    "description": None,
}
SYSTEM_BULK_DATA = list()
SYSTEM_BULK_DATA.append(
    System(
        system_id=SYSTEM_DATA1["system_id"],
        namespace=SYSTEM_DATA1["namespace"],
        name=SYSTEM_DATA1["name"],
        name_en=SYSTEM_DATA1["name_en"],
        clients=SYSTEM_DATA1["clients"],
        provider_config=SYSTEM_DATA1["provider_config"],
        logo_url=SYSTEM_DATA1["logo_url"],
        system_url=SYSTEM_DATA1["system_url"],
        description=SYSTEM_DATA1["description"],
    )
)
SYSTEM_BULK_DATA.append(
    System(
        system_id=SYSTEM_DATA2["system_id"],
        namespace=SYSTEM_DATA2["namespace"],
        name=SYSTEM_DATA2["name"],
        name_en=SYSTEM_DATA2["name_en"],
        clients=SYSTEM_DATA2["clients"],
        provider_config=SYSTEM_DATA2["provider_config"],
        logo_url=SYSTEM_DATA2["logo_url"],
        system_url=SYSTEM_DATA2["system_url"],
        description=SYSTEM_DATA2["description"],
    )
)

SYSTEM_ROLE_DATA = {
    "system_id": settings.APP_CODE,
    "role": IAM_MANAGER_ROLE,
    "username": USERNAME,
}
RESOURCE_TYPE_DATA = {
    "system_id": settings.APP_CODE,
    "resource_type_id": RESOURCE_TYPE_ID,
    "name": "业务",
    "name_en": "business",
    "sensitivity": 0,
    "provider_config": {"path": "/api/v1/iam/resources"},
    "version": 1,
    "description": None,
}
SNAPSHOT_RUNNING_STATUS_CLOSED = "closed"
SNAPSHOT_DATA = {
    "system_id": settings.APP_CODE,
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
    "is_dimension": EVENT_ID.is_dimension,
    "is_delete": EVENT_ID.is_delete,
    "is_required": EVENT_ID.is_required,
    "is_display": EVENT_ID.is_display,
    "is_built_in": EVENT_ID.is_built_in,
    "option": EVENT_ID.option,
    "description": str(EVENT_ID.description),
    "priority_index": EVENT_ID.priority_index,
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
    },
    {
        **SYSTEM_DATA2,
        "managers": [USERNAME],
        "last_time": STATUS_NORMAL_COPY["last_time"],
        "status": STATUS_NORMAL_COPY["status"],
        "status_msg": STATUS_NORMAL_COPY["status_msg"],
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
    },
    {
        **SYSTEM_DATA1,
        "managers": [],
        "last_time": STATUS_ABNORMAL_COPY["last_time"],
        "status": STATUS_ABNORMAL_COPY["status"],
        "status_msg": STATUS_ABNORMAL_COPY["status_msg"],
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
    },
    {
        "id": SYSTEM_DATA1["system_id"],
        "name": SYSTEM_DATA1["name"],
    },
]
SYSTEM_LIST_ALL_OF_ACTION_IDS_PARAMS = {"namespace": settings.DEFAULT_NAMESPACE}
SYSTEM_LIST_ALL_OF_ACTION_IDS_DATA = [
    {
        "id": settings.APP_CODE,
        "name": settings.APP_CODE,
    }
]

# System Info
SYSTEM_INFO_PARAMS = {"system_id": settings.APP_CODE}
SYSTEM_DATA_COPY = copy.deepcopy(SYSTEM_DATA2)
SYSTEM_DATA_COPY.update({"managers": [USERNAME]})
SYSTEM_INFO_DATA = SYSTEM_DATA_COPY

# Resource Type List
RESOURCE_TYPE_LIST_PARAMS = {"system_id": settings.APP_CODE}
RESOURCE_TYPE_LIST_DATA = copy.deepcopy(RESOURCE_TYPE_DATA)
RESOURCE_TYPE_LIST_DATA.update(
    {
        "status": SNAPSHOT_DATA["status"],
        "bkbase_url": get_saas_url(settings.BKBASE_APP_CODE)
        + str(settings.BK_BASE_ACCESS_URL).rstrip("/")
        + "/"
        + str(SNAPSHOT_DATA["bkbase_data_id"]),
    }
)
RESOURCE_TYPE_LIST_DATA2 = copy.deepcopy(RESOURCE_TYPE_DATA)
RESOURCE_TYPE_LIST_DATA2.update({"status": SNAPSHOT_RUNNING_STATUS_CLOSED, "bkbase_url": None})

# System Filter
GET_AUTH_SYSTEMS_API_RESP = copy.deepcopy(_GET_AUTH_SYSTEMS_API_RESP)
SYSTEM_FILTER_PARAMS = {
    "namespace": settings.DEFAULT_NAMESPACE,
    "system_ids": settings.APP_CODE,
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


class CollectorParamConditionTypeEnum(TextChoices):
    MATCH = "match", gettext_lazy("字符串过滤")
    SEPARATOR = "separator", gettext_lazy("分隔符过滤")


class CollectorParamConditionMatchType(TextChoices):
    INCLUDE = "include", gettext_lazy("保留匹配字符串")


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
    "system_id": settings.APP_CODE,
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

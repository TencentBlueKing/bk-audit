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
from typing import List, Union
from unittest import mock

import arrow
from django.conf import settings
from django.utils.translation import gettext_lazy
from iam import Resource

from apps.meta.utils.fields import ACCESS_TYPE, RESULT_CODE
from apps.permission.handlers.actions import ActionMeta
from services.web.query.constants import COLLECT_SEARCH_CONFIG, DATE_FORMAT
from services.web.query.constants import DEFAULT_TIMEDELTA as _DEFAULT_TIMEDELTA
from tests.test_databus.collector_plugin.constants import INDEX_SET_ID as _INDEX_SET_ID
from tests.test_databus.collector_plugin.constants import PLUGIN_DATA as _PLUGIN_DATA
from tests.test_databus.collector_plugin.constants import PLUGIN_RESULT_TABLE

# Base
PLUGIN_DATA = copy.deepcopy(_PLUGIN_DATA)
PAGE = 1
PAGE_SIZE = 10


class PermissionMock(mock.MagicMock):
    @classmethod
    def get_apply_data(cls, actions: List[Union[ActionMeta, str]], resources: List[Resource] = None):
        return {"apply_data": ""}, "apply_url"


# Search
ES_QUERY_SEARCH_API_RESP = {
    "hits": {
        "total": 2,
        "hits": [
            {
                "_source": {},
                "system_id": {},
            }
        ],
    }
}
GET_AUTH_SYSTEMS_API_RESP = [
    [
        {"permission": {"search_regular_event": "test"}, "id": settings.BK_IAM_SYSTEM_ID},
        {"permission": {"view_system": "test"}, "id": settings.BK_IAM_SYSTEM_ID},
    ],
    [settings.BK_IAM_SYSTEM_ID],
]
SEARCH_PARAMS = {
    "namespace": settings.DEFAULT_NAMESPACE,
    "start_time": "2022-01-01 00:00:00",
    "end_time": "2022-12-31 00:00:00",
    "query_string": "",
    "sort_list": "",
    "page": PAGE,
    "page_size": PAGE_SIZE,
    "index_set_id": _INDEX_SET_ID,
}
SEARCH_DATA = {
    "page": PAGE,
    "num_pages": PAGE_SIZE,
    "total": ES_QUERY_SEARCH_API_RESP["hits"]["total"],
    "results": [{"system_info": item["system_id"]} for item in ES_QUERY_SEARCH_API_RESP["hits"]["hits"]],
    "scroll_id": None,
}

# Field Map
FIELD_MAP_PARAMS = {
    "namespace": settings.DEFAULT_NAMESPACE,
    "timedelta": _DEFAULT_TIMEDELTA,
    "fields": ACCESS_TYPE.field_name + "," + RESULT_CODE.field_name,
}
FIELD_MAP_DATA = {
    "access_type": [
        {"id": "0", "name": "WebUI"},
        {"id": "1", "name": "API"},
        {"id": "2", "name": "Console"},
        {"id": "-1", "name": "Other"},
    ],
    "result_code": [{"id": "0", "name": gettext_lazy("成功")}, {"id": "-1", "name": gettext_lazy("其他")}],
}

# CollectorSearch Params
start_time = arrow.get("2022-01-01 00:00:00")
end_time = arrow.get("2022-12-31 00:00:00")
start_date = start_time.strftime(DATE_FORMAT)
end_date = end_time.strftime(DATE_FORMAT)
start_timestamp = int(start_time.timestamp()) * 1000
end_timestamp = int(end_time.timestamp()) * 1000
COLLECTOR_SEARCH_PARAMS = {
    "namespace": settings.DEFAULT_NAMESPACE,
    "start_time": start_time.isoformat(),
    "end_time": end_time.isoformat(),
    "conditions": [
        {"field": {"raw_name": "system_id", "field_type": "string"}, "operator": "include", "filters": ["s1", "s2"]},
        {
            "field": {"raw_name": "action_id", "field_type": "string"},
            "operator": "include",
            "filters": ["create_link_table"],
        },
        {
            "field": {"raw_name": "resource_type_id", "field_type": "string"},
            "operator": "include",
            "filters": ["audit_log", "notice_group"],
        },
        {"field": {"raw_name": "instance_name", "field_type": "string"}, "operator": "like", "filters": ["123131"]},
        {"field": {"raw_name": "username", "field_type": "string"}, "operator": "include", "filters": ["xxx"]},
        {"field": {"raw_name": "event_id", "field_type": "string"}, "operator": "include", "filters": ["xxx"]},
        {"field": {"raw_name": "request_id", "field_type": "string"}, "operator": "include", "filters": ["xxx"]},
        {"field": {"raw_name": "instance_id", "field_type": "string"}, "operator": "include", "filters": ["xxx"]},
        {"field": {"raw_name": "log", "field_type": "string"}, "operator": "match_any", "filters": ["12313"]},
        {"field": {"raw_name": "access_type", "field_type": "int"}, "operator": "include", "filters": [1, 2, -1]},
        {"field": {"raw_name": "access_source_ip", "field_type": "int"}, "operator": "include", "filters": ["1.2.3.4"]},
        {"field": {"raw_name": "event_content", "field_type": "string"}, "operator": "like", "filters": ["123123"]},
        {"field": {"raw_name": "user_identify_type", "field_type": "int"}, "operator": "include", "filters": [0, 1]},
        {"field": {"raw_name": "access_user_agent", "field_type": "string"}, "operator": "like", "filters": ["1"]},
        {"field": {"raw_name": "result_content", "field_type": "int"}, "operator": "include", "filters": [1]},
        {
            "field": {"raw_name": "instance_data", "field_type": "string", "keys": ["k1", "k2"]},
            "operator": "include",
            "filters": [1],
        },
        {
            "field": {"raw_name": "instance_origin_data", "field_type": "int", "keys": ["k1", "k2"]},
            "operator": "include",
            "filters": [1],
        },
        {
            "field": {"raw_name": "extend_data", "field_type": "string", "keys": ["k1", "k2"]},
            "operator": "include",
            "filters": [1],
        },
        {
            "field": {"raw_name": "snapshot_resource_type_info", "field_type": "int", "keys": ["k1", "k2"]},
            "operator": "include",
            "filters": [1],
        },
        {
            "field": {"raw_name": "snapshot_action_info", "field_type": "string", "keys": ["k1", "k2"]},
            "operator": "like",
            "filters": [1],
        },
        {
            "field": {"raw_name": "snapshot_instance_data", "field_type": "string", "keys": ["k1", "k2"]},
            "operator": "like",
            "filters": [1],
        },
    ],
    "page": PAGE,
    "page_size": PAGE_SIZE,
}

# CollectorSearch BKBASE RESP
BKBASE_COLLECTOR_SEARCH_DATA_RESP = {
    "list": [
        {
            '__ext': None,
            '__shard_key__': 29012278003,
            'access_source_ip': '1.2.3.4',
            'access_type': 0,
            'access_user_agent': 'Mozilla/5.0',
            'action_id': 'view_system',
            'bk_app_code': 'bk-audit',
            'bk_data_id': 546009,
            'bk_receive_time': 1740736711,
            'bk_storage_time': None,
            'cloudid': 0,
            'collector_config_id': 912,
            'dteventtime': '2025-02-28 17:58:29',
            'dteventtimestamp': 1740736709614,
            'end_time': 1740736709625,
            'event_content': '获取系统详情',
            'event_id': '8fc08ffff5ba11efae7aded3b5168cdb',
            'extend_data': '{"request_data":{"namespace":"default","system_id":"bk-audit"}}',
            'gseindex': 84079,
            'instance_data': '{}',
            'instance_id': 'bk-audit',
            'instance_name': 'bk-audit',
            'instance_origin_data': '{}',
            'iterationindex': 0,
            'localtime': '2025-02-28 17:58:00',
            'log': '{}',
            'path': None,
            'request_id': '8014a83c39b7215696f9be7e1a6671ea',
            'resource_type_id': 'system',
            'result_code': 0,
            'result_content': '',
            'scope_id': '',
            'scope_type': '',
            'serverip': '',
            'snapshot_action_info': '{"action_id":"view_system","created_at":1666854601129,"created_by":"bk-audit",'
            '"description":"","id":922,"name":"系统查看","name_en":"View System",'
            '"sensitivity":0,"system_id":"bk-audit","type":"view",'
            '"updated_at":1666854601148,"updated_by":"bk-audit","version":1}',
            'snapshot_instance_data': None,
            'snapshot_instance_name': None,
            'snapshot_resource_type_info': '{"created_at":1666854601123,"created_by":"bk-audit","description":"",'
            '"id":127,"name":"接入系统","name_en":"Systems",'
            '"resource_type_id":"system","sensitivity":0,"system_id":"bk-audit",'
            '"updated_at":1666854602110,"updated_by":"bk-audit","version":1}',
            'snapshot_user_info': '{"department_full_name":"xxx/xxx","department_id":123,"department_name":"xxx",'
            '"department_path":"xxx/xxx","display_name":"xxx","enabled":1,"gender":"男",'
            '"id":123,"leader_username":"xxx","manager_level":0,'
            '"manager_unit_name":123,"move_type_id":1,"phone":"","staff_status":1,'
            '"staff_type":3,"username":"xxx"}',
            'start_time': 1740736709614,
            'system_id': 'bk-audit',
            'thedate': 20250228,
            'time': 1740736709614,
            'user_identify_src': '',
            'user_identify_src_username': '',
            'user_identify_tenant_id': '',
            'user_identify_type': -1,
            'username': 'xxx',
        }
    ]
}

# CollectorSearch Bkbase Count Resp
BKBASE_COLLECTOR_SEARCH_COUNT_RESP = {"list": [{'count': 1}]}

# CollectorSearch BKBASE API
BKBASE_COLLECTOR_SEARCH_API_RESP = [BKBASE_COLLECTOR_SEARCH_DATA_RESP, BKBASE_COLLECTOR_SEARCH_COUNT_RESP]

# CollectorSearch Resp
COLLECTOR_SEARCH_DATA_RESP = {
    "page": 1,
    "num_pages": 10,
    "total": 1,
    "results": [
        {
            "__ext": None,
            "__shard_key__": 29012278003,
            "access_source_ip": "1.2.3.4",
            "access_type": "WebUI",
            "access_user_agent": "Mozilla/5.0",
            "action_id": "view_system",
            "bk_app_code": "bk-audit",
            "bk_data_id": 546009,
            "bk_receive_time": 1740736711,
            "bk_storage_time": None,
            "cloudid": 0,
            "collector_config_id": 912,
            "dteventtime": "2025-02-28 17:58:29",
            "dteventtimestamp": 1740736709614,
            "end_time": "2025-02-28 17:58:29",
            "event_content": "\u83b7\u53d6\u7cfb\u7edf\u8be6\u60c5",
            "event_id": "8fc08ffff5ba11efae7aded3b5168cdb",
            "extend_data": {"request_data": {"namespace": "default", "system_id": "bk-audit"}},
            "gseindex": 84079,
            "instance_data": {},
            "instance_id": "bk-audit",
            "instance_name": "bk-audit",
            "instance_origin_data": {},
            "iterationindex": 0,
            "localtime": "2025-02-28 17:58:00",
            "log": "{}",
            "path": None,
            "request_id": "8014a83c39b7215696f9be7e1a6671ea",
            "resource_type_id": "system",
            "result_code": "\u6210\u529f(0)",
            "result_content": "",
            "scope_id": "",
            "scope_type": "",
            "serverip": "",
            "snapshot_action_info": {
                "action_id": "view_system",
                "created_at": 1666854601129,
                "created_by": "bk-audit",
                "description": "",
                "id": 922,
                "name": "\u7cfb\u7edf\u67e5\u770b",
                "name_en": "View System",
                "sensitivity": 0,
                "system_id": "bk-audit",
                "type": "view",
                "updated_at": 1666854601148,
                "updated_by": "bk-audit",
                "version": 1,
            },
            "snapshot_instance_data": {},
            "snapshot_instance_name": None,
            "snapshot_resource_type_info": {
                "created_at": 1666854601123,
                "created_by": "bk-audit",
                "description": "",
                "id": 127,
                "name": "\u63a5\u5165\u7cfb\u7edf",
                "name_en": "Systems",
                "resource_type_id": "system",
                "sensitivity": 0,
                "system_id": "bk-audit",
                "updated_at": 1666854602110,
                "updated_by": "bk-audit",
                "version": 1,
            },
            "snapshot_user_info": {
                "department_full_name": "xxx/xxx",
                "department_id": "123",
                "department_name": "xxx",
                "department_path": "xxx/xxx",
                "display_name": "xxx",
                "enabled": "1",
                "gender": "\u7537",
                "id": "123",
                "leader_username": "xxx",
                "manager_level": "0",
                "manager_unit_name": "123",
                "move_type_id": "1",
                "phone": "",
                "staff_status": "1",
                "staff_type": "3",
                "username": "xxx",
            },
            "start_time": "2025-02-28 17:58:29",
            "system_id": "bk-audit",
            "thedate": 20250228,
            "time": 1740736709614,
            "user_identify_src": "",
            "user_identify_src_username": "",
            "user_identify_tenant_id": "",
            "user_identify_type": "-1",
            "username": "xxx",
            "system_info": {},
        }
    ],
    "query_sql": f"SELECT * FROM {PLUGIN_RESULT_TABLE} WHERE `system_id` IN ('bk-audit') "
    f"AND `thedate`>='{start_date}' AND `thedate`<='{end_date}' "
    f"AND `dtEventTimeStamp`>={start_timestamp} AND `dtEventTimeStamp`<={end_timestamp} AND `system_id` "
    f"IN ('s1','s2') AND `action_id` IN ('create_link_table') "
    "AND `resource_type_id` IN ('audit_log','notice_group') AND `instance_name` "
    "LIKE '%123131%' AND `username` IN ('xxx') AND `event_id` IN ('xxx') AND `request_id` "
    "IN ('xxx') AND `instance_id` IN ('xxx') AND `log` MATCH_ANY ('12313') AND `access_type` "
    "IN (1,2,-1) AND `access_source_ip` IN ('1.2.3.4') AND `event_content` LIKE '%123123%' "
    "AND `user_identify_type` IN (0,1) AND `access_user_agent` LIKE '%1%' AND `result_content` "
    "IN (1) AND JSON_EXTRACT_STRING(`instance_data`,'$.k1.k2') IN (1) "
    "AND JSON_EXTRACT_STRING(`instance_origin_data`,'$.k1.k2') IN (1) "
    "AND JSON_EXTRACT_STRING(`extend_data`,'$.k1.k2') IN (1) AND `snapshot_resource_type_info`['k1']['k2'] IN (1) "
    "AND `snapshot_action_info`['k1']['k2'] LIKE '%1%' AND JSON_EXTRACT_STRING(`snapshot_instance_data`,'$.k1.k2') "
    f"LIKE '%1%' ORDER BY `dtEventTimeStamp` DESC,`gseIndex` DESC,`iterationIndex` DESC LIMIT 10",
    "count_sql": f"SELECT COUNT(*) `count` FROM {PLUGIN_RESULT_TABLE} "
    f"WHERE `system_id` IN ('bk-audit') AND `thedate`>='{start_date}' AND `thedate`<='{end_date}' "
    f"AND `dtEventTimeStamp`>={start_timestamp} AND `dtEventTimeStamp`<={end_timestamp} "
    f"AND `system_id` IN ('s1','s2') AND `action_id` "
    "IN ('create_link_table') AND `resource_type_id` IN ('audit_log','notice_group') AND `instance_name` "
    "LIKE '%123131%' AND `username` IN ('xxx') AND `event_id` IN ('xxx') AND `request_id` IN ('xxx') "
    "AND `instance_id` IN ('xxx') AND `log` MATCH_ANY ('12313') AND `access_type` IN (1,2,-1) "
    "AND `access_source_ip` IN ('1.2.3.4') AND `event_content` LIKE '%123123%' AND `user_identify_type` "
    "IN (0,1) AND `access_user_agent` LIKE '%1%' AND `result_content` IN (1) "
    "AND JSON_EXTRACT_STRING(`instance_data`,'$.k1.k2') IN (1) "
    "AND JSON_EXTRACT_STRING(`instance_origin_data`,'$.k1.k2') IN (1) "
    "AND JSON_EXTRACT_STRING(`extend_data`,'$.k1.k2') IN (1) AND `snapshot_resource_type_info`['k1']['k2'] IN (1) "
    "AND `snapshot_action_info`['k1']['k2'] LIKE '%1%' AND JSON_EXTRACT_STRING(`snapshot_instance_data`,'$.k1.k2') "
    f"LIKE '%1%' LIMIT 1",
}

COLLECTOR_SEARCH_ALL_DATA_RESP = {
    "page": 1,
    "num_pages": 10,
    "total": 1,
    "results": [
        {
            "__ext": None,
            "__shard_key__": 29012278003,
            "access_source_ip": "1.2.3.4",
            "access_type": "WebUI",
            "access_user_agent": "Mozilla/5.0",
            "action_id": "view_system",
            "bk_app_code": "bk-audit",
            "bk_data_id": 546009,
            "bk_receive_time": 1740736711,
            "bk_storage_time": None,
            "cloudid": 0,
            "collector_config_id": 912,
            "dteventtime": "2025-02-28 17:58:29",
            "dteventtimestamp": 1740736709614,
            "end_time": "2025-02-28 17:58:29",
            "event_content": "\u83b7\u53d6\u7cfb\u7edf\u8be6\u60c5",
            "event_id": "8fc08ffff5ba11efae7aded3b5168cdb",
            "extend_data": {"request_data": {"namespace": "default", "system_id": "bk-audit"}},
            "gseindex": 84079,
            "instance_data": {},
            "instance_id": "bk-audit",
            "instance_name": "bk-audit",
            "instance_origin_data": {},
            "iterationindex": 0,
            "localtime": "2025-02-28 17:58:00",
            "log": "{}",
            "path": None,
            "request_id": "8014a83c39b7215696f9be7e1a6671ea",
            "resource_type_id": "system",
            "result_code": "\u6210\u529f(0)",
            "result_content": "",
            "scope_id": "",
            "scope_type": "",
            "serverip": "",
            "snapshot_action_info": {
                "action_id": "view_system",
                "created_at": 1666854601129,
                "created_by": "bk-audit",
                "description": "",
                "id": 922,
                "name": "\u7cfb\u7edf\u67e5\u770b",
                "name_en": "View System",
                "sensitivity": 0,
                "system_id": "bk-audit",
                "type": "view",
                "updated_at": 1666854601148,
                "updated_by": "bk-audit",
                "version": 1,
            },
            "snapshot_instance_data": {},
            "snapshot_instance_name": None,
            "snapshot_resource_type_info": {
                "created_at": 1666854601123,
                "created_by": "bk-audit",
                "description": "",
                "id": 127,
                "name": "\u63a5\u5165\u7cfb\u7edf",
                "name_en": "Systems",
                "resource_type_id": "system",
                "sensitivity": 0,
                "system_id": "bk-audit",
                "updated_at": 1666854602110,
                "updated_by": "bk-audit",
                "version": 1,
            },
            "snapshot_user_info": {
                "department_full_name": "xxx/xxx",
                "department_id": "123",
                "department_name": "xxx",
                "department_path": "xxx/xxx",
                "display_name": "xxx",
                "enabled": "1",
                "gender": "\u7537",
                "id": "123",
                "leader_username": "xxx",
                "manager_level": "0",
                "manager_unit_name": "123",
                "move_type_id": "1",
                "phone": "",
                "staff_status": "1",
                "staff_type": "3",
                "username": "xxx",
            },
            "start_time": "2025-02-28 17:58:29",
            "system_id": "bk-audit",
            "thedate": 20250228,
            "time": 1740736709614,
            "user_identify_src": "",
            "user_identify_src_username": "",
            "user_identify_tenant_id": "",
            "user_identify_type": "-1",
            "username": "xxx",
            "system_info": {},
        }
    ],
    "query_sql": f"SELECT * FROM {PLUGIN_RESULT_TABLE} WHERE `thedate`>='{start_date}' AND `thedate`<='{end_date}' "
    f"AND `dtEventTimeStamp`>={start_timestamp} AND `dtEventTimeStamp`<={end_timestamp} AND `system_id` "
    f"IN ('s1','s2') AND `action_id` IN ('create_link_table') "
    "AND `resource_type_id` IN ('audit_log','notice_group') AND `instance_name` "
    "LIKE '%123131%' AND `username` IN ('xxx') AND `event_id` IN ('xxx') AND `request_id` "
    "IN ('xxx') AND `instance_id` IN ('xxx') AND `log` MATCH_ANY ('12313') AND `access_type` "
    "IN (1,2,-1) AND `access_source_ip` IN ('1.2.3.4') AND `event_content` LIKE '%123123%' "
    "AND `user_identify_type` IN (0,1) AND `access_user_agent` LIKE '%1%' AND `result_content` "
    "IN (1) AND JSON_EXTRACT_STRING(`instance_data`,'$.k1.k2') IN (1) AND "
    "JSON_EXTRACT_STRING(`instance_origin_data`,'$.k1.k2') IN (1) "
    "AND JSON_EXTRACT_STRING(`extend_data`,'$.k1.k2') IN (1) AND `snapshot_resource_type_info`['k1']['k2'] IN (1) "
    "AND `snapshot_action_info`['k1']['k2'] LIKE '%1%' AND JSON_EXTRACT_STRING(`snapshot_instance_data`,'$.k1.k2') "
    f"LIKE '%1%' ORDER BY `dtEventTimeStamp` DESC,`gseIndex` DESC,`iterationIndex` DESC LIMIT 10",
    "count_sql": f"SELECT COUNT(*) `count` FROM {PLUGIN_RESULT_TABLE} "
    f"WHERE `thedate`>='{start_date}' AND `thedate`<='{end_date}' "
    f"AND `dtEventTimeStamp`>={start_timestamp} AND `dtEventTimeStamp`<={end_timestamp} "
    f"AND `system_id` IN ('s1','s2') AND `action_id` "
    "IN ('create_link_table') AND `resource_type_id` IN ('audit_log','notice_group') AND `instance_name` "
    "LIKE '%123131%' AND `username` IN ('xxx') AND `event_id` IN ('xxx') AND `request_id` IN ('xxx') "
    "AND `instance_id` IN ('xxx') AND `log` MATCH_ANY ('12313') AND `access_type` IN (1,2,-1) "
    "AND `access_source_ip` IN ('1.2.3.4') AND `event_content` LIKE '%123123%' AND `user_identify_type` "
    "IN (0,1) AND `access_user_agent` LIKE '%1%' AND `result_content` IN (1) "
    "AND JSON_EXTRACT_STRING(`instance_data`,'$.k1.k2') IN (1) "
    "AND JSON_EXTRACT_STRING(`instance_origin_data`,'$.k1.k2') IN (1) "
    "AND JSON_EXTRACT_STRING(`extend_data`,'$.k1.k2') IN (1) AND `snapshot_resource_type_info`['k1']['k2'] IN (1) "
    "AND `snapshot_action_info`['k1']['k2'] LIKE '%1%' AND JSON_EXTRACT_STRING(`snapshot_instance_data`,'$.k1.k2') "
    f"LIKE '%1%' LIMIT 1",
}

# CollectorSearchData
COLLECTOR_SEARCH_DATA = {
    "page": PAGE,
    "num_pages": PAGE_SIZE,
    "total": ES_QUERY_SEARCH_API_RESP["hits"]["total"],
    "results": [{"system_info": item["system_id"]} for item in ES_QUERY_SEARCH_API_RESP["hits"]["hits"]],
    "scroll_id": None,
}

# CollectorSearchConfig
COLLECTOR_SEARCH_CONFIG = COLLECT_SEARCH_CONFIG.to_json()

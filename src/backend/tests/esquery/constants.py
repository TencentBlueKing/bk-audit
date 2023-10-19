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

from django.conf import settings
from django.utils.translation import gettext_lazy
from iam import Resource

from apps.meta.utils.fields import ACCESS_TYPE, RESULT_CODE
from apps.permission.handlers.actions import ActionMeta
from services.web.esquery.constants import DEFAULT_TIMEDELTA as _DEFAULT_TIMEDELTA
from tests.databus.collector_plugin.constants import INDEX_SET_ID as _INDEX_SET_ID
from tests.databus.collector_plugin.constants import PLUGIN_DATA as _PLUGIN_DATA

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
        {"permission": {"search_regular_event": "test"}, "id": settings.APP_CODE},
        {"permission": {"view_system": "test"}, "id": settings.APP_CODE},
    ],
    [settings.APP_CODE],
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

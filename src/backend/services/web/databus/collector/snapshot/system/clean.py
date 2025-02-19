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

import json

from bk_resource import api
from bk_resource.settings import bk_resource_settings
from django.conf import settings

from core.models import get_request_username
from services.web.databus.utils import start_bkbase_clean


class PullCleanHandler:
    def __init__(self, bkbase_data_id, clean_config_name, resource_type=None):
        self.clean_config_name = clean_config_name
        self.bkbase_data_id = bkbase_data_id
        self.resource_type = resource_type

    @classmethod
    def get_fields(cls, resource_type=None):
        fields = [
            {
                "field_name": "utctime",
                "field_type": "string",
                "field_alias": "上报时间",
                "is_dimension": False,
                "is_key": False,
                "field_index": 1,
            },
            {
                "field_name": "data",
                "field_type": "text",
                "field_alias": "实例内容",
                "is_dimension": False,
                "is_key": False,
                "field_index": 2,
            },
            {
                "field_name": "id",
                "field_type": "string",
                "field_alias": "ID",
                "is_dimension": False,
                "is_key": True,
                "field_index": 4,
            },
            {
                "field_name": "display_name",
                "field_type": "string",
                "field_alias": "名称",
                "is_dimension": False,
                "is_key": False,
                "field_index": 5,
            },
            {
                "field_name": "creator",
                "field_type": "string",
                "field_alias": "创建人",
                "is_dimension": False,
                "is_key": False,
                "field_index": 6,
            },
            {
                "field_name": "created_at",
                "field_type": "long",
                "field_alias": "创建时间",
                "is_dimension": False,
                "is_key": False,
                "field_index": 7,
            },
            {
                "field_name": "updater",
                "field_type": "string",
                "field_alias": "更新人",
                "is_dimension": False,
                "is_key": False,
                "field_index": 8,
            },
            {
                "field_name": "updated_at",
                "field_type": "long",
                "field_alias": "更新时间",
                "is_dimension": False,
                "is_key": False,
                "field_index": 9,
            },
        ]
        if resource_type != "user":
            fields.append(
                {
                    "field_name": "system_id",
                    "field_type": "string",
                    "field_alias": "系统ID",
                    "is_dimension": False,
                    "is_key": True,
                    "field_index": 3,
                }
            )
        return fields

    @property
    def config(self):
        _json_config = {
            "extract": {
                "type": "fun",
                "method": "from_json",
                "result": "json_data",
                "label": "labelf780f8",
                "args": [],
                "next": {
                    "type": "branch",
                    "name": "",
                    "label": None,
                    "next": [
                        {
                            "type": "assign",
                            "subtype": "assign_obj",
                            "label": "label61980a",
                            "assign": [{"type": "string", "assign_to": "utctime", "key": "utctime"}],
                            "next": None,
                        },
                        {
                            "type": "access",
                            "subtype": "access_obj",
                            "label": "labelcbac43",
                            "key": "data",
                            "result": "response_content",
                            "default_type": "null",
                            "default_value": "",
                            "next": {
                                "type": "fun",
                                "method": "from_json",
                                "result": "response_json",
                                "label": "label9593a0",
                                "args": [],
                                "next": {
                                    "type": "access",
                                    "subtype": "access_obj",
                                    "label": "label0dde40",
                                    "key": "data",
                                    "result": "response_data",
                                    "default_type": "null",
                                    "default_value": "",
                                    "next": {
                                        "type": "access",
                                        "subtype": "access_obj",
                                        "label": "label2c31ee",
                                        "key": "results",
                                        "result": "response_results",
                                        "default_type": "null",
                                        "default_value": "",
                                        "next": {
                                            "type": "fun",
                                            "label": "labelc1f7e1",
                                            "result": "item",
                                            "args": [],
                                            "method": "iterate",
                                            "next": {
                                                "type": "branch",
                                                "name": "",
                                                "label": None,
                                                "next": [
                                                    {
                                                        "type": "assign",
                                                        "subtype": "assign_json",
                                                        "label": "label21391f",
                                                        "assign": [
                                                            {"type": "text", "assign_to": "data", "key": "data"}
                                                        ],
                                                        "next": None,
                                                    },
                                                    {
                                                        "type": "assign",
                                                        "subtype": "assign_obj",
                                                        "label": "labeld25e39",
                                                        "assign": [
                                                            {"type": "string", "assign_to": "id", "key": "id"},
                                                            {
                                                                "type": "string",
                                                                "assign_to": "display_name",
                                                                "key": "display_name",
                                                            },
                                                            {
                                                                "type": "string",
                                                                "assign_to": "creator",
                                                                "key": "creator",
                                                            },
                                                            {
                                                                "type": "long",
                                                                "assign_to": "created_at",
                                                                "key": "created_at",
                                                            },
                                                            {
                                                                "type": "string",
                                                                "assign_to": "updater",
                                                                "key": "updater",
                                                            },
                                                            {
                                                                "type": "long",
                                                                "assign_to": "updated_at",
                                                                "key": "updated_at",
                                                            },
                                                        ],
                                                        "next": None,
                                                    },
                                                ],
                                            },
                                        },
                                    },
                                },
                            },
                        },
                    ],
                },
            },
            "conf": {
                "time_format": "yyyy-MM-dd HH:mm:ss",
                "timezone": 0,
                "time_field_name": "utctime",
                "output_field_name": "timestamp",
                "timestamp_len": 0,
                "encoding": "UTF-8",
            },
        }
        if self.resource_type != "user":
            _json_config["extract"]["next"]["next"][1]["next"]["next"]["next"]["next"]["next"]["next"].append(
                {
                    "type": "access",
                    "subtype": "access_obj",
                    "label": "label6932bf",
                    "key": "data",
                    "result": "item_data",
                    "default_type": "null",
                    "default_value": "",
                    "next": {
                        "type": "assign",
                        "subtype": "assign_obj",
                        "label": "label2962d4",
                        "assign": [
                            {
                                "type": "string",
                                "assign_to": "system_id",
                                "key": "system_id",
                            }
                        ],
                        "next": None,
                    },
                },
            )
        return {
            "bk_biz_id": settings.DEFAULT_BK_BIZ_ID,
            "bk_username": bk_resource_settings.PLATFORM_AUTH_ACCESS_USERNAME,
            "clean_config_name": self.clean_config_name,
            "description": self.clean_config_name,
            "fields": self.get_fields(self.resource_type),
            "json_config": json.dumps(_json_config),
            "raw_data_id": self.bkbase_data_id,
            "result_table_name": self.clean_config_name,
            "result_table_name_alias": self.clean_config_name,
        }

    def create_clean(self):
        print(f"[HttpPull] Params => {self.config}")
        resp = api.bk_base.databus_cleans_post(self.config)
        start_bkbase_clean(resp["result_table_id"], resp["processing_id"], get_request_username())
        return resp

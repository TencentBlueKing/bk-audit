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
import json
import os
import uuid

from bk_resource import api
from bk_resource.settings import bk_resource_settings
from django.conf import settings

from apps.meta.models import GlobalMetaConfig
from apps.meta.utils.saas import get_saas_url
from apps.permission.constants import FETCH_INSTANCE_TOKEN_KEY
from apps.permission.handlers.permission import FetchInstancePermission
from services.web.databus.constants import (
    ACTION_DATA_NAME_FORMAT,
    RESOURCE_TYPE_DATA_NAME_FORMAT,
    USER_INFO_DATA_NAME_FORMAT,
)


class HttpPullHandler:
    def __init__(self, resource_type: str):
        now = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        self.resource_type = resource_type
        # 获取结果表名
        if resource_type == "resource_type":
            self.raw_data_name = RESOURCE_TYPE_DATA_NAME_FORMAT.format(now)
        elif resource_type == "action":
            self.raw_data_name = ACTION_DATA_NAME_FORMAT.format(now)
        elif resource_type == "user":
            self.raw_data_name = USER_INFO_DATA_NAME_FORMAT.format(now)
        else:
            raise Exception(f"ResourceType Does Not Support => {resource_type}")
        # 获取认证与URL
        if resource_type == "user":
            self.token = FetchInstancePermission.build_auth(
                settings.FETCH_INSTANCE_USERNAME, os.getenv("BKAPP_FETCH_USER_INFO_TOKEN", "")
            )
            self.url = settings.SNAPSHOT_USERINFO_RESOURCE_URL
        else:
            password = GlobalMetaConfig.get(FETCH_INSTANCE_TOKEN_KEY, default=uuid.uuid4().hex)
            GlobalMetaConfig.set(FETCH_INSTANCE_TOKEN_KEY, password)
            self.token = FetchInstancePermission.build_auth(settings.FETCH_INSTANCE_USERNAME, password)
            self.url = get_saas_url(settings.APP_CODE, module_name="puller") + "/api/v1/resources/"

    def build_params(self):
        return {
            "bk_app_code": settings.APP_CODE,
            "bk_app_secret": settings.SECRET_KEY,
            "bk_username": bk_resource_settings.PLATFORM_AUTH_ACCESS_USERNAME,
            "data_scenario": "http",
            "bk_biz_id": settings.DEFAULT_BK_BIZ_ID,
            "description": "BkAudit Snapshot Data",
            "bkdata_authentication_method": "user",
            "reset_to_head": True,
            "access_raw_data": {
                "data_source_tags": [
                    "server",
                ],
                "data_source": "svr",
                "maintainer": bk_resource_settings.PLATFORM_AUTH_ACCESS_USERNAME,
                "description": "",
                "tags": [],
                "raw_data_name": self.raw_data_name,
                "sensitivity": "private",
                "data_encoding": "UTF-8",
                "raw_data_alias": self.raw_data_name,
                "data_region": settings.BKBASE_DATA_REGION,
            },
            "access_conf_info": {
                "collection_model": {
                    "collection_type": "pull",
                    "increment_field": "",
                    "period": 1,
                    "time_format": "Unix Time Stamp(milliseconds)",
                },
                "filters": {},
                "resource": {
                    "scope": [
                        {
                            "method": "post",
                            "url": self.url,
                            "headers": {
                                "Content-type": "application/json",
                                "Authorization": self.token,
                            },
                            "body": {
                                "time": {
                                    "enabled": True,
                                    "format": "Unix Time Stamp(milliseconds)",
                                    "delay": {
                                        "unit": "minute",
                                        "value": 1,
                                    },
                                },
                                "page": {
                                    "enabled": True,
                                    "total_path": ".data.count",
                                    "limit": 100,
                                    "start_offset": 0,
                                },
                                "url_params": {},
                                "content": json.dumps(
                                    {
                                        "type": self.resource_type,
                                        "method": "fetch_instance_list",
                                        "filter": {"start_time": "<start>", "end_time": "<end>"},
                                        "page": {"offset": "<offset>", "limit": "<limit>"},
                                    }
                                ),
                            },
                        }
                    ]
                },
            },
        }

    def create_data_id(self):
        params = self.build_params()
        return self.raw_data_name, api.bk_base.create_deploy_plan(params)["raw_data_id"]

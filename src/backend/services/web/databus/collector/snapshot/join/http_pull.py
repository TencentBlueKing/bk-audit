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

import base64

from bk_resource import api
from bk_resource.settings import bk_resource_settings
from blueapps.utils.logger import logger
from django.conf import settings

from apps.meta.models import ResourceType, System
from services.web.databus.constants import (
    ASSET_RT_FORMAT,
    JOIN_DATA_RT_FORMAT,
    DefaultPullConfig,
    JoinDataPullType,
    JoinDataType,
    SensitivityChoice,
)
from services.web.databus.models import Snapshot


class HttpPullHandler:
    def __init__(self, system: System, resource_type: ResourceType, snapshot: Snapshot, join_data_type: str):
        self.system = system
        self.system_id = system.system_id
        self.resource_type = resource_type
        self.resource_type_id = resource_type.resource_type_id
        self.snapshot = snapshot
        self.join_data_type = join_data_type
        self.pull_config = self.snapshot.pull_config or {}
        self.pull_type = self.snapshot.pull_type

    def update_or_create(self):
        params = self.config

        # 更新
        if self.snapshot.bkbase_data_id:
            logger.info(f"{self.__class__.__name__} Update DataID => {self.snapshot.bkbase_data_id}")
            params.update({"bkbase_data_id": self.snapshot.bkbase_data_id})
            api.bk_base.update_deploy_plan(params)
            return self.snapshot.bkbase_data_id

        # 创建
        logger.info(f"{self.__class__.__name__} Create DataID => {self.snapshot.bkbase_data_id}")
        result = api.bk_base.create_deploy_plan(params)
        return result["raw_data_id"]

    @property
    def url(self):
        return (
            self.system.provider_config["host"].rstrip("/")
            + "/"
            + self.resource_type.provider_config["path"].lstrip("/")
        )

    @property
    def authorization(self):
        base64_token = base64.b64encode(
            f"{settings.FETCH_INSTANCE_USERNAME}:{self.system.provider_config['token']}".encode("utf-8")
        ).decode("utf-8")
        return f"Basic {base64_token}"

    @property
    def config_name(self):
        if self.join_data_type == JoinDataType.ASSET:
            return ASSET_RT_FORMAT.format(system_id=self.system_id, resource_type_id=self.resource_type_id).replace(
                "-", "_"
            )
        else:
            return JOIN_DATA_RT_FORMAT.format(system_id=self.system_id, resource_type_id=self.resource_type_id).replace(
                "-", "_"
            )

    @property
    def pull_sensitivity(self) -> str:
        return self.pull_config.get("sensitivity", SensitivityChoice.PRIVATE)

    @property
    def pull_period(self) -> int:
        default_period = (
            DefaultPullConfig.period if self.pull_type == JoinDataPullType.PARTIAL else DefaultPullConfig.full_period
        )
        return int(self.pull_config.get("period", default_period))

    @property
    def pull_delay(self) -> int:
        return int(self.pull_config.get("delay", DefaultPullConfig.delay))

    @property
    def pull_pagesize(self) -> int:
        return int(self.pull_config.get("limit", DefaultPullConfig.limit))

    @property
    def pull_content(self) -> str:
        return (
            (
                "{"
                f'"type": "{self.resource_type_id}", '
                '"method": "fetch_instance_list", '
                '"filter": {"start_time": <start>, "end_time": <end>}, '
                '"page": {"offset": <offset>, "limit": <limit>}'
                "}"
            )
            if self.pull_type == JoinDataPullType.PARTIAL
            else (
                "{"
                f'"type": "{self.resource_type_id}", '
                '"method": "fetch_instance_list", '
                '"filter": {"start_time": 0, "end_time": <end>}, '
                '"page": {"offset": <offset>, "limit": <limit>}'
                "}"
            )
        )

    @property
    def config(self):
        # 配置
        return {
            "bk_username": bk_resource_settings.PLATFORM_AUTH_ACCESS_USERNAME,
            "data_scenario": "http",
            "bk_biz_id": settings.DEFAULT_BK_BIZ_ID,
            "description": "BKAudit Pull Instance Data",
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
                "raw_data_name": self.config_name,
                "sensitivity": self.pull_sensitivity,
                "data_encoding": "UTF-8",
                "raw_data_alias": self.config_name,
                "data_region": "inland",
            },
            "access_conf_info": {
                "collection_model": {
                    "collection_type": "pull",
                    "increment_field": "",
                    "period": self.pull_period,
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
                                "Authorization": self.authorization,
                            },
                            "body": {
                                "time": {
                                    "enabled": True,
                                    "format": "Unix Time Stamp(milliseconds)",
                                    "delay": {
                                        "unit": "minute",
                                        "value": self.pull_delay,
                                    },
                                },
                                "page": {
                                    "enabled": True,
                                    "total_path": ".data.count",
                                    "limit": self.pull_pagesize,
                                    "start_offset": 0,
                                },
                                "url_params": {},
                                "content": self.pull_content,
                            },
                        }
                    ]
                },
            },
        }

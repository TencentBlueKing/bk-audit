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

from bk_resource.settings import bk_resource_settings
from blueapps.utils.logger import logger
from django.conf import settings
from django.utils.translation import gettext_lazy as _

from apps.meta.models import ResourceType, System
from apps.meta.utils.builtin_assets import builtin_asset_callback_headers
from services.web.bkbase import source as bkbase_source
from services.web.bkbase.common import get_bkbase_version
from services.web.bkbase.constants import BKBaseVersion
from services.web.databus.constants import (
    ASSET_RT_FORMAT,
    JOIN_DATA_RT_FORMAT,
    DefaultPullConfig,
    JoinDataPullType,
    JoinDataType,
    SensitivityChoice,
    SnapshotRunningStatus,
)
from services.web.databus.exceptions import SecurityForbiddenError
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

        if get_bkbase_version() == BKBaseVersion.V4 and (
            not self.snapshot.bkbase_data_id
            or (
                self.snapshot.status != SnapshotRunningStatus.RUNNING
                and (self.snapshot.bkbase_v4_resources or {}).get("source_provision")
            )
        ):
            if (self.snapshot.bkbase_v4_resources or {}).get("source_provision", {}).get("stage") == "ready":
                return None
            return bkbase_source.create_deploy_plan(params, snapshot=self.snapshot)

        # 更新
        if self.snapshot.bkbase_data_id:
            logger.info(f"{self.__class__.__name__} Update DataID => {self.snapshot.bkbase_data_id}")
            params.update({"bkbase_data_id": self.snapshot.bkbase_data_id})
            bkbase_source.update_deploy_plan(params, snapshot=self.snapshot)
            return self.snapshot.bkbase_data_id

        # 创建
        logger.info(f"{self.__class__.__name__} Create DataID => {self.snapshot.bkbase_data_id}")
        result = bkbase_source.create_deploy_plan(params)
        return result["raw_data_id"]

    def advance_provision(self):
        """在后台事务之外推进新 PULL。"""
        return bkbase_source.advance_source_provision(self.snapshot, self.config)

    def prepare_replay(self):
        """由周期刷新排队已有Asset/Basic纯重放，不走新建数字ID入口。"""
        return bkbase_source.prepare_snapshot_replay(self.snapshot, self.config)

    def advance_replay(self):
        """推进已排队的源维护，终止于源观察，不调用清洗和入库。"""
        return bkbase_source.advance_snapshot_replay(self.snapshot, self.config)

    def validate_url_security(self, url: str) -> None:
        """
        校验URL安全性
        1. 检查URL是否为空
        2. 检查URL是否以http://或https://开头
        3. 检查URL是否包含高危端口
        """
        if not url:
            raise SecurityForbiddenError(messages=_("URL不能为空"))

        from urllib.parse import urlparse

        parsed = urlparse(url)

        if parsed.scheme not in ("http", "https"):
            raise SecurityForbiddenError(message=_("URL必须使用http或https协议"))

        if parsed.port and parsed.port in settings.HIGH_RISK_PORTS:
            raise SecurityForbiddenError(message=_("URL包含高危端口: {}").format(parsed.port))

    @property
    def raw_url(self):
        return self.resource_type.resource_request_url(system=self.system)

    @property
    def url(self):
        url = self.raw_url
        self.validate_url_security(url)
        return url

    @property
    def authorization(self):
        return self.system.base64_token

    @property
    def callback_headers(self) -> dict:
        """预检和实际 PULL 共用认证头，仅内置资产额外携带实例租户。"""
        headers = {"Authorization": self.authorization}
        if self.join_data_type == JoinDataType.ASSET:
            headers.update(builtin_asset_callback_headers(self.system_id, self.resource_type_id))
        return headers

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
                                **self.callback_headers,
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

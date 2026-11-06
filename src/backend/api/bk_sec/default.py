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
either express or implied. See the License for the specific language governing permissions and
limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

import abc
import os

from bk_resource import BkApiResource
from client_throttler import Throttler, ThrottlerConfig
from django.conf import settings

from api.domains import BKSEC_API_URL


class BKSec(BkApiResource, abc.ABC):

    module_name = "bk_sec"
    base_url = BKSEC_API_URL
    platform_authorization = True
    rate_limit = settings.BKSEC_API_RATE_LIMIT

    def perform_request(self, validated_request_data):
        return Throttler(
            config=ThrottlerConfig(
                func=super().perform_request,
                key=f"{self.__module__}.{self.__class__.__name__}",
                rate=self.rate_limit,
            )
        )(validated_request_data)

    def add_esb_info_before_request(self, params: dict) -> dict:
        """
        应用身份换成 stag 凭证（与调用插件接口同一对环境变量），用户身份（bk_token/bk_username）保留透传

        配置 BKAPP_BKSEC_PLUGIN_APP_CODE/SECRET 时覆写 bk_app_code/bk_app_secret；
        未配置时回落审计自身应用凭证（super 默认行为）。
        """
        params = super().add_esb_info_before_request(params)
        plugin_app_code = os.getenv("BKAPP_BKSEC_PLUGIN_APP_CODE")
        plugin_app_secret = os.getenv("BKAPP_BKSEC_PLUGIN_APP_SECRET")
        if plugin_app_code and plugin_app_secret:
            params["bk_app_code"] = plugin_app_code
            params["bk_app_secret"] = plugin_app_secret
        return params


class ProjectChoices(BKSec):
    """查询项目列表（应用认证+用户认证）"""

    name = "查询项目列表"
    method = "GET"
    action = "/api/v1/project/choices/"
    platform_authorization = True


class RiskAccessList(BKSec):
    """查询风险类型列表（内嵌 risk_access_fields 字段 schema，用户身份）

    前端下拉走本类：随请求者凭证（bk_token/bk_username）调用，网关按用户数据域出数据。
    后台同步 config 取 token 须平台身份，走 RiskAccessListAsPlatform；两类仅认证形态不同。
    """

    name = "查询风险类型列表"
    method = "GET"
    action = "/api/v1/risk/risk_access/"
    platform_authorization = False


class RiskAccessListAsPlatform(RiskAccessList):
    """查询风险类型列表（平台身份）

    同步插件 Config 取 token 专用：随平台凭证调用，不受操作者数据域影响，
    保证 token 可见性稳定（与谁触发保存/测试无关）。接口/参数复用 RiskAccessList。
    """

    name = "查询风险类型列表（平台身份）"
    platform_authorization = True

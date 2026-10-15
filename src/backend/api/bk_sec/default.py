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
software distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

import abc

from bk_resource import BkApiResource
from client_throttler import Throttler, ThrottlerConfig
from django.conf import settings
from django.utils.translation import gettext_lazy

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


class RiskAccessList(BKSec):
    """查询风险类型列表（内嵌 risk_access_fields 字段 schema）"""

    name = "查询风险类型列表"
    method = "GET"
    action = "/api/v1/risk/risk_access/"


class RiskAccessRetrieve(BKSec):
    """
    查询风险类型详情（取 token / 字段 schema）

    BKSEC 对外只提供 risk_access 列表接口：传 id 时返回该风险类型的单条记录。
    故详情复用列表接口按 id 过滤，并将首条记录以"详情对象"形态返回
    （与列表一致，均已由 IS_STANDARD_FORMAT 解包 data 信封）。
    """

    name = gettext_lazy("查询风险类型详情")
    method = "GET"
    action = "/api/v1/risk/risk_access/"

    def perform_request(self, validated_request_data):
        # project_id 为接口必填的项目维度，未显式传入时按全局配置兜底
        validated_request_data.setdefault("project_id", settings.BKSEC_PROJECT_ID or "")
        result = super().perform_request(validated_request_data) or {}
        results = result.get("results", []) or []
        return results[0] if results else {}

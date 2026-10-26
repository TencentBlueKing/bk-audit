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
import json
import os

from bk_resource import BkApiResource
from client_throttler import Throttler, ThrottlerConfig
from django.conf import settings

from api.domains import BKSEC_API_URL

# Mock 数据文件路径（WeSec API 完整响应，仅 BKAPP_BKSEC_MOCK_ENABLED=True 时使用）
_MOCK_DATA_FILE = os.path.join(os.path.dirname(__file__), "risk_type_list.json")


def _load_mock_data():
    """加载 Mock 数据（WeSec risk_access_list API 完整响应）"""
    with open(_MOCK_DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


class BKSec(BkApiResource, abc.ABC):

    module_name = "bk_sec"
    base_url = BKSEC_API_URL
    platform_authorization = True
    rate_limit = settings.BKSEC_API_RATE_LIMIT

    def perform_request(self, validated_request_data):
        # Mock 模式：直接返回本地数据
        if getattr(settings, "BKSEC_MOCK_ENABLED", False):
            return self._mock_request(validated_request_data)
        return Throttler(
            config=ThrottlerConfig(
                func=super().perform_request,
                key=f"{self.__module__}.{self.__class__.__name__}",
                rate=self.rate_limit,
            )
        )(validated_request_data)

    def _mock_request(self, validated_request_data):
        """Mock 请求处理（子类可覆盖）"""
        raise NotImplementedError


class RiskAccessList(BKSec):
    """查询风险类型列表（内嵌 risk_access_fields 字段 schema）"""

    name = "查询风险类型列表"
    method = "GET"
    action = "/api/v1/risk/risk_access/"

    def _mock_request(self, validated_request_data):
        data = _load_mock_data()
        results = (data.get("data") or {}).get("results", [])

        # is_formal 过滤（默认只返回正式类型，与真实 API 行为一致）
        is_formal = validated_request_data.get("is_formal") or "true"
        if is_formal == "true":
            results = [r for r in results if r.get("is_formal")]
        elif is_formal == "false":
            results = [r for r in results if not r.get("is_formal")]

        # name__icontains 模糊过滤
        name_icontains = validated_request_data.get("name__icontains") or ""
        if name_icontains:
            keyword = name_icontains.lower()
            results = [r for r in results if keyword in (r.get("name") or "").lower()]

        return {"count": len(results), "results": results}

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
import json
import os

from django.conf import settings

BKSAAS_SERVICE_ADDRESSES = os.getenv("BKPAAS_SERVICE_ADDRESSES_BKSAAS")
if BKSAAS_SERVICE_ADDRESSES:
    BKSAAS_SERVICE_ADDRESSES = json.loads(base64.b64decode(BKSAAS_SERVICE_ADDRESSES).decode("utf-8"))
    BKSAAS_SERVICE_ADDRESSES = {
        item["key"]["bk_app_code"]: item["value"]["prod" if settings.RUN_MODE == "PRODUCT" else "stag"].rstrip("/")
        for item in BKSAAS_SERVICE_ADDRESSES
    }
else:
    BKSAAS_SERVICE_ADDRESSES = {}


def get_saas_url(app_code: str) -> str:
    # 环境变量优先，服务发现其次
    env_saas_url = os.getenv(f"BKAPP_{app_code.replace('-', '_').upper()}_SAAS_URL", "").rstrip("/")
    service_url = BKSAAS_SERVICE_ADDRESSES.get(app_code, "")
    return env_saas_url or service_url

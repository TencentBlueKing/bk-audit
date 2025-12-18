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
from collections import defaultdict

from core.utils.tools import is_product

service_addresses = defaultdict(dict)
if os.getenv("BKPAAS_SERVICE_ADDRESSES_BKSAAS"):
    service_addresses_data = json.loads(base64.b64decode(os.getenv("BKPAAS_SERVICE_ADDRESSES_BKSAAS")).decode("utf-8"))
    for item in service_addresses_data:
        app_code = item["key"]["bk_app_code"]
        module_name = item["key"]["module_name"]
        service_addresses[app_code][module_name] = item["value"]["prod" if is_product() else "stag"].rstrip("/")


def get_saas_url(app_code: str, module_name: str = None) -> str:
    # 环境变量优先，服务发现其次
    env_saas_url = os.getenv(
        (
            f"BKAPP"
            f"_{app_code.replace('-', '_').upper()}"
            f"{'_' + module_name.replace('-', '_').upper() if module_name else ''}"
            f"_SAAS_URL"
        ),
        "",
    ).rstrip("/")
    service_url = service_addresses.get(app_code, {})
    return env_saas_url or service_url.get(module_name, "")

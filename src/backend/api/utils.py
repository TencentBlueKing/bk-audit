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

from api.constants import APIGW_URL_FORMAT, ESB_URL_FORMAT, APIProvider
from core.utils.tools import is_product


def get_endpoint(api_name, provider=APIProvider.APIGW, stag="stag", prod="prod", stage=None):
    """
    获取BK-API endpoint
    """
    # 默认环境
    if not stage:
        stage = prod if is_product() else stag

    # api provider
    if provider == APIProvider.ESB:
        return ESB_URL_FORMAT.format(api_name)
    return APIGW_URL_FORMAT.format(api_name=api_name, stage=stage)

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
import uuid

from blueapps.utils.request_provider import get_local_request
from django.conf import settings

from core.exceptions import AppPermissionDenied


def get_app_info():
    """
    获取APP信息，确保请求来自APIGW
    """

    # 开发环境忽略校验
    if settings.RUN_MODE == "DEVELOP":
        return

    try:
        app = get_local_request().app
        if not app.verified:
            raise AppPermissionDenied()
        return app
    except (IndexError, AttributeError):
        raise AppPermissionDenied()


def is_product() -> bool:
    """
    判断是否为生产模式
    """

    return settings.RUN_MODE == "PRODUCT"


def unique_id():
    """生成32个字符的唯一ID ."""
    return uuid.uuid3(uuid.uuid1(), uuid.uuid4().hex).hex

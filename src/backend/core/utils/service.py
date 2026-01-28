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
import os

from django.conf import settings

__all__ = ["get_service_name"]


def get_service_name() -> str:
    """获得服务名称"""
    app_module_name = getattr(settings, "APP_MODULE_NAME", "")
    service_name = (
        os.getenv("BKAPP_OTEL_SERVICE_NAME")
        or getattr(settings, "BKAPP_OTEL_SERVICE_NAME", None)
        or (settings.APP_CODE + f"-{app_module_name}" if app_module_name else "")
    )
    return service_name

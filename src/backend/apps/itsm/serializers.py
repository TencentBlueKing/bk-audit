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

from django.utils.translation import gettext_lazy
from rest_framework import serializers

from services.web.risk.constants import ItsmVersion


def default_itsm_version() -> str:
    """
    默认 ITSM 版本：未显式传 version 时按部署级开关决定。

    用 callable 而非字面量，避免模块加载时固化默认值，保证与新建单据读取同一配置。
    """

    from apps.itsm.utils import is_itsm_v4_enabled

    return ItsmVersion.V4.value if is_itsm_v4_enabled() else ItsmVersion.V3.value


class GetServicesRespSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()
    url = serializers.CharField(required=False, allow_null=True, allow_blank=True)


class GetServiceDetailReqSerializer(serializers.Serializer):
    # V4 下为流程标识 workflow_key（字符串），不再是 V3 的数值型服务 ID
    id = serializers.CharField(label=gettext_lazy("流程标识"))
    version = serializers.CharField(label=gettext_lazy("itsm 版本"), default=default_itsm_version)


class GetServicesReqsSerializer(serializers.Serializer):
    # 选填：用于覆盖后端默认配置（ITSM_V4_SYSTEM_ID），正常情况下前端无需传入
    system_id = serializers.CharField(label=gettext_lazy("系统标识"), required=False)
    version = serializers.CharField(label=gettext_lazy("itsm 版本"), default=default_itsm_version)

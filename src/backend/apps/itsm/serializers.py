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


class GetServicesRespSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()
    url = serializers.CharField(required=False, allow_null=True, allow_blank=True)


class GetServiceDetailReqSerializer(serializers.Serializer):
    # V4 下为流程标识 workflow_key（字符串），不再是 V3 的数值型服务 ID
    id = serializers.CharField(label=gettext_lazy("流程标识"))
    # 选填：用于回查流程名称，缺失时名称降级为流程标识
    system_id = serializers.CharField(label=gettext_lazy("系统标识"), required=False)


class GetServicesReqsSerializer(serializers.Serializer):
    system_id = serializers.CharField()

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

from services.web.analyze.models import Control, ControlVersion


class ControlTypeResponseSerializer(serializers.Serializer):
    """
    Control Type
    """

    id = serializers.CharField(label=gettext_lazy("ID"))
    name = serializers.CharField(label=gettext_lazy("Name"))


class ControlVersionListInfoSerializer(serializers.ModelSerializer):
    """
    Control Version List
    """

    class Meta:
        model = ControlVersion
        fields = ["control_id", "control_version"]


class ControlResourceRequestSerializer(serializers.Serializer):
    """
    Load Control
    """

    control_type_id = serializers.CharField(label=gettext_lazy("Control Type ID"), required=False)


class ControlResourceResponseSerializer(serializers.ModelSerializer):
    """
    Load Control
    """

    versions = ControlVersionListInfoSerializer(label=gettext_lazy("Control Versions"), many=True)

    class Meta:
        model = Control
        fields = ["control_type_id", "control_id", "control_name", "versions"]


class ControlVersionDetailRequestSerializer(serializers.Serializer):
    """
    Control Version Detail
    """

    control_id = serializers.CharField(label=gettext_lazy("Control ID"))
    control_version = serializers.CharField(label=gettext_lazy("Control Version"), required=False, default=str)


class ControlVersionDetailResponseSerializer(serializers.ModelSerializer):
    """
    Control Version Detail
    """

    class Meta:
        model = ControlVersion
        fields = "__all__"

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

from rest_framework import serializers

from core.serializers import ExtraDataSerializerMixin
from services.web.vision.models import Scenario, VisionPanel


class VisionPanelInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = VisionPanel
        fields = ["id", "name", "scenario", "scope_type", "scene_id", "status", "category", "description"]


class VisionPanelInfoQuerySerializer(serializers.Serializer):
    scenario = serializers.ChoiceField(choices=Scenario.choices, default=Scenario.DEFAULT)
    scope_type = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        label="归属级别",
        help_text="platform=平台级, scene=场景级, 空=全部",
    )
    scene_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        default=None,
        label="所属场景ID",
        help_text="仅 scope_type=scene 时有效",
    )


class QueryMetaReqSerializer(ExtraDataSerializerMixin):
    share_uid = serializers.CharField()
    type = serializers.CharField()


class QueryDataReqSerializer(serializers.Serializer):
    share_uid = serializers.CharField()
    panel_uid = serializers.CharField()
    queries = serializers.ListField(child=serializers.JSONField())
    option = serializers.JSONField()


class QueryShareDetailSerializer(ExtraDataSerializerMixin):
    share_uid = serializers.CharField()

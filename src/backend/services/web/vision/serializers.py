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
from services.web.scene.constants import PanelStatus
from services.web.scene.serializers import (
    FlexibleListField,
    ResourceBindingInputSerializer,
)
from services.web.vision.models import Scenario, VisionPanel


class VisionPanelInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = VisionPanel
        fields = ["id", "name", "scenario", "status", "category", "description"]


class VisionPanelInfoQuerySerializer(serializers.Serializer):
    scenario = serializers.ChoiceField(choices=Scenario.choices, default=Scenario.DEFAULT)
    binding_type = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        label="绑定类型",
        help_text="platform_binding=平台级, scene_binding=场景级, 空=全部",
    )
    scene_id = FlexibleListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True,
        default=list,
        label="所属场景ID列表",
        help_text="按场景过滤，支持单个值、多个同名参数、数组或逗号分隔字符串",
    )
    system_id = FlexibleListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
        default=list,
        label="系统ID列表",
        help_text="按接入系统过滤，支持单个值、多个同名参数、数组或逗号分隔字符串",
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


class CreatePlatformPanelRequestSerializer(serializers.Serializer):
    id = serializers.CharField(required=False, allow_blank=True)
    name = serializers.CharField(required=True, max_length=255)
    category = serializers.CharField(required=False, allow_blank=True, default="")
    description = serializers.CharField(required=False, allow_blank=True, default="")
    status = serializers.ChoiceField(choices=PanelStatus.choices, required=False, default=PanelStatus.UNPUBLISHED)
    visibility = ResourceBindingInputSerializer(required=False)


class UpdatePlatformPanelRequestSerializer(serializers.Serializer):
    panel_id = serializers.CharField(required=True)
    name = serializers.CharField(required=False, max_length=255)
    category = serializers.CharField(required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
    status = serializers.ChoiceField(choices=PanelStatus.choices, required=False)
    visibility = ResourceBindingInputSerializer(required=False)


class PlatformPanelOperateRequestSerializer(serializers.Serializer):
    panel_id = serializers.CharField(required=True)


class CreateScenePanelRequestSerializer(serializers.Serializer):
    scene_id = serializers.IntegerField(required=True)
    id = serializers.CharField(required=False, allow_blank=True)
    name = serializers.CharField(required=True, max_length=255)
    category = serializers.CharField(required=False, allow_blank=True, default="")
    description = serializers.CharField(required=False, allow_blank=True, default="")


class UpdateScenePanelRequestSerializer(serializers.Serializer):
    scene_id = serializers.IntegerField(required=True)
    panel_id = serializers.CharField(required=True)
    name = serializers.CharField(required=False, max_length=255)
    category = serializers.CharField(required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)


class DeleteScenePanelRequestSerializer(serializers.Serializer):
    scene_id = serializers.IntegerField(required=True)
    panel_id = serializers.CharField(required=True)

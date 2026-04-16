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
from services.web.common.constants import ScopeQueryField, ScopeType
from services.web.common.serializers import ScopeQuerySerializer
from services.web.scene.constants import BindingType, PanelStatus
from services.web.scene.serializers import ResourceBindingInputSerializer
from services.web.vision.models import Scenario, VisionPanel


class VisionPanelInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = VisionPanel
        fields = ["id", "name", "scenario", "status", "category", "description"]


class VisionPanelInfoQuerySerializer(ScopeQuerySerializer):
    scenario = serializers.ChoiceField(choices=Scenario.choices, default=Scenario.DEFAULT)
    binding_type = serializers.ChoiceField(
        choices=BindingType.choices,
        required=False,
        allow_null=True,
        default=None,
        label="绑定类型",
        help_text="可选：platform_binding=平台级，scene_binding=场景级；不传时按接口默认行为",
    )

    def validate(self, attrs: dict) -> dict:
        attrs = super().validate(attrs)
        scope_type = attrs.get(ScopeQueryField.SCOPE_TYPE)
        binding_type = attrs.get("binding_type")

        if scope_type in {ScopeType.CROSS_SYSTEM, ScopeType.SYSTEM} and binding_type == BindingType.SCENE_BINDING:
            raise serializers.ValidationError(
                {"binding_type": "系统视角 scope 不支持 binding_type=scene_binding，请使用 platform_binding 或不传。"}
            )

        return attrs


class OptionalVisionPanelInfoQuerySerializer(VisionPanelInfoQuerySerializer):
    """报表列表可选 scope 参数。"""

    scope_type = serializers.ChoiceField(choices=ScopeType.choices, required=False, allow_null=True)
    scope_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate(self, attrs: dict) -> dict:
        scope_type = attrs.get(ScopeQueryField.SCOPE_TYPE)
        scope_id = attrs.get(ScopeQueryField.SCOPE_ID)

        if not scope_type:
            if scope_id:
                raise serializers.ValidationError({ScopeQueryField.SCOPE_TYPE: "传入 scope_id 时必须同时传入 scope_type。"})
            attrs.pop(ScopeQueryField.SCOPE_TYPE, None)
            attrs.pop(ScopeQueryField.SCOPE_ID, None)
            return attrs

        return super().validate(attrs)


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

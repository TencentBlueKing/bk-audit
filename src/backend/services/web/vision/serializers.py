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
from services.web.vision.models import ReportGroup, Scenario, VisionPanel


class VisionPanelInfoSerializer(serializers.ModelSerializer):
    group_id = serializers.IntegerField(source="group.id", read_only=True, default=None)
    group_name = serializers.CharField(source="group.name", read_only=True, default="")
    group_priority_index = serializers.IntegerField(source="group.priority_index", read_only=True, default=0)
    is_favorite = serializers.BooleanField(read_only=True, default=False)
    favorite_at = serializers.DateTimeField(read_only=True, default=None, allow_null=True)

    class Meta:
        model = VisionPanel
        fields = [
            "id",
            "name",
            "scenario",
            "description",
            "is_enabled",
            "priority_index",
            "group_id",
            "group_name",
            "group_priority_index",
            "is_favorite",
            "favorite_at",
        ]


class VisionPanelInfoQuerySerializer(serializers.Serializer):
    scenario = serializers.ChoiceField(choices=Scenario.choices, default=Scenario.DEFAULT)


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


class ReportGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportGroup
        fields = ["id", "name", "priority_index"]


class ManagePanelSerializer(serializers.ModelSerializer):
    group_id = serializers.IntegerField(source="group.id", read_only=True, default=None)
    group_name = serializers.CharField(source="group.name", read_only=True, default="")
    group_priority_index = serializers.IntegerField(source="group.priority_index", read_only=True, default=0)

    class Meta:
        model = VisionPanel
        fields = [
            "id",
            "name",
            "description",
            "vision_id",
            "is_enabled",
            "priority_index",
            "group_id",
            "group_name",
            "group_priority_index",
            "updated_by",
            "updated_at",
        ]


class ListManagePanelsRequestSerializer(serializers.Serializer):
    keyword = serializers.CharField(required=False, allow_blank=True, default="")
    is_enabled = serializers.BooleanField(required=False, default=None, allow_null=True)


class CreatePanelRequestSerializer(serializers.Serializer):
    vision_id = serializers.CharField(label="BKVision 分享 UID")
    name = serializers.CharField(label="报表名称")
    group_name = serializers.CharField(label="分组名称")
    description = serializers.CharField(required=False, allow_blank=True, default="", label="描述")
    is_enabled = serializers.BooleanField(required=False, default=True, label="是否启用")


class UpdatePanelRequestSerializer(serializers.Serializer):
    id = serializers.CharField(label="Panel ID")
    name = serializers.CharField(required=False, label="报表名称")
    description = serializers.CharField(required=False, allow_blank=True, label="描述")
    group_name = serializers.CharField(required=False, label="分组名称")
    vision_id = serializers.CharField(required=False, label="BKVision 分享 UID")
    is_enabled = serializers.BooleanField(required=False, label="是否启用")


class PanelOrderItemSerializer(serializers.Serializer):
    id = serializers.CharField(label="Panel ID", help_text="需要调整排序或分组的 Panel ID")
    group_id = serializers.IntegerField(label="目标分组 ID", help_text="Panel 移动到的目标分组，跨组拖拽时传新分组 ID")
    priority_index = serializers.IntegerField(label="排序权重", help_text="数值越大排序越靠前，前端按拖拽顺序从大到小赋值")


class UpdatePanelOrderRequestSerializer(serializers.Serializer):
    panels = PanelOrderItemSerializer(
        many=True,
        help_text="全量传入当前分组内所有 Panel，priority_index 按显示顺序从大到小赋值",
    )


class GroupOrderItemSerializer(serializers.Serializer):
    id = serializers.IntegerField(label="分组 ID")
    priority_index = serializers.IntegerField(label="排序权重")


class UpdateGroupOrderRequestSerializer(serializers.Serializer):
    groups = GroupOrderItemSerializer(many=True)


class UpdatePanelPreferenceRequestSerializer(serializers.Serializer):
    config = serializers.JSONField(label="偏好配置")


class PanelPreferenceResponseSerializer(serializers.Serializer):
    config = serializers.JSONField()


class ToggleFavoriteRequestSerializer(serializers.Serializer):
    panel_id = serializers.CharField(label="Panel ID")
    is_favorite = serializers.BooleanField(label="收藏状态", help_text="True=收藏, False=取消收藏")


class ToggleFavoriteResponseSerializer(serializers.Serializer):
    is_favorite = serializers.BooleanField()
    favorite_at = serializers.DateTimeField(allow_null=True)

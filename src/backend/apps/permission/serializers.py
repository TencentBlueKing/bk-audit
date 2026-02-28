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

from apps.meta.models import System, Tag
from apps.permission.handlers.actions import ActionEnum


class CheckPermissionRequestSerializer(serializers.Serializer):
    action_ids = serializers.CharField(label=gettext_lazy("操作ID"), help_text=ActionEnum.choices())
    resources = serializers.CharField(label=gettext_lazy("资源ID列表"), required=False, allow_null=True, allow_blank=True)

    def validate_action_ids(self, value: str):
        return [action_id for action_id in value.split(",") if action_id]

    def validate_resources(self, value: str):
        return [resource for resource in value.split(",") if resource]


class CheckAnyPermissionRequestSerializer(serializers.Serializer):
    """检查当前用户对某动作是否有任意权限（不关心具体资源实例）"""

    action_ids = serializers.CharField(label=gettext_lazy("操作ID"), help_text=ActionEnum.choices())

    def validate_action_ids(self, value: str):
        return [action_id for action_id in value.split(",") if action_id]


class GetApplyDataRequestSerializer(CheckPermissionRequestSerializer):
    ...


class BatchIsAllowRequestSerializer(serializers.Serializer):
    action_ids = serializers.ListField(label=gettext_lazy("操作ID"), child=serializers.CharField())
    resources = serializers.ListField(
        label=gettext_lazy("资源ID列表"), child=serializers.CharField(), required=False, allow_null=True
    )


class SystemListSerializer(serializers.ModelSerializer):
    class Meta:
        model = System
        exclude = ["provider_config", "auth_token"]


class TagListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = "__all__"


class TagProviderSerializer(serializers.ModelSerializer):
    """用于 Provider 的标签快照/Schema 序列化器（白名单字段）。"""

    tag_id = serializers.IntegerField(label=gettext_lazy("Tag ID"))

    class Meta:
        model = Tag
        fields = ["tag_id", "tag_name"]

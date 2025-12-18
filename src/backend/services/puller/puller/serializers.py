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

from apps.meta.models import Action, ResourceType


class FetchInstanceSerializer(serializers.Serializer):
    def to_representation(self, instance):
        data = super().to_representation(instance)
        try:
            data["created_at"] = int(instance.created_at.timestamp() * 1000)
            data["updated_at"] = int(instance.updated_at.timestamp() * 1000)
        except AttributeError:
            pass
        return data


class FetchResourceTypeSerializer(FetchInstanceSerializer, serializers.ModelSerializer):
    class Meta:
        model = ResourceType
        exclude = ["provider_config", "path"]


class FetchActionSerializer(FetchInstanceSerializer, serializers.ModelSerializer):
    class Meta:
        model = Action
        fields = "__all__"


class ResourceViewFilterSerializer(serializers.Serializer):
    start_time = serializers.IntegerField(required=False)
    end_time = serializers.IntegerField(required=False)


class ResourceViewPageSerializer(serializers.Serializer):
    offset = serializers.IntegerField(required=False)
    limit = serializers.IntegerField(required=False)


class ResourceViewRequestSerializer(serializers.Serializer):
    type = serializers.CharField()
    method = serializers.CharField()
    filter = ResourceViewFilterSerializer(required=False)
    page = ResourceViewPageSerializer(required=False)


class ResourceViewResponseItemSerializer(serializers.Serializer):
    id = serializers.CharField()
    display_name = serializers.CharField()
    creator = serializers.CharField()
    created_at = serializers.CharField()
    updator = serializers.CharField()
    updated_at = serializers.CharField()
    data = serializers.JSONField()


class ResourceViewResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    results = ResourceViewResponseItemSerializer(many=True)

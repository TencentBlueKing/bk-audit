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

import abc
import datetime
from typing import List

from django.db.models import QuerySet
from rest_framework import serializers

from apps.meta.models import Action, ResourceType
from services.puller.puller.constants import FIELD_TYPE_MAP
from services.puller.puller.serializers import (
    FetchActionSerializer,
    FetchResourceTypeSerializer,
)


class FetchInstanceMixin:
    created_by_field = "created_by"
    created_at_field = "created_at"
    updated_by_field = "updated_by"
    updated_at_field = "updated_at"

    @abc.abstractmethod
    def get_queryset(self) -> QuerySet:
        ...

    @property
    @abc.abstractmethod
    def serializer(self) -> serializers.BaseSerializer:
        ...

    @abc.abstractmethod
    def get_pk(self, instance: dict):
        return ...

    @abc.abstractmethod
    def get_display_name(self, instance: dict):
        ...

    @classmethod
    def get_schema(cls):
        return {
            field_name: {"type": FIELD_TYPE_MAP.get(field.__class__), "description": field.label}
            for field_name, field in cls.serializer().fields.fields.items()
        }


class BaseFetchHandler(FetchInstanceMixin, abc.ABC):
    def __init__(self, start_time: int = None, end_time: int = None, page: dict = None):
        self.start_time = datetime.datetime.fromtimestamp(start_time / 1000) if start_time else None
        self.end_time = datetime.datetime.fromtimestamp(end_time / 1000) if end_time else None
        page = page or dict()
        self.offset = page.get("offset")
        self.limit = page.get("limit")

    def fetch_instance_list(self):
        if self.start_time and self.end_time:
            queryset = self.get_queryset().filter(updated_at__gte=self.start_time, updated_at__lte=self.end_time)
        elif self.start_time:
            queryset = self.get_queryset().filter(updated_at__gte=self.start_time)
        else:
            queryset = self.get_queryset()
        count = queryset.count()
        page = self.pagination(queryset)
        data = self.serialize(page)
        return {"count": count, "results": self.parse_data(data)}

    def pagination(self, queryset: QuerySet) -> QuerySet:
        if self.offset is not None and self.limit is not None:
            return queryset[self.offset : self.offset + self.limit]
        return queryset

    def serialize(self, queryset: QuerySet) -> list:
        serializer = self.serializer(queryset, many=True)
        return serializer.data

    def parse_data(self, data: List[dict]) -> list:
        return [
            {
                "id": self.get_pk(item),
                "display_name": self.get_display_name(item),
                "creator": item[self.created_by_field],
                "created_at": item[self.created_at_field],
                "updater": item[self.updated_by_field],
                "updated_at": item[self.updated_at_field],
                "data": item,
            }
            for item in data
        ]


class ResourceTypeFetchHandler(BaseFetchHandler):
    serializer = FetchResourceTypeSerializer

    def get_pk(self, instance: dict):
        return instance["resource_type_id"]

    def get_display_name(self, instance: dict):
        return instance["name"]

    def get_queryset(self) -> QuerySet:
        return ResourceType.objects.all()


class ActionFetchHandler(BaseFetchHandler):
    serializer = FetchActionSerializer

    def get_pk(self, instance: dict):
        return instance["action_id"]

    def get_display_name(self, instance: dict):
        return instance["name"]

    def get_queryset(self) -> QuerySet:
        return Action.objects.all()

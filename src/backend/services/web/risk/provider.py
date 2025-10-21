# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
Copyright (C) 2023 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at https://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

import datetime
from typing import List, Optional, Tuple

from django.db import models
from django.db.models import QuerySet
from django.utils import timezone
from iam import PathEqDjangoQuerySetConverter
from iam.resource.provider import ListResult, SchemaResult
from iam.resource.utils import Page

from apps.permission.handlers.resource_types import ResourceEnum
from apps.permission.provider.base import IAMResourceProvider
from core.serializers import get_serializer_fields
from services.web.risk.converter.queryset import RiskPathEqDjangoQuerySetConverter
from services.web.risk.models import Risk, TicketPermission
from services.web.risk.serializers import (
    RiskProviderSerializer,
    TicketPermissionProviderSerializer,
)


class RiskResourceProvider(IAMResourceProvider):
    def list_attr_value_choices(self, attr: str, page: Page) -> List:
        return []

    def filter_list_instance_results(self, parent_id: Optional[str], resource_type: Optional[str], page: Page) -> Tuple:
        """
        根据过滤条件查询资源实例
        """
        """查询风险类型 ."""
        if parent_id:
            if resource_type == ResourceEnum.STRATEGY.id:
                strategy_id = int(parent_id)
                queryset: QuerySet[Risk] = Risk.objects.filter(strategy_id=strategy_id)
            else:
                queryset: QuerySet[Risk] = Risk.objects.none()
        else:
            queryset: QuerySet[Risk] = Risk.objects.all()
        results = [
            {"id": str(instance.risk_id), "display_name": instance.risk_id}
            for instance in queryset[page.slice_from : page.slice_to]
        ]
        count = queryset.count()
        return results, count

    def filter_search_instance_results(
        self, parent_id: Optional[str], resource_type: Optional[str], keyword: str, page: Page
    ) -> Tuple[list, int]:
        """根据风险类型名称查询 ."""
        if parent_id:
            if resource_type == ResourceEnum.STRATEGY.id:
                strategy_id = int(parent_id)
                queryset: QuerySet[Risk] = Risk.objects.filter(strategy_id=strategy_id)
            else:
                queryset: QuerySet[Risk] = Risk.objects.none()
        else:
            queryset: QuerySet[Risk] = Risk.objects.all()

        queryset = queryset.filter(risk_id__contains=keyword)
        results = [
            {"id": str(instance.risk_id), "display_name": instance.risk_id}
            for instance in queryset[page.slice_from : page.slice_to]
        ]
        count = queryset.count()
        return results, count

    def filter_fetch_instance_results(self, ids: List[str]) -> Tuple:
        """
        批量查询资源实例
        """

        queryset = Risk.objects.filter(risk_id__in=ids)

        results = [{"id": item.risk_id, "display_name": item.risk_id} for item in queryset]
        return results, queryset.count()

    def list_instance_by_policy(self, filters, page, **options):
        expression = filters.expression
        if not expression:
            return ListResult(results=[], count=0)

        converter = RiskPathEqDjangoQuerySetConverter()
        filters = converter.convert(expression)
        queryset: QuerySet[Risk] = Risk.objects.filter(filters)
        results = [
            {"id": item.risk_id, "display_name": item.risk_id} for item in queryset[page.slice_from : page.slice_to]
        ]

        return ListResult(results=results, count=queryset.count())

    def fetch_instance_list(self, filter, page, **options):
        # 注意：filter.start_time/end_time 为毫秒时间戳，这里保持毫秒精度，避免边界被截断
        start_time = datetime.datetime.fromtimestamp(float(filter.start_time) / 1000)
        end_time = datetime.datetime.fromtimestamp(float(filter.end_time) / 1000)
        queryset = Risk.objects.filter(event_time__gt=start_time, event_time__lte=end_time)
        results = [
            {
                "id": item.risk_id,
                "display_name": item.risk_id,
                "creator": None,
                "created_at": None,
                "updater": None,
                "updated_at": None,
                "data": RiskProviderSerializer(instance=item).data,
            }
            for item in queryset[page.slice_from : page.slice_to]
        ]
        return ListResult(results=results, count=queryset.count())

    def fetch_resource_type_schema(self, **options):
        data = get_serializer_fields(RiskProviderSerializer)
        return SchemaResult(
            properties={
                item["name"]: {
                    "type": item["type"].lower(),
                    "description_en": item["name"],
                    "description": item["description"],
                }
                for item in data
            }
        )


class TicketPermissionResourceProvider(IAMResourceProvider):
    resource_type = ResourceEnum.TICKET_PERMISSION.id
    """TicketPermission 资源提供者（用于反向拉取快照）"""

    def list_attr_value_choices(self, attr: str, page: Page) -> List:
        return []

    def filter_list_instance_results(self, parent_id: Optional[str], resource_type: Optional[str], page: Page) -> Tuple:
        queryset = TicketPermission.objects.all()
        if parent_id and resource_type == ResourceEnum.RISK.id:
            queryset = queryset.filter(risk_id=str(parent_id))
        page_qs = queryset[page.slice_from : page.slice_to]
        results = [{"id": str(item.pk), "display_name": str(item.pk)} for item in page_qs]
        return results, queryset.count()

    def filter_fetch_instance_results(self, ids: List[str]) -> Tuple:
        int_ids = []
        for i in ids:
            try:
                int_ids.append(int(i))
            except (TypeError, ValueError):
                continue
        queryset = TicketPermission.objects.filter(pk__in=int_ids)
        results = [{"id": str(item.pk), "display_name": str(item.pk)} for item in queryset]
        return results, queryset.count()

    def filter_search_instance_results(
        self, parent_id: Optional[str], resource_type: Optional[str], keyword: str, page: Page
    ) -> Tuple[List[dict], int]:
        queryset = TicketPermission.objects.all()
        if parent_id and resource_type == ResourceEnum.RISK.id:
            queryset = queryset.filter(risk_id=str(parent_id))
        if keyword:
            queryset = queryset.filter(
                models.Q(risk_id__icontains=keyword)
                | models.Q(action__icontains=keyword)
                | models.Q(user__icontains=keyword)
            )
        page_qs = queryset[page.slice_from : page.slice_to]
        results = [{"id": str(item.pk), "display_name": str(item.pk)} for item in page_qs]
        return results, queryset.count()

    def list_instance_by_policy(self, filters, page, **options):
        expression = filters.expression
        if not expression:
            return ListResult(results=[], count=0)

        key_mapping = {f"{self.resource_type}.id": "id"}
        converter = PathEqDjangoQuerySetConverter(key_mapping)
        django_filters = converter.convert(expression)
        queryset = TicketPermission.objects.filter(django_filters)
        results = [
            {"id": str(item.pk), "display_name": str(item.pk)} for item in queryset[page.slice_from : page.slice_to]
        ]
        return ListResult(results=results, count=queryset.count())

    def fetch_instance_list(self, filter, page, **options):
        # 将毫秒级时间戳转换为 UTC aware datetime，避免边界/时区问题
        start_ms = float(filter.start_time)
        end_ms = float(filter.end_time)
        start_time = datetime.datetime.fromtimestamp(start_ms / 1000.0, tz=timezone.utc)
        end_time = datetime.datetime.fromtimestamp(end_ms / 1000.0, tz=timezone.utc)
        # 上界扩展 1ms，确保包含毫秒边界
        end_time_inclusive = end_time + datetime.timedelta(milliseconds=1)
        queryset = TicketPermission.objects.filter(authorized_at__gt=start_time, authorized_at__lte=end_time_inclusive)

        page_queryset = queryset[page.slice_from : page.slice_to]
        # 顶层时间戳要求为毫秒级
        results = [
            {
                "id": str(item.pk),
                "display_name": str(item.pk),
                "creator": None,
                "created_at": int(item.authorized_at.timestamp() * 1000) if item.authorized_at else None,
                "updater": None,
                "updated_at": int(item.authorized_at.timestamp() * 1000) if item.authorized_at else None,
                "data": TicketPermissionProviderSerializer(item).data,
            }
            for item in page_queryset
        ]
        return ListResult(results=results, count=queryset.count())

    def fetch_resource_type_schema(self, **options):
        data = get_serializer_fields(TicketPermissionProviderSerializer)
        return SchemaResult(
            properties={
                item["name"]: {
                    "type": item["type"].lower(),
                    "description_en": item["name"],
                    "description": item["description"],
                }
                for item in data
            }
        )

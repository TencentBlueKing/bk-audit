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
from iam.resource.provider import ListResult
from iam.resource.utils import Page

from apps.permission.handlers.resource_types import ResourceEnum
from apps.permission.provider.base import IAMResourceProvider
from services.web.risk.converter.queryset import RiskPathEqDjangoQuerySetConverter
from services.web.risk.models import ManualEvent, Risk, TicketNode, TicketPermission
from services.web.risk.serializers import (
    ManualEventProviderSerializer,
    RiskProviderSerializer,
    TicketNodeProviderSerializer,
    TicketPermissionProviderSerializer,
)


class RiskResourceProvider(IAMResourceProvider):
    resource_provider_serializer = RiskProviderSerializer
    resource_type_index_fields = [
        "risk_id",
        "raw_event_id",
        "strategy_id",
        "event_time",
        "event_end_time",
        "event_source",
        "last_operate_time",
        "title",
        "event_time_timestamp",
        "event_end_time_timestamp",
        "last_operate_time_timestamp",
    ]

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
        base_qs = Risk.objects.filter(updated_at__gt=start_time, updated_at__lte=end_time)

        # 延迟关联优化：先在 updated_at 索引上做覆盖扫描定位主键，避免深分页时大量回表
        pk_list = list(
            base_qs.order_by("updated_at").values_list("risk_id", flat=True)[page.slice_from : page.slice_to]
        )
        # 用主键精确回表，只回表 page_size 条记录
        queryset = Risk.objects.filter(risk_id__in=pk_list).order_by("updated_at")

        results = [
            {
                "id": item.risk_id,
                "display_name": item.risk_id,
                "creator": None,
                "created_at": None,
                "updater": None,
                "updated_at": None,
                "data": self.resource_provider_serializer(instance=item).data,
            }
            for item in queryset
        ]
        return ListResult(results=results, count=base_qs.count())


class ManualEventResourceProvider(IAMResourceProvider):
    resource_provider_serializer = ManualEventProviderSerializer
    resource_type_index_fields = [
        "manual_event_id",
        "raw_event_id",
        "strategy_id",
        "event_time",
        "event_source",
        "last_operate_time",
        "title",
        "event_time_timestamp",
        "last_operate_time_timestamp",
    ]

    def list_attr_value_choices(self, attr: str, page: Page) -> List:
        return []

    @staticmethod
    def _display_name(instance: ManualEvent) -> str:
        return instance.raw_event_id or str(instance.manual_event_id)

    def _filter_queryset(self, parent_id: Optional[str], resource_type: Optional[str]) -> QuerySet[ManualEvent]:
        if parent_id and resource_type == ResourceEnum.STRATEGY.id:
            return ManualEvent.objects.filter(strategy_id=int(parent_id))
        if parent_id:
            return ManualEvent.objects.none()
        return ManualEvent.objects.all()

    def filter_list_instance_results(self, parent_id: Optional[str], resource_type: Optional[str], page: Page) -> Tuple:
        queryset = self._filter_queryset(parent_id, resource_type)
        page_qs = queryset[page.slice_from : page.slice_to]
        results = [{"id": str(item.manual_event_id), "display_name": self._display_name(item)} for item in page_qs]
        return results, queryset.count()

    def filter_search_instance_results(
        self, parent_id: Optional[str], resource_type: Optional[str], keyword: str, page: Page
    ) -> Tuple[list, int]:
        queryset = self._filter_queryset(parent_id, resource_type)
        queryset = queryset.filter(raw_event_id__icontains=keyword)
        page_qs = queryset[page.slice_from : page.slice_to]
        results = [{"id": str(item.manual_event_id), "display_name": self._display_name(item)} for item in page_qs]
        return results, queryset.count()

    def filter_fetch_instance_results(self, ids: List[str]) -> Tuple:
        queryset = ManualEvent.objects.filter(manual_event_id__in=ids)
        results = [{"id": str(item.manual_event_id), "display_name": self._display_name(item)} for item in queryset]
        return results, queryset.count()

    def list_instance_by_policy(self, filters, page, **options):
        expression = filters.expression
        if not expression:
            return ListResult(results=[], count=0)

        converter = RiskPathEqDjangoQuerySetConverter()
        django_filters = converter.convert(expression)
        queryset = ManualEvent.objects.filter(django_filters)
        page_qs = queryset[page.slice_from : page.slice_to]
        results = [{"id": str(item.manual_event_id), "display_name": self._display_name(item)} for item in page_qs]
        return ListResult(results=results, count=queryset.count())

    def fetch_instance_list(self, filter, page, **options):
        start_time = datetime.datetime.fromtimestamp(float(filter.start_time) / 1000)
        end_time = datetime.datetime.fromtimestamp(float(filter.end_time) / 1000)
        base_qs = ManualEvent.objects.filter(updated_at__gt=start_time, updated_at__lte=end_time)

        # 延迟关联优化：先在 updated_at 索引上做覆盖扫描定位主键，避免深分页时大量回表
        pk_list = list(
            base_qs.order_by("updated_at").values_list("manual_event_id", flat=True)[page.slice_from : page.slice_to]
        )
        # 用主键精确回表，只回表 page_size 条记录
        queryset = ManualEvent.objects.filter(manual_event_id__in=pk_list).order_by("updated_at")

        results = [
            {
                "id": str(item.manual_event_id),
                "display_name": self._display_name(item),
                "creator": None,
                "created_at": None,
                "updater": None,
                "updated_at": None,
                "data": self.resource_provider_serializer(instance=item).data,
            }
            for item in queryset
        ]
        return ListResult(results=results, count=base_qs.count())


class TicketPermissionResourceProvider(IAMResourceProvider):
    resource_type = ResourceEnum.TICKET_PERMISSION.id
    """TicketPermission 资源提供者（用于反向拉取快照）"""
    resource_provider_serializer = TicketPermissionProviderSerializer
    resource_type_index_fields = ["risk_id", "action", "user", "authorized_at", "user_type", "authorized_at_timestamp"]

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
                "data": self.resource_provider_serializer(item).data,
            }
            for item in page_queryset
        ]
        return ListResult(results=results, count=queryset.count())


class TicketNodeResourceProvider(IAMResourceProvider):
    resource_type = ResourceEnum.TICKET_NODE.id
    resource_provider_serializer = TicketNodeProviderSerializer
    resource_type_index_fields = ["risk_id", "operator", "action", "timestamp"]

    def list_attr_value_choices(self, attr: str, page: Page) -> List:
        return []

    def filter_list_instance_results(self, parent_id: Optional[str], resource_type: Optional[str], page: Page) -> Tuple:
        queryset = TicketNode.objects.all()
        if parent_id and resource_type == ResourceEnum.RISK.id:
            queryset = queryset.filter(risk_id=str(parent_id))
        page_qs = queryset[page.slice_from : page.slice_to]
        results = [{"id": str(item.pk), "display_name": str(item.pk)} for item in page_qs]
        return results, queryset.count()

    def filter_fetch_instance_results(self, ids: List[str]) -> Tuple:
        queryset = TicketNode.objects.filter(pk__in=ids)
        results = [{"id": str(item.pk), "display_name": str(item.pk)} for item in queryset]
        return results, queryset.count()

    def filter_search_instance_results(
        self, parent_id: Optional[str], resource_type: Optional[str], keyword: str, page: Page
    ) -> Tuple[List[dict], int]:
        queryset = TicketNode.objects.all()
        if parent_id and resource_type == ResourceEnum.RISK.id:
            queryset = queryset.filter(risk_id=str(parent_id))
        if keyword:
            queryset = queryset.filter(models.Q(risk_id__icontains=keyword) | models.Q(operator__icontains=keyword))
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
        queryset = TicketNode.objects.filter(django_filters)
        results = [
            {"id": str(item.pk), "display_name": str(item.pk)} for item in queryset[page.slice_from : page.slice_to]
        ]
        return ListResult(results=results, count=queryset.count())

    def fetch_instance_list(self, filter, page, **options):
        start_ts = float(filter.start_time) / 1000.0
        end_ts = float(filter.end_time) / 1000.0
        base_qs = TicketNode.objects.filter(timestamp__gt=start_ts, timestamp__lte=end_ts)

        pk_list = list(base_qs.order_by("timestamp").values_list("id", flat=True)[page.slice_from : page.slice_to])
        queryset = TicketNode.objects.filter(pk__in=pk_list).order_by("timestamp")

        results = [
            {
                "id": str(item.pk),
                "display_name": str(item.pk),
                "creator": None,
                "created_at": int(item.timestamp * 1000),
                "updater": None,
                "updated_at": int(item.timestamp * 1000),
                "data": self.resource_provider_serializer(item).data,
            }
            for item in queryset
        ]
        return ListResult(results=results, count=base_qs.count())

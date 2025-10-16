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

from bk_resource.tools import get_serializer_fields
from django.db.models import QuerySet
from iam.resource.provider import ListResult, SchemaResult
from iam.resource.utils import Page

from apps.permission.handlers.resource_types import ResourceEnum
from apps.permission.provider.base import IAMResourceProvider
from services.web.risk.converter.queryset import RiskPathEqDjangoQuerySetConverter
from services.web.risk.models import Risk
from services.web.risk.serializers import RiskProviderSerializer


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
        start_time = datetime.datetime.fromtimestamp(int(filter.start_time // 1000))
        end_time = datetime.datetime.fromtimestamp(int(filter.end_time // 1000))
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

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

from bk_resource.tools import get_serializer_fields
from django.db.models import Q
from iam import PathEqDjangoQuerySetConverter
from iam.resource.provider import ListResult, SchemaResult

from apps.permission.provider.base import BaseResourceProvider
from services.web.risk.models import Risk
from services.web.risk.serializers import RiskInfoSerializer


class RiskBaseProvider(BaseResourceProvider):
    attrs = None
    resource_type = None

    key_mapping = {}

    def list_instance(self, filters, page, **options):
        queryset = Risk.objects.none()
        with_path = False

        if not (filters.parent or filters.search):
            queryset = Risk.objects.all()
        elif filters.search:
            # 返回结果需要带上资源拓扑路径信息
            with_path = True

            keywords = filters.search.get(self.resource_type, [])

            q_filter = Q()
            for keyword in keywords:
                q_filter |= Q(risk_id__icontains=keyword)
            queryset = Risk.objects.filter(q_filter)

        if not with_path:
            results = [
                {"id": item.risk_id, "display_name": item.risk_id} for item in queryset[page.slice_from : page.slice_to]
            ]
        else:
            results = [
                {
                    "id": item.risk_id,
                    "display_name": item.risk_id,
                    "_bk_iam_path_": [],
                }
                for item in queryset[page.slice_from : page.slice_to]
            ]

        return ListResult(results=results, count=queryset.count())

    def fetch_instance_info(self, filters, **options):
        ids = []
        if filters.ids:
            ids = [i for i in filters.ids]

        queryset = Risk.objects.filter(risk_id__in=ids)

        results = [{"id": item.risk_id, "display_name": item.risk_id} for item in queryset]
        return ListResult(results=results, count=queryset.count())

    def list_instance_by_policy(self, filters, page, **options):
        expression = filters.expression
        if not expression:
            return ListResult(results=[], count=0)

        converter = PathEqDjangoQuerySetConverter(self.key_mapping)
        filters = converter.convert(expression)
        queryset = Risk.objects.filter(filters)
        results = [
            {"id": item.risk_id, "display_name": item.risk_id} for item in queryset[page.slice_from : page.slice_to]
        ]

        return ListResult(results=results, count=queryset.count())

    def search_instance(self, filters, page, **options):
        queryset = Risk.objects.filter(risk_id__contains=filters.keyword)
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
                "data": RiskInfoSerializer(instance=item).data,
            }
            for item in queryset[page.slice_from : page.slice_to]
        ]
        return ListResult(results=results, count=queryset.count())

    def fetch_resource_type_schema(self, **options):
        data = get_serializer_fields(RiskInfoSerializer)
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


class RiskResourceProvider(RiskBaseProvider):
    """
    策略实例视图
    """

    resource_type = "risk"

    key_mapping = {
        "risk.id": "risk_id",
        "risk.risk_id": "risk_id",
    }

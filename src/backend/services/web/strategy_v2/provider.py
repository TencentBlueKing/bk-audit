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

from django.db.models import Q
from iam import PathEqDjangoQuerySetConverter
from iam.resource.provider import ListResult, SchemaResult
from iam.resource.utils import Page

from apps.permission.handlers.resource_types import ResourceEnum
from apps.permission.provider.base import BaseResourceProvider, IAMResourceProvider
from core.serializers import get_serializer_fields
from services.web.strategy_v2.models import (
    LinkTable,
    Strategy,
    StrategyTag,
    StrategyTagSyncTrash,
)
from services.web.strategy_v2.serializers import (
    LinkTableInfoSerializer,
    StrategyProviderSerializer,
    StrategyTagResourceSerializer,
)


class StrategyBaseProvider(BaseResourceProvider):
    attrs = None
    resource_type = None
    resource_type_index_fields = [
        "strategy_id",
        "strategy_name",
        "control_id",
        "control_version",
        "link_table_uid",
        "link_table_version",
        "description",
        "risk_hazard",
        "risk_guidance",
    ]

    def list_instance(self, filters, page, **options):
        queryset = Strategy.objects.none()
        with_path = False

        if not (filters.parent or filters.search):
            queryset = Strategy.objects.all()
        elif filters.search:
            # 返回结果需要带上资源拓扑路径信息
            with_path = True

            keywords = filters.search.get(self.resource_type, [])

            q_filter = Q()
            for keyword in keywords:
                q_filter |= Q(strategy_name__icontains=keyword)
            queryset = Strategy.objects.filter(q_filter)

        if not with_path:
            results = [
                {"id": item.pk, "display_name": item.strategy_name}
                for item in queryset[page.slice_from : page.slice_to]
            ]
        else:
            results = [
                {
                    "id": item.pk,
                    "display_name": item.strategy_name,
                    "_bk_iam_path_": [],
                }
                for item in queryset[page.slice_from : page.slice_to]
            ]

        return ListResult(results=results, count=queryset.count())

    def fetch_instance_info(self, filters, **options):
        ids = []
        if filters.ids:
            ids = [i for i in filters.ids]

        queryset = Strategy.objects.filter(strategy_id__in=ids)

        results = [{"id": item.pk, "display_name": item.strategy_name} for item in queryset]
        return ListResult(results=results, count=queryset.count())

    def list_instance_by_policy(self, filters, page, **options):
        expression = filters.expression
        if not expression:
            return ListResult(results=[], count=0)

        key_mapping = {
            f"{self.resource_type}.id": "id",
        }
        converter = PathEqDjangoQuerySetConverter(key_mapping)
        filters = converter.convert(expression)
        queryset = Strategy.objects.filter(filters)
        results = [
            {"id": item.id, "display_name": item.strategy_name} for item in queryset[page.slice_from : page.slice_to]
        ]

        return ListResult(results=results, count=queryset.count())

    def search_instance(self, filters, page, **options):
        queryset = Strategy.objects.filter(strategy_name__icontains=filters.keyword)
        results = [
            {"id": item.pk, "display_name": item.strategy_name} for item in queryset[page.slice_from : page.slice_to]
        ]
        return ListResult(results=results, count=queryset.count())

    def fetch_instance_list(self, filter, page, **options):
        start_time = datetime.datetime.fromtimestamp(int(filter.start_time // 1000))
        end_time = datetime.datetime.fromtimestamp(int(filter.end_time // 1000))
        queryset = Strategy.objects.filter(updated_at__gt=start_time, updated_at__lte=end_time)
        results = [
            {
                "id": item.pk,
                "display_name": item.strategy_name,
                "creator": item.created_by,
                "created_at": int(item.created_at.timestamp() * 1000) if item.created_at else None,
                "updater": item.updated_by,
                "updated_at": int(item.updated_at.timestamp() * 1000) if item.updated_at else None,
                "data": StrategyProviderSerializer(instance=item).data,
            }
            for item in queryset[page.slice_from : page.slice_to]
        ]
        return ListResult(results=results, count=queryset.count())

    def fetch_resource_type_schema(self, **options):
        # 需要在反向拉取的 Schema 中包含只读字段（如主键 strategy_id）
        data = get_serializer_fields(StrategyProviderSerializer)
        return SchemaResult(
            properties={
                item["name"]: {
                    "type": item["type"].lower(),
                    "description_en": item["name"],
                    "description": item["description"],
                    "is_index": item["name"] in self.resource_type_index_fields,
                }
                for item in data
            }
        )


class StrategyResourceProvider(StrategyBaseProvider):
    """
    策略实例视图
    """

    resource_type = "strategy"


class LinkTableProvider(BaseResourceProvider):
    attrs = None
    resource_type = "link_table"

    def list_instance(self, filters, page, **options):
        queryset = LinkTable.objects.none()
        with_path = False

        if not (filters.parent or filters.search):
            queryset = LinkTable.list_max_version_link_table()
        elif filters.search:
            # 返回结果需要带上资源拓扑路径信息
            with_path = True

            keywords = filters.search.get(self.resource_type, [])

            q_filter = Q()
            for keyword in keywords:
                q_filter |= Q(name__icontains=keyword)
            queryset = LinkTable.list_max_version_link_table().filter(q_filter)

        if not with_path:
            results = [
                {"id": item.uid, "display_name": item.name} for item in queryset[page.slice_from : page.slice_to]
            ]
        else:
            results = [
                {
                    "id": item.uid,
                    "display_name": item.name,
                    "_bk_iam_path_": [],
                }
                for item in queryset[page.slice_from : page.slice_to]
            ]

        return ListResult(results=results, count=queryset.count())

    def fetch_instance_info(self, filters, **options):
        ids = []
        if filters.ids:
            ids = [i for i in filters.ids]

        queryset = LinkTable.list_max_version_link_table().filter(uid__in=ids)

        results = [{"id": item.uid, "display_name": item.name} for item in queryset]
        return ListResult(results=results, count=queryset.count())

    def list_instance_by_policy(self, filters, page, **options):
        expression = filters.expression
        if not expression:
            return ListResult(results=[], count=0)

        key_mapping = {
            f"{self.resource_type}.id": "uid",
        }
        converter = PathEqDjangoQuerySetConverter(key_mapping)
        filters = converter.convert(expression)
        queryset = LinkTable.list_max_version_link_table().filter(filters)
        results = [{"id": item.uid, "display_name": item.name} for item in queryset[page.slice_from : page.slice_to]]

        return ListResult(results=results, count=queryset.count())

    def search_instance(self, filters, page, **options):
        queryset = LinkTable.list_max_version_link_table().filter(name__icontains=filters.keyword)
        results = [{"id": item.uid, "display_name": item.name} for item in queryset[page.slice_from : page.slice_to]]
        return ListResult(results=results, count=queryset.count())

    def fetch_instance_list(self, filter, page, **options):
        start_time = datetime.datetime.fromtimestamp(int(filter.start_time // 1000))
        end_time = datetime.datetime.fromtimestamp(int(filter.end_time // 1000))
        queryset = LinkTable.list_max_version_link_table().filter(updated_at__gt=start_time, updated_at__lte=end_time)
        results = [
            {
                "id": item.uid,
                "display_name": item.name,
                "creator": item.created_by,
                "created_at": item.created_at,
                "updater": item.updated_by,
                "updated_at": item.updated_at,
                "data": LinkTableInfoSerializer(instance=item).data,
            }
            for item in queryset[page.slice_from : page.slice_to]
        ]
        return ListResult(results=results, count=queryset.count())

    def fetch_resource_type_schema(self, **options):
        data = get_serializer_fields(LinkTableInfoSerializer)
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


class StrategyTagResourceProvider(IAMResourceProvider):
    """
    策略标签资源提供者
    """

    resource_type = ResourceEnum.STRATEGY_TAG.id
    resource_provider_serializer = StrategyTagResourceSerializer
    resource_type_index_fields = ["tag_id", "strategy_id"]

    def list_attr_value_choices(self, attr: str, page: Page) -> List:
        return []

    def filter_list_instance_results(
        self, parent_id: Optional[str], resource_type: Optional[str], page: Page
    ) -> Tuple[List[dict], int]:
        queryset = StrategyTag.objects.select_related("tag")
        if parent_id and resource_type == ResourceEnum.STRATEGY.id:
            queryset = queryset.filter(strategy_id=int(parent_id))

        results = [
            {
                "id": str(item.pk),
                "display_name": item.tag.tag_name if item.tag else str(item.pk),
            }
            for item in queryset[page.slice_from : page.slice_to]
        ]
        return results, queryset.count()

    def filter_fetch_instance_results(self, ids: List[str]) -> Tuple[List[dict], int]:
        queryset = StrategyTag.objects.select_related("tag").filter(pk__in=ids)
        results = [
            {
                "id": str(item.pk),
                "display_name": item.tag.tag_name if item.tag else str(item.pk),
            }
            for item in queryset
        ]
        return results, queryset.count()

    def filter_search_instance_results(
        self, parent_id: Optional[str], resource_type: Optional[str], keyword: str, page: Page
    ) -> Tuple[List[dict], int]:
        queryset = StrategyTag.objects.select_related("tag")
        if parent_id and resource_type == ResourceEnum.STRATEGY.id:
            queryset = queryset.filter(strategy_id=int(parent_id))

        queryset = queryset.filter(tag__tag_name__icontains=keyword)
        results = [
            {
                "id": str(item.pk),
                "display_name": item.tag.tag_name if item.tag else str(item.pk),
            }
            for item in queryset[page.slice_from : page.slice_to]
        ]
        return results, queryset.count()

    def list_instance_by_policy(self, filters, page, **options):
        expression = filters.expression
        if not expression:
            return ListResult(results=[], count=0)

        key_mapping = {
            f"{self.resource_type}.id": "id",
        }
        converter = PathEqDjangoQuerySetConverter(key_mapping)
        django_filters = converter.convert(expression)
        queryset = StrategyTag.objects.select_related("tag").filter(django_filters)
        results = [
            {
                "id": str(item.pk),
                "display_name": item.tag.tag_name if item.tag else str(item.pk),
            }
            for item in queryset[page.slice_from : page.slice_to]
        ]
        return ListResult(results=results, count=queryset.count())

    def fetch_instance_list(self, filter, page, **options):
        start_time = datetime.datetime.fromtimestamp(int(filter.start_time // 1000))
        end_time = datetime.datetime.fromtimestamp(int(filter.end_time // 1000))
        # IAM 反向同步需要同时拿到：
        # 1. 当前仍存在的策略标签（用于补录或更新）
        # 2. 已被删除的策略标签（墓碑数据，用于远端清理悬挂关系）
        queryset = (
            StrategyTag.objects.select_related("tag")
            .filter(updated_at__gt=start_time, updated_at__lte=end_time)
            .order_by("-id")
        )
        trash_queryset = StrategyTagSyncTrash.objects.filter(
            updated_at__gt=start_time, updated_at__lte=end_time
        ).order_by("-id")

        live_count = queryset.count()
        trash_count = trash_queryset.count()
        total_count = live_count + trash_count

        slice_from = page.slice_from
        slice_to = page.slice_to

        results_payload = []

        if slice_from < live_count:
            # 优先消费仍存在的实例，保证排序与原 QuerySet 保持一致
            live_slice_end = min(slice_to, live_count)
            live_slice = list(queryset[slice_from:live_slice_end])
            snapshot = self.resource_provider_serializer(live_slice, many=True).data
            results_payload.extend(zip(live_slice, snapshot))

        if slice_to > live_count:
            # 若分页范围超过现存实例数量，则继续从墓碑数据中取补足分页窗口
            trash_start = max(0, slice_from - live_count)
            trash_end = slice_to - live_count
            trash_slice = list(trash_queryset[trash_start:trash_end])
            for item in trash_slice:
                results_payload.append(
                    (
                        item,
                        {
                            "id": item.original_id,
                            "strategy_id": 0,
                            "tag_id": 0,
                        },
                    )
                )

        results = []
        for item, data in results_payload:
            if isinstance(item, StrategyTagSyncTrash):
                results.append(
                    {
                        "id": str(item.original_id),
                        "display_name": str(item.original_id),
                        "creator": item.created_by,
                        "created_at": item.created_at,
                        "updater": item.updated_by,
                        "updated_at": item.updated_at,
                        "data": data,
                    }
                )
            else:
                tag_name = item.tag.tag_name if item.tag else str(item.pk)
                results.append(
                    {
                        "id": str(item.pk),
                        "display_name": tag_name,
                        "creator": item.created_by,
                        "created_at": item.created_at,
                        "updater": item.updated_by,
                        "updated_at": item.updated_at,
                        "data": data,
                    }
                )

        return ListResult(results=results, count=total_count)

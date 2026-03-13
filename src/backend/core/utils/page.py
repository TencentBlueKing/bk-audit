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

from typing import List, Tuple

from django.db.models import QuerySet
from rest_framework.pagination import PageNumberPagination
from rest_framework.request import Request
from rest_framework.settings import api_settings


def paginate_data(queryset: QuerySet, request: Request) -> Tuple[List, PageNumberPagination]:
    """
    分页 Data
    """

    page: PageNumberPagination = api_settings.DEFAULT_PAGINATION_CLASS()
    paged_queryset = page.paginate_queryset(queryset=queryset, request=request)
    return paged_queryset, page


class _PreCountQuerySet:
    """
    包装 QuerySet，使 .count() 返回预计算的值，
    避免 DRF Paginator 对带 JOIN/CASE 的排序 QS 执行昂贵的 COUNT SQL。
    其余操作（切片、迭代等）委托给原始 QuerySet。
    """

    def __init__(self, queryset: QuerySet, count: int):
        self._queryset = queryset
        self._count = count

    def count(self):
        return self._count

    @property
    def ordered(self):
        return self._queryset.ordered

    def __getitem__(self, key):
        return self._queryset[key]

    def __len__(self):
        return self._count


def paginate_queryset(
    queryset: QuerySet,
    request: Request,
    base_queryset: QuerySet = None,
    count_queryset: QuerySet = None,
) -> (QuerySet, PageNumberPagination):
    """
    分页 QuerySet

    Args:
        queryset: 带排序的 QuerySet，用于分页切片（ORDER BY + LIMIT）
        request: DRF 请求对象
        base_queryset: 数据加载阶段使用的 QuerySet（如带注解的版本）
        count_queryset: 用于 COUNT 的轻量 QuerySet（不带排序注解/JOIN），
                        避免 COUNT SQL 包含无用的 JOIN 和 CASE/WHEN
    """

    page: PageNumberPagination = api_settings.DEFAULT_PAGINATION_CLASS()
    if count_queryset is not None:
        count = count_queryset.count()
        paged_queryset = page.paginate_queryset(queryset=_PreCountQuerySet(queryset, count), request=request)
    else:
        paged_queryset = page.paginate_queryset(queryset=queryset, request=request)
    if base_queryset is None:
        base_queryset = queryset.model.objects
    return base_queryset.filter(pk__in=[item.pk for item in paged_queryset]), page

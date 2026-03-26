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


def paginate_queryset(
    queryset: QuerySet, request: Request, base_queryset: QuerySet = None
) -> (QuerySet, PageNumberPagination):
    """
    分页 QuerySet
    """

    page: PageNumberPagination = api_settings.DEFAULT_PAGINATION_CLASS()
    paged_queryset = page.paginate_queryset(queryset=queryset, request=request)
    if base_queryset is None:
        base_queryset = queryset.model.objects
    return base_queryset.filter(pk__in=[item.pk for item in paged_queryset]), page

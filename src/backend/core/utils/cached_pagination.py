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

import hashlib

from blueapps.utils.logger import logger
from django.conf import settings
from django.core.cache import cache
from django.core.paginator import Paginator
from django.utils.functional import cached_property
from rest_framework.pagination import PageNumberPagination


class CachedCountPaginator(Paginator):
    """
    缓存 COUNT 结果到 Redis，避免每次分页都执行昂贵的 COUNT SQL。

    cache_key 根据 QuerySet 的 SQL 自动生成，调用方无需手动构建。
    通过 @cached_property 保证同一实例内只访问一次 Redis。
    """

    # 缓存 key 前缀
    CACHE_KEY_PREFIX = "paginator_count"

    @cached_property
    def count(self):
        # 非 QuerySet（如 list）没有 .query 属性，直接走原始 count 不缓存
        if not hasattr(self.object_list, "query"):
            return super().count

        # 去掉 ordering：ORDER BY 不影响 COUNT 结果，避免仅排序不同就产生不同的 cache_key
        query_string = str(self.object_list.order_by().query)
        cache_key = f"{self.CACHE_KEY_PREFIX}:{hashlib.md5(query_string.encode()).hexdigest()[:12]}"
        cache_timeout = settings.RISK_LIST_COUNT_CACHE_TIMEOUT

        total_count = cache.get(cache_key)
        if total_count is not None:
            logger.debug("[CachedCountPaginator] cache hit, key=%s, count=%d", cache_key, total_count)
            return total_count

        # 缓存未命中，走实际 COUNT SQL
        total_count = super().count
        cache.set(cache_key, total_count, cache_timeout)
        logger.debug("[CachedCountPaginator] cache miss, key=%s, count=%d", cache_key, total_count)
        return total_count


class CachedCountPageNumberPagination(PageNumberPagination):
    """
    在标准 PageNumberPagination 基础上缓存 COUNT 查询结果。

    通过 DRF 的 django_paginator_class 钩子注入 CachedCountPaginator，
    让 DRF 的分页流程完全不变，只是底层 Paginator 的 count 走缓存。

    使用方式：
        page = CachedCountPageNumberPagination()
        page_data = page.paginate_queryset(queryset, request)
    """

    django_paginator_class = CachedCountPaginator

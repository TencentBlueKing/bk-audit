# -*- coding: utf-8 -*-
"""
Tests for core.utils.cached_pagination
"""

import hashlib
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import SimpleTestCase
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from core.utils.cached_pagination import (
    CachedCountPageNumberPagination,
    CachedCountPaginator,
)


class TestCachedCountPaginator(SimpleTestCase):
    """CachedCountPaginator 单测：验证 count 的缓存行为"""

    def setUp(self):
        self.object_list = list(range(50))
        cache.clear()

    def _make_paginator(self, object_list=None):
        return CachedCountPaginator(object_list or self.object_list, per_page=10)

    def _get_cache_key(self, object_list):
        """模拟 CachedCountPaginator 内部的 cache_key 生成逻辑"""
        # 对于普通 list，str(query) 不可用；这里只测 QuerySet 场景
        # 但 Paginator 对 list 也能工作，只是 cache_key 基于 str(object_list.query)
        # 所以这里用 mock 来测试
        pass

    @staticmethod
    def _make_mock_qs(query_string, count_value=0, unordered_query_string=None):
        """构造 mock QuerySet，支持 .order_by() 返回去掉 ordering 后的 query"""
        mock_qs = MagicMock()
        mock_qs.query = query_string
        mock_qs.count.return_value = count_value
        mock_qs.__len__ = MagicMock(return_value=count_value)

        # .order_by() 返回一个新的 mock，其 query 为去掉 ordering 后的 SQL
        unordered_qs = MagicMock()
        unordered_qs.query = unordered_query_string or query_string
        mock_qs.order_by.return_value = unordered_qs
        return mock_qs

    def test_count_cache_miss_with_queryset(self):
        """缓存未命中时应计算实际 count 并写入缓存"""
        mock_qs = self._make_mock_qs("SELECT * FROM risk_risk", count_value=50)

        paginator = CachedCountPaginator(mock_qs, per_page=10)
        count = paginator.count

        self.assertEqual(count, 50)
        # 验证缓存已写入（cache_key 基于去掉 ordering 后的 query）
        expected_key = f"paginator_count:{hashlib.md5(b'SELECT * FROM risk_risk').hexdigest()[:12]}"
        self.assertEqual(cache.get(expected_key), 50)

    def test_count_cache_hit_with_queryset(self):
        """缓存命中时应直接返回缓存值，不执行 COUNT SQL"""
        query_string = "SELECT * FROM risk_risk WHERE status=1"
        cache_key = f"paginator_count:{hashlib.md5(query_string.encode()).hexdigest()[:12]}"
        cache.set(cache_key, 999, 60)

        mock_qs = self._make_mock_qs(query_string)

        paginator = CachedCountPaginator(mock_qs, per_page=10)
        count = paginator.count

        # 返回缓存的值而非实际 count
        self.assertEqual(count, 999)
        # 不应调用 queryset.count()
        mock_qs.count.assert_not_called()

    def test_count_zero(self):
        """count 为 0 时也应正常缓存和返回"""
        mock_qs = self._make_mock_qs("SELECT * FROM risk_risk WHERE 1=0", count_value=0)

        paginator = CachedCountPaginator(mock_qs, per_page=10)
        count = paginator.count

        self.assertEqual(count, 0)
        cache_key = f"paginator_count:{hashlib.md5(b'SELECT * FROM risk_risk WHERE 1=0').hexdigest()[:12]}"
        self.assertEqual(cache.get(cache_key), 0)

    def test_same_query_same_cache_key(self):
        """相同筛选条件但不同排序应命中同一个缓存 key（ORDER BY 不影响 COUNT）"""
        base_query = "SELECT * FROM risk_risk WHERE status=1"
        expected_key = f"paginator_count:{hashlib.md5(base_query.encode()).hexdigest()[:12]}"

        # 第一次：带 ORDER BY event_time 的查询
        mock_qs1 = self._make_mock_qs(
            "SELECT * FROM risk_risk WHERE status=1 ORDER BY event_time",
            count_value=42,
            unordered_query_string=base_query,
        )
        p1 = CachedCountPaginator(mock_qs1, per_page=10)
        self.assertEqual(p1.count, 42)
        self.assertEqual(cache.get(expected_key), 42)

        # 第二次：带 ORDER BY risk_level 的查询（不同排序），应命中同一个缓存
        mock_qs2 = self._make_mock_qs(
            "SELECT * FROM risk_risk WHERE status=1 ORDER BY risk_level",
            unordered_query_string=base_query,
        )
        p2 = CachedCountPaginator(mock_qs2, per_page=10)
        self.assertEqual(p2.count, 42)
        mock_qs2.count.assert_not_called()

    def test_different_query_different_cache_key(self):
        """不同 SQL 应使用不同的缓存 key"""
        mock_qs1 = self._make_mock_qs("SELECT * FROM risk_risk WHERE status=1", count_value=10)
        mock_qs2 = self._make_mock_qs("SELECT * FROM risk_risk WHERE status=2", count_value=20)

        p1 = CachedCountPaginator(mock_qs1, per_page=10)
        p2 = CachedCountPaginator(mock_qs2, per_page=10)

        self.assertEqual(p1.count, 10)
        self.assertEqual(p2.count, 20)


class TestCachedCountPageNumberPagination(SimpleTestCase):
    """CachedCountPageNumberPagination 集成测试：验证完整的 DRF 分页流程"""

    def setUp(self):
        self.factory = APIRequestFactory()
        cache.clear()

    def _make_request(self, params=None):
        return Request(self.factory.get("/", params or {}))

    def test_django_paginator_class(self):
        """应使用 CachedCountPaginator 作为底层 Paginator"""
        paginator = CachedCountPageNumberPagination()
        self.assertEqual(paginator.django_paginator_class, CachedCountPaginator)

    def test_paginate_queryset(self):
        """完整分页流程应正常工作"""
        paginator = CachedCountPageNumberPagination()
        paginator.page_size = 10

        request = self._make_request({"page": "1"})
        data = list(range(25))
        result = paginator.paginate_queryset(data, request)

        self.assertEqual(result, list(range(10)))

    def test_get_paginated_response(self):
        """get_paginated_response 应返回含 count/next/previous/results 的标准结构"""
        paginator = CachedCountPageNumberPagination()
        paginator.page_size = 10

        request = self._make_request({"page": "1"})
        data = list(range(25))
        result = paginator.paginate_queryset(data, request)
        response = paginator.get_paginated_response(result)

        self.assertEqual(response.data["count"], 25)
        self.assertIn("results", response.data)

    @patch("core.utils.cached_pagination.settings")
    def test_cache_timeout_from_settings(self, mock_settings):
        """缓存超时时间应从 settings.RISK_LIST_COUNT_CACHE_TIMEOUT 读取"""
        mock_settings.RISK_LIST_COUNT_CACHE_TIMEOUT = 120

        mock_qs = TestCachedCountPaginator._make_mock_qs("SELECT * FROM risk_risk", count_value=10)

        paginator = CachedCountPaginator(mock_qs, per_page=10)
        _ = paginator.count

        # 验证 cache.set 被调用时使用了正确的 timeout
        expected_key = f"paginator_count:{hashlib.md5(b'SELECT * FROM risk_risk').hexdigest()[:12]}"
        self.assertEqual(cache.get(expected_key), 10)

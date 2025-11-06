# -*- coding: utf-8 -*-
import datetime

import pytest
from django.conf import settings
from django.utils import timezone
from iam.collection import FancyDict
from iam.resource.utils import Page

from core.serializers import get_serializer_fields
from services.web.strategy_v2.models import Strategy
from services.web.strategy_v2.provider import StrategyResourceProvider
from services.web.strategy_v2.serializers import StrategyProviderSerializer


@pytest.mark.django_db
class TestStrategyResourceProviderAPI:
    def setup_method(self):
        self.provider = StrategyResourceProvider()

        class _R:
            headers = {}

        self._dummy_req = _R()

        def _get_local_request():
            return self._dummy_req

        setattr(StrategyResourceProvider, "get_local_request", staticmethod(_get_local_request))

    def _mk(self, name: str):
        return Strategy.objects.create(namespace=settings.DEFAULT_NAMESPACE, strategy_name=name)

    def test_list_and_fetch_info_and_search(self):
        a = self._mk("alpha")
        b = self._mk("beta")

        # list_instance 无 parent / 无 search
        lr = self.provider.list_instance(FancyDict(parent=None, search=None), Page(50, 0))
        expect = [
            {"id": a.pk, "display_name": a.strategy_name},
            {"id": b.pk, "display_name": b.strategy_name},
        ]
        assert lr.count == 2
        assert sorted(lr.results, key=lambda x: x["id"]) == sorted(expect, key=lambda x: x["id"])

        # fetch_instance_info
        lr = self.provider.fetch_instance_info(FancyDict(ids=[a.pk, b.pk]))
        assert lr.count == 2
        assert sorted(lr.results, key=lambda x: x["id"]) == sorted(expect, key=lambda x: x["id"])

        # search_instance 关键字匹配名称
        lr = self.provider.search_instance(FancyDict(keyword="alp"), Page(50, 0))
        assert lr.count == 1
        assert lr.results == [{"id": a.pk, "display_name": a.strategy_name}]

    def test_fetch_instance_list_and_schema(self):
        s = self._mk("gamma")
        now = timezone.now()
        start_ms = int((now - datetime.timedelta(days=1)).timestamp() * 1000)
        end_ms = int((now + datetime.timedelta(seconds=2)).timestamp() * 1000)

        lr = self.provider.fetch_instance_list(FancyDict(start_time=start_ms, end_time=end_ms), Page(50, 0))
        assert lr.count >= 1
        # 至少包含我们刚创建的策略
        expect_item = {
            "id": s.pk,
            "display_name": s.strategy_name,
            "creator": s.created_by,
            "created_at": int(s.created_at.timestamp() * 1000) if s.created_at else None,
            "updater": s.updated_by,
            "updated_at": int(s.updated_at.timestamp() * 1000) if s.updated_at else None,
            "data": StrategyProviderSerializer(s).data,
        }
        assert expect_item in lr.results

        # Schema 整体校验
        fields = get_serializer_fields(StrategyProviderSerializer)
        expected_props = {
            item["name"]: {
                "type": item["type"].lower(),
                "description_en": item["name"],
                "description": item["description"],
                **({"is_index": item["is_index"]} if "is_index" in item else {}),
            }
            for item in fields
        }
        schema = self.provider.fetch_resource_type_schema()
        for field_name, field_expectation in expected_props.items():
            assert field_name in schema.properties
            actual = schema.properties[field_name]
            for key, value in field_expectation.items():
                assert actual.get(key) == value

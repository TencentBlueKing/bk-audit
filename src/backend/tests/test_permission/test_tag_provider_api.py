# -*- coding: utf-8 -*-
import datetime

import pytest
from django.utils import timezone
from iam.collection import FancyDict
from iam.resource.utils import Page

from apps.meta.models import Tag
from apps.meta.provider.tag import TagResourceProvider
from apps.permission.serializers import TagProviderSerializer
from core.serializers import get_serializer_fields


@pytest.mark.django_db
class TestTagResourceProviderAPI:
    def setup_method(self):
        self.provider = TagResourceProvider()

        class _R:
            headers = {}

        self._dummy_req = _R()

        def _get_local_request():
            return self._dummy_req

        setattr(TagResourceProvider, "get_local_request", staticmethod(_get_local_request))

    def _mk(self, name: str):
        return Tag.objects.create(tag_name=name)

    def test_list_and_fetch_info_and_search(self):
        a = self._mk("blue")
        b = self._mk("green")

        # list_instance 无 parent / 无 search
        lr = self.provider.list_instance(FancyDict(parent=None, search=None), Page(50, 0))
        expect = [
            {"id": a.tag_id, "display_name": a.tag_name},
            {"id": b.tag_id, "display_name": b.tag_name},
        ]
        assert lr.count == 2
        assert sorted(lr.results, key=lambda x: x["id"]) == sorted(expect, key=lambda x: x["id"])

        # fetch_instance_info
        lr = self.provider.fetch_instance_info(FancyDict(ids=[a.tag_id, b.tag_id]))
        assert lr.count == 2
        assert sorted(lr.results, key=lambda x: x["id"]) == sorted(expect, key=lambda x: x["id"])

        # search_instance 关键字匹配
        lr = self.provider.search_instance(FancyDict(keyword="blu"), Page(50, 0))
        assert lr.count == 1
        assert lr.results == [{"id": a.tag_id, "display_name": a.tag_name}]

    def test_fetch_instance_list_and_schema(self):
        t = self._mk("red")
        now = timezone.now()
        start_ms = int((now - datetime.timedelta(days=1)).timestamp() * 1000)
        end_ms = int((now + datetime.timedelta(seconds=2)).timestamp() * 1000)

        lr = self.provider.fetch_instance_list(FancyDict(start_time=start_ms, end_time=end_ms), Page(50, 0))
        assert lr.count >= 1
        expect_item = {
            "id": t.tag_id,
            "display_name": t.tag_name,
            "creator": t.created_by,
            "created_at": int(t.created_at.timestamp() * 1000) if t.created_at else None,
            "updater": t.updated_by,
            "updated_at": int(t.updated_at.timestamp() * 1000) if t.updated_at else None,
            "data": TagProviderSerializer(t).data,
        }
        assert expect_item in lr.results

        # Schema 整体校验
        fields = get_serializer_fields(TagProviderSerializer)
        expected_props = {
            item["name"]: {
                "type": item["type"].lower(),
                "description_en": item["name"],
                "description": item["description"],
            }
            for item in fields
        }
        schema = self.provider.fetch_resource_type_schema()
        assert schema.properties == expected_props

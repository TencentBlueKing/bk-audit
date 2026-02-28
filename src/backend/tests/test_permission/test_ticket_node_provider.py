# -*- coding: utf-8 -*-
import time

import pytest
from iam.collection import FancyDict
from iam.resource.utils import Page

from apps.permission.handlers.resource_types import ResourceEnum
from core.serializers import get_serializer_fields
from services.web.risk.models import TicketNode
from services.web.risk.provider import TicketNodeResourceProvider
from services.web.risk.serializers import TicketNodeProviderSerializer


@pytest.mark.django_db
class TestTicketNodeResourceProvider:
    def setup_method(self):
        self.provider = TicketNodeResourceProvider()

    def _mk_tn(self, risk_id: str, operator: str, action: str, ts: float = None):
        if ts is None:
            ts = time.time()
        return TicketNode.objects.create(
            risk_id=risk_id,
            operator=operator,
            action=action,
            timestamp=ts,
            time=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts)),
        )

    def test_filter_list_and_parent_filter(self):
        a = self._mk_tn("R1", "alice", "CloseRisk")
        b = self._mk_tn("R2", "bob", "TransOperator")

        results, count = self.provider.filter_list_instance_results(None, None, Page(50, 0))
        assert count == 2
        expected = [
            {"id": str(a.pk), "display_name": str(a.pk)},
            {"id": str(b.pk), "display_name": str(b.pk)},
        ]
        assert sorted(results, key=lambda x: x["id"]) == sorted(expected, key=lambda x: x["id"])

        results_r1, count_r1 = self.provider.filter_list_instance_results("R1", ResourceEnum.RISK.id, Page(50, 0))
        assert count_r1 == 1
        assert results_r1 == [{"id": str(a.pk), "display_name": str(a.pk)}]

    def test_filter_fetch_instance_results_by_ids(self):
        a = self._mk_tn("R1", "alice", "CloseRisk")
        b = self._mk_tn("R2", "bob", "TransOperator")
        results, count = self.provider.filter_fetch_instance_results([str(a.pk), str(b.pk)])
        expected = [
            {"id": str(a.pk), "display_name": str(a.pk)},
            {"id": str(b.pk), "display_name": str(b.pk)},
        ]
        assert count == 2
        assert sorted(results, key=lambda x: x["id"]) == sorted(expected, key=lambda x: x["id"])

    def test_filter_search_instance_results(self):
        a = self._mk_tn("R1", "alice", "CloseRisk")
        _ = self._mk_tn("R2", "bob", "TransOperator")

        results, count = self.provider.filter_search_instance_results(None, None, "ali", Page(50, 0))
        assert count == 1
        assert results == [{"id": str(a.pk), "display_name": str(a.pk)}]

        results2, count2 = self.provider.filter_search_instance_results("R1", ResourceEnum.RISK.id, "ali", Page(50, 0))
        assert count2 == 1
        assert results2 == [{"id": str(a.pk), "display_name": str(a.pk)}]

    def test_fetch_instance_list_and_schema(self):
        now = time.time()
        past = now - 600
        ts = int(now)
        a = self._mk_tn("R1", "alice", "CloseRisk", ts=ts)

        filter_fd = FancyDict(start_time=int(past * 1000), end_time=(ts + 1) * 1000)
        page = Page(50, 0)
        lr = self.provider.fetch_instance_list(filter_fd, page)
        assert lr.count == 1
        expected_item = {
            "id": str(a.pk),
            "display_name": str(a.pk),
            "creator": None,
            "created_at": int(a.timestamp * 1000),
            "updater": None,
            "updated_at": int(a.timestamp * 1000),
            "data": TicketNodeProviderSerializer(a).data,
        }
        assert lr.results == [expected_item]

        fields = get_serializer_fields(TicketNodeProviderSerializer)
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

    def test_list_instance_by_policy_no_expression(self):
        lr = self.provider.list_instance_by_policy(FancyDict(expression=None), Page(50, 0))
        assert lr.count == 0

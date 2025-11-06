# -*- coding: utf-8 -*-
import datetime

import pytest
from django.utils import timezone
from iam.collection import FancyDict
from iam.resource.utils import Page

from apps.permission.handlers.resource_types import ResourceEnum
from core.serializers import get_serializer_fields
from services.web.risk.models import TicketPermission
from services.web.risk.provider import TicketPermissionResourceProvider
from services.web.risk.serializers import TicketPermissionProviderSerializer


@pytest.mark.django_db
class TestTicketPermissionResourceProvider:
    def setup_method(self):
        self.provider = TicketPermissionResourceProvider()

    def _mk_tp(self, risk_id: str, action: str, user: str, user_type: str = "operator", ts: datetime.datetime = None):
        """
        注意：TicketPermission.authorized_at 使用 auto_now_add=True，直接在 create() 中传值会被覆盖。
        为了保证时间精确可控（避免 CI 与本地因为毫秒边界/执行时延产生不稳定），
        这里先创建，再通过 update() 显式写入 authorized_at。
        """
        obj = TicketPermission.objects.create(
            risk_id=risk_id,
            action=action,
            user=user,
            user_type=user_type,
        )
        if ts is None:
            ts = timezone.now()
        # 通过 update() 绕过 auto_now_add 行为，确保写入指定时间
        TicketPermission.objects.filter(pk=obj.pk).update(authorized_at=ts)
        obj.refresh_from_db()
        return obj

    def test_filter_list_and_parent_filter(self):
        a = self._mk_tp("R1", "list_risk", "alice")
        b = self._mk_tp("R2", "list_risk", "bob")

        # 无父资源过滤
        results, count = self.provider.filter_list_instance_results(None, None, Page(50, 0))
        # 使用完整 JSON 校验（排序后比较）
        expected = [
            {"id": str(a.pk), "display_name": str(a.pk)},
            {"id": str(b.pk), "display_name": str(b.pk)},
        ]
        assert count == 2
        assert sorted(results, key=lambda x: x["id"]) == sorted(expected, key=lambda x: x["id"])

        # 按风险作为父资源过滤
        results_r1, count_r1 = self.provider.filter_list_instance_results("R1", ResourceEnum.RISK.id, Page(50, 0))
        assert count_r1 == 1
        assert results_r1 == [{"id": str(a.pk), "display_name": str(a.pk)}]

    def test_filter_fetch_instance_results_by_ids(self):
        a = self._mk_tp("R1", "list_risk", "alice")
        b = self._mk_tp("R2", "list_risk", "bob")
        results, count = self.provider.filter_fetch_instance_results([str(a.pk), str(b.pk), "not-int"])
        expected = [
            {"id": str(a.pk), "display_name": str(a.pk)},
            {"id": str(b.pk), "display_name": str(b.pk)},
        ]
        assert count == 2
        assert sorted(results, key=lambda x: x["id"]) == sorted(expected, key=lambda x: x["id"])

    def test_filter_search_instance_results(self):
        a = self._mk_tp("R1", "list_risk", "alice")
        _ = self._mk_tp("R2", "list_risk", "bob")

        # 关键字 user=alice
        results, count = self.provider.filter_search_instance_results(None, None, "ali", Page(50, 0))
        assert count == 1
        assert results == [{"id": str(a.pk), "display_name": str(a.pk)}]

        # 携带父资源 risk=R1 仍匹配
        results2, count2 = self.provider.filter_search_instance_results("R1", ResourceEnum.RISK.id, "ali", Page(50, 0))
        assert count2 == 1
        assert results2 == [{"id": str(a.pk), "display_name": str(a.pk)}]

    def test_fetch_instance_list_and_schema(self):
        t1 = timezone.now()
        t0 = t1 - datetime.timedelta(minutes=10)
        a = self._mk_tp("R1", "list_risk", "alice", ts=t1)
        # 构造毫秒时间窗覆盖 a
        filter_fd = FancyDict(start_time=int((t0.timestamp()) * 1000), end_time=int((t1.timestamp()) * 1000))
        page = Page(50, 0)
        lr = self.provider.fetch_instance_list(filter_fd, page)
        assert lr.count == 1
        expected_item = {
            "id": str(a.pk),
            "display_name": str(a.pk),
            "creator": None,
            "created_at": int(a.authorized_at.timestamp() * 1000),
            "updater": None,
            "updated_at": int(a.authorized_at.timestamp() * 1000),
            "data": TicketPermissionProviderSerializer(a).data,
        }
        assert lr.results == [expected_item]

        # Schema 整体 JSON 校验（依据与 provider 相同的规则生成预期）
        fields = get_serializer_fields(TicketPermissionProviderSerializer)
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
        # 无表达式返回空
        lr = self.provider.list_instance_by_policy(FancyDict(expression=None), Page(50, 0))
        assert lr.count == 0

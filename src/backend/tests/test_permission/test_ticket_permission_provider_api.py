# -*- coding: utf-8 -*-
import datetime

import pytest
from django.utils import timezone
from iam.collection import FancyDict
from iam.resource.utils import Page

from apps.permission.handlers.resource_types import ResourceEnum
from services.web.risk.models import TicketPermission
from services.web.risk.provider import TicketPermissionResourceProvider


@pytest.mark.django_db
class TestTicketPermissionResourceProviderAPI:
    def setup_method(self):
        self.provider = TicketPermissionResourceProvider()

        # 避免 list_* 等方法内部读取本地 request 造成依赖，打桩成空 headers
        class _R:
            headers = {}

        self._dummy_req = _R()

        # 这里打桩类方法，避免实例方法绑定签名问题
        def _get_local_request():
            return self._dummy_req

        setattr(TicketPermissionResourceProvider, "get_local_request", staticmethod(_get_local_request))

    def _mk(self, rid: str, action: str, user: str, user_type: str = "operator", ts: datetime.datetime = None):
        ts = ts or timezone.now()
        return TicketPermission.objects.create(
            risk_id=rid,
            action=action,
            user=user,
            user_type=user_type,
            authorized_at=ts,
        )

    def test_list_instance_no_parent_and_with_parent(self):
        a = self._mk("R1", "list_risk", "alice")
        b = self._mk("R2", "list_risk", "bob")

        # 无父资源
        filters = FancyDict(parent=None, search=None)
        lr = self.provider.list_instance(filters, Page(50, 0))
        expect = [
            {"id": str(a.pk), "display_name": str(a.pk)},
            {"id": str(b.pk), "display_name": str(b.pk)},
        ]
        assert lr.count == 2
        assert sorted(lr.results, key=lambda x: x["id"]) == sorted(expect, key=lambda x: x["id"])

        # 有父资源（risk）
        filters = FancyDict(parent={"id": "R1", "type": ResourceEnum.RISK.id}, search=None)
        lr = self.provider.list_instance(filters, Page(50, 0))
        expect = [{"id": str(a.pk), "display_name": str(a.pk)}]
        assert lr.count == 1
        assert lr.results == expect

    def test_fetch_instance_info(self):
        a = self._mk("R1", "list_risk", "alice")
        b = self._mk("R2", "list_risk", "bob")
        lr = self.provider.fetch_instance_info(FancyDict(ids=[str(a.pk), str(b.pk)]))
        expect = [
            {"id": str(a.pk), "display_name": str(a.pk)},
            {"id": str(b.pk), "display_name": str(b.pk)},
        ]
        assert lr.count == 2
        assert sorted(lr.results, key=lambda x: x["id"]) == sorted(expect, key=lambda x: x["id"])

    def test_search_instance(self):
        a = self._mk("R1", "list_risk", "alice")
        _ = self._mk("R2", "list_risk", "bob")
        # 仅关键字
        lr = self.provider.search_instance(FancyDict(parent=None, keyword="ali"), Page(50, 0))
        assert lr.count == 1
        assert lr.results == [{"id": str(a.pk), "display_name": str(a.pk)}]
        # 携带父资源
        lr = self.provider.search_instance(
            FancyDict(parent={"id": "R1", "type": ResourceEnum.RISK.id}, keyword="ali"), Page(50, 0)
        )
        assert lr.count == 1
        assert lr.results == [{"id": str(a.pk), "display_name": str(a.pk)}]

    def test_list_attr_and_list_attr_value(self):
        # 我们未定义 attr_names，故返回空
        lr = self.provider.list_attr()
        assert lr.count == 0 and lr.results == []

        lr = self.provider.list_attr_value(FancyDict(attr="any"), Page(50, 0))
        assert lr.count == 0 and lr.results == []

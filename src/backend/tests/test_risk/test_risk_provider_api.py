# -*- coding: utf-8 -*-
import datetime
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase
from django.utils import timezone
from iam.collection import FancyDict
from iam.resource.utils import Page

from apps.permission.handlers.resource_types import ResourceEnum
from services.web.risk.models import ManualEvent, Risk
from services.web.risk.provider import ManualEventResourceProvider, RiskResourceProvider
from services.web.strategy_v2.models import Strategy


def _ms(dt: datetime.datetime) -> int:
    return int(dt.timestamp() * 1000)


class RiskResourceProviderAPITest(TestCase):
    def setUp(self):
        self._dummy_request = type("DummyRequest", (), {"headers": {}})()
        self.req_patcher = patch.object(RiskResourceProvider, "get_local_request", return_value=self._dummy_request)
        self.req_patcher.start()
        self.addCleanup(self.req_patcher.stop)
        self.provider = RiskResourceProvider()

    def _create_strategy(self, name: str) -> Strategy:
        return Strategy.objects.create(namespace=settings.DEFAULT_NAMESPACE, strategy_name=name)

    def _create_risk(
        self,
        *,
        risk_id: str,
        raw_event_id: str,
        strategy: Strategy,
        event_time: datetime.datetime,
        event_end_time: datetime.datetime | None,
    ) -> Risk:
        return Risk.objects.create(
            risk_id=risk_id,
            raw_event_id=raw_event_id,
            strategy=strategy,
            event_time=event_time,
            event_end_time=event_end_time,
        )

    def test_list_fetch_search(self):
        strategy_a = self._create_strategy("strategy-a")
        strategy_b = self._create_strategy("strategy-b")

        event_time = timezone.now()
        risk_a = self._create_risk(
            risk_id="risk-A",
            raw_event_id="raw-A",
            strategy=strategy_a,
            event_time=event_time,
            event_end_time=event_time + datetime.timedelta(minutes=5),
        )
        risk_b = self._create_risk(
            risk_id="risk-B",
            raw_event_id="raw-B",
            strategy=strategy_b,
            event_time=event_time,
            event_end_time=event_time + datetime.timedelta(minutes=10),
        )

        page = Page(50, 0)

        lr = self.provider.list_instance(FancyDict(parent=None, search=None), page)
        expected = [
            {"id": risk_a.risk_id, "display_name": risk_a.risk_id},
            {"id": risk_b.risk_id, "display_name": risk_b.risk_id},
        ]
        self.assertEqual(lr.count, 2)
        self.assertEqual(sorted(lr.results, key=lambda x: x["id"]), sorted(expected, key=lambda x: x["id"]))

        lr_parent = self.provider.list_instance(
            FancyDict(parent={"id": str(strategy_a.strategy_id), "type": ResourceEnum.STRATEGY.id}, search=None),
            page,
        )
        self.assertEqual(lr_parent.count, 1)
        self.assertEqual(lr_parent.results, [{"id": risk_a.risk_id, "display_name": risk_a.risk_id}])

        lr_fetch = self.provider.fetch_instance_info(FancyDict(ids=[risk_a.risk_id, risk_b.risk_id]))
        self.assertEqual(lr_fetch.count, 2)
        self.assertEqual(sorted(lr_fetch.results, key=lambda x: x["id"]), sorted(expected, key=lambda x: x["id"]))

        lr_search = self.provider.search_instance(FancyDict(parent=None, keyword="risk-A"), page)
        self.assertEqual(lr_search.count, 1)
        self.assertEqual(lr_search.results, [{"id": risk_a.risk_id, "display_name": risk_a.risk_id}])

    def test_fetch_instance_list_returns_ms(self):
        strategy = self._create_strategy("strategy")
        event_time = timezone.now().replace(microsecond=123000)
        event_end_time = event_time + datetime.timedelta(minutes=5)

        risk = self._create_risk(
            risk_id="risk-1",
            raw_event_id="raw-1",
            strategy=strategy,
            event_time=event_time,
            event_end_time=event_end_time,
        )

        last_operate_time = event_end_time + datetime.timedelta(minutes=10)
        Risk.objects.filter(pk=risk.pk).update(last_operate_time=last_operate_time)
        risk.refresh_from_db()

        now = timezone.now()
        start_ms = int((now - datetime.timedelta(hours=1)).timestamp() * 1000)
        end_ms = int((now + datetime.timedelta(hours=1)).timestamp() * 1000)

        result = self.provider.fetch_instance_list(FancyDict(start_time=start_ms, end_time=end_ms), Page(50, 0))
        self.assertGreaterEqual(result.count, 1)

        item = next(data for data in result.results if data["id"] == risk.risk_id)
        payload = item["data"]

        self.assertEqual(payload["event_time_timestamp"], _ms(risk.event_time))
        self.assertEqual(payload["event_end_time_timestamp"], _ms(risk.event_end_time))
        self.assertEqual(payload["last_operate_time_timestamp"], _ms(risk.last_operate_time))

        schema = self.provider.fetch_resource_type_schema()
        properties = schema.properties

        self.assertEqual(properties["event_time_timestamp"]["type"], "integer")
        self.assertEqual(properties["event_end_time_timestamp"]["type"], "integer")
        self.assertEqual(properties["last_operate_time_timestamp"]["type"], "integer")

    def test_handles_null_event_end_timestamp(self):
        strategy = self._create_strategy("strategy-null")
        event_time = timezone.now()

        risk = self._create_risk(
            risk_id="risk-null",
            raw_event_id="raw-null",
            strategy=strategy,
            event_time=event_time,
            event_end_time=None,
        )
        risk.refresh_from_db()

        now = timezone.now()
        start_ms = int((now - datetime.timedelta(hours=1)).timestamp() * 1000)
        end_ms = int((now + datetime.timedelta(hours=1)).timestamp() * 1000)

        result = self.provider.fetch_instance_list(FancyDict(start_time=start_ms, end_time=end_ms), Page(50, 0))
        item = next(data for data in result.results if data["id"] == risk.risk_id)
        payload = item["data"]

        self.assertIsNone(payload["event_end_time_timestamp"])
        self.assertEqual(payload["event_time_timestamp"], _ms(risk.event_time))
        self.assertEqual(payload["last_operate_time_timestamp"], _ms(risk.last_operate_time))


class ManualEventProviderAPITest(TestCase):
    def setUp(self):
        self._dummy_request = type("DummyRequest", (), {"headers": {}})()
        self.req_patcher = patch.object(
            ManualEventResourceProvider, "get_local_request", return_value=self._dummy_request
        )
        self.req_patcher.start()
        self.addCleanup(self.req_patcher.stop)
        self.provider = ManualEventResourceProvider()

    def _create_strategy(self, name: str) -> Strategy:
        return Strategy.objects.create(namespace=settings.DEFAULT_NAMESPACE, strategy_name=name)

    def _create_manual_event(
        self,
        *,
        raw_event_id: str,
        strategy: Strategy,
        event_time: datetime.datetime,
    ) -> ManualEvent:
        return ManualEvent.objects.create(
            raw_event_id=raw_event_id,
            strategy=strategy,
            event_time=event_time,
        )

    def test_list_fetch_search(self):
        strategy_a = self._create_strategy("manual-a")
        strategy_b = self._create_strategy("manual-b")
        event_time = timezone.now()
        event_a = self._create_manual_event(
            raw_event_id="manual-raw-A",
            strategy=strategy_a,
            event_time=event_time,
        )
        event_b = self._create_manual_event(
            raw_event_id="manual-raw-B",
            strategy=strategy_b,
            event_time=event_time,
        )
        page = Page(50, 0)
        lr = self.provider.list_instance(FancyDict(parent=None, search=None), page)
        expected = [
            {"id": str(event_a.manual_event_id), "display_name": event_a.raw_event_id},
            {"id": str(event_b.manual_event_id), "display_name": event_b.raw_event_id},
        ]
        self.assertEqual(lr.count, 2)
        self.assertEqual(sorted(lr.results, key=lambda x: x["id"]), sorted(expected, key=lambda x: x["id"]))

        lr_parent = self.provider.list_instance(
            FancyDict(parent={"id": str(strategy_a.strategy_id), "type": ResourceEnum.STRATEGY.id}, search=None),
            page,
        )
        self.assertEqual(lr_parent.count, 1)
        self.assertEqual(
            lr_parent.results, [{"id": str(event_a.manual_event_id), "display_name": event_a.raw_event_id}]
        )

        lr_fetch = self.provider.fetch_instance_info(
            FancyDict(ids=[str(event_a.manual_event_id), str(event_b.manual_event_id)])
        )
        self.assertEqual(lr_fetch.count, 2)

        lr_search = self.provider.search_instance(FancyDict(parent=None, keyword="manual-raw-A"), page)
        self.assertEqual(lr_search.count, 1)
        self.assertEqual(
            lr_search.results, [{"id": str(event_a.manual_event_id), "display_name": event_a.raw_event_id}]
        )

    def test_fetch_instance_list_returns_ms(self):
        strategy = self._create_strategy("manual-strategy")
        event_time = timezone.now().replace(microsecond=123000)
        event = self._create_manual_event(
            raw_event_id="manual-raw-1",
            strategy=strategy,
            event_time=event_time,
        )
        last_operate_time = event_time + datetime.timedelta(minutes=5)
        ManualEvent.objects.filter(pk=event.pk).update(last_operate_time=last_operate_time)
        event.refresh_from_db()

        now = timezone.now()
        start_ms = int((now - datetime.timedelta(hours=1)).timestamp() * 1000)
        end_ms = int((now + datetime.timedelta(hours=1)).timestamp() * 1000)

        result = self.provider.fetch_instance_list(FancyDict(start_time=start_ms, end_time=end_ms), Page(50, 0))
        self.assertGreaterEqual(result.count, 1)
        item = next(data for data in result.results if data["id"] == str(event.manual_event_id))
        payload = item["data"]
        self.assertEqual(payload["event_time_timestamp"], _ms(event.event_time))
        self.assertEqual(payload["last_operate_time_timestamp"], _ms(event.last_operate_time))

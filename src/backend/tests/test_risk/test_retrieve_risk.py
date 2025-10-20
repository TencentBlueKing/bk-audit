import datetime
from types import SimpleNamespace
from unittest import mock

from django.conf import settings
from django.db.models import Q
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from apps.meta.constants import ConfigLevelChoices
from apps.meta.models import GlobalMetaConfig
from apps.permission.handlers.actions import ActionEnum
from services.web.databus.constants import (
    ASSET_RISK_BKBASE_RT_ID_KEY,
    ASSET_STRATEGY_BKBASE_RT_ID_KEY,
    ASSET_STRATEGY_TAG_BKBASE_RT_ID_KEY,
    DORIS_EVENT_BKBASE_RT_ID_KEY,
)
from services.web.risk.constants import EventFilterOperator, RiskStatus
from services.web.risk.models import Risk, TicketPermission, UserType
from services.web.strategy_v2.constants import RiskLevel
from services.web.strategy_v2.models import Strategy
from tests.base import TestCase


class TestListRiskResource(TestCase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.username = "admin"
        self.authed_filter_patcher = mock.patch(
            "services.web.risk.models.Risk.authed_risk_filter", return_value=Q(), autospec=True
        )
        self.authed_filter_patcher.start()
        self.addCleanup(self.authed_filter_patcher.stop)

        self.bkbase_table_config = {
            ASSET_RISK_BKBASE_RT_ID_KEY: "bkdata.risk_rt",
            ASSET_STRATEGY_BKBASE_RT_ID_KEY: "bkdata.strategy_rt",
            ASSET_STRATEGY_TAG_BKBASE_RT_ID_KEY: "bkdata.strategy_tag_rt",
            DORIS_EVENT_BKBASE_RT_ID_KEY: "bkdata.event_rt",
        }
        for config_key, table_id in self.bkbase_table_config.items():
            GlobalMetaConfig.set(
                config_key=config_key,
                config_value=table_id,
                config_level=ConfigLevelChoices.NAMESPACE.value,
                instance_key=settings.DEFAULT_NAMESPACE,
            )

        self.addCleanup(
            lambda: GlobalMetaConfig.objects.filter(config_key__in=self.bkbase_table_config.keys()).delete()
        )

        self.strategy = Strategy.objects.create(
            namespace="default",
            strategy_name="strategy",
            risk_level=RiskLevel.HIGH.value,
            event_data_field_configs=[{"field_name": "ip", "display_name": "Source IP"}],
        )
        self.risk = Risk.objects.create(
            risk_id="risk-db",
            raw_event_id="raw",
            strategy=self.strategy,
            status=RiskStatus.NEW,
            event_time=datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc),
        )
        TicketPermission.objects.create(
            risk_id=self.risk.risk_id,
            action=ActionEnum.LIST_RISK.id,
            user=self.username,
            user_type=UserType.OPERATOR,
        )

    def _format_expected_table(self, table_id: str) -> str:
        parts = [part for part in table_id.split(".") if part]
        return ".".join(f"`{part}`" for part in parts)

    def _make_request(self, query=None):
        query = query or {"page": 1, "page_size": 10}
        django_request = self.factory.get("/risks/", data=query)
        django_request.user = SimpleNamespace(username=self.username, is_authenticated=True)
        request = Request(django_request)
        request.user = django_request.user
        return request

    def _call_resource(self, payload):
        request = self._make_request()
        data = self.resource.risk.list_risk(payload, _request=request)
        return data

    def test_list_risk_via_db(self):
        data = self._call_resource({"use_bkbase": False})
        results = data["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["risk_id"], self.risk.risk_id)

    def test_list_risk_via_db_with_event_filters(self):
        payload = {
            "use_bkbase": False,
            "event_filters": [
                {
                    "field": "ip",
                    "display_name": "Source IP",
                    "operator": EventFilterOperator.CONTAINS.value,
                    "value": "127.0.0.1",
                }
            ],
        }

        data = self._call_resource(payload)

        results = data["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["risk_id"], self.risk.risk_id)

    def test_list_risk_via_bkbase(self):
        sql_log = []

        def fake_query_sync(sql):
            sql_log.append(sql)
            if "COUNT" in sql.upper():
                return {"list": [{"count": 1}]}
            return {"list": [{"risk_id": self.risk.risk_id, "strategy_id": self.risk.strategy_id}]}

        with mock.patch("bk_resource.api.bk_base.query_sync", side_effect=fake_query_sync):
            data = self._call_resource({"use_bkbase": True})

        results = data["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["risk_id"], self.risk.risk_id)
        self.assertEqual(len(sql_log), 2)  # count + data

        risk_table = self.bkbase_table_config[ASSET_RISK_BKBASE_RT_ID_KEY]
        self.assertIn(risk_table, sql_log[0])
        self.assertIn(risk_table, sql_log[1])

    def test_list_risk_via_bkbase_with_event_filters(self):
        sql_log = []

        def fake_query_sync(sql):
            sql_log.append(sql)
            if "COUNT" in sql.upper():
                return {"list": [{"count": 1}]}
            return {"list": [{"risk_id": self.risk.risk_id, "strategy_id": self.risk.strategy_id}]}

        payload = {
            "use_bkbase": True,
            "event_filters": [
                {
                    "field": "ip",
                    "display_name": "Source IP",
                    "operator": EventFilterOperator.CONTAINS.value,
                    "value": "127.0.0.1",
                }
            ],
        }

        with mock.patch("bk_resource.api.bk_base.query_sync", side_effect=fake_query_sync):
            data = self._call_resource(payload)

        results = data["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["risk_id"], self.risk.risk_id)
        self.assertTrue(any("JSON_EXTRACT" in sql for sql in sql_log))
        self.assertTrue(any("risk_event_0.risk_id = base_query.risk_id" in sql for sql in sql_log))

        event_table = self._format_expected_table(self.bkbase_table_config[DORIS_EVENT_BKBASE_RT_ID_KEY])
        self.assertTrue(any(event_table in sql for sql in sql_log))

    def test_list_risk_via_bkbase_with_risk_level(self):
        sql_log = []

        def fake_query_sync(sql):
            sql_log.append(sql)
            if "COUNT" in sql.upper():
                return {"list": [{"count": 1}]}
            return {"list": [{"risk_id": self.risk.risk_id, "strategy_id": self.risk.strategy_id}]}

        payload = {
            "use_bkbase": True,
            "risk_level": RiskLevel.HIGH.value,
            "order_field": "risk_level",
            "order_type": "desc",
        }

        with mock.patch("bk_resource.api.bk_base.query_sync", side_effect=fake_query_sync):
            data = self._call_resource(payload)

        results = data["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["risk_id"], self.risk.risk_id)

        strategy_table = self.bkbase_table_config[ASSET_STRATEGY_BKBASE_RT_ID_KEY]
        self.assertTrue(any(strategy_table in sql for sql in sql_log))
        data_sql = sql_log[1]
        self.assertIn("CASE base_query.`strategy__risk_level`", data_sql)
        self.assertIn("base_query.`event_time` DESC", data_sql)

    def test_list_risk_event_filters_without_matching_strategy_field(self):
        Strategy.objects.create(
            namespace="default",
            strategy_name="other strategy",
            risk_level=RiskLevel.HIGH.value,
            event_data_field_configs=[{"field_name": "address", "display_name": "Address"}],
        )
        payload = {
            "use_bkbase": False,
            "event_filters": [
                {
                    "field": "unknown",
                    "display_name": "Unknown Field",
                    "operator": EventFilterOperator.CONTAINS.value,
                    "value": "value",
                },
            ],
        }

        data = self._call_resource(payload)

        self.assertEqual(len(data["results"]), 0)

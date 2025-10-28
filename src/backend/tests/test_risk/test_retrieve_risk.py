import datetime
from types import SimpleNamespace
from typing import List
from unittest import mock

import sqlglot
from django.conf import settings
from django.db.models import Q
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory
from sqlglot import errors as sqlglot_errors

from apps.meta.constants import ConfigLevelChoices
from apps.meta.models import GlobalMetaConfig
from apps.permission.handlers.actions import ActionEnum
from services.web.databus.constants import (
    ASSET_RISK_BKBASE_RT_ID_KEY,
    ASSET_STRATEGY_BKBASE_RT_ID_KEY,
    ASSET_STRATEGY_TAG_BKBASE_RT_ID_KEY,
    ASSET_TICKET_PERMISSION_BKBASE_RT_ID_KEY,
    DORIS_EVENT_BKBASE_RT_ID_KEY,
)
from services.web.risk.constants import EventFilterOperator, RiskStatus
from services.web.risk.models import Risk, TicketPermission, UserType
from services.web.risk.resources.risk import ListMineRisk, ListNoticingRisk
from services.web.strategy_v2.constants import RiskLevel
from services.web.strategy_v2.models import Strategy
from tests.base import TestCase


def assert_hive_sql(testcase: TestCase, sql_statements: List[str]) -> None:
    for statement in sql_statements:
        normalized = statement.replace("```", "`")
        try:
            sqlglot.parse_one(normalized, read="hive")
        except sqlglot_errors.ParseError as exc:
            testcase.fail(f"Hive SQL parse failed: {exc}\nSQL: {normalized}")
        except Exception as exc:  # pragma: no cover
            testcase.fail(f"Hive SQL parse raised unexpected error: {exc}\nSQL: {normalized}")


class TestListRiskResource(TestCase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.username = "admin"
        self.bkbase_title = "bkbase-title"
        self.authed_filter_patcher = mock.patch(
            "services.web.risk.models.Risk.authed_risk_filter", return_value=Q(), autospec=True
        )
        self.authed_filter_patcher.start()
        self.addCleanup(self.authed_filter_patcher.stop)

        self.bkbase_table_config = {
            ASSET_RISK_BKBASE_RT_ID_KEY: "bkdata.risk_rt",
            ASSET_STRATEGY_BKBASE_RT_ID_KEY: "bkdata.strategy_rt",
            ASSET_STRATEGY_TAG_BKBASE_RT_ID_KEY: "bkdata.strategy_tag_rt",
            ASSET_TICKET_PERMISSION_BKBASE_RT_ID_KEY: "bkdata.ticket_permission_rt",
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
            event_data_field_configs=[{"field_name": "ip", "display_name": "Source IP", "duplicate_field": False}],
        )
        self.risk = Risk.objects.create(
            risk_id="risk-db",
            raw_event_id="raw",
            strategy=self.strategy,
            status=RiskStatus.NEW,
            title=self.bkbase_title,
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
        if not parts:
            return ""
        if parts[-1].strip("`").lower() != "doris":
            parts[-1] = f"{parts[-1]}.doris"
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
        self.assertEqual(data["sql"], [])

    def test_list_risk_via_db_event_end_time_ceils_microseconds(self):
        target_end_time = self.risk.event_time + datetime.timedelta(seconds=59, microseconds=1)
        Risk.objects.filter(pk=self.risk.pk).update(event_end_time=target_end_time)

        data = self._call_resource({"use_bkbase": False})
        results = data["results"]

        self.assertEqual(len(results), 1)
        result = results[0]
        self.assertEqual(result["risk_id"], self.risk.risk_id)

        original_formatted = target_end_time.strftime("%Y-%m-%d %H:%M:%S")
        expected = target_end_time.replace(microsecond=0) + datetime.timedelta(seconds=1)
        expected_formatted = expected.strftime("%Y-%m-%d %H:%M:%S")

        self.assertEqual(result["event_end_time"], expected_formatted)
        self.assertNotEqual(result["event_end_time"], original_formatted)

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
        self.assertEqual(data["sql"], [])

    def test_list_risk_via_bkbase(self):
        sql_log = []

        def fake_query_sync(sql):
            sql_log.append(sql)
            print(sql)
            if "COUNT" in sql.upper():
                return {"list": [{"count": 1}]}
            return {"list": [{"risk_id": self.risk.risk_id, "strategy_id": self.risk.strategy_id}]}

        permission_q = Q(risk_id__in=TicketPermission.objects.filter(user=self.username).values("risk_id"))
        original_return = Risk.authed_risk_filter.return_value
        Risk.authed_risk_filter.return_value = permission_q
        try:
            with mock.patch("bk_resource.api.bk_base.query_sync", side_effect=fake_query_sync):
                data = self._call_resource({"use_bkbase": True, "title": "bkbase-title"})
        finally:
            Risk.authed_risk_filter.return_value = original_return

        results = data["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["risk_id"], self.risk.risk_id)
        self.assertEqual(len(sql_log), 2)  # count + data

        risk_table = f"{self.bkbase_table_config[ASSET_RISK_BKBASE_RT_ID_KEY]}.doris"
        self.assertIn(risk_table, sql_log[0])
        self.assertIn(risk_table, sql_log[1])
        ticket_table = f"{self.bkbase_table_config[ASSET_TICKET_PERMISSION_BKBASE_RT_ID_KEY]}.doris"
        self.assertTrue(any(ticket_table in sql for sql in sql_log))
        self.assertEqual(data["sql"], sql_log)
        assert_hive_sql(self, sql_log)

    def test_list_risk_via_bkbase_with_event_filters(self):
        sql_log = []

        def fake_query_sync(sql):
            sql_log.append(sql)
            print(sql)
            if "COUNT" in sql.upper():
                return {"list": [{"count": 1}]}
            return {"list": [{"risk_id": self.risk.risk_id, "strategy_id": self.risk.strategy_id}]}

        payload = {
            "use_bkbase": True,
            "title": "bkbase-title",
            "start_time": datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc).isoformat(),
            "end_time": datetime.datetime(2024, 1, 2, tzinfo=datetime.timezone.utc).isoformat(),
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
        normalized_sql = [sql.replace("`", "") for sql in sql_log]
        self.assertTrue(any(("JSON_EXTRACT" in sql) or ("GET_JSON_OBJECT" in sql) for sql in normalized_sql))
        self.assertTrue(any("risk_event_0.strategy_id = base_query.strategy_id" in sql for sql in normalized_sql))
        self.assertTrue(any("risk_event_0.raw_event_id = base_query.raw_event_id" in sql for sql in normalized_sql))
        self.assertTrue(any("risk_event_0.dteventtimestamp >=" in sql for sql in normalized_sql))
        self.assertTrue(
            any("COALESCE(base_query.event_end_time, base_query.event_time)" in sql for sql in normalized_sql)
        )
        self.assertTrue(any("risk_event_0.thedate >=" in sql for sql in normalized_sql))
        self.assertFalse(any("base_query.thedate" in sql for sql in normalized_sql))

        event_table = self._format_expected_table(self.bkbase_table_config[DORIS_EVENT_BKBASE_RT_ID_KEY]).replace(
            "`", ""
        )
        self.assertTrue(any(event_table in sql for sql in normalized_sql))
        self.assertEqual(data["sql"], sql_log)
        assert_hive_sql(self, sql_log)

    def test_list_risk_via_bkbase_with_numeric_event_filter(self):
        sql_log = []

        def fake_query_sync(sql):
            sql_log.append(sql)
            print(sql)
            if "COUNT" in sql.upper():
                return {"list": [{"count": 1}]}
            return {"list": [{"risk_id": self.risk.risk_id, "strategy_id": self.risk.strategy_id}]}

        payload = {
            "use_bkbase": True,
            "title": "bkbase-title",
            "event_filters": [
                {
                    "field": "ip",
                    "display_name": "Source IP",
                    "operator": EventFilterOperator.GREATER_THAN.value,
                    "value": "1.5",
                }
            ],
        }

        with mock.patch("bk_resource.api.bk_base.query_sync", side_effect=fake_query_sync):
            data = self._call_resource(payload)

        results = data["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["risk_id"], self.risk.risk_id)
        normalized_sql = [sql.replace("`", "") for sql in sql_log]
        combined_sql = " ".join(normalized_sql)
        self.assertIn("CAST(JSON_EXTRACT_STRING", combined_sql)
        self.assertIn("> 1.5", combined_sql)
        self.assertNotIn("> '1.5'", combined_sql)
        self.assertEqual(data["sql"], sql_log)
        assert_hive_sql(self, sql_log)

    def test_list_risk_via_bkbase_with_duplicate_field(self):
        sql_log = []
        self.strategy.event_data_field_configs = [
            {"field_name": "ip", "display_name": "Source IP", "duplicate_field": False},
            {"field_name": "user", "display_name": "User", "duplicate_field": True},
        ]
        self.strategy.save(update_fields=["event_data_field_configs"])

        def fake_query_sync(sql):
            sql_log.append(sql)
            print(sql)
            if "COUNT" in sql.upper():
                return {"list": [{"count": 1}]}
            return {"list": [{"risk_id": self.risk.risk_id, "strategy_id": self.risk.strategy_id}]}

        payload = {
            "use_bkbase": True,
            "title": "bkbase-title",
            # 期望：thedate 应加在 base 层（risk_event_0_base）
            "start_time": datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc).isoformat(),
            "end_time": datetime.datetime(2024, 1, 2, tzinfo=datetime.timezone.utc).isoformat(),
            "event_filters": [
                {
                    "field": "user",
                    "display_name": "User",
                    "operator": EventFilterOperator.EQUAL.value,
                    "value": "tester",
                },
                {
                    "field": "ip",
                    "display_name": "Source IP",
                    "operator": EventFilterOperator.EQUAL.value,
                    "value": "127.0.0.1",
                },
            ],
        }

        with mock.patch("bk_resource.api.bk_base.query_sync", side_effect=fake_query_sync):
            data = self._call_resource(payload)

        results = data["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["risk_id"], self.risk.risk_id)

        count_sql, data_sql = data["sql"]
        window_fragment = "ROW_NUMBER() OVER (PARTITION BY risk_event_0_base.strategy_id"
        self.assertIn(window_fragment, count_sql)
        self.assertIn("JSON_EXTRACT_STRING(risk_event_0_base.event_data, '$.user')", count_sql)
        self.assertIn("JSON_EXTRACT_STRING(risk_event_1.event_data, '$.ip')", count_sql)
        # thedate 应在 base 层过滤
        normalized_count_sql = count_sql.replace("`", "")
        self.assertIn("risk_event_0_base.thedate >=", normalized_count_sql)
        self.assertIn("risk_event_0_base.thedate <=", normalized_count_sql)
        self.assertIn(window_fragment, data_sql)
        self.assertIn("JSON_EXTRACT_STRING(risk_event_0_base.event_data, '$.user')", data_sql)
        self.assertIn("JSON_EXTRACT_STRING(risk_event_1.event_data, '$.ip')", data_sql)
        normalized_data_sql = data_sql.replace("`", "")
        self.assertIn("risk_event_0_base.thedate >=", normalized_data_sql)
        self.assertIn("risk_event_0_base.thedate <=", normalized_data_sql)
        assert_hive_sql(self, data["sql"])

    def test_list_risk_via_bkbase_with_duplicate_basic_field(self):
        sql_log = []
        self.strategy.event_data_field_configs = [
            {"field_name": "user", "display_name": "User", "duplicate_field": False}
        ]
        self.strategy.event_basic_field_configs = [
            {"field_name": "raw_event_id", "display_name": "Raw Event ID", "duplicate_field": True}
        ]
        self.strategy.save(update_fields=["event_data_field_configs", "event_basic_field_configs"])

        def fake_query_sync(sql):
            sql_log.append(sql)
            print(sql)
            if "COUNT" in sql.upper():
                return {"list": [{"count": 1}]}
            return {"list": [{"risk_id": self.risk.risk_id, "strategy_id": self.risk.strategy_id}]}

        payload = {
            "use_bkbase": True,
            "title": "bkbase-title",
            # 期望：thedate 应加在 base 层（risk_event_0_base）
            "start_time": datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc).isoformat(),
            "end_time": datetime.datetime(2024, 1, 2, tzinfo=datetime.timezone.utc).isoformat(),
            "event_filters": [
                {
                    "field": "user",
                    "display_name": "User",
                    "operator": EventFilterOperator.EQUAL.value,
                    "value": "tester",
                }
            ],
        }

        with mock.patch("bk_resource.api.bk_base.query_sync", side_effect=fake_query_sync):
            data = self._call_resource(payload)

        results = data["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["risk_id"], self.risk.risk_id)

        combined_sql = " ".join(sql_log)
        self.assertIn("ROW_NUMBER() OVER", combined_sql)
        self.assertIn("risk_event_0_base.raw_event_id", combined_sql)
        normalized_sql = combined_sql.replace("`", "")
        self.assertIn("risk_event_0_base.thedate >=", normalized_sql)
        self.assertIn("risk_event_0_base.thedate <=", normalized_sql)
        self.assertEqual(data["sql"], sql_log)
        assert_hive_sql(self, sql_log)

    def test_list_risk_via_bkbase_without_duplicate_fields(self):
        sql_log = []
        self.strategy.event_data_field_configs = [
            {"field_name": "user", "display_name": "User", "duplicate_field": False}
        ]
        self.strategy.event_basic_field_configs = [
            {"field_name": "raw_event_id", "display_name": "Raw Event ID", "duplicate_field": False}
        ]
        self.strategy.save(update_fields=["event_data_field_configs", "event_basic_field_configs"])

        def fake_query_sync(sql):
            sql_log.append(sql)
            print(sql)
            if "COUNT" in sql.upper():
                return {"list": [{"count": 1}]}
            return {"list": [{"risk_id": self.risk.risk_id, "strategy_id": self.risk.strategy_id}]}

        payload = {
            "use_bkbase": True,
            "title": "bkbase-title",
            # 无去重：thedate 应在 risk_event_0 基础子查询处
            "start_time": datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc).isoformat(),
            "end_time": datetime.datetime(2024, 1, 2, tzinfo=datetime.timezone.utc).isoformat(),
            "event_filters": [
                {
                    "field": "user",
                    "display_name": "User",
                    "operator": EventFilterOperator.EQUAL.value,
                    "value": "tester",
                }
            ],
        }

        with mock.patch("bk_resource.api.bk_base.query_sync", side_effect=fake_query_sync):
            data = self._call_resource(payload)

        results = data["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["risk_id"], self.risk.risk_id)

        combined_sql = " ".join(sql_log)
        self.assertNotIn("ROW_NUMBER() OVER", combined_sql)
        normalized_sql = combined_sql.replace("`", "")
        self.assertIn("risk_event_0.thedate >=", normalized_sql)
        self.assertIn("risk_event_0.thedate <=", normalized_sql)
        self.assertEqual(data["sql"], sql_log)
        assert_hive_sql(self, sql_log)

    def test_list_risk_via_bkbase_with_risk_level(self):
        sql_log = []

        def fake_query_sync(sql):
            sql_log.append(sql)
            print(sql)
            if "COUNT" in sql.upper():
                return {"list": [{"count": 1}]}
            return {"list": [{"risk_id": self.risk.risk_id, "strategy_id": self.risk.strategy_id}]}

        payload = {
            "use_bkbase": True,
            "title": "bkbase-title",
            "risk_level": RiskLevel.HIGH.value,
            "order_field": "risk_level",
            "order_type": "desc",
        }

        with mock.patch("bk_resource.api.bk_base.query_sync", side_effect=fake_query_sync):
            data = self._call_resource(payload)

        results = data["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["risk_id"], self.risk.risk_id)

        strategy_table = f"{self.bkbase_table_config[ASSET_STRATEGY_BKBASE_RT_ID_KEY]}.doris"
        self.assertTrue(any(strategy_table in sql for sql in sql_log))
        data_sql = sql_log[1]
        data_sql_normalized = data_sql.replace("`", "")
        self.assertIn("CASE WHEN base_query.strategy__risk_level", data_sql_normalized)
        self.assertIn("ELSE 99 END DESC", data_sql_normalized)
        self.assertIn("base_query.event_time DESC", data_sql_normalized)
        self.assertEqual(data["sql"], sql_log)
        assert_hive_sql(self, sql_log)

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
        self.assertEqual(data["sql"], [])

    def test_list_risk_via_bkbase_with_full_payload(self):
        sql_log: List[str] = []

        extra_risk = Risk.objects.create(
            risk_id="risk-bkbase-full",
            raw_event_id="raw-full",
            strategy=self.strategy,
            status=RiskStatus.NEW,
            title="bkbase-full-title",
            event_time=datetime.datetime(2025, 6, 1, tzinfo=datetime.timezone.utc),
        )
        TicketPermission.objects.create(
            risk_id=extra_risk.risk_id,
            action=ActionEnum.LIST_RISK.id,
            user=self.username,
            user_type=UserType.OPERATOR,
        )

        def fake_query_sync(sql):
            sql_log.append(sql)
            print(sql)
            if "COUNT" in sql.upper():
                return {"list": [{"count": 1}]}
            return {"list": [{"risk_id": extra_risk.risk_id, "strategy_id": extra_risk.strategy_id}]}

        payload = {
            "risk_id": "",
            "tags": "",
            "start_time": "2025-04-20 17:48:16",
            "end_time": "2025-10-20 17:48:16",
            "strategy_id": "",
            "operator": "",
            "status": "",
            "event_content": "",
            "risk_level": "",
            "title": "bkbase-full-title",
            "notice_users": "",
            "use_bkbase": True,
        }

        with mock.patch("bk_resource.api.bk_base.query_sync", side_effect=fake_query_sync):
            data = self._call_resource(payload)

        results = data["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["risk_id"], extra_risk.risk_id)
        self.assertEqual(len(sql_log), 2)
        combined_sql = " ".join(sql_log)
        self.assertIn("2025-04-20", combined_sql)
        self.assertIn("2025-10-20", combined_sql)
        self.assertEqual(data["sql"], sql_log)
        assert_hive_sql(self, sql_log)


class TestListMineAndNoticingRisk(TestCase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.username = "admin"
        self.bkbase_title = "bkbase-title"

        self.strategy = Strategy.objects.create(
            namespace="default",
            strategy_name="single-strategy",
            risk_level=RiskLevel.HIGH.value,
            event_data_field_configs=[{"field_name": "ip", "display_name": "Source IP"}],
        )

        self.risk_owned = Risk.objects.create(
            risk_id="risk-owned",
            raw_event_id="raw-owned",
            strategy=self.strategy,
            status=RiskStatus.NEW,
            title=self.bkbase_title,
            current_operator=[self.username],
            notice_users=[],
            event_time=datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc),
        )
        self.risk_noticed = Risk.objects.create(
            risk_id="risk-noticed",
            raw_event_id="raw-noticed",
            strategy=self.strategy,
            status=RiskStatus.NEW,
            title=self.bkbase_title,
            current_operator=[],
            notice_users=[self.username],
            event_time=datetime.datetime(2024, 1, 2, tzinfo=datetime.timezone.utc),
        )

        TicketPermission.objects.bulk_create(
            [
                TicketPermission(
                    risk_id=self.risk_owned.risk_id,
                    action=ActionEnum.LIST_RISK.id,
                    user=self.username,
                    user_type=UserType.OPERATOR,
                ),
                TicketPermission(
                    risk_id=self.risk_noticed.risk_id,
                    action=ActionEnum.LIST_RISK.id,
                    user=self.username,
                    user_type=UserType.NOTICE_USER,
                ),
            ]
        )

    def _make_request(self, path: str = "/risks/", query=None):
        query = query or {"page": 1, "page_size": 10}
        django_request = self.factory.get(path, data=query)
        django_request.user = SimpleNamespace(username=self.username, is_authenticated=True)
        request = Request(django_request)
        request.user = django_request.user
        return request

    def test_list_mine_risk(self):
        request = self._make_request()
        with mock.patch("services.web.risk.models.Risk.load_authed_risks", autospec=True) as mocked:
            mocked.return_value = Risk.annotated_queryset().filter(
                risk_id__in=[self.risk_owned.risk_id, self.risk_noticed.risk_id]
            )
            response = ListMineRisk().request({"page": 1, "page_size": 10}, _request=request)

        results = response["results"]
        risk_ids = {item["risk_id"] for item in results}
        self.assertIn(self.risk_owned.risk_id, risk_ids)
        self.assertNotIn(self.risk_noticed.risk_id, risk_ids)
        self.assertEqual(response["sql"], [])

    def test_list_mine_risk_via_bkbase(self):
        request = self._make_request()
        sql_log: List[str] = []

        def fake_query_sync(sql):
            sql_log.append(sql)
            print(sql)
            if "COUNT" in sql.upper():
                return {"list": [{"count": 1}]}
            return {"list": [{"risk_id": self.risk_owned.risk_id, "strategy_id": self.strategy.strategy_id}]}

        with mock.patch("services.web.risk.models.Risk.load_authed_risks", autospec=True) as mocked, mock.patch(
            "bk_resource.api.bk_base.query_sync", side_effect=fake_query_sync
        ):
            mocked.return_value = Risk.annotated_queryset().filter(risk_id=self.risk_owned.risk_id)
            response = ListMineRisk().request(
                {
                    "page": 1,
                    "page_size": 10,
                    "use_bkbase": True,
                    "title": "bkbase-title",
                    "start_time": datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc).isoformat(),
                    "end_time": datetime.datetime(2024, 1, 3, tzinfo=datetime.timezone.utc).isoformat(),
                },
                _request=request,
            )

        results = response["results"]
        self.assertEqual([item["risk_id"] for item in results], [self.risk_owned.risk_id])
        self.assertEqual(len(sql_log), 2)
        self.assertEqual(response["sql"], sql_log)
        assert_hive_sql(self, sql_log)

    def test_list_noticing_risk(self):
        request = self._make_request("/notice-risks/")
        with mock.patch("services.web.risk.models.Risk.load_authed_risks", autospec=True) as mocked:
            mocked.return_value = Risk.annotated_queryset().filter(
                risk_id__in=[self.risk_owned.risk_id, self.risk_noticed.risk_id]
            )
            response = ListNoticingRisk().request({"page": 1, "page_size": 10}, _request=request)

        results = response["results"]
        risk_ids = {item["risk_id"] for item in results}
        self.assertIn(self.risk_noticed.risk_id, risk_ids)
        self.assertNotIn(self.risk_owned.risk_id, risk_ids)
        self.assertEqual(response["sql"], [])

    def test_list_noticing_risk_via_bkbase(self):
        request = self._make_request("/notice-risks/")
        sql_log: List[str] = []

        def fake_query_sync(sql):
            sql_log.append(sql)
            print(sql)
            if "COUNT" in sql.upper():
                return {"list": [{"count": 1}]}
            return {"list": [{"risk_id": self.risk_noticed.risk_id, "strategy_id": self.strategy.strategy_id}]}

        with mock.patch("services.web.risk.models.Risk.load_authed_risks", autospec=True) as mocked, mock.patch(
            "bk_resource.api.bk_base.query_sync", side_effect=fake_query_sync
        ):
            mocked.return_value = Risk.annotated_queryset().filter(risk_id=self.risk_noticed.risk_id)
            response = ListNoticingRisk().request(
                {
                    "page": 1,
                    "page_size": 10,
                    "use_bkbase": True,
                    "title": "bkbase-title",
                    "start_time": datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc).isoformat(),
                    "end_time": datetime.datetime(2024, 1, 3, tzinfo=datetime.timezone.utc).isoformat(),
                },
                _request=request,
            )

        results = response["results"]
        self.assertEqual([item["risk_id"] for item in results], [self.risk_noticed.risk_id])
        self.assertEqual(len(sql_log), 2)
        self.assertEqual(response["sql"], sql_log)
        assert_hive_sql(self, sql_log)

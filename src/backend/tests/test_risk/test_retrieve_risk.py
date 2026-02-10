import datetime
import json
from types import SimpleNamespace
from typing import List
from unittest import mock

import sqlglot
from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from rest_framework.request import Request
from rest_framework.settings import api_settings
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
from services.web.risk.constants import (
    EventFilterOperator,
    RiskDisplayStatus,
    RiskStatus,
)
from services.web.risk.models import ManualEvent, Risk, TicketPermission, UserType
from services.web.risk.resources.risk import ListMineRisk
from services.web.risk.tasks import _sync_manual_event_status, _sync_manual_risk_status
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

        self.iam_filter_patcher = mock.patch(
            "services.web.risk.models.Risk.iam_risk_filter", return_value=Q(), autospec=True
        )
        self.iam_filter_patcher.start()
        self.addCleanup(self.iam_filter_patcher.stop)

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
        if timezone.is_naive(expected):
            expected = timezone.make_aware(expected, timezone.get_current_timezone())
        expected_localized = timezone.localtime(expected)
        expected_formatted = expected_localized.strftime("%Y-%m-%d %H:%M:%S")

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

        # ListRisk（所有风险）仅用 IAM 权限，需 mock iam_risk_filter 以限定结果集
        iam_q = Q(risk_id=self.risk.risk_id)
        with (
            mock.patch(
                "services.web.risk.models.Risk.iam_risk_filter",
                return_value=iam_q,
            ),
            mock.patch("bk_resource.api.bk_base.query_sync", side_effect=fake_query_sync),
        ):
            data = self._call_resource({"use_bkbase": True, "title": "bkbase-title"})

        results = data["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["risk_id"], self.risk.risk_id)
        self.assertEqual(len(sql_log), 2)  # count + data

        risk_table = f"{self.bkbase_table_config[ASSET_RISK_BKBASE_RT_ID_KEY]}.doris"
        self.assertIn(risk_table, sql_log[0])
        self.assertIn(risk_table, sql_log[1])
        # 所有风险为 IAM 仅用，不 join ticket_permission 表
        ticket_table = f"{self.bkbase_table_config[ASSET_TICKET_PERMISSION_BKBASE_RT_ID_KEY]}.doris"
        self.assertFalse(any(ticket_table in sql for sql in sql_log))
        event_table = f"{self.bkbase_table_config[DORIS_EVENT_BKBASE_RT_ID_KEY]}.doris"
        self.assertFalse(any(event_table in sql for sql in sql_log))
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
        self.assertTrue(any("matched_event.strategy_id = base_query.strategy_id" in sql for sql in normalized_sql))
        self.assertTrue(any("matched_event.raw_event_id = base_query.raw_event_id" in sql for sql in normalized_sql))
        self.assertTrue(any("matched_event.dteventtimestamp >=" in sql for sql in normalized_sql))
        self.assertTrue(any("base_query.event_end_time + INTERVAL 1 SECOND" in sql for sql in normalized_sql))
        self.assertTrue(any("matched_event_src_base.thedate >=" in sql for sql in normalized_sql))
        self.assertFalse(any("base_query.thedate" in sql for sql in normalized_sql))

        event_table = self._format_expected_table(self.bkbase_table_config[DORIS_EVENT_BKBASE_RT_ID_KEY]).replace(
            "`", ""
        )
        self.assertTrue(any(event_table in sql for sql in normalized_sql))
        self.assertEqual(data["sql"], sql_log)
        assert_hive_sql(self, sql_log)

    def test_list_risk_via_bkbase_returns_filtered_event_data(self):
        sql_log = []
        matched_event = {"ip": "127.0.0.1"}

        def fake_query_sync(sql):
            sql_log.append(sql)
            if "COUNT" in sql.upper():
                return {"list": [{"count": 1}]}
            return {
                "list": [
                    {
                        "risk_id": self.risk.risk_id,
                        "strategy_id": self.risk.strategy_id,
                        "raw_event_id": self.risk.raw_event_id,
                        "__matched_event_data": json.dumps(matched_event),
                    }
                ]
            }

        payload = {
            "use_bkbase": True,
            "title": "bkbase-title",
            "event_filters": [
                {
                    "field": "ip",
                    "display_name": "Source IP",
                    "operator": EventFilterOperator.EQUAL.value,
                    "value": "127.0.0.1",
                }
            ],
        }

        with mock.patch("bk_resource.api.bk_base.query_sync", side_effect=fake_query_sync):
            data = self._call_resource(payload)

        self.assertEqual(len(sql_log), 2)
        _, data_sql = sql_log
        self.assertIn("__matched_event_data", data_sql)
        assert_hive_sql(self, sql_log)

        results = data["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["risk_id"], self.risk.risk_id)
        self.assertEqual(results[0]["event_data"], matched_event)

    def test_list_risk_via_bkbase_order_by_event_data_field(self):
        sql_log = []

        def fake_query_sync(sql):
            sql_log.append(sql)
            if "COUNT" in sql.upper():
                return {"list": [{"count": 1}]}
            return {
                "list": [
                    {
                        "risk_id": self.risk.risk_id,
                        "strategy_id": self.risk.strategy_id,
                        "raw_event_id": self.risk.raw_event_id,
                        "__order_event_field": "192.168.0.1",
                        "__matched_event_data": json.dumps({"ip": "192.168.0.1"}),
                    }
                ]
            }

        payload = {
            "use_bkbase": True,
            "title": "bkbase-title",
            "order_field": "event_data.ip",
            "order_type": "desc",
            "event_filters": [
                {
                    "field": "ip",
                    "display_name": "Source IP",
                    "operator": EventFilterOperator.CONTAINS.value,
                    "value": "192.168",
                }
            ],
        }

        with mock.patch("bk_resource.api.bk_base.query_sync", side_effect=fake_query_sync):
            data = self._call_resource(payload)

        self.assertEqual(len(sql_log), 2)
        _, data_sql = sql_log
        normalized_sql = data_sql.replace("`", "")
        normalized_upper = normalized_sql.upper()
        self.assertIn("__ORDER_EVENT_FIELD", normalized_upper)
        self.assertIn("__MATCHED_EVENT_DATA", normalized_upper)
        self.assertIn("ORDER BY __ORDER_EVENT_FIELD DESC", normalized_upper)
        self.assertIn("MATCHED_EVENT.DTEVENTTIMESTAMP DESC", normalized_upper)
        assert_hive_sql(self, sql_log)

        results = data["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["risk_id"], self.risk.risk_id)

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
        window_fragment = "ROW_NUMBER() OVER (PARTITION BY matched_event_src_filtered.strategy_id"
        self.assertIn(window_fragment, count_sql)
        self.assertIn("JSON_EXTRACT_STRING(matched_event_src_filtered.event_data, '$.user')", count_sql)
        self.assertIn("JSON_EXTRACT_STRING(matched_event_src.event_data, '$.ip')", count_sql)
        # thedate 应在 base 层过滤
        normalized_count_sql = count_sql.replace("`", "")
        self.assertIn("matched_event_src_base.thedate >=", normalized_count_sql)
        self.assertIn("matched_event_src_base.thedate <=", normalized_count_sql)
        self.assertIn(window_fragment, data_sql)
        self.assertIn("JSON_EXTRACT_STRING(matched_event_src_filtered.event_data, '$.user')", data_sql)
        normalized_data_sql = data_sql.replace("`", "")
        self.assertIn("matched_event_src_base.thedate >=", normalized_data_sql)
        self.assertIn("matched_event_src_base.thedate <=", normalized_data_sql)
        assert_hive_sql(self, data["sql"])

    def test_list_risk_via_bkbase_with_duplicate_basic_field(self):
        sql_log = []
        self.strategy.event_data_field_configs = [
            {"field_name": "user", "display_name": "User", "duplicate_field": True}
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
        self.assertIn("matched_event_src_filtered.raw_event_id", combined_sql)
        normalized_sql = combined_sql.replace("`", "")
        self.assertIn("matched_event_src_base.thedate >=", normalized_sql)
        self.assertIn("matched_event_src_base.thedate <=", normalized_sql)
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
        self.assertIn("ROW_NUMBER() OVER", combined_sql)
        self.assertIn("COALESCE(matched_event_src_filtered.raw_event_id", combined_sql)
        normalized_sql = combined_sql.replace("`", "")
        self.assertIn("matched_event_src_base.thedate >=", normalized_sql)
        self.assertIn("matched_event_src_base.thedate <=", normalized_sql)
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
        self.assertIn("CASE WHEN base_query.risk_level", data_sql_normalized)
        self.assertIn("ELSE -1 END DESC", data_sql_normalized)
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
        event_table = f"{self.bkbase_table_config[DORIS_EVENT_BKBASE_RT_ID_KEY]}.doris"
        self.assertFalse(any(event_table in sql for sql in sql_log))
        self.assertEqual(data["sql"], sql_log)
        assert_hive_sql(self, sql_log)

    def test_list_risk_via_bkbase_with_display_status_filter(self):
        """传入具体 status 值时，BkBase SQL 中应包含 display_status 筛选条件"""
        # 创建一条 display_status=CLOSED 的风险
        closed_risk = Risk.objects.create(
            risk_id="risk-closed-display",
            raw_event_id="raw-closed",
            strategy=self.strategy,
            status=RiskStatus.CLOSED,
            display_status=RiskDisplayStatus.CLOSED,
            title=self.bkbase_title,
            event_time=datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc),
        )
        TicketPermission.objects.create(
            risk_id=closed_risk.risk_id,
            action=ActionEnum.LIST_RISK.id,
            user=self.username,
            user_type=UserType.OPERATOR,
        )
        sql_log: List[str] = []

        def fake_query_sync(sql):
            sql_log.append(sql)
            if "COUNT" in sql.upper():
                return {"list": [{"count": 1}]}
            return {"list": [{"risk_id": closed_risk.risk_id, "strategy_id": closed_risk.strategy_id}]}

        payload = {
            "use_bkbase": True,
            "status": RiskDisplayStatus.CLOSED,
        }

        with mock.patch("bk_resource.api.bk_base.query_sync", side_effect=fake_query_sync):
            data = self._call_resource(payload)

        results = data["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["risk_id"], closed_risk.risk_id)
        # 验证 BkBase SQL 中包含 display_status 筛选条件
        self.assertEqual(len(sql_log), 2)
        combined_sql = " ".join(sql_log).replace("`", "")
        self.assertIn("display_status", combined_sql)
        self.assertIn(RiskDisplayStatus.CLOSED, combined_sql)
        self.assertEqual(data["sql"], sql_log)
        assert_hive_sql(self, sql_log)

    def test_list_risk_via_db_with_display_status_filter(self):
        """DB 路径下传入 status 时，应通过 display_status 字段筛选"""
        # setUp 中的 risk 默认 display_status=NEW
        closed_risk = Risk.objects.create(
            risk_id="risk-closed-db",
            raw_event_id="raw-closed-db",
            strategy=self.strategy,
            status=RiskStatus.CLOSED,
            display_status=RiskDisplayStatus.CLOSED,
            title="closed-risk",
            event_time=datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc),
        )
        TicketPermission.objects.create(
            risk_id=closed_risk.risk_id,
            action=ActionEnum.LIST_RISK.id,
            user=self.username,
            user_type=UserType.OPERATOR,
        )

        # 传入 status=closed，应只返回 display_status=closed 的风险
        data = self._call_resource({"use_bkbase": False, "status": RiskDisplayStatus.CLOSED})
        results = data["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["risk_id"], closed_risk.risk_id)

        # 传入 status=new，应只返回 display_status=new 的风险（setUp 中的 risk）
        data = self._call_resource({"use_bkbase": False, "status": RiskDisplayStatus.NEW})
        results = data["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["risk_id"], self.risk.risk_id)

    def test_list_risk_via_bkbase_with_multiple_display_status(self):
        """传入多个 status 值时，BkBase SQL 中应包含多个 display_status 筛选条件"""
        sql_log: List[str] = []

        def fake_query_sync(sql):
            sql_log.append(sql)
            if "COUNT" in sql.upper():
                return {"list": [{"count": 1}]}
            return {"list": [{"risk_id": self.risk.risk_id, "strategy_id": self.risk.strategy_id}]}

        # 逗号分隔传入多个 status
        payload = {
            "use_bkbase": True,
            "status": f"{RiskDisplayStatus.NEW},{RiskDisplayStatus.CLOSED}",
        }

        with mock.patch("bk_resource.api.bk_base.query_sync", side_effect=fake_query_sync):
            self._call_resource(payload)

        self.assertEqual(len(sql_log), 2)
        combined_sql = " ".join(sql_log).replace("`", "")
        # 验证 SQL 中包含 display_status 筛选
        self.assertIn("display_status", combined_sql)
        self.assertIn(RiskDisplayStatus.NEW, combined_sql)
        self.assertIn(RiskDisplayStatus.CLOSED, combined_sql)
        assert_hive_sql(self, sql_log)

    def test_list_risk_via_bkbase_prioritizes_manual_unsynced(self):
        manual_risk = Risk.objects.create(
            risk_id="risk-manual-unsynced",
            raw_event_id="raw-manual",
            strategy=self.strategy,
            status=RiskStatus.NEW,
            title=self.bkbase_title,
            event_time=datetime.datetime(2023, 12, 31, tzinfo=datetime.timezone.utc),
            manual_synced=False,
        )
        sql_log: List[str] = []

        def fake_query_sync(sql):
            sql_log.append(sql)
            if "COUNT" in sql.upper():
                return {"list": [{"count": 1}]}
            return {"list": [{"risk_id": self.risk.risk_id, "strategy_id": self.risk.strategy_id}]}

        request_first = self._make_request({"page": 1, "page_size": 1})
        with mock.patch("bk_resource.api.bk_base.query_sync", side_effect=fake_query_sync):
            data = self.resource.risk.list_risk({"use_bkbase": True, "title": "bkbase-title"}, _request=request_first)

        self.assertEqual(data["total"], 2)
        self.assertEqual(data["num_pages"], 2)
        self.assertEqual([item["risk_id"] for item in data["results"]], [manual_risk.risk_id])
        self.assertEqual(data["results"][0]["status"], "stand_by")
        self.assertTrue(any("count" in sql.lower() for sql in data["sql"]))

        sql_log_second: List[str] = []

        def fake_query_sync_second(sql):
            sql_log_second.append(sql)
            if "COUNT" in sql.upper():
                return {"list": [{"count": 1}]}
            return {"list": [{"risk_id": self.risk.risk_id, "strategy_id": self.risk.strategy_id}]}

        request_second = self._make_request({"page": 2, "page_size": 1})
        with mock.patch("bk_resource.api.bk_base.query_sync", side_effect=fake_query_sync_second):
            data_second = self.resource.risk.list_risk(
                {"use_bkbase": True, "title": "bkbase-title"}, _request=request_second
            )

        self.assertEqual([item["risk_id"] for item in data_second["results"]], [self.risk.risk_id])
        self.assertEqual(data_second["total"], 2)
        self.assertEqual(data_second["num_pages"], 2)
        self.assertEqual(data_second["results"][0]["status"], RiskStatus.NEW)

    def test_list_risk_via_bkbase_prioritizes_manual_unsynced_with_event_filters(self):
        manual_risk = Risk.objects.create(
            risk_id="risk-manual-unsynced-event-filter",
            raw_event_id="raw-manual",
            strategy=self.strategy,
            status=RiskStatus.NEW,
            title=self.bkbase_title,
            event_time=datetime.datetime(2023, 12, 31, tzinfo=datetime.timezone.utc),
            manual_synced=False,
        )
        sql_log: List[str] = []

        def fake_query_sync(sql):
            sql_log.append(sql)
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
                    "operator": EventFilterOperator.CONTAINS.value,
                    "value": "127.0.0.1",
                }
            ],
        }

        request_first = self._make_request({"page": 1, "page_size": 1})
        with mock.patch("bk_resource.api.bk_base.query_sync", side_effect=fake_query_sync):
            data = self.resource.risk.list_risk(payload, _request=request_first)

        self.assertEqual([item["risk_id"] for item in data["results"]], [manual_risk.risk_id])
        self.assertEqual(data["results"][0]["status"], "stand_by")

        request_second = self._make_request({"page": 2, "page_size": 1})
        sql_log_second: List[str] = []

        def fake_query_sync_second(sql):
            sql_log_second.append(sql)
            if "COUNT" in sql.upper():
                return {"list": [{"count": 1}]}
            return {"list": [{"risk_id": self.risk.risk_id, "strategy_id": self.risk.strategy_id}]}

        with mock.patch("bk_resource.api.bk_base.query_sync", side_effect=fake_query_sync_second):
            data_second = self.resource.risk.list_risk(payload, _request=request_second)

        self.assertEqual([item["risk_id"] for item in data_second["results"]], [self.risk.risk_id])
        self.assertEqual(data_second["results"][0]["status"], RiskStatus.NEW)


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

        with mock.patch("bk_resource.api.bk_base.query_sync", side_effect=fake_query_sync):
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

    def test_list_mine_risk_no_perm_check(self):
        """ListMineRisk 不依赖 load_authed_risks，直接按 current_operator 查询"""
        request = self._make_request()
        response = ListMineRisk().request({"page": 1, "page_size": 10}, _request=request)
        results = response["results"]
        risk_ids = {item["risk_id"] for item in results}
        self.assertIn(self.risk_owned.risk_id, risk_ids)
        self.assertNotIn(self.risk_noticed.risk_id, risk_ids)

    def test_list_noticing_risk_no_perm_check(self):
        """ListNoticingRisk 不依赖 load_authed_risks，直接按 notice_users 查询"""
        from services.web.risk.resources.risk import ListNoticingRisk

        request = self._make_request()
        response = ListNoticingRisk().request({"page": 1, "page_size": 10}, _request=request)
        results = response["results"]
        risk_ids = {item["risk_id"] for item in results}
        self.assertIn(self.risk_noticed.risk_id, risk_ids)
        self.assertNotIn(self.risk_owned.risk_id, risk_ids)


class TestRetrieveRiskDetail(TestCase):
    def setUp(self):
        super().setUp()
        self.strategy = Strategy.objects.create(
            namespace="default",
            strategy_name="detail-strategy",
            risk_level=RiskLevel.MIDDLE.value,
        )
        self.risk = Risk.objects.create(
            risk_id="risk-detail",
            raw_event_id="raw-detail",
            strategy=self.strategy,
            status=RiskStatus.NEW,
            title="risk-detail-title",
            event_time=datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc),
            event_end_time=datetime.datetime(2024, 1, 2, tzinfo=datetime.timezone.utc),
        )
        self.search_event_patcher = mock.patch(
            "services.web.risk.resources.risk.EventHandler.search_event", return_value={"results": [], "total": 0}
        )
        self.search_event_mock = self.search_event_patcher.start()
        self.addCleanup(self.search_event_patcher.stop)

    def test_retrieve_risk_returns_unsynced_manual_events(self):
        in_range = ManualEvent.objects.create(
            raw_event_id=self.risk.raw_event_id,
            strategy=self.strategy,
            event_time=self.risk.event_time + datetime.timedelta(hours=1),
            manual_synced=False,
        )
        ManualEvent.objects.create(
            raw_event_id=self.risk.raw_event_id,
            strategy=self.strategy,
            event_time=self.risk.event_time - datetime.timedelta(days=1),
            manual_synced=False,
        )
        ManualEvent.objects.create(
            raw_event_id=self.risk.raw_event_id,
            strategy=self.strategy,
            event_time=self.risk.event_end_time + datetime.timedelta(minutes=1),
            manual_synced=False,
        )
        ManualEvent.objects.create(
            raw_event_id=self.risk.raw_event_id,
            strategy=self.strategy,
            event_time=self.risk.event_time + datetime.timedelta(minutes=30),
            manual_synced=True,
        )

        data = self.resource.risk.retrieve_risk({"risk_id": self.risk.risk_id})

        unsynced_ids = [item["manual_event_id"] for item in data.get("unsynced_events", [])]
        self.assertEqual(unsynced_ids, [in_range.manual_event_id])

    def test_retrieve_risk_without_end_time_returns_later_manual_events(self):
        open_risk = Risk.objects.create(
            risk_id="risk-open",
            raw_event_id="raw-open",
            strategy=self.strategy,
            status=RiskStatus.NEW,
            title="open-risk",
            event_time=datetime.datetime(2024, 2, 1, tzinfo=datetime.timezone.utc),
            event_end_time=None,
        )
        later_event = ManualEvent.objects.create(
            raw_event_id=open_risk.raw_event_id,
            strategy=self.strategy,
            event_time=open_risk.event_time + datetime.timedelta(hours=2),
            manual_synced=False,
        )
        ManualEvent.objects.create(
            raw_event_id=open_risk.raw_event_id,
            strategy=self.strategy,
            event_time=open_risk.event_time - datetime.timedelta(minutes=10),
            manual_synced=False,
        )

        data = self.resource.risk.retrieve_risk({"risk_id": open_risk.risk_id})
        unsynced_ids = [item["manual_event_id"] for item in data.get("unsynced_events", [])]
        self.assertEqual(unsynced_ids, [later_event.manual_event_id])

    def test_retrieve_risk_marks_manual_unsynced_as_standby(self):
        unsynced_risk = Risk.objects.create(
            risk_id="risk-manual-unsynced-status",
            raw_event_id="raw-manual-unsynced-status",
            strategy=self.strategy,
            status=RiskStatus.NEW,
            title="manual-unsynced-status",
            event_time=datetime.datetime(2024, 1, 3, tzinfo=datetime.timezone.utc),
            manual_synced=False,
        )

        data = self.resource.risk.retrieve_risk({"risk_id": unsynced_risk.risk_id})
        self.assertEqual(data["status"], "stand_by")

    def test_retrieve_risk_report_generating_when_lock_exists(self):
        """测试报告生成中时 report_generating 返回 True"""
        from django.core.cache import cache

        from services.web.risk.constants import RISK_RENDER_LOCK_KEY

        lock_key = RISK_RENDER_LOCK_KEY.format(risk_id=self.risk.risk_id)
        cache.set(lock_key, "task-uuid", timeout=60)
        try:
            data = self.resource.risk.retrieve_risk({"risk_id": self.risk.risk_id})
            self.assertTrue(data["report_generating"])
        finally:
            cache.delete(lock_key)

    def test_retrieve_risk_report_generating_when_no_lock(self):
        """测试无锁时 report_generating 返回 False"""
        from django.core.cache import cache

        from services.web.risk.constants import RISK_RENDER_LOCK_KEY

        lock_key = RISK_RENDER_LOCK_KEY.format(risk_id=self.risk.risk_id)
        cache.delete(lock_key)

        data = self.resource.risk.retrieve_risk({"risk_id": self.risk.risk_id})
        self.assertFalse(data["report_generating"])


class TestSyncManualRiskStatus(TestCase):
    def setUp(self):
        super().setUp()
        self.strategy = Strategy.objects.create(
            namespace="default",
            strategy_name="sync-manual-risk",
            risk_level=RiskLevel.MIDDLE.value,
        )
        GlobalMetaConfig.set(
            config_key=ASSET_RISK_BKBASE_RT_ID_KEY,
            config_value="bkdata.risk_rt",
            config_level=ConfigLevelChoices.NAMESPACE.value,
            instance_key=settings.DEFAULT_NAMESPACE,
        )
        self.addCleanup(lambda: GlobalMetaConfig.objects.filter(config_key=ASSET_RISK_BKBASE_RT_ID_KEY).delete())

    def test_sync_manual_risk_status_updates_flag(self):
        target = Risk.objects.create(
            risk_id="risk-unsynced",
            raw_event_id="raw-unsynced",
            strategy=self.strategy,
            status=RiskStatus.NEW,
            title="manual-unsynced",
            event_time=datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc),
            manual_synced=False,
        )
        untouched = Risk.objects.create(
            risk_id="risk-still-unsynced",
            raw_event_id="raw-still-unsynced",
            strategy=self.strategy,
            status=RiskStatus.NEW,
            title="manual-unsynced-2",
            event_time=datetime.datetime(2024, 1, 2, tzinfo=datetime.timezone.utc),
            manual_synced=False,
        )
        called_sql = {}

        def fake_query_sync(sql):
            called_sql["value"] = sql
            return {"list": [{"risk_id": target.risk_id}]}

        with mock.patch("bk_resource.api.bk_base.query_sync", side_effect=fake_query_sync):
            _sync_manual_risk_status(batch_size=10)

        self.assertTrue(Risk.objects.get(pk=target.pk).manual_synced)
        self.assertFalse(Risk.objects.get(pk=untouched.pk).manual_synced)
        self.assertIn(target.risk_id, called_sql.get("value", ""))


class TestSyncManualEventStatus(TestCase):
    def setUp(self):
        super().setUp()
        self.strategy = Strategy.objects.create(
            namespace="default",
            strategy_name="sync-manual-event",
            risk_level=RiskLevel.MIDDLE.value,
        )

    def test_sync_manual_event_status_updates_flag(self):
        event_time = datetime.datetime(2024, 1, 5, tzinfo=datetime.timezone.utc)
        manual_event = ManualEvent.objects.create(
            raw_event_id="raw-manual-event",
            strategy=self.strategy,
            event_time=event_time,
            manual_synced=False,
        )
        called_kwargs = {}

        def fake_search_event(**kwargs):
            called_kwargs["value"] = kwargs
            return {"results": [{"manual_event_id": manual_event.manual_event_id}], "total": 1}

        with mock.patch("services.web.risk.tasks.EventHandler.search_event", side_effect=fake_search_event):
            _sync_manual_event_status()

        manual_event.refresh_from_db()
        self.assertTrue(manual_event.manual_synced)
        window = datetime.timedelta(hours=1)
        expected_start = timezone.localtime(event_time - window).strftime(api_settings.DATETIME_FORMAT)
        expected_end = timezone.localtime(event_time + window).strftime(api_settings.DATETIME_FORMAT)
        self.assertEqual(called_kwargs["value"]["start_time"], expected_start)
        self.assertEqual(called_kwargs["value"]["end_time"], expected_end)
        self.assertEqual(called_kwargs["value"]["manual_event_id"], str(manual_event.manual_event_id))

    def test_sync_manual_event_status_skips_when_missing(self):
        manual_event = ManualEvent.objects.create(
            raw_event_id="raw-missing-event",
            strategy=self.strategy,
            event_time=datetime.datetime(2024, 2, 1, tzinfo=datetime.timezone.utc),
            manual_synced=False,
        )

        with mock.patch(
            "services.web.risk.tasks.EventHandler.search_event", return_value={"results": [], "total": 0}
        ) as search_event:
            _sync_manual_event_status()

        manual_event.refresh_from_db()
        self.assertFalse(manual_event.manual_synced)
        search_event.assert_called_once()

    def test_sync_manual_event_status_batch_query(self):
        event_time_a = datetime.datetime(2024, 3, 1, tzinfo=datetime.timezone.utc)
        event_time_b = datetime.datetime(2024, 3, 2, tzinfo=datetime.timezone.utc)
        manual_event_a = ManualEvent.objects.create(
            raw_event_id="raw-batch-event",
            strategy=self.strategy,
            event_time=event_time_a,
            manual_synced=False,
        )
        manual_event_b = ManualEvent.objects.create(
            raw_event_id="raw-batch-event",
            strategy=self.strategy,
            event_time=event_time_b,
            manual_synced=False,
        )
        called_kwargs = {}

        def fake_search_event(**kwargs):
            called_kwargs["value"] = kwargs
            return {"results": [{"manual_event_id": manual_event_a.manual_event_id}], "total": 1}

        with mock.patch("services.web.risk.tasks.EventHandler.search_event", side_effect=fake_search_event):
            _sync_manual_event_status()

        manual_event_a.refresh_from_db()
        manual_event_b.refresh_from_db()
        self.assertTrue(manual_event_a.manual_synced)
        self.assertFalse(manual_event_b.manual_synced)

        window = datetime.timedelta(hours=1)
        expected_start = min(
            timezone.localtime(event_time_a - window).strftime(api_settings.DATETIME_FORMAT),
            timezone.localtime(event_time_b - window).strftime(api_settings.DATETIME_FORMAT),
        )
        expected_end = max(
            timezone.localtime(event_time_a + window).strftime(api_settings.DATETIME_FORMAT),
            timezone.localtime(event_time_b + window).strftime(api_settings.DATETIME_FORMAT),
        )
        expected_ids = f"{manual_event_a.manual_event_id},{manual_event_b.manual_event_id}"

        self.assertEqual(called_kwargs["value"]["manual_event_id"], expected_ids)
        self.assertEqual(called_kwargs["value"]["start_time"], expected_start)
        self.assertEqual(called_kwargs["value"]["end_time"], expected_end)


class TestRiskPermissionFilters(TestCase):
    """测试 Risk 模型的三层权限过滤方法"""

    def setUp(self):
        super().setUp()
        self.strategy = Strategy.objects.create(
            strategy_id=301,
            strategy_name="perm-test-strategy",
            risk_level=RiskLevel.HIGH.value,
        )
        # 风险1：用户通过 TicketPermission 有权限（本地权限）
        self.risk_local = Risk.objects.create(
            risk_id="R-LOCAL",
            title="local-perm-risk",
            strategy=self.strategy,
            status=RiskStatus.NEW,
            event_time=datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc),
        )
        TicketPermission.objects.create(
            risk_id=self.risk_local.risk_id,
            action=ActionEnum.LIST_RISK.id,
            user="admin",
            user_type=UserType.OPERATOR,
        )
        # 风险2：用户通过 IAM 有权限（无 TicketPermission）
        self.risk_iam = Risk.objects.create(
            risk_id="R-IAM",
            title="iam-perm-risk",
            strategy=self.strategy,
            status=RiskStatus.NEW,
            event_time=datetime.datetime(2024, 1, 2, tzinfo=datetime.timezone.utc),
        )
        # 风险3：用户无任何权限
        self.risk_none = Risk.objects.create(
            risk_id="R-NONE",
            title="no-perm-risk",
            strategy=self.strategy,
            status=RiskStatus.NEW,
            event_time=datetime.datetime(2024, 1, 3, tzinfo=datetime.timezone.utc),
        )

    def _mock_iam_policies(self):
        """mock IAM 返回仅包含 R-IAM 的策略"""
        return Q(risk_id="R-IAM")

    @mock.patch("services.web.risk.models.RiskPathEqDjangoQuerySetConverter")
    @mock.patch("services.web.risk.models.Permission")
    def test_iam_risk_filter_only_returns_iam_risks(self, mock_perm_cls, mock_converter_cls):
        """iam_risk_filter 应仅返回 IAM 策略匹配的风险"""
        mock_perm = mock_perm_cls.return_value
        mock_perm.make_request.return_value = mock.MagicMock()
        mock_perm.iam_client._do_policy_query.return_value = {"some": "policy"}
        mock_converter_cls.return_value.convert.return_value = self._mock_iam_policies()

        q = Risk.iam_risk_filter(ActionEnum.LIST_RISK)
        risk_ids = set(Risk.objects.filter(q).values_list("risk_id", flat=True))

        self.assertIn("R-IAM", risk_ids)
        self.assertNotIn("R-LOCAL", risk_ids)
        self.assertNotIn("R-NONE", risk_ids)

    def test_local_risk_filter_only_returns_ticket_permission_risks(self):
        """local_risk_filter 应仅返回 TicketPermission 中有记录的风险"""
        q = Risk.local_risk_filter()
        risk_ids = set(Risk.objects.filter(q).values_list("risk_id", flat=True))

        self.assertIn("R-LOCAL", risk_ids)
        self.assertNotIn("R-IAM", risk_ids)
        self.assertNotIn("R-NONE", risk_ids)

    @mock.patch("services.web.risk.models.Permission")
    def test_iam_risk_filter_no_policies_returns_empty(self, mock_perm_cls):
        """IAM 无策略时应返回空集"""
        mock_perm = mock_perm_cls.return_value
        mock_perm.make_request.return_value = mock.MagicMock()
        mock_perm.iam_client._do_policy_query.return_value = None

        q = Risk.iam_risk_filter(ActionEnum.LIST_RISK)
        risk_ids = list(Risk.objects.filter(q).values_list("risk_id", flat=True))
        self.assertEqual(risk_ids, [])

    @mock.patch("services.web.risk.models.RiskPathEqDjangoQuerySetConverter")
    @mock.patch("services.web.risk.models.Permission")
    def test_load_iam_authed_risks_has_annotations(self, mock_perm_cls, mock_converter_cls):
        """load_iam_authed_risks 返回的 QuerySet 应保留 annotated_queryset 的注解字段"""
        mock_perm = mock_perm_cls.return_value
        mock_perm.make_request.return_value = mock.MagicMock()
        mock_perm.iam_client._do_policy_query.return_value = {"some": "policy"}
        mock_converter_cls.return_value.convert.return_value = self._mock_iam_policies()

        qs = Risk.load_iam_authed_risks(ActionEnum.LIST_RISK)
        risk = qs.first()
        self.assertTrue(hasattr(risk, "event_content_short"))
        self.assertTrue(hasattr(risk, "_has_report"))

    @mock.patch("services.web.risk.models.RiskPathEqDjangoQuerySetConverter")
    @mock.patch("services.web.risk.models.Permission")
    def test_load_authed_risks_backward_compatible(self, mock_perm_cls, mock_converter_cls):
        """load_authed_risks 应保持向后兼容，返回 IAM + TicketPermission 的并集"""
        mock_perm = mock_perm_cls.return_value
        mock_perm.make_request.return_value = mock.MagicMock()
        mock_perm.iam_client._do_policy_query.return_value = {"some": "policy"}
        mock_converter_cls.return_value.convert.return_value = self._mock_iam_policies()

        qs = Risk.load_authed_risks(ActionEnum.LIST_RISK)
        risk_ids = set(qs.values_list("risk_id", flat=True))

        self.assertIn("R-LOCAL", risk_ids)
        self.assertIn("R-IAM", risk_ids)
        self.assertNotIn("R-NONE", risk_ids)


class TestListProcessedRisk(TestCase):
    """处理历史接口：返回我曾作为处理人的风险，排除当前处理人包含我的"""

    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.username = "admin"
        self.strategy = Strategy.objects.create(
            strategy_id=404,
            strategy_name="processed-strategy",
            risk_level=RiskLevel.HIGH.value,
        )
        self.risk_past = Risk.objects.create(
            risk_id="R-PAST",
            title="past-processed",
            strategy=self.strategy,
            status=RiskStatus.CLOSED,
            display_status=RiskDisplayStatus.CLOSED,
            event_time=datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc),
            current_operator=[],
        )
        TicketPermission.objects.create(
            risk_id="R-PAST",
            action=ActionEnum.LIST_RISK.id,
            user=self.username,
            user_type=UserType.OPERATOR,
        )
        self.risk_current = Risk.objects.create(
            risk_id="R-CURRENT",
            title="current-processing",
            strategy=self.strategy,
            status=RiskStatus.AWAIT_PROCESS,
            display_status=RiskDisplayStatus.AWAIT_PROCESS,
            event_time=datetime.datetime(2024, 1, 2, tzinfo=datetime.timezone.utc),
            current_operator=[self.username],
        )
        TicketPermission.objects.create(
            risk_id="R-CURRENT",
            action=ActionEnum.LIST_RISK.id,
            user=self.username,
            user_type=UserType.OPERATOR,
        )
        self.risk_noticed = Risk.objects.create(
            risk_id="R-NOTICED",
            title="noticed-only",
            strategy=self.strategy,
            status=RiskStatus.NEW,
            display_status=RiskDisplayStatus.NEW,
            event_time=datetime.datetime(2024, 1, 3, tzinfo=datetime.timezone.utc),
            notice_users=[self.username],
        )
        TicketPermission.objects.create(
            risk_id="R-NOTICED",
            action=ActionEnum.LIST_RISK.id,
            user=self.username,
            user_type=UserType.NOTICE_USER,
        )
        self.risk_open = Risk.objects.create(
            risk_id="R-OPEN",
            title="open-past",
            strategy=self.strategy,
            status=RiskStatus.NEW,
            display_status=RiskDisplayStatus.NEW,
            event_time=datetime.datetime(2024, 1, 4, tzinfo=datetime.timezone.utc),
            current_operator=["someone_else"],
        )
        TicketPermission.objects.create(
            risk_id="R-OPEN",
            action=ActionEnum.LIST_RISK.id,
            user=self.username,
            user_type=UserType.OPERATOR,
        )
        # 低风险等级策略 + 风险，用于筛选测试
        self.strategy_low = Strategy.objects.create(
            strategy_id=405,
            strategy_name="processed-strategy-low",
            risk_level=RiskLevel.LOW.value,
        )
        self.risk_past_low = Risk.objects.create(
            risk_id="R-PAST-LOW",
            title="past-processed-low",
            strategy=self.strategy_low,
            status=RiskStatus.CLOSED,
            display_status=RiskDisplayStatus.CLOSED,
            event_time=datetime.datetime(2024, 1, 5, tzinfo=datetime.timezone.utc),
            current_operator=[],
        )
        TicketPermission.objects.create(
            risk_id="R-PAST-LOW",
            action=ActionEnum.LIST_RISK.id,
            user=self.username,
            user_type=UserType.OPERATOR,
        )

    def _make_request(self):
        django_request = self.factory.get("/risks/processed/", data={"page": 1, "page_size": 10})
        django_request.user = SimpleNamespace(username=self.username, is_authenticated=True)
        request = Request(django_request)
        request.user = django_request.user
        return request

    def test_list_processed_risk_returns_past_risks(self):
        from services.web.risk.resources.risk import ListProcessedRisk

        request = self._make_request()
        resp = ListProcessedRisk().request({"page": 1, "page_size": 10}, _request=request)
        risk_ids = {item["risk_id"] for item in resp["results"]}
        self.assertIn("R-PAST", risk_ids)
        self.assertIn("R-OPEN", risk_ids)
        self.assertNotIn("R-CURRENT", risk_ids)
        self.assertNotIn("R-NOTICED", risk_ids)

    def test_list_processed_risk_includes_closed(self):
        from services.web.risk.resources.risk import ListProcessedRisk

        request = self._make_request()
        resp = ListProcessedRisk().request({"page": 1, "page_size": 10}, _request=request)
        statuses = {item["risk_id"]: item["status"] for item in resp["results"]}
        self.assertIn("R-PAST", statuses)
        self.assertEqual(statuses["R-PAST"], RiskDisplayStatus.CLOSED)

    def test_list_processed_risk_with_risk_level_filter(self):
        """筛选参数与 TicketPermission 子查询 + exclude 组合正确工作"""
        from services.web.risk.resources.risk import ListProcessedRisk

        request = self._make_request()
        # 只筛选高风险：应返回 R-PAST 和 R-OPEN（高风险），不含 R-PAST-LOW（低风险）
        # 接口要求 risk_level 为字符串，serializer 会按逗号拆成列表
        resp = ListProcessedRisk().request(
            {"page": 1, "page_size": 10, "risk_level": RiskLevel.HIGH.value},
            _request=request,
        )
        risk_ids = {item["risk_id"] for item in resp["results"]}
        self.assertIn("R-PAST", risk_ids)
        self.assertIn("R-OPEN", risk_ids)
        self.assertNotIn("R-PAST-LOW", risk_ids)
        self.assertNotIn("R-CURRENT", risk_ids)

        # 只筛选低风险：应只返回 R-PAST-LOW
        resp = ListProcessedRisk().request(
            {"page": 1, "page_size": 10, "risk_level": RiskLevel.LOW.value},
            _request=request,
        )
        risk_ids = {item["risk_id"] for item in resp["results"]}
        self.assertEqual(risk_ids, {"R-PAST-LOW"})

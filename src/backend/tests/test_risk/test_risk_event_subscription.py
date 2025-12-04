# -*- coding: utf-8 -*-
from unittest import mock

from django.conf import settings
from django.core.exceptions import ValidationError

from apps.meta.constants import ConfigLevelChoices
from apps.meta.models import GlobalMetaConfig
from core.sql.constants import FieldType, FilterConnector, Operator
from core.sql.model import Condition, Field, WhereCondition
from services.web.databus.constants import (
    ASSET_RISK_BKBASE_RT_ID_KEY,
    ASSET_STRATEGY_BKBASE_RT_ID_KEY,
    ASSET_STRATEGY_TAG_BKBASE_RT_ID_KEY,
    DORIS_EVENT_BKBASE_RT_ID_KEY,
)
from services.web.risk.exceptions import RiskEventSubscriptionNotFound
from services.web.risk.handlers.subscription_sql import RiskEventSubscriptionSQLBuilder
from services.web.risk.models import RiskEventSubscription
from services.web.risk.serializers import RiskEventSubscriptionQuerySerializer
from tests.base import TestCase


class RiskEventSubscriptionTestMixin:
    """
    统一注入 BKBase 表配置，确保 SQL 输出可预测。
    """

    TIME_RANGE = (1000, 2000)

    def setUp(self):
        super().setUp()
        self.table_map = {
            ASSET_RISK_BKBASE_RT_ID_KEY: "test.asset_risk",
            ASSET_STRATEGY_BKBASE_RT_ID_KEY: "test.asset_strategy",
            ASSET_STRATEGY_TAG_BKBASE_RT_ID_KEY: "test.asset_strategy_tag",
            DORIS_EVENT_BKBASE_RT_ID_KEY: "test.event_rt",
        }
        for key, value in self.table_map.items():
            GlobalMetaConfig.set(
                config_key=key,
                config_value=value,
                config_level=ConfigLevelChoices.NAMESPACE.value,
                instance_key=settings.DEFAULT_NAMESPACE,
            )

    def tearDown(self):
        GlobalMetaConfig.objects.filter(config_key__in=self.table_map.keys()).delete()
        super().tearDown()

    # Helpers
    def _table(self, key: str) -> str:
        suffix = RiskEventSubscriptionSQLBuilder.STORAGE_SUFFIX
        return f"{self.table_map[key]}.{suffix}"

    def _column_specs(self):
        cls = RiskEventSubscriptionSQLBuilder
        return [
            (cls.EVENT_ALIAS, "dtEventTime", "dtEventTime"),
            (cls.EVENT_ALIAS, "dtEventTimeStamp", "dtEventTimeStamp"),
            (cls.EVENT_ALIAS, "event_id", "event_id"),
            (cls.EVENT_ALIAS, "event_content", "event_content"),
            (cls.EVENT_ALIAS, "raw_event_id", "raw_event_id"),
            (cls.EVENT_ALIAS, "strategy_id", "strategy_id"),
            (cls.EVENT_ALIAS, "event_evidence", "event_evidence"),
            (cls.EVENT_ALIAS, "event_type", "event_type"),
            (cls.EVENT_ALIAS, "event_data", "event_data"),
            (cls.EVENT_ALIAS, "event_time", "event_time"),
            (cls.EVENT_ALIAS, "event_source", "event_source"),
            (cls.EVENT_ALIAS, "operator", "event_operator"),
            (cls.RISK_ALIAS, "risk_id", "risk_id"),
            (cls.RISK_ALIAS, "event_end_time", "event_end_time"),
            (cls.RISK_ALIAS, "operator", "risk_operator"),
            (cls.RISK_ALIAS, "status", "risk_status"),
            (cls.RISK_ALIAS, "rule_id", "rule_id"),
            (cls.RISK_ALIAS, "rule_version", "rule_version"),
            (cls.RISK_ALIAS, "origin_operator", "origin_operator"),
            (cls.RISK_ALIAS, "current_operator", "current_operator"),
            (cls.RISK_ALIAS, "notice_users", "notice_users"),
            (cls.RISK_ALIAS, "risk_label", "risk_label"),
            (cls.RISK_ALIAS, "title", "risk_title"),
            (cls.STRATEGY_TAG_ALIAS, "tag_ids_json", "strategy_tag_ids"),
            (cls.STRATEGY_ALIAS, "risk_level", "risk_level"),
            (cls.STRATEGY_ALIAS, "is_formal", "is_formal"),
            (cls.STRATEGY_ALIAS, "status", "strategy_status"),
        ]

    def _outer_select_clause(self) -> str:
        alias = RiskEventSubscriptionSQLBuilder.OUTER_ALIAS
        return ",".join(f"`{alias}`.`{display}` `{display}`" for _, _, display in self._column_specs())

    def _inner_select_clause(self) -> str:
        return ",".join(f"`{table}`.`{raw}` `{alias}`" for table, raw, alias in self._column_specs())

    def _strategy_tag_subquery(self) -> str:
        table = self._table(ASSET_STRATEGY_TAG_BKBASE_RT_ID_KEY)
        return (
            "("
            "SELECT `strategy_id`,CONCAT('[',GROUP_CONCAT(CAST(`tag_id` AS STRING)),']') `tag_ids_json` "
            f"FROM {table} GROUP BY `strategy_id`"
            ")"
        )

    def _inner_query_sql(self) -> str:
        cls = RiskEventSubscriptionSQLBuilder
        event = self._table(DORIS_EVENT_BKBASE_RT_ID_KEY)
        risk = self._table(ASSET_RISK_BKBASE_RT_ID_KEY)
        strategy = self._table(ASSET_STRATEGY_BKBASE_RT_ID_KEY)
        subquery = self._strategy_tag_subquery()
        risk_join = (
            f"JOIN {risk} `{cls.RISK_ALIAS}` "
            "ON `e`.`strategy_id`=`r`.`strategy_id` "
            "AND `e`.`raw_event_id`=`r`.`raw_event_id` "
        )
        return (
            f"(SELECT {self._inner_select_clause()} "
            f"FROM {event} `{cls.EVENT_ALIAS}` "
            f"{risk_join}"
            f"JOIN {strategy} `{cls.STRATEGY_ALIAS}` ON `e`.`strategy_id`=`s`.`strategy_id` "
            f"LEFT JOIN {subquery} `{cls.STRATEGY_TAG_ALIAS}` ON `s`.`strategy_id`=`st`.`strategy_id` "
            f"WHERE `e`.`dtEventTimeStamp` BETWEEN {self.TIME_RANGE[0]} AND {self.TIME_RANGE[1]})"
        )

    def _expected_query_sql(self, limit: int = 10, where: str | None = None) -> str:
        outer = RiskEventSubscriptionSQLBuilder.OUTER_ALIAS
        base = f"SELECT {self._outer_select_clause()} FROM {self._inner_query_sql()} `{outer}`"
        if where:
            base += f" WHERE {where}"
        return f"{base} ORDER BY `{outer}`.`dtEventTimeStamp` DESC LIMIT {limit}"

    def _expected_count_sql(self, where: str | None = None) -> str:
        outer = RiskEventSubscriptionSQLBuilder.OUTER_ALIAS
        base = f"SELECT COUNT(`{outer}`.`raw_event_id`) `count` FROM {self._inner_query_sql()} `{outer}`"
        if where:
            base += f" WHERE {where}"
        return base


class TestRiskEventSubscriptionSQLBuilder(RiskEventSubscriptionTestMixin, TestCase):
    def test_build_sql_matches_expected_snapshot(self):
        """SQL builder 输出需与模板字符串完全一致。"""
        builder = RiskEventSubscriptionSQLBuilder(
            namespace=settings.DEFAULT_NAMESPACE,
            time_range=self.TIME_RANGE,
        )
        sql = builder.build_query_sql(limit=10, offset=0)
        self.assertEqual(sql, self._expected_query_sql())
        count_sql = builder.build_count_sql()
        self.assertEqual(count_sql, self._expected_count_sql())

    def test_json_contains_condition_in_sql(self):
        """带 JSON_CONTAINS 的订阅条件要在 SQL 中呈现完整函数。"""
        condition = WhereCondition(
            condition=Condition(
                field=Field(
                    table="st",
                    raw_name="tag_ids_json",
                    display_name="strategy_tag_ids",
                    field_type=FieldType.STRING,
                ),
                operator=Operator.JSON_CONTAINS,
                filter='["1"]',
            )
        )
        builder = RiskEventSubscriptionSQLBuilder(
            namespace=settings.DEFAULT_NAMESPACE,
            time_range=self.TIME_RANGE,
            subscription_condition=condition,
        )
        where = "JSON_CONTAINS(`t`.`strategy_tag_ids`,'[\"1\"]')"
        sql = builder.build_query_sql(limit=10, offset=0)
        self.assertEqual(sql, self._expected_query_sql(where=where))
        count_sql = builder.build_count_sql()
        self.assertEqual(count_sql, self._expected_count_sql(where=where))

    def test_multiple_conditions_rendered_in_where(self):
        """复合条件应在外层 WHERE 中按 AND 连接。"""
        condition = WhereCondition(
            connector=FilterConnector.AND,
            conditions=[
                WhereCondition(
                    condition=Condition(
                        field=Field(
                            table="r",
                            raw_name="status",
                            display_name="risk_status",
                            field_type=FieldType.STRING,
                        ),
                        operator=Operator.EQ,
                        filter="OPEN",
                    )
                ),
                WhereCondition(
                    condition=Condition(
                        field=Field(
                            table="s",
                            raw_name="risk_level",
                            display_name="risk_level",
                            field_type=FieldType.STRING,
                        ),
                        operator=Operator.EQ,
                        filter="HIGH",
                    )
                ),
            ],
        )
        builder = RiskEventSubscriptionSQLBuilder(
            namespace=settings.DEFAULT_NAMESPACE,
            time_range=self.TIME_RANGE,
            subscription_condition=condition,
        )
        where = "`t`.`risk_status`='OPEN' AND `t`.`risk_level`='HIGH'"
        sql = builder.build_query_sql(limit=5, offset=0)
        self.assertEqual(sql, self._expected_query_sql(limit=5, where=where))
        count_sql = builder.build_count_sql()
        self.assertEqual(count_sql, self._expected_count_sql(where=where))

    def test_or_connector_preserved(self):
        """OR 连接的筛选条件要保持原有逻辑。"""
        status_field = Field(
            table="r",
            raw_name="status",
            display_name="risk_status",
            field_type=FieldType.STRING,
        )
        condition = WhereCondition(
            connector=FilterConnector.OR,
            conditions=[
                WhereCondition(
                    condition=Condition(field=status_field, operator=Operator.EQ, filter="OPEN"),
                ),
                WhereCondition(
                    condition=Condition(field=status_field, operator=Operator.EQ, filter="NEW"),
                ),
            ],
        )
        builder = RiskEventSubscriptionSQLBuilder(
            namespace=settings.DEFAULT_NAMESPACE,
            time_range=self.TIME_RANGE,
            subscription_condition=condition,
        )
        where = "`t`.`risk_status`='OPEN' OR `t`.`risk_status`='NEW'"
        sql = builder.build_query_sql(limit=5, offset=0)
        self.assertEqual(sql, self._expected_query_sql(limit=5, where=where))
        count_sql = builder.build_count_sql()
        self.assertEqual(count_sql, self._expected_count_sql(where=where))

    def test_complex_mixed_conditions(self):
        """多层嵌套 AND/OR/JSON 应正确展开并保留括号。"""
        json_condition = WhereCondition(
            condition=Condition(
                field=Field(
                    table="st",
                    raw_name="tag_ids_json",
                    display_name="strategy_tag_ids",
                    field_type=FieldType.STRING,
                ),
                operator=Operator.JSON_CONTAINS,
                filter='["1"]',
            )
        )
        status_or = WhereCondition(
            connector=FilterConnector.OR,
            conditions=[
                WhereCondition(
                    condition=Condition(
                        field=Field(
                            table="r",
                            raw_name="status",
                            display_name="risk_status",
                            field_type=FieldType.STRING,
                        ),
                        operator=Operator.EQ,
                        filter="OPEN",
                    )
                ),
                WhereCondition(
                    condition=Condition(
                        field=Field(
                            table="r",
                            raw_name="status",
                            display_name="risk_status",
                            field_type=FieldType.STRING,
                        ),
                        operator=Operator.EQ,
                        filter="NEW",
                    )
                ),
            ],
        )
        risk_level = WhereCondition(
            condition=Condition(
                field=Field(
                    table="s",
                    raw_name="risk_level",
                    display_name="risk_level",
                    field_type=FieldType.STRING,
                ),
                operator=Operator.EQ,
                filter="HIGH",
            )
        )
        condition = WhereCondition(
            connector=FilterConnector.AND,
            conditions=[json_condition, status_or, risk_level],
        )
        builder = RiskEventSubscriptionSQLBuilder(
            namespace=settings.DEFAULT_NAMESPACE,
            time_range=self.TIME_RANGE,
            subscription_condition=condition,
        )
        where = (
            "JSON_CONTAINS(`t`.`strategy_tag_ids`,'[\"1\"]') AND "
            "(`t`.`risk_status`='OPEN' OR `t`.`risk_status`='NEW') AND "
            "`t`.`risk_level`='HIGH'"
        )
        sql = builder.build_query_sql(limit=5, offset=0)
        self.assertEqual(sql, self._expected_query_sql(limit=5, where=where))
        count_sql = builder.build_count_sql()
        self.assertEqual(count_sql, self._expected_count_sql(where=where))

    def test_event_data_drilldown_generates_json_extract(self):
        """event_data 下钻应使用 Doris JSON_EXTRACT 函数。"""
        condition = WhereCondition(
            condition=Condition(
                field=Field(
                    table="t",
                    raw_name="event_data",
                    display_name="event_data",
                    field_type=FieldType.STRING,
                    keys=["login", "ip"],
                ),
                operator=Operator.EQ,
                filter="127.0.0.1",
            )
        )
        builder = RiskEventSubscriptionSQLBuilder(
            namespace=settings.DEFAULT_NAMESPACE,
            time_range=self.TIME_RANGE,
            subscription_condition=condition,
        )
        where = "JSON_EXTRACT_STRING(`t`.`event_data`,'$.login.ip')='127.0.0.1'"
        sql = builder.build_query_sql(limit=5, offset=0)
        self.assertEqual(sql, self._expected_query_sql(limit=5, where=where))
        count_sql = builder.build_count_sql()
        self.assertEqual(count_sql, self._expected_count_sql(where=where))

    def test_event_data_drilldown_numeric_type(self):
        """自定义返回类型为 long 时应生成 JSON_EXTRACT_LARGEINT 并进行整型比较。"""
        condition = WhereCondition(
            condition=Condition(
                field=Field(
                    table="t",
                    raw_name="event_data",
                    display_name="event_data",
                    field_type=FieldType.LONG,
                    keys=["metric", "value"],
                ),
                operator=Operator.GTE,
                filter=100,
            )
        )
        builder = RiskEventSubscriptionSQLBuilder(
            namespace=settings.DEFAULT_NAMESPACE,
            time_range=self.TIME_RANGE,
            subscription_condition=condition,
        )
        where = "CAST(JSON_EXTRACT_STRING(`t`.`event_data`,'$.metric.value') AS BIGINT)>=100"
        sql = builder.build_query_sql(limit=5, offset=0)
        self.assertEqual(sql, self._expected_query_sql(limit=5, where=where))
        count_sql = builder.build_count_sql()
        self.assertEqual(count_sql, self._expected_count_sql(where=where))


class TestRiskEventSubscriptionResource(RiskEventSubscriptionTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.subscription = RiskEventSubscription.objects.create(name="test")

    def test_query_subscription_returns_full_payload(self):
        """资源层应返回完整的分页数据与 SQL，并正确构造 bulk 请求。"""
        payload = {
            "token": self.subscription.token,
            "start_time": self.TIME_RANGE[0],
            "end_time": self.TIME_RANGE[1],
            "page": 1,
            "page_size": 10,
        }

        mocked_resp = [{"list": [{"event_id": "e1"}]}, {"list": [{"count": 1}]}]
        with mock.patch(
            "bk_resource.api.bk_base.query_sync.bulk_request",
            return_value=mocked_resp,
        ) as bulk:
            data = self.resource.risk.query_risk_event_subscription(payload)

        expected_request = [
            {"sql": self._expected_query_sql()},
            {"sql": self._expected_count_sql()},
        ]
        bulk.assert_called_once_with(expected_request)
        expected_response = {
            "page": 1,
            "page_size": 10,
            "total": 1,
            "results": [{"event_id": "e1"}],
            "query_sql": self._expected_query_sql(),
            "count_sql": self._expected_count_sql(),
        }
        self.assertEqual(data, expected_response)

    def test_query_subscription_with_condition(self):
        """订阅条件应透传到资源层 SQL 中。"""
        condition = WhereCondition(
            condition=Condition(
                field=Field(
                    table="st",
                    raw_name="tag_ids_json",
                    display_name="strategy_tag_ids",
                    field_type=FieldType.STRING,
                ),
                operator=Operator.JSON_CONTAINS,
                filter='["1"]',
            )
        )
        self.subscription.set_where_condition(condition)
        self.subscription.save()
        payload = {
            "token": self.subscription.token,
            "start_time": self.TIME_RANGE[0],
            "end_time": self.TIME_RANGE[1],
            "page": 1,
            "page_size": 10,
        }

        mocked_resp = [{"list": [{"event_id": "e1"}]}, {"list": [{"count": 1}]}]
        with mock.patch(
            "bk_resource.api.bk_base.query_sync.bulk_request",
            return_value=mocked_resp,
        ) as bulk:
            data = self.resource.risk.query_risk_event_subscription(payload)

        where = "JSON_CONTAINS(`t`.`strategy_tag_ids`,'[\"1\"]')"
        expected_request = [
            {"sql": self._expected_query_sql(where=where)},
            {"sql": self._expected_count_sql(where=where)},
        ]
        bulk.assert_called_once_with(expected_request)
        self.assertEqual(data["query_sql"], self._expected_query_sql(where=where))
        self.assertEqual(data["count_sql"], self._expected_count_sql(where=where))

    def test_query_subscription_not_found(self):
        """不存在或关闭的 token 需抛出 RiskEventSubscriptionNotFound。"""
        payload = {
            "token": "invalid-token",
            "start_time": self.TIME_RANGE[0],
            "end_time": self.TIME_RANGE[1],
            "page": 1,
            "page_size": 10,
        }
        with self.assertRaises(RiskEventSubscriptionNotFound):
            self.resource.risk.query_risk_event_subscription(payload)


class TestRiskEventSubscriptionModel(TestCase):
    def test_condition_round_trip(self):
        """set/get_where_condition 应保持 Pydantic 结构一致。"""
        where = WhereCondition(
            condition=Condition(
                field=Field(table="e", raw_name="strategy_id", display_name="strategy_id", field_type=FieldType.LONG),
                operator=Operator.GTE,
                filter=100,
            )
        )
        sub = RiskEventSubscription.objects.create(name="round-trip")
        sub.set_where_condition(where)
        sub.save()
        loaded = RiskEventSubscription.objects.get(pk=sub.pk).get_where_condition()
        self.assertEqual(loaded.dict(), where.dict())

    def test_validate_condition_dict_invalid(self):
        """无效 condition 需抛出 DjangoValidationError，并含可读错误信息。"""
        invalid_condition = {"condition": {"field": "invalid"}}
        with self.assertRaises(ValidationError):
            RiskEventSubscription.validate_condition_dict(invalid_condition)

    def test_validate_condition_dict_invalid_json_path(self):
        """JSON path 不是合法字符串列表时需报错。"""
        invalid_condition = {
            "condition": {
                "field": {
                    "table": "t",
                    "raw_name": "event_data",
                    "display_name": "event_data",
                    "keys": ["login", ""],
                },
                "operator": Operator.EQ,
                "filter": "value",
            }
        }
        with self.assertRaises(ValidationError):
            RiskEventSubscription.validate_condition_dict(invalid_condition)

    def test_validate_condition_dict_preserves_field_type(self):
        """携带 JSON path 时字段类型应被正确解析。"""
        condition = {
            "condition": {
                "field": {
                    "table": "t",
                    "raw_name": "event_data",
                    "display_name": "event_data",
                    "keys": ["login", "ip"],
                    "field_type": FieldType.STRING.value,
                },
                "operator": Operator.EQ,
                "filter": "127.0.0.1",
            }
        }
        parsed = RiskEventSubscription.validate_condition_dict(condition)
        self.assertEqual(parsed.condition.field.field_type, FieldType.STRING)


class TestRiskEventSubscriptionSerializer(TestCase):
    def test_time_range_validation(self):
        """Serializer 在开始时间大于结束时间时需报 params_error。"""
        serializer = RiskEventSubscriptionQuerySerializer(
            data={"token": "t", "start_time": 2000, "end_time": 1000, "page": 1, "page_size": 10}
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("params_error", serializer.errors)

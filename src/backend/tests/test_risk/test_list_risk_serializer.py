# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
Copyright (C) 2023 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at https://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

import datetime
from unittest import mock

from django.test import SimpleTestCase
from django.utils import timezone
from rest_framework import serializers
from sqlglot import exp

from services.web.risk.constants import (
    EventFilterOperator,
    RiskDisplayStatus,
    RiskStatus,
)
from services.web.risk.converter.bkbase import (
    BkBaseFieldResolver,
    BkBaseQueryComponentsBuilder,
    FinalSelectAssembler,
)
from services.web.risk.models import Risk
from services.web.risk.serializers import (
    ListRiskRequestSerializer,
    ListRiskResponseSerializer,
    RiskInfoSerializer,
)
from services.web.strategy_v2.models import Strategy


class TestListRiskResponseSerializer(SimpleTestCase):
    def setUp(self):
        super().setUp()
        self.strategy = Strategy(strategy_id=1, namespace="test", strategy_name="测试策略")
        self.strategy.prefetched_tags = []

    def create_risk(
        self,
        *,
        risk_id: str,
        event_end_time: datetime.datetime | None,
        display_status: str = RiskDisplayStatus.NEW,
        status: str = RiskStatus.NEW,
        manual_synced: bool = True,
    ) -> Risk:
        risk = Risk(
            risk_id=risk_id,
            raw_event_id=f"raw_{risk_id}",
            strategy=self.strategy,
            event_time=datetime.datetime(2024, 1, 1, 0, 0, 0),
            event_end_time=event_end_time,
            display_status=display_status,
            status=status,
            manual_synced=manual_synced,
        )
        risk.event_content_short = ""
        return risk

    def _expected_output(self, dt: datetime.datetime | None) -> str | None:
        if dt is None:
            return None

        normalized = dt
        if normalized.microsecond > 0:
            normalized = normalized.replace(microsecond=0) + datetime.timedelta(seconds=1)

        if timezone.is_naive(normalized):
            normalized = timezone.make_aware(normalized, timezone.get_current_timezone())

        normalized = timezone.localtime(normalized)

        return normalized.strftime("%Y-%m-%d %H:%M:%S")

    def test_event_end_time_rounds_up_when_microseconds_present(self):
        risk = self.create_risk(
            risk_id="risk_round",
            event_end_time=datetime.datetime(2024, 1, 1, 0, 0, 59, 999999),
        )

        serialized = ListRiskResponseSerializer(instance=risk).data
        expected = self._expected_output(datetime.datetime(2024, 1, 1, 0, 0, 59, 999999))
        self.assertEqual(serialized["event_end_time"], expected)

    def test_event_end_time_keeps_original_when_already_rounded(self):
        risk = self.create_risk(
            risk_id="risk_exact",
            event_end_time=datetime.datetime(2024, 1, 1, 0, 0, 59),
        )

        serialized = ListRiskResponseSerializer(instance=risk).data

        expected = self._expected_output(datetime.datetime(2024, 1, 1, 0, 0, 59))
        self.assertEqual(serialized["event_end_time"], expected)

    def test_event_end_time_none_returns_none(self):
        risk = self.create_risk(risk_id="risk_none", event_end_time=None)

        serialized = ListRiskResponseSerializer(instance=risk).data

        self.assertIsNone(serialized["event_end_time"])

    def test_event_end_time_timezone_conversion_preserves_round_up(self):
        aware_end_time = datetime.datetime(2024, 1, 1, 0, 0, 59, 999999, tzinfo=datetime.timezone.utc)
        risk = self.create_risk(risk_id="risk_tz", event_end_time=aware_end_time)

        serialized = ListRiskResponseSerializer(instance=risk).data

        expected = self._expected_output(aware_end_time)
        self.assertEqual(serialized["event_end_time"], expected)

    def test_event_data_prefers_filtered_event_data(self):
        risk = self.create_risk(risk_id="risk_data", event_end_time=None)
        risk.event_data = {"from": "model"}
        risk.filtered_event_data = {"from": "filtered"}

        serialized = ListRiskResponseSerializer(instance=risk).data

        self.assertEqual(serialized["event_data"], {"from": "filtered"})

    # ---- display_status → status 映射测试 ----

    def test_status_field_uses_display_status_value(self):
        """正常映射：序列化后 status 字段取自 display_status"""
        risk = self.create_risk(
            risk_id="risk_ds_normal",
            event_end_time=None,
            display_status=RiskDisplayStatus.PROCESSING,
            status=RiskStatus.AWAIT_PROCESS,
        )

        serialized = ListRiskResponseSerializer(instance=risk).data

        # status 应为 display_status 的值，而非原始 status
        self.assertEqual(serialized["status"], RiskDisplayStatus.PROCESSING.value)
        # display_status 字段应被 pop 掉，不暴露给前端
        self.assertNotIn("display_status", serialized)

    def test_status_field_shows_stand_by_when_manual_unsynced(self):
        """manual_synced=False 优先级：即使 display_status 有值，status 也应为 stand_by"""
        risk = self.create_risk(
            risk_id="risk_ds_standby",
            event_end_time=None,
            display_status=RiskDisplayStatus.AWAIT_PROCESS,
            status=RiskStatus.AWAIT_PROCESS,
            manual_synced=False,
        )

        serialized = ListRiskResponseSerializer(instance=risk).data

        self.assertEqual(serialized["status"], RiskDisplayStatus.STAND_BY.value)
        self.assertNotIn("display_status", serialized)

    def test_status_field_maps_all_display_status_values(self):
        """验证所有 RiskDisplayStatus 枚举值都能正确映射（STAND_BY 除外，它由 manual_synced 控制）"""
        for ds in RiskDisplayStatus:
            if ds == RiskDisplayStatus.STAND_BY:
                continue
            risk = self.create_risk(
                risk_id=f"risk_ds_{ds.value}",
                event_end_time=None,
                display_status=ds,
            )
            serialized = ListRiskResponseSerializer(instance=risk).data
            self.assertEqual(
                serialized["status"],
                ds.value,
                f"display_status={ds.value} 应映射为 status={ds.value}",
            )
            self.assertNotIn("display_status", serialized)

    def test_risk_info_serializer_status_uses_display_status(self):
        """RiskInfoSerializer 与 ListRiskResponseSerializer 使用相同的 to_representation 映射逻辑"""
        risk = self.create_risk(
            risk_id="risk_info_ds",
            event_end_time=None,
            display_status=RiskDisplayStatus.FOR_APPROVE,
            status=RiskStatus.FOR_APPROVE,
        )

        # RiskInfoSerializer 包含多个会触发 DB 查询的字段（tags, report 等）
        # 我们只需测试 to_representation 中 display_status 的映射逻辑
        base_data = {"status": RiskStatus.FOR_APPROVE, "display_status": RiskDisplayStatus.FOR_APPROVE}
        with mock.patch.object(serializers.ModelSerializer, "to_representation", return_value=dict(base_data)):
            serializer = RiskInfoSerializer(instance=risk)
            serialized = serializer.to_representation(risk)

        self.assertEqual(serialized["status"], RiskDisplayStatus.FOR_APPROVE.value)
        self.assertNotIn("display_status", serialized)

    def test_risk_info_serializer_stand_by_when_manual_unsynced(self):
        """RiskInfoSerializer: manual_synced=False 时 status 为 stand_by"""
        risk = self.create_risk(
            risk_id="risk_info_standby",
            event_end_time=None,
            display_status=RiskDisplayStatus.NEW,
            status=RiskStatus.NEW,
            manual_synced=False,
        )

        base_data = {"status": RiskStatus.NEW, "display_status": RiskDisplayStatus.NEW}
        with mock.patch.object(serializers.ModelSerializer, "to_representation", return_value=dict(base_data)):
            serializer = RiskInfoSerializer(instance=risk)
            serialized = serializer.to_representation(risk)

        self.assertEqual(serialized["status"], RiskDisplayStatus.STAND_BY.value)
        self.assertNotIn("display_status", serialized)


class TestListRiskRequestSerializer(SimpleTestCase):
    def test_event_data_order_requires_matching_filter(self):
        serializer = ListRiskRequestSerializer(
            data={
                "order_field": "event_data.ip",
                "event_filters": [
                    {
                        "field": "other",
                        "display_name": "其他",
                        "operator": EventFilterOperator.EQUAL.value,
                        "value": "x",
                    }
                ],
            }
        )

        self.assertFalse(serializer.is_valid())
        error_text = str(serializer.errors)
        self.assertIn("关联事件字段排序需在筛选条件中包含字段", error_text)

    def test_event_data_order_passes_with_matching_filter(self):
        serializer = ListRiskRequestSerializer(
            data={
                "order_field": "-event_data.ip",
                "event_filters": [
                    {
                        "field": "ip",
                        "display_name": "IP",
                        "operator": EventFilterOperator.EQUAL.value,
                        "value": "1.1.1.1",
                    }
                ],
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["order_field"], "-event_data.ip")

    # ---- status → display_status 映射测试 ----

    def test_status_mapped_to_display_status_in_validated_data(self):
        """传入 status 后，validate 应将其重命名为 display_status"""
        serializer = ListRiskRequestSerializer(data={"status": "closed"})

        self.assertTrue(serializer.is_valid(), serializer.errors)
        validated = serializer.validated_data
        self.assertIn("display_status", validated)
        self.assertEqual(validated["display_status"], ["closed"])
        # 原始 status 键应被移除
        self.assertNotIn("status", validated)

    def test_empty_status_not_mapped_to_display_status(self):
        """传入空字符串 status 时，display_status 不应出现在 validated_data 中"""
        serializer = ListRiskRequestSerializer(data={"status": ""})

        self.assertTrue(serializer.is_valid(), serializer.errors)
        validated = serializer.validated_data
        self.assertNotIn("display_status", validated)
        # 空字符串经过 split(",") + filter 后变为空列表，status 键仍保留
        self.assertEqual(validated.get("status", []), [])

    def test_multiple_status_values_mapped_to_display_status(self):
        """传入多个 status 值（逗号分隔），应正确拆分映射到 display_status"""
        serializer = ListRiskRequestSerializer(data={"status": "closed,processing,await_deal"})

        self.assertTrue(serializer.is_valid(), serializer.errors)
        validated = serializer.validated_data
        self.assertIn("display_status", validated)
        self.assertEqual(validated["display_status"], ["closed", "processing", "await_deal"])
        self.assertNotIn("status", validated)


class TestBkBaseEventOrdering(SimpleTestCase):
    def _build_final_query(self, order_field: str, operator: str, value: str):
        resolver = BkBaseFieldResolver(
            order_field=order_field,
            event_filters=[
                {
                    "field": "latency",
                    "display_name": "Latency",
                    "operator": operator,
                    "value": value,
                }
            ],
            duplicate_field_map={},
        )
        base_expression = exp.select(
            exp.column("risk_id", table="risk"),
            exp.column("strategy_id", table="risk"),
            exp.column("raw_event_id", table="risk"),
            exp.column("event_time", table="risk"),
            exp.column("event_end_time", table="risk"),
            exp.column("event_time_timestamp", table="risk"),
            exp.column("event_end_time_timestamp", table="risk"),
        ).from_("risk")
        components_builder = BkBaseQueryComponentsBuilder(
            resolver=resolver,
            duplicate_field_map={},
            thedate_range=None,
            table_name="risk_event",
        )
        components = components_builder.build(base_expression)
        assembler = FinalSelectAssembler(resolver)
        order_direction = "DESC" if order_field.startswith("-") else "ASC"
        order_field_name = order_field.lstrip("-")
        data_query = assembler.assemble_data_query(
            components.base_query,
            components.matched_event,
            order_field=order_field_name,
            order_direction=order_direction,
            limit=0,
            offset=0,
        )
        return resolver, data_query

    def _extract_order_alias(self, select_expression: exp.Select) -> exp.Alias:
        for expression in select_expression.expressions or []:
            if isinstance(expression, exp.Alias) and expression.alias_or_name == "__order_event_field":
                return expression
        raise AssertionError("order field alias not found")

    def test_numeric_filters_cast_order_field(self):
        resolver, select_expr = self._build_final_query(
            order_field="-event_data.latency",
            operator=EventFilterOperator.GREATER_THAN.value,
            value="1.5",
        )
        order_alias = self._extract_order_alias(select_expr)
        self.assertTrue(resolver.event_order_requires_numeric_cast())
        self.assertIsInstance(order_alias.this, exp.Cast)
        cast_to = order_alias.this.args.get("to")
        self.assertIsNotNone(cast_to)
        self.assertEqual(cast_to.sql(dialect="mysql"), "DOUBLE")

    def test_non_numeric_filters_keep_string_order(self):
        resolver, select_expr = self._build_final_query(
            order_field="event_data.latency",
            operator=EventFilterOperator.EQUAL.value,
            value="slow",
        )
        order_alias = self._extract_order_alias(select_expr)
        self.assertFalse(resolver.event_order_requires_numeric_cast())
        self.assertFalse(isinstance(order_alias.this, exp.Cast))
        self.assertIn("JSON_EXTRACT_STRING", order_alias.this.sql(dialect="mysql"))

    def test_join_uses_datetime_columns_for_range(self):
        _resolver, select_expr = self._build_final_query(
            order_field="event_data.latency",
            operator=EventFilterOperator.EQUAL.value,
            value="slow",
        )
        sql_text = select_expr.sql(dialect="mysql")
        self.assertIn("UNIX_TIMESTAMP", sql_text)
        self.assertIn("base_query.event_time", sql_text)
        self.assertIn("base_query.event_end_time", sql_text)

    def test_matched_event_subquery_uses_row_number_for_latest_event(self):
        resolver = BkBaseFieldResolver(
            order_field="",
            event_filters=[
                {
                    "field": "latency",
                    "display_name": "Latency",
                    "operator": EventFilterOperator.EQUAL.value,
                    "value": "1",
                }
            ],
            duplicate_field_map={},
        )
        base_expression = exp.select(
            exp.column("risk_id", table="risk"),
            exp.column("strategy_id", table="risk"),
            exp.column("raw_event_id", table="risk"),
            exp.column("event_time", table="risk"),
            exp.column("event_end_time", table="risk"),
            exp.column("event_time_timestamp", table="risk"),
            exp.column("event_end_time_timestamp", table="risk"),
        ).from_("risk")
        components_builder = BkBaseQueryComponentsBuilder(
            resolver=resolver,
            duplicate_field_map={},
            thedate_range=None,
            table_name="risk_event",
        )
        components = components_builder.build(base_expression)
        matched_sql = components.matched_event.sql(dialect="mysql")
        self.assertIn("ROW_NUMBER()", matched_sql)
        self.assertIn("_row_number", matched_sql)
        self.assertIn("= 1", matched_sql)

    def test_without_event_filters_skips_event_join(self):
        resolver = BkBaseFieldResolver(
            order_field="",
            event_filters=[],
            duplicate_field_map={},
        )
        base_expression = exp.select(
            exp.column("risk_id", table="risk"),
            exp.column("strategy_id", table="risk"),
            exp.column("raw_event_id", table="risk"),
            exp.column("event_time", table="risk"),
            exp.column("event_end_time", table="risk"),
        ).from_("risk")
        components_builder = BkBaseQueryComponentsBuilder(
            resolver=resolver,
            duplicate_field_map={},
            thedate_range=None,
            table_name="risk_event",
        )
        components = components_builder.build(base_expression)
        self.assertIsNone(components.matched_event)


class TestListRiskRequestSerializerHasReport(SimpleTestCase):
    """ListRiskRequestSerializer has_report 字段验证"""

    def test_has_report_true_is_valid(self):
        """传入 has_report=True 时序列化器合法"""
        serializer = ListRiskRequestSerializer(data={"has_report": True})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertIs(serializer.validated_data["has_report"], True)

    def test_has_report_false_is_valid(self):
        """传入 has_report=False 时序列化器合法，且值保留为 False"""
        serializer = ListRiskRequestSerializer(data={"has_report": False})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertIs(serializer.validated_data["has_report"], False)

    def test_has_report_null_is_valid(self):
        """传入 has_report=null 时序列化器合法（allow_null=True）"""
        serializer = ListRiskRequestSerializer(data={"has_report": None})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertIsNone(serializer.validated_data["has_report"])

    def test_has_report_not_provided_is_valid(self):
        """不传 has_report 时序列化器合法，validated_data 中不含该键"""
        serializer = ListRiskRequestSerializer(data={})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertNotIn("has_report", serializer.validated_data)

    def test_has_report_not_split_by_comma_logic(self):
        """has_report 不被通用逗号分割逻辑处理，布尔值保持原样"""
        serializer = ListRiskRequestSerializer(data={"has_report": True})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        # 确认 validated_data 中 has_report 是布尔值，而非列表
        self.assertIsInstance(serializer.validated_data["has_report"], bool)

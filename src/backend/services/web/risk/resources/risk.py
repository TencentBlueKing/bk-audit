# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
Copyright (C) 2023 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

import abc
import json
import logging
import re
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple, Type

import sqlglot
from bk_resource import CacheResource, api, resource
from bk_resource.settings import bk_resource_settings
from bk_resource.utils.cache import CacheTypeItem
from bk_resource.utils.common_utils import ignored
from django.conf import settings
from django.db import transaction
from django.db.models import Case, Count, IntegerField, Q, QuerySet, When
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext, gettext_lazy
from rest_framework.settings import api_settings
from sqlglot import exp

from apps.audit.resources import AuditMixinResource
from apps.itsm.constants import TicketOperate, TicketStatus
from apps.meta.constants import ConfigLevelChoices
from apps.meta.models import GlobalMetaConfig, Tag
from apps.permission.handlers.actions import ActionEnum
from apps.permission.handlers.drf import wrapper_permission_field
from apps.permission.handlers.resource_types import ResourceEnum
from apps.sops.constants import SOPSTaskOperation, SOPSTaskStatus
from core.exceptions import RiskStatusInvalid
from core.exporter.constants import ExportField
from core.models import get_request_username
from core.utils.data import choices_to_dict, data2string, preserved_order_sort
from core.utils.page import paginate_queryset
from core.utils.time import mstimestamp_to_date_string
from core.utils.tools import get_app_info
from services.web.databus.constants import (
    ASSET_RISK_BKBASE_RT_ID_KEY,
    ASSET_STRATEGY_BKBASE_RT_ID_KEY,
    ASSET_STRATEGY_TAG_BKBASE_RT_ID_KEY,
    DORIS_EVENT_BKBASE_RT_ID_KEY,
)
from services.web.risk.constants import (
    EVENT_EXPORT_FIELD_PREFIX,
    RISK_EXPORT_FILE_NAME_TMP,
    RISK_LEVEL_ORDER_FIELD,
    RISK_SHOW_FIELDS,
    EventFilterOperator,
    RiskExportField,
    RiskFields,
    RiskLabel,
    RiskStatus,
    RiskViewType,
    TicketNodeStatus,
)
from services.web.risk.exceptions import ExportRiskNoPermission
from services.web.risk.handlers.risk_export import MultiSheetRiskExporterXlsx
from services.web.risk.handlers.ticket import (
    AutoProcess,
    CloseRisk,
    CustomProcess,
    ForApprove,
    MisReport,
    ReOpen,
    ReOpenMisReport,
    TransOperator,
)
from services.web.risk.models import (
    ProcessApplication,
    Risk,
    RiskAuditInstance,
    RiskExperience,
    TicketNode,
)
from services.web.risk.serializers import (
    BulkCustomTransRiskReqSerializer,
    CustomAutoProcessReqSerializer,
    CustomCloseRiskRequestSerializer,
    CustomTransRiskReqSerializer,
    ForceRevokeApproveTicketReqSerializer,
    ForceRevokeAutoProcessReqSerializer,
    GetRiskFieldsByStrategyRequestSerializer,
    GetRiskFieldsByStrategyResponseSerializer,
    ListEventFieldsByStrategyRequestSerializer,
    ListEventFieldsByStrategyResponseSerializer,
    ListRiskMetaRequestSerializer,
    ListRiskRequestSerializer,
    ListRiskResponseSerializer,
    ListRiskStrategyRespSerializer,
    ListRiskTagsRespSerializer,
    ReopenRiskReqSerializer,
    RetrieveRiskStrategyInfoResponseSerializer,
    RetryAutoProcessReqSerializer,
    RiskExportReqSerializer,
    RiskInfoSerializer,
    TicketNodeSerializer,
    UpdateRiskLabelReqSerializer,
)
from services.web.risk.tasks import process_one_risk, sync_auto_result
from services.web.strategy_v2.constants import RiskLevel, StrategyFieldSourceEnum
from services.web.strategy_v2.models import Strategy, StrategyTag

logger = logging.getLogger(__name__)


class RiskMeta(AuditMixinResource, abc.ABC):
    tags = ["Risk"]
    audit_resource_type = ResourceEnum.RISK


class RetrieveRisk(RiskMeta):
    name = gettext_lazy("获取风险详情")
    audit_action = ActionEnum.LIST_RISK

    def perform_request(self, validated_request_data):
        risk = get_object_or_404(Risk, risk_id=validated_request_data["risk_id"])
        self.add_audit_instance_to_context(instance=RiskAuditInstance(risk))
        data = RiskInfoSerializer(risk).data
        data = wrapper_permission_field(
            data, actions=[ActionEnum.EDIT_RISK], id_field=lambda risk: risk["risk_id"], many=False
        )
        risk = data[0]
        nodes = TicketNode.objects.filter(risk_id=risk["risk_id"]).order_by("timestamp")
        risk["ticket_history"] = TicketNodeSerializer(nodes, many=True).data
        return risk


class RetrieveRiskStrategyInfo(RiskMeta):
    name = gettext_lazy("获取风险策略信息")
    ResponseSerializer = RetrieveRiskStrategyInfoResponseSerializer

    def perform_request(self, validated_request_data):
        risk: Risk = get_object_or_404(Risk, risk_id=validated_request_data["risk_id"])
        strategy = Strategy.objects.filter(strategy_id=risk.strategy_id).first()
        return strategy or {}


class RetrieveRiskAPIGW(RetrieveRisk):
    audit_action = None

    def perform_request(self, validated_request_data):
        get_app_info()
        risk = get_object_or_404(Risk, risk_id=validated_request_data["risk_id"])
        return RiskInfoSerializer(risk).data


class ListRisk(RiskMeta):
    name = gettext_lazy("获取风险列表")
    RequestSerializer = ListRiskRequestSerializer
    bind_request = True
    audit_action = ActionEnum.LIST_RISK

    def perform_request(self, validated_request_data):
        request = validated_request_data.pop("_request")
        order_field = validated_request_data.pop("order_field", "-event_time")
        use_bkbase = bool(validated_request_data.pop("use_bkbase", False))
        event_filters = validated_request_data.pop("event_filters", [])
        thedate_range = self._extract_thedate_range(validated_request_data)
        base_queryset = self.load_risks(validated_request_data)
        base_queryset = self._filter_queryset_by_event_data_fields(base_queryset, event_filters)

        if use_bkbase:
            paged_risks, page, risk_ids = self.retrieve_via_bkbase(
                base_queryset=base_queryset,
                request=request,
                order_field=order_field,
                event_filters=event_filters,
                thedate_range=thedate_range,
            )
        else:
            paged_risks, page, risk_ids = self.retrieve_via_db(
                base_queryset=base_queryset, request=request, order_field=order_field
            )

        experiences = {
            e["risk_id"]: e["count"]
            for e in RiskExperience.objects.filter(risk_id__in=risk_ids)
            .values("risk_id")
            .order_by("risk_id")
            .annotate(count=Count("risk_id"))
        }
        for risk in paged_risks:
            setattr(risk, "experiences", experiences.get(risk.risk_id, 0))
        return page.get_paginated_response(data=ListRiskResponseSerializer(instance=paged_risks, many=True).data).data

    def _extract_thedate_range(self, validated_request_data) -> Tuple[str, str]:
        end_dt = (
            validated_request_data['event_time__lt'][0]
            if validated_request_data.get('event_time__lt')
            else datetime.now()
        )
        start_dt = (
            validated_request_data['event_time__gte'][0]
            if validated_request_data.get('event_time__gte')
            else end_dt - timedelta(days=180)
        )
        start_date = start_dt.date().strftime("%Y%m%d")
        end_date = end_dt.date().strftime("%Y%m%d")
        return start_date, end_date

    def retrieve_via_db(self, base_queryset: QuerySet, request, order_field: str):
        risks = self._apply_ordering(base_queryset, order_field).only("pk")
        paged_queryset, page = paginate_queryset(
            queryset=risks, request=request, base_queryset=Risk.annotated_queryset()
        )
        paged_queryset = self._apply_ordering(Risk.prefetch_strategy_tags(paged_queryset), order_field)
        paged_risks = list(paged_queryset)
        risk_ids = [risk.risk_id for risk in paged_risks]
        return paged_risks, page, risk_ids

    def _filter_queryset_by_event_data_fields(
        self, queryset: QuerySet, event_filters: List[Dict[str, Any]]
    ) -> QuerySet:
        if not event_filters:
            return queryset

        strategy_ids = list(queryset.values_list("strategy_id", flat=True).distinct())
        if not strategy_ids:
            return queryset.none()

        # 使用JSONField contains能力在数据库侧完成过滤，避免加载并解析所有配置
        strategy_queryset = Strategy.objects.filter(strategy_id__in=strategy_ids)

        for item in event_filters:
            field = item.get("field")
            display_name = item.get("display_name")
            strategy_queryset = strategy_queryset.filter(
                event_data_field_configs__contains=[{"field_name": field, "display_name": display_name}]
            )

        matched_strategy_ids = list(strategy_queryset.values_list("strategy_id", flat=True))
        if not matched_strategy_ids:
            return queryset.none()

        return queryset.filter(strategy_id__in=matched_strategy_ids)

    def retrieve_via_bkbase(
        self,
        base_queryset: QuerySet,
        request,
        order_field: str,
        event_filters: List[Dict[str, Any]],
        thedate_range: Optional[Tuple[str, str]] = None,
    ):
        order_field_name = order_field.lstrip("-")
        order_direction = "DESC" if order_field.startswith("-") else "ASC"

        value_fields = ["risk_id", "strategy_id"]
        if order_field_name not in value_fields:
            value_fields.append(order_field_name)
        if order_field_name == RISK_LEVEL_ORDER_FIELD and "event_time" not in value_fields:
            value_fields.append("event_time")

        values_queryset = base_queryset.values(*value_fields).distinct()

        total = self._query_total_count(values_queryset, event_filters, thedate_range)
        page = api_settings.DEFAULT_PAGINATION_CLASS()
        page.paginate_queryset(range(total), request)

        page_obj = getattr(page, "page", None)
        page_size = page_obj.paginator.per_page if page_obj else 0
        page_number = page_obj.number if page_obj else 1

        offset = (page_number - 1) * page_size if page_size else 0
        limit = page_size or total

        risk_ids: List[str] = []
        if total:
            risk_ids = self._query_risk_ids(
                queryset=values_queryset,
                event_filters=event_filters,
                order_field=order_field_name,
                order_direction=order_direction,
                limit=limit,
                offset=offset,
                thedate_range=thedate_range,
            )

        paged_queryset = self._build_risk_queryset(risk_ids)
        paged_queryset = Risk.prefetch_strategy_tags(paged_queryset)
        paged_risks = list(paged_queryset)
        risk_ids = [risk.risk_id for risk in paged_risks]

        if getattr(page, "page", None):
            page.page.object_list = list(risk_ids)

        return paged_risks, page, risk_ids

    def _apply_ordering(self, queryset: QuerySet["Risk"], order_field: str) -> QuerySet["Risk"]:
        """Apply ordering, including custom order for strategy risk level.

        - Use ORM order_by for general fields
        - For strategy__risk_level, use custom numeric order: asc => LOW<MIDDLE<HIGH, desc => HIGH>MIDDLE>LOW
        """
        if not order_field:
            return queryset
        field = order_field.lstrip("-")
        if field == RISK_LEVEL_ORDER_FIELD:
            return preserved_order_sort(
                queryset,
                ordering_field=order_field,
                value_list=[RiskLevel.LOW, RiskLevel.MIDDLE, RiskLevel.HIGH],
                extra_order_by=["-event_time"],
            )
        return queryset.order_by(order_field)

    def load_risks(self, validated_request_data: dict) -> QuerySet["Risk"]:
        # 构造表达式
        q = Q()
        # 风险等级
        risk_level = validated_request_data.pop("risk_level", None)
        if risk_level:
            q &= Q(strategy__risk_level__in=risk_level)

        # 标签筛选条件
        if tag_filter := validated_request_data.pop("tag_objs__in", None):
            q &= Q(strategy__tags__tag_id__in=tag_filter)

        for key, val in validated_request_data.items():
            if not val:
                continue
            # 普通匹配，针对单值匹配
            _q = Q()
            for i in val:
                _q |= Q(**{key: i})
            q &= _q
        # 获取有权限且符合表达式的
        return Risk.load_authed_risks(action=ActionEnum.LIST_RISK).filter(q).distinct()

    def _build_risk_queryset(self, risk_ids: List[str]) -> QuerySet["Risk"]:
        if not risk_ids:
            return Risk.annotated_queryset().none()

        order_cases = [When(risk_id=risk_id, then=index) for index, risk_id in enumerate(risk_ids)]
        order_expression = Case(*order_cases, default=len(risk_ids), output_field=IntegerField())
        return Risk.annotated_queryset().filter(risk_id__in=risk_ids).order_by(order_expression)

    def _query_total_count(
        self, queryset: QuerySet, event_filters: List[Dict[str, Any]], thedate_range: Optional[Tuple[str, str]]
    ) -> int:
        base_query = queryset.order_by()
        base_sql = self._compile_queryset_sql(base_query)
        base_expression = self._convert_to_bkbase_expression(base_sql)
        filtered_query = self._build_filtered_query(base_expression, event_filters, thedate_range)
        count_query = self._build_count_query(filtered_query)
        count_sql = count_query.sql(dialect="hive")
        logger.info("BKBase count SQL: %s", count_sql)
        count_resp = api.bk_base.query_sync(sql=count_sql) or {}
        results = count_resp.get("list") or []
        if not results:
            return 0
        count_value = results[0].get("count", 0)
        try:
            return int(count_value)
        except (TypeError, ValueError):
            return 0

    def _query_risk_ids(
        self,
        queryset: QuerySet,
        event_filters: List[Dict[str, Any]],
        order_field: str,
        order_direction: str,
        limit: int,
        offset: int,
        thedate_range: Optional[Tuple[str, str]],
    ) -> List[str]:
        base_query = queryset
        base_sql = self._compile_queryset_sql(base_query)
        base_expression = self._convert_to_bkbase_expression(base_sql)
        filtered_query = self._build_filtered_query(base_expression, event_filters, thedate_range)
        data_query = self._apply_order_and_limit(
            filtered_query,
            order_field=order_field,
            order_direction=order_direction,
            limit=limit,
            offset=offset,
        )
        data_sql = data_query.sql(dialect="hive")
        logger.info("BKBase data SQL: %s", data_sql)
        data_resp = api.bk_base.query_sync(sql=data_sql) or {}
        results = data_resp.get("list") or []
        risk_ids: List[str] = []
        for row in results:
            risk_ids.append(row["risk_id"])
        return risk_ids

    def _get_bkbase_table_map(self) -> Dict[str, str]:
        if not hasattr(self, "_bkbase_table_map"):
            self._bkbase_table_map = {
                Risk._meta.db_table: self._get_configured_table_name(
                    config_key=ASSET_RISK_BKBASE_RT_ID_KEY, fallback=Risk._meta.db_table
                ),
                Strategy._meta.db_table: self._get_configured_table_name(
                    config_key=ASSET_STRATEGY_BKBASE_RT_ID_KEY, fallback=Strategy._meta.db_table
                ),
                StrategyTag._meta.db_table: self._get_configured_table_name(
                    config_key=ASSET_STRATEGY_TAG_BKBASE_RT_ID_KEY, fallback=StrategyTag._meta.db_table
                ),
                "risk_event": self._get_configured_table_name(
                    config_key=DORIS_EVENT_BKBASE_RT_ID_KEY, fallback="risk_event"
                ),
            }
        return self._bkbase_table_map

    def _get_configured_table_name(self, *, config_key: str, fallback: str) -> str:
        return GlobalMetaConfig.get(
            config_key=config_key,
            config_level=ConfigLevelChoices.NAMESPACE.value,
            instance_key=settings.DEFAULT_NAMESPACE,
            default=fallback,
        )

    @staticmethod
    def _split_table_parts(table_name: str) -> Tuple[Optional[str], Optional[str], str]:
        cleaned = (table_name or "").strip().strip("`")
        if not cleaned:
            return None, None, ""
        parts = [part.strip().strip("`") for part in cleaned.split(".") if part.strip()]
        if not parts:
            return None, None, ""
        if len(parts) == 1:
            return None, None, parts[0]
        if len(parts) == 2:
            return None, parts[0], parts[1]
        # 当存在 catalog.db.table 或更多层级时，仅保留后三段
        return parts[-3], parts[-2], parts[-1]

    def _compile_queryset_sql(self, queryset: QuerySet) -> str:
        compiler = queryset.query.get_compiler(using=queryset.db)
        sql, params = compiler.as_sql()
        sql = self._clean_sql(sql or "")
        if params:
            sql = self._render_sql_with_params(sql, params)
        return sql

    def _render_sql_with_params(self, sql: str, params: Sequence[Any]) -> str:
        params_iter: Iterator[Any] = iter(params or [])

        def replacer(match: re.Match[str]) -> str:
            try:
                value = next(params_iter)
            except StopIteration:
                return match.group(0)
            return self._literal(value).sql("mysql")

        return re.sub(r"%s", replacer, sql)

    def _convert_to_bkbase_expression(self, sql: str) -> exp.Expression:
        if not sql:
            return sqlglot.parse_one("SELECT 1")
        table_map = self._get_bkbase_table_map()
        if not table_map:
            return sqlglot.parse_one(sql, read="mysql")
        try:
            expression = sqlglot.parse_one(sql, read="mysql")
        except sqlglot.errors.ParseError:
            expression = sqlglot.parse_one(sql, read="hive")

        def transform_table(node: exp.Expression) -> exp.Expression:
            if not isinstance(node, exp.Table):
                return node
            source = node.name
            if not source:
                return node
            target = table_map.get(source)
            if not target or target == source:
                return node

            catalog, db, table = self._split_table_parts(target)
            if not table:
                node.set("catalog", None)
                node.set("db", None)
                node.set("this", exp.Identifier(this=target, quoted=False))
            else:
                node.set("catalog", exp.Identifier(this=catalog, quoted=False) if catalog else None)
                node.set("db", exp.Identifier(this=db, quoted=False) if db else None)
                node.set("this", exp.Identifier(this=table, quoted=False))

            if not node.alias:
                node.set("alias", exp.TableAlias(this=exp.to_identifier(source)))
            return node

        transformed = expression.transform(transform_table)
        return transformed

    def _get_risk_event_table_reference(self) -> str:
        table_name = self._get_bkbase_table_map().get("risk_event", "risk_event")
        formatted = self._format_table_identifier(table_name)
        return formatted or "risk_event"

    @classmethod
    def _format_table_identifier(cls, table_name: str) -> str:
        catalog, db, table = cls._split_table_parts(table_name)
        parts = [part for part in (catalog, db, table) if part]
        return ".".join(f"`{part}`" for part in parts)

    def _prepare_base_expression(
        self, base_expression: exp.Expression, thedate_range: Optional[Tuple[str, str]]
    ) -> exp.Expression:
        prepared = base_expression.copy()
        prepared = self._strip_select_ordering(prepared)
        prepared = self._push_partition_filters(prepared, thedate_range)
        return prepared

    def _strip_select_ordering(self, expression: exp.Expression) -> exp.Expression:
        if isinstance(expression, exp.Select):
            expression.set("order", None)
            expression.set("limit", None)
            expression.set("offset", None)
        return expression

    def _has_primary_key_filter(self, expression: exp.Select) -> bool:
        where_clause = expression.args.get("where")
        if not isinstance(where_clause, exp.Expression):
            return False
        for node in where_clause.walk():
            if not isinstance(node, exp.EQ):
                continue
            left = node.args.get("this")
            right = node.args.get("expression")
            if self._is_risk_id_equality(left, right) or self._is_risk_id_equality(right, left):
                return True
        return False

    def _is_risk_id_equality(self, column: Optional[exp.Expression], other: Optional[exp.Expression]) -> bool:
        if not isinstance(column, exp.Column):
            return False
        if column.name != "risk_id":
            return False
        table_name = column.table
        if table_name and table_name.strip("`") != "risk_risk":
            return False
        return isinstance(other, (exp.Literal, exp.Boolean, exp.Null))

    def _push_partition_filters(
        self, expression: exp.Expression, thedate_range: Optional[Tuple[str, str]]
    ) -> exp.Expression:
        if not isinstance(expression, exp.Select):
            return expression
        if not thedate_range:
            return expression
        start_date, end_date = thedate_range
        if not start_date or not end_date:
            return expression
        alias = self._get_risk_table_alias(expression)
        if not alias:
            return expression
        conditions = self._combine_conditions(
            [
                exp.GTE(this=self._column(alias, "thedate"), expression=self._literal(start_date)),
                exp.LTE(this=self._column(alias, "thedate"), expression=self._literal(end_date)),
            ]
        )
        if not conditions:
            return expression
        existing_where = expression.args.get("where")
        if isinstance(existing_where, exp.Where):
            combined = exp.and_(existing_where.this, conditions)
            expression.set("where", exp.Where(this=combined))
        elif isinstance(existing_where, exp.Expression):
            expression.set("where", exp.Where(this=exp.and_(existing_where, conditions)))
        else:
            expression.set("where", exp.Where(this=conditions))
        return expression

    def _get_risk_table_alias(self, expression: exp.Select) -> Optional[str]:
        from_clause = expression.args.get("from")
        if not isinstance(from_clause, exp.From):
            return None
        for table in from_clause.find_all(exp.Table):
            alias_name = table.alias or None
            if not alias_name:
                table_identifier = table.this
                if isinstance(table_identifier, exp.Identifier):
                    alias_name = table_identifier.this
                elif table_identifier is not None:
                    alias_name = str(table_identifier)
                else:
                    alias_name = table.name
            if not alias_name:
                continue
            cleaned = str(alias_name).strip("`")
            if cleaned == "risk_risk":
                return cleaned
        return None

    def _build_filtered_query(
        self,
        base_expression: exp.Expression,
        event_filters: List[Dict[str, Any]],
        thedate_range: Optional[Tuple[str, str]],
    ) -> exp.Select:
        prepared_base = self._prepare_base_expression(base_expression, thedate_range)
        base_subquery = exp.Subquery(
            this=prepared_base,
            alias=exp.TableAlias(this=exp.to_identifier("base_query")),
        )
        query = exp.select(exp.Star()).from_(base_subquery)

        conditions: List[exp.Expression] = []
        if event_filters:
            conditions.extend(self._build_thedate_conditions(alias="base_query", thedate_range=thedate_range))
        conditions.extend(
            condition
            for index, item in enumerate(event_filters)
            if (condition := self._build_event_filter_condition(item, index, thedate_range))
        )

        combined = self._combine_conditions(conditions)
        if combined is not None:
            query = query.where(combined)
        return query

    def _build_count_query(self, filtered_query: exp.Expression) -> exp.Select:
        filtered_copy = self._strip_select_ordering(filtered_query.copy())
        subquery = exp.Subquery(
            this=filtered_copy,
            alias=exp.TableAlias(this=exp.to_identifier("risk_count")),
        )
        count_expr = exp.func("COUNT", exp.Star())
        count_query = exp.select(exp.alias_(count_expr, "count")).from_(subquery)
        return count_query.limit(exp.Literal.number(1))

    def _apply_order_and_limit(
        self, query: exp.Select, order_field: str, order_direction: str, limit: int, offset: int
    ) -> exp.Select:
        ordered_query = query.copy()
        order_expressions = self._build_order_expressions(order_field, order_direction)
        if order_expressions:
            ordered_query = ordered_query.order_by(*order_expressions)
        if limit:
            ordered_query = ordered_query.limit(int(limit))
            if offset:
                ordered_query = ordered_query.offset(int(offset))
        elif offset:
            ordered_query = ordered_query.offset(int(offset))
        return ordered_query

    def _build_order_expressions(self, order_field: str, order_direction: str) -> List[exp.Expression]:
        if not order_field:
            return []
        field_name = order_field.lstrip("-")
        descending = order_direction.upper() == "DESC"

        if field_name == RISK_LEVEL_ORDER_FIELD:
            case_expr = exp.Case()
            for index, level in enumerate([RiskLevel.LOW.value, RiskLevel.MIDDLE.value, RiskLevel.HIGH.value]):
                comparison = exp.EQ(
                    this=self._column("base_query", field_name),
                    expression=self._literal(level),
                )
                case_expr = case_expr.when(comparison, exp.Literal.number(str(index)))
            case_expr = case_expr.else_(exp.Literal.number("99"))
            return [
                exp.Ordered(this=case_expr, desc=descending),
                exp.Ordered(this=self._column("base_query", "event_time"), desc=True),
            ]

        return [exp.Ordered(this=self._column("base_query", field_name), desc=descending)]

    def _build_event_filter_condition(
        self, filter_item: Dict[str, Any], index: int, thedate_range: Optional[Tuple[str, str]]
    ) -> Optional[exp.Expression]:
        alias = f"risk_event_{index}"
        join_conditions: List[exp.Expression] = [
            exp.EQ(
                this=self._column(alias, "strategy_id"),
                expression=self._column("base_query", "strategy_id"),
            ),
            exp.EQ(
                this=self._column(alias, "risk_id"),
                expression=self._column("base_query", "risk_id"),
            ),
        ]

        field_expression = self._build_event_field_expression(alias, filter_item)
        if field_expression is None:
            return None

        comparison = self._build_event_filter_expression(field_expression, filter_item)
        if comparison is None:
            return None

        conditions = join_conditions + self._build_thedate_conditions(alias, thedate_range) + [comparison]
        combined = self._combine_conditions(conditions)
        if combined is None:
            return None

        table_reference = self._get_risk_event_table_reference()
        table_expr = exp.to_table(table_reference).copy().as_(alias)
        exists_query = exp.select("1").from_(table_expr).where(combined)
        return exp.Exists(this=exists_query)

    def _build_thedate_conditions(self, alias: str, thedate_range: Optional[Tuple[str, str]]) -> List[exp.Expression]:
        if not thedate_range:
            return []
        start_date, end_date = thedate_range
        if not start_date or not end_date:
            return []
        return [
            exp.GTE(this=self._column(alias, "thedate"), expression=self._literal(start_date)),
            exp.LTE(this=self._column(alias, "thedate"), expression=self._literal(end_date)),
        ]

    def _build_event_field_expression(self, alias: str, filter_item: Dict[str, Any]) -> Optional[exp.Expression]:
        field_name = filter_item.get("field")
        if not field_name:
            return None

        resolved_source = filter_item.get("field_source") or StrategyFieldSourceEnum.DATA.value

        if resolved_source == StrategyFieldSourceEnum.BASIC.value:
            return self._column(alias, field_name)

        if resolved_source == StrategyFieldSourceEnum.DATA.value:
            column = self._column(alias, "event_data")
        elif resolved_source == StrategyFieldSourceEnum.EVIDENCE.value:
            column = self._column(alias, "event_evidence")
        else:
            return None

        json_path = self._build_json_path(field_name)
        return exp.func("JSON_EXTRACT", column, exp.Literal.string(json_path))

    def _build_event_filter_expression(
        self, field_expr: exp.Expression, filter_item: Dict[str, Any]
    ) -> Optional[exp.Expression]:
        value = filter_item.get("value")
        operator = filter_item.get("operator") or EventFilterOperator.EQUAL.value
        if isinstance(operator, str):
            operator = operator.upper()

        if operator == EventFilterOperator.EQUAL.value:
            if value is None:
                return exp.Is(this=field_expr.copy(), expression=exp.Null())
            return exp.EQ(this=field_expr.copy(), expression=self._literal(value))

        if operator == EventFilterOperator.NOT_EQUAL.value:
            if value is None:
                return exp.not_(exp.Is(this=field_expr.copy(), expression=exp.Null()))
            return exp.NEQ(this=field_expr.copy(), expression=self._literal(value))

        if operator in {
            EventFilterOperator.GREATER_THAN.value,
            EventFilterOperator.GREATER_THAN_EQUAL.value,
            EventFilterOperator.LESS_THAN.value,
            EventFilterOperator.LESS_THAN_EQUAL.value,
        }:
            comparator_map = {
                EventFilterOperator.GREATER_THAN.value: exp.GT,
                EventFilterOperator.GREATER_THAN_EQUAL.value: exp.GTE,
                EventFilterOperator.LESS_THAN.value: exp.LT,
                EventFilterOperator.LESS_THAN_EQUAL.value: exp.LTE,
            }
            comparator = comparator_map[operator]
            if self._is_numeric_value(value):
                cast_field = exp.Cast(this=field_expr.copy(), to=exp.DataType.build("DOUBLE"))
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    literal = exp.Literal.number(str(value))
                else:
                    literal = exp.Literal.number(str(float(value)))
                return comparator(this=cast_field, expression=literal)
            return comparator(this=field_expr.copy(), expression=self._literal(value))

        if operator in {EventFilterOperator.IN.value, EventFilterOperator.NOT_IN.value}:
            values = self._ensure_list(value)
            if not values:
                return exp.false() if operator == EventFilterOperator.IN.value else exp.true()
            in_expr = exp.In(
                this=field_expr.copy(),
                expressions=[self._literal(item) for item in values],
            )
            return exp.not_(in_expr) if operator == EventFilterOperator.NOT_IN.value else in_expr

        if operator in {EventFilterOperator.CONTAINS.value, EventFilterOperator.NOT_CONTAINS.value}:
            pattern = self._escape_like_pattern(str(value))
            like_expr = exp.Like(this=field_expr.copy(), expression=exp.Literal.string(f"%{pattern}%"))
            escape_expr = exp.Escape(this=like_expr, expression=exp.Literal.string("\\"))
            return exp.not_(escape_expr) if operator == EventFilterOperator.NOT_CONTAINS.value else escape_expr

        return None

    def _build_json_path(self, field_name: str) -> str:
        safe_field = field_name.replace("\\", "\\\\").replace("'", "\\'")
        path_parts = [part for part in safe_field.split(".") if part]
        return "$" + "".join(f".{part}" for part in path_parts)

    def _combine_conditions(self, conditions: List[exp.Expression]) -> Optional[exp.Expression]:
        if not conditions:
            return None
        combined = conditions[0]
        for condition in conditions[1:]:
            combined = exp.and_(combined, condition)
        return combined

    def _column(self, alias: str, identifier: str) -> exp.Column:
        return exp.column(identifier, table=alias)

    def _literal(self, value: Any) -> exp.Expression:
        if value is None:
            return exp.Null()
        if isinstance(value, bool):
            return exp.Literal.string("true" if value else "false")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return exp.Literal.number(str(value))
        return exp.Literal.string(str(value))

    def _ensure_list(self, value: Any) -> List[Any]:
        if value is None:
            return []
        if isinstance(value, (list, tuple, set)):
            return list(value)
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return [value]

    def _escape_like_pattern(self, value: str) -> str:
        return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

    def _is_numeric_value(self, value: Any) -> bool:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return True
        if isinstance(value, str):
            try:
                float(value)
                return True
            except ValueError:
                return False
        return False

    @staticmethod
    def _clean_sql(sql: str) -> str:
        return sql.strip().rstrip(";")


class ListMineRisk(ListRisk):
    name = gettext_lazy("获取待我处理的风险列表")

    def load_risks(self, validated_request_data):
        queryset = super().load_risks(validated_request_data)
        queryset = queryset.filter(Q(current_operator__contains=get_request_username()))
        return queryset


class ListNoticingRisk(ListRisk):
    name = gettext_lazy("获取我关注的风险列表")

    def load_risks(self, validated_request_data):
        queryset = super().load_risks(validated_request_data)
        queryset = queryset.filter(Q(notice_users__contains=get_request_username()))
        return queryset


class ListRiskFields(RiskMeta):
    name = gettext_lazy("获取风险字段")

    def perform_request(self, validated_request_data):
        show_fields = set(RISK_SHOW_FIELDS)
        return [
            {
                "id": f.attname if getattr(f, "attname", None) in show_fields else f.name,
                "name": str(f.verbose_name),
            }
            for f in Risk.fields()
            if f.name in show_fields or getattr(f, "attname", None) in show_fields
        ]


class UpdateRiskLabel(RiskMeta):
    name = gettext_lazy("更新风险标记")
    RequestSerializer = UpdateRiskLabelReqSerializer
    ResponseSerializer = RiskInfoSerializer
    audit_action = ActionEnum.EDIT_RISK

    @transaction.atomic()
    def perform_request(self, validated_request_data):
        # 初始化风险
        risk = get_object_or_404(Risk, risk_id=validated_request_data["risk_id"])
        origin_data = RiskInfoSerializer(risk).data
        # 确认要变更的类型
        new_risk_label = validated_request_data["risk_label"]
        # 重开需要登记重开，并转单
        if new_risk_label == RiskLabel.NORMAL:
            ReOpenMisReport(risk_id=risk.risk_id, operator=get_request_username()).run(
                new_operators=validated_request_data.get("new_operators", [])
            )
        # 误报需要登记误报，并关单
        elif new_risk_label == RiskLabel.MISREPORT:
            MisReport(risk_id=risk.risk_id, operator=get_request_username()).run(
                description=validated_request_data["description"],
                revoke_process=validated_request_data["revoke_process"],
            )
        risk.refresh_from_db()
        setattr(risk, "instance_origin_data", origin_data)
        self.add_audit_instance_to_context(instance=RiskAuditInstance(risk))
        return risk


class RiskStatusCommon(RiskMeta):
    name = gettext_lazy("获取风险状态类型")

    def perform_request(self, validated_request_data):
        return choices_to_dict(RiskStatus)


class ListRiskBase(RiskMeta, CacheResource, abc.ABC):
    RequestSerializer = ListRiskMetaRequestSerializer
    many_response_data = True
    # 风险视图类型与风险类的映射
    risk_cls_map: Dict[str, Type[ListRisk]] = {
        RiskViewType.ALL.value: ListRisk,
        RiskViewType.TODO.value: ListMineRisk,
        RiskViewType.WATCH.value: ListNoticingRisk,
    }

    @classmethod
    def load_risk_view_type_risks(cls, risk_view_type: str, filter_dict: dict) -> QuerySet[Risk]:
        """
        加载指定风险视图下有权限的风险
        """

        risk_cls = cls.risk_cls_map.get(risk_view_type)
        if not risk_cls:
            return Risk.objects.none()
        return risk_cls().load_risks(filter_dict)


class ListRiskTags(ListRiskBase):
    """
    获取用户的风险标签列表，支持用户在不同风险视图下的数据展示
    注意：该接口的筛选条件主要需要风险列表的事件发生时间，当该参数变化时需要重新查询
    """

    name = gettext_lazy("获取风险的标签")
    ResponseSerializer = ListRiskTagsRespSerializer
    cache_type = CacheTypeItem(key="ListRiskTags", timeout=60, user_related=True)

    def perform_request(self, validated_request_data):
        tags = Tag.objects.all().only("tag_id", "tag_name")
        risk_view_type: str = validated_request_data.pop("risk_view_type", None)
        if not risk_view_type:
            return tags
        risk_ids = set(
            self.load_risk_view_type_risks(risk_view_type, validated_request_data).values_list("risk_id", flat=True)
        )
        if not risk_ids:
            return []

        # 1. 获取这些风险对应的策略ID
        strategy_ids = set(Risk.objects.filter(risk_id__in=risk_ids).values_list("strategy_id", flat=True))

        # 2. 查询这些策略关联的标签ID
        tag_ids = set(StrategyTag.objects.filter(strategy_id__in=strategy_ids).values_list("tag_id", flat=True))

        # 3. 返回对应的标签
        return tags.filter(tag_id__in=tag_ids)


class ListRiskStrategy(ListRiskBase):
    """
    获取风险的策略，支持不同风险视图下的数据展示
    注意：该接口的筛选条件主要需要风险列表的事件发生时间，当该参数变化时需要重新查询
    """

    name = gettext_lazy("获取风险的策略")
    ResponseSerializer = ListRiskStrategyRespSerializer
    cache_type = CacheTypeItem(key="ListRiskStrategy", timeout=60, user_related=True)

    def perform_request(self, validated_request_data):
        strategies: QuerySet[Strategy] = Strategy.objects.all().only("strategy_id", "strategy_name")
        risk_view_type: str = validated_request_data.pop("risk_view_type", None)
        if not risk_view_type:
            return strategies
        strategy_ids = set(
            self.load_risk_view_type_risks(risk_view_type, validated_request_data)
            .values_list("strategy_id", flat=True)
            .distinct()
        )
        if not strategy_ids:
            return []
        return strategies.filter(strategy_id__in=strategy_ids)


class CustomCloseRisk(RiskMeta):
    name = gettext_lazy("人工关单")
    RequestSerializer = CustomCloseRiskRequestSerializer
    audit_action = ActionEnum.EDIT_RISK

    @transaction.atomic()
    def perform_request(self, validated_request_data):
        username = get_request_username()
        risk = get_object_or_404(Risk, risk_id=validated_request_data["risk_id"])
        origin_data = RiskInfoSerializer(risk).data
        CustomProcess(risk_id=risk.risk_id, operator=username).run(
            custom_action=CloseRisk.__name__, description=validated_request_data["description"]
        )
        CloseRisk(risk_id=risk.risk_id, operator=username).run(description=gettext("%s 人工关单") % username)
        setattr(risk, "instance_origin_data", origin_data)
        self.add_audit_instance_to_context(instance=RiskAuditInstance(risk))


class CustomTransRisk(RiskMeta):
    name = gettext_lazy("人工转单")
    RequestSerializer = CustomTransRiskReqSerializer
    audit_action = ActionEnum.EDIT_RISK

    @transaction.atomic()
    def perform_request(self, validated_request_data):
        risk = get_object_or_404(Risk, risk_id=validated_request_data["risk_id"])
        if risk.status != RiskStatus.AWAIT_PROCESS.value:
            raise RiskStatusInvalid(message=RiskStatusInvalid.MESSAGE % risk.status)
        origin_data = RiskInfoSerializer(risk).data
        # 使用当前用户 or 并发请求时透传的用户
        operator = get_request_username(validated_request_data.get("_request", None))
        TransOperator(risk_id=risk.risk_id, operator=operator).run(
            new_operators=validated_request_data["new_operators"], description=validated_request_data["description"]
        )
        setattr(risk, "instance_origin_data", origin_data)
        self.add_audit_instance_to_context(instance=RiskAuditInstance(risk))


class BulkCustomTransRisk(RiskMeta):
    name = gettext_lazy("批量人工转单")
    RequestSerializer = BulkCustomTransRiskReqSerializer

    def perform_request(self, validated_request_data):
        bulk_req_params = [
            {
                "risk_id": risk_id,
                "new_operators": validated_request_data["new_operators"],
                "description": validated_request_data["description"],
            }
            for risk_id in validated_request_data["risk_ids"]
        ]
        CustomTransRisk().bulk_request(bulk_req_params, ignore_exceptions=True)


class CustomAutoProcess(RiskMeta):
    name = gettext_lazy("人工执行处理套餐")
    RequestSerializer = CustomAutoProcessReqSerializer
    audit_action = ActionEnum.EDIT_RISK

    @transaction.atomic()
    def perform_request(self, validated_request_data):
        username = get_request_username()
        risk = get_object_or_404(Risk, risk_id=validated_request_data["risk_id"])
        origin_data = RiskInfoSerializer(risk).data
        # 获取处理套餐
        pa = get_object_or_404(ProcessApplication, id=validated_request_data["pa_id"])
        # 记录执行
        CustomProcess(risk_id=risk.risk_id, operator=username).run(
            custom_action=AutoProcess.__name__,
            pa_id=validated_request_data["pa_id"],
            pa_params=validated_request_data["pa_params"],
            auto_close_risk=validated_request_data["auto_close_risk"],
        )
        # 处理节点
        if pa.need_approve:
            processor = ForApprove
        else:
            processor = AutoProcess
        processor(risk_id=risk.risk_id, operator=username).run(
            pa_config={
                "pa_id": validated_request_data["pa_id"],
                "pa_params": validated_request_data["pa_params"],
                "auto_close_risk": validated_request_data["auto_close_risk"],
            }
        )
        setattr(risk, "instance_origin_data", origin_data)
        self.add_audit_instance_to_context(instance=RiskAuditInstance(risk))


class ForceRevokeApproveTicket(RiskMeta):
    name = gettext_lazy("强制撤销审批单据")
    RequestSerializer = ForceRevokeApproveTicketReqSerializer
    audit_action = ActionEnum.EDIT_RISK

    def perform_request(self, validated_request_data):
        risk = get_object_or_404(Risk, risk_id=validated_request_data["risk_id"])
        origin_data = RiskInfoSerializer(risk).data
        node = get_object_or_404(TicketNode, risk_id=risk.risk_id, id=validated_request_data["node_id"])
        if node.action != ForApprove.__name__:
            raise RiskStatusInvalid(message=gettext("节点类型异常 => %s") % node.action)
        sn = node.process_result["ticket"]["sn"]
        # 判断单据状态
        status = api.bk_itsm.ticket_approve_result(sn=[sn])[0]
        if status["current_status"] in TicketStatus.get_finished_status():
            sync_auto_result(node_id=node.id)
            return
        # 关单
        api.bk_itsm.operate_ticket(
            sn=sn,
            operator=bk_resource_settings.PLATFORM_AUTH_ACCESS_USERNAME,
            action_type=TicketOperate.WITHDRAW,
            action_message=str(TicketOperate.WITHDRAW.label),
        )
        sync_auto_result(node_id=node.id)
        setattr(risk, "instance_origin_data", origin_data)
        self.add_audit_instance_to_context(instance=RiskAuditInstance(risk))


class ForceRevokeAutoProcess(RiskMeta):
    name = gettext_lazy("强制终止处理套餐")
    RequestSerializer = ForceRevokeAutoProcessReqSerializer
    audit_action = ActionEnum.EDIT_RISK

    def perform_request(self, validated_request_data):
        risk = get_object_or_404(Risk, risk_id=validated_request_data["risk_id"])
        origin_data = RiskInfoSerializer(risk).data
        node = get_object_or_404(TicketNode, risk_id=risk.risk_id, id=validated_request_data["node_id"])
        if node.action != AutoProcess.__name__:
            raise RiskStatusInvalid(message=gettext("节点类型异常 => %s") % node.action)
        task_id = node.process_result["task"]["task_id"]
        # 判断套餐状态
        status = api.bk_sops.get_task_status(task_id=task_id, bk_biz_id=settings.DEFAULT_BK_BIZ_ID)
        if status["state"] in SOPSTaskStatus.get_finished_status():
            sync_auto_result(node_id=node.id)
            return
        # 终止套餐
        api.bk_sops.operate_task(bk_biz_id=settings.DEFAULT_BK_BIZ_ID, task_id=task_id, action=SOPSTaskOperation.REVOKE)
        sync_auto_result(node_id=node.id)
        setattr(risk, "instance_origin_data", origin_data)
        self.add_audit_instance_to_context(instance=RiskAuditInstance(risk))


class RetryAutoProcess(RiskMeta):
    name = gettext_lazy("重试处理套餐")
    RequestSerializer = RetryAutoProcessReqSerializer

    def perform_request(self, validated_request_data):
        risk = get_object_or_404(Risk, risk_id=validated_request_data["risk_id"])
        node = get_object_or_404(TicketNode, risk_id=risk.risk_id, id=validated_request_data["node_id"])
        task_id = node.process_result.get("task", {}).get("task_id", "")
        # 获取节点状态
        status = api.bk_sops.get_task_status(task_id=task_id, bk_biz_id=settings.DEFAULT_BK_BIZ_ID)
        # 对每个失败的节点，获取节点输入并重试
        for item in status["children"].values():
            if item["state"] != SOPSTaskStatus.FAILED:
                continue
            io_data = api.bk_sops.get_node_data(
                task_id=task_id, bk_biz_id=settings.DEFAULT_BK_BIZ_ID, node_id=item["id"]
            )
            api.bk_sops.operate_node(
                task_id=task_id,
                bk_biz_id=settings.DEFAULT_BK_BIZ_ID,
                node_id=item["id"],
                action=SOPSTaskOperation.RETRY,
                inputs=io_data["inputs"],
            )
        with transaction.atomic():
            node.status = TicketNodeStatus.RUNNING
            node.process_result["status"]["state"] = SOPSTaskStatus.RUNNING
            node.save(update_fields=["status", "process_result"])
            # 若最后一个节点为处理套餐节点，则更新状态为自动处理中，并清理处理人
            if risk.last_history.id == node.id:
                risk.status = RiskStatus.AUTO_PROCESS
                risk.current_operator = []
                risk.save(update_fields=["status", "current_operator"])
        # 更新节点信息
        sync_auto_result.apply_async(countdown=60, kwargs={"node_id": node.id})


class ReopenRisk(RiskMeta):
    name = gettext_lazy("重开单据")
    RequestSerializer = ReopenRiskReqSerializer
    audit_action = ActionEnum.EDIT_RISK

    def perform_request(self, validated_request_data):
        risk = get_object_or_404(Risk, risk_id=validated_request_data["risk_id"])
        origin_data = RiskInfoSerializer(risk).data
        ReOpen(risk_id=risk.risk_id, operator=get_request_username()).run(
            new_operators=validated_request_data["new_operators"],
            description=gettext("%s 重开单据，指定处理人 %s")
            % (get_request_username(), ";".join(validated_request_data["new_operators"])),
        )
        setattr(risk, "instance_origin_data", origin_data)
        self.add_audit_instance_to_context(instance=RiskAuditInstance(risk))


class GetRiskFieldsByStrategy(RiskMeta):
    name = gettext_lazy("获取风险字段")
    RequestSerializer = GetRiskFieldsByStrategyRequestSerializer
    ResponseSerializer = GetRiskFieldsByStrategyResponseSerializer
    many_response_data = True

    def perform_request(self, validated_request_data):
        get_app_info()
        # 获取基础字段
        fields = [
            {
                "key": field.field_name,
                "name": str(field.alias_name),
                "unique": field.field_name in (RiskFields.RAW_EVENT_ID.field_name, RiskFields.STRATEGY_ID.field_name),
            }
            for field in RiskFields().fields
        ]
        # 获取风险
        risk: Risk = Risk.objects.filter(strategy_id=validated_request_data["strategy_id"]).first()
        # 风险不存在时直接返回
        if risk is None:
            return fields
        # 补充风险拓展字段
        for key in risk.event_data.keys():
            fields.append(
                {
                    "key": f"{RiskFields.RISK_DATA.field_name}__{key}",
                    "name": f"{str(RiskFields.RISK_DATA.alias_name)}.{key}",
                }
            )
        # 补充风险证据字段
        with ignored(Exception, log_exception=False):
            origin_data = json.loads(json.loads(risk.event_evidence)[0].get("origin_data", "{}"))
            for key in origin_data.keys():
                fields.append(
                    {
                        "key": f"{RiskFields.RISK_EVIDENCE.field_name}__{key}",
                        "name": f"{str(RiskFields.RISK_EVIDENCE.alias_name)}.{key}",
                    }
                )
        return fields


class ProcessRiskTicket(RiskMeta):
    name = gettext_lazy("风险单据流转")

    def perform_request(self, validated_request_data):
        process_one_risk(risk_id=validated_request_data["risk_id"])
        return


class RiskExport(RiskMeta):
    name = gettext_lazy("风险导出")
    RequestSerializer = RiskExportReqSerializer

    def perform_request(self, validated_request_data):
        risk_view_type: str = validated_request_data.get("risk_view_type", "")
        risk_ids: List[str] = validated_request_data["risk_ids"]

        # 1. 获取有权限的风险列表
        risks: QuerySet[Risk] = Risk.prefetch_strategy_tags(Risk.load_authed_risks(action=ActionEnum.LIST_RISK)).filter(
            risk_id__in=risk_ids
        )

        authed_risk_ids = list(risks.values_list("risk_id", flat=True))
        no_authed_risk_ids = set(risk_ids) - set(authed_risk_ids)
        if no_authed_risk_ids:
            raise ExportRiskNoPermission(risk_ids=",".join(no_authed_risk_ids))

        # 2. 按策略分组风险
        strategies = list(
            Strategy.objects.filter(strategy_id__in=risks.values_list("strategy_id", flat=True)).order_by("strategy_id")
        )

        # 3. 获取策略的导出字段
        strategy_export_fields: Dict[str, List[ExportField]] = defaultdict(list)
        for strategy in strategies:
            risk_basic_fields = RiskExportField.export_fields()
            event_fields = [
                ExportField(
                    raw_name=f"{EVENT_EXPORT_FIELD_PREFIX}{field['field_name']}",
                    display_name=field["display_name"] or field["field_name"],
                )
                for field in strategy.event_data_field_configs
            ]
            strategy_export_fields[strategy.build_sheet_name()] = risk_basic_fields + event_fields

        # 4. 获取风险关联的事件,按策略分组并格式化数据
        bulk_events_params = []
        formatted_risks_by_strategy = defaultdict(list)
        risk_map = {risk.risk_id: risk for risk in risks}
        for risk_id in risk_ids:
            risk = risk_map[risk_id]
            # 时间转为 +8 时间字符串
            start_time = mstimestamp_to_date_string(int(risk.event_time.timestamp() * 1000))
            end_time = mstimestamp_to_date_string(int(datetime.now().timestamp() * 1000))
            risk_id = risk.risk_id
            bulk_events_params.append(
                {"risk_id": risk_id, "start_time": start_time, "end_time": end_time, "page": 1, "page_size": 10}
            )
        bulk_resp = resource.risk.list_event.bulk_request(bulk_events_params)
        for risk_id, resp in zip(risk_ids, bulk_resp):
            risk = risk_map[risk_id]
            events = resp["results"]
            risk_basic_data = {
                RiskExportField.RISK_ID: risk_id,
                RiskExportField.RISK_TITLE: risk.title,
                RiskExportField.EVENT_CONTENT: risk.event_content,
                RiskExportField.RISK_TAGS: data2string(
                    [tag_rel.tag.tag_name for tag_rel in risk.strategy.prefetched_tags]
                ),
                RiskExportField.EVENT_TYPE: data2string(risk.event_type),
                RiskExportField.RISK_LEVEL: str(RiskLevel.get_label(risk.strategy.risk_level)),
                RiskExportField.STRATEGY_NAME: risk.strategy.strategy_name,
                RiskExportField.STRATEGY_ID: risk.strategy.strategy_id,
                RiskExportField.RAW_EVENT_ID: risk.raw_event_id,
                RiskExportField.EVENT_END_TIME: risk.event_end_time.strftime(api_settings.DATETIME_FORMAT),
                RiskExportField.EVENT_TIME: risk.event_time.strftime(api_settings.DATETIME_FORMAT),
                RiskExportField.RISK_HAZARD: risk.strategy.risk_hazard,
                RiskExportField.RISK_GUIDANCE: risk.strategy.risk_guidance,
                RiskExportField.STATUS: str(RiskStatus.get_label(risk.status)),
                RiskExportField.RULE_ID: risk.rule_id,
                RiskExportField.OPERATOR: data2string(risk.operator),
                RiskExportField.CURRENT_OPERATOR: data2string(risk.current_operator),
                RiskExportField.NOTICE_USERS: data2string(risk.notice_users),
            }
            if not events:
                formatted_risks_by_strategy[risk.strategy.build_sheet_name()].append(risk_basic_data)
                continue
            for event in events:
                event_data = {
                    field["field_name"]: event.get("event_data", {}).get(field["field_name"], "")
                    for field in risk.strategy.event_data_field_configs
                }
                # 合并风险和事件字段，事件字段增加前缀
                formatted_risk = {
                    **risk_basic_data,
                    **{f"{EVENT_EXPORT_FIELD_PREFIX}{k}": v for k, v in event_data.items()},
                }
                formatted_risks_by_strategy[risk.strategy.build_sheet_name()].append(formatted_risk)

        # 5. 导出 excel
        exporter = MultiSheetRiskExporterXlsx()
        exporter.write(sheets_data=formatted_risks_by_strategy, sheets_headers=strategy_export_fields)
        excel_file = exporter.save()
        filename = RISK_EXPORT_FILE_NAME_TMP.format(
            risk_view_type=str(RiskViewType.get_label(risk_view_type)),
            datetime=datetime.now().strftime('%Y%m%d_%H%M%S'),
        )
        stream_response = FileResponse(excel_file, as_attachment=True, filename=filename)
        stream_response["Content-Type"] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        return stream_response


class ListEventFieldsByStrategy(RiskMeta):
    """
    新增接口：根据策略获取对应的事件字段；支持返回所有策略的事件字段（不传 strategy_ids）
    返回结构化字段 key，用于前端筛选构建
    """

    name = gettext_lazy("根据策略获取事件字段")
    RequestSerializer = ListEventFieldsByStrategyRequestSerializer
    ResponseSerializer = ListEventFieldsByStrategyResponseSerializer
    many_response_data = True

    def perform_request(self, validated_request_data):
        # 决定策略集合
        strategy_ids = validated_request_data.get("strategy_ids")
        if strategy_ids:
            strategies = Strategy.objects.filter(strategy_id__in=strategy_ids)
        else:
            strategies = Strategy.objects.all()

        results = set()
        for s in strategies:
            for config_name in ["event_data_field_configs"]:
                for cfg in getattr(s, config_name) or []:
                    field_name = cfg.get("field_name")
                    display_name = cfg.get("display_name") or field_name
                    if not field_name:
                        continue
                    results.add((field_name, display_name))
        return [
            {"field_name": field_name, "display_name": display_name, "id": f"{display_name}:{field_name}"}
            for field_name, display_name in results
        ]

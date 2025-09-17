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
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Type

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
from services.web.risk.constants import (
    EVENT_EXPORT_FIELD_PREFIX,
    EVENT_RESULT_TABLE_ID_KEY,
    RISK_EXPORT_FILE_NAME_TMP,
    RISK_LEVEL_ORDER_FIELD,
    RISK_RESULT_TABLE_ID_KEY,
    RISK_SHOW_FIELDS,
    STRATEGY_RESULT_TABLE_ID_KEY,
    STRATEGY_TAG_RESULT_TABLE_ID_KEY,
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
        base_queryset = self.load_risks(validated_request_data).order_by()

        if use_bkbase:
            paged_risks, page, risk_ids = self.retrieve_via_bkbase(
                base_queryset=base_queryset,
                request=request,
                order_field=order_field,
                event_filters=event_filters,
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

    def retrieve_via_db(self, base_queryset: QuerySet, request, order_field: str):
        risks = self._apply_ordering(base_queryset, order_field).only("pk")
        paged_queryset, page = paginate_queryset(
            queryset=risks, request=request, base_queryset=Risk.annotated_queryset()
        )
        paged_queryset = Risk.prefetch_strategy_tags(paged_queryset).order_by(order_field)
        paged_risks = list(paged_queryset)
        risk_ids = [risk.risk_id for risk in paged_risks]
        return paged_risks, page, risk_ids

    def retrieve_via_bkbase(
        self,
        base_queryset: QuerySet,
        request,
        order_field: str,
        event_filters: List[Dict[str, Any]],
    ):
        order_field_name = order_field.lstrip("-")
        order_direction = "DESC" if order_field.startswith("-") else "ASC"

        value_fields = ["risk_id", "strategy_id"]
        if order_field_name not in value_fields:
            value_fields.append(order_field_name)
        if order_field_name == RISK_LEVEL_ORDER_FIELD and "event_time" not in value_fields:
            value_fields.append("event_time")

        values_queryset = base_queryset.values(*value_fields).distinct()

        total = self._query_total_count(values_queryset, event_filters)
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
            q &= Q(strategy_id__in=Strategy.objects.filter(risk_level__in=risk_level).values("strategy_id"))

        # 标签筛选条件
        if tag_filter := validated_request_data.pop("tag_objs__in", None):
            strategy_ids = StrategyTag.objects.filter(tag_id__in=tag_filter).values_list('strategy_id', flat=True)
            q &= Q(strategy_id__in=strategy_ids)

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

    def _query_total_count(self, queryset: QuerySet, event_filters: List[Dict[str, Any]]) -> int:
        base_query = queryset.order_by()
        base_sql = self._clean_sql(str(base_query.query))
        base_sql = self._convert_to_bkbase_sql(base_sql)
        filtered_sql = self._build_filtered_subquery(base_sql, event_filters)
        count_sql = f"SELECT COUNT(*) AS count FROM ({filtered_sql}) AS risk_count"
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
    ) -> List[str]:
        base_query = queryset.order_by()
        base_sql = self._clean_sql(str(base_query.query))
        base_sql = self._convert_to_bkbase_sql(base_sql)
        filtered_sql = self._build_filtered_subquery(base_sql, event_filters)
        data_sql = self._append_order_and_limit(
            filtered_sql,
            order_field=order_field,
            order_direction=order_direction,
            limit=limit,
            offset=offset,
        )
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
                    config_key=RISK_RESULT_TABLE_ID_KEY, fallback=Risk._meta.db_table
                ),
                Strategy._meta.db_table: self._get_configured_table_name(
                    config_key=STRATEGY_RESULT_TABLE_ID_KEY, fallback=Strategy._meta.db_table
                ),
                StrategyTag._meta.db_table: self._get_configured_table_name(
                    config_key=STRATEGY_TAG_RESULT_TABLE_ID_KEY, fallback=StrategyTag._meta.db_table
                ),
                "risk_event": self._get_configured_table_name(
                    config_key=EVENT_RESULT_TABLE_ID_KEY, fallback="risk_event"
                ),
            }
        return self._bkbase_table_map

    def _get_configured_table_name(self, *, config_key: str, fallback: str) -> str:
        return GlobalMetaConfig.get(config_key=config_key, default=fallback)

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

    def _convert_to_bkbase_sql(self, sql: str) -> str:
        if not sql:
            return sql
        table_map = self._get_bkbase_table_map()
        if not table_map:
            return sql
        try:
            expression = sqlglot.parse_one(sql, read="mysql")
        except sqlglot.errors.ParseError:
            return sql

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
            node.set("catalog", exp.to_identifier(catalog) if catalog else None)
            node.set("db", exp.to_identifier(db) if db else None)
            node.set("this", exp.to_identifier(table))

            if not node.alias:
                node.set("alias", exp.TableAlias(this=exp.to_identifier(source)))
            return node

        transformed = expression.transform(transform_table)
        return transformed.sql(dialect="hive")

    def _get_risk_event_table_reference(self) -> str:
        table_name = self._get_bkbase_table_map().get("risk_event", "risk_event")
        formatted = self._format_table_identifier(table_name)
        return formatted or "risk_event"

    @classmethod
    def _format_table_identifier(cls, table_name: str) -> str:
        catalog, db, table = cls._split_table_parts(table_name)
        parts = [part for part in (catalog, db, table) if part]
        return ".".join(f"`{part}`" for part in parts)

    def _build_filtered_subquery(self, base_sql: str, event_filters: List[Dict[str, Any]]) -> str:
        subquery = f"SELECT * FROM ({base_sql}) AS base_query"
        conditions = [
            condition
            for index, item in enumerate(event_filters)
            if (condition := self._build_event_filter_condition(item, index))
        ]
        if not conditions:
            return subquery
        return f"{subquery} WHERE {' AND '.join(conditions)}"

    def _append_order_and_limit(
        self, subquery_sql: str, order_field: str, order_direction: str, limit: int, offset: int
    ) -> str:
        order_clause = self._build_order_clause(order_field, order_direction)
        limit_clause = ""
        if limit:
            limit_clause = f" LIMIT {int(limit)}"
            if offset:
                limit_clause += f" OFFSET {int(offset)}"
        return f"{subquery_sql}{order_clause}{limit_clause}"

    def _build_order_clause(self, order_field: str, order_direction: str) -> str:
        if order_field == RISK_LEVEL_ORDER_FIELD:
            field_expr = f"base_query.{self._quote_identifier(order_field)}"
            case_parts = []
            for index, level in enumerate([RiskLevel.LOW.value, RiskLevel.MIDDLE.value, RiskLevel.HIGH.value]):
                case_parts.append(f"WHEN {field_expr} = {self._format_sql_value(level)} THEN {index}")
            case_expression = f"CASE {field_expr} " + " ".join(case_parts) + " ELSE 99 END"
            return (
                f" ORDER BY {case_expression} {order_direction}, "
                f"base_query.{self._quote_identifier('event_time')} DESC"
            )
        field_expr = f"base_query.{self._quote_identifier(order_field)}"
        return f" ORDER BY {field_expr} {order_direction}"

    def _build_event_filter_condition(self, filter_item: Dict[str, Any], index: int) -> str:
        field = filter_item.get("field")
        field_source = filter_item.get("field_source")
        operator = filter_item.get("operator")
        value = filter_item.get("value")

        alias = f"risk_event_{index}"
        join_conditions = [f"{alias}.strategy_id = base_query.strategy_id"]

        field_expression = self._build_event_field_expression(alias, field_source, field)
        if not field_expression:
            return ""

        comparison = self._build_event_filter_expression(field_expression, operator, value)
        if not comparison:
            return ""

        join_clause = " AND ".join(join_conditions)
        table_reference = self._get_risk_event_table_reference()
        return f"EXISTS (SELECT 1 FROM {table_reference} {alias} WHERE {join_clause} AND {comparison})"

    def _build_event_field_expression(self, alias: str, field_source: str, field_name: str) -> str:
        if field_source == StrategyFieldSourceEnum.BASIC.value:
            return f"{alias}.{self._quote_identifier(field_name)}"

        if field_source == StrategyFieldSourceEnum.DATA.value:
            column = self._qualified_column(alias, "event_data")
        elif field_source == StrategyFieldSourceEnum.EVIDENCE.value:
            column = self._qualified_column(alias, "event_evidence")
        else:
            return ""

        json_path = self._build_json_path(field_name)
        return f"JSON_EXTRACT({column}, '{json_path}')"

    def _build_event_filter_expression(self, field_expr: str, operator: str, value: Any) -> str:
        if operator in {EventFilterOperator.EQUAL.value, EventFilterOperator.NOT_EQUAL.value}:
            formatted_value = self._format_sql_value(value)
            comparator = "=" if operator == EventFilterOperator.EQUAL.value else "!="
            if formatted_value == "NULL":
                return f"{field_expr} IS {'NOT ' if comparator == '!=' else ''}NULL"
            return f"{field_expr} {comparator} {formatted_value}"

        if operator in {
            EventFilterOperator.GREATER_THAN.value,
            EventFilterOperator.GREATER_THAN_EQUAL.value,
            EventFilterOperator.LESS_THAN.value,
            EventFilterOperator.LESS_THAN_EQUAL.value,
        }:
            if self._is_numeric_value(value):
                field_expr = f"CAST({field_expr} AS DOUBLE)"
                formatted_value = str(float(value))
            else:
                formatted_value = self._format_sql_value(value)
            return f"{field_expr} {operator} {formatted_value}"

        if operator in {EventFilterOperator.IN.value, EventFilterOperator.NOT_IN.value}:
            values = self._ensure_list(value)
            if not values:
                return "1=0" if operator == EventFilterOperator.IN.value else "1=1"
            formatted = ", ".join(self._format_sql_value(item) for item in values)
            return f"{field_expr} {operator} ({formatted})"

        if operator in {EventFilterOperator.CONTAINS.value, EventFilterOperator.NOT_CONTAINS.value}:
            pattern = self._escape_like_pattern(str(value))
            comparator = "NOT LIKE" if operator == EventFilterOperator.NOT_CONTAINS.value else "LIKE"
            return f"{field_expr} {comparator} '%{pattern}%' ESCAPE '\\\\'"

        return ""

    def _quote_identifier(self, identifier: str) -> str:
        parts = [part for part in identifier.split(".") if part]
        return ".".join(f"`{part}`" for part in parts)

    def _qualified_column(self, alias: str, column: str) -> str:
        return f"{alias}.{self._quote_identifier(column)}"

    def _build_json_path(self, field_name: str) -> str:
        safe_field = field_name.replace("\\", "\\\\").replace("'", "\\'")
        path_parts = [part for part in safe_field.split(".") if part]
        return "$" + "".join(f".{part}" for part in path_parts)

    def _ensure_list(self, value: Any) -> List[Any]:
        if value is None:
            return []
        if isinstance(value, (list, tuple, set)):
            return list(value)
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return [value]

    def _format_sql_value(self, value: Any) -> str:
        if value is None:
            return "NULL"
        if isinstance(value, bool):
            return "'true'" if value else "'false'"
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return str(value)
        escaped = str(value).replace("'", "''")
        return f"'{escaped}'"

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

        results = []
        for s in strategies:
            for cfg in s.event_basic_field_configs or []:
                field_name = cfg.get("field_name")
                display_name = cfg.get("display_name") or field_name
                if not field_name:
                    continue
                results.append(
                    {
                        "strategy_id": s.strategy_id,
                        "strategy_name": s.strategy_name,
                        "field_name": field_name,
                        "display_name": display_name,
                    }
                )

        return results


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

        results = []
        for s in strategies:
            for config_name in [
                "event_data_field_configs",
                "event_evidence_field_configs",
                "event_basic_field_configs",
            ]:
                for cfg in getattr(s, config_name) or []:
                    field_name = cfg.get("field_name")
                    display_name = cfg.get("display_name") or field_name
                    if not field_name:
                        continue
                    results.append(
                        {
                            "strategy_id": s.strategy_id,
                            "strategy_name": s.strategy_name,
                            "field_source": config_name.split("event_")[1].split("_field_configs")[0],
                            "field_name": field_name,
                            "display_name": display_name,
                        }
                    )

        return results

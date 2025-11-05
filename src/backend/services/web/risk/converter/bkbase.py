# -*- coding: utf-8 -*-
"""
事件检索 BKBase 检索链路表达式与执行逻辑。
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone as dt_timezone
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Set, Tuple

import sqlglot
from django.core.exceptions import EmptyResultSet
from django.db.models import QuerySet
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from sqlglot import exp
from sqlglot.errors import ParseError

logger = logging.getLogger(__name__)


def _convert_to_float(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


NUMERIC_EVENT_OPERATORS = {">", ">=", "<", "<="}


def build_event_json_path(field_name: str) -> str:
    safe_field = (field_name or "").replace("\\", "\\\\").replace("'", "\\'")
    path_parts = [part for part in safe_field.split(".") if part]
    return "$" + "".join(f".{part}" for part in path_parts)


@dataclass(frozen=True)
class EventFilterSpec:
    raw_field: str
    normalized_field: str
    operator: str
    value: Any
    json_path: str
    requires_numeric: bool

    @classmethod
    def from_raw(cls, item: Dict[str, Any], *, prefix: str) -> Optional["EventFilterSpec"]:
        if not isinstance(item, dict):
            return None
        raw_field = (item.get("field") or "").strip()
        if not raw_field:
            return None
        operator = str(item.get("operator") or "").upper()
        value = item.get("value")
        normalized = raw_field
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :].strip()
        if not normalized:
            return None
        json_path = build_event_json_path(normalized)
        requires_numeric = operator in NUMERIC_EVENT_OPERATORS and _convert_to_float(value) is not None
        return cls(
            raw_field=raw_field,
            normalized_field=normalized,
            operator=operator,
            value=value,
            json_path=json_path,
            requires_numeric=requires_numeric,
        )


class SQLHelper:
    """封装常用的 SQLGlot 构造函数。"""

    @staticmethod
    def column(alias: str, identifier: str) -> exp.Column:
        return exp.column(identifier, table=alias)

    @staticmethod
    def literal(value: Any) -> exp.Expression:
        if value is None:
            return exp.Null()
        if isinstance(value, bool):
            return exp.Literal.string("true" if value else "false")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return exp.Literal.number(str(value))
        return exp.Literal.string(str(value))

    @staticmethod
    def to_milliseconds(expression: exp.Expression) -> exp.Expression:
        unix_timestamp = exp.func("UNIX_TIMESTAMP", expression.copy())
        return exp.Mul(this=unix_timestamp, expression=exp.Literal.number("1000"))

    @staticmethod
    def add_seconds(expression: exp.Expression, seconds: int) -> exp.Expression:
        interval = exp.Interval(this=exp.Literal.number(str(seconds)), unit="SECOND")
        return exp.Add(this=expression.copy(), expression=interval)


class BkBaseQueryExpressionBuilder:
    """负责将 QuerySet 编译为 BKBase 可用的 SQL 与表达式。"""

    _TEXTUAL_CAST_PREFIXES = ("BINARY", "CHAR", "NCHAR", "VARCHAR", "NVARCHAR", "TEXT", "STRING")

    def __init__(self, table_map: Dict[str, str], storage_suffix: str) -> None:
        self.table_map = table_map or {}
        self.storage_suffix = (storage_suffix or "").strip()
        self._storage_suffix_lower = self.storage_suffix.lower()

    def compile_queryset_sql(self, queryset: QuerySet) -> Optional[str]:
        compiler = queryset.query.get_compiler(using=queryset.db)
        try:
            sql, params = compiler.as_sql()
        except EmptyResultSet:
            return None
        sql_text = (sql or "").strip()
        if params:
            sql_text = self._render_sql_with_params(sql_text, params)
        cleaned_sql = self._clean_sql(sql_text)
        if cleaned_sql:
            logger.info("BKBase base queryset SQL: %s", cleaned_sql)
        return cleaned_sql

    def convert_to_expression(self, sql: str) -> exp.Expression:
        if not sql:
            return sqlglot.parse_one("SELECT 1")
        if not self.table_map:
            return sqlglot.parse_one(sql, read="mysql")
        try:
            expression = sqlglot.parse_one(sql, read="mysql")
        except ParseError:
            expression = sqlglot.parse_one(sql, read="hive")

        def transform_table(node: exp.Expression) -> exp.Expression:
            if not isinstance(node, exp.Table):
                return node
            source = node.name
            if not source:
                return node
            target = self.table_map.get(source)
            if not target or target == source:
                return node

            catalog, db_name, table = self._split_table_parts(target)
            if not table:
                node.set("catalog", None)
                node.set("db", None)
                node.set("this", exp.Identifier(this=target, quoted=False))
            else:
                node.set("catalog", exp.Identifier(this=catalog, quoted=False) if catalog else None)
                node.set("db", exp.Identifier(this=db_name, quoted=False) if db_name else None)
                node.set("this", exp.Identifier(this=table, quoted=False))

            if not node.alias:
                node.set("alias", exp.TableAlias(this=exp.to_identifier(source)))
            return node

        transformed = expression.transform(transform_table)
        try:
            logger.info("BKBase transformed base SQL: %s", transformed.sql(dialect="mysql"))
        except Exception:  # noqa: BLE001
            logger.debug("Failed to serialize transformed BKBase SQL", exc_info=True)
        return transformed

    def format_table_identifier(self, table_name: str) -> str:
        catalog, db_name, table = self._split_table_parts(table_name)
        parts = [part for part in (catalog, db_name, table) if part]
        return ".".join(parts)

    def _render_sql_with_params(self, sql: str, params: Sequence[Any]) -> str:
        params_iter: Iterator[Any] = iter(params or [])

        def replacer(match: re.Match[str]) -> str:
            try:
                value = next(params_iter)
            except StopIteration:
                return match.group(0)
            return self._literal(value).sql("mysql")

        return re.sub(r"%s", replacer, sql)

    def _literal(self, value: Any) -> exp.Expression:
        if value is None:
            return exp.Null()
        if isinstance(value, bool):
            return exp.Literal.string("true" if value else "false")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return exp.Literal.number(str(value))
        if isinstance(value, datetime):
            if timezone.is_aware(value):
                localized = timezone.localtime(value)
            else:
                localized = timezone.make_aware(value, timezone.get_current_timezone())
            return exp.Literal.string(localized.strftime("%Y-%m-%d %H:%M:%S"))
        return exp.Literal.string(str(value))

    def _clean_sql(self, sql: str) -> str:
        cleaned = (sql or "").strip().rstrip(";")
        if not cleaned:
            return cleaned
        return self._normalize_query_expressions(cleaned)

    def _normalize_query_expressions(self, sql: str) -> str:
        try:
            expression = sqlglot.parse_one(sql, read="mysql")
        except ParseError:
            try:
                expression = sqlglot.parse_one(sql, read="hive")
            except ParseError:
                return sql

        def transform(node: exp.Expression) -> exp.Expression:
            if isinstance(node, exp.Like):
                literal = self._unwrap_text_cast(node.args.get("expression"))
                if literal is not None:
                    node.set("expression", literal)
            elif isinstance(node, (exp.GT, exp.GTE, exp.LT, exp.LTE, exp.EQ)):
                self._normalize_event_time_comparison(node)
            return node

        return expression.transform(transform).sql(dialect="mysql")

    def _unwrap_text_cast(self, expression: Optional[exp.Expression]) -> Optional[exp.Expression]:
        if isinstance(expression, (exp.Cast, exp.TryCast)):
            literal = expression.args.get("this")
            dtype = expression.args.get("to")
            if isinstance(literal, exp.Literal) and isinstance(dtype, exp.DataType):
                dtype_name = dtype.sql(dialect="mysql").upper()
                if any(dtype_name.startswith(prefix) for prefix in self._TEXTUAL_CAST_PREFIXES):
                    return literal.copy()
        return None

    def _normalize_event_time_comparison(self, node: exp.Expression) -> None:
        left = node.args.get("this")
        right = node.args.get("expression")
        if self._is_event_time_column(left):
            localized = self._localize_datetime_expression(right)
            if localized is not None:
                node.set("expression", localized)
        if self._is_event_time_column(right):
            localized = self._localize_datetime_expression(left)
            if localized is not None:
                node.set("this", localized)

    def _is_event_time_column(self, expression: Optional[exp.Expression]) -> bool:
        if not isinstance(expression, exp.Column):
            return False
        column_name = expression.name
        return column_name == "event_time"

    def _localize_datetime_expression(self, expression: Optional[exp.Expression]) -> Optional[exp.Expression]:
        target = expression
        if isinstance(target, exp.Paren):
            inner = self._localize_datetime_expression(target.args.get("this"))
            if inner is not None:
                target.set("this", inner)
                return target
            return None
        if not isinstance(target, exp.Literal) or not target.is_string:
            return None
        localized = self._localize_datetime_string(target.this)
        if localized is None:
            return None
        return exp.Literal.string(localized)

    def _localize_datetime_string(self, value: str) -> Optional[str]:
        raw = (value or "").strip()
        if not raw:
            return None
        dt_obj = parse_datetime(raw)
        if dt_obj is None:
            try:
                dt_obj = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                return None
        if timezone.is_naive(dt_obj):
            dt_obj = dt_obj.replace(tzinfo=dt_timezone.utc)
        localized = timezone.localtime(dt_obj, timezone.get_current_timezone())
        return localized.strftime("%Y-%m-%d %H:%M:%S")

    def _split_table_parts(self, table_name: str) -> Tuple[Optional[str], Optional[str], str]:
        cleaned = (table_name or "").strip().strip("`")
        if not cleaned:
            return None, None, ""
        parts = [part.strip().strip("`") for part in cleaned.split(".") if part.strip()]
        if not parts:
            return None, None, ""
        if (
            self._storage_suffix_lower
            and len(parts) >= 2
            and parts[-1].strip("`").lower() == self._storage_suffix_lower
        ):
            merged = f"{parts[-2]}.{parts[-1]}"
            parts = parts[:-2] + [merged]
        if len(parts) == 1:
            return None, None, parts[0]
        if len(parts) == 2:
            return None, parts[0], parts[1]
        if len(parts) == 3:
            return parts[0], parts[1], parts[2]
        return parts[-3], parts[-2], parts[-1]


class BkBaseFieldResolver:
    """负责解析排序字段、事件过滤等基础信息。"""

    EVENT_DATA_PREFIX = "event_data."

    def __init__(
        self,
        order_field: str,
        event_filters: Sequence[Dict[str, Any]],
        duplicate_field_map: Dict[int, Dict[str, Sequence[str]]],
    ) -> None:
        self.order_field = order_field or ""
        self._event_filter_specs: Tuple[EventFilterSpec, ...] = self._build_event_filter_specs(event_filters)
        self.duplicate_field_map = duplicate_field_map or {}
        self._numeric_event_filter_fields = self._collect_numeric_event_filter_fields()

    def resolve_value_fields(self, base_fields: Iterable[str]) -> List[str]:
        fields = list(base_fields)
        order_field_name = self.order_field.lstrip("-")
        if order_field_name and not self._is_event_order_field() and order_field_name not in fields:
            fields.append(order_field_name)
        if order_field_name == "strategy__risk_level" and "event_time" not in fields:
            fields.append("event_time")
        return fields

    def event_order_field(self) -> Optional[str]:
        normalized = self.order_field.lstrip("-")
        if normalized.startswith(self.EVENT_DATA_PREFIX):
            return normalized[len(self.EVENT_DATA_PREFIX) :].strip() or None
        return None

    def needs_deduplicate(self) -> bool:
        return bool(self.duplicate_field_map)

    def _is_event_order_field(self) -> bool:
        return self.event_order_field() is not None

    def event_order_requires_numeric_cast(self) -> bool:
        normalized = self.event_order_field()
        if not normalized:
            return False
        return normalized in self._numeric_event_filter_fields

    def _collect_numeric_event_filter_fields(self) -> Set[str]:
        return {spec.normalized_field for spec in self.event_filters if spec.requires_numeric}

    def _build_event_filter_specs(self, event_filters: Sequence[Dict[str, Any]]) -> Tuple[EventFilterSpec, ...]:
        specs: List[EventFilterSpec] = []
        for item in event_filters or []:
            spec = EventFilterSpec.from_raw(item, prefix=self.EVENT_DATA_PREFIX)
            if spec is not None:
                specs.append(spec)
        return tuple(specs)

    @property
    def event_filters(self) -> Tuple[EventFilterSpec, ...]:
        return self._event_filter_specs


class BaseRiskSelectBuilder(SQLHelper):
    """负责构建风险基础查询表达式。"""

    def build(self, base_expression: exp.Expression) -> exp.Select:
        prepared = self._prepare_base_expression(base_expression)
        # Wrap ORM-produced SQL as subquery so later joins reference a stable alias.
        return exp.select(exp.Star()).from_(
            exp.Subquery(
                this=prepared,
                alias=exp.TableAlias(this=exp.to_identifier("base_query")),
            )
        )

    @staticmethod
    def _prepare_base_expression(expression: exp.Expression) -> exp.Expression:
        copy_expr = expression.copy()
        if isinstance(copy_expr, exp.Select):
            copy_expr.set("order", None)
            copy_expr.set("limit", None)
            copy_expr.set("offset", None)
        return copy_expr


@dataclass
class BkBaseQueryComponents:
    base_query: exp.Select
    matched_event: exp.Subquery

    def clone(self) -> "BkBaseQueryComponents":
        # All downstream builders mutate sqlglot nodes; clone to keep originals reusable.
        return BkBaseQueryComponents(
            base_query=self.base_query.copy(),
            matched_event=self.matched_event.copy(),
        )


class BkBaseQueryComponentsBuilder:
    """构建 risk + event 的基础组件集合。"""

    def __init__(
        self,
        resolver: BkBaseFieldResolver,
        duplicate_field_map: Dict[int, Dict[str, Sequence[str]]],
        thedate_range: Optional[Tuple[str, str]],
        table_name: str,
    ) -> None:
        self.resolver = resolver
        self.duplicate_field_map = duplicate_field_map
        self.thedate_range = thedate_range
        self.table_name = table_name
        self.base_builder = BaseRiskSelectBuilder()

    def build(self, base_expression: exp.Expression) -> BkBaseQueryComponents:
        base_query = self.base_builder.build(base_expression)
        matched_event_subquery = MatchedEventSubqueryBuilder(
            self.resolver,
            self.duplicate_field_map,
            self.thedate_range,
            self.table_name,
        ).build()
        return BkBaseQueryComponents(
            base_query=base_query,
            matched_event=matched_event_subquery,
        )


class MatchedEventSubqueryBuilder(SQLHelper):
    """构建匹配事件的子查询，包含去重与过滤逻辑。"""

    STORAGE_ALIAS = "matched_event_src_base"

    def __init__(
        self,
        resolver: BkBaseFieldResolver,
        duplicate_field_map: Dict[int, Dict[str, Sequence[str]]],
        thedate_range: Optional[Tuple[str, str]],
        table_name: str,
    ) -> None:
        self.resolver = resolver
        self.duplicate_field_map = duplicate_field_map or {}
        self.thedate_range = thedate_range
        self.table_name = table_name

    def build(self) -> exp.Subquery:
        final_alias = "matched_event_src"
        base_alias = self.STORAGE_ALIAS
        base_table = self._with_thedate(exp.to_table(self.table_name).copy(), base_alias)
        select_expressions = [
            self.column(final_alias, "strategy_id"),
            self.column(final_alias, "raw_event_id"),
            self.column(final_alias, "event_data"),
            self.column(final_alias, "dteventtimestamp"),
        ]
        select_query = exp.select(*select_expressions).from_(base_table.as_(final_alias))

        filter_conditions = self._build_event_filter_conditions(final_alias)
        if filter_conditions is not None:
            select_query = select_query.where(filter_conditions)

        filtered_alias = f"{final_alias}_filtered"
        filtered_subquery = exp.Subquery(
            this=select_query,
            alias=exp.TableAlias(this=exp.to_identifier(filtered_alias)),
        )

        deduplicated_subquery = self._apply_deduplicate(
            filtered_subquery,
            final_alias=final_alias,
            base_alias=filtered_alias,
        )

        deduplicated_subquery.set("alias", exp.TableAlias(this=exp.to_identifier("matched_event")))
        return deduplicated_subquery

    def _with_thedate(self, base_table: exp.Expression, alias: str) -> exp.Expression:
        table_as = base_table.as_(alias)
        if not self.thedate_range:
            return table_as
        start_date, end_date = self.thedate_range
        if not start_date or not end_date:
            return table_as
        inner_select = (
            exp.select(exp.Star())
            .from_(table_as)
            .where(
                exp.and_(
                    exp.GTE(
                        this=self.column(alias, "thedate"),
                        expression=self.literal(start_date),
                    ),
                    exp.LTE(
                        this=self.column(alias, "thedate"),
                        expression=self.literal(end_date),
                    ),
                )
            )
        )
        return exp.Subquery(
            this=inner_select,
            alias=exp.TableAlias(this=exp.to_identifier(alias)),
        )

    def _apply_deduplicate(
        self,
        table_expr: exp.Expression,
        *,
        final_alias: str,
        base_alias: str,
    ) -> exp.Subquery:
        partition_key = self._build_duplicate_partition_key_expression(base_alias)
        if partition_key is None:
            partition_key = self._default_partition_key_expression(base_alias)

        partition_expressions = [
            self.column(base_alias, "strategy_id"),
            partition_key,
        ]
        order_expressions = [
            exp.Ordered(
                this=self.column(base_alias, "dteventtimestamp"),
                desc=True,
            ),
            exp.Ordered(
                this=self.column(base_alias, "raw_event_id"),
                desc=True,
            ),
        ]
        window = exp.Window(
            this=exp.func("ROW_NUMBER"),
            partition_by=partition_expressions,
            order=exp.Order(expressions=order_expressions),
        )

        ranked_select = exp.select(
            self.column(base_alias, "strategy_id"),
            self.column(base_alias, "raw_event_id"),
            self.column(base_alias, "event_data"),
            self.column(base_alias, "dteventtimestamp"),
            exp.alias_(window, "_row_number"),
        ).from_(table_expr)

        ranked_alias = f"{final_alias}_ranked"
        ranked_subquery = exp.Subquery(
            this=ranked_select,
            alias=exp.TableAlias(this=exp.to_identifier(ranked_alias)),
        )

        filtered_select = (
            exp.select(
                self.column(ranked_alias, "strategy_id"),
                self.column(ranked_alias, "raw_event_id"),
                self.column(ranked_alias, "event_data"),
                self.column(ranked_alias, "dteventtimestamp"),
            )
            .from_(ranked_subquery)
            .where(
                exp.EQ(
                    this=self.column(ranked_alias, "_row_number"),
                    expression=exp.Literal.number("1"),
                )
            )
        )
        return exp.Subquery(
            this=filtered_select,
            alias=exp.TableAlias(this=exp.to_identifier(final_alias)),
        )

    def _build_duplicate_partition_key_expression(self, alias: str) -> Optional[exp.Expression]:
        if not self.duplicate_field_map:
            return None

        cases: List[Tuple[exp.Expression, exp.Expression]] = []
        for strategy_id, source_fields in self.duplicate_field_map.items():
            field_expressions: List[exp.Expression] = []
            for source, fields in source_fields.items():
                for field_name in fields:
                    expr = self._build_duplicate_partition_value_expression(alias, field_name, source)
                    if expr is not None:
                        field_expressions.append(expr)
            if not field_expressions:
                continue
            concat_expr = self._concat_partition_values(field_expressions)
            condition = exp.EQ(
                this=self.column(alias, "strategy_id"),
                expression=exp.Literal.number(str(strategy_id)),
            )
            cases.append((condition, concat_expr))

        if not cases:
            return None

        case_expr = exp.Case()
        for condition, value in cases:
            case_expr = case_expr.when(condition, value)
        return case_expr.else_(self._default_partition_key_expression(alias))

    def _concat_partition_values(self, expressions: List[exp.Expression]) -> exp.Expression:
        safe_expressions = [
            exp.func(
                "COALESCE",
                exp.Cast(this=expr.copy(), to=exp.DataType.build("CHAR")),
                exp.Literal.string(""),
            )
            for expr in expressions
        ]
        return exp.func("CONCAT_WS", exp.Literal.string("||"), *safe_expressions)

    def _build_duplicate_partition_value_expression(
        self, alias: str, field_name: str, source: str
    ) -> Optional[exp.Expression]:
        if source == "basic":
            return self.column(alias, field_name)
        if source == "data":
            column = self.column(alias, "event_data")
        elif source == "evidence":
            column = self.column(alias, "event_evidence")
        else:
            return None
        json_path = build_event_json_path(field_name)
        return exp.func("JSON_EXTRACT_STRING", column, exp.Literal.string(json_path))

    def _default_partition_key_expression(self, alias: str) -> exp.Expression:
        timestamp_as_text = exp.Cast(this=self.column(alias, "dteventtimestamp"), to=exp.DataType.build("CHAR"))
        return exp.func(
            "COALESCE",
            self.column(alias, "raw_event_id"),
            timestamp_as_text,
        )

    def _build_event_filter_conditions(self, alias: str) -> Optional[exp.Expression]:
        comparisons: List[exp.Expression] = []
        for filter_spec in self.resolver.event_filters:
            if (isinstance(filter_spec.value, str) and not filter_spec.value) or filter_spec.value is None:
                continue
            field_expr = exp.func(
                "JSON_EXTRACT_STRING",
                self.column(alias, "event_data"),
                exp.Literal.string(filter_spec.json_path),
            )
            comparison = self._build_event_filter_expression(field_expr, filter_spec)
            if comparison is not None:
                comparisons.append(comparison)
        if not comparisons:
            return None
        combined = comparisons[0]
        for comparison in comparisons[1:]:
            combined = exp.and_(combined, comparison)
        return combined

    def _build_event_filter_expression(
        self, field_expr: exp.Expression, filter_spec: EventFilterSpec
    ) -> Optional[exp.Expression]:
        value = filter_spec.value
        operator = filter_spec.operator

        if operator == "=":
            if value is None:
                return exp.Is(this=field_expr.copy(), expression=exp.Null())
            return exp.EQ(this=field_expr.copy(), expression=self.literal(value))
        if operator == "!=":
            if value is None:
                return exp.not_(exp.Is(this=field_expr.copy(), expression=exp.Null()))
            return exp.NEQ(this=field_expr.copy(), expression=self.literal(value))
        if operator == "CONTAINS":
            pattern = self._escape_like_pattern(str(value))
            return exp.Like(
                this=field_expr.copy(),
                expression=exp.Literal.string(f"%{pattern}%"),
            )
        if operator == "NOT CONTAINS":
            pattern = self._escape_like_pattern(str(value))
            like_expr = exp.Like(
                this=field_expr.copy(),
                expression=exp.Literal.string(f"%{pattern}%"),
            )
            return exp.not_(like_expr)
        if operator == "IN":
            values = self._ensure_list(value)
            if not values:
                return exp.false()
            # IN list comparisons remain string based, align with JSON_EXTRACT_STRING typing.
            return exp.In(
                this=field_expr.copy(),
                expressions=[self.literal(item) for item in values],
            )
        if operator == "NOT IN":
            values = self._ensure_list(value)
            if not values:
                return exp.true()
            in_expr = exp.In(
                this=field_expr.copy(),
                expressions=[self.literal(item) for item in values],
            )
            return exp.not_(in_expr)
        if operator in NUMERIC_EVENT_OPERATORS:
            comparator = {
                ">": exp.GT,
                ">=": exp.GTE,
                "<": exp.LT,
                "<=": exp.LTE,
            }[operator]
            numeric_value = _convert_to_float(value)
            if numeric_value is not None:
                # Cast JSON string to DOUBLE before comparing to avoid lexicographical ordering.
                cast_expr = exp.Cast(this=field_expr.copy(), to=exp.DataType.build("DOUBLE"))
                literal = exp.Literal.number(format(numeric_value, "g"))
                return comparator(this=cast_expr, expression=literal)
            return comparator(this=field_expr.copy(), expression=self.literal(value))
        return None

    @staticmethod
    def _escape_like_pattern(value: str) -> str:
        return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

    @staticmethod
    def _ensure_list(value: Any) -> List[Any]:
        if value is None:
            return []
        if isinstance(value, (list, tuple, set)):
            return list(value)
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return [value]


class FinalSelectAssembler(SQLHelper):
    """将基础风险查询与事件子查询组合成最终 SQL。"""

    def __init__(self, resolver: BkBaseFieldResolver) -> None:
        self.resolver = resolver

    def assemble_count_query(self, base_query: exp.Select, matched_event: exp.Subquery) -> exp.Select:
        joined = self._join_events(base_query, matched_event)
        filtered_copy = joined.copy()
        filtered_copy.set("order", None)
        filtered_copy.set("limit", None)
        filtered_copy.set("offset", None)
        filtered_copy.set(
            "expressions",
            [
                exp.alias_(
                    exp.Literal.number(1),
                    "__dummy",
                )
            ],
        )
        subquery = exp.Subquery(
            this=filtered_copy,
            alias=exp.TableAlias(this=exp.to_identifier("risk_count")),
        )
        count_expr = exp.func("COUNT", exp.Star())
        return exp.select(exp.alias_(count_expr, "count")).from_(subquery).limit(exp.Literal.number(1))

    def assemble_data_query(
        self,
        base_query: exp.Select,
        matched_event: exp.Subquery,
        *,
        order_field: str,
        order_direction: str,
        limit: int,
        offset: int,
    ) -> exp.Select:
        joined = self._join_events(base_query, matched_event)

        projections = list(joined.expressions or [exp.Star()])
        if not projections:
            projections = [exp.Star()]
        projections.append(
            # Expose matched event payload so Django objects can attach filtered_event_data later.
            exp.alias_(
                self.column("matched_event", "event_data"),
                "__matched_event_data",
            )
        )
        event_order_field = self.resolver.event_order_field()
        if event_order_field:
            order_expression = exp.func(
                "JSON_EXTRACT_STRING",
                self.column("matched_event", "event_data"),
                exp.Literal.string(build_event_json_path(event_order_field)),
            )
            if self.resolver.event_order_requires_numeric_cast():
                order_expression = exp.Cast(this=order_expression, to=exp.DataType.build("DOUBLE"))
            projections.append(exp.alias_(order_expression, "__order_event_field"))
        joined.set("expressions", projections)

        order_expressions = self._build_order_expressions(order_field, order_direction)
        if order_expressions:
            joined = joined.order_by(*order_expressions)
        if limit:
            joined = joined.limit(int(limit))
            if offset:
                joined = joined.offset(int(offset))
        elif offset:
            joined = joined.offset(int(offset))

        return joined

    def _join_events(self, base_query: exp.Select, matched_event: exp.Subquery) -> exp.Select:
        join_conditions = [
            exp.EQ(
                this=self.column("matched_event", "strategy_id"),
                expression=self.column("base_query", "strategy_id"),
            ),
            exp.EQ(
                this=self.column("matched_event", "raw_event_id"),
                expression=self.column("base_query", "raw_event_id"),
            ),
        ]
        join_conditions.extend(self._build_join_timestamp_conditions("matched_event"))
        combined = join_conditions[0]
        for condition in join_conditions[1:]:
            combined = exp.and_(combined, condition)

        return base_query.join(
            matched_event,
            join_type="inner",
            on=combined,
        )

    def _build_order_expressions(self, order_field: str, order_direction: str) -> List[exp.Expression]:
        if not order_field:
            return []
        descending = order_direction.upper() == "DESC"
        event_field = self.resolver.event_order_field()
        if event_field:
            return [
                exp.Ordered(this=exp.column("__order_event_field"), desc=descending),
                exp.Ordered(
                    this=self.column("matched_event", "dteventtimestamp"),
                    desc=True,
                ),
            ]
        field_name = order_field.lstrip("-")
        from services.web.risk.constants import RISK_LEVEL_ORDER_FIELD  # noqa
        from services.web.strategy_v2.constants import RiskLevel  # noqa

        base_column = self._base_query_column(field_name)
        if field_name == RISK_LEVEL_ORDER_FIELD:
            rank_expr = self._build_risk_level_rank_expression(base_column)
            return [
                exp.Ordered(this=rank_expr, desc=descending),
                exp.Ordered(this=self._base_query_column("event_time"), desc=True),
            ]
        return [exp.Ordered(this=base_column, desc=descending)]

    def _build_join_timestamp_conditions(self, alias: str) -> List[exp.Expression]:
        event_timestamp = self.column(alias, "dteventtimestamp")
        start_ms = self.to_milliseconds(self.column("base_query", "event_time"))
        end_ms = self.to_milliseconds(self.add_seconds(self.column("base_query", "event_end_time"), seconds=1))
        return [
            exp.GTE(this=event_timestamp.copy(), expression=start_ms),
            exp.LT(this=event_timestamp.copy(), expression=end_ms),
        ]

    def _build_risk_level_rank_expression(self, field_expr: exp.Expression) -> exp.Expression:
        from services.web.strategy_v2.constants import RiskLevel  # noqa

        case_expr = exp.Case()
        for index, level in enumerate([RiskLevel.LOW.value, RiskLevel.MIDDLE.value, RiskLevel.HIGH.value]):
            case_expr = case_expr.when(
                exp.EQ(this=field_expr.copy(), expression=self.literal(level)),
                exp.Literal.number(str(index)),
            )
        return case_expr.else_(exp.Literal.number("99"))

    def _base_query_column(self, field_name: str) -> exp.Column:
        normalized = field_name.split("__")[-1] if "__" in field_name else field_name
        return self.column("base_query", normalized)


class BkBaseCountQueryBuilder:
    """构建统计数量的 SQL。"""

    def __init__(self, assembler: FinalSelectAssembler) -> None:
        self.assembler = assembler

    def build(self, components: BkBaseQueryComponents) -> exp.Select:
        clones = components.clone()
        # COUNT 使用去除排序的拷贝，避免多余的 LIMIT/OFFSET 干扰。
        return self.assembler.assemble_count_query(
            clones.base_query,
            clones.matched_event,
        )


class BkBaseDataQueryBuilder:
    """构建数据查询 SQL。"""

    def __init__(self, assembler: FinalSelectAssembler) -> None:
        self.assembler = assembler

    def build(
        self,
        components: BkBaseQueryComponents,
        *,
        order_field: str,
        order_direction: str,
        limit: int,
        offset: int,
    ) -> exp.Select:
        clones = components.clone()
        # 生成 data SQL 时复用克隆，保持 planner 中的组件引用可安全再次使用。
        return self.assembler.assemble_data_query(
            clones.base_query,
            clones.matched_event,
            order_field=order_field,
            order_direction=order_direction,
            limit=limit,
            offset=offset,
        )


class BkBasePaginationPlanner:
    """处理页码与 limit/offset 计算。"""

    def __init__(self, pagination_class):
        self.pagination_class = pagination_class

    def paginate(self, total: int, request) -> Tuple[Any, int, int]:
        page = self.pagination_class()
        page.paginate_queryset(range(total), request)

        limit = 0
        offset = 0
        page_obj = getattr(page, "page", None)
        if page_obj:
            # Default paginator exposes per_page via Django Paginator.
            limit = getattr(page_obj.paginator, "per_page", 0)
            if limit:
                offset = (page_obj.number - 1) * limit
        if limit == 0 and total:
            limit = total
        return page, limit, offset


class BkBaseSQLRunner:
    """执行 SQL 并记录日志。"""

    def __init__(self, api_client):
        self.api_client = api_client
        self.sql_statements: List[str] = []

    def run_count(self, query: exp.Select) -> int:
        count_sql = query.sql(dialect="mysql")
        logger.info("BKBase count SQL: %s", count_sql)
        self.sql_statements.append(count_sql)
        count_resp = self.api_client(sql=count_sql) or {}
        results = count_resp.get("list") or []
        try:
            return int(results[0].get("count", 0)) if results else 0
        except (TypeError, ValueError):
            return 0

    def run_data(self, query: exp.Select) -> List[Dict[str, Any]]:
        data_sql = query.sql(dialect="mysql")
        logger.info("BKBase data SQL: %s", data_sql)
        self.sql_statements.append(data_sql)
        data_resp = self.api_client(sql=data_sql) or {}
        return data_resp.get("list") or []


class BkBaseCountExecutor:
    """负责执行 count 查询。"""

    def __init__(
        self,
        components_builder: BkBaseQueryComponentsBuilder,
        count_query_builder: BkBaseCountQueryBuilder,
        sql_runner: BkBaseSQLRunner,
    ) -> None:
        self.components_builder = components_builder
        self.count_query_builder = count_query_builder
        self.sql_runner = sql_runner

    def execute(self, base_expression: exp.Expression) -> Tuple[int, BkBaseQueryComponents]:
        components = self.components_builder.build(base_expression)
        count_query = self.count_query_builder.build(components)
        total = self.sql_runner.run_count(count_query)
        # 返回组件以便数据查询沿用同一份 matched_event 子查询。
        return total, components


class BkBaseDataExecutor:
    """负责执行数据查询。"""

    def __init__(
        self,
        components_builder: BkBaseQueryComponentsBuilder,
        data_query_builder: BkBaseDataQueryBuilder,
        sql_runner: BkBaseSQLRunner,
    ) -> None:
        self.components_builder = components_builder
        self.data_query_builder = data_query_builder
        self.sql_runner = sql_runner

    def execute(
        self,
        base_expression: exp.Expression,
        *,
        order_field: str,
        order_direction: str,
        limit: int,
        offset: int,
        components: Optional[BkBaseQueryComponents] = None,
    ) -> List[Dict[str, Any]]:
        base_components = components or self.components_builder.build(base_expression)
        data_query = self.data_query_builder.build(
            base_components,
            order_field=order_field,
            order_direction=order_direction,
            limit=limit,
            offset=offset,
        )
        return self.sql_runner.run_data(data_query)


class BkBaseEventJoiner:
    """根据风险列表与匹配事件结果，补齐 ORM 对象并注入过滤后的事件数据。"""

    def __init__(self, list_risk_resource):
        self.list_risk_resource = list_risk_resource

    def attach_events(
        self,
        risks: List[Any],
        risk_rows: List[Dict[str, Any]],
    ) -> None:
        if not risk_rows:
            return
        matched_event_map = {}
        for row in risk_rows:
            raw = row.get("__matched_event_data") or row.get("matched_event_data")
            matched_event_map[row["risk_id"]] = self._normalize_matched_event_data(raw)
        if not matched_event_map:
            return
        for risk in risks:
            data = matched_event_map.get(risk.risk_id)
            if data is not None:
                setattr(risk, "filtered_event_data", data)

    @staticmethod
    def _normalize_matched_event_data(raw: Any) -> Dict[str, Any]:
        if raw in (None, "", []):
            return {}
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, bytes):
            try:
                raw = raw.decode("utf-8")
            except Exception:  # noqa: BLE001
                return {}
        if isinstance(raw, str):
            try:
                parsed = json.loads(raw)
            except (TypeError, ValueError, json.JSONDecodeError):
                return {}
            if isinstance(parsed, dict):
                return parsed
            return {}
        return {}


class BkBaseResponseAssembler:
    """拼装最终响应结构。"""

    def __init__(self, list_risk_resource, serializer_cls):
        self.list_risk_resource = list_risk_resource
        self.serializer_cls = serializer_cls

    def build_response(self, risks: List[Any], page, sql_statements: List[str]) -> Dict[str, Any]:
        experiences = self.list_risk_resource._fetch_experiences([risk.risk_id for risk in risks])
        for risk in risks:
            setattr(risk, "experiences", experiences.get(risk.risk_id, 0))
        response = page.get_paginated_response(data=self.serializer_cls(instance=risks, many=True).data).data
        response["sql"] = sql_statements
        return response


class BkBaseQueryPlanner:
    """调度 count/data 执行与分页处理。"""

    def __init__(
        self,
        *,
        queryset_expression: exp.Expression,
        count_executor: BkBaseCountExecutor,
        data_executor: BkBaseDataExecutor,
        pagination_planner: BkBasePaginationPlanner,
        sql_runner: BkBaseSQLRunner,
    ):
        self.queryset_expression = queryset_expression
        self.count_executor = count_executor
        self.data_executor = data_executor
        self.pagination_planner = pagination_planner
        self.sql_runner = sql_runner

    def plan(
        self,
        request,
        *,
        order_field: str,
        order_direction: str,
    ) -> Tuple[List[Dict[str, Any]], Any]:
        total, components = self.count_executor.execute(self.queryset_expression)
        page, limit, offset = self.pagination_planner.paginate(total, request)

        data_rows: List[Dict[str, Any]] = []
        if total:
            # 复用 count 阶段生成的组件，避免重复构造冗长的 sqlglot AST。
            data_rows = self.data_executor.execute(
                self.queryset_expression,
                order_field=order_field,
                order_direction=order_direction,
                limit=limit,
                offset=offset,
                components=components,
            )

        return data_rows, page

    @property
    def sql_statements(self) -> List[str]:
        return self.sql_runner.sql_statements

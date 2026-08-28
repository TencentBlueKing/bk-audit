"""受控日志明细查询：投影补列、脱敏后裁剪，绝不返回原始查询细节。"""

import re
import time
from typing import Any, Dict, Iterable, List, Sequence

from bk_resource.base import Empty
from django.conf import settings
from django.utils import timezone

from api.bk_base.constants import StorageType
from core.utils.data import extract_nested_value
from services.web.query.ai_assistant.constants import SNAPSHOT_DEFAULT_COLUMNS
from services.web.query.ai_assistant.exceptions import LogQueryResponseTooLarge
from services.web.query.ai_assistant.log_tools.context import (
    LogQueryContext,
    LogQueryContextService,
)
from services.web.query.ai_assistant.log_tools.errors import map_log_query_error
from services.web.query.ai_assistant.log_tools.query_sync import safe_query_sync
from services.web.query.ai_assistant.log_tools.schemas import (
    LOG_SEARCH_RESPONSE_MAX_BYTES,
    LogDetailColumn,
    LogFieldRef,
    LogSearchPagination,
    SearchLogsRequest,
    SearchLogsResponse,
)
from services.web.query.ai_assistant.log_tools.sql import ProjectedLogSQLBuilder
from services.web.query.ai_assistant.schemas import QuerySummary, SelectionFieldOption
from services.web.query.constants import DEFAULT_COLLECTOR_SORT_LIST, DEFAULT_TIMEDELTA
from services.web.query.search_data import SearchDataParser
from services.web.query.utils.field import LOG_SEARCH_ALL_FIELDS_MAP
from services.web.query.utils.field_map import FieldMapHandler


class LogDetailSearchService:
    """执行受控日志明细查询，并在最终投影前完成敏感数据处理。

    设计意图：即使调用方只请求一个 JSON 子字段，也必须额外查询敏感判定所需
    三列，并将完整行交给 SearchDataParser；投影发生在脱敏之后，辅助列永不外泄。
    """

    _SENSITIVE_HELPER_FIELDS = (
        LogFieldRef(raw_name="system_id"),
        LogFieldRef(raw_name="resource_type_id"),
        LogFieldRef(raw_name="action_id"),
    )
    _DEFAULT_FIELDS = tuple(LogFieldRef(raw_name=raw_name) for raw_name, _display_name in SNAPSHOT_DEFAULT_COLUMNS)

    @classmethod
    def search(cls, *, username: str, namespace: str, request: SearchLogsRequest) -> SearchLogsResponse:
        """构建授权 Context，执行一次 data/count 批量查询并返回脱敏分页结果。"""

        # 服务入口重新校验，防御内部调用通过 model_construct 绕过协议边界。
        request = SearchLogsRequest.model_validate(request.model_dump())
        context = LogQueryContextService.build(username=username, namespace=namespace, condition=request.condition)
        requested_fields = tuple(request.fields) if request.fields is not None else cls._DEFAULT_FIELDS
        query_fields = cls._with_helpers(requested_fields)
        try:
            data_response, count_response, took_ms = cls._query(context=context, request=request, fields=query_fields)
            rows = data_response["list"]
            total = cls._parse_total(count_response)
            safe_rows = SearchDataParser().parse_data(rows, username=username) if rows else []
            columns = cls._build_columns(namespace=namespace, fields=requested_fields)
            items = tuple(cls._project_item(row, requested_fields) for row in safe_rows)
            # took_ms 只覆盖紧邻的 Doris bulk_request；executed_at 在响应组装完成后记录。
            response = SearchLogsResponse(
                total=total,
                columns=columns,
                items=items,
                pagination=LogSearchPagination(
                    page=request.page,
                    page_size=request.page_size,
                    total=total,
                    returned_count=len(items),
                    has_more=request.page * request.page_size < total,
                ),
                query_summary=QuerySummary(
                    scope_type=request.condition.scope_type,
                    scope_id=request.condition.scope_id,
                    time_range={"start_time": request.condition.start_time, "end_time": request.condition.end_time},
                    condition_count=len(request.condition.conditions),
                    took_ms=took_ms,
                    executed_at="",
                ),
            )
            response.query_summary.executed_at = timezone.now().isoformat()
            cls._ensure_response_within_budget(response)
        except Exception as err:  # noqa: BLE001
            mapped_error = map_log_query_error(err)
            if mapped_error is err:
                raise
            raise mapped_error from err
        return response

    @classmethod
    def _query(
        cls, *, context: LogQueryContext, request: SearchLogsRequest, fields: Sequence[LogFieldRef]
    ) -> tuple[dict, dict, int]:
        """以同一授权条件批量执行数据和计数查询，且不记录 SQL 或条件值。"""

        if request.sort:
            sort_list = [{"order_field": item.field.raw_name, "order_type": item.direction} for item in request.sort]
            sorted_fields = {item["order_field"] for item in sort_list}
            # 用户排序在前；采集器唯一序列键补在后面，保证 OFFSET 分页稳定。
            sort_list.extend(item for item in DEFAULT_COLLECTOR_SORT_LIST if item["order_field"] not in sorted_fields)
        else:
            sort_list = DEFAULT_COLLECTOR_SORT_LIST
        builder = ProjectedLogSQLBuilder(
            table=context.table,
            conditions=list(context.conditions),
            sort_list=sort_list,
            page=request.page,
            page_size=request.page_size,
        )
        started_at = time.perf_counter()
        responses = safe_query_sync.bulk_request(
            [
                {"sql": builder.build_data_sql(fields), "prefer_storage": StorageType.DORIS.value},
                {"sql": builder.build_count_sql(), "prefer_storage": StorageType.DORIS.value},
            ]
        )
        took_ms = int((time.perf_counter() - started_at) * 1000)
        data_response, count_response = responses
        return data_response, count_response, took_ms

    @staticmethod
    def _parse_total(count_response: dict) -> int:
        """只接受 Doris 明确返回的非负整型计数，拒绝宽松类型转换。"""

        count = count_response["list"][0]["count"]
        if isinstance(count, bool):
            raise ValueError("invalid count")
        if isinstance(count, int) and count >= 0:
            return count
        if isinstance(count, str) and re.fullmatch(r"[0-9]+", count):
            return int(count)
        raise ValueError("invalid count")

    @classmethod
    def _with_helpers(cls, fields: Sequence[LogFieldRef]) -> tuple[LogFieldRef, ...]:
        """补齐脱敏身份列和 JSON 根列，避免子字段请求绕过敏感规则。"""

        required = [*fields, *cls._SENSITIVE_HELPER_FIELDS]
        required.extend(LogFieldRef(raw_name=field.raw_name) for field in fields if field.keys)
        unique_fields = []
        seen = set()
        for field in required:
            marker = (field.raw_name, tuple(field.keys))
            if marker not in seen:
                seen.add(marker)
                unique_fields.append(field)
        return tuple(unique_fields)

    @classmethod
    def _build_columns(cls, *, namespace: str, fields: Sequence[LogFieldRef]) -> List[LogDetailColumn]:
        """提供响应 key 与展示元信息，调用方无需推测字段路径。"""

        options_map = FieldMapHandler(
            fields=[field.raw_name for field in fields], timedelta=DEFAULT_TIMEDELTA, namespace=namespace
        ).field_map
        return [
            LogDetailColumn(
                field=field,
                key=cls._field_key(field),
                display_name=field.keys[-1]
                if field.keys
                else str(LOG_SEARCH_ALL_FIELDS_MAP[field.raw_name].description),
                description="" if field.keys else str(LOG_SEARCH_ALL_FIELDS_MAP[field.raw_name].description),
                options=[SelectionFieldOption(**option) for option in options_map.get(field.raw_name, [])] or None,
            )
            for field in fields
        ]

    @classmethod
    def _project_item(cls, row: Dict[str, Any], fields: Iterable[LogFieldRef]) -> Dict[str, Any]:
        """仅从已脱敏完整行按受控字段引用提取最终响应项。"""

        item = {}
        for field in fields:
            value = row.get(field.raw_name, Empty())
            if isinstance(value, Empty) and field.raw_name.lower() != field.raw_name:
                value = row.get(field.raw_name.lower(), Empty())
            value = extract_nested_value(value, field.keys)
            if not isinstance(value, Empty):
                item[cls._field_key(field)] = value
        return item

    @staticmethod
    def _field_key(field: LogFieldRef) -> str:
        return ".".join((field.raw_name, *field.keys))

    @staticmethod
    def _ensure_response_within_budget(response: SearchLogsResponse) -> None:
        """检查一次完整响应的 UTF-8 大小；超限显式失败而不截断或改写字段值。"""

        configured_limit = getattr(settings, "AI_LOG_SEARCH_RESPONSE_MAX_BYTES", LOG_SEARCH_RESPONSE_MAX_BYTES)
        response_limit = min(LOG_SEARCH_RESPONSE_MAX_BYTES, max(0, configured_limit))
        if len(response.model_dump_json().encode("utf-8")) > response_limit:
            raise LogQueryResponseTooLarge()

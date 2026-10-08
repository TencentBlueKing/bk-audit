"""日志字段元信息探索：声明根字段与按需 JSON 子字段采样。

根字段直接复用现有日志检索配置，不访问 Doris。调用方指定可见 JSON 父字段后，
服务才执行一次最小列采样，先预检条件字段权限，再逐行脱敏后推断字段元信息。
MCP 仅探索下一层；Web 可在同一批样本上返回父路径自身和全部对象后代。
"""

import json
from typing import Any, Dict, Iterable, List, Tuple

from bk_resource import api
from django.conf import settings
from pydantic import ValidationError as PydanticValidationError

from api.bk_base.constants import StorageType
from apps.meta.utils.fields import START_TIME
from services.web.query.ai_assistant.constants import EXTENSION_FIELD_DEFAULT_OPERATORS
from services.web.query.ai_assistant.exceptions import LogQueryResponseTooLarge
from services.web.query.ai_assistant.log_tools.context import (
    LogQueryContext,
    LogQueryContextService,
)
from services.web.query.ai_assistant.log_tools.errors import map_log_query_error
from services.web.query.ai_assistant.log_tools.schemas import (
    LOG_FIELD_METADATA_MAX_FIELDS,
    LOG_FIELD_METADATA_RESPONSE_MAX_BYTES,
    LOG_FIELD_METADATA_SAMPLE_ROWS,
    LOG_FIELD_METADATA_SAMPLE_VALUE_MAX_BYTES,
    LOG_FIELD_METADATA_SAMPLE_VALUES,
    LOG_TOOL_MAX_FIELD_PATH_DEPTH,
    FieldSampleSummary,
    GetLogFieldMetadataRequest,
    GetLogFieldMetadataResponse,
    GetLogFieldMetadataTreeResponse,
    JSONValueType,
    LogFieldCategory,
    LogFieldMetadataItem,
    LogFieldMetadataTypeSource,
    LogFieldRef,
    LogFieldType,
    StatisticsUnsupportedReason,
)
from services.web.query.ai_assistant.log_tools.sensitive import (
    SensitiveLogFieldPermissionService,
    prepare_sensitive_query_fields,
)
from services.web.query.ai_assistant.log_tools.sql import ProjectedLogSQLBuilder
from services.web.query.ai_assistant.log_tools.statistics_types import (
    statistics_capability,
)
from services.web.query.ai_assistant.schemas import SelectionFieldOption
from services.web.query.constants import (
    COLLECT_SEARCH_CONFIG,
    DEFAULT_COLLECTOR_SORT_LIST,
    DEFAULT_TIMEDELTA,
)
from services.web.query.search_data import SearchDataParser
from services.web.query.utils.field_map import FieldMapHandler


class LogFieldMetadataService:
    """返回用户可见根字段，或从一次采样探索可见 JSON 父路径。

    根字段范围与 WEB 日志检索配置同源。JSON 子字段样本统一通过 SearchDataParser，
    条件字段单独预检权限，确保类型与样例不旁路现有权限和脱敏逻辑。
    """

    _JSON_TYPE_ORDER = tuple(JSONValueType)

    @classmethod
    def get_metadata(
        cls,
        *,
        username: str,
        namespace: str,
        request: GetLogFieldMetadataRequest,
        include_descendants: bool = False,
    ) -> GetLogFieldMetadataResponse:
        """鉴权后返回元信息；include_descendants 仅由 Web 入口开启整树发现。"""

        request = GetLogFieldMetadataRequest.model_validate(request.model_dump())
        context = LogQueryContextService.build(
            username=username,
            namespace=namespace,
            condition=request.condition,
        )
        sampled_count = 0
        sampling_performed = False
        scan_truncated = False
        try:
            if request.parent_field is None:
                fields = cls._build_basic_fields(namespace=namespace)
            else:
                parent_field = request.parent_field
                # 父对象可能混有无权子字段，不整体拒绝探索；由逐行脱敏负责遮罩和私密删除。
                # 条件会影响样本命中，无法靠结果脱敏补救，仍须在查询前校验。
                SensitiveLogFieldPermissionService.ensure_access(
                    username=username,
                    system_id=request.condition.scope_id,
                    fields=SensitiveLogFieldPermissionService.collect_field_paths(
                        condition.field for condition in context.condition.conditions
                    ),
                )
                sample_limit = cls._effective_limit(
                    settings.AI_ASSISTANT_FIELD_SAMPLE_ROWS, LOG_FIELD_METADATA_SAMPLE_ROWS, 0
                )
                sampling_performed = sample_limit > 0
                rows = cls._query_samples(context, parent_field, page_size=sample_limit) if sampling_performed else []
                safe_rows = (
                    SearchDataParser().parse_data(rows, username=username, system_id=context.condition.scope_id)
                    if sampling_performed
                    else []
                )
                sampled_count = len(safe_rows)
                fields, scan_truncated = cls._build_extended_fields(
                    parent_field=parent_field,
                    rows=safe_rows,
                    include_descendants=include_descendants,
                )
                # 满页不能证明检索范围已耗尽；预算为零时也不能声称完成发现。
                scan_truncated = scan_truncated or not sampling_performed or len(rows) >= sample_limit
            max_fields = cls._effective_limit(
                settings.AI_LOG_FIELD_METADATA_MAX_FIELDS, LOG_FIELD_METADATA_MAX_FIELDS, 0
            )
            truncated = scan_truncated
            if not include_descendants:
                truncated = truncated or len(fields) > max_fields
                fields = fields[:max_fields]
            access = SensitiveLogFieldPermissionService.get_access(
                username=username,
                system_id=request.condition.scope_id,
                fields=SensitiveLogFieldPermissionService.collect_field_paths(item.field for item in fields),
            )
            for item in fields:
                path = ".".join((item.field.raw_name, *item.field.keys))
                if not access[path]:
                    # 目录可保留可展开路径，但遮罩值不能被误当成可统计类别或真实样例。
                    item.statistics_supported = False
                    item.statistics_kind = None
                    item.unsupported_reason = StatisticsUnsupportedReason.PERMISSION_DENIED
                    item.allowed_metrics = []
                    item.sample_values = []
                    item.options = None
                    item.observed_types = []
                    item.sampled_non_null_count = 0
                    item.coverage = 0.0
        except Exception as err:  # noqa: BLE001
            mapped_error = map_log_query_error(err)
            if mapped_error is err:
                raise
            raise mapped_error from err

        response_class = GetLogFieldMetadataTreeResponse if include_descendants else GetLogFieldMetadataResponse
        response = response_class(
            fields=fields,
            sample_summary=FieldSampleSummary(
                sampling_performed=sampling_performed,
                sampled_count=sampled_count,
                returned_field_count=len(fields),
                truncated=truncated,
            ),
        )
        cls._ensure_response_within_budget(response)
        return response

    @classmethod
    def _query_samples(cls, context: LogQueryContext, parent_field: LogFieldRef, *, page_size: int) -> List[dict]:
        """只投影 JSON 根字段和脱敏身份列；裸表配合 prefer_storage 指定 Doris。"""

        query_fields = prepare_sensitive_query_fields((parent_field,))
        builder = ProjectedLogSQLBuilder(
            table=context.table.removesuffix(".doris"),
            conditions=list(context.conditions),
            sort_list=DEFAULT_COLLECTOR_SORT_LIST,
            page=1,
            page_size=page_size,
        )
        sql = (
            builder.build_parent_object_sample_sql(query_fields, parent_field)
            if parent_field.raw_name in builder.JSON_TYPE_FIELDS
            else builder.build_data_sql(query_fields)
        )
        records = api.bk_base.safe_query_sync(
            sql=sql,
            prefer_storage=StorageType.DORIS.value,
        )
        return records.get("list") or []

    @classmethod
    def _build_basic_fields(cls, *, namespace: str) -> List[LogFieldMetadataItem]:
        """从 WEB 日志检索配置构造全部可见根字段，不依赖样本。"""

        max_path_depth = cls._effective_limit(
            settings.AI_LOG_TOOL_MAX_FIELD_PATH_DEPTH,
            LOG_TOOL_MAX_FIELD_PATH_DEPTH,
            0,
        )
        options_map = FieldMapHandler(
            fields=[config.field.field_name for config in COLLECT_SEARCH_CONFIG.field_configs],
            timedelta=DEFAULT_TIMEDELTA,
            namespace=namespace,
        ).field_map
        fields = []
        for config in COLLECT_SEARCH_CONFIG.field_configs:
            field = config.field
            fields.append(
                cls._build_item(
                    field_ref=LogFieldRef(raw_name=field.field_name, field_type=field.field_type),
                    category=LogFieldCategory.BASIC,
                    display_name=str(field.description or field.alias_name or field.field_name),
                    description=str(field.description or ""),
                    type_source=LogFieldMetadataTypeSource.DECLARED,
                    allow_operators=[operator.value for operator in config.allow_operators],
                    options=options_map.get(field.field_name),
                    values=[],
                    sampled_count=0,
                    is_expandable=bool(field.is_json and max_path_depth > 0),
                )
            )
        # start_time 可用于投影、排序和聚合，但时间过滤通过 SearchCondition 的顶层字段表达，
        # 因此它不在 COLLECT_SEARCH_CONFIG 条件列中，需要在字段发现响应中显式补充。
        fields.append(
            cls._build_item(
                field_ref=LogFieldRef(raw_name=START_TIME.field_name, field_type=START_TIME.field_type),
                category=LogFieldCategory.BASIC,
                display_name=str(START_TIME.description or START_TIME.alias_name),
                description=str(START_TIME.description or ""),
                type_source=LogFieldMetadataTypeSource.DECLARED,
                allow_operators=[],
                options=None,
                values=[],
                sampled_count=0,
                is_expandable=False,
            )
        )
        return fields

    @classmethod
    def _build_extended_fields(
        cls,
        *,
        parent_field: LogFieldRef,
        rows: List[dict],
        include_descendants: bool = False,
    ) -> Tuple[List[LogFieldMetadataItem], bool]:
        """在同一批脱敏样本中合并直接子字段，或父路径自身及全部对象后代。

        递归模式使用栈遍历，不额外查询、不展开数组、不截断字段数量；路径深度
        仍与实际查询协议一致。单层模式保留 MCP 字段预算与返回结构。
        """
        parent_keys = tuple(parent_field.keys)
        values_by_keys: Dict[Tuple[str, ...], List[Any]] = {parent_keys: []} if include_descendants else {}
        scan_truncated = False
        max_fields = cls._effective_limit(settings.AI_LOG_FIELD_METADATA_MAX_FIELDS, LOG_FIELD_METADATA_MAX_FIELDS, 0)
        max_path_depth = cls._effective_limit(
            settings.AI_LOG_TOOL_MAX_FIELD_PATH_DEPTH, LOG_TOOL_MAX_FIELD_PATH_DEPTH, 0
        )
        response_limit = cls._effective_limit(
            settings.AI_LOG_FIELD_METADATA_RESPONSE_MAX_BYTES, LOG_FIELD_METADATA_RESPONSE_MAX_BYTES, 0
        )
        minimum_response_bytes = 0
        for row in rows:
            root_value = row.get(parent_field.raw_name, row.get(parent_field.raw_name.lower()))
            container, sample_truncated = cls._resolve_parent(root_value, parent_field.keys)
            scan_truncated = scan_truncated or sample_truncated
            if include_descendants:
                values_by_keys[parent_keys].append(container)
            if not isinstance(container, dict):
                continue
            stack = [(parent_keys, container)]
            while stack:
                container_keys, current = stack.pop()
                for inspected_count, (key, value) in enumerate(current.items(), start=1):
                    if not include_descendants and inspected_count > max_fields:
                        scan_truncated = True
                        break
                    try:
                        field_ref = LogFieldRef(raw_name=parent_field.raw_name, keys=[*container_keys, key])
                    except PydanticValidationError:
                        # 不可表达路径不能参与后续 SQL；跳过整个子树并明确发现不完整。
                        scan_truncated = True
                        continue
                    field_keys = tuple(field_ref.keys)
                    if field_keys in values_by_keys:
                        values_by_keys[field_keys].append(value)
                    elif include_descendants or len(values_by_keys) < max_fields:
                        if include_descendants:
                            # 字段引用只是完整响应的一部分；其总字节已超限时必然无法返回。
                            # 提前停止宽对象遍历，沿用既有413预算，不额外限制字段个数。
                            minimum_response_bytes += len(field_ref.model_dump_json().encode("utf-8"))
                            if minimum_response_bytes > response_limit:
                                raise LogQueryResponseTooLarge()
                        values_by_keys[field_keys] = [value]
                    else:
                        scan_truncated = True
                    if include_descendants and isinstance(value, dict) and value:
                        if len(field_keys) < max_path_depth:
                            stack.append((field_keys, value))
                        else:
                            scan_truncated = True

        config = COLLECT_SEARCH_CONFIG.query_field_map[parent_field.raw_name]
        fields = []
        for keys in sorted(values_by_keys):
            values = values_by_keys[keys]
            is_root = not keys
            fields.append(
                cls._build_item(
                    field_ref=LogFieldRef(
                        raw_name=parent_field.raw_name,
                        keys=list(keys),
                        field_type=config.field.field_type if is_root else LogFieldType.STRING,
                    ),
                    category=LogFieldCategory.BASIC if is_root else LogFieldCategory.EXTENDED,
                    display_name=(
                        str(config.field.description or config.field.alias_name or parent_field.raw_name)
                        if is_root
                        else keys[-1]
                    ),
                    description=str(config.field.description or "") if is_root else "",
                    type_source=LogFieldMetadataTypeSource.DECLARED if is_root else LogFieldMetadataTypeSource.INFERRED,
                    allow_operators=(
                        [operator.value for operator in config.allow_operators]
                        if is_root
                        else list(EXTENSION_FIELD_DEFAULT_OPERATORS)
                    ),
                    options=None,
                    values=values,
                    sampled_count=len(rows),
                    is_expandable=JSONValueType.OBJECT in cls._observed_types(values) and len(keys) < max_path_depth,
                )
            )
        return fields, scan_truncated

    @classmethod
    def _build_item(
        cls,
        *,
        field_ref: LogFieldRef,
        category: LogFieldCategory,
        display_name: str,
        description: str,
        type_source: LogFieldMetadataTypeSource,
        allow_operators: List[str],
        options: Iterable[dict] | None,
        values: List[Any],
        sampled_count: int,
        is_expandable: bool,
    ) -> LogFieldMetadataItem:
        """把声明信息和脱敏观察值转换为稳定响应。"""

        non_null_values = [value for value in values if value is not None]
        observed_types = cls._observed_types(values)
        return LogFieldMetadataItem(
            field=field_ref,
            category=category,
            display_name=display_name,
            description=description,
            type_source=type_source,
            observed_types=observed_types,
            **statistics_capability(field_ref, observed_types),
            allow_operators=allow_operators,
            options=[SelectionFieldOption(**option) for option in options] if options else None,
            is_expandable=is_expandable,
            sample_values=cls._stable_sample_values(non_null_values),
            sampled_non_null_count=len(non_null_values),
            coverage=len(non_null_values) / sampled_count if sampled_count else 0.0,
        )

    @staticmethod
    def _resolve_parent(value: Any, parent_keys: List[str]) -> Tuple[Any, bool]:
        """解析 JSON 字符串并按父路径下钻，不递归枚举更深层字段。"""

        current = value
        for key in [None, *parent_keys]:
            if isinstance(current, str):
                json_limit = LogFieldMetadataService._effective_limit(
                    settings.AI_LOG_FIELD_METADATA_RESPONSE_MAX_BYTES,
                    LOG_FIELD_METADATA_RESPONSE_MAX_BYTES,
                    0,
                )
                if len(current) > json_limit:
                    return None, True
                try:
                    if len(current.encode("utf-8")) > json_limit:
                        return None, True
                    current = json.loads(current)
                except UnicodeEncodeError:
                    return None, True
                except (TypeError, json.JSONDecodeError):
                    return None, False
            if key is not None:
                if not isinstance(current, dict):
                    return None, False
                current = current.get(key)
        return current, False

    @classmethod
    def _observed_types(cls, values: List[Any]) -> List[JSONValueType]:
        observed = {value_type for value in values if (value_type := cls._json_type(value)) is not None}
        return [value_type for value_type in cls._JSON_TYPE_ORDER if value_type in observed]

    @staticmethod
    def _json_type(value: Any) -> JSONValueType | None:
        if value is None:
            return JSONValueType.NULL
        if isinstance(value, bool):
            return JSONValueType.BOOLEAN
        if isinstance(value, int):
            return JSONValueType.INTEGER
        if isinstance(value, float):
            return JSONValueType.NUMBER
        if isinstance(value, str):
            return JSONValueType.STRING
        if isinstance(value, list):
            return JSONValueType.ARRAY
        if isinstance(value, dict):
            return JSONValueType.OBJECT
        return None

    @classmethod
    def _stable_sample_values(cls, values: List[Any]) -> List[Any]:
        """只保留受限标量样例，避免父对象泄露下一层 JSON 内容。"""

        unique_values = {}
        max_bytes = cls._effective_limit(
            settings.AI_LOG_FIELD_METADATA_SAMPLE_VALUE_MAX_BYTES,
            LOG_FIELD_METADATA_SAMPLE_VALUE_MAX_BYTES,
            0,
        )
        for value in values:
            if not cls._is_scalar(value):
                continue
            try:
                serialized_value = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                serialized_bytes = serialized_value.encode("utf-8")
            except (UnicodeEncodeError, TypeError, ValueError, OverflowError):
                continue
            if len(serialized_bytes) > max_bytes:
                continue
            unique_values.setdefault(serialized_value, value)
        sample_limit = cls._effective_limit(
            settings.AI_LOG_FIELD_METADATA_SAMPLE_VALUES,
            LOG_FIELD_METADATA_SAMPLE_VALUES,
            0,
        )
        return [unique_values[key] for key in sorted(unique_values)[:sample_limit]]

    @staticmethod
    def _ensure_response_within_budget(response: GetLogFieldMetadataResponse) -> None:
        """业务 data 载荷超限时显式失败，不返回部分 JSON。"""

        response_limit = LogFieldMetadataService._effective_limit(
            settings.AI_LOG_FIELD_METADATA_RESPONSE_MAX_BYTES,
            LOG_FIELD_METADATA_RESPONSE_MAX_BYTES,
            0,
        )
        if len(response.model_dump_json().encode("utf-8")) > response_limit:
            raise LogQueryResponseTooLarge()

    @staticmethod
    def _effective_limit(configured_limit: int, hard_limit: int, minimum: int) -> int:
        """环境配置只能收紧代码冻结的协议上限。"""

        return min(hard_limit, max(minimum, configured_limit))

    @staticmethod
    def _is_scalar(value: Any) -> bool:
        return isinstance(value, (bool, int, float, str))

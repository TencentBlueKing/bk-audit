"""日志字段元信息探索：受控采样、脱敏后统计当前 extend_data 层。"""

import json
from typing import Any, Dict, Iterable, List, Tuple

from bk_resource import api
from bk_resource.exceptions import APIRequestError
from django.conf import settings
from pydantic import ValidationError as PydanticValidationError
from requests.exceptions import Timeout as RequestsTimeout

from api.bk_base.constants import StorageType
from apps.meta.utils.fields import EXTEND_DATA
from services.web.query.ai_assistant.constants import (
    AI_ASSISTANT_FIELD_SAMPLE_ROWS,
    EXTENSION_FIELD_DEFAULT_OPERATORS,
)
from services.web.query.ai_assistant.exceptions import (
    LogQueryFailed,
    LogQueryTimeout,
    LogToolException,
)
from services.web.query.ai_assistant.log_tools.context import (
    LogQueryContext,
    LogQueryContextService,
)
from services.web.query.ai_assistant.log_tools.schemas import (
    FieldSampleSummary,
    GetLogFieldMetadataRequest,
    GetLogFieldMetadataResponse,
    LogFieldMetadataItem,
    LogFieldMetadataTypeSource,
    LogFieldRef,
    LogFieldScope,
)
from services.web.query.ai_assistant.log_tools.sql import ProjectedLogSQLBuilder
from services.web.query.ai_assistant.schemas import SelectionFieldOption
from services.web.query.constants import (
    COLLECT_SEARCH_CONFIG,
    DEFAULT_COLLECTOR_SORT_LIST,
    DEFAULT_TIMEDELTA,
)
from services.web.query.resources.base import SearchDataParser
from services.web.query.utils.field_map import FieldMapHandler


class LogFieldMetadataService:
    """为已授权查询范围返回声明字段和一层拓展字段的样本观察。

    设计意图：查询只取脱敏器和 extend_data 探索必需的列；统计必须在
    SearchDataParser 完成当前用户脱敏之后进行，避免样例或类型归纳旁路权限边界。
    """

    _SAMPLE_FIELDS = (
        LogFieldRef(raw_name="system_id"),
        LogFieldRef(raw_name="resource_type_id"),
        LogFieldRef(raw_name="action_id"),
        LogFieldRef(raw_name=EXTEND_DATA.field_name),
    )
    _JSON_TYPE_ORDER = ("boolean", "integer", "number", "string", "array", "object", "null")

    @classmethod
    def get_metadata(
        cls, *, username: str, namespace: str, request: GetLogFieldMetadataRequest
    ) -> GetLogFieldMetadataResponse:
        """构建严格 Context 后探索字段，不返回任何原始命中或 SQL。"""

        context = LogQueryContextService.build(username=username, namespace=namespace, condition=request.condition)
        try:
            rows = cls._query_samples(context)
            # 脱敏必须先于 JSON 下钻和样例去重，否则受限字段可能经汇总链路泄露。
            safe_rows = SearchDataParser().parse_data(rows, username=username)
        except LogToolException:
            raise
        except (RequestsTimeout, TimeoutError) as err:
            raise LogQueryTimeout() from err
        except APIRequestError as err:
            if cls._has_timeout_in_chain(err):
                raise LogQueryTimeout() from err
            raise LogQueryFailed() from err
        except Exception as err:  # noqa: BLE001
            raise LogQueryFailed() from err

        fields: List[LogFieldMetadataItem] = []
        if request.field_scope != LogFieldScope.EXTENDED:
            fields.extend(cls._build_basic_fields(namespace=namespace, rows=safe_rows))
        if request.field_scope != LogFieldScope.BASIC:
            fields.extend(cls._build_extended_fields(parent_keys=request.parent_keys, rows=safe_rows))

        max_fields = max(0, getattr(settings, "AI_LOG_FIELD_METADATA_MAX_FIELDS", 100))
        truncated = len(fields) > max_fields
        fields = fields[:max_fields]
        return GetLogFieldMetadataResponse(
            fields=fields,
            sample_summary=FieldSampleSummary(
                sampled_count=len(safe_rows),
                returned_field_count=len(fields),
                truncated=truncated,
            ),
        )

    @classmethod
    def _query_samples(cls, context: LogQueryContext) -> List[dict]:
        """执行最小字段投影采样；Doris 失败统一映射到受控工具异常。"""

        builder = ProjectedLogSQLBuilder(
            table=context.table,
            conditions=list(context.conditions),
            sort_list=DEFAULT_COLLECTOR_SORT_LIST,
            page=1,
            page_size=getattr(settings, "AI_ASSISTANT_FIELD_SAMPLE_ROWS", AI_ASSISTANT_FIELD_SAMPLE_ROWS),
        )
        records = api.bk_base.query_sync(
            sql=builder.build_data_sql(cls._SAMPLE_FIELDS),
            prefer_storage=StorageType.DORIS.value,
        )
        return records.get("list") or []

    @classmethod
    def _build_basic_fields(cls, *, namespace: str, rows: List[dict]) -> List[LogFieldMetadataItem]:
        """标准字段只使用现有检索配置定义，不从样本推断其可查询契约。"""

        options_map = FieldMapHandler(
            fields=[config.field.field_name for config in COLLECT_SEARCH_CONFIG.field_configs],
            timedelta=DEFAULT_TIMEDELTA,
            namespace=namespace,
        ).field_map
        fields = []
        for config in COLLECT_SEARCH_CONFIG.field_configs:
            field = config.field
            values = [
                row[field.field_name] if field.field_name in row else row[field.field_name.lower()]
                for row in rows
                if field.field_name in row or field.field_name.lower() in row
            ]
            fields.append(
                cls._build_item(
                    field_ref=LogFieldRef(raw_name=field.field_name, field_type=field.field_type),
                    category=LogFieldScope.BASIC,
                    display_name=str(field.description or field.alias_name or field.field_name),
                    description=str(field.description or ""),
                    type_source=LogFieldMetadataTypeSource.DECLARED,
                    allow_operators=[operator.value for operator in config.allow_operators],
                    options=options_map.get(field.field_name),
                    values=values,
                    sampled_count=len(rows),
                    is_expandable=field.is_json,
                )
            )
        return fields

    @classmethod
    def _build_extended_fields(cls, *, parent_keys: List[str], rows: List[dict]) -> List[LogFieldMetadataItem]:
        """只展开父路径的下一层，并跳过不能由 LogFieldRef 表达的发现 key。"""

        values_by_keys: Dict[Tuple[str, ...], List[Any]] = {}
        for row in rows:
            container = cls._resolve_parent(row.get(EXTEND_DATA.field_name), parent_keys)
            if not isinstance(container, dict):
                continue
            for key, value in container.items():
                try:
                    field_ref = LogFieldRef(raw_name=EXTEND_DATA.field_name, keys=[*parent_keys, key])
                except PydanticValidationError:
                    # 首期协议无法安全表达的 key 只跳过该 key，不能中断整批字段发现。
                    continue
                values_by_keys.setdefault(tuple(field_ref.keys), []).append(value)

        fields = []
        for keys in sorted(values_by_keys):
            values = values_by_keys[keys]
            fields.append(
                cls._build_item(
                    field_ref=LogFieldRef(raw_name=EXTEND_DATA.field_name, keys=list(keys), field_type="string"),
                    category=LogFieldScope.EXTENDED,
                    display_name=keys[-1],
                    description="",
                    type_source=LogFieldMetadataTypeSource.INFERRED,
                    allow_operators=list(EXTENSION_FIELD_DEFAULT_OPERATORS),
                    options=None,
                    values=values,
                    sampled_count=len(rows),
                    is_expandable="object" in cls._observed_types(values),
                )
            )
        return fields

    @classmethod
    def _build_item(
        cls,
        *,
        field_ref: LogFieldRef,
        category: LogFieldScope,
        display_name: str,
        description: str,
        type_source: LogFieldMetadataTypeSource,
        allow_operators: List[str],
        options: Iterable[dict] | None,
        values: List[Any],
        sampled_count: int,
        is_expandable: bool,
    ) -> LogFieldMetadataItem:
        """将已脱敏值转换为稳定、受限的字段观察。"""

        non_null_values = [value for value in values if value is not None]
        return LogFieldMetadataItem(
            field=field_ref,
            category=category,
            display_name=display_name,
            description=description,
            type_source=type_source,
            observed_types=cls._observed_types(values),
            allow_operators=allow_operators,
            options=[SelectionFieldOption(**option) for option in options] if options else None,
            is_expandable=is_expandable,
            sample_values=cls._stable_sample_values(non_null_values),
            sampled_non_null_count=len(non_null_values),
            coverage=len(non_null_values) / sampled_count if sampled_count else 0.0,
        )

    @staticmethod
    def _resolve_parent(value: Any, parent_keys: List[str]) -> Any:
        """解析 extend_data 后按请求父路径下钻；不递归枚举更深层字段。"""

        current = value
        for key in [None, *parent_keys]:
            if isinstance(current, str):
                try:
                    current = json.loads(current)
                except (TypeError, json.JSONDecodeError):
                    return None
            if key is not None:
                if not isinstance(current, dict):
                    return None
                current = current.get(key)
        return current

    @classmethod
    def _observed_types(cls, values: List[Any]) -> List[str]:
        observed = {cls._json_type(value) for value in values}
        return [type_name for type_name in cls._JSON_TYPE_ORDER if type_name in observed] + sorted(
            observed.difference(cls._JSON_TYPE_ORDER)
        )

    @staticmethod
    def _json_type(value: Any) -> str:
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, int):
            return "integer"
        if isinstance(value, float):
            return "number"
        if isinstance(value, str):
            return "string"
        if isinstance(value, list):
            return "array"
        if isinstance(value, dict):
            return "object"
        return type(value).__name__.lower()

    @classmethod
    def _stable_sample_values(cls, values: List[Any]) -> List[Any]:
        """只保留字节受限的标量样例，防止当前层字段泄露下一层 JSON 内容。"""

        unique_values = {}
        for value in values:
            if not cls._is_scalar(value):
                continue
            try:
                serialized_value = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                serialized_bytes = serialized_value.encode("utf-8")
            except (UnicodeEncodeError, TypeError, ValueError, OverflowError):
                # 样例是可选提示；不能严格序列化的单值不得中断字段发现或改变统计口径。
                continue
            if len(serialized_bytes) > max(0, getattr(settings, "AI_LOG_FIELD_METADATA_SAMPLE_VALUE_MAX_BYTES", 1024)):
                continue
            unique_values.setdefault(serialized_value, value)
        sample_limit = max(0, getattr(settings, "AI_LOG_FIELD_METADATA_SAMPLE_VALUES", 3))
        return [unique_values[key] for key in sorted(unique_values)[:sample_limit]]

    @staticmethod
    def _is_scalar(value: Any) -> bool:
        return isinstance(value, (bool, int, float, str))

    @staticmethod
    def _has_timeout_in_chain(error: BaseException) -> bool:
        """识别 bk_resource 保留在 cause/context 中的网络超时，不记录底层异常正文。"""

        pending = [error]
        visited = set()
        while pending:
            current = pending.pop()
            if id(current) in visited:
                continue
            visited.add(id(current))
            if isinstance(current, (RequestsTimeout, TimeoutError)):
                return True
            pending.extend(item for item in (current.__cause__, current.__context__) if item is not None)
        return False

"""日志工具共享的 Pydantic 协议。"""

import json
import re
from enum import StrEnum
from typing import Annotated, Any, Dict, List, Literal, Optional, Tuple

from django.conf import settings
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from rest_framework import serializers

from apps.meta.utils.fields import EXTEND_DATA, STANDARD_FIELDS, START_TIME
from services.web.query.ai_assistant.schemas import (
    Condition,
    ConditionField,
    QuerySummary,
    SearchCondition,
    SelectionFieldOption,
)
from services.web.query.constants import COLLECT_SEARCH_CONFIG

FIELD_KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
LOG_TOOL_MAX_CONDITIONS = 100
LOG_TOOL_MAX_FILTERS_PER_CONDITION = 1000
LOG_TOOL_MAX_CONDITION_BYTES = 256 * 1024
LOG_TOOL_MAX_FILTER_BYTES = 16 * 1024
LOG_TOOL_MAX_FIELD_KEY_LENGTH = 128
LOG_TOOL_MAX_FIELD_PATH_DEPTH = 16
LOG_TOOL_MAX_FIELD_PATH_BYTES = 1024
LOG_TOOL_MAX_SCOPE_ID_LENGTH = 255
LogFieldKey = Annotated[
    str,
    Field(pattern=FIELD_KEY_PATTERN.pattern, max_length=LOG_TOOL_MAX_FIELD_KEY_LENGTH),
]
LOG_SEARCH_MAX_FIELDS = 20
LOG_SEARCH_MAX_SORT_FIELDS = 3
LOG_SEARCH_MAX_PAGE = 100
LOG_SEARCH_MAX_PAGE_SIZE = 100
LOG_SEARCH_RESPONSE_MAX_BYTES = 1024 * 1024
LOG_FIELD_METADATA_MAX_FIELDS = 100
LOG_FIELD_METADATA_SAMPLE_ROWS = 50
LOG_FIELD_METADATA_SAMPLE_VALUES = 3
LOG_FIELD_METADATA_SAMPLE_VALUE_MAX_BYTES = 1024
LOG_FIELD_METADATA_RESPONSE_MAX_BYTES = 1024 * 1024
# 字段展示元信息可覆盖 WEB 列，但 Agent 投影只能使用条件白名单和默认列必需的 start_time。
LOG_TOOL_ALLOWED_FIELD_NAMES = frozenset((*COLLECT_SEARCH_CONFIG.query_field_map, START_TIME.field_name))
LOG_TOOL_SORTABLE_FIELD_NAMES = frozenset((START_TIME.field_name,))
# 聚合和明细查询的风险模型不同：聚合无法逐行脱敏，因此只允许这一组经过
# 成本评估的字段。它刻意不以 LogFieldRef 的允许集作为聚合白名单。
AGGREGATION_DIMENSION_FIELD_NAMES = frozenset(
    ("action_id", "resource_type_id", "username", "result_code", "access_type", "start_time", "extend_data")
)
AGGREGATION_METRIC_FIELD_NAMES = frozenset(
    ("action_id", "resource_type_id", "username", "result_code", "access_type", "start_time", "extend_data")
)
AGGREGATION_STANDARD_FIELD_TYPES = {field.field_name: field.field_type for field in STANDARD_FIELDS}
AGGREGATION_NUMERIC_FIELD_TYPES = frozenset(("int", "long", "float", "double", "timestamp"))
AGGREGATION_MAX_DIMENSIONS = 2
AGGREGATION_MAX_METRICS = 5
AGGREGATION_MAX_LIMIT = 100
AGGREGATION_RESPONSE_MAX_BYTES = 1024 * 1024


def _bounded_limit(setting_name: str, hard_limit: int, minimum: int) -> int:
    """运行环境只能收紧冻结协议上限，不能放大 Agent 工具成本。"""

    return min(hard_limit, max(minimum, getattr(settings, setting_name, hard_limit)))


def _json_size(value: Any) -> int:
    """按真实 UTF-8 JSON 计算请求成本，不以 Python 字符数近似。"""

    try:
        serialized = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return len(serialized.encode("utf-8"))
    except (TypeError, ValueError, OverflowError, UnicodeEncodeError) as err:
        raise ValueError("value is not valid UTF-8 JSON") from err


def _validate_field_path(raw_name: str, keys: List[str]) -> None:
    if len(keys) > _bounded_limit("AI_LOG_TOOL_MAX_FIELD_PATH_DEPTH", LOG_TOOL_MAX_FIELD_PATH_DEPTH, 0):
        raise ValueError("field path is too deep")
    key_limit = _bounded_limit("AI_LOG_TOOL_MAX_FIELD_KEY_LENGTH", LOG_TOOL_MAX_FIELD_KEY_LENGTH, 0)
    if any(len(key) > key_limit for key in keys):
        raise ValueError("field key is too long")
    path_limit = _bounded_limit("AI_LOG_TOOL_MAX_FIELD_PATH_BYTES", LOG_TOOL_MAX_FIELD_PATH_BYTES, 1)
    if len(".".join((raw_name, *keys)).encode("utf-8")) > path_limit:
        raise ValueError("field path is too long")


class AgentConditionField(ConditionField):
    """Agent 工具条件字段；只收紧公共 WEB 条件，不改变原检索协议。"""

    keys: Annotated[
        List[LogFieldKey],
        serializers.ListField(
            child=serializers.RegexField(regex=FIELD_KEY_PATTERN, max_length=LOG_TOOL_MAX_FIELD_KEY_LENGTH),
            allow_empty=True,
            max_length=LOG_TOOL_MAX_FIELD_PATH_DEPTH,
        ),
    ] = Field(
        default_factory=list,
        max_length=LOG_TOOL_MAX_FIELD_PATH_DEPTH,
        description="最多 16 段 ASCII 安全子键；完整字段路径 UTF-8 最大 1024 bytes。",
    )

    @model_validator(mode="after")
    def validate_agent_field_path(self):
        _validate_field_path(self.raw_name, self.keys)
        return self


class AgentCondition(Condition):
    """Agent 工具单条件，限制过滤值数量与单值 JSON 字节。"""

    field: AgentConditionField
    filters: Annotated[
        List[Any],
        serializers.ListField(
            child=serializers.JSONField(),
            allow_empty=True,
            max_length=LOG_TOOL_MAX_FILTERS_PER_CONDITION,
            help_text="最多 1000 个比较值；单个值的 UTF-8 JSON 最大 16 KiB。",
        ),
    ] = Field(
        default_factory=list,
        max_length=LOG_TOOL_MAX_FILTERS_PER_CONDITION,
        description="最多 1000 个比较值；单个值的 UTF-8 JSON 最大 16 KiB。",
    )

    @model_validator(mode="after")
    def validate_agent_filter_cost(self):
        filter_count_limit = _bounded_limit(
            "AI_LOG_TOOL_MAX_FILTERS_PER_CONDITION", LOG_TOOL_MAX_FILTERS_PER_CONDITION, 0
        )
        if len(self.filters) > filter_count_limit:
            raise ValueError("too many condition filters")
        filter_bytes_limit = _bounded_limit("AI_LOG_TOOL_MAX_FILTER_BYTES", LOG_TOOL_MAX_FILTER_BYTES, 1)
        if any(_json_size(value) > filter_bytes_limit for value in self.filters):
            raise ValueError("condition filter is too large")
        return self


class AgentSearchCondition(SearchCondition):
    """仅供三项 Agent 日志工具使用的冻结成本协议。"""

    scope_id: str = Field(..., min_length=1, max_length=LOG_TOOL_MAX_SCOPE_ID_LENGTH)
    conditions: List[AgentCondition] = Field(
        default_factory=list,
        max_length=LOG_TOOL_MAX_CONDITIONS,
        description="最多 100 个条件；完整 condition 的 UTF-8 JSON 最大 256 KiB。",
    )

    @model_validator(mode="after")
    def validate_agent_condition_cost(self):
        scope_limit = _bounded_limit("AI_LOG_TOOL_MAX_SCOPE_ID_LENGTH", LOG_TOOL_MAX_SCOPE_ID_LENGTH, 1)
        if len(self.scope_id) > scope_limit:
            raise ValueError("scope_id is too long")
        condition_count_limit = _bounded_limit("AI_LOG_TOOL_MAX_CONDITIONS", LOG_TOOL_MAX_CONDITIONS, 0)
        if len(self.conditions) > condition_count_limit:
            raise ValueError("too many conditions")
        condition_bytes_limit = _bounded_limit("AI_LOG_TOOL_MAX_CONDITION_BYTES", LOG_TOOL_MAX_CONDITION_BYTES, 1)
        if _json_size(self.model_dump(mode="json")) > condition_bytes_limit:
            raise ValueError("condition is too large")
        return self


class AgentLogToolRequest(BaseModel):
    """三项 Agent 日志工具的公共条件入口。"""

    model_config = ConfigDict(extra="forbid")

    condition: AgentSearchCondition = Field(
        ...,
        description=("单系统日志检索条件；服务端会按当前用户重新鉴权。最多 100 个条件，" "完整 condition 的 UTF-8 JSON 最大 256 KiB。"),
    )

    @field_validator("condition", mode="before")
    @classmethod
    def normalize_existing_condition(cls, condition):
        if isinstance(condition, SearchCondition):
            return condition.model_dump(mode="json")
        return condition


class LogFieldRef(BaseModel):
    """受控日志字段引用，仅允许白名单字段或 extend_data 的安全子路径。

    一期仅支持 JSONPath helper 可无歧义表达的 ASCII 标识符子键；这不是 SQL
    注入的唯一防线。Task 3 字段发现必须复用本模型过滤，不能返回不可消费的子键。
    """

    model_config = ConfigDict(extra="forbid")

    raw_name: str = Field(..., min_length=1, description="已声明的标准字段，或 extend_data。")
    keys: Annotated[
        List[LogFieldKey],
        serializers.ListField(
            child=serializers.RegexField(regex=FIELD_KEY_PATTERN, max_length=LOG_TOOL_MAX_FIELD_KEY_LENGTH),
            allow_empty=True,
            max_length=LOG_TOOL_MAX_FIELD_PATH_DEPTH,
            help_text="extend_data 的安全子路径；标准字段必须为空数组。",
        ),
    ] = Field(
        default_factory=list,
        max_length=LOG_TOOL_MAX_FIELD_PATH_DEPTH,
        description="extend_data 的安全子路径；标准字段必须为空数组，完整字段路径最大 1024 bytes。",
    )
    field_type: Optional[str] = Field(default=None, description="可选声明类型，仅用于字段元信息或安全数值转换。")

    @field_validator("keys")
    @classmethod
    def validate_keys(cls, keys: List[str]) -> List[str]:
        for key in keys:
            if not FIELD_KEY_PATTERN.fullmatch(key):
                raise ValueError("invalid field key")
        return keys

    @model_validator(mode="after")
    def validate_field_reference(self):
        if self.raw_name not in LOG_TOOL_ALLOWED_FIELD_NAMES:
            raise ValueError("unsupported log field")
        # 当前工具只允许动态 extend_data 下钻，避免将任意 JSON 容器暴露给 Agent。
        if self.keys and self.raw_name != EXTEND_DATA.field_name:
            raise ValueError("nested keys are only supported for extend_data")
        _validate_field_path(self.raw_name, self.keys)
        return self


class LogFieldScope(StrEnum):
    """字段探索范围；ALL 仅用于请求，返回字段分类只使用 BASIC/EXTENDED。"""

    ALL = "ALL"
    BASIC = "BASIC"
    EXTENDED = "EXTENDED"


class LogFieldCategory(StrEnum):
    """字段探索响应分类，不返回请求专用的 ALL。"""

    BASIC = "BASIC"
    EXTENDED = "EXTENDED"


class LogFieldMetadataTypeSource(StrEnum):
    """字段类型的来源，避免把采样观察误表述为全量定义。"""

    DECLARED = "DECLARED"
    INFERRED = "INFERRED"


class GetLogFieldMetadataRequest(AgentLogToolRequest):
    """字段元信息探索请求，父路径复用可消费的 extend_data 路径约束。"""

    parent_keys: Annotated[
        List[LogFieldKey],
        serializers.ListField(
            child=serializers.RegexField(regex=FIELD_KEY_PATTERN, max_length=LOG_TOOL_MAX_FIELD_KEY_LENGTH),
            allow_empty=True,
            max_length=LOG_TOOL_MAX_FIELD_PATH_DEPTH,
            required=False,
            help_text="仅探索 extend_data 的下一层路径；空数组表示第一层，不会递归展开。",
        ),
    ] = Field(
        default_factory=list,
        max_length=LOG_TOOL_MAX_FIELD_PATH_DEPTH,
        description=("仅探索 extend_data 的下一层路径；空数组表示第一层，不会递归展开，" "完整字段路径最大 1024 bytes。"),
    )
    field_scope: LogFieldScope = Field(
        default=LogFieldScope.ALL,
        description="返回范围：BASIC 标准字段、EXTENDED 拓展字段或 ALL；样例最多来自 50 行脱敏数据。",
    )

    @field_validator("parent_keys")
    @classmethod
    def validate_parent_keys(cls, parent_keys: List[str]) -> List[str]:
        LogFieldRef(raw_name=EXTEND_DATA.field_name, keys=parent_keys)
        return parent_keys


class LogFieldMetadataItem(BaseModel):
    """单个可查询字段的声明元信息与当前样本观察。"""

    field: LogFieldRef
    category: LogFieldCategory
    display_name: str = ""
    description: str = ""
    type_source: LogFieldMetadataTypeSource
    observed_types: List[str] = Field(default_factory=list)
    allow_operators: List[str] = Field(default_factory=list)
    options: Optional[List[SelectionFieldOption]] = None
    is_expandable: bool = Field(
        default=False,
        description="extend_data 根字段及其对象子字段可为 true；其他标准 JSON 字段当前协议不可下钻。",
    )
    sample_values: Annotated[
        List[Any],
        serializers.ListField(
            child=serializers.JSONField(),
            allow_empty=True,
            max_length=LOG_FIELD_METADATA_SAMPLE_VALUES,
            help_text="最多 3 个脱敏标量样例，单样例 UTF-8 JSON 最大 1024 bytes。",
        ),
    ] = Field(
        default_factory=list,
        max_length=LOG_FIELD_METADATA_SAMPLE_VALUES,
        description="最多 3 个脱敏标量样例，单样例 UTF-8 JSON 最大 1024 bytes；对象和数组不回显。",
    )
    sampled_non_null_count: int = 0
    coverage: float = 0.0


class FieldSampleSummary(BaseModel):
    """字段探索的有界采样摘要。"""

    sampled_count: int = 0
    returned_field_count: int = 0
    truncated: bool = False


class GetLogFieldMetadataResponse(BaseModel):
    """字段探索响应，不包含 SQL、物理表或未经脱敏的命中行。"""

    fields: List[LogFieldMetadataItem] = Field(
        default_factory=list,
        max_length=LOG_FIELD_METADATA_MAX_FIELDS,
        description="最多返回 100 个字段；完整响应 UTF-8 JSON 最大 1 MiB。",
    )
    sample_summary: FieldSampleSummary


class LogSortItem(BaseModel):
    """明细查询的受控排序项，仅允许已知标准字段。"""

    model_config = ConfigDict(extra="forbid")

    field: LogFieldRef
    direction: Literal["asc", "desc"] = "desc"

    @model_validator(mode="after")
    def validate_sort_field(self):
        if self.field.raw_name not in LOG_TOOL_SORTABLE_FIELD_NAMES or self.field.keys:
            raise ValueError("sort only supports start_time")
        return self


class SearchLogsRequest(AgentLogToolRequest):
    """日志明细请求，所有字段和排序均以 LogFieldRef 表达。"""

    fields: Optional[List[LogFieldRef]] = Field(
        default=None,
        min_length=1,
        max_length=LOG_SEARCH_MAX_FIELDS,
        description="可选受控投影列；省略时使用紧凑默认列，显式传入时为 1 至 20 列。",
    )
    sort: List[LogSortItem] = Field(
        default_factory=list,
        max_length=LOG_SEARCH_MAX_SORT_FIELDS,
        description="最多 3 个排序项；一期仅支持 start_time，未提供时使用稳定默认排序。",
    )
    page: int = Field(default=1, ge=1, le=LOG_SEARCH_MAX_PAGE, description="页码，最大 100；运行配置只能进一步收紧。")
    page_size: int = Field(
        default=20,
        ge=1,
        le=LOG_SEARCH_MAX_PAGE_SIZE,
        description="每页条数，最大 100；运行配置只能进一步收紧。",
    )

    @model_validator(mode="after")
    def validate_limits(self):
        if self.fields is not None:
            if not self.fields:
                raise ValueError("at least one field is required")
            field_keys = [(field.raw_name, tuple(field.keys)) for field in self.fields]
            if len(field_keys) != len(set(field_keys)):
                raise ValueError("duplicate fields are not allowed")
            if len(self.fields) > _bounded_limit("AI_LOG_SEARCH_MAX_FIELDS", LOG_SEARCH_MAX_FIELDS, 0):
                raise ValueError("too many fields")

        sort_keys = [(item.field.raw_name, tuple(item.field.keys)) for item in self.sort]
        if len(sort_keys) != len(set(sort_keys)):
            raise ValueError("duplicate sort fields are not allowed")
        if len(self.sort) > _bounded_limit("AI_LOG_SEARCH_MAX_SORT_FIELDS", LOG_SEARCH_MAX_SORT_FIELDS, 0):
            raise ValueError("too many sort fields")
        if self.page > _bounded_limit("AI_LOG_SEARCH_MAX_PAGE", LOG_SEARCH_MAX_PAGE, 1):
            raise ValueError("page exceeds maximum")
        if self.page_size > _bounded_limit("AI_LOG_SEARCH_MAX_PAGE_SIZE", LOG_SEARCH_MAX_PAGE_SIZE, 1):
            raise ValueError("page_size exceeds maximum")
        return self


class LogDetailColumn(BaseModel):
    """返回列元信息；key 是 items 中稳定且无歧义的键。"""

    field: LogFieldRef
    key: str
    display_name: str = ""
    description: str = ""
    options: Optional[List[SelectionFieldOption]] = None


class LogSearchPagination(BaseModel):
    """明细分页结果。"""

    page: int
    page_size: int
    total: int
    returned_count: int
    has_more: bool


class SearchLogsResponse(BaseModel):
    """受控明细响应，不包含 SQL、物理表、条件值或原始命中。"""

    total: int
    columns: List[LogDetailColumn] = Field(default_factory=list)
    items: Annotated[
        Tuple[Dict[str, Any], ...],
        serializers.ListField(child=serializers.JSONField(), allow_empty=True, help_text="脱敏后的日志行"),
    ] = Field(default=(), description="脱敏后的日志行，仅含 columns 声明的稳定 key。")
    pagination: LogSearchPagination
    query_summary: QuerySummary


class AggregationDimensionType(StrEnum):
    """聚合维度只允许字段或受控时间桶。"""

    FIELD = "FIELD"
    TIME_BUCKET = "TIME_BUCKET"


class AggregationMetricType(StrEnum):
    """聚合函数枚举，禁止接收调用方给出的函数名。"""

    COUNT = "COUNT"
    DISTINCT_COUNT = "DISTINCT_COUNT"
    MIN = "MIN"
    MAX = "MAX"
    AVG = "AVG"
    SUM = "SUM"
    PERCENTILE_APPROX = "PERCENTILE_APPROX"


class AggregationValueType(StrEnum):
    """字符串或拓展数值转换的固定 Doris 目标类型。"""

    LONG = "LONG"
    DOUBLE = "DOUBLE"


class AggregationTimeInterval(StrEnum):
    """时间桶粒度；AUTO 只存在于请求阶段。"""

    AUTO = "AUTO"
    MINUTE = "MINUTE"
    HOUR = "HOUR"
    DAY = "DAY"


class AggregationEffectiveTimeInterval(StrEnum):
    """聚合响应中的实际时间桶粒度，不含请求专用的 AUTO。"""

    MINUTE = "MINUTE"
    HOUR = "HOUR"
    DAY = "DAY"


class AggregationOrderDirection(StrEnum):
    """排序方向固定为 Doris 可映射的两个枚举值。"""

    ASC = "ASC"
    DESC = "DESC"


class AggregationColumnRole(StrEnum):
    """聚合响应列的语义角色。"""

    DIMENSION = "DIMENSION"
    METRIC = "METRIC"


class AggregationDimension(BaseModel):
    """一个受控分组键；TIME_BUCKET 只能用于 start_time。"""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., pattern=r"^[A-Za-z][A-Za-z0-9_]{0,63}$", description="维度唯一 ID，仅允许字母开头。")
    type: AggregationDimensionType = Field(
        ...,
        description="FIELD 按字段分组且不得传 interval；TIME_BUCKET 只能使用无 keys 的 start_time，必须传 interval。",
    )
    field: LogFieldRef = Field(
        ...,
        description=(
            "FIELD 允许的根字段仅限 action_id、resource_type_id、username、result_code、access_type、"
            "start_time、extend_data，extend_data 必须带 keys；TIME_BUCKET 只能使用无 keys 的 start_time。"
        ),
    )
    interval: Optional[AggregationTimeInterval] = Field(
        default=None,
        description="FIELD 必须省略；TIME_BUCKET 必填，可选 AUTO、MINUTE、HOUR、DAY；AUTO 由服务按时间范围选择实际粒度。",
    )

    @model_validator(mode="after")
    def validate_dimension_contract(self):
        if self.field.raw_name not in AGGREGATION_DIMENSION_FIELD_NAMES:
            raise ValueError("unsupported aggregation dimension field")
        if self.field.raw_name == EXTEND_DATA.field_name and not self.field.keys:
            raise ValueError("extend_data dimension requires a key path")
        if self.type == AggregationDimensionType.TIME_BUCKET:
            if self.field.raw_name != START_TIME.field_name or self.field.keys or self.interval is None:
                raise ValueError("time bucket only supports start_time with an interval")
        elif self.interval is not None:
            raise ValueError("field dimension does not accept interval")
        return self


class AggregationMetric(BaseModel):
    """一个固定函数的聚合指标，数值转换意图必须显式且有限。"""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., pattern=r"^[A-Za-z][A-Za-z0-9_]{0,63}$", description="指标唯一 ID，仅允许字母开头。")
    type: AggregationMetricType = Field(
        ...,
        description=(
            "COUNT 仅 COUNT(*)，必须省略 field/value_type/percentile；DISTINCT_COUNT 必须传 field 且省略 "
            "value_type/percentile；MIN/MAX/AVG/SUM 必须传 field，按字段类型决定 value_type 且必须省略 "
            "percentile；PERCENTILE_APPROX 同数值指标并额外必须传 0 < percentile < 1。"
        ),
    )
    field: Optional[LogFieldRef] = Field(
        default=None,
        description=(
            "COUNT 必须省略；其余指标必须传。允许的根字段仅限 action_id、resource_type_id、username、"
            "result_code、access_type、start_time、extend_data；extend_data 必须带 keys。"
        ),
    )
    value_type: Optional[AggregationValueType] = Field(
        default=None,
        description=(
            "COUNT/DISTINCT_COUNT 必须省略；MIN/MAX/AVG/SUM/PERCENTILE_APPROX 对字符串或 extend_data 数值"
            "聚合必须传 LONG 或 DOUBLE，标准数值字段必须省略。"
        ),
    )
    percentile: Optional[float] = Field(
        default=None,
        description="仅 PERCENTILE_APPROX 必填且满足 0 < percentile < 1；其余指标必须省略。",
        json_schema_extra={"exclusiveMinimum": 0, "exclusiveMaximum": 1},
    )

    @property
    def is_numeric(self) -> bool:
        return self.type in {
            AggregationMetricType.MIN,
            AggregationMetricType.MAX,
            AggregationMetricType.AVG,
            AggregationMetricType.SUM,
            AggregationMetricType.PERCENTILE_APPROX,
        }

    @property
    def needs_conversion(self) -> bool:
        if not self.is_numeric or self.field is None:
            return False
        declared_type = AGGREGATION_STANDARD_FIELD_TYPES.get(self.field.raw_name)
        return bool(self.field.keys or declared_type not in AGGREGATION_NUMERIC_FIELD_TYPES)

    @model_validator(mode="after")
    def validate_metric_contract(self):
        if self.type == AggregationMetricType.COUNT:
            if self.field is not None or self.value_type is not None or self.percentile is not None:
                raise ValueError("COUNT only supports COUNT(*)")
            return self

        if self.field is None:
            raise ValueError("aggregation metric requires a field")
        if self.field.raw_name not in AGGREGATION_METRIC_FIELD_NAMES:
            raise ValueError("unsupported aggregation metric field")
        if self.field.raw_name == EXTEND_DATA.field_name and not self.field.keys:
            raise ValueError("extend_data metric requires a key path")

        if self.type == AggregationMetricType.DISTINCT_COUNT:
            if self.value_type is not None or self.percentile is not None:
                raise ValueError("DISTINCT_COUNT does not accept numeric options")
            return self

        declared_type = AGGREGATION_STANDARD_FIELD_TYPES.get(self.field.raw_name)
        if self.needs_conversion and self.value_type is None:
            raise ValueError("string and extended numeric metrics require value_type")
        if not self.needs_conversion and self.value_type is not None:
            raise ValueError("standard numeric metrics do not accept value_type")
        if not self.needs_conversion and declared_type not in AGGREGATION_NUMERIC_FIELD_TYPES:
            raise ValueError("numeric aggregation requires a numeric field or value_type")
        if self.type == AggregationMetricType.PERCENTILE_APPROX:
            if self.percentile is None or not 0 < self.percentile < 1:
                raise ValueError("percentile must be between zero and one")
        elif self.percentile is not None:
            raise ValueError("percentile is only valid for PERCENTILE_APPROX")
        return self


class AggregationOrder(BaseModel):
    """仅引用请求中已声明的安全列 ID，不能传 Doris 排序片段。"""

    model_config = ConfigDict(extra="forbid")

    target_id: str = Field(..., pattern=r"^[A-Za-z][A-Za-z0-9_]{0,63}$", description="已声明维度或指标的 ID。")
    direction: AggregationOrderDirection = Field(..., description="固定排序方向 ASC 或 DESC。")


class AggregateLogsRequest(AgentLogToolRequest):
    """类型化聚合请求，配置只能收紧 frozen hard limit。"""

    dimensions: Tuple[AggregationDimension, ...] = Field(
        default=(),
        max_length=AGGREGATION_MAX_DIMENSIONS,
        description="0 至 2 个分组维度；TIME_BUCKET 最多一个，AUTO 会按已验证时间范围选择实际粒度。",
    )
    metrics: Tuple[AggregationMetric, ...] = Field(
        ...,
        min_length=1,
        max_length=AGGREGATION_MAX_METRICS,
        description="1 至 5 个固定聚合指标；不接受 SQL、任意函数名或表达式。",
    )
    order_by: Tuple[AggregationOrder, ...] = Field(default=(), description="可选排序，只能引用已声明的维度或指标 ID。")
    limit: int = Field(
        default=20,
        ge=1,
        le=AGGREGATION_MAX_LIMIT,
        description="返回分组数，最大 100；运行配置只能进一步收紧，服务通过多取一行计算 has_more。",
    )

    @model_validator(mode="after")
    def validate_request_contract(self):
        if len(self.dimensions) > AGGREGATION_MAX_DIMENSIONS:
            raise ValueError("too many aggregation dimensions")
        if not self.metrics or len(self.metrics) > AGGREGATION_MAX_METRICS:
            raise ValueError("invalid aggregation metric count")
        if sum(item.type == AggregationDimensionType.TIME_BUCKET for item in self.dimensions) > 1:
            raise ValueError("at most one time bucket is allowed")

        ids = [item.id for item in (*self.dimensions, *self.metrics)]
        if len(ids) != len(set(ids)):
            raise ValueError("dimension and metric ids must be globally unique")
        order_ids = [item.target_id for item in self.order_by]
        if len(order_ids) != len(set(order_ids)):
            raise ValueError("duplicate order targets are not allowed")
        if len(order_ids) > len(ids) or any(item not in ids for item in order_ids):
            raise ValueError("order_by must reference declared ids")
        if self.limit > _bounded_limit("AI_LOG_AGGREGATION_MAX_LIMIT", AGGREGATION_MAX_LIMIT, 1):
            raise ValueError("aggregation limit exceeds maximum")
        return self


class AggregationColumn(BaseModel):
    """响应列描述，不回显 SQL、条件或物理表。"""

    id: str
    name: str
    role: AggregationColumnRole
    data_type: str
    effective_time_interval: Optional[AggregationEffectiveTimeInterval] = None


class AggregationDataQuality(BaseModel):
    """一个安全转换指标的输入质量计数。"""

    metric_id: str
    non_empty_count: int
    converted_count: int
    conversion_failed_count: int


class AggregationQuerySummary(BaseModel):
    """聚合执行摘要，仅保留非敏感运行元数据。"""

    returned_count: int
    has_more: bool
    took_ms: int
    executed_at: str


class AggregateLogsResponse(BaseModel):
    """聚合响应仅含声明列、分组结果和转换质量摘要。"""

    columns: Tuple[AggregationColumn, ...]
    rows: Annotated[
        Tuple[Dict[str, Any], ...],
        serializers.ListField(
            child=serializers.JSONField(),
            allow_empty=True,
            max_length=AGGREGATION_MAX_LIMIT,
            help_text="最多 100 行声明列对应的聚合结果；完整响应最大 1 MiB。",
        ),
    ] = Field(
        ...,
        max_length=AGGREGATION_MAX_LIMIT,
        description="最多 100 行声明列对应的聚合结果；完整响应 UTF-8 JSON 最大 1 MiB。",
    )
    query_summary: AggregationQuerySummary
    data_quality: Tuple[AggregationDataQuality, ...] = ()

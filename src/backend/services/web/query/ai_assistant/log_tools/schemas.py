"""日志工具共享的 Pydantic 协议。"""

import re
from enum import StrEnum
from typing import Any, Dict, List, Literal, Optional, Tuple

from django.conf import settings
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from apps.meta.utils.fields import EXTEND_DATA, STANDARD_FIELDS, START_TIME
from services.web.query.ai_assistant.schemas import (
    QuerySummary,
    SearchCondition,
    SelectionFieldOption,
)
from services.web.query.constants import COLLECT_SEARCH_CONFIG

FIELD_KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
LOG_SEARCH_MAX_FIELDS = 20
LOG_SEARCH_MAX_SORT_FIELDS = 3
LOG_SEARCH_MAX_PAGE = 100
LOG_SEARCH_MAX_PAGE_SIZE = 100
LOG_SEARCH_RESPONSE_MAX_BYTES = 1024 * 1024
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


def _bounded_limit(setting_name: str, hard_limit: int, minimum: int) -> int:
    """运行环境只能收紧冻结协议上限，不能放大 Agent 工具成本。"""

    return min(hard_limit, max(minimum, getattr(settings, setting_name, hard_limit)))


class LogFieldRef(BaseModel):
    """受控日志字段引用，仅允许白名单字段或 extend_data 的安全子路径。

    一期仅支持 JSONPath helper 可无歧义表达的 ASCII 标识符子键；这不是 SQL
    注入的唯一防线。Task 3 字段发现必须复用本模型过滤，不能返回不可消费的子键。
    """

    model_config = ConfigDict(extra="forbid")

    raw_name: str = Field(..., min_length=1)
    keys: List[str] = Field(default_factory=list)
    field_type: Optional[str] = None

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
        return self


class LogFieldScope(StrEnum):
    """字段探索范围；ALL 仅用于请求，返回字段分类只使用 BASIC/EXTENDED。"""

    ALL = "ALL"
    BASIC = "BASIC"
    EXTENDED = "EXTENDED"


class LogFieldMetadataTypeSource(StrEnum):
    """字段类型的来源，避免把采样观察误表述为全量定义。"""

    DECLARED = "DECLARED"
    INFERRED = "INFERRED"


class GetLogFieldMetadataRequest(BaseModel):
    """字段元信息探索请求，父路径复用可消费的 extend_data 路径约束。"""

    condition: SearchCondition
    parent_keys: List[str] = Field(default_factory=list)
    field_scope: LogFieldScope = LogFieldScope.ALL

    @field_validator("parent_keys")
    @classmethod
    def validate_parent_keys(cls, parent_keys: List[str]) -> List[str]:
        LogFieldRef(raw_name=EXTEND_DATA.field_name, keys=parent_keys)
        return parent_keys


class LogFieldMetadataItem(BaseModel):
    """单个可查询字段的声明元信息与当前样本观察。"""

    field: LogFieldRef
    category: LogFieldScope
    display_name: str = ""
    description: str = ""
    type_source: LogFieldMetadataTypeSource
    observed_types: List[str] = Field(default_factory=list)
    allow_operators: List[str] = Field(default_factory=list)
    options: Optional[List[SelectionFieldOption]] = None
    is_expandable: bool = False
    sample_values: List[Any] = Field(default_factory=list)
    sampled_non_null_count: int = 0
    coverage: float = 0.0


class FieldSampleSummary(BaseModel):
    """字段探索的有界采样摘要。"""

    sampled_count: int = 0
    returned_field_count: int = 0
    truncated: bool = False


class GetLogFieldMetadataResponse(BaseModel):
    """字段探索响应，不包含 SQL、物理表或未经脱敏的命中行。"""

    fields: List[LogFieldMetadataItem] = Field(default_factory=list)
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


class SearchLogsRequest(BaseModel):
    """日志明细请求，所有字段和排序均以 LogFieldRef 表达。"""

    model_config = ConfigDict(extra="forbid")

    condition: SearchCondition
    fields: Optional[List[LogFieldRef]] = None
    sort: List[LogSortItem] = Field(default_factory=list)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1)

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
    items: Tuple[Dict[str, Any], ...] = ()
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

    id: str = Field(..., pattern=r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
    type: AggregationDimensionType
    field: LogFieldRef
    interval: Optional[AggregationTimeInterval] = None

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

    id: str = Field(..., pattern=r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
    type: AggregationMetricType
    field: Optional[LogFieldRef] = None
    value_type: Optional[AggregationValueType] = None
    percentile: Optional[float] = None

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

    target_id: str = Field(..., pattern=r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
    direction: AggregationOrderDirection


class AggregateLogsRequest(BaseModel):
    """类型化聚合请求，配置只能收紧 frozen hard limit。"""

    model_config = ConfigDict(extra="forbid")

    condition: SearchCondition
    dimensions: Tuple[AggregationDimension, ...] = ()
    metrics: Tuple[AggregationMetric, ...]
    order_by: Tuple[AggregationOrder, ...] = ()
    limit: int = Field(default=20, ge=1)

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
    effective_time_interval: Optional[AggregationTimeInterval] = None


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
    rows: Tuple[Dict[str, Any], ...]
    query_summary: AggregationQuerySummary
    data_quality: Tuple[AggregationDataQuality, ...] = ()

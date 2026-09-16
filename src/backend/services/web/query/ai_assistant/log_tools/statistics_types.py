"""日志字段目录的统计能力提示。

声明类型仅用于根字段；JSON 子路径以观察到的标量类型推断，不能信任调用方的类型提示。
未知样本只影响目录提示，执行统计仍须重新校验权限和全范围类型，不得据此拒绝空结果。
"""

from apps.meta.utils.fields import START_TIME
from services.web.query.ai_assistant.log_tools.schemas import (
    LOG_TOOL_NESTED_FIELD_NAMES,
    AggregationMetricType,
    JSONValueType,
    LogFieldRef,
    LogFieldType,
    StatisticsKind,
    StatisticsUnsupportedReason,
)
from services.web.query.constants import COLLECT_SEARCH_CONFIG

_DECLARED_TYPES = {
    **{config.field.field_name: config.field.field_type for config in COLLECT_SEARCH_CONFIG.field_configs},
    START_TIME.field_name: START_TIME.field_type,
}
_NUMERIC_TYPES = frozenset(
    (LogFieldType.INT, LogFieldType.LONG, LogFieldType.DOUBLE, LogFieldType.FLOAT, LogFieldType.TIMESTAMP)
)


def statistics_capability(field: LogFieldRef, observed_types: list[JSONValueType]) -> dict:
    """根据可信根声明或 JSON 观察类型生成四个统计能力字段。

    Args:
        field: 通过 LogFieldRef 校验的业务字段；子路径的 field_type 不参与推断。
        observed_types: 已脱敏样本的 JSON 类型，NULL 不改变已观察标量的类别。
    Returns:
        可直接传给 LogFieldMetadataItem 的能力字段；不含用户权限判断。
    """
    kind = None
    reason = None
    if not field.keys:
        if field.raw_name in LOG_TOOL_NESTED_FIELD_NAMES:
            reason = StatisticsUnsupportedReason.OBJECT
        elif _DECLARED_TYPES.get(field.raw_name) in _NUMERIC_TYPES:
            kind = StatisticsKind.NUMERIC
        else:
            kind = StatisticsKind.CATEGORICAL
    else:
        observed = set(observed_types) - {JSONValueType.NULL}
        if JSONValueType.OBJECT in observed:
            reason = StatisticsUnsupportedReason.OBJECT
        elif JSONValueType.ARRAY in observed:
            reason = StatisticsUnsupportedReason.ARRAY
        elif not observed:
            reason = StatisticsUnsupportedReason.UNKNOWN_TYPE
        elif observed <= {JSONValueType.INTEGER, JSONValueType.NUMBER}:
            kind = StatisticsKind.NUMERIC
        else:
            kind = StatisticsKind.CATEGORICAL
    metrics = []
    if kind == StatisticsKind.NUMERIC:
        metrics = list(AggregationMetricType)
    elif kind == StatisticsKind.CATEGORICAL:
        metrics = [AggregationMetricType.COUNT, AggregationMetricType.DISTINCT_COUNT]
    return {
        "statistics_supported": kind is not None,
        "statistics_kind": kind,
        "unsupported_reason": reason,
        "allowed_metrics": metrics,
    }

"""日志字段目录的统计能力提示。

声明类型仅用于根字段；JSON 子路径以观察到的标量类型推断，不能信任调用方的类型提示。
未知样本只影响目录提示，执行统计仍须重新校验权限和全范围类型，不得据此拒绝空结果。
"""

import json
import math
from decimal import Decimal

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


SAFE_STATISTICS_INTEGER = 9007199254740991


def _reject_json_constant(value: str):
    """拒绝 JSON 标准以外的非有限数字，不回显字段值。"""
    raise ValueError("non-finite statistics scalar")


def parse_statistics_scalar(value_type: str, value_json_text: str):
    """从 SQL STRING 通道恢复有界 JSON 标量，绝不用于生成或修复分组键。

    数字先以 Decimal/int 解析以守住安全整数边界；非整值仅在输出边界恢复 binary64。
    Raises:
        ValueError: 非标量、类型错配、不安全整数或浮点下溢。
        TypeError: 远端绕过文本通道。
    """
    if not isinstance(value_json_text, str):
        raise TypeError("statistics scalar must use SQL text channel")
    if value_type not in {"number", "integer", "boolean", "string"}:
        raise ValueError("invalid statistics scalar type")
    if value_type in {"number", "integer"} and len(value_json_text) > 128:
        raise ValueError("statistics number text too long")
    value = json.loads(value_json_text, parse_int=int, parse_float=Decimal, parse_constant=_reject_json_constant)
    if value_type == "string" and type(value) is str:
        return value
    if value_type == "boolean" and type(value) is bool:
        return value
    if value_type not in {"integer", "number"} or type(value) not in {int, Decimal}:
        raise ValueError("statistics scalar type mismatch")
    number = Decimal(value)
    if not number.is_finite() or number.copy_abs() > SAFE_STATISTICS_INTEGER:
        raise ValueError("statistics number exceeds safe integer range")
    if number == number.to_integral_value():
        return int(number)
    if value_type == "integer":
        raise ValueError("statistics integer is fractional")
    result = float(number)
    if not math.isfinite(result) or (number != 0 and result == 0):
        raise ValueError("statistics number does not roundtrip")
    if result.is_integer() and abs(result) > SAFE_STATISTICS_INTEGER:
        raise ValueError("statistics number exceeds safe integer range")
    if json.loads(json.dumps(result)) != result:
        raise ValueError("statistics number does not roundtrip")
    return result

"""解析同快照字段 SUMMARY 帧。

只使用全范围类型/存在性计数选择统计类别，不读取样本或预检类型。
数值走共享 STRING 保真通道，错误或不完整摘要整包拒绝。
"""
from dataclasses import dataclass

from services.web.query.ai_assistant.log_tools.field_statistics_schemas import (
    FieldNumericSummary,
)
from services.web.query.ai_assistant.log_tools.schemas import (
    AGGREGATION_STANDARD_FIELD_TYPES,
    StatisticsKind,
)
from services.web.query.ai_assistant.log_tools.statistics_types import (
    parse_statistics_scalar,
)


@dataclass(frozen=True)
class StatisticsFieldSummary:
    """验证后的全范围类型及摘要，present 用于与分布缺失计数闭合。"""

    kind: StatisticsKind
    present_count: int
    numeric_summary: FieldNumericSummary | None


def parse_field_summary(frames, field, groups, total, parse_count):
    """校验唯一摘要、计数和数值边界；任何不一致抛 ValueError。"""
    if len(frames) != 1:
        raise ValueError("missing or duplicate field summary")
    frame = frames[0]
    present, numeric = (parse_count(frame.get(key)) for key in ("n", "a"))
    missing = sum(group.count for group in groups if group.kind == "MISSING")
    if present != total - missing or numeric > present:
        raise ValueError("field summary counts do not close")
    selected_numeric = sum(g.count for g in groups if g.kind == "VALUE" and g.values[0].value_type == "number")
    selected_other = sum(g.count for g in groups if g.kind == "VALUE" and g.values[0].value_type != "number")
    if selected_numeric > numeric or selected_other > present - numeric:
        raise ValueError("field summary contradicts selected scalar types")
    declared_numeric = not field.keys and AGGREGATION_STANDARD_FIELD_TYPES.get(field.raw_name) in {
        "int",
        "long",
        "timestamp",
        "double",
        "float",
    }
    is_numeric = declared_numeric or (present > 0 and present == numeric)
    if declared_numeric and present != numeric:
        raise ValueError("field summary contradicts declared numeric type")
    values = {}
    for name in ("min", "max", "avg", "median"):
        key = f"s_{name}"
        if key not in frame:
            raise ValueError("field summary misses value")
        text = frame[key]
        if is_numeric and numeric:
            if text is None:
                raise ValueError("field summary misses numeric value")
            values[name] = parse_statistics_scalar("number", text)
        elif text is not None:
            raise ValueError("field summary has unexpected numeric value")
        else:
            values[name] = None
    if numeric and is_numeric:
        if (
            not values["min"] <= values["avg"] <= values["max"]
            or not values["min"] <= values["median"] <= values["max"]
        ):
            raise ValueError("field summary numeric bounds do not close")
    summary = (
        FieldNumericSummary(**values, valid_count=numeric, conversion_failed_count=present - numeric)
        if is_numeric
        else None
    )
    return StatisticsFieldSummary(
        StatisticsKind.NUMERIC if is_numeric else StatisticsKind.CATEGORICAL, present, summary
    )

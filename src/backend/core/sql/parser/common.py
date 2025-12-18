import numbers
from typing import Any

from sqlglot import exp

from core.sql.parser.model import RangeVariableData


def _create_sqlglot_literal(value: Any) -> exp.Expression:
    """
    将Python值转换为sqlglot的Literal表达式。
    """
    if isinstance(value, RangeVariableData):
        t = exp.Tuple(
            expressions=[
                _create_sqlglot_literal(value.start),
                _create_sqlglot_literal(value.end),
            ]
        )
        t.set("is_range", True)
        return t
    if isinstance(value, str):
        return exp.Literal.string(value)
    if isinstance(value, bool):
        return exp.Boolean(this=value)
    if isinstance(value, numbers.Integral):
        return exp.Literal.number(int(value))
    if isinstance(value, numbers.Real):
        return exp.Literal.number(float(value))
    if isinstance(value, list):
        return exp.Tuple(expressions=[_create_sqlglot_literal(item) for item in value])
    if value is None:
        return exp.Null()
    raise TypeError(f"不支持将 Python 类型 '{type(value).__name__}' 自动转换为 SQL 字面量。值为: {value!r}")

from datetime import datetime
from enum import Enum
from itertools import chain
from typing import Set

from sqlglot import expressions as exp
from sqlglot.dialects import Dialect

from core.sql.exceptions import SQLParseError
from core.sql.parser.common import _create_sqlglot_literal

_SKIP_NULL_OPERATORS = {
    "eq": exp.EQ,
    "exact": exp.EQ,
    "gt": exp.GT,
    "gte": exp.GTE,
    "lt": exp.LT,
    "lte": exp.LTE,
    "like": exp.Like,
    "in": exp.In,
}


class TimeRange(exp.Func):
    """Expression for the TIME_RANGE function."""

    arg_types = {"field": True, "range": True, "fmt": False}


class SkipNullClause(exp.Func):
    """Expression for the SKIP_NULL_CLAUSE function."""

    arg_types = {
        "field": True,
        "op": True,
        "value": True,
        "invert": False,
    }


def get_skip_null_var_names(parsed_expression: exp.Expression):
    """获取 SKIP_NULL_CLAUSE 中的变量名"""
    skip_null_var_names: Set[str] = set()
    for func in parsed_expression.find_all(exp.Func):
        if func.__class__ == SkipNullClause:
            value_expr = func.args['value']
            for var_node in chain(value_expr.find_all(exp.Var), value_expr.find_all(exp.Placeholder)):
                if var_node.name != "?":
                    skip_null_var_names.add(var_node.name)
    return skip_null_var_names


def register_functions(dialect_name: str | None) -> None:
    """Register custom functions on the given dialect."""
    if not dialect_name:
        dialect_name = "hive"

    dialect_cls = Dialect.get(dialect_name)
    if not dialect_cls:
        return

    funcs = dict(getattr(dialect_cls.Parser, "FUNCTIONS", {}))

    updated = False
    if "TIME_RANGE" not in funcs:
        funcs["TIME_RANGE"] = TimeRange.from_arg_list
        updated = True
    if "SKIP_NULL_CLAUSE" not in funcs:
        funcs["SKIP_NULL_CLAUSE"] = SkipNullClause.from_arg_list
        updated = True

    if updated:
        dialect_cls.Parser.FUNCTIONS = funcs


class TimestampType(Enum):
    TS_S = 'Timestamp(s)'
    TS_MS = 'Timestamp(ms)'
    TS_US = 'Timestamp(us)'


def _replace_time_range(node: exp.Func, **kwargs) -> exp.Expression:
    """将 TIME_RANGE 函数替换为实际的时间范围比较语句"""
    field, range_data, fmt = node.args['field'], node.args['range'], node.args.get('fmt', TimestampType.TS_MS.value)
    if not (isinstance(range_data, exp.Tuple) and range_data.args.get('is_range', False)):
        raise SQLParseError("TIME_RANGE 函数的第二个参数类型必须是范围数组")
    fmt = fmt.this if isinstance(fmt, exp.Literal) else fmt

    start_val, end_val = range_data.expressions[0].this, range_data.expressions[1].this
    if fmt == TimestampType.TS_S.value:  # 秒级时间戳
        start_val = int(start_val) // 1000
        end_val = int(end_val) // 1000
    elif fmt == TimestampType.TS_MS.value:  # 毫秒级时间戳(保持原样)
        start_val = int(start_val)
        end_val = int(end_val)
    elif fmt == TimestampType.TS_US.value:  # 微秒级时间戳
        start_val = int(start_val) * 1000
        end_val = int(end_val) * 1000
    else:  # 其他格式按原样处理
        start_val = datetime.fromtimestamp(int(start_val) / 1000).strftime(fmt)
        end_val = datetime.fromtimestamp(int(end_val) / 1000).strftime(fmt)
    low = _create_sqlglot_literal(start_val)
    high = _create_sqlglot_literal(end_val)
    return exp.And(
        this=exp.GTE(this=field.copy(), expression=low),
        expression=exp.LT(this=field.copy(), expression=high),
    )


def _replace_skip_null_clause(node: exp.Func, **kwargs) -> exp.Expression:
    """将 SKIP_NULL_CLAUSE 函数替换为实际的条件语句"""
    field_expr, op_expr, value_expr, invert = (
        node.args['field'],
        node.args['op'],
        node.args['value'],
        node.args.get('invert', None),
    )

    if isinstance(value_expr, exp.Null) or (isinstance(value_expr, exp.Tuple) and not value_expr.expressions):
        return exp.true()

    invert = invert.this if invert else False

    op_name = op_expr.this if isinstance(op_expr, exp.Literal) else op_expr.name
    op_name = op_name.lower()

    op_cls = _SKIP_NULL_OPERATORS.get(op_name)
    if op_cls is None:
        raise SQLParseError(f"不支持的操作符: {op_name}")
    elif op_cls is exp.In:
        values = value_expr.expressions if isinstance(value_expr, exp.Tuple) else [value_expr]
        base_expr = op_cls(this=field_expr, expressions=values)
    else:
        base_expr = op_cls(this=field_expr, expression=value_expr)

    return exp.Not(this=base_expr) if invert else base_expr


function_visitors = {
    TimeRange: _replace_time_range,
    SkipNullClause: _replace_skip_null_clause,
}

register_functions('hive')

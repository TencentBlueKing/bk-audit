from typing import List

from pypika import Field
from pypika import functions as fn

from core.sql.builder.functions import JsonContains
from core.sql.builder.terms import DorisField
from core.sql.constants import AggregateType, Operator
from core.sql.exceptions import OperatorValueError, UnsupportedOperatorError


def operate(operator: str, field: Field, value: str | int | float, values: List[str | int | float]):
    cls = Operator
    # 根据操作符类型调用对应的处理函数
    if not value and values:
        value = values[0]
    if operator == cls.EQ:
        return field.eq(value)
    elif operator == cls.NEQ:
        return field != value
    elif operator == cls.INCLUDE:
        return field.isin(values)
    elif operator == cls.EXCLUDE:
        return ~field.isin(values)
    elif operator == cls.LIKE:
        return field.like(str(value))
    elif operator == cls.NOT_LIKE:
        return ~field.like(str(value))
    elif operator == cls.LTE:
        return field.lte(value)
    elif operator == cls.LT:
        return field.lt(value)
    elif operator == cls.GTE:
        return field.gte(value)
    elif operator == cls.GT:
        return field.gt(value)
    elif operator == cls.ISNULL:
        return field.isnull()
    elif operator == cls.NOTNULL:
        return field.notnull()
    elif operator == cls.BETWEEN:
        if len(values) != 2:
            raise OperatorValueError(operator=operator, value=values)
        return field.between(*values[:2])
    elif operator == cls.MATCH_ALL and isinstance(field, DorisField):
        return field.match_all(values)
    elif operator == cls.MATCH_ANY and isinstance(field, DorisField):
        return field.match_any(values)
    elif operator == cls.JSON_CONTAINS:
        return JsonContains(field, value)
    else:
        raise UnsupportedOperatorError(operator)


def get_function(aggregate_type: str):
    """根据聚合类型返回 PyPika 对应的函数"""

    from core.sql.builder.functions import DisCount, DisGroupConcat, GroupConcat

    cls = AggregateType

    aggregate_mapping = {
        cls.COUNT.value: fn.Count,
        cls.SUM.value: fn.Sum,
        cls.AVG.value: fn.Avg,
        cls.MAX.value: fn.Max,
        cls.MIN.value: fn.Min,
        cls.DISCOUNT.value: DisCount,
        cls.LIST.value: GroupConcat,
        cls.LIST_DISTINCT.value: DisGroupConcat,
    }
    if aggregate_type not in aggregate_mapping:
        raise ValueError(f"不支持的聚合类型: {aggregate_type}")
    return aggregate_mapping[aggregate_type]

# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
Copyright (C) 2023 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""
from functools import cached_property
from typing import List

from django.utils.translation import gettext_lazy
from pypika import Field
from pypika import functions as fn

from core.choices import TextChoices
from core.sql.exceptions import OperatorValueError, UnsupportedOperatorError


class FilterConnector(TextChoices):
    """
    Filter Connector
    """

    AND = "and", gettext_lazy("AND")
    OR = "or", gettext_lazy("OR")


class FieldType(TextChoices):
    """
    字段类型
    """

    STRING = "string", gettext_lazy("字符串")
    DOUBLE = "double", gettext_lazy("双精度浮点数")
    INT = "int", gettext_lazy("整数")
    LONG = "long", gettext_lazy("长整数")
    TEXT = "text", gettext_lazy("文本")
    TIMESTAMP = "timestamp", gettext_lazy("时间戳")
    FLOAT = "float", gettext_lazy("浮点数")

    @cached_property
    def python_type(self):
        """
        将字段类型转换为 Python 类型
        """
        type_mapping = {
            self.STRING: str,
            self.DOUBLE: float,
            self.INT: int,
            self.LONG: int,
            self.TEXT: str,
            self.TIMESTAMP: int,
            self.FLOAT: float,
        }
        return type_mapping[self.value]


class AggregateType(TextChoices):
    """
    聚合类型
    """

    COUNT = "COUNT", gettext_lazy("计数")
    SUM = "SUM", gettext_lazy("求和")
    AVG = "AVG", gettext_lazy("平均值")
    MAX = "MAX", gettext_lazy("最大值")
    MIN = "MIN", gettext_lazy("最小值")
    DISCOUNT = "DISCOUNT", gettext_lazy("去重计数")

    @classmethod
    def get_function(cls, aggregate_type: str):
        """根据聚合类型返回 PyPika 对应的函数"""

        from core.sql.functions import DisCount

        aggregate_mapping = {
            cls.COUNT.value: fn.Count,
            cls.SUM.value: fn.Sum,
            cls.AVG.value: fn.Avg,
            cls.MAX.value: fn.Max,
            cls.MIN.value: fn.Min,
            cls.DISCOUNT.value: DisCount,
        }
        if aggregate_type not in aggregate_mapping:
            raise ValueError(f"不支持的聚合类型: {aggregate_type}")
        return aggregate_mapping[aggregate_type]

    @cached_property
    def result_data_type(self):
        """
        返回聚合函数的结果数据类型
        """
        if self.value in {self.COUNT, self.DISCOUNT}:
            return FieldType.LONG


class JoinType(TextChoices):
    """
    连接类型
    """

    INNER_JOIN = "inner_join", gettext_lazy("inner_join")
    LEFT_JOIN = "left_join", gettext_lazy("left_join")
    RIGHT_JOIN = "right_join", gettext_lazy("right_join")
    FULL_OUTER_JOIN = "full_outer_join", gettext_lazy("full_join")


DORIS_FIELD_KEY_QUOTE = "'"


class Operator(TextChoices):
    """匹配符"""

    EQ = "eq", gettext_lazy("=")
    NEQ = "neq", gettext_lazy("!=")
    GT = "gt", gettext_lazy(">")
    LT = "lt", gettext_lazy("<")
    GTE = "gte", gettext_lazy(">=")
    LTE = "lte", gettext_lazy("<=")
    INCLUDE = "include", gettext_lazy("in")
    EXCLUDE = "exclude", gettext_lazy("not in")
    LIKE = "like", gettext_lazy("like")
    NOT_LIKE = "not_like", gettext_lazy("not like")
    ISNULL = "isnull", gettext_lazy("is null")
    NOTNULL = "notnull", gettext_lazy("is not null")
    MATCH_ALL = "match_all", gettext_lazy("match all")
    MATCH_ANY = "match_any", gettext_lazy("match any")
    BETWEEN = "between", gettext_lazy("between")

    @classmethod
    def handler(cls, operator: str, field: Field, value: str | int | float, values: List[str | int | float]):
        from core.sql.terms import DorisField

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
        else:
            raise UnsupportedOperatorError(operator)

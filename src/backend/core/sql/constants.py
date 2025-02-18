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
from typing import List

from django.utils.translation import gettext_lazy
from pypika import Field
from pypika import functions as fn

from core.choices import TextChoices


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


class JoinType(TextChoices):
    """
    连接类型
    """

    INNER_JOIN = "inner_join", gettext_lazy("内连接")
    LEFT_JOIN = "left_join", gettext_lazy("左连接")
    RIGHT_JOIN = "right_join", gettext_lazy("右连接")
    FULL_OUTER_JOIN = "full_outer_join", gettext_lazy("全连接")


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
    REG = "reg", gettext_lazy("regex")
    NREG = "nreg", gettext_lazy("not regex")

    @classmethod
    def handler(cls, operator: str, field: Field, value: str | int | float, values: List[str | int | float]):
        # 根据操作符类型调用对应的处理函数
        if not value and values:
            value = values[0]
        match operator:
            case cls.EQ:
                return field == value
            case cls.NEQ:
                return field != value
            case cls.INCLUDE:
                return field.isin(values)
            case cls.EXCLUDE:
                return ~field.isin(values)
            case cls.LIKE:
                return field.like(str(value))
            case cls.NOT_LIKE:
                return ~field.like(str(value))
            case cls.REG:
                return field.regex(str(value))
            case cls.NREG:
                return ~field.regex(str(value))
            case cls.LTE:
                return field.lte(value)
            case cls.LT:
                return field.lt(value)
            case cls.GTE:
                return field.gte(value)
            case cls.GT:
                return field.gt(value)
            case cls.ISNULL:
                return field.isnull()
            case cls.NOTNULL:
                return field.notnull()
            case _:
                return None

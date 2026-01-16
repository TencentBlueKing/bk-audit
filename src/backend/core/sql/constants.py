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

from django.utils.translation import gettext_lazy

from core.choices import TextChoices, register_choices


class FilterConnector(TextChoices):
    """
    Filter Connector
    """

    AND = "and", gettext_lazy("AND")
    OR = "or", gettext_lazy("OR")


@register_choices("core_sql_field_type")
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

    @cached_property
    def sql_data_type(self):
        """
        返回 Hive / Flink 通用 SQL 类型
        """
        type_mapping = {
            self.STRING: 'string',
            self.DOUBLE: 'double',
            self.INT: 'int',
            self.LONG: 'long',
            self.TEXT: 'string',
            self.TIMESTAMP: 'long',
            self.FLOAT: 'float',
        }
        return type_mapping[self.value]

    @cached_property
    def query_data_type(self):
        """
        返回查询阶段 CAST 可使用的 SQL 类型
        """
        type_mapping = {
            self.STRING: "STRING",
            self.DOUBLE: "DOUBLE",
            self.INT: "INT",
            self.LONG: "BIGINT",
            self.TEXT: "TEXT",
            self.TIMESTAMP: "BIGINT",
            self.FLOAT: "FLOAT",
        }
        return type_mapping[self.value]


class JoinType(TextChoices):
    """
    连接类型
    """

    INNER_JOIN = "inner_join", gettext_lazy("inner_join")
    LEFT_JOIN = "left_join", gettext_lazy("left_join")
    RIGHT_JOIN = "right_join", gettext_lazy("right_join")
    FULL_OUTER_JOIN = "full_outer_join", gettext_lazy("full_join")


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
    LIST = "LIST", gettext_lazy("列表")
    LIST_DISTINCT = "LIST_DISTINCT", gettext_lazy("去重列表")

    @cached_property
    def result_data_type(self):
        """
        返回聚合函数的结果数据类型
        """
        if self.value in {self.COUNT, self.DISCOUNT}:
            return FieldType.LONG
        if self.value in {self.LIST, self.LIST_DISTINCT}:
            return FieldType.STRING


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
    JSON_CONTAINS = "json_contains", gettext_lazy("json contains")
    BETWEEN = "between", gettext_lazy("between")

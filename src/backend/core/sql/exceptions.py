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

from django.utils.translation import gettext_lazy


class SQLGeneratorError(Exception):
    """基础异常类，用于所有 SQLGenerator 相关的异常。"""


class TableNotRegisteredError(SQLGeneratorError):
    """当请求的表未在配置中注册时抛出。"""

    MESSAGE = gettext_lazy("表 '{table_name}' 未在配置中声明。")

    def __init__(self, table_name: str):
        message = self.MESSAGE.format(table_name=table_name)
        super().__init__(message)


class UnsupportedJoinTypeError(SQLGeneratorError):
    """当使用了不支持的 JOIN 类型时抛出。"""

    MESSAGE = gettext_lazy("不支持的 JOIN 类型：'{join_type}'。")

    def __init__(self, join_type: str):
        message = self.MESSAGE.format(join_type=join_type)
        super().__init__(message)


class UnsupportedOperatorError(SQLGeneratorError):
    """当使用了不支持的操作符时抛出。"""

    MESSAGE = gettext_lazy("不支持的操作符：'{operator}'。")

    def __init__(self, operator: str):
        message = self.MESSAGE.format(operator=operator)
        super().__init__(message)


class InvalidAggregateTypeError(SQLGeneratorError):
    """当使用了无效的聚合类型时抛出。"""

    MESSAGE = gettext_lazy("不支持的聚合类型：'{aggregate_type}'。")

    def __init__(self, aggregate_type: str):
        message = self.MESSAGE.format(aggregate_type=aggregate_type)
        super().__init__(message)


class MissingFromOrJoinError(SQLGeneratorError):
    """当既未指定 from_table 也未指定 join_tables 时抛出。"""

    MESSAGE = gettext_lazy("配置中必须指定 `from_table` 或 `join_tables`。")

    def __init__(self):
        super().__init__(self.MESSAGE)


class OperatorValueError(SQLGeneratorError):
    """当操作符值错误时抛出。"""

    MESSAGE = gettext_lazy("操作符 {operator} 的值 {value} 不符合预期。")

    def __init__(self, value, operator):
        message = self.MESSAGE.format(value=value, operator=operator)
        super().__init__(message)


class FilterValueError(SQLGeneratorError):
    """当过滤值错误时抛出。"""

    MESSAGE = gettext_lazy("条件表达式中字段 {field} 的值 {value} 无法转换成预期类型 {type}。")

    def __init__(self, field, value, type):
        message = self.MESSAGE.format(field=field, type=type, value=value)
        super().__init__(message)

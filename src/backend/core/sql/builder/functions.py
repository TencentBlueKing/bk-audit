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
from typing import Any, Optional, Self, Union

from pypika.functions import Cast, Count, DistinctOptionFunction
from pypika.terms import Function, Term

from core.sql.constants import FieldType


class DisCount(Count):
    """
    去重计数
    """

    def __init__(self, param, alias=None):
        super().__init__(param, alias=alias)
        self._distinct = True


class ConcatWs(Function):
    """
    CONCAT_WS函数
    """

    def __init__(self, separator, *args):
        super(ConcatWs, self).__init__("CONCAT_WS", separator, *args)


class JsonExtractFunction(Function):
    """
    通用 JSON 函数抽象基类，封装 returning_type 和 cast_to 逻辑
    """

    ENABLE_RETURN_TYPE_DECLARATION = True  # 控制是否启用类型声明

    def __init__(
        self, func_name: str, json_column: Term, json_path: str, returning_type: str = None, alias: str = None
    ):
        path_term = Term.wrap_constant(json_path)
        super().__init__(func_name, json_column, path_term, alias=alias)
        self._returning_type_str = returning_type.lower() if returning_type else None

    def cast_to(self, sql_type: Optional[str] = None, alias: str = None) -> Union[Cast, Self]:
        """统一类型转换逻辑，支持自动映射"""
        if self.ENABLE_RETURN_TYPE_DECLARATION and self._returning_type_str:
            type_str = sql_type or self._returning_type_str
            type_enum = FieldType(type_str)
            sql_type = type_enum.sql_data_type
            casted = Cast(self, sql_type)
            return casted.as_(alias) if alias else casted
        return self


class JsonValue(JsonExtractFunction):
    """
    JSON_VALUE 函数（Flink）
    """

    def __init__(self, json_column: Term, json_path: str, returning_type: str = None, alias: str = None):
        super().__init__("JSON_VALUE", json_column, json_path, returning_type, alias)


class GetJsonObject(JsonExtractFunction):
    """
    GET_JSON_OBJECT 函数（Hive）
    """

    def __init__(self, json_column: Term, json_path: str, returning_type: str = None, alias: str = None):
        super().__init__("GET_JSON_OBJECT", json_column, json_path, returning_type, alias)


class DateTrunc(Function):
    """日期截断函数"""

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__("DATE_TRUNC", *args, **kwargs)


class FromUnixTime(Function):
    """Unix时间戳转换为日期函数"""

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__("FROM_UNIXTIME", *args, **kwargs)


class PercentileApprox(Function):
    """近似百分位数函数"""

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__("PERCENTILE_APPROX", *args, **kwargs)


class JsonContains(Function):
    """JSON_CONTAINS 函数"""

    def __init__(self, json_doc: Term, candidate: Any, json_path: Optional[str] = None, alias: str = None):
        params = [json_doc, Term.wrap_constant(candidate)]
        if json_path:
            params.append(Term.wrap_constant(json_path))
        super().__init__("JSON_CONTAINS", *params, alias=alias)


class GroupConcat(DistinctOptionFunction):
    """
    GROUP_CONCAT 函数
    """

    def __init__(self, term: Term, alias: Optional[str] = None):
        super().__init__("GROUP_CONCAT", term, alias=alias)


class DisGroupConcat(GroupConcat):
    """
    GROUP_CONCAT DISTINCT 函数（去重）
    """

    def __init__(self, term: Term, alias: Optional[str] = None):
        super().__init__(term, alias=alias)
        self._distinct = True


class Concat(Function):
    """
    CONCAT 函数
    """

    def __init__(self, *terms: Term):
        super().__init__("CONCAT", *terms)

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

from pypika.functions import Cast, Count
from pypika.terms import Function, Term


class DisCount(Count):
    """
    去重计数
    """

    def __init__(self, param, alias=None):
        super().__init__(param, alias=alias)
        self.distinct()


class ConcatWs(Function):
    """
    CONCAT_WS函数
    """

    def __init__(self, separator, *args):
        super(ConcatWs, self).__init__("CONCAT_WS", separator, *args)


class JsonValue(Function):
    """
    JSON_VALUE函数,用于Flink SQL
    """

    ENABLE_RETURN_TYPE_DECLARATION = False  # bkbase暂不支持RETURNING {type} 声明

    def __init__(self, json_column: Term, json_path: str, returning_type: str = None, alias: str = None):
        path_term = Term.wrap_constant(json_path)
        super().__init__("JSON_VALUE", json_column, path_term, alias=alias)
        self._returning_type_str = returning_type.upper() if returning_type else None

    def get_special_params_sql(self, **kwargs: Any) -> Any:
        """添加RETURNING信息到SQL中"""
        if self.ENABLE_RETURN_TYPE_DECLARATION and self._returning_type_str:
            return f"RETURNING {self._returning_type_str}"


class GetJsonObject(Function):
    """
    GET_JSON_OBJECT函数,用于Hive SQL
    """

    ENABLE_RETURN_TYPE_DECLARATION = False  # bkbase暂不支持CAST和GET_JSON_OBJECT复合声明

    def __init__(self, json_column: Term, json_path: str, returning_type: str = None, alias: str = None):
        path_term = Term.wrap_constant(json_path)
        super().__init__("GET_JSON_OBJECT", json_column, path_term, alias=alias)
        self._returning_type_str = returning_type.upper() if returning_type else None

    def cast_to(self, sql_type: Optional[str] = None, alias: str = None) -> Union[Cast, Self]:
        """将结果转换为指定类型"""
        if self.ENABLE_RETURN_TYPE_DECLARATION and self._returning_type_str:
            sql_type = (sql_type or self._returning_type_str).upper()
            casted_expression = Cast(self, sql_type)

            if alias:
                return casted_expression.as_(alias)
            return casted_expression
        else:
            return self


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

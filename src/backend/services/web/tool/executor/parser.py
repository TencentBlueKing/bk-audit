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
import abc
import numbers
from typing import Any, Callable

from arrow import ParserError
from blueapps.utils.logger import logger

from core.sql.parser.model import RangeVariableData
from core.utils.time import parse_datetime
from services.web.tool.constants import (
    ApiInputVariableUnion,
    FieldCategory,
    SQLDataSearchInputVariable,
)
from services.web.tool.exceptions import (
    InputVariableValueError,
    InvalidVariableFormatError,
    InvalidVariableStructureError,
    ParseVariableError,
    VariableHasNoParseFunction,
)


class BaseVariableParser(abc.ABC):
    """
    变量解析器基类
    """

    def __init__(self, field_type: FieldCategory):
        self.field_type = field_type

    def _format_time_range_select(self, value: Any) -> RangeVariableData:
        """
        格式化时间范围选择器
        """
        if not isinstance(value, list) or len(value) != 2:
            raise InvalidVariableStructureError(var_type=self.field_type, expected_structure="一个包含2个元素的列表", value=value)
        start_time = self._format_time_select(value[0])
        end_time = self._format_time_select(value[1])
        return RangeVariableData(
            start=start_time,
            end=end_time,
        )

    def _format_time_select(self, value: Any) -> int:
        """
        格式化时间选择器 (毫秒时间戳)
        """
        if isinstance(value, numbers.Number):
            return int(value)
        try:
            return int(parse_datetime(value).timestamp()) * 1000
        except (ParserError, TypeError, ValueError):
            raise InvalidVariableFormatError(var_type=self.field_type, value=value)

    def _format_input(self, value: Any) -> Any:
        """
        格式化输入
        """
        # 如果值已经是字典或列表，直接返回，不进行str转换
        if isinstance(value, (dict, list)):
            return value
        return str(value)

    def _format_number_input(self, value: Any) -> int:
        """
        格式化数字输入
        """
        try:
            return int(value)
        except (ValueError, TypeError):
            raise InvalidVariableFormatError(var_type=self.field_type, value=value)

    def _format_person_select(self, value: Any) -> list:
        """
        格式化人员选择器 (默认保持列表)
        如果输入是字符串，则用逗号拆分为列表
        """
        if isinstance(value, str):
            return [v.strip() for v in value.split(",") if v.strip()]
        if not isinstance(value, list):
            return [str(value)]
        return [str(v) for v in value]

    def _format_multiselect(self, value: Any) -> list:
        """
        格式化多选下拉框 (默认保持列表)
        """
        if isinstance(value, list):
            return value
        return [value]

    def parse(self, value: Any) -> Any:
        """
        解析变量值
        """
        func: Callable[[Any], Any] = getattr(self, f"_format_{self.field_type.value}", None)
        if not func:
            raise VariableHasNoParseFunction(var_type=self.field_type)
        try:
            return func(value)
        except InputVariableValueError:
            raise
        except Exception as e:
            logger.error(f"VariableValueParser 解析错误: {e}", exc_info=True)
            raise ParseVariableError(var_type=self.field_type, value=value)


class SqlVariableParser(BaseVariableParser):
    """
    SQL 变量解析器
    """

    def __init__(self, variable: SQLDataSearchInputVariable):
        super().__init__(variable.field_category)


class ApiVariableParser(BaseVariableParser):
    """
    API 变量解析器
    """

    def __init__(self, variable: ApiInputVariableUnion):
        super().__init__(variable.field_category)

    def _format_person_select(self, value: Any) -> str:
        """
        格式化人员选择器 (API 工具中转为逗号拼接的字符串)
        如果输入是字符串，则用逗号拆分后再重新拼接（去除空白）
        """
        if isinstance(value, str):
            # 用逗号拆分，去除空白后重新拼接
            return ",".join(v.strip() for v in value.split(",") if v.strip())
        if not isinstance(value, list):
            return str(value)
        return ",".join(str(v) for v in value)

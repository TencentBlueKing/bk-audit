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
from typing import Any, Callable, Dict, Generic, Optional, Type, TypeVar, Union

from arrow import ParserError
from bk_resource import api
from bk_resource.exceptions import APIRequestError
from blueapps.utils.logger import logger
from pydantic import BaseModel

from api.bk_base.constants import UserAuthActionEnum
from core.models import get_request_username
from core.sql.parser.model import RangeVariableData
from core.sql.parser.praser import SqlQueryAnalysis
from core.utils.time import parse_datetime
from services.web.tool.constants import (
    BkvisionConfig,
    DataSearchConfigTypeEnum,
    SQLDataSearchConfig,
    SQLDataSearchInputVariable,
    ToolTypeEnum,
)
from services.web.tool.exceptions import (
    BkbaseApiRequestError,
    DataSearchTablePermission,
    InputVariableMissingError,
    InputVariableValueError,
    InvalidVariableFormatError,
    InvalidVariableStructureError,
    ParseVariableError,
    VariableHasNoParseFunction,
)
from services.web.tool.executor.model import (
    BkVisionExecuteResult,
    DataSearchToolExecuteParams,
    DataSearchToolExecuteResult,
)
from services.web.tool.models import Tool
from services.web.tool.permissions import check_bkvision_share_permission
from services.web.vision.handlers.query import VisionHandler

TConfig = TypeVar('TConfig', bound=BaseModel)
TParams = TypeVar('TParams', bound=BaseModel)
TResult = TypeVar('TResult', bound=BaseModel)


class BaseToolExecutor(abc.ABC, Generic[TConfig, TParams, TResult]):
    """工具执行器基类"""

    tool: Optional[Tool]
    config: TConfig

    def __init__(self, source: Union[Tool, BaseModel]):
        """
        初始化执行器
        :param source: 可以是Tool对象或直接配置对象
        """

        if isinstance(source, Tool):
            self.tool = source
            self.config = self._parse_config(source)
        else:
            self.tool = None
            self.config = source

    @classmethod
    @abc.abstractmethod
    def _parse_config(cls, tool: Tool) -> TConfig:
        """
        从Tool对象解析配置
        """

        raise NotImplementedError()

    @abc.abstractmethod
    def _parse_params(self, params: dict) -> TParams:
        """
        解析输入参数
        """

        raise NotImplementedError()

    def validate_permission(self, params: TParams):
        """
        校验权限
        """

        pass

    @abc.abstractmethod
    def _execute(self, params: TParams) -> TResult:
        """
        执行工具
        """

        raise NotImplementedError()

    def execute(self, params: dict):
        params = self._parse_params(params)
        self.validate_permission(params)
        return self._execute(params)


class VariableValueParser:
    """
    变量值解析器
    """

    def __init__(self, variable: SQLDataSearchInputVariable):
        self.variable = variable

    def _format_time_range_select(self, value: Any) -> RangeVariableData:
        """
        格式化时间范围选择器
        """

        if not isinstance(value, list) or len(value) != 2:
            raise InvalidVariableStructureError(
                var_type=self.variable.field_category, expected_structure="一个包含2个元素的列表", value=value
            )
        # 来自 _format_time_select 的更具体的 InvalidVariableFormatError 将会被传递上来
        start_time = self._format_time_select(value[0])
        end_time = self._format_time_select(value[1])
        return RangeVariableData(
            start=start_time,
            end=end_time,
        )

    def _format_time_select(self, value: Any) -> int:
        """
        格式化时间选择器
        """
        if isinstance(value, numbers.Number):
            return int(value)
        try:
            return int(parse_datetime(value).timestamp()) * 1000
        except (ParserError, TypeError, ValueError):
            raise InvalidVariableFormatError(var_type=self.variable.field_category, value=value)

    def _format_input(self, value: Any) -> str:
        """
        格式化输入
        """

        return str(value)

    def _format_number_input(self, value: Any) -> int:
        """
        格式化数字输入
        """

        try:
            return int(value)
        except (ValueError, TypeError):
            raise InvalidVariableFormatError(var_type=self.variable.field_category, value=value)

    def _format_person_select(self, value: Any) -> list | str:
        """
        格式化人员选择器为 sql 中的 in
        """

        if not isinstance(value, list):
            return str(value)
        return [str(v) for v in value]

    def _format_multiselect(self, value: Any) -> list:
        """
        格式化多选下拉框
        """
        if isinstance(value, list):
            return value
        return [value]

    def parse(self, value: Any) -> Any:
        """
        解析变量值
        """

        func: Callable[[Any], Any] = getattr(self, f"_format_{self.variable.field_category.value}", None)
        if not func:
            raise VariableHasNoParseFunction(var_type=self.variable.field_category)
        try:
            return func(value)
        # 捕获任何用户输入错误 (结构、格式等) 并重新抛出它。这允许具体的异常冒泡到上层。
        except InputVariableValueError:
            raise
        # 捕获任何其他意外错误并将其包装为通用的内部错误。
        except Exception as e:
            logger.error(f"VariableValueParser 解析错误: {e}", exc_info=True)
            raise ParseVariableError(var_type=self.variable.field_category, value=value)


class SqlDataSearchExecutor(
    BaseToolExecutor[SQLDataSearchConfig, DataSearchToolExecuteParams, DataSearchToolExecuteResult]
):
    """SQL数据查询执行器"""

    def __init__(self, source: Union[Tool, SQLDataSearchConfig], analyzer_cls: Type[SqlQueryAnalysis]):
        super().__init__(source)
        self.analyzer = analyzer_cls(sql=self.config.sql)

    @classmethod
    def _parse_config(cls, tool: Tool) -> TConfig:
        return SQLDataSearchConfig.model_validate(tool.config)

    def _parse_params(self, params):
        return DataSearchToolExecuteParams.model_validate(params)

    def validate_permission(self, params: DataSearchToolExecuteParams):
        """
        校验权限: 校验工具更新人 or 当前请求用户有表查询条件
        """
        user_id = self.tool.updated_by if self.tool else get_request_username()
        parsed_def = self.analyzer.get_parsed_def()
        permissions = [
            {
                "user_id": user_id,
                "action_id": UserAuthActionEnum.RT_QUERY.value,
                "object_id": table.table_name,
            }
            for table in parsed_def.referenced_tables
        ]
        bulk_resp = api.bk_base.user_auth_batch_check({"permissions": permissions})
        for rt in bulk_resp:
            if rt.get("result"):
                continue
            raise DataSearchTablePermission(rt.get("user_id"), rt.get("object_id"))

    def render_value(self, var: SQLDataSearchInputVariable, value: Any) -> Any:
        """
        渲染变量值
        """

        return VariableValueParser(var).parse(value)

    def render_variables(self, params: DataSearchToolExecuteParams) -> Dict[str, Any]:
        """
        渲染变量
        """

        origin_variable_values = {tv.raw_name: tv.value for tv in params.tool_variables}
        rendered_variable_values = {}
        for var in self.config.input_variable:
            origin_value = origin_variable_values.get(var.raw_name, None)
            # 变量值存在进行渲染
            if origin_value is not None:
                rendered_value = self.render_value(var, origin_value)
            # 变量值不存在 or 为空校验是否必填
            elif var.required:
                raise InputVariableMissingError(var.display_name)
            # 变量值非必填且不存在默认给 None
            else:
                rendered_value = None
            rendered_variable_values[var.raw_name] = rendered_value
        return rendered_variable_values

    def _execute(self, params: DataSearchToolExecuteParams):
        """
        执行 SQL 数据查询
        """

        # 渲染变量
        variable_values_for_rendering = self.render_variables(params)
        # 生成可执行的 SQL
        limit = params.page_size
        offset = (params.page - 1) * params.page_size
        sql_result = self.analyzer.generate_sql_with_values(
            params=variable_values_for_rendering, limit=limit, offset=offset, with_count=True
        )
        logger.info(f"{[self.__class__.__name__]} Execute SQL: {sql_result}")
        executable_sql = sql_result["data"]
        count_sql = sql_result["count"]
        bulk_req_params = [
            {
                "sql": executable_sql,
            },
            {
                "sql": count_sql,
            },
        ]
        # 请求 BKBASE
        try:
            bulk_resp = api.bk_base.query_sync.bulk_request(bulk_req_params)
        except APIRequestError as e:
            logger.error(f"{[self.__class__.__name__]} Request BKBASE Error: {e}")
            raise BkbaseApiRequestError(sql=executable_sql)
        data_resp, count_resp = bulk_resp
        total = count_resp.get("list", [{}])[0].get("count", 0)
        return DataSearchToolExecuteResult(
            page=params.page,
            num_pages=params.page_size,
            total=total,
            results=data_resp.get("list", []),
            query_sql=executable_sql,
            count_sql=count_sql,
        )


class BkVisionExecutor(BaseToolExecutor[BkvisionConfig, None, BkVisionExecuteResult]):
    """BK Vision执行器"""

    @classmethod
    def _parse_config(cls, tool: Tool) -> TConfig:
        return BkvisionConfig.model_validate(tool.config)

    def _parse_params(self, params: dict) -> TParams:
        pass

    def validate_permission(self, params=None):
        """
        校验权限: 校验工具更新人 or 当前请求用户是否有 bkvision 嵌入记录权限。
        """
        user_id = self.tool.updated_by if self.tool else get_request_username()
        share_uid = self.config.uid
        check_bkvision_share_permission(user_id, share_uid)

    def _execute(self, params=None) -> BkVisionExecuteResult:
        """
        执行 BK Vision 工具
        """

        if self.tool:
            panel = self.tool.bkvision_config.panel
        else:
            panel = Tool.fetch_tool_vision_panel(
                vision_id=self.config.uid,
                handler=VisionHandler.__name__,
            )
        return BkVisionExecuteResult(panel_id=panel.id)


class ToolExecutorFactory:
    """工具执行器工厂"""

    def __init__(self, sql_analyzer_cls: Type[SqlQueryAnalysis]):
        self.sql_analyzer_cls = sql_analyzer_cls

    def create_from_tool(self, tool: Tool) -> BaseToolExecutor:
        """从Tool对象创建执行器"""
        if tool.tool_type == ToolTypeEnum.DATA_SEARCH.value:
            if tool.data_search_config.data_search_config_type == DataSearchConfigTypeEnum.SQL.value:
                return SqlDataSearchExecutor(tool, analyzer_cls=self.sql_analyzer_cls)
        elif tool.tool_type == ToolTypeEnum.BK_VISION.value:
            return BkVisionExecutor(tool)
        # 其他数据查询类型...
        raise ValueError(f"Unsupported tool type: {tool.tool_type}")

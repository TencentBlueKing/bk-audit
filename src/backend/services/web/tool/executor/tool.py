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
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union

import requests
from bk_resource import api
from bk_resource.exceptions import APIRequestError
from blueapps.utils.logger import logger
from django.conf import settings
from django.utils.translation import gettext
from pydantic import BaseModel

from api.bk_base.constants import UserAuthActionEnum
from core.models import get_request_username
from core.sql.parser.praser import SqlQueryAnalysis
from services.web.tool.constants import (
    ApiToolConfig,
    ApiVariablePosition,
    BkVisionConfig,
    DataSearchConfigTypeEnum,
    SQLDataSearchConfig,
    SQLDataSearchInputVariable,
    TimeRangeInputVariable,
    ToolTypeEnum,
)
from services.web.tool.exceptions import (
    ApiToolExecuteError,
    BkbaseApiRequestError,
    DataSearchTablePermission,
    InputVariableMissingError,
    ToolTypeNotSupport,
)
from services.web.tool.executor.auth import AuthHandlerFactory
from services.web.tool.executor.model import (
    ApiToolErrorType,
    APIToolExecuteParams,
    ApiToolExecuteResult,
    BkVisionExecuteResult,
    DataSearchToolExecuteParams,
    DataSearchToolExecuteResult,
)
from services.web.tool.executor.parser import ApiVariableParser, SqlVariableParser
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

    def __init__(self, source: Union[Tool, Any]):
        """
        初始化执行器
        :param source: 可以是Tool对象或直接配置对象
        """

        if isinstance(source, Tool):
            self.tool = source
            self.config = self._parse_config(source.config)
        else:
            self.tool = None
            self.config = self._parse_config(source)

    @classmethod
    @abc.abstractmethod
    def _parse_config(cls, config: Any) -> TConfig:
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


class SqlDataSearchExecutor(
    BaseToolExecutor[SQLDataSearchConfig, DataSearchToolExecuteParams, DataSearchToolExecuteResult]
):
    """SQL数据查询执行器"""

    def __init__(self, source: Union[Tool, Any], analyzer_cls: Type[SqlQueryAnalysis]):
        super().__init__(source)
        self.analyzer = analyzer_cls(sql=self.config.sql)

    @classmethod
    def _parse_config(cls, config: dict) -> TConfig:
        return SQLDataSearchConfig.model_validate(config)

    def _parse_params(self, params):
        return DataSearchToolExecuteParams.model_validate(params)

    def validate_permission(self, params: DataSearchToolExecuteParams):
        """
        校验权限: 校验工具更新人 or 当前请求用户有表查询条件
        """
        user_id = self.tool.get_permission_owner() if self.tool else get_request_username()
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

        return SqlVariableParser(var).parse(value)

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


class BkVisionExecutor(BaseToolExecutor[BkVisionConfig, None, BkVisionExecuteResult]):
    """BK Vision执行器"""

    @classmethod
    def _parse_config(cls, config: Any) -> TConfig:
        return BkVisionConfig.model_validate(config)

    def _parse_params(self, params: dict) -> TParams:
        pass

    def validate_permission(self, params=None):
        """
        校验权限: 校验工具更新人 or 当前请求用户是否有 bkvision 嵌入记录权限。
        """
        user_id = self.tool.get_permission_owner() if self.tool else get_request_username()
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


class ApiToolExecutor(BaseToolExecutor[ApiToolConfig, APIToolExecuteParams, ApiToolExecuteResult]):
    """API 工具执行器"""

    @classmethod
    def _parse_config(cls, config: Any) -> TConfig:
        return ApiToolConfig.model_validate(config)

    def _parse_params(self, params: dict) -> APIToolExecuteParams:
        """
        仅做结构解析，不做业务渲染
        """
        return APIToolExecuteParams.model_validate(params)

    def _render_request_params(self, params: APIToolExecuteParams) -> List[Dict[str, Any]]:
        """
        渲染请求参数：校验、格式化、拆分时间范围
        """
        tool_vars_map = {var.raw_name: var.value for var in params.tool_variables}
        final_params = []

        for var_config in self.config.input_variable:
            # 1. 获取值
            value = tool_vars_map.get(var_config.raw_name)

            # 2. 校验
            if var_config.required and value is None:
                raise InputVariableMissingError(var_config.display_name)
            elif value is None:
                # 非必填且无值，不传
                continue

            # 3. 格式化值
            parsed_value = ApiVariableParser(var_config).parse(value)

            # 4. 特殊处理：时间范围拆分
            if isinstance(var_config, TimeRangeInputVariable):
                final_params.extend(
                    [
                        {
                            "name": var_config.split_config.start_field,
                            "value": parsed_value.start,
                            "position": var_config.position,
                        },
                        {
                            "name": var_config.split_config.end_field,
                            "value": parsed_value.end,
                            "position": var_config.position,
                        },
                    ]
                )
            else:
                # 5. 普通参数直接添加
                final_params.append(
                    {
                        "name": var_config.var_name,
                        "value": parsed_value,
                        "position": var_config.position,
                    }
                )

        return final_params

    def _execute(self, params: APIToolExecuteParams) -> ApiToolExecuteResult:
        # 1. 渲染参数
        request_params = self._render_request_params(params)

        # 2. 分类参数
        path_params = {}
        query_params = {}
        body_params = {}

        for param in request_params:
            position = param["position"]
            name = param["name"]
            value = param["value"]

            if position == ApiVariablePosition.PATH:
                path_params[name] = value
            elif position == ApiVariablePosition.QUERY:
                query_params[name] = value
            elif position == ApiVariablePosition.BODY:
                body_params[name] = value

        # 3. 准备 URL 和 Headers
        api_config = self.config.api_config
        try:
            url = api_config.url.format(**path_params)
        except KeyError as e:
            raise ApiToolExecuteError(status_code=400, detail=gettext("URL 路径参数缺失: %s") % e)

        method = api_config.method.lower()
        headers = {h.key: h.value for h in api_config.headers}

        # 4. 应用认证
        auth_handler = AuthHandlerFactory.get_handler(api_config.auth_config)
        auth_handler.apply_auth(headers)

        # 5. 发送请求
        request_kwargs = {}
        if query_params:
            request_kwargs["params"] = query_params
        if body_params:
            request_kwargs["json"] = body_params

        try:
            # 日志脱敏
            safe_headers = auth_handler.mask_headers(headers)
            logger.info(
                f"[{self.__class__.__name__}] Request: {method.upper()} {url}, "
                f"headers={safe_headers}, kwargs={request_kwargs}"
            )

            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                timeout=settings.API_TOOL_EXECUTE_DEFAULT_TIMEOUT,
                **request_kwargs,
            )
            try:
                parsed_result = response.json()
                return ApiToolExecuteResult(
                    status_code=response.status_code,
                    result=parsed_result,
                    err_type=ApiToolErrorType.NONE,
                    message="",
                )
            except ValueError:
                return ApiToolExecuteResult(
                    status_code=response.status_code,
                    result=None,
                    err_type=ApiToolErrorType.NON_JSON_RESPONSE,
                    message=(
                        response.text[: settings.API_TOOL_EXECUTE_DEFAULT_MAX_RETURN_CHAR] if response.text else ""
                    ),
                )
        except requests.RequestException as e:
            return ApiToolExecuteResult(
                status_code=500,
                result=None,
                err_type=ApiToolErrorType.REQUEST_ERROR,
                message=str(e),
            )
        except Exception as e:  # NOCC:broad-except(需要处理所有错误)
            logger.error(f"[{self.__class__.__name__}] Request Failed: {e}", exc_info=True)
            raise ApiToolExecuteError(status_code=500, detail=gettext("请求异常，请联系系统管理员"))


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
        elif tool.tool_type == ToolTypeEnum.API.value:
            return ApiToolExecutor(tool)
        # 其他数据查询类型...
        raise ToolTypeNotSupport()

    def create_from_config(
        self,
        tool_type: str,
        config: dict,
        data_search_config_type: DataSearchConfigTypeEnum = DataSearchConfigTypeEnum.SQL.value,
    ) -> BaseToolExecutor:
        """
        从配置创建执行器 (用于调试)
        """
        if (
            tool_type == ToolTypeEnum.DATA_SEARCH.value
            and data_search_config_type == DataSearchConfigTypeEnum.SQL.value
        ):
            return SqlDataSearchExecutor(config, analyzer_cls=self.sql_analyzer_cls)
        elif tool_type == ToolTypeEnum.API.value:
            return ApiToolExecutor(config)
        # BkVision 不支持调试执行
        raise ToolTypeNotSupport()

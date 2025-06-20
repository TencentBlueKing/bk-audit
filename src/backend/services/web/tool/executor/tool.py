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
from typing import Any, Dict, Generic, Optional, Type, TypeVar, Union

from bk_resource import api
from pydantic import BaseModel

from api.bk_base.constants import UserAuthActionEnum
from apps.permission.handlers.actions import ActionEnum
from apps.permission.handlers.permission import Permission
from apps.permission.handlers.resource_types import ResourceEnum
from core.models import get_request_username
from services.web.tool.constants import (
    BkvisionConfig,
    DataSearchConfigTypeEnum,
    SQLDataSearchConfig,
    ToolTypeEnum,
)
from services.web.tool.exceptions import DataSearchTablePermission
from services.web.tool.executor.model import (
    BkVisionExecuteResult,
    DataSearchToolExecuteParams,
    DataSearchToolExecuteResult,
)
from services.web.tool.models import Tool
from services.web.tool.parser.model import ParsedSQLInfo
from services.web.vision.handlers.query import VisionHandler


class SqlQueryAnalysis(abc.ABC):
    def __init__(self, sql: str):
        """
        初始化 SQL 查询分析器。
        """
        self.sql = sql

    def generate_sql_with_values(self, params: Dict[str, Any], page: int, page_size: int) -> str:
        """
        根据提供的参数生成可执行的 SQL。
        """

        pass

    def generate_count_sql_with_values(self, params: Dict[str, Any]) -> str:
        """
        根据提供的参数生成统计总数 SQL。
        """

        pass

    def get_parsed_def(self) -> ParsedSQLInfo:
        """
        获取解析后的SQL信息
        """

        pass


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
        TODO: 使用批量 check 接口
        """
        user_id = self.tool.updated_by if self.tool else get_request_username()
        parsed_def = self.analyzer.get_parsed_def()
        bulk_params = [
            {
                "user_id": user_id,
                "action_id": UserAuthActionEnum.RT_QUERY.value,
                "object_id": table.table_name,
            }
            for table in parsed_def.referenced_tables
        ]
        bulk_resp = api.bk_base.user_auth_check.bulk_request(bulk_params)
        for param, resp in zip(bulk_params, bulk_resp):
            if resp:
                continue
            raise DataSearchTablePermission(param["user_id"], param["object_id"])

    def _execute(self, params: TParams):
        """
        执行 SQL 数据查询
        """

        # 渲染变量
        variable_values_for_rendering = {tv.raw_name: tv.value for tv in params.tool_variables}
        # 生成可执行的 SQL
        executable_sql = self.analyzer.generate_sql_with_values(
            params=variable_values_for_rendering, page=params.page, page_size=params.page_size
        )
        count_sql = self.analyzer.generate_count_sql_with_values(params=variable_values_for_rendering)
        bulk_req_params = [
            {
                "sql": executable_sql,
                "prefer_storage": self.config.prefer_storage,
            },
            {
                "sql": count_sql,
                "prefer_storage": self.config.prefer_storage,
            },
        ]
        # 请求 BKBASE
        bulk_resp = api.bk_base.query_sync.bulk_request(bulk_req_params)
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
        校验权限: 校验工具更新人 or 当前请求用户是否有权限查看 bkvision 嵌入记录
        """

        user_id = self.tool.updated_by if self.tool else get_request_username()
        Permission(user_id).is_allowed(
            action=ActionEnum.VIEW_SHARE_BKVISION,
            resources=[ResourceEnum.SHARE_BK_VISION.create_instance(self.config.uid)],
            raise_exception=True,
        )

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

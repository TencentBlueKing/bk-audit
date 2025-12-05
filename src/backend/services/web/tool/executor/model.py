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
from typing import Any, List

from pydantic import BaseModel
from pydantic import Field as PydanticField

from services.web.tool.constants import BkVisionConfig

DATA_SEARCH_TOOL_DEFAULT_PAGE_SIZE = 100


class ToolVariable(BaseModel):
    """
    工具变量
    """

    raw_name: str = PydanticField(..., title="工具使用的变量名")
    value: Any = PydanticField(..., title="工具使用的变量值")


class DataSearchToolExecuteParams(BaseModel):
    """
    数据查询工具执行参数
    """

    tool_variables: List[ToolVariable] = PydanticField(list, title="工具使用的变量列表")
    page: int = PydanticField(1, title="页码")
    page_size: int = PydanticField(DATA_SEARCH_TOOL_DEFAULT_PAGE_SIZE, title="每页条数")


class DataSearchToolExecuteResult(BaseModel):
    """
    数据查询工具执行结果
    """

    page: int
    num_pages: int
    total: int
    results: List[dict]
    query_sql: str
    count_sql: str


class BkVisionExecuteResult(BaseModel):
    """
    BkVision执行结果
    """

    panel_id: str


class ApiToolExecuteResult(BaseModel):
    """
    Api工具执行结果
    """
    results: Any = PydanticField(..., title="Api工具执行结果")
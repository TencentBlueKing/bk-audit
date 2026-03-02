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
from typing import Annotated, List, Union

from django.utils.translation import gettext_lazy
from drf_pydantic import BaseModel
from pydantic import Field as PydanticField
from rest_framework.fields import JSONField

from services.web.tool.constants import ApiToolErrorType, ApiVariablePosition

DATA_SEARCH_TOOL_DEFAULT_PAGE_SIZE = 100
AnyValue = Annotated[Union[str, int, float, bool, dict, list, None], JSONField(allow_null=True)]


class ToolVariable(BaseModel):
    """
    工具变量

    注意：
    - 对于非必填变量，如果用户未输入值，前端应传入 `value: null` 来表示用户未输入
    - 后台会忽略 `value` 为 `null` 的非必填变量，不会进行变量替换或校验
    - 必填变量必须提供有效的值，不能为 `null`
    """

    raw_name: str = PydanticField(..., title="工具使用的变量名")
    value: AnyValue = PydanticField(..., title="工具使用的变量值")


class DataSearchToolExecuteParams(BaseModel):
    """
    数据查询工具执行参数
    """

    tool_variables: List[ToolVariable] = PydanticField(default_factory=list, title="工具使用的变量列表")
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

    status_code: int = PydanticField(..., title="HTTP 响应状态码")
    result: AnyValue = PydanticField(..., title="Api工具执行结果")
    err_type: ApiToolErrorType = PydanticField(
        default=ApiToolErrorType.NONE, title=gettext_lazy("错误类型"), description=gettext_lazy("标识执行异常原因")
    )
    message: str = PydanticField(default="", title=gettext_lazy("错误信息"))


class APIToolExecuteParams(BaseModel):
    """
    API工具执行参数
    """

    tool_variables: List[ToolVariable] = PydanticField(default_factory=list, title="工具使用的变量列表")


class ApiRequestParam(BaseModel):
    """
    API 请求参数条目

    用于表示渲染后的单个请求参数，包含参数名、值和位置信息
    """

    name: str = PydanticField(..., title="参数名")
    value: AnyValue = PydanticField(..., title="参数值")
    position: ApiVariablePosition = PydanticField(..., title="参数位置")

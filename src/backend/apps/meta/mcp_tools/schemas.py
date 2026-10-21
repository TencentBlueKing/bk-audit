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
software distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.

audit-meta MCP 工具集的 Pydantic 契约（系统接入元数据探索）。

字段探索的响应契约直接复用日志工具的 ``GetLogFieldMetadataResponse``，
保持同一服务两种入口的输出完全一致，不维护平行定义。
"""

from typing import Annotated, List, Optional

from pydantic import BaseModel, ConfigDict, Field
from rest_framework import serializers

# 与日志工具 schemas 同一约定：模型可空字符串经服务层兜底为 ""，drf-pydantic 生成的
# CharField 默认 allow_blank=False，必须显式声明。注意：DRF 字段实例不可跨字段共享
# （bind 原地改写实例状态），Annotated 中的 CharField 必须在每个字段声明处独立创建。

# 与 AgentSearchCondition 的 scope_id 上限一致；防止超长标识压垮下游校验。
META_TOOL_MAX_SYSTEM_ID_LENGTH = 64
# 关键词检索上限；超长关键词无命中价值且易放大like成本。
META_TOOL_MAX_KEYWORD_LENGTH = 64

LIST_SYSTEMS_PAGE_SIZE = 20
LIST_SYSTEMS_MAX_PAGE_SIZE = 50
LIST_ACTIONS_PAGE_SIZE = 50
LIST_ACTIONS_MAX_PAGE_SIZE = 100

# 字段探索不采样根目录，默认时间窗只用于满足检索条件协议；取最近一天。
EXPLORE_FIELDS_LOOKBACK_DAYS = 1


class _MetaToolRequest(BaseModel):
    """audit-meta 工具请求的公共约束：禁止未知字段。"""

    model_config = ConfigDict(extra="forbid")


class ListAuditSystemsRequest(_MetaToolRequest):
    """系统列表请求：按当前用户检索权限列出已接入审计的系统。"""

    keyword: Optional[str] = Field(
        default=None,
        max_length=META_TOOL_MAX_KEYWORD_LENGTH,
        description="可选关键词，对 system_id、名称、描述做包含匹配；省略返回全部可检索系统。",
    )
    page: int = Field(default=1, ge=1, description="页码，从 1 开始。")
    page_size: int = Field(
        default=LIST_SYSTEMS_PAGE_SIZE,
        ge=1,
        le=LIST_SYSTEMS_MAX_PAGE_SIZE,
        description=f"每页数量，默认 {LIST_SYSTEMS_PAGE_SIZE}，最大 {LIST_SYSTEMS_MAX_PAGE_SIZE}。",
    )


class SystemSummary(BaseModel):
    """单个可检索系统的摘要，system_id 是后续工具与检索条件的系统标识。"""

    system_id: str = Field(..., description="系统 ID，后续工具与检索条件的 scope_id 使用该值。")
    name: Annotated[str, serializers.CharField(allow_blank=True)] = Field(..., description="系统名称。")
    description: Annotated[str, serializers.CharField(allow_blank=True)] = Field(..., description="系统描述，可能为空字符串。")
    audit_status: str = Field(..., description="审计接入状态，列表结果固定为 accessed（已接入）。")


class ListAuditSystemsResponse(BaseModel):
    """系统列表响应，按名称排序分页。"""

    systems: List[SystemSummary] = Field(default_factory=list, description="当前页系统摘要。")
    total: int = Field(..., ge=0, description="命中关键词的可检索系统总数。")
    page: int = Field(..., description="当前页码。")
    page_size: int = Field(..., description="当前页大小。")
    has_more: bool = Field(..., description="是否还有下一页。")


class GetAuditSystemDetailRequest(_MetaToolRequest):
    """系统详情请求。"""

    system_id: str = Field(
        ...,
        min_length=1,
        max_length=META_TOOL_MAX_SYSTEM_ID_LENGTH,
        description="系统 ID，必须来自 mcp_list_audit_systems 的返回。",
    )


class AuditSystemDetail(BaseModel):
    """接入系统概要详情，只暴露 Agent 决策所需的安全字段。"""

    system_id: str = Field(..., description="系统 ID。")
    name: Annotated[str, serializers.CharField(allow_blank=True)] = Field(..., description="系统中文名称，可能为空字符串。")
    name_en: Annotated[str, serializers.CharField(allow_blank=True)] = Field(..., description="系统英文名称，可能为空字符串。")
    description: Annotated[str, serializers.CharField(allow_blank=True)] = Field(..., description="系统描述，可能为空字符串。")
    audit_status: str = Field(..., description="审计接入状态（PENDING 待接入 / ACCESSED 已接入）。")
    source_type: str = Field(..., description="系统来源类型。")
    system_url: Annotated[str, serializers.CharField(allow_blank=True)] = Field(..., description="系统访问地址，可能为空字符串。")
    action_count: int = Field(..., ge=0, description="该系统已登记的操作数量。")
    resource_type_count: int = Field(..., ge=0, description="该系统已登记的资源类型数量。")


class GetAuditSystemDetailResponse(BaseModel):
    """系统详情响应。"""

    system: AuditSystemDetail = Field(..., description="系统概要详情。")


class ListSystemActionsRequest(_MetaToolRequest):
    """系统操作列表请求：把自然语言中的动作描述映射为 action_id 合法值。"""

    system_id: str = Field(
        ...,
        min_length=1,
        max_length=META_TOOL_MAX_SYSTEM_ID_LENGTH,
        description="系统 ID，必须来自 mcp_list_audit_systems 的返回。",
    )
    keyword: Optional[str] = Field(
        default=None,
        max_length=META_TOOL_MAX_KEYWORD_LENGTH,
        description="可选关键词，对 action_id、中英文名称、描述、操作类型做包含匹配。",
    )
    resource_type_id: Optional[str] = Field(
        default=None,
        max_length=META_TOOL_MAX_SYSTEM_ID_LENGTH,
        description="可选资源类型 ID，仅返回作用于该资源类型的操作。",
    )
    page: int = Field(default=1, ge=1, description="页码，从 1 开始。")
    page_size: int = Field(
        default=LIST_ACTIONS_PAGE_SIZE,
        ge=1,
        le=LIST_ACTIONS_MAX_PAGE_SIZE,
        description=f"每页数量，默认 {LIST_ACTIONS_PAGE_SIZE}，最大 {LIST_ACTIONS_MAX_PAGE_SIZE}。",
    )


class SystemActionItem(BaseModel):
    """单个操作：action_id 是检索条件 action_id 字段的合法值。"""

    action_id: str = Field(..., description="操作 ID，检索条件 action_id 字段的合法值。")
    name: Annotated[str, serializers.CharField(allow_blank=True)] = Field(..., description="操作中文名称。")
    name_en: Annotated[str, serializers.CharField(allow_blank=True)] = Field(..., description="操作英文名称，可能为空字符串。")
    # 模型 blank+null 双开：线上同时存在 null 与空串两种形态，显式声明 allow_null + allow_blank；
    # Optional[str] 经 drf-pydantic 只会得到 allow_null，空串仍会被默认 allow_blank=False 拒绝。
    type: Annotated[Optional[str], serializers.CharField(allow_null=True, allow_blank=True)] = Field(
        default=None, description="操作类型，可能为空。"
    )
    sensitivity: int = Field(..., description="敏感等级，0 表示普通。")
    description: Annotated[str, serializers.CharField(allow_blank=True)] = Field(..., description="操作描述，可能为空字符串。")
    resource_type_ids: List[str] = Field(
        default_factory=list,
        description="该操作作用的资源类型 ID 列表，可作为 resource_type 条件的参考值。",
    )


class ListSystemActionsResponse(BaseModel):
    """操作列表响应，按 action_id 排序分页。"""

    actions: List[SystemActionItem] = Field(default_factory=list, description="当前页操作。")
    total: int = Field(..., ge=0, description="命中条件的操作总数。")
    page: int = Field(..., description="当前页码。")
    page_size: int = Field(..., description="当前页大小。")
    has_more: bool = Field(..., description="是否还有下一页。")


class ListSystemResourceTypesRequest(_MetaToolRequest):
    """资源类型列表请求：把资源对象描述映射为 resource_type 合法值。"""

    system_id: str = Field(
        ...,
        min_length=1,
        max_length=META_TOOL_MAX_SYSTEM_ID_LENGTH,
        description="系统 ID，必须来自 mcp_list_audit_systems 的返回。",
    )
    keyword: Optional[str] = Field(
        default=None,
        max_length=META_TOOL_MAX_KEYWORD_LENGTH,
        description="可选关键词，对 resource_type_id、中英文名称、描述做包含匹配。",
    )
    page: int = Field(default=1, ge=1, description="页码，从 1 开始。")
    page_size: int = Field(
        default=LIST_ACTIONS_PAGE_SIZE,
        ge=1,
        le=LIST_ACTIONS_MAX_PAGE_SIZE,
        description=f"每页数量，默认 {LIST_ACTIONS_PAGE_SIZE}，最大 {LIST_ACTIONS_MAX_PAGE_SIZE}。",
    )


class SystemResourceTypeItem(BaseModel):
    """单个资源类型：resource_type_id 是检索条件 resource_type 字段的合法值。"""

    resource_type_id: str = Field(..., description="资源类型 ID，检索条件 resource_type 字段的合法值。")
    name: Annotated[str, serializers.CharField(allow_blank=True)] = Field(..., description="资源类型中文名称。")
    name_en: Annotated[str, serializers.CharField(allow_blank=True)] = Field(..., description="资源类型英文名称，可能为空字符串。")
    sensitivity: int = Field(..., description="敏感等级，0 表示普通。")
    description: Annotated[str, serializers.CharField(allow_blank=True)] = Field(..., description="资源类型描述，可能为空字符串。")
    ancestor: List[str] = Field(
        default_factory=list,
        description="直接父资源类型 ID 列表；空列表表示根资源类型。",
    )


class ListSystemResourceTypesResponse(BaseModel):
    """资源类型列表响应，按 resource_type_id 排序分页。"""

    resource_types: List[SystemResourceTypeItem] = Field(default_factory=list, description="当前页资源类型。")
    total: int = Field(..., ge=0, description="命中条件的资源类型总数。")
    page: int = Field(..., description="当前页码。")
    page_size: int = Field(..., description="当前页大小。")
    has_more: bool = Field(..., description="是否还有下一页。")


class ExploreSystemFieldsRequest(_MetaToolRequest):
    """系统字段探索请求：返回目标系统可检索字段的声明目录。

    目录复用日志工具 mcp_get_log_field_metadata 的根字段契约；需要按检索条件
    采样 JSON 子键时，改用 mcp_get_log_field_metadata 并传入完整 condition。
    """

    system_id: str = Field(
        ...,
        min_length=1,
        max_length=META_TOOL_MAX_SYSTEM_ID_LENGTH,
        description="系统 ID，必须来自 mcp_list_audit_systems 的返回。",
    )

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

audit-meta 工具集的元数据组装服务。

权限与可见性和检索链路同源：系统列表复用 SearchLogPermission.
get_auth_systems_by_username（候选系统口径），单系统工具先鉴权再校验
命名空间归属；字段探索直接复用日志工具的 LogFieldMetadataService，
鉴权、脱敏与响应预算全部内置，不重复实现。
"""

import logging
from datetime import timedelta

from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from apps.meta.constants import SystemAuditStatusEnum
from apps.meta.mcp_tools.errors import MetaQueryFailed, SystemNotAccessible
from apps.meta.mcp_tools.schemas import (
    EXPLORE_FIELDS_LOOKBACK_DAYS,
    AuditSystemDetail,
    GetAuditSystemDetailRequest,
    GetAuditSystemDetailResponse,
    ListAuditSystemsRequest,
    ListAuditSystemsResponse,
    ListSystemActionsRequest,
    ListSystemActionsResponse,
    ListSystemResourceTypesRequest,
    ListSystemResourceTypesResponse,
    SystemActionItem,
    SystemResourceTypeItem,
    SystemSummary,
)
from apps.meta.models import Action, ResourceType, ResourceTypeActionRelation, System
from apps.meta.permissions import SearchLogPermission

logger = logging.getLogger(__name__)


class MetaToolService:
    """audit-meta 五个工具的组装服务：鉴权 → 过滤 → 裁剪 → 分页。"""

    @classmethod
    def list_systems(
        cls, *, username: str, namespace: str, request: ListAuditSystemsRequest
    ) -> ListAuditSystemsResponse:
        """列出当前用户可检索日志的已接入系统。

        口径与意图识别候选系统一致：检索权限（系统直权 ∪ 场景间接授权）
        ∩ 已接入（audit_status=ACCESSED）。无权限时返回空列表，不抛权限异常。
        """

        _, authorized_ids = SearchLogPermission.get_auth_systems_by_username(namespace, username)
        if not authorized_ids:
            return ListAuditSystemsResponse(
                systems=[], total=0, page=request.page, page_size=request.page_size, has_more=False
            )

        queryset = System.objects.filter(
            system_id__in=list(authorized_ids),
            namespace=namespace,
            audit_status=SystemAuditStatusEnum.ACCESSED.value,
        )
        if request.keyword:
            queryset = queryset.filter(
                Q(system_id__icontains=request.keyword)
                | Q(name__icontains=request.keyword)
                | Q(description__icontains=request.keyword)
            )
        queryset = queryset.order_by("name", "system_id")
        total = queryset.count()
        offset = (request.page - 1) * request.page_size
        rows = queryset[offset : offset + request.page_size]
        return ListAuditSystemsResponse(
            systems=[
                SystemSummary(
                    system_id=row.system_id,
                    name=str(row.name or row.system_id),
                    description=str(row.description or ""),
                    audit_status=str(row.audit_status),
                )
                for row in rows
            ],
            total=total,
            page=request.page,
            page_size=request.page_size,
            has_more=offset + len(rows) < total,
        )

    @classmethod
    def get_system_detail(
        cls, *, username: str, namespace: str, request: GetAuditSystemDetailRequest
    ) -> GetAuditSystemDetailResponse:
        """获取单个接入系统的概要详情，只暴露 Agent 决策所需的安全字段。"""

        system = cls._get_accessible_system(username=username, namespace=namespace, system_id=request.system_id)
        try:
            action_count = Action.objects.filter(system_id=system.system_id).count()
            resource_type_count = ResourceType.objects.filter(system_id=system.system_id).count()
        except Exception as error:  # noqa: BLE001 - 计数失败收敛为领域错误，不泄露底层细节。
            logger.exception("[MetaToolService] count system meta failed")
            raise MetaQueryFailed() from error
        return GetAuditSystemDetailResponse(
            system=AuditSystemDetail(
                system_id=system.system_id,
                name=str(system.name or ""),
                name_en=str(system.name_en or ""),
                description=str(system.description or ""),
                audit_status=str(system.audit_status),
                source_type=str(system.source_type),
                system_url=str(system.system_url or ""),
                action_count=action_count,
                resource_type_count=resource_type_count,
            )
        )

    @classmethod
    def list_actions(
        cls, *, username: str, namespace: str, request: ListSystemActionsRequest
    ) -> ListSystemActionsResponse:
        """列出指定系统已登记的操作，用于映射检索条件 action_id 的合法值。"""

        cls._ensure_system_accessible(username=username, namespace=namespace, system_id=request.system_id)
        queryset = Action.objects.filter(system_id=request.system_id)
        if request.keyword:
            queryset = queryset.filter(
                Q(action_id__icontains=request.keyword)
                | Q(name__icontains=request.keyword)
                | Q(name_en__icontains=request.keyword)
                | Q(description__icontains=request.keyword)
            )
        if request.resource_type_id:
            relation_exists = ResourceTypeActionRelation.objects.filter(
                system_id=request.system_id,
                resource_type_id=request.resource_type_id,
                action_id=OuterRef("action_id"),
            )
            queryset = queryset.filter(Exists(relation_exists))
        queryset = queryset.order_by("action_id")
        total = queryset.count()
        offset = (request.page - 1) * request.page_size
        rows = queryset[offset : offset + request.page_size]
        resource_map = Action.get_resource_type_id_map([request.system_id]).get(request.system_id, {})
        return ListSystemActionsResponse(
            actions=[
                SystemActionItem(
                    action_id=str(row.action_id or ""),
                    name=str(row.name or ""),
                    name_en=str(row.name_en or ""),
                    # 模型 blank+null 双开：空串归一为 None，与契约的 nullable 语义对齐
                    type=row.type or None,
                    sensitivity=int(row.sensitivity or 0),
                    description=str(row.description or ""),
                    resource_type_ids=list(resource_map.get(str(row.action_id), [])),
                )
                for row in rows
            ],
            total=total,
            page=request.page,
            page_size=request.page_size,
            has_more=offset + len(rows) < total,
        )

    @classmethod
    def list_resource_types(
        cls, *, username: str, namespace: str, request: ListSystemResourceTypesRequest
    ) -> ListSystemResourceTypesResponse:
        """列出指定系统已登记的资源类型，用于映射检索条件 resource_type 的合法值。"""

        cls._ensure_system_accessible(username=username, namespace=namespace, system_id=request.system_id)
        queryset = ResourceType.objects.filter(system_id=request.system_id)
        if request.keyword:
            queryset = queryset.filter(
                Q(resource_type_id__icontains=request.keyword)
                | Q(name__icontains=request.keyword)
                | Q(name_en__icontains=request.keyword)
                | Q(description__icontains=request.keyword)
            )
        queryset = queryset.order_by("resource_type_id")
        total = queryset.count()
        offset = (request.page - 1) * request.page_size
        rows = queryset[offset : offset + request.page_size]
        return ListSystemResourceTypesResponse(
            resource_types=[
                SystemResourceTypeItem(
                    resource_type_id=row.resource_type_id,
                    name=str(row.name or ""),
                    name_en=str(row.name_en or ""),
                    sensitivity=int(row.sensitivity or 0),
                    description=str(row.description or ""),
                    ancestor=list(row.ancestor or []),
                )
                for row in rows
            ],
            total=total,
            page=request.page,
            page_size=request.page_size,
            has_more=offset + len(rows) < total,
        )

    @classmethod
    def explore_system_fields(cls, *, username: str, namespace: str, system_id: str):
        """探索指定系统可检索字段的声明目录，复用日志工具的根目录构建。

        复用 ``mcp_get_log_field_metadata`` 的 ``LogFieldMetadataService``：
        鉴权（检索权限 + 命名空间归属）、敏感遮罩、字段声明与枚举选项
        全部同源。目录请求不采样，默认时间窗只用于满足检索条件协议；
        返回 ``GetLogFieldMetadataResponse``，错误映射沿用日志工具领域码。
        """

        from services.web.query.ai_assistant.log_tools.field_metadata import (
            LogFieldMetadataService,
        )
        from services.web.query.ai_assistant.log_tools.schemas import (
            AgentSearchCondition,
            GetLogFieldMetadataRequest,
        )

        now = timezone.now()
        condition = AgentSearchCondition(
            scope_type="system",
            scope_id=system_id,
            start_time=(now - timedelta(days=EXPLORE_FIELDS_LOOKBACK_DAYS)).isoformat(),
            end_time=now.isoformat(),
            conditions=[],
        )
        return LogFieldMetadataService.get_metadata(
            username=username,
            namespace=namespace,
            request=GetLogFieldMetadataRequest(condition=condition),
        )

    # ------------------------------------------------------------------
    # 单系统鉴权与归属校验
    # ------------------------------------------------------------------

    @classmethod
    def _ensure_system_accessible(cls, *, username: str, namespace: str, system_id: str) -> None:
        """单系统工具的统一入口校验：先鉴权（403），再校验归属（400）。"""

        if not SearchLogPermission.has_system_search_permission(system_id, username):
            SearchLogPermission.raise_system_view_permission_exception(username=username)
        if not System.objects.filter(system_id=system_id, namespace=namespace).exists():
            raise SystemNotAccessible()

    @classmethod
    def _get_accessible_system(cls, *, username: str, namespace: str, system_id: str) -> System:
        """鉴权并返回系统实例；系统不存在或不属于命名空间时抛领域错误。"""

        cls._ensure_system_accessible(username=username, namespace=namespace, system_id=system_id)
        try:
            return System.objects.get(system_id=system_id, namespace=namespace)
        except System.DoesNotExist as error:
            raise SystemNotAccessible() from error

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
from typing import List

from bk_resource import resource
from bk_resource.viewsets import ResourceRoute, ResourceViewSet

from apps.permission.handlers.actions import ActionEnum
from apps.permission.handlers.drf import (
    IAMPermission,
    InstanceActionPermission,
    insert_permission_field,
)
from apps.permission.handlers.resource_types import ResourceEnum
from core.view_sets import APIGWViewSet
from services.web.risk.permissions import (
    BatchRiskTicketPermission,
    RiskTicketPermission,
    RiskViewPermission,
)


class EventsViewSet(ResourceViewSet):
    """
    Event Endpoint
    """

    def get_permissions(self):
        if self.action in ["list"]:
            return [
                RiskViewPermission(
                    actions=[ActionEnum.LIST_RISK],
                    resource_meta=ResourceEnum.RISK,
                    get_instance_id=self.get_instance_id,
                )
            ]
        return []

    def get_instance_id(self) -> str:
        return self.request.query_params.get("risk_id", "--")

    resource_routes = [
        ResourceRoute("POST", resource.risk.create_event),
        ResourceRoute("GET", resource.risk.list_event),
    ]


class RisksAPIGWViewSet(ResourceViewSet):
    """
    Risks APIGW
    """

    def get_authenticators(self):
        return []

    def get_permissions(self):
        return []

    resource_routes = [
        ResourceRoute("GET", resource.risk.retrieve_risk_apigw, pk_field="risk_id"),
        ResourceRoute(
            "GET", resource.risk.retrieve_risk_strategy_info_apigw, pk_field="risk_id", endpoint="strategy_info"
        ),
        ResourceRoute("GET", resource.risk.get_risk_fields_by_strategy, endpoint="risk_fields_by_strategy"),
    ]


class RisksViewSet(ResourceViewSet):
    """
    Risks
    """

    def get_permissions(self):
        if self.action in [
            "risk_label",
            "close",
            "trans",
            "auto_process",
            "force_revoke_auto_process",
            "reopen",
            "retry_auto_process",
            "process_risk_ticket",
        ]:
            return [RiskTicketPermission()]
        if self.action in ["retrieve", "strategy_info"]:
            return [
                RiskViewPermission(actions=[ActionEnum.LIST_RISK], resource_meta=ResourceEnum.RISK, lookup_field="pk")
            ]
        if self.action in ["bulk_trans"]:
            return [BatchRiskTicketPermission(get_risk_ids=self.get_bulk_risk_ids)]
        # 风险编辑相关权限
        if self.action in ["update"]:
            return [InstanceActionPermission(actions=[ActionEnum.EDIT_RISK], resource_meta=ResourceEnum.RISK)]
        return []

    def get_bulk_risk_ids(self) -> List[str]:
        return self.request.data.get("risk_ids", [])

    resource_routes = [
        ResourceRoute("GET", resource.risk.retrieve_risk, pk_field="risk_id"),
        ResourceRoute("GET", resource.risk.retrieve_risk_strategy_info, pk_field="risk_id", endpoint="strategy_info"),
        ResourceRoute(
            "POST",
            resource.risk.list_risk,
            decorators=[
                insert_permission_field(
                    actions=[ActionEnum.EDIT_RISK, ActionEnum.PROCESS_RISK],
                    data_field=lambda data: data["results"],
                    id_field=lambda risk: risk["risk_id"],
                )
            ],
        ),
        ResourceRoute(
            "POST",
            resource.risk.list_mine_risk,
            endpoint="todo",
            decorators=[
                insert_permission_field(
                    actions=[ActionEnum.EDIT_RISK, ActionEnum.PROCESS_RISK],
                    data_field=lambda data: data["results"],
                    id_field=lambda risk: risk["risk_id"],
                )
            ],
        ),
        ResourceRoute(
            "POST",
            resource.risk.list_noticing_risk,
            endpoint="watch",
            decorators=[
                insert_permission_field(
                    actions=[ActionEnum.EDIT_RISK, ActionEnum.PROCESS_RISK],
                    data_field=lambda data: data["results"],
                    id_field=lambda risk: risk["risk_id"],
                )
            ],
        ),
        ResourceRoute("GET", resource.risk.list_risk_fields, endpoint="fields"),
        ResourceRoute("GET", resource.risk.list_event_fields_by_strategy, endpoint="event_fields"),
        ResourceRoute("PUT", resource.risk.update_risk_label, pk_field="risk_id", endpoint="risk_label"),
        ResourceRoute("GET", resource.risk.risk_status_common, endpoint="status_common"),
        ResourceRoute("GET", resource.risk.list_risk_tags, endpoint="tags"),
        ResourceRoute("GET", resource.risk.list_risk_strategy, endpoint="strategies"),
        ResourceRoute("POST", resource.risk.custom_close_risk, endpoint="close", pk_field="risk_id"),
        ResourceRoute("POST", resource.risk.custom_trans_risk, endpoint="trans", pk_field="risk_id"),
        ResourceRoute("POST", resource.risk.bulk_custom_trans_risk, endpoint="bulk_trans"),
        ResourceRoute("POST", resource.risk.custom_auto_process, endpoint="auto_process", pk_field="risk_id"),
        ResourceRoute(
            "POST", resource.risk.force_revoke_auto_process, endpoint="force_revoke_auto_process", pk_field="risk_id"
        ),
        ResourceRoute("POST", resource.risk.retry_auto_process, endpoint="retry_auto_process", pk_field="risk_id"),
        ResourceRoute("POST", resource.risk.reopen_risk, endpoint="reopen", pk_field="risk_id"),
        ResourceRoute("POST", resource.risk.process_risk_ticket, endpoint="process_risk_ticket", pk_field="risk_id"),
        ResourceRoute("POST", resource.risk.risk_export, endpoint="export"),
        # 风险编辑
        ResourceRoute("PUT", resource.risk.update_risk, pk_field="risk_id"),
        # 风险简要列表（用于策略配置时选择风险单进行预览）
        ResourceRoute("GET", resource.risk.list_risk_brief, endpoint="brief", enable_paginate=True),
    ]


class RiskReportViewSet(ResourceViewSet):
    """
    风险报告管理

    提供风险报告的创建、编辑、生成等功能。
    路由前缀：/api/v1/risk_report/{risk_id}/
    """

    def get_permissions(self):
        # 所有报告相关操作都需要风险编辑权限
        return [InstanceActionPermission(actions=[ActionEnum.EDIT_RISK], resource_meta=ResourceEnum.RISK)]

    resource_routes = [
        # POST /api/v1/risk_report/{risk_id}/save/ -> 创建报告
        ResourceRoute("POST", resource.risk.create_risk_report, pk_field="risk_id", endpoint="save"),
        # PUT /api/v1/risk_report/{risk_id}/ -> 编辑报告
        ResourceRoute("PUT", resource.risk.update_risk_report, pk_field="risk_id"),
        # POST /api/v1/risk_report/{risk_id}/generate/ -> 生成报告
        ResourceRoute("POST", resource.risk.generate_risk_report, pk_field="risk_id", endpoint="generate"),
        # POST /api/v1/risk_report/{risk_id}/ai_preview/ -> AI 智能体预览
        ResourceRoute("POST", resource.risk.ai_preview, pk_field="risk_id", endpoint="ai_preview"),
        # GET /api/v1/risk_report/{risk_id}/task/ -> 查询任务结果
        ResourceRoute("GET", resource.risk.get_task_result, endpoint="task"),
    ]


class RiskExperiencesViewSet(ResourceViewSet):
    def get_permissions(self):
        if self.action in ["retrieve"]:
            return [
                RiskViewPermission(actions=[ActionEnum.LIST_RISK], resource_meta=ResourceEnum.RISK, lookup_field="pk")
            ]
        if self.action in ["create"]:
            return [RiskTicketPermission()]
        return []

    resource_routes = [
        ResourceRoute("GET", resource.risk.list_risk_experience, pk_field="risk_id"),
        ResourceRoute("POST", resource.risk.save_risk_experience),
    ]


class ProcessApplicationsViewSet(ResourceViewSet):
    def get_permissions(self):
        if self.action in ["list"]:
            return [IAMPermission(actions=[ActionEnum.LIST_PA])]
        if self.action in ["update", "toggle"]:
            return [IAMPermission(actions=[ActionEnum.EDIT_PA])]
        if self.action in ["create"]:
            return [IAMPermission(actions=[ActionEnum.CREATE_PA])]
        if self.action in ["rules"]:
            return [IAMPermission(actions=[ActionEnum.LIST_RULE])]
        return []

    resource_routes = [
        ResourceRoute("GET", resource.risk.list_process_applications, enable_paginate=True),
        ResourceRoute("GET", resource.risk.list_all_process_applications, endpoint="all"),
        ResourceRoute("POST", resource.risk.create_process_application),
        ResourceRoute("PUT", resource.risk.update_process_application, pk_field="id"),
        ResourceRoute("GET", resource.risk.list_rule_by_pa, pk_field="id", endpoint="rules", enable_paginate=True),
        ResourceRoute("PUT", resource.risk.toggle_process_application, pk_field="id", endpoint="toggle"),
        ResourceRoute("GET", resource.risk.approve_build_in_fields, endpoint="approve_build_in_fields"),
    ]


class RiskRulesViewSet(ResourceViewSet):
    def get_permissions(self):
        if self.action in ["list", "risks"]:
            return [IAMPermission(actions=[ActionEnum.LIST_RULE])]
        if self.action in ["create"]:
            return [IAMPermission(actions=[ActionEnum.CREATE_RULE])]
        if self.action in ["update", "toggle", "set_priority_index"]:
            return [IAMPermission(actions=[ActionEnum.EDIT_RULE])]
        if self.action in ["destroy"]:
            return [IAMPermission(actions=[ActionEnum.DELETE_RULE])]
        return []

    resource_routes = [
        ResourceRoute("GET", resource.risk.list_risk_rule, enable_paginate=True),
        ResourceRoute("GET", resource.risk.list_all_risk_rule, endpoint="all"),
        ResourceRoute("POST", resource.risk.create_risk_rule),
        ResourceRoute("PUT", resource.risk.update_risk_rule, pk_field="rule_id"),
        ResourceRoute("DELETE", resource.risk.delete_risk_rule, pk_field="rule_id"),
        ResourceRoute(
            "GET", resource.risk.list_risk_by_rule, pk_field="rule_id", endpoint="risks", enable_paginate=True
        ),
        ResourceRoute("PUT", resource.risk.toggle_risk_rule, pk_field="rule_id", endpoint="toggle"),
        ResourceRoute("GET", resource.risk.list_risk_rule_operator, endpoint="operators"),
        ResourceRoute("PUT", resource.risk.batch_update_risk_rule_priority_index, endpoint="set_priority_index"),
        ResourceRoute("GET", resource.risk.list_event_fields_by_strategy, endpoint="event_fields"),
    ]


class RiskEventSubscriptionApigwViewSet(APIGWViewSet):
    resource_routes = [
        ResourceRoute("POST", resource.risk.query_risk_event_subscription, endpoint="subscription"),
    ]


class RiskEventSubscriptionAdminViewSet(ResourceViewSet):
    resource_routes = [
        ResourceRoute("POST", resource.risk.query_risk_event_subscription, endpoint="preview"),
    ]

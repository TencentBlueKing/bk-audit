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

from bk_resource import api
from django.utils.translation import gettext_lazy

from apps.audit.resources import AuditMixinResource
from apps.itsm.constants import TicketStatus
from apps.itsm.serializers import GetServicesRespSerializer
from core.utils.data import choices_to_dict


class ITSMMeta(AuditMixinResource, abc.ABC):
    tags = ["ITSM"]


class GetServices(ITSMMeta):
    name = gettext_lazy("获取服务列表")
    ResponseSerializer = GetServicesRespSerializer
    many_response_data = True

    def perform_request(self, validated_request_data):
        # 使用 ITSM V4 的系统流程列表接口代替原 get_services 接口
        resp = api.bk_itsm_v4.system_workflow_list()
        services = [{"id": s["key"], "name": s["name"], "url": s.get("frontend_url")} for s in resp["results"]]
        services.sort(key=lambda s: s["name"])
        return services


class GetServiceDetail(ITSMMeta):
    name = gettext_lazy("获取服务详情")

    def perform_request(self, validated_request_data):
        # 使用 ITSM V4 的获取流程启用版本详情接口代替原 get_service_detail 接口
        # Workflows 接口返回 data.items（流程详情数组），此处按单个流程标识取首个详情
        resp = api.bk_itsm_v4.workflows(workflow_keys=validated_request_data["id"])
        items = resp.get("items") or []
        return items[0] if items else {}


class GetTicketStatusCommon(ITSMMeta):
    name = gettext_lazy("获取单据状态常量")

    def perform_request(self, validated_request_data):
        return choices_to_dict(TicketStatus)

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
from blueapps.utils.logger import logger
from django.utils.translation import gettext_lazy

from apps.audit.resources import AuditMixinResource
from apps.itsm.constants import TicketStatus
from apps.itsm.serializers import (
    GetServiceDetailReqSerializer,
    GetServicesReqsSerializer,
    GetServicesRespSerializer,
)
from apps.itsm.utils import adapt_v4_workflow_to_service_detail
from core.utils.data import choices_to_dict


class ITSMMeta(AuditMixinResource, abc.ABC):
    tags = ["ITSM"]


class GetServices(ITSMMeta):
    name = gettext_lazy("获取服务列表")
    ResponseSerializer = GetServicesRespSerializer
    RequestSerializer = GetServicesReqsSerializer
    many_response_data = True

    def perform_request(self, validated_request_data):
        # 使用 ITSM V4 的系统流程列表接口代替原 get_services 接口
        system_id = validated_request_data.get("system_id")
        services, page = [], 1
        while True:
            resp = api.bk_itsm_v4.system_workflow_list(system_id=system_id, page=page, page_size=100)
            services.extend({"id": s["key"], "name": s["name"], "url": s.get("frontend_url")} for s in resp["results"])
            if len(services) >= resp["count"]:
                break
            page += 1
        return services


class GetServiceDetail(ITSMMeta):
    name = gettext_lazy("获取服务详情")
    RequestSerializer = GetServiceDetailReqSerializer

    def perform_request(self, validated_request_data):
        # 使用 ITSM V4 的获取流程启用版本详情接口代替原 get_service_detail 接口
        # Workflows 接口返回 items（流程详情数组），此处按单个流程标识取首个详情
        workflow_key = validated_request_data["id"]
        resp = api.bk_itsm_v4.workflows(workflow_keys=workflow_key)
        items = resp.get("items") or []
        if not items:
            return {}
        # V4 的 workflow dict 与 V3 的 service detail 结构不同（字段在
        # form_canvas_data 里且 key 带 ticket__ 前缀），此处适配成 V3 结构，
        # 保证前端审批字段配置与 ProcessApplication.approve_config 无需改动
        return adapt_v4_workflow_to_service_detail(
            items[0],
            name=self.load_workflow_name(workflow_key, validated_request_data.get("system_id")),
        )

    @staticmethod
    def load_workflow_name(workflow_key: str, system_id: str = "") -> str:
        """
        V4 的 workflows 响应不含流程名称，需从系统流程列表带回。
        列表接口依赖 system_id 与 SYSTEM-TOKEN，取不到时降级为流程标识。
        """

        if not system_id:
            return ""
        try:
            resp = api.bk_itsm_v4.system_workflow_list(system_id=system_id, key__in=workflow_key)
            for item in resp.get("results") or []:
                if item.get("key") == workflow_key:
                    return item.get("name") or ""
        except Exception as err:  # NOCC:broad-except(名称缺失可降级为流程标识)
            logger.warning("[GetServiceDetail] load workflow name failed: %s, %s", workflow_key, err)
        return ""


class GetTicketStatusCommon(ITSMMeta):
    name = gettext_lazy("获取单据状态常量")

    def perform_request(self, validated_request_data):
        return choices_to_dict(TicketStatus)

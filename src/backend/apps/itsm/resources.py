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
from django.conf import settings
from django.utils.translation import gettext, gettext_lazy

from apps.audit.resources import AuditMixinResource
from apps.exceptions import MetaConfigNotExistException
from apps.itsm.constants import (
    ITSM_SERVICE_CATALOG_ID_KEY,
    ITSM_SERVICE_PROJECT_ID_KEY,
    TicketStatus,
)
from apps.itsm.serializers import (
    GetServiceDetailReqSerializer,
    GetServicesReqsSerializer,
    GetServicesRespSerializer,
    default_itsm_version,
)
from apps.itsm.utils import adapt_v4_workflow_to_service_detail, get_itsm_v4_system_id
from apps.meta.models import GlobalMetaConfig
from apps.meta.utils.saas import get_saas_url
from core.utils.data import choices_to_dict
from services.web.risk.constants import ItsmVersion


class ITSMMeta(AuditMixinResource, abc.ABC):
    tags = ["ITSM"]


class GetServices(ITSMMeta):
    name = gettext_lazy("获取服务列表")
    ResponseSerializer = GetServicesRespSerializer
    RequestSerializer = GetServicesReqsSerializer
    many_response_data = True

    # ITSM V4 系统流程列表分页大小
    PAGE_SIZE = 100

    def perform_request(self, validated_request_data):
        # 根据不同的 itsm 版本 使用不同的 itsm 接口（未显式传 version 时按部署级开关）
        version = validated_request_data.get("version") or default_itsm_version()
        if version == ItsmVersion.V3:
            services = self._fetch_v3_services()
        else:
            services = self._fetch_v4_services(validated_request_data.get("system_id"))
        services.sort(key=lambda s: s["name"])
        return services

    def _fetch_v3_services(self) -> list:
        raw_services = api.bk_itsm.get_services(catalog_id=GlobalMetaConfig.get(ITSM_SERVICE_CATALOG_ID_KEY))
        return [{"id": s["id"], "name": s["name"], "url": self.build_itsm_service_url(s["id"])} for s in raw_services]

    def _fetch_v4_services(self, system_id=None) -> list:
        system_id = system_id or get_itsm_v4_system_id()
        if not system_id:
            raise MetaConfigNotExistException(message=gettext("未配置 ITSM V4 系统标识"))

        services, page = [], 1
        while True:
            resp = api.bk_itsm_v4.system_workflow_list(
                system_id=system_id, is_enable=True, page=page, page_size=self.PAGE_SIZE
            )
            results = resp.get("results") or []
            if not results:
                break
            services.extend({"id": s["key"], "name": s["name"], "url": s.get("frontend_url")} for s in results)
            # 末页（返回数量不足一页）即停止，避免依赖 total count 缺失/不准导致漏翻或死循环
            if len(results) < self.PAGE_SIZE:
                break
            page += 1
        return services

    def build_itsm_service_url(self, id: int) -> str:
        project_id = GlobalMetaConfig.get(ITSM_SERVICE_PROJECT_ID_KEY)
        catalog_id = GlobalMetaConfig.get(ITSM_SERVICE_CATALOG_ID_KEY)
        return "{}/#/project/service/edit/basic?serviceId={}&project_id={}&catalog_id={}".format(
            get_saas_url(settings.BK_ITSM_APP_CODE),
            id,
            project_id,
            catalog_id,
        )


class GetServiceDetail(ITSMMeta):
    name = gettext_lazy("获取服务详情")
    RequestSerializer = GetServiceDetailReqSerializer

    def perform_request(self, validated_request_data):
        # 未显式传 version 时按部署级开关，与新建单据读取同一配置
        version = validated_request_data.get("version") or default_itsm_version()
        if version == ItsmVersion.V3:
            return self._get_v3_service_detail(validated_request_data["id"])
        return self._get_v4_service_detail(validated_request_data["id"])

    def _get_v3_service_detail(self, service_id: str) -> dict:
        return api.bk_itsm.get_service_detail(service_id=int(service_id))

    def _get_v4_service_detail(self, workflow_key: str) -> dict:
        # ITSM V4 中，获取流程启用版本详情接口代替原 get_service_detail 接口
        # Workflows 接口返回 items（流程详情数组），此处按单个流程标识取首个详情
        resp = api.bk_itsm_v4.workflows(workflow_keys=workflow_key)
        items = resp.get("items") or []
        if not items:
            return {}
        # V4 的 workflow dict 与 V3 的 service detail 结构不同，此处适配成 V3 结构
        return adapt_v4_workflow_to_service_detail(items[0], name=self.load_workflow_name(workflow_key))

    @staticmethod
    def load_workflow_name(workflow_key: str) -> str:
        """
        V4 的 workflows 响应不含流程名称，需从系统流程列表带回。

        system_id 与 GetServices 保持一致，由后端配置注入（前端不传）；
        SYSTEM-TOKEN 由 BKITSMV4.build_header 注入。取不到时降级为流程标识。
        """

        system_id = get_itsm_v4_system_id()
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

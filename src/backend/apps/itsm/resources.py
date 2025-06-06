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
from django.conf import settings
from django.utils.translation import gettext_lazy

from apps.audit.resources import AuditMixinResource
from apps.itsm.constants import (
    ITSM_SERVICE_CATALOG_ID_KEY,
    ITSM_SERVICE_PROJECT_ID_KEY,
    TicketStatus,
)
from apps.itsm.serializers import GetServicesRespSerializer
from apps.meta.models import GlobalMetaConfig
from apps.meta.utils.saas import get_saas_url
from core.utils.data import choices_to_dict


class ITSMMeta(AuditMixinResource, abc.ABC):
    tags = ["ITSM"]


class GetServices(ITSMMeta):
    name = gettext_lazy("获取服务列表")
    ResponseSerializer = GetServicesRespSerializer
    many_response_data = True

    def perform_request(self, validated_request_data):
        services = [
            {"id": s["id"], "name": s["name"], "url": self.build_itsm_service_url(s["id"])}
            for s in api.bk_itsm.get_services(catalog_id=GlobalMetaConfig.get(ITSM_SERVICE_CATALOG_ID_KEY))
        ]
        services.sort(key=lambda s: s["name"])
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

    def perform_request(self, validated_request_data):
        return api.bk_itsm.get_service_detail(service_id=validated_request_data["id"])


class GetTicketStatusCommon(ITSMMeta):
    name = gettext_lazy("获取单据状态常量")

    def perform_request(self, validated_request_data):
        return choices_to_dict(TicketStatus)

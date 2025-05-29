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
from apps.meta.utils.saas import get_saas_url
from apps.sops.constants import SOPSTaskStatus
from apps.sops.serializers import GetTemplatesRespSerializer
from core.utils.data import choices_to_dict


class SopsMeta(AuditMixinResource, abc.ABC):
    tags = ["SOps"]


class ListTemplates(SopsMeta):
    name = gettext_lazy("获取执行模板列表")
    ResponseSerializer = GetTemplatesRespSerializer
    many_response_data = True

    def perform_request(self, validated_request_data):
        templates = [
            {"id": t["id"], "name": t["name"], "url": self.build_sops_url(t["id"], t["project_id"])}
            for t in api.bk_sops.get_template_list(bk_biz_id=settings.DEFAULT_BK_BIZ_ID)
        ]
        templates.sort(key=lambda t: t["name"])
        return templates

    def build_sops_url(self, template_id: int, project_id: int) -> str:
        return f"{get_saas_url(settings.BK_SOPS_APP_CODE)}/template/view/{project_id}/?template_id={template_id}"


class RetrieveTemplate(SopsMeta):
    name = gettext_lazy("获取执行模板详情")

    def perform_request(self, validated_request_data):
        return api.bk_sops.get_template_info(
            bk_biz_id=settings.DEFAULT_BK_BIZ_ID, template_id=validated_request_data["id"]
        )


class GetWorkflowStatusCommon(SopsMeta):
    name = gettext_lazy("获取任务状态常量")

    def perform_request(self, validated_request_data):
        return choices_to_dict(SOPSTaskStatus)

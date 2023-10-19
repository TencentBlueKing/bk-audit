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

from bk_resource import Resource
from blueapps.utils.request_provider import get_request_username
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy

from services.web.risk.models import Risk, RiskExperience
from services.web.risk.serializers import (
    ListRiskExperienceReqSerializer,
    RiskExperienceInfoSerializer,
    SaveRiskExperienceReqSerializer,
)


class RiskExperienceMeta(Resource, abc.ABC):
    tags = ["RiskExperience"]


class SaveRiskExperience(RiskExperienceMeta):
    name = gettext_lazy("保存风险处理经验")
    RequestSerializer = SaveRiskExperienceReqSerializer
    ResponseSerializer = RiskExperienceInfoSerializer

    def perform_request(self, validated_request_data):
        risk = get_object_or_404(Risk, risk_id=validated_request_data["risk_id"])
        risk_experience: RiskExperience = RiskExperience.objects.filter(
            risk_id=risk.risk_id, created_by=get_request_username()
        ).first()
        if not risk_experience:
            return RiskExperience.objects.create(risk_id=risk.risk_id, content=validated_request_data["content"])
        risk_experience.content = validated_request_data["content"]
        risk_experience.save(update_fields=["content"])
        return risk_experience


class ListRiskExperience(RiskExperienceMeta):
    name = gettext_lazy("获取风险处理经验")
    RequestSerializer = ListRiskExperienceReqSerializer
    ResponseSerializer = RiskExperienceInfoSerializer
    many_response_data = True

    def perform_request(self, validated_request_data):
        risk = get_object_or_404(Risk, risk_id=validated_request_data["risk_id"])
        return RiskExperience.objects.filter(risk_id=risk.risk_id)

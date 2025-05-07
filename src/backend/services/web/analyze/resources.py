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

from abc import ABC
from collections import defaultdict

from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy

from apps.audit.resources import AuditMixinResource
from core.utils.data import choices_to_select_list
from services.web.analyze.constants import ControlTypeChoices
from services.web.analyze.models import Control, ControlVersion
from services.web.analyze.serializers import (
    ControlResourceRequestSerializer,
    ControlResourceResponseSerializer,
    ControlTypeResponseSerializer,
    ControlVersionDetailRequestSerializer,
    ControlVersionDetailResponseSerializer,
)


class ControlBaseResource(AuditMixinResource, ABC):
    tags = ["Control"]


class ControlType(ControlBaseResource):
    name = gettext_lazy("Analyze Ability")
    ResponseSerializer = ControlTypeResponseSerializer
    many_response_data = True

    def perform_request(self, validated_request_data):
        return choices_to_select_list(ControlTypeChoices)


class ControlResource(ControlBaseResource):
    name = gettext_lazy("Control")
    RequestSerializer = ControlResourceRequestSerializer
    ResponseSerializer = ControlResourceResponseSerializer
    many_response_data = True

    def perform_request(self, validated_request_data):
        # load controls
        controls = Control.objects.filter(**validated_request_data).order_by("-priority_index", "control_name")
        # load control versions
        # only display the newest version
        control_versions = ControlVersion.objects.filter(control_id__in=controls.values("control_id")).order_by(
            "control_id", "-control_version"
        )
        control_version_map = defaultdict(list)
        for cv in control_versions:
            # 返回所有版本
            # if cv.control_id in control_version_map.keys():
            #     continue
            control_version_map[cv.control_id].append(cv)
        # bind control version
        for control in controls:
            setattr(control, "versions", control_version_map.get(control.control_id, []))
        # resp
        return controls


class ControlVersionDetail(ControlBaseResource):
    name = gettext_lazy("Control Version Detail")
    RequestSerializer = ControlVersionDetailRequestSerializer
    ResponseSerializer = ControlVersionDetailResponseSerializer

    def perform_request(self, validated_request_data):
        # specify version
        if validated_request_data.get("control_version"):
            control_version = get_object_or_404(ControlVersion, **validated_request_data)
        # default of latest version
        else:
            control_version = (
                ControlVersion.objects.filter(control_id=validated_request_data["control_id"])
                .order_by("-control_version")
                .first()
            )
            if control_version is None:
                raise Http404()
        return control_version

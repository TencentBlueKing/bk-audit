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

from django.db import transaction
from django.db.models import Q
from django.utils.translation import gettext_lazy
from rest_framework.generics import get_object_or_404

from apps.audit.resources import AuditMixinResource
from core.exceptions import ValidationError
from core.models import UUIDField, get_request_username
from services.web.vision.models import (
    ReportGroup,
    ReportUserPreference,
    Scenario,
    VisionPanel,
)
from services.web.vision.serializers import (
    CreatePanelRequestSerializer,
    ListManagePanelsRequestSerializer,
    ManagePanelSerializer,
    PanelPreferenceResponseSerializer,
    UpdateGroupOrderRequestSerializer,
    UpdatePanelOrderRequestSerializer,
    UpdatePanelPreferenceRequestSerializer,
    UpdatePanelRequestSerializer,
)


class PanelManage(AuditMixinResource, abc.ABC):
    tags = ["PanelManage"]


class ListManagePanels(PanelManage):
    name = gettext_lazy("管理端 Panel 列表")
    RequestSerializer = ListManagePanelsRequestSerializer
    ResponseSerializer = ManagePanelSerializer
    many_response_data = True

    def perform_request(self, validated_request_data):
        panels = VisionPanel.objects.filter(scenario=Scenario.DEFAULT).select_related("group")

        keyword = validated_request_data.get("keyword", "")
        is_enabled = validated_request_data.get("is_enabled")

        if keyword:
            panels = panels.filter(
                Q(id__icontains=keyword)
                | Q(name__icontains=keyword)
                | Q(description__icontains=keyword)
                | Q(vision_id__icontains=keyword)
                | Q(updated_by__icontains=keyword)
            )

        if is_enabled is not None:
            panels = panels.filter(is_enabled=is_enabled)

        return panels.order_by("-group__priority_index", "group__name", "-priority_index", "name")


class CreatePanel(PanelManage):
    name = gettext_lazy("创建 Panel")
    RequestSerializer = CreatePanelRequestSerializer
    ResponseSerializer = ManagePanelSerializer

    @transaction.atomic
    def perform_request(self, validated_request_data):
        group = ReportGroup.get_or_create_by_name(validated_request_data["group_name"])
        panel = VisionPanel.objects.create(
            id=UUIDField.get_default_value(),
            vision_id=validated_request_data["vision_id"],
            name=validated_request_data["name"],
            description=validated_request_data.get("description", ""),
            group=group,
            is_enabled=validated_request_data.get("is_enabled", True),
            scenario=Scenario.DEFAULT,
        )
        return panel


class UpdatePanel(PanelManage):
    name = gettext_lazy("更新 Panel")
    RequestSerializer = UpdatePanelRequestSerializer
    ResponseSerializer = ManagePanelSerializer

    @transaction.atomic
    def perform_request(self, validated_request_data):
        panel = get_object_or_404(VisionPanel, id=validated_request_data.pop("id"))
        old_group_id = panel.group_id

        if "group_name" in validated_request_data:
            panel.group = ReportGroup.get_or_create_by_name(validated_request_data.pop("group_name"))

        for key, val in validated_request_data.items():
            setattr(panel, key, val)
        panel.save(update_fields=[*validated_request_data.keys(), "group_id"])

        if old_group_id and old_group_id != panel.group_id:
            ReportGroup.cleanup_empty()

        return panel


class DeletePanel(PanelManage):
    name = gettext_lazy("删除 Panel")

    @transaction.atomic
    def perform_request(self, validated_request_data):
        panel = get_object_or_404(VisionPanel, id=validated_request_data["id"])
        panel.delete()
        ReportGroup.cleanup_empty()
        return {}


class UpdatePanelOrder(PanelManage):
    """批量更新 Panel 的分组归属和排序权重。

    前端拖拽排序或跨分组移动后，全量传入当前分组内所有 Panel 的新排序：
    panels: [{"id": "<panel_id>", "group_id": <目标分组ID>, "priority_index": <新排序>}, ...]
    priority_index 按显示顺序从大到小赋值；移动后原分组若为空则自动清理。
    仅更新排序字段，不触发 updated_at/updated_by 变更。
    """

    name = gettext_lazy("更新 Panel 排序")
    RequestSerializer = UpdatePanelOrderRequestSerializer

    @transaction.atomic
    def perform_request(self, validated_request_data):
        order_list = validated_request_data["panels"]
        panel_ids = [item["id"] for item in order_list]
        panels = {p.id: p for p in VisionPanel.objects.filter(id__in=panel_ids)}

        missing = set(panel_ids) - set(panels.keys())
        if missing:
            raise ValidationError(message=f"Panel not found: {', '.join(missing)}")

        to_update = []
        for item in order_list:
            panel = panels[item["id"]]
            panel.group_id = item["group_id"]
            panel.priority_index = item["priority_index"]
            to_update.append(panel)

        VisionPanel.objects.bulk_update(to_update, update_record=False, fields=["group_id", "priority_index"])
        ReportGroup.cleanup_empty()
        return {}


class UpdateGroupOrder(PanelManage):
    name = gettext_lazy("更新分组排序")
    RequestSerializer = UpdateGroupOrderRequestSerializer

    @transaction.atomic
    def perform_request(self, validated_request_data):
        order_list = validated_request_data["groups"]
        group_ids = [item["id"] for item in order_list]
        groups = {g.id: g for g in ReportGroup.objects.filter(id__in=group_ids)}

        missing = set(group_ids) - set(groups.keys())
        if missing:
            raise ValidationError(message=f"Group not found: {', '.join(str(i) for i in missing)}")

        to_update = []
        for item in order_list:
            group = groups[item["id"]]
            group.priority_index = item["priority_index"]
            to_update.append(group)

        ReportGroup.objects.bulk_update(to_update, update_record=False, fields=["priority_index"])
        return {}


class GetPanelPreference(PanelManage):
    name = gettext_lazy("获取 Panel 用户偏好")
    ResponseSerializer = PanelPreferenceResponseSerializer

    def perform_request(self, validated_request_data):
        username = get_request_username()
        pref, _ = ReportUserPreference.objects.get_or_create(username=username)
        return pref


class UpdatePanelPreference(PanelManage):
    name = gettext_lazy("更新 Panel 用户偏好")
    RequestSerializer = UpdatePanelPreferenceRequestSerializer
    ResponseSerializer = PanelPreferenceResponseSerializer

    def perform_request(self, validated_request_data):
        username = get_request_username()
        pref, _ = ReportUserPreference.objects.update_or_create(
            username=username,
            defaults={"config": validated_request_data["config"]},
        )
        return pref

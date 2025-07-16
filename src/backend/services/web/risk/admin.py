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

from django.contrib import admin

from services.web.risk.models import (
    ProcessApplication,
    Risk,
    RiskExperience,
    RiskRule,
    TicketNode,
    TicketPermission,
)


@admin.register(Risk)
class RiskAdmin(admin.ModelAdmin):
    list_display = [
        "risk_id",
        "title",
        "event_content_short",
        "operator",
        "event_time",
        "status",
        "current_operator",
        "notice_users",
        "risk_label",
        "display_tags",
    ]
    search_fields = ["risk_id", "title", "tag_objs__tag_name"]
    list_filter = ["status", "risk_label", "tag_objs__tag_name"]
    list_prefetch_related = ["tag_objs"]

    def get_queryset(self, request):
        qs = Risk.annotated_queryset()
        ordering = self.get_ordering(request)
        if ordering:
            qs = qs.order_by(*ordering)
        if self.list_prefetch_related:
            qs = qs.prefetch_related(*self.list_prefetch_related)
        return qs

    def event_content_short(self, obj: Risk):
        return getattr(obj, "event_content_short", "")

    event_content_short.short_description = "Event Content Short"

    def display_tags(self, obj: Risk):
        return ", ".join([t.tag_name for t in obj.tag_objs.all()])

    display_tags.short_description = "Tags"


@admin.register(ProcessApplication)
class ProcessApplicationAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "need_approve", "is_deleted"]
    search_fields = ["id", "name"]
    list_filter = ["is_deleted"]


@admin.register(RiskRule)
class RiskRuleAdmin(admin.ModelAdmin):
    list_display = ["id", "rule_id", "version", "name", "auto_close_risk", "priority_index", "is_enabled", "is_deleted"]
    search_fields = ["rule_id", "name"]
    list_filter = ["auto_close_risk", "is_enabled", "is_deleted"]


@admin.register(RiskExperience)
class RiskExperienceAdmin(admin.ModelAdmin):
    list_display = ["risk_id", "content", "created_by", "created_at", "is_deleted"]
    search_fields = ["risk_id", "created_by"]
    list_filter = ["is_deleted"]


@admin.register(TicketNode)
class TicketNodeAdmin(admin.ModelAdmin):
    list_display = ["id", "risk_id", "action", "operator", "current_operator", "time", "status"]
    list_filter = ["action", "status"]
    search_fields = ["risk_id"]


@admin.register(TicketPermission)
class TicketPermissionAdmin(admin.ModelAdmin):
    list_display = ["id", "risk_id", "action", "user"]
    search_fields = ["risk_id", "user"]
    list_filter = ["action"]

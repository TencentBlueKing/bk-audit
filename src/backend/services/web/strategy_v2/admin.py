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

from django.contrib import admin
from django.utils.translation import gettext_lazy

from apps.meta.models import Tag
from core.utils.data import choices_to_items
from services.web.analyze.constants import ControlTypeChoices
from services.web.analyze.models import Control
from services.web.strategy_v2.models import (
    DispatchRule,
    LinkTable,
    LinkTableTag,
    Strategy,
    StrategyRule,
    StrategyTag,
    StrategyTagSyncTrash,
)


@admin.register(Strategy)
class StrategyAdmin(admin.ModelAdmin):
    list_display = [
        "strategy_id",
        "strategy_name",
        "namespace",
        "control_type_name",
        "control_id",
        "control_version",
        "source",
        "status",
        "is_formal",
        "tags",
        "is_deleted",
    ]
    list_filter = ["namespace", "is_deleted", "strategy_type", "is_formal", "source"]
    search_fields = ["strategy_id", "strategy_name"]
    ordering = ["-strategy_id"]

    @admin.display(description=gettext_lazy("Control Type Name"))
    def control_type_name(self, inst: Strategy) -> str:
        control_type_id = Control.objects.get(control_id=inst.control_id).control_type_id
        return choices_to_items(ControlTypeChoices).get(control_type_id, control_type_id)

    @admin.display(description=gettext_lazy("Tags"))
    def tags(self, inst: Strategy) -> List[str]:
        tag_ids = StrategyTag.objects.filter(strategy_id=inst.strategy_id).values("tag_id")
        tags = Tag.objects.filter(tag_id__in=tag_ids)
        return [t.tag_name for t in tags]


@admin.register(LinkTable)
class LinkTableAdmin(admin.ModelAdmin):
    list_display = (
        "uid",
        "name",
        "namespace",
        "version",
        "created_at",
        "updated_at",
    )
    list_filter = ("namespace",)
    search_fields = ("name", "uid")


@admin.register(LinkTableTag)
class LinkTableTagAdmin(admin.ModelAdmin):
    list_display = ("id", "link_table_uid", "tag_id", "created_at", "updated_at")
    list_filter = ("created_at",)
    search_fields = ("link_table_uid", "tag_id")


@admin.register(StrategyTagSyncTrash)
class StrategyTagSyncTrashAdmin(admin.ModelAdmin):
    list_display = ("id", "original_id", "strategy_id", "tag_id", "created_at", "updated_at")
    list_filter = ("created_at", "updated_at")
    search_fields = ("original_id", "strategy_id", "tag_id")


@admin.register(StrategyRule)
class StrategyRuleAdmin(admin.ModelAdmin):
    # JSONField 截断展示的最大长度
    JSON_DISPLAY_MAX_LENGTH = 100

    list_display = (
        "rule_id",
        "rule_name",
        "strategy_link",
        "risk_level",
        "conditions_short",
        "risk_title_short",
        "processor_short",
        "follower_short",
        "is_deleted",
        "created_at",
        "updated_at",
    )
    list_filter = ("risk_level", "is_deleted")
    search_fields = ("rule_id", "rule_name", "strategy__strategy_name", "strategy__strategy_id")
    ordering = ("-rule_id",)

    @admin.display(description=gettext_lazy("Strategy"))
    def strategy_link(self, inst: StrategyRule) -> str:
        return f"[{inst.strategy_id}] {inst.strategy.strategy_name}"

    def _truncate_json(self, value, max_length: int = None) -> str:
        if not value:
            return "-"
        text = str(value)
        max_len = max_length or self.JSON_DISPLAY_MAX_LENGTH
        return text[:max_len] + "..." if len(text) > max_len else text

    @admin.display(description=gettext_lazy("Conditions"))
    def conditions_short(self, inst: StrategyRule) -> str:
        return self._truncate_json(inst.conditions)

    @admin.display(description=gettext_lazy("Risk Title"))
    def risk_title_short(self, inst: StrategyRule) -> str:
        return self._truncate_text(inst.risk_title)

    @admin.display(description=gettext_lazy("Processor"))
    def processor_short(self, inst: StrategyRule) -> str:
        return self._truncate_json(inst.processor)

    @admin.display(description=gettext_lazy("Follower"))
    def follower_short(self, inst: StrategyRule) -> str:
        return self._truncate_json(inst.follower)

    def _truncate_text(self, value: str, max_length: int = None) -> str:
        if not value:
            return "-"
        max_len = max_length or self.JSON_DISPLAY_MAX_LENGTH
        return value[:max_len] + "..." if len(value) > max_len else value

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("strategy")


@admin.register(DispatchRule)
class DispatchRuleAdmin(admin.ModelAdmin):
    # JSONField 截断展示的最大长度
    JSON_DISPLAY_MAX_LENGTH = 100

    list_display = (
        "rule_id",
        "rule_name",
        "strategy_link",
        "target_scene",
        "conditions_short",
        "processor_short",
        "follower_short",
        "confirmer_short",
        "dispatch_mode",
        "is_default",
        "is_deleted",
        "created_at",
        "updated_at",
    )
    list_filter = ("dispatch_mode", "is_default", "is_deleted")
    search_fields = ("rule_id", "rule_name", "strategy__strategy_name", "strategy__strategy_id")
    ordering = ("-rule_id",)

    @admin.display(description=gettext_lazy("Strategy"))
    def strategy_link(self, inst: DispatchRule) -> str:
        return f"[{inst.strategy_id}] {inst.strategy.strategy_name}"

    def _truncate_json(self, value, max_length: int = None) -> str:
        if not value:
            return "-"
        text = str(value)
        max_len = max_length or self.JSON_DISPLAY_MAX_LENGTH
        return text[:max_len] + "..." if len(text) > max_len else text

    @admin.display(description=gettext_lazy("Conditions"))
    def conditions_short(self, inst: DispatchRule) -> str:
        return self._truncate_json(inst.conditions)

    @admin.display(description=gettext_lazy("Processor"))
    def processor_short(self, inst: DispatchRule) -> str:
        return self._truncate_json(inst.processor)

    @admin.display(description=gettext_lazy("Follower"))
    def follower_short(self, inst: DispatchRule) -> str:
        return self._truncate_json(inst.follower)

    @admin.display(description=gettext_lazy("Confirmer"))
    def confirmer_short(self, inst: DispatchRule) -> str:
        return self._truncate_json(inst.confirmer)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("strategy", "target_scene")

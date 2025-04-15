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
from core.utils.tools import choices_to_items
from services.web.analyze.constants import ControlTypeChoices
from services.web.analyze.models import Control
from services.web.strategy_v2.models import (
    LinkTable,
    LinkTableTag,
    Strategy,
    StrategyTag,
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
        "status",
        "tags",
        "is_deleted",
    ]
    list_filter = ["namespace", "is_deleted", "strategy_type"]
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

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

from services.web.vision.models import (
    ReportGroup,
    ReportUserPreference,
    UserPanelFavorite,
    VisionPanel,
)


@admin.register(VisionPanel)
class VisionPanelAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "priority_index", "vision_id", "group", "is_enabled", "scenario"]
    list_filter = ["is_enabled", "scenario", "group"]
    search_fields = ["id", "name", "vision_id"]


@admin.register(ReportGroup)
class ReportGroupAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "priority_index"]
    search_fields = ["name"]


@admin.register(ReportUserPreference)
class ReportUserPreferenceAdmin(admin.ModelAdmin):
    list_display = ["id", "username"]
    search_fields = ["username"]


@admin.register(UserPanelFavorite)
class UserPanelFavoriteAdmin(admin.ModelAdmin):
    list_display = ["id", "username", "panel", "created_at"]
    list_filter = ["username"]
    search_fields = ["username", "panel__id", "panel__name"]

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

from apps.notice.models import NoticeGroup, NoticeLogV2


@admin.register(NoticeGroup)
class NoticeGroupAdmin(admin.ModelAdmin):
    list_display = ["group_id", "group_name", "group_member", "description", "is_deleted"]
    list_filter = ["is_deleted"]
    search_fields = ["group_id", "group_name"]


@admin.register(NoticeLogV2)
class NoticeLogV2Admin(admin.ModelAdmin):
    list_display = [
        "id",
        "relate_type",
        "relate_id",
        "agg_key",
        "msg_type",
        "receivers",
        "title",
        "create_at",
        "schedule_at",
        "schedule_result",
    ]
    list_filter = ["relate_type", "schedule_result"]
    search_fields = ["title", "agg_key", "relate_id"]
    ordering = ["-id"]

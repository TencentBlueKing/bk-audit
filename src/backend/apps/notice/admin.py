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

import datetime

from django.contrib import admin
from django.utils.translation import gettext_lazy
from rest_framework.settings import api_settings

from apps.notice.models import NoticeGroup, NoticeLog


@admin.register(NoticeGroup)
class NoticeGroupAdmin(admin.ModelAdmin):
    list_display = ["group_id", "group_name", "group_member", "description", "is_deleted"]
    list_filter = ["is_deleted"]
    search_fields = ["group_id", "group_name"]


@admin.register(NoticeLog)
class NoticeLogAdmin(admin.ModelAdmin):
    list_display = ["log_id", "msg_type", "receivers", "title", "send_at_str", "trace_id", "is_success", "is_duplicate"]
    list_filter = ["msg_type", "is_success", "is_duplicate"]
    search_fields = ["receivers", "title", "trace_id"]

    @admin.display(description=gettext_lazy("发送时间"))
    def send_at_str(self, inst: NoticeLog) -> str:
        return datetime.datetime.fromtimestamp(inst.send_at / 1000).strftime(api_settings.DATETIME_FORMAT)

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
from django.utils.translation import gettext_lazy

from services.web.query.constants import TaskEnum
from services.web.query.models import ExportFieldLog, LogExportTask, TaskDownloadRecord


@admin.register(LogExportTask)
class LogExportTaskAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "created_at",
        "get_status_display",
        "repeat_times",
        "task_start_time",
        "task_end_time",
        "name",
        "current_records",
        "total",
    ]
    search_fields = ["created_by", "status"]
    list_filter = ["status", "is_deleted", "namespace"]

    def get_status_display(self, obj):
        return dict(TaskEnum.choices).get(obj.status, obj.status)

    get_status_display.short_description = gettext_lazy("任务状态")

    actions = ['mark_as_deleted', 'restore_deleted']

    @admin.action(description="标记为删除")
    def mark_as_deleted(self, request, queryset):
        queryset.update(is_deleted=True)

    @admin.action(description="恢复删除")
    def restore_deleted(self, request, queryset):
        queryset.update(is_deleted=False)


@admin.register(ExportFieldLog)
class ExportFieldLogAdmin(admin.ModelAdmin):
    """
    自定义 ExportFieldLog 在 Admin 界面中的展示和操作方式
    """

    # 显示的字段
    list_display = ('raw_name', "keys", 'display_name', 'created_by', 'updated_by')

    # 搜索字段，允许通过这些字段在 admin 界面中搜索
    search_fields = ('raw_name', "keys", 'display_name')

    list_filter = [
        "raw_name",
    ]

    # 只显示部分记录，分页配置
    list_per_page = 100


@admin.register(TaskDownloadRecord)
class TaskDownloadRecordAdmin(admin.ModelAdmin):
    list_display = ["id", "downloaded_at", "downloaded_by", "task", "get_task_name"]
    search_fields = ["downloaded_by", "task__name"]

    def get_task_name(self, obj):
        return obj.task.name if obj.task else "-"

    get_task_name.short_description = "Task Name"

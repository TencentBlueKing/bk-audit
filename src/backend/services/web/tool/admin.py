# -*- coding: utf-8 -*-

from django.contrib import admin

from services.web.tool.models import Tool


@admin.register(Tool)
class ToolAdmin(admin.ModelAdmin):
    list_display = ["uid", "name", "namespace", "tool_type", "version", "updated_at"]
    search_fields = ["uid", "name", "namespace", "description"]
    list_filter = ["tool_type", "namespace"]
    readonly_fields = ["created_at", "updated_at"]

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields + ["uid", "tool_type", "version"]
        return self.readonly_fields

    fieldsets = (
        (None, {"fields": ("uid", "namespace", "name", "description", "tool_type", "version", "config")}),
        (
            "时间信息",
            {
                "fields": ("created_at", "updated_at"),
            },
        ),
    )

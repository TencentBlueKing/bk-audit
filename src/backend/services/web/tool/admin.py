# -*- coding: utf-8 -*-

from django.contrib import admin

from services.web.tool.models import Tool, ToolFavorite


@admin.register(Tool)
class ToolAdmin(admin.ModelAdmin):
    list_display = ["uid", "name", "namespace", "tool_type", "version", "updated_at"]
    search_fields = ["uid", "name", "namespace", "description"]
    list_filter = ["tool_type", "namespace"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(ToolFavorite)
class ToolFavoriteAdmin(admin.ModelAdmin):
    list_display = ["tool_uid", "username", "created_at"]
    list_filter = ["username"]
    search_fields = ["tool_uid", "username"]

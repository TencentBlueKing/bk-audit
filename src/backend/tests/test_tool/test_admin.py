# -*- coding: utf-8 -*-

from django.contrib import admin

from services.web.tool.models import Tool


class TestToolAdmin:
    def test_tool_admin_allows_editing_existing_tool_fields(self):
        tool_admin = admin.site._registry[Tool]
        readonly_fields = tool_admin.get_readonly_fields(request=None, obj=object())

        assert "uid" not in readonly_fields
        assert "tool_type" not in readonly_fields
        assert "version" not in readonly_fields
        assert readonly_fields == ["created_at", "updated_at"]

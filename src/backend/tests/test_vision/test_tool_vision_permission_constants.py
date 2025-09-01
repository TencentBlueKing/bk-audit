# -*- coding: utf-8 -*-
from unittest import mock

from django.test import TestCase


class DummyUser:
    def __init__(self, username):
        self.username = username


class DummyRequest:
    def __init__(self, query_params=None, username="admin"):
        self.query_params = query_params or {}
        self.user = DummyUser(username)


class DummyView:
    # 模拟 MetaViewSet
    __name__ = "MetaViewSet"

    @property
    def __class__(self):
        class _C:
            __name__ = "MetaViewSet"

        return _C


class DummyOtherView:
    # 模拟非 meta 的 view
    @property
    def __class__(self):
        class _C:
            __name__ = "DatasetViewSet"

        return _C


class TestToolVisionPermissionConstants(TestCase):
    def test_meta_extracts_constants_and_calls_skip(self):
        from services.web.vision.views import ToolVisionPermission

        # 构造带 constants[...] 的 query
        query = {
            "share_uid": "76ae...ec7",
            "type": "dashboard",
            "constants[system_id]": "1756457818000",
            "constants[caller_resource_type]": "risk",
            "constants[caller_resource_id]": "20250829165705091109",
            "constants[drill_field]": "raw_event_id",
            "constants[event_start_time]": "2025-08-29 16:56:58",
            "constants[event_end_time]": "2025-08-29 16:56:58",
        }
        req = DummyRequest(query)

        expected = {
            "caller_resource_type": "risk",
            "caller_resource_id": "20250829165705091109",
            "drill_field": "raw_event_id",
            "event_start_time": "2025-08-29 16:56:58",
            "event_end_time": "2025-08-29 16:56:58",
            "system_id": "1756457818000",
        }

        with mock.patch("services.web.vision.views.should_skip_permission_from", return_value=True) as m_should_skip:
            ok = ToolVisionPermission().has_permission(req, DummyView())
        self.assertTrue(ok)
        # 断言以 constants 字典形式调用
        args, kwargs = m_should_skip.call_args
        self.assertEqual(args[0], expected)

    def test_non_meta_does_not_use_constants_branch(self):
        from services.web.vision.views import ToolVisionPermission

        req = DummyRequest()
        # 非 meta 分支走工具权限与分享权限，为避免依赖 DB，这里打桩 get_tool_and_panel_id 与权限校验
        with (
            mock.patch.object(ToolVisionPermission, "get_tool_and_panel_id", return_value=("panel", "tool")),
            mock.patch("services.web.vision.views.UseToolPermission.has_permission", return_value=True),
            mock.patch("services.web.vision.views.check_bkvision_share_permission", return_value=True),
            mock.patch(
                "services.web.vision.views.Tool.last_version_tool", return_value=type("T", (), {"updated_by": "u"})()
            ),
            mock.patch("services.web.vision.views.should_skip_permission_from") as m_skip,
        ):
            ok = ToolVisionPermission().has_permission(req, DummyOtherView())
            self.assertTrue(ok)
            # 非 meta 不应以 constants 字典形式触发 should_skip_permission_from
            self.assertFalse(m_skip.called)

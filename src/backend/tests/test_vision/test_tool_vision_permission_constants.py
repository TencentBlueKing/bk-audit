# -*- coding: utf-8 -*-
from unittest import mock

from django.test import TestCase

from services.web.scene.models import Scene


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
            "current_type": "tool",
            "current_object_id": "tool-uid-1",
            'tool_variables': [{'raw_name': 'system_id', 'value': '1756457818000'}],
        }

        with (
            mock.patch.object(ToolVisionPermission, "get_tool_and_panel_id", return_value=("panel", "tool-uid-1")),
            mock.patch("services.web.vision.views.should_skip_permission_from", return_value=True) as m_should_skip,
        ):
            ok = ToolVisionPermission(True).has_permission(req, DummyView())
        self.assertTrue(ok)
        # 断言以 constants 字典形式调用
        args, kwargs = m_should_skip.call_args
        self.assertEqual(args[0], expected)

    def test_non_meta_does_not_use_constants_branch(self):
        from services.web.tool.constants import ToolTypeEnum
        from services.web.tool.models import Tool
        from services.web.vision.views import ToolVisionPermission

        req = DummyRequest()
        # 准备一个真实的 Tool 供权限逻辑读取 updated_by
        real_tool = Tool.objects.create(
            namespace="ns",
            name="vision_related_tool",
            uid="tool",
            version=1,
            tool_type=ToolTypeEnum.BK_VISION.value,
            config={"uid": "v_panel", "input_variable": []},
            updated_by="u",
        )
        # 非 meta 分支走工具权限与分享权限，这里打桩 get_tool_and_panel_id 与权限校验
        with (
            mock.patch.object(ToolVisionPermission, "get_tool_and_panel_id", return_value=("panel", "tool")),
            mock.patch("services.web.vision.views.UseToolPermission.has_permission", return_value=True),
            mock.patch("services.web.vision.views.check_bkvision_share_permission", return_value=True),
            mock.patch("services.web.vision.views.Tool.last_version_tool", return_value=real_tool),
            mock.patch("services.web.vision.views.should_skip_permission_from") as m_skip,
        ):
            ok = ToolVisionPermission().has_permission(req, DummyOtherView())
            self.assertTrue(ok)
            # 非 meta 不应以 constants 字典形式触发 should_skip_permission_from
            self.assertFalse(m_skip.called)

    def test_non_meta_uses_use_tool_permission_with_tool_uid(self):
        from services.web.tool.constants import ToolTypeEnum
        from services.web.tool.models import Tool
        from services.web.vision.views import ToolVisionPermission

        req = DummyRequest()
        real_tool = Tool.objects.create(
            namespace="ns",
            name="vision_related_tool_2",
            uid="tool-2",
            version=1,
            tool_type=ToolTypeEnum.BK_VISION.value,
            config={"uid": "v_panel", "input_variable": []},
            updated_by="u",
        )

        with (
            mock.patch.object(ToolVisionPermission, "get_tool_and_panel_id", return_value=("panel", "tool-2")),
            mock.patch("services.web.vision.views.UseToolPermission") as m_use_tool_perm,
            mock.patch("services.web.vision.views.check_bkvision_share_permission", return_value=True),
            mock.patch("services.web.vision.views.Tool.last_version_tool", return_value=real_tool),
        ):
            m_use_tool_perm.return_value.has_permission.return_value = True
            ok = ToolVisionPermission().has_permission(req, DummyOtherView())
            self.assertTrue(ok)
            m_use_tool_perm.assert_called_once()
            kwargs = m_use_tool_perm.call_args.kwargs
            self.assertIn("get_instance_id", kwargs)
            self.assertEqual(kwargs["get_instance_id"](), "tool-2")


class TestSceneManageViewSetPermission(TestCase):
    def test_scene_panel_manage_permissions_uses_instance_action_permission(self):
        from apps.permission.handlers.actions import ActionEnum
        from apps.permission.handlers.drf import InstanceActionPermission
        from apps.permission.handlers.resource_types import ResourceEnum
        from services.web.vision.views import ScenePanelManageViewSet

        view = ScenePanelManageViewSet()
        permissions = view.get_permissions()

        self.assertEqual(len(permissions), 1)
        self.assertIsInstance(permissions[0], InstanceActionPermission)
        self.assertEqual(permissions[0].actions, [ActionEnum.MANAGE_SCENE])
        self.assertEqual(permissions[0].resource_meta, ResourceEnum.SCENE)

    def test_scene_group_manage_permissions_uses_instance_action_permission(self):
        from apps.permission.handlers.actions import ActionEnum
        from apps.permission.handlers.drf import InstanceActionPermission
        from apps.permission.handlers.resource_types import ResourceEnum
        from services.web.vision.views import SceneReportGroupManageViewSet

        view = SceneReportGroupManageViewSet()
        view.action = "create"
        view.request = mock.MagicMock(query_params={}, data={"scene_id": "1"})
        view.kwargs = {}
        permissions = view.get_permissions()

        self.assertEqual(len(permissions), 1)
        self.assertIsInstance(permissions[0], InstanceActionPermission)
        self.assertEqual(permissions[0].actions, [ActionEnum.MANAGE_SCENE])
        self.assertEqual(permissions[0].resource_meta, ResourceEnum.SCENE)

    def test_get_scene_id_from_query_params(self):
        from services.web.vision.views import ScenePanelManageViewSet

        view = ScenePanelManageViewSet()
        view.request = mock.MagicMock(query_params={"scene_id": "123"}, data={})

        self.assertEqual(view.get_scene_id(), "123")

    def test_scene_group_manage_create_permission_uses_request_scene_id(self):
        from services.web.vision.views import SceneReportGroupManageViewSet

        view = SceneReportGroupManageViewSet()
        view.action = "create"
        view.request = mock.MagicMock(query_params={}, data={"scene_id": "456"})
        view.kwargs = {}
        permission = view.get_permissions()[0]

        self.assertEqual(permission._get_instance_id(view.request, view), "456")

    def test_scene_group_manage_destroy_permission_uses_group_scene_id(self):
        from services.web.vision.models import SceneReportGroup
        from services.web.vision.views import SceneReportGroupManageViewSet

        scene = Scene.objects.create(name="分组归属场景", managers=["admin"])
        group = SceneReportGroup.objects.create(scene=scene, name="待删分组")

        view = SceneReportGroupManageViewSet()
        view.action = "destroy"
        view.request = mock.MagicMock(query_params={}, data={})
        view.kwargs = {"group_id": str(group.id)}
        permission = view.get_permissions()[0]

        self.assertEqual(permission._get_instance_id(view.request, view), str(scene.scene_id))

    def test_scene_group_manage_destroy_prefers_group_scene_id_over_request_scene_id(self):
        from services.web.vision.models import SceneReportGroup
        from services.web.vision.views import SceneReportGroupManageViewSet

        scene = Scene.objects.create(name="真实归属场景", managers=["admin"])
        other_scene = Scene.objects.create(name="伪造请求场景", managers=["admin"])
        group = SceneReportGroup.objects.create(scene=scene, name="待更新分组")

        view = SceneReportGroupManageViewSet()
        view.action = "destroy"
        view.request = mock.MagicMock(query_params={}, data={"scene_id": str(other_scene.scene_id)})
        view.kwargs = {"group_id": str(group.id)}
        permission = view.get_permissions()[0]

        self.assertEqual(permission._get_instance_id(view.request, view), str(scene.scene_id))

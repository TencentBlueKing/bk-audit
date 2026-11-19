# -*- coding: utf-8 -*-
import uuid
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory

from apps.permission.handlers.drf import AnyOfPermissions, InstanceActionPermission
from core.exceptions import PermissionException, ValidationError
from services.web.common.scope_permission import ScopeInstancePermission
from services.web.scene.constants import BindingType, ResourceVisibilityType
from services.web.scene.models import ResourceBinding, ResourceBindingScene, Scene
from services.web.tool.models import Tool
from services.web.tool.permissions import CallerContextPermission, UseToolPermission
from services.web.tool.views import (
    SceneScopeToolViewSet,
    ToolViewSet,
    _append_scene_admin_contact,
)
from tests.base import TestCase


class TestToolViewPermissions(TestCase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.view = ToolViewSet()
        self.view.kwargs = {}

    def _get_use_tool_permission(self, permissions):
        self.assertEqual(len(permissions), 1)
        self.assertIsInstance(permissions[0], AnyOfPermissions)
        permission_ops = permissions[0].ops
        self.assertEqual(len(permission_ops), 2)
        self.assertIsInstance(permission_ops[0], CallerContextPermission)
        self.assertIsInstance(permission_ops[1], UseToolPermission)
        return permission_ops[1]

    def test_execute_permission_uses_uid_kwarg(self):
        request = SimpleNamespace(query_params={}, data={}, parser_context={"kwargs": {"uid": "tool-uid-3"}})
        self.view.request = request
        self.view.action = "execute"
        self.view.kwargs = {"uid": "tool-uid-3"}

        permission = self._get_use_tool_permission(self.view.get_permissions())

        self.assertEqual(permission._get_instance_id(request, self.view), "tool-uid-3")

    def test_execute_permission_prefers_uid_kwarg_over_request_uid(self):
        request = SimpleNamespace(
            query_params={"uid": "query-tool-uid"},
            data={"uid": "data-tool-uid"},
            parser_context={"kwargs": {"uid": "path-tool-uid"}},
        )
        self.view.request = request
        self.view.action = "execute"
        self.view.kwargs = {"uid": "path-tool-uid"}

        permission = self._get_use_tool_permission(self.view.get_permissions())

        self.assertEqual(permission._get_instance_id(request, self.view), "path-tool-uid")

    def test_scene_scope_tool_create_permission_uses_request_scene_id(self):
        view = SceneScopeToolViewSet()
        view.action = "create"
        view.request = SimpleNamespace(query_params={}, data={"scene_id": "11"})
        view.kwargs = {}

        permission = view.get_permissions()[0]

        self.assertIsInstance(permission, InstanceActionPermission)
        self.assertEqual(permission._get_instance_id(view.request, view), "11")

    def test_scene_scope_tool_destroy_permission_uses_tool_scene_id(self):
        scene = Scene.objects.create(name="工具归属场景")
        other_scene = Scene.objects.create(name="伪造请求场景")
        tool = Tool.objects.create(
            name="场景工具",
            uid=str(uuid.uuid4()),
            version=1,
            namespace="default",
            tool_type="data_search",
            config={},
            permission_owner="admin",
        )
        binding = ResourceBinding.objects.create(
            resource_type=ResourceVisibilityType.TOOL,
            resource_id=tool.uid,
            binding_type=BindingType.SCENE_BINDING,
        )
        ResourceBindingScene.objects.create(binding=binding, scene_id=scene.scene_id)

        view = SceneScopeToolViewSet()
        view.action = "destroy"
        view.request = SimpleNamespace(
            query_params={},
            data={"scene_id": str(other_scene.scene_id)},
            parser_context={"kwargs": {"uid": tool.uid}},
        )
        view.kwargs = {"uid": tool.uid}

        permission = view.get_permissions()[0]

        self.assertIsInstance(permission, InstanceActionPermission)
        self.assertEqual(permission._get_instance_id(view.request, view), str(scene.scene_id))


class TestUseToolEmptyApplyWindow(SimpleTestCase):
    def _call(self, uid="tool-1"):
        request = SimpleNamespace()
        view = SimpleNamespace(kwargs={"uid": uid}, lookup_field="uid", lookup_url_kwarg=None)
        return UseToolPermission().has_permission(request, view)

    def test_missing_tool_is_plain_message(self):
        with patch.object(Tool, "last_version_tool", return_value=None):
            with self.assertRaises(ValidationError) as raised:
                self._call()

        self.assertEqual(raised.exception.message, "工具不存在，联系场景管理员")
        self.assertEqual(raised.exception.STATUS_CODE, 400)
        self.assertNotEqual(raised.exception.code, "9900403")

    def test_empty_apply_url_keeps_original_message(self):
        denied = PermissionException(action_name="访问资源(tool:tool-1)", permission={}, apply_url="")
        with (
            patch.object(Tool, "last_version_tool", return_value=SimpleNamespace(status="published")),
            patch.object(UseToolPermission, "_is_scene_binding_enabled", return_value=True),
            patch.object(UseToolPermission, "_is_resource_manager_exception", return_value=False),
            patch.object(UseToolPermission, "_is_resource_published", return_value=True),
            patch.object(ScopeInstancePermission, "has_permission", side_effect=denied),
        ):
            with self.assertRaises(ValidationError) as raised:
                self._call()

        self.assertEqual(raised.exception.message, "当前用户无 [访问资源(tool:tool-1)] 权限，联系场景管理员")
        self.assertEqual(raised.exception.STATUS_CODE, 400)
        self.assertIsNone(raised.exception.data)
        self.assertNotEqual(raised.exception.code, "9900403")

    def test_inner_apply_url_is_not_returned(self):
        denied = PermissionException(
            action_name="访问资源(tool:tool-1)",
            permission={"id": "tool"},
            apply_url="https://iam.example/apply",
        )
        with (
            patch.object(Tool, "last_version_tool", return_value=SimpleNamespace(status="published")),
            patch.object(UseToolPermission, "_is_scene_binding_enabled", return_value=True),
            patch.object(UseToolPermission, "_is_resource_manager_exception", return_value=False),
            patch.object(UseToolPermission, "_is_resource_published", return_value=True),
            patch.object(ScopeInstancePermission, "has_permission", side_effect=denied),
        ):
            with self.assertRaises(ValidationError) as raised:
                self._call()

        self.assertEqual(raised.exception.STATUS_CODE, 400)
        self.assertIsNone(raised.exception.data)
        self.assertEqual(raised.exception.message, "当前用户无 [访问资源(tool:tool-1)] 权限，联系场景管理员")

    def test_unpublished_tool_is_400_for_ordinary_user(self):
        with (
            patch.object(Tool, "last_version_tool", return_value=SimpleNamespace(status="unpublished")),
            patch.object(UseToolPermission, "_is_scene_binding_enabled", return_value=True),
            patch.object(UseToolPermission, "_is_resource_manager_exception", return_value=False),
            patch.object(UseToolPermission, "_is_resource_published", return_value=False),
        ):
            with self.assertRaises(ValidationError) as raised:
                self._call()

        self.assertEqual(raised.exception.message, "工具未上架，联系场景管理员")
        self.assertEqual(raised.exception.STATUS_CODE, 400)

    def test_manager_can_use_unpublished_tool(self):
        with (
            patch.object(Tool, "last_version_tool", return_value=SimpleNamespace(status="unpublished")),
            patch.object(UseToolPermission, "_is_scene_binding_enabled", return_value=True),
            patch.object(UseToolPermission, "_is_resource_manager_exception", return_value=True),
            patch.object(ScopeInstancePermission, "has_permission", return_value=True),
        ):
            self.assertTrue(self._call())

    def test_disabled_or_deleted_scene_binding_is_400(self):
        with (
            patch.object(Tool, "last_version_tool", return_value=SimpleNamespace(status="published")),
            patch.object(UseToolPermission, "_is_scene_binding_enabled", return_value=False),
            patch.object(UseToolPermission, "_is_resource_manager_exception", return_value=True),
        ):
            with self.assertRaises(ValidationError) as raised:
                self._call()

        self.assertEqual(raised.exception.message, "绑定场景停用或被删除，联系场景管理员")
        self.assertEqual(raised.exception.STATUS_CODE, 400)

    def test_execute_contact_does_not_rewrite_these_messages(self):
        self.assertEqual(_append_scene_admin_contact("工具不存在"), "工具不存在，联系场景管理员")
        self.assertEqual(
            _append_scene_admin_contact("当前用户无 [访问资源(tool:tool-1)] 权限，联系场景管理员"),
            "当前用户无 [访问资源(tool:tool-1)] 权限，联系场景管理员",
        )

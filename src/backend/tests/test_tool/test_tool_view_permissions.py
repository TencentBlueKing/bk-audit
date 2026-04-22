# -*- coding: utf-8 -*-
import uuid
from types import SimpleNamespace

from rest_framework.test import APIRequestFactory

from apps.permission.handlers.drf import AnyOfPermissions, InstanceActionPermission
from services.web.scene.constants import BindingType, ResourceVisibilityType
from services.web.scene.models import ResourceBinding, ResourceBindingScene, Scene
from services.web.tool.models import Tool
from services.web.tool.permissions import CallerContextPermission, UseToolPermission
from services.web.tool.views import SceneScopeToolViewSet, ToolViewSet
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
        scene = Scene.objects.create(name="工具归属场景", managers=["admin"])
        other_scene = Scene.objects.create(name="伪造请求场景", managers=["admin"])
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

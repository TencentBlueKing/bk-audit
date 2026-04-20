# -*- coding: utf-8 -*-
from types import SimpleNamespace

from rest_framework.test import APIRequestFactory

from apps.permission.handlers.drf import AnyOfPermissions
from services.web.tool.permissions import CallerContextPermission, UseToolPermission
from services.web.tool.views import ToolViewSet
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
        request = SimpleNamespace(query_params={}, data={})
        self.view.request = request
        self.view.action = "execute"
        self.view.kwargs = {"uid": "tool-uid-3"}

        permission = self._get_use_tool_permission(self.view.get_permissions())

        self.assertEqual(permission._get_instance_id(request, self.view), "tool-uid-3")

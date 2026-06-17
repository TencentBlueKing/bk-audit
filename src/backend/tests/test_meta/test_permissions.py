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

import json
from types import SimpleNamespace
from unittest import mock

from rest_framework.test import APIRequestFactory

from apps.meta.permissions import SearchLogPermission, SearchLogSystemSearchPermission
from apps.meta.views.system_views import SystemsViewSet
from apps.permission.handlers.actions import ActionEnum
from apps.permission.handlers.drf import AnyOfPermissions
from core.exceptions import PermissionException
from services.web.common.constants import ScopeType
from tests.base import TestCase


class TestSearchLogSystemSearchPermission(TestCase):
    def setUp(self):
        self.permission = SearchLogSystemSearchPermission()
        self.request = APIRequestFactory().get("/meta/systems/bklog/search/")
        self.view = SimpleNamespace(lookup_url_kwarg=None, lookup_field="system_id", kwargs={"system_id": "bklog"})

    @mock.patch("apps.meta.permissions.get_request_username", mock.Mock(return_value="admin"))
    @mock.patch(
        "apps.meta.permissions.SearchLogPermission.has_system_search_permission",
        mock.Mock(return_value=True),
    )
    def test_has_permission_when_authorized(self):
        self.assertTrue(self.permission.has_permission(self.request, self.view))

    @mock.patch("apps.meta.permissions.get_request_username", mock.Mock(return_value="admin"))
    @mock.patch(
        "apps.meta.permissions.SearchLogPermission.has_system_search_permission",
        mock.Mock(return_value=False),
    )
    @mock.patch("apps.permission.handlers.service.PermissionService")
    def test_has_permission_raise_apply_exception_when_unauthorized(self, permission_service_cls):
        permission_service_cls.return_value.get_apply_data.return_value = (
            [{"id": ActionEnum.VIEW_SYSTEM.id}],
            "https://iam.example/apply",
        )
        with self.assertRaises(PermissionException) as cm:
            self.permission.has_permission(self.request, self.view)

        exception_data = json.loads(cm.exception.data)
        self.assertEqual(exception_data["apply_url"], "https://iam.example/apply")
        self.assertEqual(exception_data["permission"], [{"id": ActionEnum.VIEW_SYSTEM.id}])
        permission_service_cls.assert_called_once_with(username="admin")


class TestSearchLogPermission(TestCase):
    @mock.patch("services.web.common.scope_permission.ScopePermission")
    def test_get_scope_auth_systems_return_empty_string_filter_when_scope_has_no_systems(self, scope_permission_cls):
        scope_permission_cls.return_value.get_system_ids_for_scope.return_value = set()

        system_ids = SearchLogPermission.get_scope_auth_systems(
            scope_type=ScopeType.SCENE,
            scope_id="1",
            username="admin",
        )

        self.assertEqual(system_ids, [""])


class TestSystemsViewSetPermissions(TestCase):
    def test_create_system_has_no_iam_permission_check(self):
        view = SystemsViewSet()
        view.action = "create"

        self.assertEqual(view.get_permissions(), [])

    def test_update_audit_status_requires_system_admin_permission_without_source_check(self):
        view = SystemsViewSet()
        view.action = "audit_status"

        permissions = view.get_permissions()

        self.assertEqual(len(permissions), 1)
        self.assertIsInstance(permissions[0], AnyOfPermissions)

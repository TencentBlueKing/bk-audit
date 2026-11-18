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

from apps.meta.constants import SystemAuditStatusEnum
from apps.meta.models import System
from apps.meta.permissions import SearchLogPermission, SearchLogSystemSearchPermission
from apps.meta.views.system_views import SystemsViewSet
from apps.permission.handlers.actions import ActionEnum
from apps.permission.handlers.drf import AnyOfPermissions
from core.exceptions import PermissionException
from services.web.common.constants import ScopeType
from services.web.scene.models import Scene, SceneSystem
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
    def setUp(self):
        for system_id, status in [
            ("accessed-system", SystemAuditStatusEnum.ACCESSED),
            ("pending-system", SystemAuditStatusEnum.PENDING),
            ("unauthorized-system", SystemAuditStatusEnum.ACCESSED),
        ]:
            System.objects.create(namespace="example", system_id=system_id, instance_id=system_id, audit_status=status)

    @mock.patch("services.web.common.scope_permission.ScopePermission")
    def test_each_scope_only_returns_authorized_accessed_systems(self, permission_cls):
        permission_cls.return_value.get_system_ids_for_scope.return_value = [
            "accessed-system",
            "pending-system",
            "missing-system",
        ]
        for scope_type, scope_id in [
            (ScopeType.SYSTEM, "accessed-system"),
            (ScopeType.SCENE, "42"),
            (ScopeType.CROSS_SYSTEM, None),
            (ScopeType.CROSS_SCENE, None),
        ]:
            with self.subTest(scope_type=scope_type):
                self.assertEqual(
                    SearchLogPermission.get_scope_auth_systems(scope_type, scope_id, "export-user"), ["accessed-system"]
                )

    @mock.patch("services.web.common.scope_permission.ScopePermission")
    def test_only_pending_or_missing_authorizations_keep_empty_filter(self, permission_cls):
        permission_cls.return_value.get_system_ids_for_scope.return_value = ["pending-system", "missing-system"]
        self.assertEqual(SearchLogPermission.get_scope_auth_systems(ScopeType.CROSS_SYSTEM, None, "export-user"), [""])

    @mock.patch.object(
        SearchLogPermission,
        "_get_scene_scope_system_ids",
        return_value={"accessed-system", "pending-system", "missing-system"},
    )
    @mock.patch.object(SearchLogPermission, "_get_system_scope_system_ids", return_value=set())
    def test_scene_authorization_requires_accessed_system(self, system_ids, scene_ids):
        self.assertTrue(SearchLogPermission.has_system_search_permission("accessed-system", "export-user"))
        for system_id in ["pending-system", "missing-system", "unauthorized-system", ""]:
            with self.subTest(system_id=system_id):
                self.assertFalse(SearchLogPermission.has_system_search_permission(system_id, "export-user"))

    @mock.patch.object(SearchLogPermission, "_get_scene_scope_system_ids", return_value=set())
    @mock.patch.object(
        SearchLogPermission,
        "_get_system_scope_system_ids",
        return_value={"accessed-system", "pending-system", "missing-system"},
    )
    def test_system_authorization_requires_accessed_system(self, system_ids, scene_ids):
        self.assertTrue(SearchLogPermission.has_system_search_permission("accessed-system", "export-user"))
        self.assertFalse(SearchLogPermission.has_system_search_permission("pending-system", "export-user"))
        self.assertFalse(SearchLogPermission.has_system_search_permission("missing-system", "export-user"))

    @mock.patch("apps.meta.permissions.resource.meta.system_list_all")
    @mock.patch.object(SearchLogPermission, "_get_scene_scope_system_ids", return_value={"pending-system"})
    @mock.patch.object(
        SearchLogPermission, "_get_system_scope_system_ids", return_value={"accessed-system", "missing-system"}
    )
    def test_candidates_preserve_catalog_but_filter_authorized_ids(self, system_ids, scene_ids, list_all):
        catalog = [{"id": sid} for sid in ["accessed-system", "pending-system", "unauthorized-system"]]
        list_all.return_value = catalog
        systems, authorized = SearchLogPermission.get_auth_systems_by_username("example", "export-user")
        self.assertEqual(systems, catalog)
        self.assertEqual(authorized, ["accessed-system"])
        list_all.assert_called_once_with(namespace="example")

    @mock.patch("services.web.common.scope_permission.Permission")
    def test_real_manager_scope_excludes_pending_system(self, permission_cls):
        permission_cls.return_value.get_authorized_resource_ids.return_value = []
        System.objects.filter(system_id__in=["accessed-system", "pending-system"]).update(managers=["export-user"])
        self.assertEqual(
            SearchLogPermission.get_scope_auth_systems(ScopeType.CROSS_SYSTEM, None, "export-user"), ["accessed-system"]
        )
        self.assertTrue(SearchLogPermission.has_system_search_permission("accessed-system", "export-user"))
        self.assertFalse(SearchLogPermission.has_system_search_permission("pending-system", "export-user"))

    @mock.patch("services.web.common.scope_permission.Permission")
    def test_real_scene_scope_excludes_pending_and_missing_systems(self, permission_cls):
        scene = Scene.objects.create(name="synthetic-log-scope")
        permission_cls.return_value.get_authorized_resource_ids.return_value = [str(scene.scene_id)]
        permission_cls.return_value.is_allowed.return_value = True
        for system_id in ["accessed-system", "pending-system", "missing-system"]:
            SceneSystem.objects.create(scene=scene, system_id=system_id)
        for scope_type, scope_id in [(ScopeType.SCENE, str(scene.scene_id)), (ScopeType.CROSS_SCENE, None)]:
            with self.subTest(scope_type=scope_type):
                self.assertEqual(
                    SearchLogPermission.get_scope_auth_systems(scope_type, scope_id, "export-user"), ["accessed-system"]
                )
        self.assertTrue(SearchLogPermission.has_system_search_permission("accessed-system", "export-user"))
        self.assertFalse(SearchLogPermission.has_system_search_permission("pending-system", "export-user"))

    @mock.patch("services.web.common.scope_permission.Permission")
    def test_real_all_systems_scene_only_returns_accessed_systems(self, permission_cls):
        scene = Scene.objects.create(name="synthetic-all-log-scope")
        permission_cls.return_value.get_authorized_resource_ids.return_value = [str(scene.scene_id)]
        SceneSystem.objects.create(scene=scene, system_id="", is_all_systems=True)
        self.assertEqual(
            set(SearchLogPermission.get_scope_auth_systems(ScopeType.CROSS_SCENE, None, "export-user")),
            {"accessed-system", "unauthorized-system"},
        )

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

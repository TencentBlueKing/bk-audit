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
from types import SimpleNamespace
from unittest import mock

from django.test import override_settings

from apps.meta.models import System
from apps.permission.handlers.actions import ActionEnum
from tests.base import TestCase
from tests.test_permission.constants import (
    CHECK_ALLOWED_API_RESP,
    CHECK_PERMISSION_DATA,
    CHECK_PERMISSION_OF_BK_LOG_DATA,
    CHECK_PERMISSION_PARAMS,
    PermissionMock,
)


class PermissionTest(TestCase):
    def setUp(self) -> None:
        pass

    @mock.patch("permission.resources.PermissionService", mock.Mock(return_value=PermissionMock()))
    def test_check_permission(self):
        """CheckPermissionResource"""
        result = self.resource.permission.check_permission(**CHECK_PERMISSION_PARAMS)
        self.assertEqual(result, CHECK_PERMISSION_DATA)

    @mock.patch("permission.resources.get_request_username", mock.Mock(return_value="admin"), create=True)
    @mock.patch("permission.resources.PermissionService", mock.Mock(return_value=PermissionMock()))
    def test_check_system_permission_allows_system_manager(self):
        """系统管理员即使没有 IAM 权限，也应拥有系统查看/编辑权限"""
        system = System.objects.create(namespace=self.namespace, system_id="manager-system", managers=["admin"])

        result = self.resource.permission.check_permission(
            action_ids=f"{ActionEnum.VIEW_SYSTEM.id},{ActionEnum.EDIT_SYSTEM.id}",
            resources=system.system_id,
        )

        self.assertEqual(result, {ActionEnum.VIEW_SYSTEM.id: True, ActionEnum.EDIT_SYSTEM.id: True})

    @mock.patch("permission.resources.api.bk_log.check_allowed", mock.Mock(return_value=CHECK_ALLOWED_API_RESP))
    @mock.patch("permission.resources.settings.BK_IAM_SYSTEM_ID", mock.Mock(return_value=None))
    def test_check_permission_of_bk_log(self):
        """CheckPermissionResource"""
        result = self.resource.permission.check_permission(**CHECK_PERMISSION_PARAMS)
        self.assertEqual(result, CHECK_PERMISSION_OF_BK_LOG_DATA)

    @override_settings(IAM_PERMISSION_BACKEND="v4", BK_IAM_SYSTEM_ID="bk-audit")
    @mock.patch("apps.permission.handlers.iam_v4.get_local_request")
    @mock.patch("apps.permission.handlers.iam_v4.api.bk_iam_v4.direct_auth")
    def test_check_permission_uses_v4_backend_chain(self, mock_direct_auth, mock_get_request):
        """CheckPermissionResource -> PermissionService -> IAMV4Permission"""
        mock_get_request.return_value = SimpleNamespace(user=SimpleNamespace(username="admin"))
        mock_direct_auth.request.return_value = {"allowed": True}

        result = self.resource.permission.check_permission(
            action_ids=ActionEnum.VIEW_SCENE.id,
            resources="100",
        )

        self.assertEqual(result, {ActionEnum.VIEW_SCENE.id: True})
        mock_direct_auth.request.assert_called_once_with(
            {
                "system_id": "bk-audit",
                "subject": {"type": "user", "id": "admin"},
                "action_id": ActionEnum.VIEW_SCENE.id,
                "resource": {"type": "scene", "id": "100"},
            }
        )

    @override_settings(IAM_PERMISSION_BACKEND="v4", BK_IAM_SYSTEM_ID="bk-audit")
    @mock.patch("apps.permission.handlers.iam_v4.get_local_request")
    @mock.patch("apps.permission.handlers.iam_v4.api.bk_iam_v4.list_authorized_resource")
    def test_check_any_permission_uses_scene_dimension_for_risk_in_v4(self, mock_list, mock_get_request):
        """CheckAnyPermissionResource -> PermissionService -> IAMV4Permission risk scene auth"""
        mock_get_request.return_value = SimpleNamespace(user=SimpleNamespace(username="admin"))
        mock_list.return_value = [{"type": "scene", "ids": ["100"]}]

        result = self.resource.permission.check_any_permission(action_ids=ActionEnum.LIST_RISK.id)

        self.assertEqual(result, {ActionEnum.LIST_RISK.id: True})
        mock_list.assert_called_once_with(
            system_id="bk-audit",
            subject={"type": "user", "id": "admin"},
            action_id=ActionEnum.LIST_RISK.id,
        )

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

from apps.meta.permissions import SearchLogSystemSearchPermission
from apps.permission.handlers.actions import ActionEnum
from core.exceptions import PermissionException
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
    @mock.patch("apps.permission.handlers.permission.Permission")
    def test_has_permission_raise_apply_exception_when_unauthorized(self, permission_cls):
        permission_cls.return_value.get_apply_data.return_value = (
            [{"id": ActionEnum.VIEW_SYSTEM.id}],
            "https://iam.example/apply",
        )
        with self.assertRaises(PermissionException) as cm:
            self.permission.has_permission(self.request, self.view)

        exception_data = json.loads(cm.exception.data)
        self.assertEqual(exception_data["apply_url"], "https://iam.example/apply")
        self.assertEqual(exception_data["permission"], [{"id": ActionEnum.VIEW_SYSTEM.id}])

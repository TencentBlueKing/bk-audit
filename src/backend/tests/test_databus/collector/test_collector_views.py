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

from apps.permission.handlers.drf import AnyOfPermissions, InstanceActionPermission
from services.web.databus.collector.views import (
    CollectorsViewSet,
    DataIdEtlViewSet,
    DataIdsViewSet,
)
from tests.base import TestCase


class DatabusCollectorViewPermissionTest(TestCase):
    def get_permissions(self, view_cls, action):
        view = view_cls()
        view.action = action
        return view.get_permissions()

    def assert_flat_permissions(self, permissions):
        self.assertTrue(permissions)
        self.assertFalse(any(isinstance(permission, list) for permission in permissions))

    def assert_system_edit_permissions(self, permissions):
        self.assertEqual(len(permissions), 1)
        self.assertIsInstance(permissions[0], AnyOfPermissions)

    def test_api_push_actions_use_system_edit_permission_handler(self):
        for action in ["api_push", "create_api_push", "api_push_tail_log"]:
            permissions = self.get_permissions(CollectorsViewSet, action)

            self.assert_flat_permissions(permissions)
            self.assert_system_edit_permissions(permissions)

    def test_collector_info_and_mutation_permissions_are_flat(self):
        info_permissions = self.get_permissions(CollectorsViewSet, "get_collector_info")
        self.assert_flat_permissions(info_permissions)
        self.assertIsInstance(info_permissions[0], AnyOfPermissions)
        self.assertIsInstance(info_permissions[1], InstanceActionPermission)

        for action in ["update_collector", "delete_collector"]:
            permissions = self.get_permissions(CollectorsViewSet, action)

            self.assert_flat_permissions(permissions)
            self.assertIsInstance(permissions[0], AnyOfPermissions)
            self.assertIsInstance(permissions[1], InstanceActionPermission)

    def test_data_id_tail_and_destroy_use_system_edit_permission_handler(self):
        for action in ["tail", "destroy"]:
            permissions = self.get_permissions(DataIdsViewSet, action)

            self.assert_flat_permissions(permissions)
            self.assert_system_edit_permissions(permissions)

    def test_data_id_etl_actions_use_system_edit_permission_handler(self):
        for action in ["create", "field_history"]:
            permissions = self.get_permissions(DataIdEtlViewSet, action)

            self.assert_flat_permissions(permissions)
            self.assert_system_edit_permissions(permissions)

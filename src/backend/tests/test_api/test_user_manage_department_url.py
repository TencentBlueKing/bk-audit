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
software distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from unittest import mock

from django.test import override_settings

from api.user_manage.default import ListUserDepartments, RetrieveDepartment
from tests.base import TestCase


class UserManageDepartmentUrlTest(TestCase):
    """验证 user_manage 部门相关资源在多租户/单租户下的 URL 拼装参数映射
    约定：
    - 多租户：调用方传 id=，资源层映射为 department_id / bk_username 后拼 URL
    - 单租户：保持原有 id 路径（id 作为 query string 经 session.get(params=...) 传出），行为不变
    """

    def _mock_get(self, resource):
        """mock session.get，使 request() 不发起真实网络请求，并捕获最终 URL 与 params。"""
        response = mock.Mock()
        response.json.return_value = {"result": True, "code": 0, "data": {}}
        response.raise_for_status.return_value = None
        resource.session.get = mock.Mock(return_value=response)
        return resource.session.get

    @override_settings(BKPAAS_MULTI_TENANT_MODE=True)
    def test_multi_tenant_retrieve_department_maps_id_to_department_id(self):
        """多租户：id 应映射为 department_id 拼进 URL，且不再作为 query 参数发送"""
        resource = RetrieveDepartment()
        session_get = self._mock_get(resource)
        resource.request.refresh({"id": "20"})

        url = session_get.call_args.args[0]
        params = session_get.call_args.kwargs["params"]
        self.assertIn("/api/v3/open/tenant/departments/20/", url)
        self.assertNotIn("id", params)
        self.assertEqual(params.get("department_id"), "20")

    @override_settings(BKPAAS_MULTI_TENANT_MODE=True)
    def test_multi_tenant_list_user_departments_maps_id_to_bk_username(self):
        """多租户：id 应映射为 bk_username 拼进 URL，且不再作为 query 参数发送"""
        resource = ListUserDepartments()
        session_get = self._mock_get(resource)
        resource.request.refresh({"id": "tester"})

        url = session_get.call_args.args[0]
        params = session_get.call_args.kwargs["params"]
        self.assertIn("/api/v3/open/tenant/users/tester/departments/", url)
        self.assertNotIn("id", params)
        self.assertEqual(params.get("bk_username"), "tester")

    @override_settings(BKPAAS_MULTI_TENANT_MODE=True)
    def test_multi_tenant_no_double_mapping_when_target_key_present(self):
        """多租户：调用方已传 department_id 时不应二次映射/丢值"""
        resource = RetrieveDepartment()
        session_get = self._mock_get(resource)
        resource.request.refresh({"department_id": "99"})

        url = session_get.call_args.args[0]
        params = session_get.call_args.kwargs["params"]
        self.assertIn("/api/v3/open/tenant/departments/99/", url)
        self.assertNotIn("id", params)
        self.assertEqual(params.get("department_id"), "99")

    @override_settings(BKPAAS_MULTI_TENANT_MODE=False)
    def test_single_tenant_retrieve_department_keeps_id_query(self):
        """单租户：id 仍作为 query string 经 params 传出，URL 保持旧路径（无租户占位符）"""
        resource = RetrieveDepartment()
        session_get = self._mock_get(resource)
        resource.request.refresh({"id": "20"})

        url = session_get.call_args.args[0]
        params = session_get.call_args.kwargs["params"]
        self.assertEqual(params.get("id"), "20")
        self.assertNotIn("/api/v3/open/tenant/departments/", url)

    @override_settings(BKPAAS_MULTI_TENANT_MODE=False)
    def test_single_tenant_list_user_departments_keeps_id_query(self):
        """单租户：id 仍作为 query string 经 params 传出，URL 保持旧路径（无租户占位符）"""
        resource = ListUserDepartments()
        session_get = self._mock_get(resource)
        resource.request.refresh({"id": "tester"})

        url = session_get.call_args.args[0]
        params = session_get.call_args.kwargs["params"]
        self.assertEqual(params.get("id"), "tester")
        self.assertNotIn("/api/v3/open/tenant/users/", url)

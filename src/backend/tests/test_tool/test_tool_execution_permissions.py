# -*- coding: utf-8 -*-
"""临时工具调试的角色权限回归。

通过真实 HTTP 路由、DRF 权限和 Resource 序列化验证角色准入。
仅替换外部 IAM 决策、BKBase 与 HTTP 出站，不要求调试绑定场景。
"""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings
from django.urls import resolve
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIRequestFactory, force_authenticate

from api.bk_base.default import QuerySyncResource
from apps.permission.handlers.actions import ActionEnum
from services.web.tool.executor.tool import ToolExecutorFactory


@override_settings(ROOT_URLCONF="services.web.urls")
class TestToolDebugPermissions(SimpleTestCase):
    """平台管理员或任意场景管理员可调试，普通用户在执行前拒绝。"""

    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.platform_manager = False
        self.scene_manager = False
        self.platform_checks = []
        self.scene_checks = []
        self.enterContext(
            patch("apps.permission.handlers.drf.PermissionService.is_allowed", side_effect=self._check_platform)
        )
        self.enterContext(
            patch(
                "apps.permission.handlers.drf.PermissionService.has_action_any_permission",
                side_effect=self._check_any_scene,
            )
        )
        self.http = self.enterContext(patch("services.web.tool.executor.tool.requests.request"))
        self.http.return_value = MagicMock(status_code=200)
        self.http.return_value.json.return_value = {"marker": "debug-result"}
        self.create_executor = self.enterContext(
            patch.object(
                ToolExecutorFactory,
                "create_from_config",
                autospec=True,
                side_effect=ToolExecutorFactory.create_from_config,
            )
        )
        self.payload = {
            "tool_type": "api",
            "config": {
                "api_config": {
                    "url": "https://api.example.invalid/debug",
                    "method": "GET",
                    "headers": [],
                    "auth_config": {"method": "none"},
                },
                "input_variable": [],
                "output_config": {"enable_grouping": False},
            },
            "params": {},
        }

    def _check_platform(self, action, resources, raise_exception):
        """模拟平台管理动作的外部 IAM 判定。"""
        self.platform_checks.append((action, resources))
        allowed = action == ActionEnum.MANAGE_PLATFORM and self.platform_manager
        if not allowed and raise_exception:
            raise PermissionDenied("无平台管理权限")
        return allowed

    def _check_any_scene(self, action):
        """仅场景管理动作的任意实例授权可通过，查看权限不能替代。"""
        self.scene_checks.append(action)
        return action == ActionEnum.MANAGE_SCENE and self.scene_manager

    def _post(self, query=""):
        path = "/api/v1/namespaces/default/tool/tool_execute_debug/"
        match = resolve(path)
        request = self.factory.post(path + query, deepcopy(self.payload), format="json")
        force_authenticate(request, user=SimpleNamespace(username="test-user", is_authenticated=True))
        return match.func(request, **match.kwargs)

    def _assert_rejected(self, response):
        self.assertEqual(response.status_code, 403, response.data)
        self.create_executor.assert_not_called()
        self.http.assert_not_called()

    def _assert_api_result(self, response):
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            response.data,
            {
                "data": {
                    "status_code": 200,
                    "result": {"marker": "debug-result"},
                    "err_type": "none",
                    "message": "",
                },
                "tool_type": "api",
            },
        )
        self.assertEqual(self.http.call_count, 1)

    def test_platform_manager_can_debug_without_scene_id(self):
        self.platform_manager = True
        self._assert_api_result(self._post())
        self.assertEqual(self.platform_checks, [(ActionEnum.MANAGE_PLATFORM, [])])
        self.assertEqual(self.scene_checks, [])

    def test_any_scene_manager_can_debug_without_scene_id(self):
        self.scene_manager = True
        self._assert_api_result(self._post())
        self.assertEqual(self.scene_checks, [ActionEnum.MANAGE_SCENE])

    def test_ordinary_user_is_rejected_before_executor_creation(self):
        self._assert_rejected(self._post())

    def test_scene_viewer_cannot_substitute_for_scene_manager(self):
        with patch(
            "apps.permission.handlers.drf.PermissionService.has_action_any_permission",
            side_effect=lambda action: action == ActionEnum.VIEW_SCENE,
        ):
            self._assert_rejected(self._post())

    def test_scene_id_cannot_grant_ordinary_user_debug_permission(self):
        self.payload["scene_id"] = "untrusted-scene"
        self._assert_rejected(self._post(query="?scene_id=another-scene"))

    def test_admin_flags_in_payload_cannot_grant_debug_permission(self):
        self.payload.update(is_superuser=True, role="manager", manage_platform=True, manage_scene=True)
        self._assert_rejected(self._post())

    def test_scene_manager_does_not_need_to_match_incidental_scene_context(self):
        self.scene_manager = True
        self.payload["scene_id"] = "incidental-scene"
        self._assert_api_result(self._post(query="?scene_id=different-scene"))

    def test_legacy_payload_without_params_remains_valid(self):
        self.scene_manager = True
        self.payload.pop("params")
        self._assert_api_result(self._post())

    def test_post_api_debug_remains_supported(self):
        self.scene_manager = True
        self.payload["config"]["api_config"]["method"] = "POST"
        self._assert_api_result(self._post())
        self.assertEqual(self.http.call_args.kwargs["method"], "post")

    def _sql_payload(self):
        return {
            "tool_type": "data_search",
            "config": {
                "sql": "SELECT 1 AS value",
                "referenced_tables": [],
                "input_variable": [],
                "output_fields": [],
            },
            "params": {"page": 1, "page_size": 10},
        }

    def _assert_sql_result(self):
        self.payload = self._sql_payload()
        with patch.object(
            QuerySyncResource,
            "bulk_request",
            return_value=[{"list": [{"value": 1}]}, {"list": [{"count": 1}]}],
        ):
            response = self._post()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            response.data,
            {
                "tool_type": "data_search",
                "data": {
                    "page": 1,
                    "num_pages": 10,
                    "total": 1,
                    "results": [{"value": 1}],
                    "query_sql": "SELECT 1 AS value LIMIT 10",
                    "count_sql": "SELECT COUNT(*) AS count FROM (SELECT 1 AS value) AS _sub",
                },
            },
        )
        self.http.assert_not_called()

    def test_platform_manager_can_debug_sql(self):
        self.platform_manager = True
        self._assert_sql_result()

    def test_any_scene_manager_can_debug_sql(self):
        self.scene_manager = True
        self._assert_sql_result()

    def test_sql_cannot_bypass_debug_permission(self):
        self.payload = self._sql_payload()
        self._assert_rejected(self._post())

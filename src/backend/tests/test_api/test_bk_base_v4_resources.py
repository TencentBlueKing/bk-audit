"""V4资源真实请求链路中的URL、完整PUT及个人鉴权契约。"""
import json
from types import SimpleNamespace
from unittest import mock

from django.core.exceptions import PermissionDenied
from django.test import SimpleTestCase, override_settings

from api.bk_base_v4 import default as v4_resources
from api.bk_base_v4.default import (
    CleanGet,
    CleanUpdate,
    DataStorageCreate,
    ResultTable,
    UserDataSourceList,
)


class V4ResourceContractTests(SimpleTestCase):
    def response(self, data):
        response = mock.Mock()
        response.status_code = 200
        response.history = []
        response.json.return_value = {"result": True, "code": "00", "data": data}
        response.raise_for_status.return_value = None
        return response

    @override_settings(
        BK_RESOURCE={
            "PLATFORM_AUTH_ENABLED": True,
            "PLATFORM_AUTH_ACCESS_USERNAME": "platform_user",
            "PLATFORM_AUTH_ACCESS_TOKEN": "fixture_token",
        }
    )
    def test_platform_namespace_scope_uses_platform_identity_and_tenant_header(self):
        cls = getattr(v4_resources, "NamespacesList", None)
        self.assertIsNotNone(cls, "Platform project enumeration must use the existing namespaces protocol")
        resource = cls()
        resource.session.get = mock.Mock(return_value=self.response([]))
        self.assertEqual(resource.request({"tenant": "tenant_a"}), [])
        kwargs = resource.session.get.call_args.kwargs
        self.assertTrue(resource.session.get.call_args.args[0].endswith("/v4/tenants/tenant_a/namespaces"))
        self.assertEqual(kwargs["params"], {})
        self.assertEqual(kwargs["headers"]["X-Bk-Tenant-Id"], "tenant_a")
        auth = json.loads(kwargs["headers"]["x-bkapi-authorization"])
        self.assertEqual(auth["bk_username"], "platform_user")

    def test_personal_namespace_scope_still_requires_authenticated_user(self):
        resource = v4_resources.UserNamespacesList()
        with mock.patch("api.bk_base_v4.default.get_local_request", return_value=None):
            with self.assertRaises(PermissionDenied):
                resource.request({"tenant": "tenant_a"})

    def test_clean_put_preserves_complete_body_and_strips_path(self):
        resource = CleanUpdate()
        payload = {
            "metadata": {"name": "clean_a", "annotations": {"keep": "value"}},
            "spec": {"rules": [], "custom": {"keep": 1}},
            "status": None,
        }
        resource.session.request = mock.Mock(return_value=self.response(payload))
        with mock.patch.object(resource, "build_header", return_value={}):
            result = resource.request({"tenant": "tenant_a", "namespace": "audit", "name": "clean_a", **payload})
        self.assertEqual(result, payload)
        self.assertTrue(
            resource.session.request.call_args.kwargs["url"].endswith(
                "/tenants/tenant_a/namespaces/audit/cleans/clean_a/"
            )
        )
        self.assertEqual(resource.session.request.call_args.kwargs["json"], payload)

    def test_get_requires_name_before_network(self):
        resource = CleanGet()
        resource.session.get = mock.Mock()
        with self.assertRaises(Exception) as caught:
            resource.request({"tenant": "tenant_a", "namespace": "audit"})
        self.assertNotIsInstance(caught.exception, KeyError)
        self.assertIn("name", str(caught.exception).lower())
        resource.session.get.assert_not_called()

    def test_create_does_not_require_path_name(self):
        resource = DataStorageCreate()
        resource.session.request = mock.Mock(return_value=self.response({"metadata": {"name": "s"}, "spec": {}}))
        with mock.patch.object(resource, "build_header", return_value={}):
            resource.request({"tenant": "tenant_a", "namespace": "audit", "metadata": {"name": "s"}, "spec": {}})
        self.assertTrue(resource.session.request.call_args.kwargs["url"].endswith("/datastorages/"))

    def test_metadata_preserves_extra_fields(self):
        resource = ResultTable()
        data = {"result_table_id": "rt_a", "fields": [{"field_name": "x", "extra": True}], "new_field": "value"}
        resource.session.get = mock.Mock(return_value=self.response(data))
        with mock.patch.object(resource, "build_header", return_value={}):
            self.assertEqual(resource.request({"result_table_id": "rt_a", "related": ["fields"]}), data)
        self.assertEqual(resource.session.get.call_args.kwargs["params"], {"related": ["fields"]})

    @override_settings(
        BK_RESOURCE={
            "PLATFORM_AUTH_ENABLED": True,
            "PLATFORM_AUTH_ACCESS_USERNAME": "platform_user",
            "PLATFORM_AUTH_ACCESS_TOKEN": "fixture_token",
        }
    )
    def test_personal_datasource_uses_authenticated_user(self):
        resource = UserDataSourceList()
        request = SimpleNamespace(user=SimpleNamespace(bk_username="user_a", is_authenticated=True), COOKIES={})
        resource.session.get = mock.Mock(return_value=self.response([]))
        with mock.patch.object(resource, "build_auth_args", return_value={"bk_ticket": "user_ticket"}):
            self.assertEqual(resource.request({"tenant": "tenant_a", "namespace": "audit"}, _request=request), [])
        kwargs = resource.session.get.call_args.kwargs
        auth = json.loads(kwargs["headers"]["x-bkapi-authorization"])
        self.assertEqual(auth["bk_username"], "user_a")
        self.assertEqual(auth["bk_ticket"], "user_ticket")
        self.assertNotIn("access_token", auth)
        self.assertEqual(kwargs["params"], {})

    def test_personal_datasource_requires_request(self):
        resource = UserDataSourceList()
        with mock.patch("api.bk_base_v4.default.get_local_request", return_value=None):
            with self.assertRaises(PermissionDenied):
                resource.request({"tenant": "tenant_a", "namespace": "audit"})

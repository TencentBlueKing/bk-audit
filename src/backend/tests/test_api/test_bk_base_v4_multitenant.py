"""Verify final gateway requests without calling the real BKBase or user service."""
import json
from types import SimpleNamespace
from unittest import mock

import requests
from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.test import RequestFactory, SimpleTestCase, override_settings

from api.bk_base_v4 import default as sdk
from services.web.bkbase.common import get_bkbase_context


@override_settings(
    BKPAAS_MULTI_TENANT_MODE=True,
    BK_TENANT_ID="tencent",
    BKBASE_API_VERSION="v4",
    BKBASE_V4_TENANT="tencent",
    BK_BASE_APIGW_NAME="tenant-bkbase",
    APP_CODE="fixture_app",
    SECRET_KEY="fixture_secret",
    BK_RESOURCE={"PLATFORM_AUTH_ENABLED": True, "PLATFORM_AUTH_ACCESS_USERNAME": "", "PLATFORM_AUTH_ACCESS_TOKEN": ""},
)
class V4MultitenantTests(SimpleTestCase):
    def setUp(self):
        self.enterContext(mock.patch("api.utils.APIGW_URL_FORMAT", "https://{api_name}.invalid/{stage}"))
        self.admin = self.enterContext(mock.patch("core.bk_api_base.get_admin_username", return_value="fixture_admin"))

    @staticmethod
    def response(payload):
        response = requests.Response()
        response.status_code = 200
        response._content = json.dumps({"result": True, "code": "00", "data": payload}).encode()
        return response

    def test_platform_list_uses_tenant_admin_without_legacy_credentials(self):
        endpoint = sdk.NamespacesList()
        endpoint.session.get = mock.Mock(return_value=self.response({"results": []}))
        self.assertEqual(endpoint.request(tenant="tencent"), {"results": []})
        url = endpoint.session.get.call_args.args[0]
        sent = endpoint.session.get.call_args.kwargs
        self.assertEqual(url, "https://tenant-bkbase.invalid/prod/v4/tenants/tencent/namespaces")
        self.assertEqual(sent["params"], {})
        self.assertEqual(sent["headers"]["X-Bk-Tenant-Id"], "tencent")
        self.assertNotIn("cookie", sent["headers"])
        self.assertEqual(
            json.loads(sent["headers"]["x-bkapi-authorization"]),
            {"bk_app_code": "fixture_app", "bk_app_secret": "fixture_secret", "bk_username": "fixture_admin"},
        )
        self.admin.assert_called_once_with("tencent")

    def test_personal_dataset_retains_user_credentials_and_strips_tenant_from_query(self):
        endpoint = sdk.UserDatasetList()
        endpoint.session.get = mock.Mock(return_value=self.response({"results": []}))
        request = RequestFactory().get("/fixture/")
        request.user = SimpleNamespace(bk_username="fixture_user", is_authenticated=True, tenant_id="tencent")
        request.COOKIES = {"bk_token": "fixture_user_token"}
        self.assertEqual(endpoint.request(tenant="tencent", namespace="audit", _request=request), {"results": []})
        sent = endpoint.session.get.call_args.kwargs
        self.assertEqual(sent["headers"]["X-Bk-Tenant-Id"], "tencent")
        self.assertNotIn("tenant", sent["params"])
        self.assertEqual(
            json.loads(sent["headers"]["x-bkapi-authorization"]),
            {
                "bk_app_code": "fixture_app",
                "bk_app_secret": "fixture_secret",
                "bk_username": "fixture_user",
                "bk_token": "fixture_user_token",
            },
        )
        self.admin.assert_not_called()

    def test_application_only_check_binds_owner_permission_request_to_instance_tenant(self):
        endpoint = sdk.DirectAuthByResources()
        endpoint.session.request = mock.Mock(return_value=self.response([{"resource_id": "7_test", "allowed": True}]))
        self.assertEqual(
            endpoint.request(user_id="owner", resource_ids=["7_test"]), [{"resource_id": "7_test", "allowed": True}]
        )
        sent = endpoint.session.request.call_args.kwargs
        self.assertEqual(sent["headers"]["X-Bk-Tenant-Id"], "tencent")
        self.assertEqual(sent["json"]["tenant"], "tencent")
        self.assertIsNone(sent["json"]["namespace"])
        self.assertEqual(
            json.loads(sent["headers"]["x-bkapi-authorization"]),
            {"bk_app_code": "fixture_app", "bk_app_secret": "fixture_secret"},
        )
        self.admin.assert_not_called()

    def test_wrong_tenant_rejected_before_http(self):
        for params in (
            {"tenant": "system"},
            {"metadata": {"name": "table", "tenant": "system"}},
            {"spec": {"target": {"kind": "ResultTable", "tenant": "system", "namespace": "other", "name": "table"}}},
        ):
            with self.subTest(params=params):
                endpoint = sdk.DataStorageCreate()
                endpoint.session.request = mock.Mock(return_value=self.response({}))
                with self.assertRaises(PermissionDenied):
                    endpoint.request({"tenant": "tencent", "namespace": "audit", "metadata": {}, "spec": {}, **params})
                endpoint.session.request.assert_not_called()
        self.admin.assert_not_called()

    @override_settings(BKBASE_V4_TENANT="system")
    def test_mismatched_config_stops_context_and_http(self):
        endpoint = sdk.ResultTable()
        endpoint.session.get = mock.Mock()
        for request in (get_bkbase_context, lambda: endpoint.request(result_table_id="7_test")):
            with self.assertRaises(ImproperlyConfigured):
                request()
        endpoint.session.get.assert_not_called()

    @override_settings(
        BK_TENANT_ID="system",
        BKBASE_V4_TENANT="system",
        BK_RESOURCE={
            "PLATFORM_AUTH_ENABLED": True,
            "PLATFORM_AUTH_ACCESS_USERNAME": "legacy_platform",
            "PLATFORM_AUTH_ACCESS_TOKEN": "legacy_token",
        },
    )
    def test_unscoped_platform_endpoint_uses_system_instance_tenant(self):
        endpoint = sdk.ResultTable()
        endpoint.session.get = mock.Mock(return_value=self.response({"result_table_id": "7_test"}))
        self.assertEqual(endpoint.request(result_table_id="7_test"), {"result_table_id": "7_test"})
        headers = endpoint.session.get.call_args.kwargs["headers"]
        self.assertEqual(headers["X-Bk-Tenant-Id"], "system")
        self.assertEqual(
            json.loads(headers["x-bkapi-authorization"]),
            {"bk_app_code": "fixture_app", "bk_app_secret": "fixture_secret", "bk_username": "fixture_admin"},
        )
        self.admin.assert_called_once_with("system")

    def test_personal_credentials_from_another_tenant_are_rejected(self):
        endpoint = sdk.UserNamespacesList()
        endpoint.session.get = mock.Mock()
        request = RequestFactory().get("/fixture/")
        request.user = SimpleNamespace(bk_username="fixture_user", is_authenticated=True, tenant_id="system")
        with self.assertRaises(PermissionDenied):
            endpoint.request(tenant="tencent", _request=request)
        endpoint.session.get.assert_not_called()
        self.admin.assert_not_called()

    @override_settings(
        BKPAAS_MULTI_TENANT_MODE=False,
        BKBASE_V4_TENANT="custom_single",
        BK_RESOURCE={
            "PLATFORM_AUTH_ENABLED": True,
            "PLATFORM_AUTH_ACCESS_USERNAME": "legacy_platform",
            "PLATFORM_AUTH_ACCESS_TOKEN": "legacy_token",
        },
    )
    def test_single_tenant_keeps_explicit_namespace_header_and_legacy_identity(self):
        endpoint = sdk.NamespacesList()
        endpoint.session.get = mock.Mock(return_value=self.response([]))
        self.assertEqual(get_bkbase_context()["tenant"], "custom_single")
        self.assertEqual(endpoint.request(tenant="custom_single"), [])
        self.assertEqual(
            endpoint.session.get.call_args.args[0],
            f"{sdk.BK_BASE_API_URL.rstrip('/')}/v4/tenants/custom_single/namespaces",
        )
        sent = endpoint.session.get.call_args.kwargs
        self.assertEqual(sent["headers"]["X-Bk-Tenant-Id"], "custom_single")
        self.assertEqual(
            json.loads(sent["headers"]["x-bkapi-authorization"]),
            {
                "bk_app_code": "fixture_app",
                "bk_app_secret": "fixture_secret",
                "bk_username": "legacy_platform",
                "access_token": "legacy_token",
            },
        )
        self.admin.assert_not_called()

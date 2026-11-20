"""正式个人项目列表复用真实请求Cookie；业务检查不再调用旧MCP check。"""
import json
from types import SimpleNamespace
from unittest import mock

import requests
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, SimpleTestCase, override_settings

from api.bk_base_v4.default import UserNamespacesList


@override_settings(
    APP_CODE="synthetic_app", SECRET_KEY="synthetic_secret", OAUTH_COOKIES_PARAMS={"bk_token": "bk_token"}
)
class UserCheckProtocolTests(SimpleTestCase):
    def test_formal_project_request_uses_authenticated_cookie_not_spoofed_username(self):
        request = RequestFactory().get("/synthetic/")
        request.user = SimpleNamespace(bk_username="synthetic_user", is_authenticated=True)
        request.COOKIES["bk_token"] = "synthetic-cookie"
        endpoint = UserNamespacesList()
        response = requests.Response()
        response.status_code = 200
        response._content = json.dumps({"result": True, "code": "00", "data": []}).encode()
        with mock.patch.object(endpoint.session, "request", return_value=response) as send:
            self.assertEqual(
                endpoint.request(tenant="tenant_a", _request=request, bk_username="spoofed", _is_backend=True), []
            )
        sent = send.call_args.kwargs
        authorization = json.loads(sent["headers"]["x-bkapi-authorization"])
        self.assertEqual(authorization["bk_username"], "synthetic_user")
        self.assertEqual(authorization["bk_token"], "synthetic-cookie")
        self.assertEqual(sent["headers"]["X-Bk-Tenant-Id"], "tenant_a")
        self.assertTrue((sent.get("url") or send.call_args.args[1]).endswith("/v4/tenants/tenant_a/namespaces"))
        self.assertEqual(sent["params"], {})
        self.assertNotIn("json", sent)
        self.assertFalse(endpoint.platform_authorization)

    def test_anonymous_request_cannot_fall_back_to_platform_authorization(self):
        endpoint = UserNamespacesList()
        with mock.patch("api.bk_base_v4.default.get_local_request", return_value=None), mock.patch.object(
            endpoint.session, "request"
        ) as send:
            with self.assertRaises(PermissionDenied):
                endpoint.request(tenant="tenant_a")
        send.assert_not_called()

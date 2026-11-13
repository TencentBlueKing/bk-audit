"""指定负责人权限接口使用应用认证，并严格校验网关成功与布尔授权协议。"""
import json
from types import SimpleNamespace
from unittest import mock

import requests
from bk_resource.exceptions import APIRequestError, ValidateException
from django.test import RequestFactory, SimpleTestCase, override_settings

from api.bk_base_v4 import default as sdk


@override_settings(APP_CODE="synthetic_app", SECRET_KEY="synthetic_secret")
class OwnerAuthContractTests(SimpleTestCase):
    def endpoint(self, payload):
        endpoint = sdk.DirectAuthByResources()
        response = requests.Response()
        response.status_code = 200
        response._content = json.dumps(payload).encode()
        endpoint.session.request = mock.Mock(return_value=response)
        return endpoint

    @staticmethod
    def success(rows):
        return {"result": True, "code": "00", "data": rows}

    def test_seven_key_request_uses_only_application_authentication(self):
        endpoint = self.endpoint(self.success([{"resource_id": "7_alpha", "allowed": True}]))
        request = RequestFactory().get("/synthetic/")
        request.user = SimpleNamespace(username="caller", is_authenticated=True)
        request.COOKIES = {"bk_token": "synthetic-cookie", "bk_ticket": "synthetic-ticket"}
        with mock.patch("blueapps.utils.request_provider.get_local_request", return_value=request):
            result = endpoint.request(user_id="owner", resource_ids=["7_alpha"], _request=request)
        self.assertEqual(result, [{"resource_id": "7_alpha", "allowed": True}])
        sent = endpoint.session.request.call_args.kwargs
        self.assertTrue(sent["url"].endswith("/v4/auth/users/direct_auth_by_resources/"))
        self.assertEqual(sent["method"], "POST")
        self.assertIs(sent.get("allow_redirects"), False)
        self.assertEqual(
            sent["json"],
            {
                "tenant": None,
                "namespace": None,
                "user_id": "owner",
                "action_id": "query_dataset",
                "resource_ids": ["7_alpha"],
                "parent_resource_type": None,
                "parent_resource_id": None,
            },
        )
        self.assertEqual(
            json.loads(sent["headers"]["x-bkapi-authorization"]),
            {"bk_app_code": "synthetic_app", "bk_app_secret": "synthetic_secret"},
        )
        self.assertNotIn("cookie", sent["headers"])

    def test_explicit_denial_is_a_successful_check(self):
        endpoint = self.endpoint(self.success([{"resource_id": "7_alpha", "allowed": False}]))
        self.assertEqual(
            endpoint.request(user_id="owner", resource_ids=["7_alpha"]),
            [{"resource_id": "7_alpha", "allowed": False}],
        )

    def test_invalid_response_never_coerces_permission_to_true(self):
        for rows in (
            None,
            {},
            [None],
            [{"resource_id": "7_alpha", "allowed": "true"}],
            [{"resource_id": "7_alpha", "allowed": 1}],
            [{"resource_id": "7_alpha"}],
            [{"allowed": True}],
            [{"resource_id": 7, "allowed": True}],
        ):
            with self.subTest(rows=rows):
                endpoint = self.endpoint(self.success(rows))
                with self.assertRaises(ValidateException):
                    endpoint.request(user_id="owner", resource_ids=["7_alpha"])

    def test_only_explicit_success_envelope_is_accepted(self):
        row = {"resource_id": "7_alpha", "allowed": True}
        for payload in (
            [row],
            {"data": [row]},
            {"result": True, "code": "1500319", "data": [row]},
            {"result": "true", "code": "00", "data": [row]},
            {"result": False, "code": "1500319", "data": None},
            {"result": True, "code": "00", "data": [row], "message": "contradictory failure"},
            {"result": True, "code": "00", "data": [row], "errors": {}},
            {"result": True, "code": "00", "data": [row], "messages": {}},
        ):
            with self.subTest(payload=payload):
                endpoint = self.endpoint(payload)
                with self.assertRaises(APIRequestError):
                    endpoint.request(user_id="owner", resource_ids=["7_alpha"])

    def test_invalid_input_is_rejected_before_http(self):
        for params in (
            {"user_id": "", "resource_ids": ["7_alpha"]},
            {"user_id": "owner", "resource_ids": ["7_alpha"], "tenant": ""},
            {"user_id": "owner", "resource_ids": ["7_alpha"], "action_id": "result_table.query_data"},
            {"resource_ids": ["7_alpha"]},
        ):
            with self.subTest(params=params):
                endpoint = self.endpoint(self.success([]))
                with self.assertRaises(ValidateException):
                    endpoint.request(params)
                endpoint.session.request.assert_not_called()

    def test_redirect_cannot_forward_application_credentials_or_authorize(self):
        for status in (301, 302, 307, 308):
            with self.subTest(status=status):
                endpoint = self.endpoint(self.success([{"resource_id": "7_alpha", "allowed": True}]))
                endpoint.session.request.return_value.status_code = status
                endpoint.session.request.return_value.headers["Location"] = "https://other.invalid/auth"
                with self.assertRaises(APIRequestError):
                    endpoint.request(user_id="owner", resource_ids=["7_alpha"])
                self.assertEqual(endpoint.session.request.call_count, 1)
                self.assertIs(endpoint.session.request.call_args.kwargs.get("allow_redirects"), False)

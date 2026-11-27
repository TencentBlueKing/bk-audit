"""Verify the credentials sent by personal and platform resources at the HTTP boundary."""

import json
from types import SimpleNamespace
from unittest import mock

import requests
from blueapps.utils.local import request_local
from django.core.cache import cache
from django.test import RequestFactory, SimpleTestCase, override_settings

from api.bk_base import default as bk_base
from api.bk_log import default as bk_log


@override_settings(
    BKPAAS_MULTI_TENANT_MODE=True,
    BK_TENANT_ID="tencent",
    BK_BASE_APIGW_NAME="tenant-bkbase",
    LOG_APIGW_NAME="tenant-bklog",
    APP_CODE="fixture_app",
    SECRET_KEY="fixture_secret",
    OAUTH_COOKIES_PARAMS={"bk_token": "bk_token"},
    BK_RESOURCE={
        "PLATFORM_AUTH_ENABLED": True,
        "PLATFORM_AUTH_ACCESS_USERNAME": "fixture_legacy",
        "PLATFORM_AUTH_ACCESS_TOKEN": "fixture_legacy_token",
        "LOCAL_CACHE_ENABLE": False,
    },
)
class TestMultitenantPersonalAuth(SimpleTestCase):
    def setUp(self):
        self.enterContext(mock.patch("api.utils.APIGW_URL_FORMAT", "https://{api_name}.invalid/{stage}"))
        # The SDK detects pytest as a background process; these resources are called by web requests.
        self.enterContext(mock.patch("bk_resource.contrib.bk_api.is_backend", return_value=False))
        self.admin_lookup = self.enterContext(
            mock.patch("core.bk_api_base.get_admin_username", return_value="fixture_tenant_admin")
        )
        self.web_request = RequestFactory().get("/audit/")
        self.web_request.user = SimpleNamespace(username="fixture_user", is_authenticated=True)
        self.web_request.COOKIES = {"bk_token": "fixture_user_token"}
        self.enterContext(mock.patch.object(request_local, "request", self.web_request, create=True))

    @staticmethod
    def response(payload):
        response = requests.Response()
        response.status_code = 200
        response._content = json.dumps({"result": True, "code": "00", "data": payload}).encode()
        return response

    def send(self, resource_class, params, payload, **kwargs):
        endpoint = resource_class()
        method = "get" if endpoint.method == "GET" else "request"
        with mock.patch.object(endpoint.session, method, return_value=self.response(payload)) as transport:
            request = getattr(endpoint.request, "cacheless", endpoint.request)
            request(params, **kwargs)
        return transport.call_args.kwargs

    def assert_personal(self, sent, *, multitenant=True):
        self.assertEqual(
            json.loads(sent["headers"]["x-bkapi-authorization"]),
            {
                "bk_app_code": "fixture_app",
                "bk_app_secret": "fixture_secret",
                "bk_username": "fixture_user",
                "bk_token": "fixture_user_token",
            },
        )
        if multitenant:
            self.assertEqual(sent["headers"]["X-Bk-Tenant-Id"], "tencent")
        else:
            self.assertNotIn("X-Bk-Tenant-Id", sent["headers"])

    def test_bkbase_v3_user_resources_do_not_use_platform_identity(self):
        for endpoint, params, payload in (
            (bk_base.GetMyRawdataList, {"page": 1}, {"count": 0, "results": []}),
            (bk_base.GetRawdataDetail, {"bk_data_id": 123}, {"id": 123}),
            (bk_base.GetMineResultTables, {"bk_username": "fixture_user"}, []),
            (bk_base.GetBizsList, {"bk_username": "fixture_user"}, []),
        ):
            with self.subTest(endpoint=endpoint.__name__):
                sent = self.send(endpoint, params, payload)
                self.assert_personal(sent)
                self.assertEqual(sent["params"]["bk_username"], "fixture_user")
        self.admin_lookup.assert_not_called()

    def test_bkbase_v3_retains_current_user_when_bulk_worker_supplies_request(self):
        request_local.request = None
        sent = self.send(bk_base.GetMyRawdataList, {"page": 2}, {"count": 0, "results": []}, _request=self.web_request)
        self.assert_personal(sent)
        self.assertEqual(sent["params"]["bk_username"], "fixture_user")

    def test_bkbase_v3_query_username_matches_gateway_alias(self):
        self.web_request.user.bk_username = "fixture_gateway_user"
        sent = self.send(bk_base.GetMineResultTables, {"bk_username": "fixture_user"}, [])
        auth = json.loads(sent["headers"]["x-bkapi-authorization"])
        self.assertEqual(sent["params"]["bk_username"], "fixture_gateway_user")
        self.assertEqual(auth["bk_username"], "fixture_gateway_user")

    def test_bkbase_v3_personal_request_with_no_user_does_not_fill_platform_username(self):
        request_local.request = None
        sent = self.send(bk_base.GetRawdataDetail, {"bk_data_id": 123}, {"id": 123})
        self.assertNotIn("bk_username", sent["params"])
        self.assertNotIn("bk_username", json.loads(sent["headers"]["x-bkapi-authorization"]))

    def test_bklog_user_lists_and_permissions_use_current_user(self):
        for endpoint, params, payload in (
            (bk_log.BizsList, {}, []),
            (bk_log.GetSpacesMine, {}, []),
            (
                bk_log.CheckAllowed,
                {"action_ids": ["view_collection"]},
                [{"action_id": "view_collection", "is_allowed": False}],
            ),
            (
                bk_log.GetApplyData,
                {"action_ids": ["view_collection"]},
                {"apply_data": {}, "apply_url": "https://iam.invalid/"},
            ),
        ):
            with self.subTest(endpoint=endpoint.__name__):
                self.assert_personal(self.send(endpoint, params, payload))
        self.admin_lookup.assert_not_called()

    @override_settings(
        CACHES={
            "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "bklog-personal-test"}
        }
    )
    def test_bklog_spaces_does_not_reuse_a_result_from_before_personal_auth(self):
        with mock.patch("bk_resource.utils.cache.mem_cache", cache):
            # The old multitenant resource used the same cache key as single-tenant mode.
            with override_settings(BKPAAS_MULTI_TENANT_MODE=False):
                legacy = bk_log.GetSpacesMine()
                with mock.patch.object(legacy.session, "get", return_value=self.response([{"space_id": "old_scope"}])):
                    self.assertEqual(legacy.request(), [{"space_id": "old_scope"}])

            current = bk_log.GetSpacesMine()
            with mock.patch.object(current.session, "get", return_value=self.response([{"space_id": "my_space"}])):
                self.assertEqual(current.request(), [{"space_id": "my_space"}])

    def test_bkbase_v3_and_bklog_platform_resources_keep_admin_identity(self):
        for endpoint, payload in ((bk_base.GetResultTables, []), (bk_log.GetStorages, [])):
            with self.subTest(endpoint=endpoint.__name__):
                sent = self.send(endpoint, {}, payload)
                auth = json.loads(sent["headers"]["x-bkapi-authorization"])
                self.assertEqual(sent["headers"]["X-Bk-Tenant-Id"], "tencent")
                self.assertEqual(auth["bk_username"], "fixture_tenant_admin")
                self.assertNotIn("access_token", auth)

    def test_explicit_bkbase_v3_non_admin_resource_uses_personal_identity(self):
        # 多租户下不论 platform_authorization 取值，只要 use_admin_username=False
        # 即视为用户态，以真实登录用户身份发起，不借用旧平台凭据；用户态保留
        # build_auth_args 注入的鉴权参数（含 cookie 中的 access_token），不做 pop。
        sent = self.send(bk_base.DatabusCleansDelete, {"processing_id": "audit_clean"}, None)
        auth = json.loads(sent["headers"]["x-bkapi-authorization"])
        self.assertEqual(sent["headers"]["X-Bk-Tenant-Id"], "tencent")
        self.assertEqual(auth["bk_username"], "fixture_user")
        self.assertEqual(auth["bk_token"], "fixture_user_token")
        # 用户态不使用租户管理员身份
        self.admin_lookup.assert_not_called()

    @override_settings(BKPAAS_MULTI_TENANT_MODE=False)
    def test_single_tenant_keeps_legacy_header_and_bkbase_query(self):
        sent = self.send(bk_base.GetMyRawdataList, {"page": 1}, {"count": 0, "results": []})
        self.assert_personal(sent, multitenant=False)
        self.assertEqual(sent["params"]["bk_username"], "fixture_legacy")
        self.assert_personal(self.send(bk_log.BizsList, {}, []), multitenant=False)
        self.admin_lookup.assert_not_called()

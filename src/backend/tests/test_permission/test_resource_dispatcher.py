# -*- coding: utf-8 -*-
import base64
import json
from unittest import mock

from django.core.cache.backends.locmem import LocMemCache
from django.test import RequestFactory, SimpleTestCase, override_settings
from iam.resource.provider import ListResult, ResourceProvider
from requests import Request
from requests.exceptions import ConnectionError

from apps.permission.dispatcher import BkAuditResourceApiDispatcher
from apps.permission.handlers.service import PermissionService

from .test_iam_v4_model_client import reply

IAM_GATEWAY = "https://gateway.example.test/bkiam/prod"
IAM_TOKEN = "fake-callback-token"
IAM_AUTH = "Basic " + base64.b64encode(f"bk_iam:{IAM_TOKEN}".encode()).decode()


class FakeResourceProvider(ResourceProvider):
    def __init__(self):
        self.list_pages = []
        self.search_pages = []
        self.search_filters = []
        self.fetch_filters = []

    def list_attr(self, **options):
        return ListResult(results=[], count=0)

    def list_attr_value(self, filters, page, **options):
        return ListResult(results=[], count=0)

    def list_instance(self, filters, page, **options):
        self.list_pages.append(page)
        return ListResult(
            results=[{"id": str(index), "display_name": f"scene-{index}"} for index in range(page.limit or 1)],
            count=100,
        )

    def fetch_instance_info(self, filters, **options):
        self.fetch_filters.append(filters)
        return ListResult(
            results=[{"id": resource_id, "display_name": f"scene-{resource_id}"} for resource_id in filters.ids],
            count=len(filters.ids),
        )

    def list_instance_by_policy(self, filters, page, **options):
        return ListResult(results=[], count=0)

    def search_instance(self, filters, page, **options):
        self.search_pages.append(page)
        return ListResult(
            results=[{"id": "matched", "display_name": filters.keyword}],
            count=1,
        )

    def filter_search_instance_results(self, parent_id, resource_type, keyword, page):
        self.search_filters.append(
            {
                "parent_id": parent_id,
                "resource_type": resource_type,
                "keyword": keyword,
                "page": page,
            }
        )
        return [{"id": "filtered", "display_name": keyword}], 1


@override_settings(
    IAM_PERMISSION_BACKEND="v3",
    APP_CODE="audit-app",
    SECRET_KEY="fake-application-secret",
    BKPAAS_MULTI_TENANT_MODE=False,
)
class TestBkAuditResourceApiDispatcher(SimpleTestCase):
    def setUp(self):
        self.enterContext(mock.patch("api.bk_iam_v4.default.BK_IAM_V4_API_URL", IAM_GATEWAY))
        self.get_legacy_client = self.enterContext(
            mock.patch("apps.permission.handlers.permission.Permission.get_iam_client")
        )
        token_cache = LocMemCache("iam-v4-resource-callback", {})
        token_cache.clear()
        self.addCleanup(token_cache.clear)
        self.gateway = self.enterContext(mock.patch("requests.session")).return_value
        self.gateway.get.return_value = reply(
            200, {"data": {"system_info": {"id": "bk-audit", "auth_token": IAM_TOKEN}}}
        )

    def make_dispatcher(self, legacy=None):
        self.get_legacy_client.return_value = legacy
        return BkAuditResourceApiDispatcher(PermissionService(), "bk-audit")

    @override_settings(
        IAM_PERMISSION_BACKEND="v4",
        BKPAAS_MULTI_TENANT_MODE=True,
        BK_TENANT_ID="tencent",
        SYSTEM_TENANT_ID="global-test",
    )
    def test_v4_lookup_uses_system_header_and_app_credentials(self):
        dispatcher = self.make_dispatcher()
        dispatcher.register("scene", FakeResourceProvider())
        response = dispatcher._dispatch(self.callback_request(IAM_AUTH, tenant_id="tencent"))

        self.assertEqual(response.status_code, 200)
        self.get_legacy_client.assert_not_called()
        self.gateway.get.assert_called_once()
        args, kwargs = self.gateway.get.call_args
        self.assertEqual(args, (IAM_GATEWAY + "/api/v1/open/rabc/share/model/systems/bk-audit/",))
        self.assertEqual(kwargs["params"], {"fields": "system_info"})
        self.assertFalse(kwargs["allow_redirects"])
        self.assertTrue(kwargs["verify"])
        self.assertEqual(kwargs["headers"]["X-Bk-Tenant-Id"], "global-test")
        self.assertEqual(
            json.loads(kwargs["headers"]["X-Bkapi-Authorization"]),
            {"bk_app_code": "audit-app", "bk_app_secret": "fake-application-secret"},
        )

    @override_settings(
        IAM_PERMISSION_BACKEND="v4",
        BK_IAM_V4_SYSTEM_DETAIL_ACTION="/api/v1/open/rbac/share/model/systems/{system_id}/",
    )
    def test_v4_callback_credential_lookup_uses_configured_system_detail_path(self):
        dispatcher = self.make_dispatcher()
        dispatcher.register("scene", FakeResourceProvider())

        response = dispatcher._dispatch(self.callback_request(IAM_AUTH))

        self.assertEqual(response.status_code, 200)
        self.gateway.get.assert_called_once()
        self.assertEqual(
            self.gateway.get.call_args.args, (IAM_GATEWAY + "/api/v1/open/rbac/share/model/systems/bk-audit/",)
        )

    @override_settings(IAM_PERMISSION_BACKEND="v4")
    def test_v4_single_tenant_uses_default_scope_and_reuses_token(self):
        dispatcher = self.make_dispatcher()
        dispatcher.register("scene", FakeResourceProvider())
        for _ in range(2):
            self.assertEqual(dispatcher._dispatch(self.callback_request(IAM_AUTH)).status_code, 200)
        self.gateway.get.assert_called_once()
        self.assertNotIn("X-Bk-Tenant-Id", self.gateway.get.call_args.kwargs["headers"])

    @override_settings(IAM_PERMISSION_BACKEND="v4")
    def test_v4_token_lookup_failure_blocks_resources_without_legacy_fallback(self):
        provider = FakeResourceProvider()
        dispatcher = self.make_dispatcher()
        dispatcher.register("scene", provider)
        unavailable = reply(503, {"data": {}})
        unavailable.request = Request("GET", IAM_GATEWAY).prepare()
        for upstream in (
            ConnectionError("test gateway unavailable"),
            unavailable,
            reply(200),
            reply(200, {"data": {"system_info": {"auth_token": ""}}}),
        ):
            with self.subTest(upstream=upstream):
                self.gateway.get.side_effect = [upstream]
                response = dispatcher._dispatch(self.callback_request(IAM_AUTH))
                self.assertEqual(response.status_code, 503)
                self.assertEqual(json.loads(response.content)["error"]["code"], "503")
                self.assertEqual(provider.list_pages, [])
        self.get_legacy_client.assert_not_called()

    @override_settings(IAM_PERMISSION_BACKEND="v4")
    def test_v4_lookup_retains_gateway_error_details_in_internal_logs(self):
        self.gateway.get.return_value = reply(
            403,
            {"error": {"code": "FORBIDDEN", "message": "application not authorized"}},
        )
        dispatcher = self.make_dispatcher()
        with self.assertLogs("app", level="ERROR") as logs:
            response = dispatcher._dispatch(self.callback_request(IAM_AUTH))

        self.assertEqual(response.status_code, 503)
        self.assertNotContains(response, "application not authorized", status_code=503)
        self.assertIn("application not authorized", "\n".join(logs.output))

    @override_settings(IAM_PERMISSION_BACKEND="v4")
    def test_v4_wrong_token_is_rejected_without_logging_credentials(self):
        dispatcher = self.make_dispatcher()
        supplied = "Basic " + base64.b64encode(b"bk_iam:fake-wrong-token").decode()
        with self.assertLogs("app", level="ERROR") as logs:
            response = dispatcher._dispatch(self.callback_request(supplied))
        self.assertEqual(response.status_code, 401)
        self.assertNotIn(supplied, "\n".join(logs.output))
        self.assertNotIn(IAM_TOKEN, "\n".join(logs.output))

    def callback_request(self, auth, **kwargs):
        return RequestFactory().post(
            "/api/v1/iam/resources/",
            data=json.dumps({"method": "list_instance", "type": "scene", "page": {"page": 1, "page_size": 1}}),
            content_type="application/json",
            HTTP_AUTHORIZATION=auth,
            HTTP_X_BK_TENANT_ID=kwargs.get("tenant_id", ""),
        )

    def test_dispatch_v3_backend_accepts_resource_type_id_with_v3_envelope(self):
        iam_client = mock.MagicMock()
        iam_client.is_basic_auth_allowed.return_value = True
        provider = FakeResourceProvider()
        provider.list_instance = mock.Mock(wraps=provider.list_instance)
        dispatcher = self.make_dispatcher(iam_client)
        dispatcher.register("scene", provider)

        request = RequestFactory().post(
            "/api/v1/iam/resources/",
            data=json.dumps(
                {
                    "method": "list_instance",
                    "resource_type_id": "scene",
                    "filter": {},
                    "page": {"page": 2, "page_size": 10},
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=IAM_AUTH,
            HTTP_X_REQUEST_ID="request-id",
        )

        response = dispatcher._dispatch(request)

        self.assertEqual(response.status_code, 200)
        iam_client.is_basic_auth_allowed.assert_called_once()
        self.gateway.get.assert_not_called()
        provider.list_instance.assert_called_once()
        data = json.loads(response.content)
        self.assertEqual(data["code"], 0)
        self.assertTrue(data["result"])
        self.assertEqual(data["data"]["count"], 100)
        self.assertEqual(data["data"]["results"][0]["id"], "0")

    def test_dispatch_v3_invalid_json_uses_v3_envelope(self):
        iam_client = mock.MagicMock()
        iam_client.is_basic_auth_allowed.return_value = True
        dispatcher = self.make_dispatcher(iam_client)

        request = RequestFactory().post(
            "/api/v1/iam/resources/",
            data="{",
            content_type="application/json",
            HTTP_AUTHORIZATION=IAM_AUTH,
            HTTP_X_REQUEST_ID="request-id",
        )

        response = dispatcher._dispatch(request)

        data = json.loads(response.content)
        self.assertEqual(data["code"], 400)
        self.assertFalse(data["result"])
        self.assertEqual(data["message"], "reqeust body is not a valid json")

    @override_settings(IAM_PERMISSION_BACKEND="v4")
    def test_dispatch_v4_invalid_json_uses_error_envelope(self):
        dispatcher = self.make_dispatcher()

        request = RequestFactory().post(
            "/api/v1/iam/resources/",
            data="{",
            content_type="application/json",
            HTTP_AUTHORIZATION=IAM_AUTH,
            HTTP_X_REQUEST_ID="request-id",
        )

        response = dispatcher._dispatch(request)

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertEqual(set(data.keys()), {"error"})
        self.assertEqual(data["error"]["code"], "400")
        self.assertEqual(data["error"]["message"], "reqeust body is not a valid json")

    @override_settings(IAM_PERMISSION_BACKEND="v4")
    def test_dispatch_v4_missing_method_or_resource_type_uses_error_envelope(self):
        dispatcher = self.make_dispatcher()

        request = RequestFactory().post(
            "/api/v1/iam/resources/",
            data=json.dumps({"filter": {}, "page": {"page": 1, "page_size": 20}}),
            content_type="application/json",
            HTTP_AUTHORIZATION=IAM_AUTH,
            HTTP_X_REQUEST_ID="request-id",
        )

        response = dispatcher._dispatch(request)

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertEqual(set(data.keys()), {"error"})
        self.assertEqual(data["error"]["code"], "400")
        self.assertEqual(data["error"]["message"], "method and resource type is required field")

    @override_settings(IAM_PERMISSION_BACKEND="v4")
    def test_dispatch_v4_page_size_uses_v4_envelope_and_page_offset(self):
        provider = FakeResourceProvider()
        dispatcher = self.make_dispatcher()
        dispatcher.register("scene", provider)

        request = RequestFactory().post(
            "/api/v1/iam/resources/",
            data=json.dumps(
                {
                    "type": "scene",
                    "method": "list_instance",
                    "filter": {},
                    "page": {"page": 2, "page_size": 25},
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=IAM_AUTH,
            HTTP_X_REQUEST_ID="request-id",
        )

        response = dispatcher._dispatch(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-Request-Id"], "request-id")
        data = json.loads(response.content)
        self.assertEqual(set(data.keys()), {"data"})
        self.assertEqual(len(data["data"]["results"]), 25)
        self.assertEqual(provider.list_pages[0].limit, 25)
        self.assertEqual(provider.list_pages[0].offset, 25)

    @override_settings(IAM_PERMISSION_BACKEND="v4")
    def test_dispatch_v3_limit_offset_uses_v4_envelope_when_backend_is_v4(self):
        provider = FakeResourceProvider()
        dispatcher = self.make_dispatcher()
        dispatcher.register("scene", provider)

        request = RequestFactory().post(
            "/api/v1/iam/resources/",
            data=json.dumps(
                {
                    "type": "scene",
                    "method": "list_instance",
                    "filter": {},
                    "page": {"limit": 10, "offset": 20},
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=IAM_AUTH,
            HTTP_X_REQUEST_ID="request-id",
        )

        response = dispatcher._dispatch(request)

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(set(data.keys()), {"data"})
        self.assertEqual(data["data"]["count"], 100)
        self.assertEqual(provider.list_pages[0].limit, 10)
        self.assertEqual(provider.list_pages[0].offset, 20)

    @override_settings(IAM_PERMISSION_BACKEND="v4")
    def test_dispatch_v4_list_instance_keyword_uses_search_instance(self):
        provider = FakeResourceProvider()
        provider.list_instance = mock.Mock(wraps=provider.list_instance)
        provider.search_instance = mock.Mock(wraps=provider.search_instance)
        provider.filter_search_instance_results = None
        dispatcher = self.make_dispatcher()
        dispatcher.register("scene", provider)

        request = RequestFactory().post(
            "/api/v1/iam/resources/",
            data=json.dumps(
                {
                    "type": "scene",
                    "method": "list_instance",
                    "filter": {"keyword": "a"},
                    "page": {"page": 1, "page_size": 20},
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=IAM_AUTH,
            HTTP_X_REQUEST_ID="request-id",
        )

        response = dispatcher._dispatch(request)

        self.assertEqual(response.status_code, 200)
        provider.list_instance.assert_not_called()
        provider.search_instance.assert_called_once()
        data = json.loads(response.content)
        self.assertEqual(data["data"]["results"][0]["display_name"], "a")

    @override_settings(IAM_PERMISSION_BACKEND="v4")
    def test_dispatch_v4_list_instance_parent_keyword_preserves_parent_filter(self):
        provider = FakeResourceProvider()
        provider.search_instance = mock.Mock(wraps=provider.search_instance)
        dispatcher = self.make_dispatcher()
        dispatcher.register("scene", provider)

        request = RequestFactory().post(
            "/api/v1/iam/resources/",
            data=json.dumps(
                {
                    "type": "scene",
                    "method": "list_instance",
                    "filter": {"parent": {"type": "system", "id": "bk-audit"}, "keyword": "a"},
                    "page": {"page": 1, "page_size": 20},
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=IAM_AUTH,
            HTTP_X_REQUEST_ID="request-id",
        )

        response = dispatcher._dispatch(request)

        self.assertEqual(response.status_code, 200)
        provider.search_instance.assert_not_called()
        self.assertEqual(provider.search_filters[0]["parent_id"], "bk-audit")
        self.assertEqual(provider.search_filters[0]["resource_type"], "system")
        self.assertEqual(provider.search_filters[0]["keyword"], "a")

    @override_settings(IAM_PERMISSION_BACKEND="v4")
    def test_dispatch_v4_invalid_page_uses_error_envelope(self):
        provider = FakeResourceProvider()
        dispatcher = self.make_dispatcher()
        dispatcher.register("scene", provider)

        request = RequestFactory().post(
            "/api/v1/iam/resources/",
            data=json.dumps(
                {
                    "type": "scene",
                    "method": "list_instance",
                    "filter": {},
                    "page": {"page": "bad", "page_size": 20},
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=IAM_AUTH,
            HTTP_X_REQUEST_ID="request-id",
        )

        response = dispatcher._dispatch(request)

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertEqual(set(data.keys()), {"error"})
        self.assertEqual(data["error"]["code"], "400")

    @override_settings(IAM_PERMISSION_BACKEND="v4")
    def test_dispatch_v4_page_size_zero_uses_error_envelope(self):
        provider = FakeResourceProvider()
        dispatcher = self.make_dispatcher()
        dispatcher.register("scene", provider)

        request = RequestFactory().post(
            "/api/v1/iam/resources/",
            data=json.dumps(
                {
                    "type": "scene",
                    "method": "list_instance",
                    "filter": {},
                    "page": {"page": 1, "page_size": 0},
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=IAM_AUTH,
            HTTP_X_REQUEST_ID="request-id",
        )

        response = dispatcher._dispatch(request)

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertEqual(set(data.keys()), {"error"})
        self.assertEqual(data["error"]["code"], "400")

    @override_settings(IAM_PERMISSION_BACKEND="v4")
    def test_dispatch_v4_fetch_instance_info_maps_requires_to_attrs(self):
        provider = FakeResourceProvider()
        dispatcher = self.make_dispatcher()
        dispatcher.register("scene", provider)

        request = RequestFactory().post(
            "/api/v1/iam/resources/",
            data=json.dumps(
                {
                    "type": "scene",
                    "method": "fetch_instance_info",
                    "filter": {"ids": ["1"]},
                    "requires": ["display_name"],
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=IAM_AUTH,
            HTTP_X_REQUEST_ID="request-id",
        )

        response = dispatcher._dispatch(request)

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(set(data.keys()), {"data"})
        self.assertEqual(data["data"][0]["display_name"], "scene-1")
        self.assertEqual(provider.fetch_filters[0].attrs, ["display_name"])

    @override_settings(IAM_PERMISSION_BACKEND="v4")
    def test_dispatch_fetch_instance_info_uses_v4_envelope_when_backend_is_v4(self):
        provider = FakeResourceProvider()
        dispatcher = self.make_dispatcher()
        dispatcher.register("scene", provider)

        request = RequestFactory().post(
            "/api/v1/iam/resources/",
            data=json.dumps(
                {
                    "type": "scene",
                    "method": "fetch_instance_info",
                    "filter": {"ids": ["1"]},
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=IAM_AUTH,
            HTTP_X_REQUEST_ID="request-id",
        )

        response = dispatcher._dispatch(request)

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(set(data.keys()), {"data"})
        self.assertEqual(data["data"][0]["display_name"], "scene-1")

    @override_settings(IAM_PERMISSION_BACKEND="v4")
    def test_dispatch_v4_failure_uses_error_envelope(self):
        dispatcher = self.make_dispatcher()

        request = RequestFactory().post(
            "/api/v1/iam/resources/",
            data=json.dumps(
                {
                    "type": "unknown",
                    "method": "list_instance",
                    "filter": {},
                    "page": {"page": 1, "page_size": 20},
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=IAM_AUTH,
            HTTP_X_REQUEST_ID="request-id",
        )

        response = dispatcher._dispatch(request)

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response["X-Request-Id"], "request-id")
        data = json.loads(response.content)
        self.assertEqual(set(data.keys()), {"error"})
        self.assertEqual(data["error"]["code"], "404")
        self.assertEqual(data["error"]["message"], "unsupported resource type: unknown")

    def test_dispatch_v3_auth_failure_uses_v3_envelope(self):
        iam_client = mock.MagicMock()
        iam_client.is_basic_auth_allowed.return_value = False
        provider = FakeResourceProvider()
        dispatcher = self.make_dispatcher(iam_client)
        dispatcher.register("scene", provider)

        request = RequestFactory().post(
            "/api/v1/iam/resources/",
            data=json.dumps(
                {
                    "type": "scene",
                    "method": "list_instance",
                    "filter": {},
                    "page": {"limit": 10, "offset": 0},
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION="bad-token",
            HTTP_X_REQUEST_ID="request-id",
        )

        response = dispatcher._dispatch(request)

        data = json.loads(response.content)
        self.assertEqual(data["code"], 401)
        self.assertFalse(data["result"])
        self.assertEqual(data["message"], "basic auth failed")

    @override_settings(IAM_PERMISSION_BACKEND="v4")
    def test_dispatch_v4_auth_failure_uses_error_envelope(self):
        provider = FakeResourceProvider()
        dispatcher = self.make_dispatcher()
        dispatcher.register("scene", provider)

        request = RequestFactory().post(
            "/api/v1/iam/resources/",
            data=json.dumps(
                {
                    "type": "scene",
                    "method": "list_instance",
                    "filter": {},
                    "page": {"page": 1, "page_size": 20},
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION="bad-token",
            HTTP_X_REQUEST_ID="request-id",
        )

        response = dispatcher._dispatch(request)

        self.assertEqual(response.status_code, 401)
        data = json.loads(response.content)
        self.assertEqual(set(data.keys()), {"error"})
        self.assertEqual(data["error"]["code"], "401")
        self.assertEqual(data["error"]["message"], "basic auth failed")
        self.get_legacy_client.assert_not_called()
        self.gateway.get.assert_not_called()

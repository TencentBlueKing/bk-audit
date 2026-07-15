# -*- coding: utf-8 -*-
import json
from unittest import mock

from django.test import RequestFactory, SimpleTestCase, override_settings
from iam.resource.provider import ListResult, ResourceProvider

from apps.permission.dispatcher import BkAuditResourceApiDispatcher


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


class TestBkAuditResourceApiDispatcher(SimpleTestCase):
    def test_dispatch_v3_backend_accepts_resource_type_id_with_v3_envelope(self):
        iam_client = mock.MagicMock()
        iam_client.is_basic_auth_allowed.return_value = True
        provider = FakeResourceProvider()
        provider.list_instance = mock.Mock(wraps=provider.list_instance)
        dispatcher = BkAuditResourceApiDispatcher(iam_client, "bk-audit")
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
            HTTP_AUTHORIZATION="basic-token",
            HTTP_X_REQUEST_ID="request-id",
        )

        response = dispatcher._dispatch(request)

        self.assertEqual(response.status_code, 200)
        provider.list_instance.assert_called_once()
        data = json.loads(response.content)
        self.assertEqual(data["code"], 0)
        self.assertTrue(data["result"])
        self.assertEqual(data["data"]["count"], 100)
        self.assertEqual(data["data"]["results"][0]["id"], "0")

    def test_dispatch_v3_invalid_json_uses_v3_envelope(self):
        iam_client = mock.MagicMock()
        iam_client.is_basic_auth_allowed.return_value = True
        dispatcher = BkAuditResourceApiDispatcher(iam_client, "bk-audit")

        request = RequestFactory().post(
            "/api/v1/iam/resources/",
            data="{",
            content_type="application/json",
            HTTP_AUTHORIZATION="basic-token",
            HTTP_X_REQUEST_ID="request-id",
        )

        response = dispatcher._dispatch(request)

        data = json.loads(response.content)
        self.assertEqual(data["code"], 400)
        self.assertFalse(data["result"])
        self.assertEqual(data["message"], "reqeust body is not a valid json")

    @override_settings(IAM_PERMISSION_BACKEND="v4")
    def test_dispatch_v4_invalid_json_uses_error_envelope(self):
        iam_client = mock.MagicMock()
        iam_client.is_basic_auth_allowed.return_value = True
        dispatcher = BkAuditResourceApiDispatcher(iam_client, "bk-audit")

        request = RequestFactory().post(
            "/api/v1/iam/resources/",
            data="{",
            content_type="application/json",
            HTTP_AUTHORIZATION="basic-token",
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
        iam_client = mock.MagicMock()
        iam_client.is_basic_auth_allowed.return_value = True
        dispatcher = BkAuditResourceApiDispatcher(iam_client, "bk-audit")

        request = RequestFactory().post(
            "/api/v1/iam/resources/",
            data=json.dumps({"filter": {}, "page": {"page": 1, "page_size": 20}}),
            content_type="application/json",
            HTTP_AUTHORIZATION="basic-token",
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
        iam_client = mock.MagicMock()
        iam_client.is_basic_auth_allowed.return_value = True
        provider = FakeResourceProvider()
        dispatcher = BkAuditResourceApiDispatcher(iam_client, "bk-audit")
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
            HTTP_AUTHORIZATION="basic-token",
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
        iam_client = mock.MagicMock()
        iam_client.is_basic_auth_allowed.return_value = True
        provider = FakeResourceProvider()
        dispatcher = BkAuditResourceApiDispatcher(iam_client, "bk-audit")
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
            HTTP_AUTHORIZATION="basic-token",
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
        iam_client = mock.MagicMock()
        iam_client.is_basic_auth_allowed.return_value = True
        provider = FakeResourceProvider()
        provider.list_instance = mock.Mock(wraps=provider.list_instance)
        provider.search_instance = mock.Mock(wraps=provider.search_instance)
        provider.filter_search_instance_results = None
        dispatcher = BkAuditResourceApiDispatcher(iam_client, "bk-audit")
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
            HTTP_AUTHORIZATION="basic-token",
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
        iam_client = mock.MagicMock()
        iam_client.is_basic_auth_allowed.return_value = True
        provider = FakeResourceProvider()
        provider.search_instance = mock.Mock(wraps=provider.search_instance)
        dispatcher = BkAuditResourceApiDispatcher(iam_client, "bk-audit")
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
            HTTP_AUTHORIZATION="basic-token",
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
        iam_client = mock.MagicMock()
        iam_client.is_basic_auth_allowed.return_value = True
        provider = FakeResourceProvider()
        dispatcher = BkAuditResourceApiDispatcher(iam_client, "bk-audit")
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
            HTTP_AUTHORIZATION="basic-token",
            HTTP_X_REQUEST_ID="request-id",
        )

        response = dispatcher._dispatch(request)

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertEqual(set(data.keys()), {"error"})
        self.assertEqual(data["error"]["code"], "400")

    @override_settings(IAM_PERMISSION_BACKEND="v4")
    def test_dispatch_v4_page_size_zero_uses_error_envelope(self):
        iam_client = mock.MagicMock()
        iam_client.is_basic_auth_allowed.return_value = True
        provider = FakeResourceProvider()
        dispatcher = BkAuditResourceApiDispatcher(iam_client, "bk-audit")
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
            HTTP_AUTHORIZATION="basic-token",
            HTTP_X_REQUEST_ID="request-id",
        )

        response = dispatcher._dispatch(request)

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertEqual(set(data.keys()), {"error"})
        self.assertEqual(data["error"]["code"], "400")

    @override_settings(IAM_PERMISSION_BACKEND="v4")
    def test_dispatch_v4_fetch_instance_info_maps_requires_to_attrs(self):
        iam_client = mock.MagicMock()
        iam_client.is_basic_auth_allowed.return_value = True
        provider = FakeResourceProvider()
        dispatcher = BkAuditResourceApiDispatcher(iam_client, "bk-audit")
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
            HTTP_AUTHORIZATION="basic-token",
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
        iam_client = mock.MagicMock()
        iam_client.is_basic_auth_allowed.return_value = True
        provider = FakeResourceProvider()
        dispatcher = BkAuditResourceApiDispatcher(iam_client, "bk-audit")
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
            HTTP_AUTHORIZATION="basic-token",
            HTTP_X_REQUEST_ID="request-id",
        )

        response = dispatcher._dispatch(request)

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(set(data.keys()), {"data"})
        self.assertEqual(data["data"][0]["display_name"], "scene-1")

    @override_settings(IAM_PERMISSION_BACKEND="v4")
    def test_dispatch_v4_failure_uses_error_envelope(self):
        iam_client = mock.MagicMock()
        iam_client.is_basic_auth_allowed.return_value = True
        dispatcher = BkAuditResourceApiDispatcher(iam_client, "bk-audit")

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
            HTTP_AUTHORIZATION="basic-token",
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
        dispatcher = BkAuditResourceApiDispatcher(iam_client, "bk-audit")
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
        iam_client = mock.MagicMock()
        iam_client.is_basic_auth_allowed.return_value = False
        provider = FakeResourceProvider()
        dispatcher = BkAuditResourceApiDispatcher(iam_client, "bk-audit")
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

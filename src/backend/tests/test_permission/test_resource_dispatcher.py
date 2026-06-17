# -*- coding: utf-8 -*-
import json
from unittest import mock

from django.test import RequestFactory, SimpleTestCase
from iam.resource.provider import ListResult, ResourceProvider

from apps.permission.dispatcher import BkAuditResourceApiDispatcher


class FakeResourceProvider(ResourceProvider):
    def list_attr(self, **options):
        return ListResult(results=[], count=0)

    def list_attr_value(self, filters, page, **options):
        return ListResult(results=[], count=0)

    def list_instance(self, filters, page, **options):
        return ListResult(
            results=[{"id": "1", "display_name": "scene"}],
            count=1,
        )

    def fetch_instance_info(self, filters, **options):
        return ListResult(results=[], count=0)

    def list_instance_by_policy(self, filters, page, **options):
        return ListResult(results=[], count=0)

    def search_instance(self, filters, page, **options):
        return ListResult(results=[], count=0)


class TestBkAuditResourceApiDispatcher(SimpleTestCase):
    def test_dispatch_accepts_v4_resource_type_id(self):
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
                    "page": {"limit": 10, "offset": 0},
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
        self.assertEqual(data["data"]["count"], 1)
        self.assertEqual(data["data"]["results"][0]["id"], "1")

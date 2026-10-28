"""验证V4用户态Query真实请求/响应序列化边界。"""
import json
from unittest import mock

from django.test import SimpleTestCase, override_settings

from api.bk_base_v4.default import QuerySyncResource


class V4QueryContractTests(SimpleTestCase):
    def test_empty_page_allows_null_result_schema_without_inventing_rows_or_count(self):
        resource = QuerySyncResource()
        response = mock.Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "result": True,
            "code": "00",
            "data": {"list": [], "result_schema": None, "select_fields_order": [], "total_records": 0},
        }
        resource.session.request = mock.Mock(return_value=response)
        with mock.patch.object(resource, "build_header", return_value={}):
            self.assertEqual(
                resource.request({"sql": "SELECT * FROM sample LIMIT 1 OFFSET 1"}),
                {"list": [], "select_fields_order": [], "total_records": 0},
            )

    @mock.patch.object(QuerySyncResource, "build_header", return_value={})
    def test_query_payload_and_response(self, _header):
        resource = QuerySyncResource()
        response = mock.Mock()
        response.json.return_value = {
            "result": True,
            "code": "00",
            "data": {
                "list": [{"count": "100"}],
                "total_records": 1,
                "select_fields_order": ["count"],
                "timetaken": 0.1,
            },
        }
        response.raise_for_status.return_value = None
        response.request.url = "https://gateway.test/query"
        resource.session.request = mock.Mock(return_value=response)
        result = resource.request({"sql": "SELECT COUNT(*)", "prefer_storage": "doris"})
        self.assertEqual(
            result, {"list": [{"count": "100"}], "total_records": 1, "select_fields_order": ["count"], "timetaken": 0.1}
        )
        kwargs = resource.session.request.call_args.kwargs
        self.assertTrue(kwargs["url"].endswith("/v4/queryengine/user/query_sync/"))
        self.assertEqual(
            kwargs["json"],
            {"sql": "SELECT COUNT(*)", "prefer_storage": "doris", "bkdata_authentication_method": "user"},
        )
        self.assertEqual(kwargs["timeout"], 300)

        resource.request({"sql": "SELECT COUNT(*)", "prefer_storage": "doris", "request_timeout": 2.5})
        kwargs = resource.session.request.call_args.kwargs
        self.assertEqual(kwargs["timeout"].total, 2.5)
        self.assertNotIn("request_timeout", kwargs["json"])

    @override_settings(
        BK_RESOURCE={
            "PLATFORM_AUTH_ENABLED": True,
            "PLATFORM_AUTH_ACCESS_USERNAME": "platform_user",
            "PLATFORM_AUTH_ACCESS_TOKEN": "fixture_token",
        }
    )
    def test_platform_identity_is_in_authorization_header(self):
        resource = QuerySyncResource()
        response = mock.Mock()
        response.json.return_value = {"result": True, "code": "00", "data": {"list": []}}
        response.raise_for_status.return_value = None
        resource.session.request = mock.Mock(return_value=response)
        self.assertEqual(resource.request({"sql": "SELECT 1"}), {"list": []})
        auth = json.loads(resource.session.request.call_args.kwargs["headers"]["x-bkapi-authorization"])
        self.assertEqual(auth["bk_username"], "platform_user")
        self.assertEqual(auth["access_token"], "fixture_token")
        self.assertEqual(
            resource.session.request.call_args.kwargs["json"],
            {"sql": "SELECT 1", "bkdata_authentication_method": "user"},
        )

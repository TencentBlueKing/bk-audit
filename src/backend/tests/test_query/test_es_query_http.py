"""旧 ES 检索的 HTTP 响应契约。"""

import json
from types import SimpleNamespace
from unittest import mock

from bk_resource import resource
from bk_resource.exceptions import APIRequestError
from blueapps.utils.local import request_local
from django.test import SimpleTestCase
from django.urls import resolve
from django.utils import translation
from requests import Request, Response
from requests.exceptions import Timeout
from rest_framework.test import APIRequestFactory, force_authenticate

from api.bk_log.default import EsQuerySearchResource
from apps.meta.permissions import SearchLogPermission
from core.exceptions import PermissionException
from core.log import JsonLogFormatter
from services.web.common.constants import ScopeType


class TestEsQueryHTTP(SimpleTestCase):
    base_path = "/api/v1/query/namespaces/test-ns/es_query/"
    request_id = "audit-request-1"
    trace_id = "audit-trace-1"
    upstream_marker = "synthetic-bklog-error"
    detail_marker = "synthetic-bklog-detail"
    public_message = "日志查询失败。请核对查询条件，或提供请求 ID 联系管理员。"

    def setUp(self):
        self.http = self.enterContext(mock.patch("requests.sessions.Session.request"))
        self.permissions = self.enterContext(
            mock.patch.object(SearchLogPermission, "get_scope_auth_systems", return_value=["test-system"])
        )
        self.enterContext(mock.patch.object(resource.query.search.__class__, "_bk_audit_client"))
        self.enterContext(mock.patch.object(request_local, "request_id", self.request_id, create=True))
        self.enterContext(translation.override("zh-hans"))

    def get(self, action="search", **params):
        path = f"{self.base_path}{action}/"
        match = resolve(path)
        request = APIRequestFactory().get(path, params)
        request.user = SimpleNamespace(username="test-user", is_authenticated=True)
        request.otel_trace_id = self.trace_id
        force_authenticate(request, user=request.user)
        with mock.patch.object(request_local, "request", request, create=True):
            return match.func(request, **match.kwargs).render()

    def search(self, **overrides):
        params = {
            "start_time": "2026-01-01 00:00:00",
            "end_time": "2026-01-02 00:00:00",
            "query_string": "sample",
            "page": 1,
            "page_size": 5,
            "index_set_id": 1,
            "storage_cluster_id": 1,
            "scope_type": ScopeType.CROSS_SYSTEM,
            "bind_system_info": "false",
        }
        return self.get(**(params | overrides))

    def upstream_response(self, payload, status_code=200):
        response = Response()
        response.status_code = status_code
        response.request = Request("POST", "https://bklog.example.invalid/esquery_search/").prepare()
        response.url = response.request.url
        response._content = json.dumps(payload).encode()
        return response

    def assert_controlled_error(self, response):
        self.assertEqual(response.status_code, 500)
        self.assertNotIn(self.upstream_marker.encode(), response.content)
        self.assertNotIn(self.detail_marker.encode(), response.content)
        self.assertNotIn(b"bklog.example.invalid", response.content)
        self.assertEqual(
            json.loads(response.content),
            {
                "result": False,
                "code": 500,
                "message": self.public_message,
                "request_id": self.request_id,
                "trace_id": self.trace_id,
                "data": None,
                "errors": None,
            },
        )

    def test_bklog_business_failure_only_returns_controlled_error(self):
        self.http.return_value = self.upstream_response(
            {
                "result": False,
                "code": 1234,
                "message": self.upstream_marker,
                "data": {"details": [{"message": self.detail_marker}]},
            }
        )
        with self.assertLogs("app", level="ERROR") as errors:
            response = self.search()

        self.assert_controlled_error(response)
        self.http.assert_called_once()
        record = next(record for record in errors.records if self.upstream_marker in record.getMessage())
        log = JsonLogFormatter().json_record(record.getMessage(), {}, record)
        self.assertEqual(log["request_id"], json.loads(response.content)["request_id"])

    def test_bklog_http_failure_only_returns_controlled_error(self):
        self.http.return_value = self.upstream_response(
            {"code": 1234, "message": f"{self.upstream_marker} at https://bklog.example.invalid"}, status_code=502
        )

        self.assert_controlled_error(self.search())
        self.http.assert_called_once()

    def test_bklog_network_failure_only_returns_controlled_error(self):
        self.http.side_effect = Timeout(self.detail_marker)

        self.assert_controlled_error(self.search())
        self.http.assert_called_once()

    def test_search_preserves_query_and_authorized_system_filter(self):
        self.http.return_value = self.upstream_response({"result": True, "code": 0, "data": {"hits": {"total": 0}}})
        self.enterContext(mock.patch.object(resource.query.search.__class__, "parse_data", return_value=[]))

        for query in ("sample", "message:sample*"):
            with self.subTest(query=query):
                response = self.search(query_string=query)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    json.loads(response.content)["data"],
                    {"page": 1, "num_pages": 5, "total": 0, "results": [], "scroll_id": None},
                )
                sent_data = self.http.call_args.kwargs["json"]
                self.assertEqual(sent_data["query_string"], query)
                self.assertIn(
                    {
                        "field": "system_id",
                        "operator": "is one of",
                        "value": ["test-system"],
                        "condition": "and",
                        "type": "field",
                    },
                    sent_data["filter"],
                )

    def test_permission_denial_preserves_apply_data(self):
        self.permissions.side_effect = PermissionException(
            action_name="查询日志", permission={"actions": []}, apply_url="https://iam.example.invalid"
        )

        response = self.search()

        self.assertEqual(response.status_code, 403)
        payload = json.loads(response.content)
        self.assertEqual(payload["code"], "9900403")
        self.assertEqual(payload["data"], {"permission": {"actions": []}, "apply_url": "https://iam.example.invalid"})
        self.http.assert_not_called()

    def test_invalid_params_return_validation_error(self):
        response = self.search(page="invalid")

        self.assertEqual(response.status_code, 400)
        self.assertIn("page", json.loads(response.content)["message"].lower())
        self.http.assert_not_called()

    def test_search_does_not_rewrite_errors_from_other_calls(self):
        other_calls = (
            ("permission-service", EsQuerySearchResource.action),
            (EsQuerySearchResource.module_name, "/search_index_set/operators/"),
        )
        for module_name, url in other_calls:
            with self.subTest(module_name=module_name, url=url):
                self.permissions.side_effect = APIRequestError(
                    module_name=module_name, url=url, result="dependency lookup failed"
                )
                self.assertEqual(json.loads(self.search().content)["message"], "dependency lookup failed")
        self.http.assert_not_called()

    def test_other_action_does_not_rewrite_bklog_error(self):
        error = APIRequestError(
            module_name=EsQuerySearchResource.module_name,
            url=EsQuerySearchResource.action,
            result="field map lookup failed",
        )
        with mock.patch.object(resource.query.field_map.__class__, "perform_request", side_effect=error):
            response = self.get("field_map", fields="system_id")

        self.assertEqual(json.loads(response.content)["message"], "field map lookup failed")
        self.http.assert_not_called()

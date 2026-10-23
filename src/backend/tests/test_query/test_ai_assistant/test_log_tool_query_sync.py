# -*- coding: utf-8 -*-
"""日志工具 QuerySync 诊断信息保留测试。"""

from unittest import mock

from bk_resource.exceptions import APIRequestError
from django.test import SimpleTestCase
from requests.exceptions import HTTPError

from api.bk_base.default import SafeQuerySyncResource
from core.observability import _run_with_api_resource_span
from services.web.query.ai_assistant.exceptions import LogQueryTimeout
from services.web.query.ai_assistant.log_tools.errors import map_log_query_error
from services.web.query.resources.doris import CollectorSearchAllResource


class TestSafeQuerySyncResource(SimpleTestCase):
    """远端错误正文需保留在日志、异常和 OTel 状态中供排障。"""

    sentinel = "SELECT secret_value FROM audit WHERE token='raw-condition'"

    def _response(self, *, payload, http_error=None):
        response = mock.MagicMock()
        response.json.return_value = payload
        response.content = self.sentinel.encode()
        response.status_code = 502
        response.headers = {"x-bkapi-request-id": "request-123"}
        if isinstance(http_error, HTTPError):
            http_error.response = response
        response.raise_for_status.side_effect = http_error
        return response

    def test_success_keeps_query_sync_data_contract(self):
        resource = SafeQuerySyncResource()
        response = self._response(payload={"result": True, "code": 0, "data": {"list": [{"count": 1}]}})

        self.assertEqual(resource.parse_response(response), {"list": [{"count": 1}]})

    def test_request_timeout_reaches_http_without_leaking_into_next_request(self):
        """单次查询预算只控制本次连接/读取超时，不发送给BKBase或修改共享实例。"""
        resource = SafeQuerySyncResource()
        response = self._response(payload={"result": True, "code": 0, "data": {"list": []}})
        with mock.patch.object(resource.session, "request", return_value=response) as request:
            resource.request(sql="SELECT 1", request_timeout=2)
            first = request.call_args.kwargs
            self.assertEqual(first["timeout"].total, 2)
            self.assertNotIn("request_timeout", first["json"])
            resource.request(sql="SELECT 2")
            self.assertEqual(request.call_args.kwargs["timeout"], 300)

    def test_collector_budget_reaches_both_http_queries(self):
        """经过真实Collector及BKBase两层serializer后，两条并发查询都受预算约束。"""
        collector = CollectorSearchAllResource()
        response = self._response(payload={"result": True, "code": 0, "data": {"list": [{"count": 0}]}})
        with (
            mock.patch.object(collector, "build_sql", return_value={"data": "SELECT 1", "count": "SELECT 0"}),
            mock.patch.object(collector, "parse_data", return_value=[]),
            mock.patch("requests.sessions.Session.request", return_value=response) as http,
        ):
            result = collector.request(
                namespace="default",
                start_time="2026-09-19T10:00:00+08:00",
                end_time="2026-09-20T10:00:00+08:00",
                page=1,
                page_size=1,
                bind_system_info=False,
                conditions=[],
                query_timeout=2,
            )
        self.assertEqual(result["total"], 0)
        self.assertEqual(len(http.call_args_list), 2)
        for call in http.call_args_list:
            self.assertEqual(call.kwargs["timeout"].total, 2)
            self.assertNotIn("request_timeout", call.kwargs["json"])

    def test_resource_collection_stays_enabled(self):
        self.assertTrue(SafeQuerySyncResource.support_data_collect)

    def test_client_logs_sql(self):
        resource = SafeQuerySyncResource()
        response = self._response(payload={"result": True, "code": 0, "data": {"list": []}})
        with (
            mock.patch.object(resource.session, "request", return_value=response),
            mock.patch("api.bk_base.default.logger.info") as info,
        ):
            self.assertEqual(resource.request(sql=self.sentinel, prefer_storage="doris"), {"list": []})

        info.assert_any_call("[SafeQuerySyncResource] SQL => %s", self.sentinel)

    def test_remote_failure_body_is_kept_in_exception_logs_and_span_status(self):
        resource = SafeQuerySyncResource()
        response = self._response(
            payload={"result": False, "code": "1500200", "message": self.sentinel, "data": self.sentinel}
        )
        span = mock.Mock()
        span.is_recording.return_value = True
        span_context = mock.MagicMock()
        span_context.__enter__.return_value = span
        tracer = mock.Mock()
        tracer.start_as_current_span.return_value = span_context

        with mock.patch("core.observability.trace.get_tracer", return_value=tracer), mock.patch(
            "bk_resource.contrib.api.logger"
        ) as resource_logger:
            with self.assertRaises(APIRequestError) as raised:
                _run_with_api_resource_span(resource, lambda: resource.parse_response(response))

        self.assertIn(self.sentinel, str(raised.exception))
        self.assertIn(self.sentinel, str(raised.exception.data))
        self.assertIn(self.sentinel, str(resource_logger.error.call_args_list))
        statuses = [call.args[0] for call in span.set_status.call_args_list]
        self.assertTrue(statuses)
        self.assertTrue(any(self.sentinel in (status.description or "") for status in statuses))

    def test_http_and_nonstandard_responses_keep_remote_error_body(self):
        resource = SafeQuerySyncResource()
        cases = (
            self._response(payload={"message": self.sentinel}, http_error=HTTPError("bad gateway")),
            self._response(payload=[self.sentinel]),
        )

        for response in cases:
            with self.subTest(response=response):
                with self.assertRaises(APIRequestError) as raised:
                    resource.parse_response(response)
                self.assertIn(self.sentinel, str(raised.exception))

    def test_http_timeout_status_is_mapped_to_log_query_timeout(self):
        resource = SafeQuerySyncResource()
        for status_code in (408, 504):
            response = self._response(
                payload={"result": False, "message": self.sentinel},
                http_error=HTTPError("remote timeout"),
            )
            response.status_code = status_code
            with self.subTest(status_code=status_code), self.assertRaises(APIRequestError) as raised:
                resource.parse_response(response)

            self.assertIsInstance(map_log_query_error(raised.exception), LogQueryTimeout)

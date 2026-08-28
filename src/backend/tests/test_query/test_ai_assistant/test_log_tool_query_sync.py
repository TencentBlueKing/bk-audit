# -*- coding: utf-8 -*-
"""日志工具 QuerySync 响应隔离测试。"""

from unittest import mock

from bk_resource.exceptions import APIRequestError
from django.test import SimpleTestCase
from requests.exceptions import HTTPError

from core.observability import _run_with_api_resource_span
from services.web.query.ai_assistant.log_tools.query_sync import SafeQuerySyncResource


class TestSafeQuerySyncResource(SimpleTestCase):
    """远端错误正文不得进入日志、异常或 OTel 状态描述。"""

    sentinel = "SELECT secret_value FROM audit WHERE token='raw-condition'"

    def _response(self, *, payload, http_error=None):
        response = mock.MagicMock()
        response.json.return_value = payload
        response.content = self.sentinel.encode()
        response.status_code = 502
        response.headers = {"x-bkapi-request-id": "request-123"}
        response.raise_for_status.side_effect = http_error
        return response

    def test_success_keeps_query_sync_data_contract(self):
        resource = SafeQuerySyncResource()
        response = self._response(payload={"result": True, "code": 0, "data": {"list": [{"count": 1}]}})

        self.assertEqual(resource.parse_response(response), {"list": [{"count": 1}]})

    def test_client_call_does_not_emit_sdk_request_log_with_sql(self):
        resource = SafeQuerySyncResource()
        with mock.patch.object(SafeQuerySyncResource, "request", return_value={"list": []}), mock.patch(
            "bk_resource.base.bk_resource_settings.REQUEST_LOG_HANDLER"
        ) as request_log_handler:
            self.assertEqual(resource(sql=self.sentinel, prefer_storage="doris"), {"list": []})

        request_log_handler.assert_not_called()

    def test_remote_failure_body_is_absent_from_exception_logs_and_span_status(self):
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

        self.assertNotIn(self.sentinel, str(raised.exception))
        self.assertNotIn(self.sentinel, repr(raised.exception.data))
        resource_logger.error.assert_not_called()
        resource_logger.exception.assert_not_called()
        statuses = [call.args[0] for call in span.set_status.call_args_list]
        self.assertTrue(statuses)
        self.assertTrue(all(self.sentinel not in str(status) for status in statuses))

    def test_http_and_nonstandard_responses_raise_generic_api_error(self):
        resource = SafeQuerySyncResource()
        cases = (
            self._response(payload={"message": self.sentinel}, http_error=HTTPError("bad gateway")),
            self._response(payload=[self.sentinel]),
        )

        for response in cases:
            with self.subTest(response=response):
                with self.assertRaises(APIRequestError) as raised:
                    resource.parse_response(response)
                self.assertNotIn(self.sentinel, str(raised.exception))
                self.assertNotIn(self.sentinel, repr(raised.exception.data))

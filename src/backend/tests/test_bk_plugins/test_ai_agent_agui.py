# -*- coding: utf-8 -*-
"""AG-UI 专用流式资源的协议与兼容性测试。"""

import json
import logging
from contextlib import contextmanager
from unittest import mock

from bk_resource import api
from bk_resource.exceptions import APIRequestError
from django.test import override_settings
from requests.exceptions import HTTPError

from api.bk_plugins_ai_agent.agui import AGUIStreamResponse
from api.bk_plugins_ai_agent.default import AGUIChatCompletion, ChatCompletion
from api.bk_plugins_ai_agent.exceptions import (
    AGUIStreamCapacityExceeded,
    AGUIStreamProtocolError,
)
from tests.base import TestCase


def build_sse_response(events):
    """构造只包含 AG-UI data 帧的 HTTP 流响应。"""
    response = mock.MagicMock()
    response.status_code = 200
    response.headers = {"Content-Type": "text/event-stream"}
    response.raise_for_status.return_value = None
    response.iter_lines.return_value = ["data: " + json.dumps(event, ensure_ascii=False) for event in events]
    return response


def build_complete_events(content="hello", result=None):
    return [
        {"type": "RUN_STARTED", "threadId": "t1", "runId": "r1"},
        {"type": "TEXT_MESSAGE_START", "messageId": "m1", "role": "assistant"},
        {"type": "TEXT_MESSAGE_CONTENT", "messageId": "m1", "delta": content},
        {"type": "TEXT_MESSAGE_END", "messageId": "m1"},
        {"type": "RUN_FINISHED", "threadId": "t1", "runId": "r1", "result": result},
    ]


@contextmanager
def capture_named_logs(*logger_names):
    """捕获实际应用与 bk_resource logger 的记录，供敏感信息断言。"""
    handler = _LogCaptureHandler()
    loggers = [logging.getLogger(name) for name in logger_names]
    original_levels = [logger.level for logger in loggers]
    for logger in loggers:
        logger.setLevel(logging.DEBUG)
        logger.addHandler(handler)
    try:
        yield handler.records
    finally:
        for logger, level in zip(loggers, original_levels):
            logger.removeHandler(handler)
            logger.setLevel(level)


@contextmanager
def patch_public_resource_request(resource, response):
    """临时替换缓存 Resource 的 HTTP 调用，退出时由 patch 恢复单例状态。"""
    with mock.patch.object(resource.session, "request", return_value=response) as request:
        yield request


class _LogCaptureHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record)


class TestAGUIChatCompletion(TestCase):
    """验证 AG-UI 事件协议、资源隔离和旧接口兼容性。"""

    def setUp(self):
        self.resource = AGUIChatCompletion()
        self.public_agui_resource = api.bk_plugins_ai_agent.agui_chat_completion
        self.public_legacy_resource = api.bk_plugins_ai_agent.chat_completion
        self._public_session_request_attributes = {
            "agui": "request" in vars(self.public_agui_resource.session),
            "legacy": "request" in vars(self.public_legacy_resource.session),
        }

    def tearDown(self):
        self.assertEqual(
            "request" in vars(self.public_agui_resource.session),
            self._public_session_request_attributes["agui"],
        )
        self.assertEqual(
            "request" in vars(self.public_legacy_resource.session),
            self._public_session_request_attributes["legacy"],
        )

    @staticmethod
    def _public_request_payload(on_event, input_text="request-input"):
        return {
            "agent_code": "bp-ai-aud-rsk-srch",
            "user": "alice",
            "input": input_text,
            "chat_history": [],
            "execute_kwargs": {"stream": True},
            "on_event": on_event,
        }

    def test_returns_ordered_events_and_final_result(self):
        seen = []
        events = build_complete_events(result={"ok": True})

        result = self.resource._parse_agui_stream_response(build_sse_response(events), on_event=seen.append)

        self.assertEqual(result.final_content, "hello")
        self.assertEqual(result.final_result, {"ok": True})
        self.assertEqual(list(result.events), seen)

    def test_run_error_is_delivered_before_protocol_error(self):
        seen = []
        event = {"type": "RUN_ERROR", "message": "upstream failed"}

        with self.assertRaises(AGUIStreamProtocolError):
            self.resource._parse_agui_stream_response(build_sse_response([event]), on_event=seen.append)

        self.assertEqual(seen, [event])

    def test_http_error_is_not_converted_to_stream_result(self):
        response = build_sse_response([])
        response.raise_for_status.side_effect = HTTPError("bad gateway")

        with self.assertRaises(HTTPError):
            self.resource.parse_response(response)

    def test_rejects_stream_without_run_finished(self):
        with self.assertRaises(AGUIStreamProtocolError):
            self.resource._parse_agui_stream_response(build_sse_response(build_complete_events()[:-1]))

    def test_rejects_unclosed_assistant_message(self):
        events = build_complete_events()
        del events[3]

        with self.assertRaises(AGUIStreamProtocolError):
            self.resource._parse_agui_stream_response(build_sse_response(events))

    def test_rejects_empty_final_assistant_message(self):
        with self.assertRaises(AGUIStreamProtocolError):
            self.resource._parse_agui_stream_response(build_sse_response(build_complete_events(content="   ")))

    def test_rejects_non_json_event(self):
        response = build_sse_response([])
        response.iter_lines.return_value = ["data: not-json"]

        with self.assertRaises(AGUIStreamProtocolError):
            self.resource._parse_agui_stream_response(response)

    @override_settings(AI_ASSISTANT_STREAM_MAX_EVENTS=4)
    def test_rejects_event_count_over_platform_limit(self):
        with self.assertRaises(AGUIStreamCapacityExceeded):
            self.resource._parse_agui_stream_response(build_sse_response(build_complete_events()))

    def test_accepts_event_count_at_platform_limit(self):
        events = build_complete_events()
        with override_settings(AI_ASSISTANT_STREAM_MAX_EVENTS=len(events)):
            result = self.resource._parse_agui_stream_response(build_sse_response(events))

        self.assertEqual(result.final_content, "hello")

    def test_rejects_serialized_events_over_platform_limit(self):
        events = build_complete_events()
        serialized_size = len(json.dumps(events, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        with override_settings(AI_ASSISTANT_STREAM_ARCHIVE_MAX_BYTES=serialized_size - 1):
            with self.assertRaises(AGUIStreamCapacityExceeded):
                self.resource._parse_agui_stream_response(build_sse_response(events))

    def test_accepts_serialized_events_at_platform_limit(self):
        events = build_complete_events()
        serialized_size = len(json.dumps(events, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        with override_settings(AI_ASSISTANT_STREAM_ARCHIVE_MAX_BYTES=serialized_size):
            result = self.resource._parse_agui_stream_response(build_sse_response(events))

        self.assertEqual(result.final_content, "hello")

    def test_perform_request_keeps_callback_in_context_local_scope(self):
        callback = mock.Mock()
        with mock.patch.object(
            ChatCompletion,
            "perform_request",
            side_effect=lambda request_data: AGUIChatCompletion._on_event_context.get(),
        ):
            result = self.resource.perform_request({"on_event": callback})

        self.assertIs(result, callback)
        self.assertIsNone(AGUIChatCompletion._on_event_context.get())

    def test_public_request_returns_events_uses_header_and_preserves_callback_payload(self):
        seen = []
        events = build_complete_events(result={"ok": True})
        response = build_sse_response(events)
        resource = self.public_agui_resource
        payload = self._public_request_payload(seen.append)
        original_payload = dict(payload)

        with patch_public_resource_request(resource, response) as request:
            result = resource.request(payload)

        self.assertIsInstance(resource, AGUIChatCompletion)
        self.assertIsInstance(result, AGUIStreamResponse)
        self.assertEqual(result.final_content, "hello")
        self.assertEqual(result.final_result, {"ok": True})
        self.assertEqual(seen, events)
        self.assertEqual(payload, original_payload)
        self.assertIsNone(AGUIChatCompletion._on_event_context.get())
        request_kwargs = request.call_args.kwargs
        self.assertEqual(request_kwargs["headers"]["X-BKAIDEV-USER"], "alice")
        self.assertNotIn("user", request_kwargs["json"])
        self.assertNotIn("on_event", request_kwargs["json"])

    def test_public_legacy_chat_completion_keeps_string_contract(self):
        resource = self.public_legacy_resource
        payload = self._public_request_payload(mock.Mock())
        payload.pop("on_event")

        with patch_public_resource_request(resource, build_sse_response(build_complete_events())):
            result = resource.request(payload)

        self.assertIsInstance(resource, ChatCompletion)
        self.assertIsInstance(result, str)
        self.assertEqual(result, "hello")

    def test_public_request_does_not_log_sensitive_event_or_http_bodies(self):
        secret_delta = "secret-final-content"
        secret_args = '{"password":"secret-tool-args"}'
        secret_input = "secret-request-input"
        secret_http_body = "secret-http-body"
        events = build_complete_events(content=secret_delta)
        events.insert(1, {"type": "TOOL_CALL_ARGS", "toolCallId": "c1", "delta": secret_args})
        response = build_sse_response(events)
        response.request.body = secret_http_body.encode("utf-8")
        resource = self.public_agui_resource

        with patch_public_resource_request(resource, response):
            with capture_named_logs("app", "bk_resource") as records:
                resource.request(self._public_request_payload(mock.Mock(), input_text=secret_input))

        messages = [record.getMessage() for record in records]
        for secret in (secret_input, secret_delta, secret_args, secret_http_body):
            self.assertFalse(any(secret in message for message in messages), secret)

    def test_public_request_logs_real_agent_code_without_sensitive_payload(self):
        secret_input = "SECRET_REQUEST_INPUT"
        secret_history = "SECRET_CHAT_HISTORY"
        resource = self.public_agui_resource
        payload = self._public_request_payload(mock.Mock(), input_text=secret_input)
        payload["chat_history"] = [{"role": "user", "content": secret_history}]

        with patch_public_resource_request(resource, build_sse_response(build_complete_events())):
            with capture_named_logs("app", "bk_resource") as records:
                resource.request(payload)

        messages = [record.getMessage() for record in records]
        self.assertTrue(any("agent_code=bp-ai-aud-rsk-srch" in message for message in messages))
        for secret in (secret_input, secret_history):
            self.assertFalse(any(secret in message for message in messages))

    def test_parse_response_logs_success_metadata_without_business_body(self):
        secret_content = "SECRET_FINAL_CONTENT"
        response = build_sse_response(build_complete_events(content=secret_content))

        with capture_named_logs("app") as records:
            result = self.resource.parse_response(response)

        messages = [record.getMessage() for record in records]
        self.assertEqual(result.final_content, secret_content)
        self.assertTrue(any("status_code=200" in message and "stream_response=True" in message for message in messages))
        self.assertTrue(
            any(
                "event_count=5" in message and f"final_content_size={len(secret_content)}" in message
                for message in messages
            )
        )
        self.assertFalse(any(secret_content in message for message in messages))

    def test_parse_response_logs_http_error_metadata_without_business_body(self):
        secret_body = "SECRET_HTTP_ERROR_BODY"
        response = build_sse_response([])
        response.status_code = 502
        response.content = secret_body.encode()
        response.raise_for_status.side_effect = HTTPError("bad gateway", response=response)

        with capture_named_logs("app") as records:
            with self.assertRaises(HTTPError):
                self.resource.parse_response(response)

        messages = [record.getMessage() for record in records]
        self.assertTrue(any("status_code=502" in message and "stream_response=True" in message for message in messages))
        self.assertFalse(any(secret_body in message for message in messages))

    def test_parse_response_logs_run_error_metadata_without_business_body(self):
        secret_error = "SECRET_RUN_ERROR_BODY"
        response = build_sse_response([{"type": "RUN_ERROR", "message": secret_error}])

        with capture_named_logs("app") as records:
            with self.assertRaises(AGUIStreamProtocolError):
                self.resource.parse_response(response)

        messages = [record.getMessage() for record in records]
        self.assertTrue(any("status_code=200" in message and "stream_response=True" in message for message in messages))
        self.assertFalse(any(secret_error in message for message in messages))

    def test_public_agui_request_restores_session_after_protocol_error(self):
        response = build_sse_response([{"type": "RUN_ERROR", "message": "upstream failed"}])

        with patch_public_resource_request(self.public_agui_resource, response):
            with self.assertRaises(AGUIStreamProtocolError):
                self.public_agui_resource.request(self._public_request_payload(mock.Mock()))

    def test_public_legacy_request_restores_session_after_stream_error(self):
        response = build_sse_response([{"type": "RUN_ERROR", "message": "upstream failed"}])
        payload = self._public_request_payload(mock.Mock())
        payload.pop("on_event")

        with patch_public_resource_request(self.public_legacy_resource, response):
            with self.assertRaises(APIRequestError):
                self.public_legacy_resource.request(payload)

    def test_existing_chat_completion_still_returns_string(self):
        response = build_sse_response(build_complete_events())

        result = ChatCompletion()._parse_stream_response(response)

        self.assertIsInstance(result, str)
        self.assertEqual(result, "hello")

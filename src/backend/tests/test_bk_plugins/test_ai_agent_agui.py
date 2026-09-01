# -*- coding: utf-8 -*-
"""ChatCompletion 回调模式的传输、资源隔离与旧接口兼容性测试。"""

import io
import json
import logging
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

import requests
from bk_resource import api
from bk_resource.exceptions import APIRequestError, IAMNoPermission
from django.test import SimpleTestCase
from requests.exceptions import HTTPError
from urllib3.response import HTTPResponse

from api.bk_plugins_ai_agent.default import AIAgentBase, ChatCompletion
from api.bk_plugins_ai_agent.exceptions import AGUIStreamProtocolError


def build_sse_response(events):
    """构造只包含 AG-UI data 帧的 HTTP 流响应。"""
    response = mock.MagicMock()
    response.status_code = 200
    response.headers = {"Content-Type": "text/event-stream"}
    response.raise_for_status.return_value = None
    lines = ["data: " + json.dumps(event, ensure_ascii=False) for event in events]
    response.iter_lines.return_value = lines
    return response


def build_json_response(payload, *, status_code=200):
    """构造 Agent 未按流式约定返回的 JSON 响应。"""

    response = mock.MagicMock()
    response.status_code = status_code
    response.headers = {"Content-Type": "application/json"}
    response.json.return_value = payload
    if 400 <= status_code < 600:
        response.raise_for_status.side_effect = HTTPError("agent request failed", response=response)
    else:
        response.raise_for_status.return_value = None
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


class TestAGUIBufferedHTTP(SimpleTestCase):
    """真实 socket 验证两种传输形态，不要求小事件在缓冲填满前交付。"""

    def test_events_are_complete_after_upstream_closes(self):
        for chunked in (False, True):
            with self.subTest(chunked=chunked):
                sent, release = threading.Event(), threading.Event()
                events = [
                    {"type": "TOOL_CALL_START", "toolCallId": "local-http-test"},
                    {"type": "TEXT_MESSAGE_CONTENT", "delta": "x" * 2048},
                    {"type": "RUN_FINISHED"},
                ]
                seen, errors = [], []

                class Handler(BaseHTTPRequestHandler):
                    protocol_version = "HTTP/1.1"

                    def do_GET(self):  # noqa: N802
                        self.send_response(200)
                        self.send_header("Content-Type", "text/event-stream")
                        self.send_header(
                            "Transfer-Encoding" if chunked else "Connection", "chunked" if chunked else "close"
                        )
                        self.end_headers()
                        for index, event in enumerate(events):
                            frame = f"data: {json.dumps(event)}\n\n".encode()
                            if chunked:
                                self.wfile.write(f"{len(frame):X}\r\n".encode() + frame + b"\r\n")
                            else:
                                self.wfile.write(frame)
                            self.wfile.flush()
                            if index == 0:
                                sent.set()
                                release.wait(5)
                        if chunked:
                            self.wfile.write(b"0\r\n\r\n")
                            self.wfile.flush()
                        self.close_connection = True

                    def log_message(self, *args):
                        pass

                server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
                server_thread = threading.Thread(target=server.serve_forever, daemon=True)

                def read():
                    try:
                        with requests.Session() as session:
                            session.trust_env = False
                            with session.get(
                                f"http://127.0.0.1:{server.server_port}/", stream=True, timeout=5
                            ) as response:

                                ChatCompletion()._relay_stream_response(response, seen.append)
                    except Exception as error:
                        errors.append(error)

                reader = threading.Thread(target=read, daemon=True)
                server_thread.start()
                reader.start()
                try:
                    self.assertTrue(sent.wait(3), "测试上游尚未发送事件")
                finally:
                    release.set()
                    reader.join(6)
                    server.shutdown()
                    server.server_close()
                    server_thread.join(3)
                self.assertFalse(reader.is_alive())
                self.assertFalse(server_thread.is_alive())
                self.assertEqual(errors, [])
                # 首帧允许缓冲，大帧允许跨读取块；EOF 时尾部小事件也不能遗漏。
                self.assertEqual(seen, events)


class TestChatCompletionRelay(SimpleTestCase):
    """验证 AG-UI 事件协议、资源隔离和旧接口兼容性。"""

    def setUp(self):
        self.resource = ChatCompletion()
        self.public_agui_resource = api.bk_plugins_ai_agent.chat_completion
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

    def relay(self, response, on_event=None):
        return self.resource._relay_stream_response(response, on_event if on_event is not None else mock.Mock())

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

    def test_relays_all_events_without_returning_duplicate_result(self):
        seen = []
        events = [
            {"type": "RUN_FINISHED", "result": {"ok": True}},
            {"custom": "event without AG-UI lifecycle fields"},
            {"type": "RUN_ERROR", "message": "business decides how to handle this"},
        ]

        result = self.relay(build_sse_response(events), on_event=seen.append)

        self.assertIsNone(result)
        self.assertEqual(seen, events)

    def test_run_error_is_a_business_event_and_does_not_stop_transport(self):
        seen = []
        events = [
            {"type": "RUN_ERROR", "message": "upstream failed"},
            {"type": "STATE_SNAPSHOT", "snapshot": {"retrying": True}},
        ]

        result = self.relay(build_sse_response(events), on_event=seen.append)

        self.assertEqual(seen, events)
        self.assertIsNone(result)

    def test_does_not_enforce_run_or_message_lifecycle(self):
        seen = []
        events = [
            {"type": "TEXT_MESSAGE_START", "messageId": "early", "role": "assistant"},
            {"type": "TEXT_MESSAGE_CONTENT", "messageId": "early", "delta": "premature"},
            {"type": "RUN_FINISHED"},
        ]

        result = self.relay(build_sse_response(events), on_event=seen.append)

        self.assertEqual(seen, events)
        self.assertIsNone(result)

    def test_http_error_is_not_converted_to_stream_result(self):
        response = build_sse_response([])
        response.raise_for_status.side_effect = HTTPError("bad gateway")

        with self.assertRaises(HTTPError):
            self.relay(response)

        response.close.assert_called_once_with()

    def test_parse_response_closes_stream_after_callback_or_protocol_error(self):
        for callback_error in (False, True):
            with self.subTest(callback_error=callback_error):
                response = build_sse_response([{"type": "CUSTOM"}])
                if not callback_error:
                    response.iter_lines.return_value = ["data: not-json"]
                callback = mock.Mock(side_effect=RuntimeError("callback failed")) if callback_error else mock.Mock()
                resource = self.public_agui_resource
                with patch_public_resource_request(resource, response):
                    with self.assertRaises(RuntimeError if callback_error else AGUIStreamProtocolError):
                        resource.request(self._public_request_payload(callback))
                response.close.assert_called_once_with()
                self.assertIsNone(ChatCompletion._on_event_context.get())

    def test_rejects_non_json_event(self):
        response = build_sse_response([])
        response.iter_lines.return_value = ["data: not-json"]

        with self.assertRaises(AGUIStreamProtocolError):
            self.relay(response)

    def test_rejects_non_object_json_event(self):
        response = build_sse_response([])
        response.iter_lines.return_value = ['data: ["not", "an", "object"]']

        with self.assertRaises(AGUIStreamProtocolError):
            self.relay(response)

    def test_perform_request_keeps_callback_in_context_local_scope(self):
        callback = mock.Mock()
        with mock.patch.object(
            AIAgentBase,
            "perform_request",
            side_effect=lambda request_data: ChatCompletion._on_event_context.get(),
        ):
            result = self.resource.perform_request({"on_event": callback})

        self.assertIs(result, callback)
        self.assertIsNone(ChatCompletion._on_event_context.get())

    def test_public_request_returns_events_uses_header_and_preserves_callback_payload(self):
        seen = []
        events = build_complete_events(result={"ok": True})
        response = build_sse_response(events)
        resource = self.public_agui_resource
        payload = self._public_request_payload(seen.append)
        original_payload = dict(payload)

        with patch_public_resource_request(resource, response) as request:
            result = resource.request(payload)

        self.assertIsInstance(resource, ChatCompletion)
        self.assertIsNone(result)
        self.assertEqual(seen, events)
        self.assertEqual(payload, original_payload)
        self.assertIsNone(ChatCompletion._on_event_context.get())
        request_kwargs = request.call_args.kwargs
        self.assertEqual(request_kwargs["headers"]["X-BKAIDEV-USER"], "alice")
        self.assertNotIn("user", request_kwargs["json"])
        self.assertNotIn("on_event", request_kwargs["json"])
        self.assertNotIn("max_sse_line_bytes", request_kwargs["json"])
        response.close.assert_called_once_with()

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
            result = self.relay(response)

        messages = [record.getMessage() for record in records]
        self.assertIsNone(result)
        self.assertTrue(any("status_code=200" in message and "stream_response=True" in message for message in messages))
        self.assertTrue(any("event_count=5" in message for message in messages))
        self.assertFalse(any(secret_content in message for message in messages))

    def test_parse_response_logs_http_error_metadata_without_business_body(self):
        secret_body = "SECRET_HTTP_ERROR_BODY"
        response = build_sse_response([])
        response.status_code = 502
        response.content = secret_body.encode()
        response.raise_for_status.side_effect = HTTPError("bad gateway", response=response)

        with capture_named_logs("app") as records:
            with self.assertRaises(HTTPError):
                self.relay(response)

        messages = [record.getMessage() for record in records]
        self.assertTrue(any("status_code=502" in message and "stream_response=True" in message for message in messages))
        self.assertFalse(any(secret_body in message for message in messages))

    def test_parse_response_relays_run_error_without_logging_business_body(self):
        secret_error = "SECRET_RUN_ERROR_BODY"
        response = build_sse_response([{"type": "RUN_ERROR", "message": secret_error}])

        with capture_named_logs("app") as records:
            result = self.relay(response)

        messages = [record.getMessage() for record in records]
        self.assertIsNone(result)
        self.assertTrue(any("status_code=200" in message and "stream_response=True" in message for message in messages))
        self.assertFalse(any(secret_error in message for message in messages))

    def test_public_agui_request_restores_session_after_protocol_error(self):
        response = build_sse_response([])
        response.iter_lines.return_value = ["data: not-json"]

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


class TestChatCompletionCallback(SimpleTestCase):
    """同一公开入口有回调时交付 JSON 对象，无回调时维持历史正文返回。"""

    def test_public_chat_completion_delivers_json_and_consumes_past_run_finished(self):
        events = build_complete_events() + [{"type": "CUSTOM", "value": "完成事件之后仍需透传"}]
        response = build_sse_response(events)
        seen = []
        payload = TestChatCompletionRelay._public_request_payload(seen.append)
        original = dict(payload)
        resource = api.bk_plugins_ai_agent.chat_completion

        with patch_public_resource_request(resource, response) as request:
            result = resource.request(payload)

        self.assertEqual(seen, events)
        self.assertIsNone(result)
        self.assertEqual(payload, original)
        self.assertNotIn("on_event", request.call_args.kwargs["json"])
        response.close.assert_called_once_with()

    def test_callback_mode_preserves_standard_json_business_error(self):
        response = build_json_response(
            {
                "result": False,
                "code": 50001,
                "message": "agent overloaded",
                "data": None,
                "request_id": "request-id",
            }
        )
        seen = []
        resource = api.bk_plugins_ai_agent.chat_completion

        with patch_public_resource_request(resource, response):
            with self.assertRaises(APIRequestError) as caught:
                resource.request(TestChatCompletionRelay._public_request_payload(seen.append))

        self.assertIn("agent overloaded", str(caught.exception))
        self.assertEqual(seen, [])
        response.close.assert_called_once_with()

    def test_callback_mode_preserves_iam_permission_error(self):
        permission = {"action": "view", "resource": "audit_log"}
        for status_code in (200, 403):
            with self.subTest(status_code=status_code):
                response = build_json_response(
                    {
                        "result": False,
                        "code": IAMNoPermission().code,
                        "message": "permission denied",
                        "data": {"system_id": "system-1"},
                        "permission": permission,
                    },
                    status_code=status_code,
                )
                seen = []
                resource = api.bk_plugins_ai_agent.chat_completion

                with patch_public_resource_request(resource, response):
                    with self.assertRaises(IAMNoPermission) as caught:
                        resource.request(TestChatCompletionRelay._public_request_payload(seen.append))

                self.assertEqual(json.loads(caught.exception.data), {"system_id": "system-1", "permission": permission})
                self.assertEqual(seen, [])
                response.close.assert_called_once_with()

    def test_callback_mode_rejects_successful_non_stream_response(self):
        response = build_json_response({"result": True, "code": 0, "data": {"content": "unexpected"}})
        seen = []
        resource = api.bk_plugins_ai_agent.chat_completion

        with patch_public_resource_request(resource, response):
            with self.assertRaises(AGUIStreamProtocolError):
                resource.request(TestChatCompletionRelay._public_request_payload(seen.append))

        self.assertEqual(seen, [])
        response.close.assert_called_once_with()


class TestChatCompletionLineFraming(SimpleTestCase):
    """使用 Requests 自身的 iter_lines，覆盖网络分片和换行，不替身分行算法。"""

    def test_nonchunked_large_event_uses_buffered_reads(self):
        """接受缓冲延迟，但不能为一条长行逐字节读取、反复扫描 pending。"""

        class CountingBody(io.BytesIO):
            reads = 0

            def read(self, size=-1):
                self.reads += 1
                return super().read(size)

        event = {"type": "CUSTOM", "text": "x" * (64 * 1024)}
        body = CountingBody(("data: " + json.dumps(event) + "\n\n").encode())
        response = requests.Response()
        response.status_code = 200
        response.headers["Content-Type"] = "text/event-stream"
        response.raw = HTTPResponse(body=body, preload_content=False)
        seen = []

        ChatCompletion()._relay_stream_response(response, seen.append)

        self.assertEqual(seen, [event])
        self.assertTrue(body.closed)
        # 正常读取约 130 次，逐字节读取会超过 65000 次；不依赖 CI 的 CPU 速度。
        self.assertLess(body.reads, 1024)

    def test_fragmented_json_and_sse_metadata(self):
        for ending in (b"\n", b"\r", b"\r\n"):
            for chunk_size in (1, 17, 512):
                with self.subTest(ending=ending, chunk_size=chunk_size):
                    events = [{"type": "CUSTOM", "value": "中文\n第二行"}, {"tail": True}]
                    lines = [
                        b": heartbeat",
                        b"event: custom",
                        b"id: 8",
                        b"",
                        *(b"data: " + json.dumps(event, ensure_ascii=False).encode() for event in events),
                    ]
                    # 第二条事件无尾部换行，仍交由 Requests 在 EOF 产出。
                    body = ending.join(lines)
                    response = requests.Response()
                    response.status_code = 200
                    response.headers["Content-Type"] = "text/event-stream"
                    response.iter_content = mock.Mock(
                        return_value=(body[index : index + chunk_size] for index in range(0, len(body), chunk_size))
                    )
                    response.close = mock.Mock()
                    seen = []
                    ChatCompletion()._relay_stream_response(response, seen.append)
                    self.assertEqual(seen, events)
                    response.close.assert_called_once_with()

    def test_callbacks_are_isolated_across_overlapping_requests(self):
        resource = ChatCompletion()
        barrier = threading.Barrier(2)
        callbacks = [mock.Mock(), mock.Mock()]
        errors = []

        def perform(request_data):
            barrier.wait(timeout=5)
            resource._on_event_context.get()(request_data["event"])

        def request(index):
            try:
                resource.perform_request({"on_event": callbacks[index], "event": {"index": index}})
                self.assertIsNone(resource._on_event_context.get())
            except Exception as error:
                errors.append(error)

        with mock.patch.object(AIAgentBase, "perform_request", side_effect=perform):
            threads = [threading.Thread(target=request, args=(index,)) for index in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(6)
            self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(errors, [])
        for index, callback in enumerate(callbacks):
            callback.assert_called_once_with({"index": index})

import threading
from unittest import mock

import requests
from django.conf import settings
from django.test import LiveServerTestCase, SimpleTestCase, override_settings
from rest_framework.permissions import AllowAny

from services.web.ai_assistant.constants import (
    AttachmentType,
    ExecutionStatus,
    MessageType,
    PlatformStreamEvent,
)
from services.web.ai_assistant.handlers import (
    attachment_handler_registry,
    message_handler_registry,
)
from services.web.ai_assistant.models import Attachment
from services.web.ai_assistant.schemas import parse_stream_config
from services.web.ai_assistant.streaming import RedisLiveStore
from services.web.ai_assistant.views import (
    AttachmentsViewSet,
    ConversationsViewSet,
    MessagesViewSet,
)
from tests.test_ai_assistant.celery_integration import running_celery_worker
from tests.test_ai_assistant.http_integration import (
    iter_http_sse_frames,
    iter_sse_frames,
    start_http_sse_collector,
    wait_for_http_json,
)
from tests.test_ai_assistant.integration_handlers import (
    INTEGRATION_QUEUE,
    RealAttachmentHttpFailOnceHandler,
    RealAttachmentHttpStreamHandler,
    RealAttachmentHttpStreamRetryHandler,
    RealMessageSuccessHandler,
    http_stream_release,
    http_stream_started,
    release_http_stream_events,
    reset_http_attachment_fail_once,
    reset_http_stream_events,
)
from tests.test_ai_assistant.stream_cleanup import delete_attachment_stream_keys

HTTP_USER = "alice"
INTERNAL_FIELDS = ("task_id", "context_data", "stream_config")
USERNAME_TARGETS = (
    "services.web.ai_assistant.resources.conversation.get_request_username",
    "services.web.ai_assistant.resources.message.get_request_username",
    "services.web.ai_assistant.resources.attachment.get_request_username",
    "services.web.ai_assistant.resources.stream.get_request_username",
)


class SSEParserTest(SimpleTestCase):
    def test_iter_sse_frames_parses_default_named_id_json_and_heartbeat(self):
        frames = list(
            iter_sse_frames(
                [
                    b'data: {"delta":"hello"}\n',
                    b"\n",
                    b"event: platform.stream_end\n",
                    b"id: 2-0\n",
                    b'data: {"status":"SUCCESS"}\n',
                    b"\n",
                    b": heartbeat\n",
                    b"\n",
                    b"id: 1-0\n",
                    b'data: {"step":1}\n',
                    b"\n",
                    b"id: 1-1\n",
                    b'data: {"step":2}\n',
                    b"\n",
                ]
            )
        )

        self.assertEqual(len(frames), 4)
        self.assertIsNone(frames[0].event)
        self.assertIsNone(frames[0].stream_id)
        self.assertEqual(frames[0].data, {"delta": "hello"})
        self.assertEqual(frames[1].event, "platform.stream_end")
        self.assertEqual(frames[1].stream_id, "2-0")
        self.assertEqual(frames[1].data, {"status": "SUCCESS"})
        self.assertEqual(frames[2].stream_id, "1-0")
        self.assertEqual(frames[2].data, {"step": 1})
        self.assertEqual(frames[3].stream_id, "1-1")
        self.assertEqual(frames[3].data, {"step": 2})

    def test_iter_http_sse_frames_disables_requests_chunk_buffering(self):
        response = mock.Mock(url="http://test/stream")
        response.iter_lines.return_value = iter([b'data: {"step":1}', b""])

        frames = list(iter_http_sse_frames(response))

        response.iter_lines.assert_called_once_with(chunk_size=1)
        self.assertEqual(frames[0].data, {"step": 1})

    def test_iter_http_sse_frames_enforces_overall_deadline(self):
        response = mock.Mock(url="http://test/stream")
        response.iter_lines.return_value = iter([b": heartbeat"])

        with (
            mock.patch("tests.test_ai_assistant.http_integration.time.monotonic", side_effect=[0.0, 2.0]),
            self.assertRaisesRegex(TimeoutError, "SSE 读取超时"),
        ):
            list(iter_http_sse_frames(response, timeout=1))


class HttpIntegrationTest(LiveServerTestCase):
    """真实 HTTP 走中间件和 Worker，验证消息、附件与 SSE 主链路。"""

    available_apps = ["services.web.ai_assistant"]
    reset_sequences = True

    @classmethod
    def setUpClass(cls):
        rest_framework = {
            **settings.REST_FRAMEWORK,
            "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.AllowAny",),
            "DEFAULT_AUTHENTICATION_CLASSES": (),
        }
        middleware = tuple(
            item
            for item in settings.MIDDLEWARE
            if "Login" not in item and "JWTUser" not in item and "JWTApp" not in item
        )
        cls._settings_override = override_settings(REST_FRAMEWORK=rest_framework, MIDDLEWARE=middleware)
        cls._settings_override.enable()
        cls._username_patchers = [mock.patch(target, return_value=HTTP_USER) for target in USERNAME_TARGETS]
        for patcher in cls._username_patchers:
            patcher.start()
        cls._view_auth_originals = {}
        for viewset in (ConversationsViewSet, MessagesViewSet, AttachmentsViewSet):
            cls._view_auth_originals[viewset] = (viewset.authentication_classes, viewset.permission_classes)
            viewset.authentication_classes = []
            viewset.permission_classes = [AllowAny]
        super().setUpClass()
        cls.worker_context = running_celery_worker(queue_name=INTEGRATION_QUEUE)
        cls.worker_context.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.worker_context.__exit__(None, None, None)
        for viewset, originals in cls._view_auth_originals.items():
            viewset.authentication_classes, viewset.permission_classes = originals
        for patcher in cls._username_patchers:
            patcher.stop()
        cls._settings_override.disable()
        super().tearDownClass()

    def setUp(self):
        reset_http_stream_events()
        reset_http_attachment_fail_once()
        self._sse_collectors: list[threading.Thread] = []
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    def tearDown(self):
        release_http_stream_events()
        for thread in self._sse_collectors:
            thread.join(timeout=settings.CELERY_TEST_TASK_TIMEOUT)
        leftovers = delete_attachment_stream_keys(
            attachment_uids=Attachment.objects.filter(is_stream=True).values_list("uid", flat=True)
        )
        self.session.close()
        message_handler_registry.unregister(MessageType.NATURAL_LANGUAGE_SEARCH)
        attachment_handler_registry.unregister(AttachmentType.AI_ANALYSIS)
        reset_http_stream_events()
        if leftovers:
            raise AssertionError(f"专项 Redis key 残留: {leftovers}")

    def api_url(self, path: str) -> str:
        return f"{self.live_server_url}/api/v1/ai_assistant{path}"

    def unwrap(self, response) -> dict:
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertTrue(payload["result"], payload)
        self.assertEqual(payload["code"], 0)
        return payload["data"]

    def assert_public_envelope(self, data: dict) -> None:
        for field_name in INTERNAL_FIELDS:
            self.assertNotIn(field_name, data)

    def create_conversation(self) -> dict:
        return self.unwrap(self.session.post(self.api_url("/conversations/"), json={}))

    def create_message(self, *, conversation_uid: str, text: str) -> dict:
        return self.unwrap(
            self.session.post(
                self.api_url("/messages/"),
                json={
                    "conversation_uid": conversation_uid,
                    "message_type": MessageType.NATURAL_LANGUAGE_SEARCH,
                    "input_data": {"text": text},
                },
            )
        )

    def wait_status(self, path: str, status: str) -> dict:
        payload = wait_for_http_json(
            session=self.session,
            url=self.api_url(path),
            predicate=lambda data: data.get("status") == status,
        )
        self.assertTrue(payload["result"], payload)
        return payload["data"]

    def create_success_message(self, *, text: str = "query") -> dict:
        message_handler_registry.register(RealMessageSuccessHandler())
        conversation = self.create_conversation()
        created = self.create_message(conversation_uid=conversation["uid"], text=text)
        self.assertEqual(created["status"], ExecutionStatus.PROCESSING)
        self.assert_public_envelope(created)
        completed = self.wait_status(f"/messages/{created['uid']}/", ExecutionStatus.SUCCESS)
        self.assert_public_envelope(completed)
        self.assertEqual(completed["output_data"], {"content": f"real:{text}"})
        return completed

    def first_live_stream_id(self, *, attachment_uid: str) -> str:
        """读取 Worker 已写入 Redis 的首条事件游标。

        LiveServer/wsgiref 会缓冲整段 ``StreamingHttpResponse``，测试进程无法在
        释放 Worker 前从 HTTP 响应里读到 SSE ``id``。该游标与首帧 ``id`` 同源。
        """

        attachment = Attachment.objects.get(uid=attachment_uid)
        config = parse_stream_config(attachment.stream_config)
        self.assertIsNotNone(config)
        result = RedisLiveStore().read(redis_key=config.redis_key, after_id="0-0", block_ms=100)
        self.assertTrue(result.events, "Redis 中应已有首条流式事件")
        cursor = result.events[0].stream_id
        self.assertTrue(cursor)
        return cursor

    def start_sse_request(
        self, *, attachment_uid: str, execution_id: str, last_event_id: str | None = None, terminal_event: str
    ):
        """在独立线程发起 SSE，避免 LiveServer 缓冲导致 get() 阻塞到流结束。"""

        headers = {}
        if last_event_id:
            headers["Last-Event-ID"] = last_event_id
        frames, done, thread, errors = start_http_sse_collector(
            session=self.session,
            url=self.api_url(f"/attachments/{attachment_uid}/stream/"),
            params={"execution_id": execution_id},
            headers=headers,
            terminal_event=terminal_event,
        )
        self._sse_collectors.append(thread)
        return frames, done, thread, errors

    def test_async_message_creates_and_reaches_success_over_http(self):
        completed = self.create_success_message(text="http-message")
        self.assertEqual(completed["message_type"], MessageType.NATURAL_LANGUAGE_SEARCH)
        self.assertEqual(completed["input_data"], {"text": "http-message"})

    def test_async_attachment_creates_and_retries_after_failure_over_http(self):
        source = self.create_success_message(text="source")
        message_handler_registry.unregister(MessageType.NATURAL_LANGUAGE_SEARCH)
        attachment_handler_registry.register(RealAttachmentHttpFailOnceHandler())

        created = self.unwrap(
            self.session.post(
                self.api_url(f"/messages/{source['uid']}/attachments/"),
                json={"attachment_type": AttachmentType.AI_ANALYSIS, "input_data": {"text": "analyse"}},
            )
        )
        self.assertEqual(created["status"], ExecutionStatus.PROCESSING)
        self.assert_public_envelope(created)
        failed = self.wait_status(f"/attachments/{created['uid']}/", ExecutionStatus.FAILED)
        self.assert_public_envelope(failed)

        retried = self.unwrap(self.session.post(self.api_url(f"/attachments/{created['uid']}/retry/"), json={}))
        self.assertEqual(retried["status"], ExecutionStatus.PROCESSING)
        completed = self.wait_status(f"/attachments/{created['uid']}/", ExecutionStatus.SUCCESS)
        self.assertEqual(completed["output_data"], {"content": "http-retry:success"})
        self.assert_public_envelope(completed)

    def test_stream_attachment_emits_business_events_and_terminal_over_http(self):
        source = self.create_success_message(text="source")
        message_handler_registry.unregister(MessageType.NATURAL_LANGUAGE_SEARCH)
        attachment_handler_registry.register(RealAttachmentHttpStreamHandler())

        created = self.unwrap(
            self.session.post(
                self.api_url(f"/messages/{source['uid']}/attachments/"),
                json={"attachment_type": AttachmentType.AI_ANALYSIS, "input_data": {"text": "stream"}},
            )
        )
        self.assertTrue(http_stream_started.wait(settings.CELERY_TEST_TASK_TIMEOUT))
        snapshot = self.unwrap(self.session.get(self.api_url(f"/attachments/{created['uid']}/stream/snapshot/")))
        execution_id = snapshot["execution_id"]
        self.assertTrue(execution_id)

        frames, done, thread, errors = self.start_sse_request(
            attachment_uid=created["uid"],
            execution_id=execution_id,
            terminal_event=PlatformStreamEvent.STREAM_END,
        )
        http_stream_release.set()
        self.assertTrue(done.wait(settings.CELERY_TEST_TASK_TIMEOUT))
        thread.join(timeout=1)
        self.assertFalse(errors, errors)

        business = [frame.data for frame in frames if frame.event is None]
        self.assertEqual(business, [{"step": 1}, {"step": 2}])
        self.assertEqual(frames[-1].event, PlatformStreamEvent.STREAM_END)
        self.assertEqual(frames[-1].data, {"status": ExecutionStatus.SUCCESS})
        detail = self.wait_status(f"/attachments/{created['uid']}/", ExecutionStatus.SUCCESS)
        self.assertEqual(detail["output_data"], {"content": "http-stream:success"})
        self.assert_public_envelope(detail)

    def test_last_event_id_filters_consumed_event_over_http(self):
        source = self.create_success_message(text="source")
        message_handler_registry.unregister(MessageType.NATURAL_LANGUAGE_SEARCH)
        attachment_handler_registry.register(RealAttachmentHttpStreamHandler())
        created = self.unwrap(
            self.session.post(
                self.api_url(f"/messages/{source['uid']}/attachments/"),
                json={"attachment_type": AttachmentType.AI_ANALYSIS, "input_data": {"text": "resume"}},
            )
        )
        self.assertTrue(http_stream_started.wait(settings.CELERY_TEST_TASK_TIMEOUT))
        snapshot = self.unwrap(self.session.get(self.api_url(f"/attachments/{created['uid']}/stream/snapshot/")))
        cursor = self.first_live_stream_id(attachment_uid=created["uid"])
        frames, done, thread, errors = self.start_sse_request(
            attachment_uid=created["uid"],
            execution_id=snapshot["execution_id"],
            last_event_id=cursor,
            terminal_event=PlatformStreamEvent.STREAM_END,
        )
        http_stream_release.set()
        self.assertTrue(done.wait(settings.CELERY_TEST_TASK_TIMEOUT))
        thread.join(timeout=1)
        self.assertFalse(errors, errors)
        self.assertFalse(any(frame.data == {"step": 1} for frame in frames))
        self.assertEqual(frames[0].data, {"step": 2})
        self.assertEqual(frames[-1].event, PlatformStreamEvent.STREAM_END)

    def test_stream_retry_resets_old_execution_and_rebuilds_snapshot(self):
        source = self.create_success_message(text="source")
        message_handler_registry.unregister(MessageType.NATURAL_LANGUAGE_SEARCH)
        attachment_handler_registry.register(RealAttachmentHttpStreamRetryHandler())
        created = self.unwrap(
            self.session.post(
                self.api_url(f"/messages/{source['uid']}/attachments/"),
                json={"attachment_type": AttachmentType.AI_ANALYSIS, "input_data": {"text": "retry"}},
            )
        )
        self.assertTrue(http_stream_started.wait(settings.CELERY_TEST_TASK_TIMEOUT))
        snapshot = self.unwrap(self.session.get(self.api_url(f"/attachments/{created['uid']}/stream/snapshot/")))
        old_execution_id = snapshot["execution_id"]
        old_frames, done, thread, errors = self.start_sse_request(
            attachment_uid=created["uid"],
            execution_id=old_execution_id,
            terminal_event=PlatformStreamEvent.STREAM_RESET,
        )
        http_stream_release.set()
        self.assertTrue(done.wait(settings.CELERY_TEST_TASK_TIMEOUT))
        thread.join(timeout=1)
        self.assertFalse(errors, errors)
        self.assertEqual(old_frames[-1].event, PlatformStreamEvent.STREAM_RESET)

        detail = self.wait_status(f"/attachments/{created['uid']}/", ExecutionStatus.SUCCESS)
        new_snapshot = self.unwrap(self.session.get(self.api_url(f"/attachments/{created['uid']}/stream/snapshot/")))
        self.assertNotEqual(new_snapshot["execution_id"], old_execution_id)
        self.assertEqual(detail["output_data"], {"content": "http-stream:success"})
        self.assertTrue(any(event.get("data") == {"step": 2} for event in new_snapshot["events"]))
        self.assertEqual(new_snapshot["events"][-1]["event"], PlatformStreamEvent.STREAM_END)

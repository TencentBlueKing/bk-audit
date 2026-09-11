"""生产同类 Web 栈的 SSE 专项测试。

本模块使用独立 Gunicorn/gevent 进程验证真实 socket 行为，补足
LiveServer/wsgiref 无法证明事件实时到达的边界。
"""

from contextlib import ExitStack

import requests
from django.conf import settings
from django.test import TransactionTestCase

from services.web.ai_assistant.constants import (
    AttachmentType,
    ExecutionStatus,
    MessageType,
    PlatformStreamEvent,
)
from services.web.ai_assistant.handlers import attachment_handler_registry
from services.web.ai_assistant.models import Attachment, Conversation, Message
from services.web.ai_assistant.services import AttachmentService
from tests.test_ai_assistant.celery_integration import (
    running_celery_worker,
    wait_for_snapshot,
    wait_for_task_postrun,
)
from tests.test_ai_assistant.http_integration import iter_http_sse_frames
from tests.test_ai_assistant.special.web_process import running_gunicorn_web
from tests.test_ai_assistant.special_handlers import (
    SPECIAL_SSE_QUEUE,
    SpecialRealtimeSSEHandler,
    SpecialRealtimeSSERetryHandler,
    finish_realtime_sse_observations,
    finish_retry_sse_observations,
    realtime_sse_first_sent,
    realtime_sse_second_sent,
    release_realtime_sse_observations,
    release_retry_sse_observations,
    reset_realtime_sse_observations,
    reset_retry_sse_observations,
    retry_sse_first_sent,
    retry_sse_second_sent,
)
from tests.test_ai_assistant.stream_cleanup import delete_attachment_stream_keys

SSE_TEST_USER = "sse-e2e-user"


class GunicornSSESpecialTest(TransactionTestCase):
    """真实 Gunicorn/gevent、RabbitMQ、Redis 和 MySQL 组合下验证 SSE 时序。"""

    available_apps = ["services.web.ai_assistant"]
    reset_sequences = True

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._contexts = ExitStack()
        try:
            cls._contexts.enter_context(running_celery_worker(queue_name=SPECIAL_SSE_QUEUE))
            cls.base_url = cls._contexts.enter_context(running_gunicorn_web(username=SSE_TEST_USER))
        except Exception:
            cls._contexts.close()
            super().tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        release_realtime_sse_observations()
        finish_realtime_sse_observations()
        release_retry_sse_observations()
        finish_retry_sse_observations()
        try:
            cls._contexts.close()
        finally:
            super().tearDownClass()

    def setUp(self):
        self.user = SSE_TEST_USER
        self.conversation = Conversation.objects.create(created_by=self.user, updated_by=self.user)
        self.session = requests.Session()
        self.task_postrun_expectations: dict[str, bool] = {}
        reset_realtime_sse_observations()
        reset_retry_sse_observations()

    def tearDown(self):
        release_realtime_sse_observations()
        finish_realtime_sse_observations()
        release_retry_sse_observations()
        finish_retry_sse_observations()
        processing_ids = Attachment.objects.filter(
            created_by=self.user,
            status=ExecutionStatus.PROCESSING,
        ).values_list("id", flat=True)
        for attachment_id in processing_ids:
            wait_for_snapshot(
                model=Attachment,
                instance_id=attachment_id,
                predicate=lambda value: value.status in {ExecutionStatus.SUCCESS, ExecutionStatus.FAILED},
            )
        # 数据库终态先于 Redis terminal 发布；异常路径也要等 Worker 完整退出后再清理实时流。
        for task_id, may_retry in self.task_postrun_expectations.items():
            expected_count = 2 if may_retry and retry_sse_second_sent.is_set() else 1
            wait_for_task_postrun(task_id=task_id, expected_count=expected_count)
        leftovers = delete_attachment_stream_keys(
            attachment_uids=Attachment.objects.filter(is_stream=True).values_list("uid", flat=True)
        )
        self.session.close()
        attachment_handler_registry.unregister(AttachmentType.AI_ANALYSIS)
        reset_realtime_sse_observations()
        reset_retry_sse_observations()
        if leftovers:
            raise AssertionError(f"专项 Redis key 残留: {leftovers}")

    def api_url(self, path: str) -> str:
        return f"{self.base_url}/api/v1/ai_assistant{path}"

    def unwrap(self, response) -> dict:
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertTrue(payload["result"], payload)
        self.assertEqual(payload["code"], 0, payload)
        return payload["data"]

    def create_stream_attachment(self, *, handler=None) -> Attachment:
        handler = handler or SpecialRealtimeSSEHandler()
        attachment_handler_registry.register(handler)
        source = Message.objects.create(
            conversation=self.conversation,
            message_type=MessageType.LOG_SEARCH,
            status=ExecutionStatus.SUCCESS,
            input_data={"text": "source"},
            context_data={"prefix": "source"},
            output_data={"content": "source"},
            created_by=self.user,
            updated_by=self.user,
        )
        attachment = AttachmentService(user=self.user).create(
            source_message_uid=str(source.uid),
            attachment_type=AttachmentType.AI_ANALYSIS,
            input_data={"text": "sse-e2e"},
        )
        # apply_async 失败时 Service 已同步写为 FAILED，不会产生 task_postrun。
        if attachment.status == ExecutionStatus.PROCESSING:
            self.task_postrun_expectations[attachment.task_id] = isinstance(handler, SpecialRealtimeSSERetryHandler)
        return attachment

    def get_snapshot(self, attachment: Attachment) -> dict:
        response = self.session.get(
            self.api_url(f"/attachments/{attachment.uid}/stream/snapshot/"),
            timeout=(3.05, settings.CELERY_TEST_TASK_TIMEOUT),
        )
        return self.unwrap(response)

    def open_stream(self, attachment: Attachment, *, execution_id: str, last_event_id: str | None = None):
        headers = {"Accept": "text/event-stream"}
        if last_event_id:
            headers["Last-Event-ID"] = last_event_id
        response = self.session.get(
            self.api_url(f"/attachments/{attachment.uid}/stream/"),
            params={"execution_id": execution_id},
            headers=headers,
            stream=True,
            timeout=(3.05, settings.CELERY_TEST_TASK_TIMEOUT),
        )
        if response.status_code != 200:
            self.fail(f"SSE HTTP {response.status_code}: {response.text}")
        return response

    def test_first_event_arrives_before_task_finishes(self):
        attachment = self.create_stream_attachment()
        self.assertTrue(realtime_sse_first_sent.wait(settings.CELERY_TEST_TASK_TIMEOUT))
        snapshot = self.get_snapshot(attachment)

        response = self.open_stream(attachment, execution_id=snapshot["execution_id"])
        try:
            frames = iter_http_sse_frames(response)
            first = next(frames)

            attachment.refresh_from_db()
            self.assertEqual(first.data, {"step": 1})
            self.assertEqual(attachment.status, ExecutionStatus.PROCESSING)
            self.assertTrue(response.headers["Content-Type"].startswith("text/event-stream"))
            self.assertIn("no-cache", response.headers["Cache-Control"])
            self.assertEqual(response.headers["X-Accel-Buffering"], "no")

            release_realtime_sse_observations()
            finish_realtime_sse_observations()
            remaining = list(frames)
        finally:
            response.close()

        self.assertEqual([frame.data for frame in remaining if frame.event is None], [{"step": 2}])
        self.assertEqual(remaining[-1].event, PlatformStreamEvent.STREAM_END)
        completed = wait_for_snapshot(
            model=Attachment,
            instance_id=attachment.id,
            predicate=lambda value: value.status == ExecutionStatus.SUCCESS,
        )
        self.assertEqual(completed.output_data, {"content": "sse-e2e:success"})

    def test_last_event_id_resumes_without_replaying_consumed_event(self):
        attachment = self.create_stream_attachment()
        self.assertTrue(realtime_sse_first_sent.wait(settings.CELERY_TEST_TASK_TIMEOUT))
        snapshot = self.get_snapshot(attachment)

        first_response = self.open_stream(attachment, execution_id=snapshot["execution_id"])
        try:
            first = next(iter_http_sse_frames(first_response))
        finally:
            first_response.close()
        self.assertEqual(first.data, {"step": 1})
        self.assertIsNotNone(first.stream_id)

        release_realtime_sse_observations()
        self.assertTrue(realtime_sse_second_sent.wait(settings.CELERY_TEST_TASK_TIMEOUT))
        resumed_response = self.open_stream(
            attachment,
            execution_id=snapshot["execution_id"],
            last_event_id=first.stream_id,
        )
        try:
            resumed_frames = iter_http_sse_frames(resumed_response)
            second = next(resumed_frames)
            self.assertEqual(second.data, {"step": 2})

            finish_realtime_sse_observations()
            remaining = list(resumed_frames)
        finally:
            resumed_response.close()

        observed = [second, *remaining]
        self.assertFalse(any(frame.data == {"step": 1} for frame in observed))
        self.assertEqual(observed[-1].event, PlatformStreamEvent.STREAM_END)
        wait_for_snapshot(
            model=Attachment,
            instance_id=attachment.id,
            predicate=lambda value: value.status == ExecutionStatus.SUCCESS,
        )

    def test_retry_resets_live_old_connection_and_new_stream_completes(self):
        attachment = self.create_stream_attachment(handler=SpecialRealtimeSSERetryHandler())
        self.assertTrue(retry_sse_first_sent.wait(settings.CELERY_TEST_TASK_TIMEOUT))
        old_snapshot = self.get_snapshot(attachment)

        old_response = self.open_stream(attachment, execution_id=old_snapshot["execution_id"])
        try:
            old_frames = iter_http_sse_frames(old_response)
            first = next(old_frames)
            self.assertEqual(first.data, {"attempt": 1})

            release_retry_sse_observations()
            reset = next(old_frames)
            self.assertEqual(reset.event, PlatformStreamEvent.STREAM_RESET)
            self.assertEqual(list(old_frames), [])
        finally:
            old_response.close()

        self.assertTrue(retry_sse_second_sent.wait(settings.CELERY_TEST_TASK_TIMEOUT))
        new_snapshot = self.get_snapshot(attachment)
        self.assertNotEqual(new_snapshot["execution_id"], old_snapshot["execution_id"])

        new_response = self.open_stream(attachment, execution_id=new_snapshot["execution_id"])
        try:
            new_frames = iter_http_sse_frames(new_response)
            second = next(new_frames)
            self.assertEqual(second.data, {"attempt": 2})

            finish_retry_sse_observations()
            remaining = list(new_frames)
        finally:
            new_response.close()

        self.assertEqual(remaining[-1].event, PlatformStreamEvent.STREAM_END)
        completed = wait_for_snapshot(
            model=Attachment,
            instance_id=attachment.id,
            predicate=lambda value: value.status == ExecutionStatus.SUCCESS,
        )
        business_events = [event["data"] for event in completed.stream_archive if event["event"] is None]
        self.assertEqual(business_events, [{"attempt": 2}])
        self.assertEqual(completed.output_data, {"content": "sse-e2e-retry:success"})

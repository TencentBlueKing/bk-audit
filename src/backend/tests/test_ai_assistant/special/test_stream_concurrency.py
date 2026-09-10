import threading
from unittest import mock

import pytest
import requests
from amqp.exceptions import ChannelError
from blueapps.core.celery import celery_app
from django.conf import settings
from django.test import LiveServerTestCase, TransactionTestCase, override_settings
from rest_framework.permissions import AllowAny

from services.web.ai_assistant.constants import (
    AttachmentType,
    ExecutionStatus,
    MessageType,
    PlatformStreamEvent,
)
from services.web.ai_assistant.exceptions import (
    AttachmentNotFound,
    ConversationNotFound,
    MessageNotFound,
)
from services.web.ai_assistant.handlers import (
    attachment_handler_registry,
    message_handler_registry,
)
from services.web.ai_assistant.models import Attachment, Conversation, Message
from services.web.ai_assistant.resources.attachment import GetAttachment
from services.web.ai_assistant.resources.conversation import GetConversation
from services.web.ai_assistant.resources.message import GetMessage
from services.web.ai_assistant.resources.stream import (
    GetAttachmentStream,
    GetAttachmentStreamSnapshot,
)
from services.web.ai_assistant.schemas import parse_stream_config
from services.web.ai_assistant.services import AttachmentService, ConversationService
from services.web.ai_assistant.services.attachment_stream import AttachmentStreamService
from services.web.ai_assistant.views import (
    AttachmentsViewSet,
    ConversationsViewSet,
    MessagesViewSet,
)
from tests.test_ai_assistant import special_handlers
from tests.test_ai_assistant.celery_integration import (
    running_celery_worker,
    wait_for_snapshot,
    wait_for_task_postrun,
)
from tests.test_ai_assistant.http_integration import start_http_sse_collector
from tests.test_ai_assistant.special_handlers import (
    CONCURRENT_ATTACHMENT_COUNT,
    CONCURRENT_SEQUENCE,
    SPECIAL_CONCURRENCY_QUEUE,
    SpecialDeleteHoldHandler,
    SpecialIdleHoldHandler,
    SpecialIsolationHandler,
    SpecialSequenceHandler,
    release_concurrency_observations,
    reset_concurrency_observations,
)
from tests.test_ai_assistant.stream_cleanup import delete_attachment_stream_keys

pytestmark = pytest.mark.special

USERNAME_TARGETS = (
    "services.web.ai_assistant.resources.conversation.get_request_username",
    "services.web.ai_assistant.resources.message.get_request_username",
    "services.web.ai_assistant.resources.attachment.get_request_username",
    "services.web.ai_assistant.resources.stream.get_request_username",
)


def assert_queue_absent(queue_name: str) -> None:
    with celery_app.connection_for_write(url=settings.CELERY_TEST_BROKER_URL) as connection:
        with connection.channel() as channel:
            try:
                channel.queue_declare(queue=queue_name, passive=True)
            except ChannelError as error:
                if error.reply_code == 404:
                    return
                raise
            raise AssertionError(f"专项队列残留: {queue_name}")


class StreamConcurrencySpecialTest(TransactionTestCase):
    """验证多端读取、多附件隔离和删除中任务的用户不可见性。"""

    available_apps = ["services.web.ai_assistant"]
    reset_sequences = True

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.worker_context = running_celery_worker(queue_name=SPECIAL_CONCURRENCY_QUEUE)
        cls.worker_context.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.worker_context.__exit__(None, None, None)
        assert_queue_absent(SPECIAL_CONCURRENCY_QUEUE)
        super().tearDownClass()

    def setUp(self):
        self.user = "special-concurrency-user"
        self.conversation = Conversation.objects.create(created_by=self.user, updated_by=self.user)
        reset_concurrency_observations()

    def tearDown(self):
        release_concurrency_observations()
        leftovers = delete_attachment_stream_keys(
            attachment_uids=Attachment.objects.filter(is_stream=True).values_list("uid", flat=True)
        )
        attachment_handler_registry.unregister(AttachmentType.AI_ANALYSIS)
        reset_concurrency_observations()
        if leftovers:
            raise AssertionError(f"专项 Redis key 残留: {leftovers}")

    def create_source_message(self) -> Message:
        return Message.objects.create(
            conversation=self.conversation,
            message_type=MessageType.LOG_SEARCH,
            status=ExecutionStatus.SUCCESS,
            input_data={"text": "source"},
            context_data={"prefix": "source"},
            output_data={"content": "source"},
            created_by=self.user,
            updated_by=self.user,
        )

    def create_attachment(self, *, text: str) -> Attachment:
        return AttachmentService(user=self.user).create(
            source_message_uid=str(self.create_source_message().uid),
            attachment_type=AttachmentType.AI_ANALYSIS,
            input_data={"text": text},
        )

    def test_two_consumers_read_the_same_sequence_and_terminal(self):
        attachment_handler_registry.register(SpecialSequenceHandler())
        attachment = self.create_attachment(text="sequence")
        self.assertTrue(special_handlers.sequence_started.wait(settings.CELERY_TEST_TASK_TIMEOUT))
        snapshot = AttachmentStreamService(user=self.user).get_snapshot(attachment_uid=str(attachment.uid))
        self.assertIsNotNone(snapshot.execution_id)

        results: list[list] = [[], []]
        first_event = [threading.Event(), threading.Event()]
        errors: list[BaseException] = []

        def consume(index: int):
            try:
                for item in AttachmentStreamService(user=self.user).iter_events(
                    attachment_uid=str(attachment.uid),
                    execution_id=snapshot.execution_id,
                    last_stream_id=None,
                ):
                    if item is None:
                        continue
                    results[index].append(item)
                    if item.event is None:
                        first_event[index].set()
                    if item.event in (PlatformStreamEvent.STREAM_END, PlatformStreamEvent.STREAM_RESET):
                        break
            except Exception as error:  # noqa: BLE001
                errors.append(error)

        threads = [threading.Thread(target=consume, args=(index,), daemon=True) for index in range(2)]
        for thread in threads:
            thread.start()
        for started in first_event:
            self.assertTrue(started.wait(settings.CELERY_TEST_TASK_TIMEOUT))
        special_handlers.sequence_release.set()
        for thread in threads:
            thread.join(timeout=settings.CELERY_TEST_TASK_TIMEOUT)
        self.assertFalse(errors, errors)

        expected_business = CONCURRENT_SEQUENCE
        for events in results:
            business = [item.data for item in events if item.event is None]
            self.assertEqual(business, expected_business)
            self.assertEqual(events[-1].event, PlatformStreamEvent.STREAM_END)
        self.assertEqual(
            [item.data for item in results[0] if item.event is None],
            [item.data for item in results[1] if item.event is None],
        )

    def test_concurrent_attachments_are_isolated_and_one_failure_does_not_affect_others(self):
        # CONCURRENT_ATTACHMENT_COUNT 只用于制造执行重叠，不是性能 SLA。
        attachment_handler_registry.register(SpecialIsolationHandler())
        source = self.create_source_message()
        tokens = [f"token-{index}" for index in range(CONCURRENT_ATTACHMENT_COUNT - 1)]
        tokens.append(f"token-{CONCURRENT_ATTACHMENT_COUNT - 1}:fail")
        created: list[Attachment | None] = [None] * len(tokens)
        errors: list[BaseException] = []

        def create_one(index: int, token: str):
            try:
                created[index] = AttachmentService(user=self.user).create(
                    source_message_uid=str(source.uid),
                    attachment_type=AttachmentType.AI_ANALYSIS,
                    input_data={"text": token},
                )
            except Exception as error:  # noqa: BLE001
                errors.append(error)

        threads = [
            threading.Thread(target=create_one, args=(index, token), daemon=True) for index, token in enumerate(tokens)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=settings.CELERY_TEST_TASK_TIMEOUT)
        self.assertFalse(errors, errors)
        self.assertTrue(all(created))
        self.assertTrue(
            special_handlers.isolation_overlap_started.wait(settings.CELERY_TEST_TASK_TIMEOUT),
            "至少两个附件任务应在释放屏障前同时进入执行逻辑",
        )
        special_handlers.isolation_release.set()

        completed = []
        for attachment, token in zip(created, tokens, strict=True):
            expected = ExecutionStatus.FAILED if token.endswith(":fail") else ExecutionStatus.SUCCESS
            completed.append(
                wait_for_snapshot(
                    model=Attachment,
                    instance_id=attachment.id,
                    predicate=lambda value, status=expected: value.status == status,
                )
            )

        execution_ids = []
        redis_keys = []
        for attachment, token in zip(completed, tokens, strict=True):
            config = parse_stream_config(attachment.stream_config)
            self.assertIsNotNone(config)
            execution_ids.append(str(config.execution_id))
            redis_keys.append(config.redis_key)
            business = [event["data"] for event in attachment.stream_archive if event.get("event") is None]
            self.assertEqual(business, [{"token": token}])
            if token.endswith(":fail"):
                self.assertEqual(attachment.status, ExecutionStatus.FAILED)
            else:
                self.assertEqual(attachment.output_data, {"content": f"iso:{token}"})
                self.assertEqual(attachment.stream_archive[-1]["event"], PlatformStreamEvent.STREAM_END)

        self.assertEqual(len(set(execution_ids)), CONCURRENT_ATTACHMENT_COUNT)
        self.assertEqual(len(set(redis_keys)), CONCURRENT_ATTACHMENT_COUNT)

    def test_soft_deleted_conversation_hides_user_apis_but_task_can_finish(self):
        attachment_handler_registry.register(SpecialDeleteHoldHandler())
        source = self.create_source_message()
        attachment = AttachmentService(user=self.user).create(
            source_message_uid=str(source.uid),
            attachment_type=AttachmentType.AI_ANALYSIS,
            input_data={"text": "delete"},
        )
        self.assertTrue(special_handlers.delete_hold.wait(settings.CELERY_TEST_TASK_TIMEOUT))

        ConversationService(user=self.user).delete_conversation(conversation_uid=str(self.conversation.uid))
        special_handlers.delete_release.set()
        completed = wait_for_snapshot(
            model=Attachment,
            instance_id=attachment.id,
            predicate=lambda value: value.status == ExecutionStatus.SUCCESS,
        )
        self.assertEqual(completed.output_data, {"content": "delete:done"})

        patches = [mock.patch(target, return_value=self.user) for target in USERNAME_TARGETS]
        for patcher in patches:
            patcher.start()
        try:
            with self.assertRaises(ConversationNotFound):
                GetConversation().request({"conversation_uid": str(self.conversation.uid)})
            with self.assertRaises(MessageNotFound):
                GetMessage().request({"message_uid": str(source.uid)})
            with self.assertRaises(AttachmentNotFound):
                GetAttachment().request({"attachment_uid": str(attachment.uid)})
            with self.assertRaises(AttachmentNotFound):
                GetAttachmentStreamSnapshot().request({"attachment_uid": str(attachment.uid)})
            config = parse_stream_config(completed.stream_config)
            with self.assertRaises(AttachmentNotFound):
                GetAttachmentStream().request(
                    {
                        "attachment_uid": str(attachment.uid),
                        "execution_id": str(config.execution_id),
                    }
                )
        finally:
            for patcher in patches:
                patcher.stop()


class StreamIdleHttpSpecialTest(LiveServerTestCase):
    """真实 HTTP 下验证无业务事件流在空闲超时后断开。"""

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
        cls._username_patchers = [mock.patch(target, return_value="special-idle-user") for target in USERNAME_TARGETS]
        for patcher in cls._username_patchers:
            patcher.start()
        cls._view_auth_originals = {}
        for viewset in (ConversationsViewSet, MessagesViewSet, AttachmentsViewSet):
            cls._view_auth_originals[viewset] = (viewset.authentication_classes, viewset.permission_classes)
            viewset.authentication_classes = []
            viewset.permission_classes = [AllowAny]
        super().setUpClass()
        cls.worker_context = running_celery_worker(queue_name=SPECIAL_CONCURRENCY_QUEUE)
        cls.worker_context.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.worker_context.__exit__(None, None, None)
        assert_queue_absent(SPECIAL_CONCURRENCY_QUEUE)
        for viewset, originals in cls._view_auth_originals.items():
            viewset.authentication_classes, viewset.permission_classes = originals
        for patcher in cls._username_patchers:
            patcher.stop()
        cls._settings_override.disable()
        super().tearDownClass()

    def setUp(self):
        self.user = "special-idle-user"
        self.conversation = Conversation.objects.create(created_by=self.user, updated_by=self.user)
        self.dispatched_task_id: str | None = None
        self.attachment_id: int | None = None
        reset_concurrency_observations()
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    def tearDown(self):
        release_concurrency_observations()
        if self.attachment_id is not None:
            wait_for_snapshot(
                model=Attachment,
                instance_id=self.attachment_id,
                predicate=lambda value: value.status in {ExecutionStatus.SUCCESS, ExecutionStatus.FAILED},
            )
        if self.dispatched_task_id is not None:
            wait_for_task_postrun(task_id=self.dispatched_task_id)
        leftovers = delete_attachment_stream_keys(
            attachment_uids=Attachment.objects.filter(is_stream=True).values_list("uid", flat=True)
        )
        self.session.close()
        message_handler_registry.unregister(MessageType.NATURAL_LANGUAGE_SEARCH)
        attachment_handler_registry.unregister(AttachmentType.AI_ANALYSIS)
        reset_concurrency_observations()
        if leftovers:
            raise AssertionError(f"专项 Redis key 残留: {leftovers}")

    def api_url(self, path: str) -> str:
        return f"{self.live_server_url}/api/v1/ai_assistant{path}"

    def test_idle_http_stream_closes_after_heartbeat(self):
        attachment_handler_registry.register(SpecialIdleHoldHandler())
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
            input_data={"text": "idle"},
        )
        self.attachment_id = attachment.id
        if attachment.status == ExecutionStatus.PROCESSING:
            self.dispatched_task_id = attachment.task_id
        self.assertTrue(special_handlers.idle_started.wait(settings.CELERY_TEST_TASK_TIMEOUT))
        snapshot = AttachmentStreamService(user=self.user).get_snapshot(attachment_uid=str(attachment.uid))
        self.assertIsNotNone(snapshot.execution_id)

        # 1 秒只是测试配置；BLOCK_MS 默认 15s 会跳过 heartbeat，因此压到 200ms 才能先看到心跳。
        with (
            override_settings(AI_ASSISTANT_STREAM_IDLE_TIMEOUT=1),
            mock.patch.object(AttachmentStreamService, "BLOCK_MS", 200),
        ):
            frames, done, thread, errors = start_http_sse_collector(
                session=self.session,
                url=self.api_url(f"/attachments/{attachment.uid}/stream/"),
                params={"execution_id": str(snapshot.execution_id)},
                include_heartbeats=True,
            )
            self.assertTrue(done.wait(settings.CELERY_TEST_TASK_TIMEOUT))
            thread.join(timeout=1)
        special_handlers.idle_release.set()
        self.assertFalse(errors, errors)
        self.assertTrue(any(frame.is_heartbeat for frame in frames))
        self.assertFalse(any(not frame.is_heartbeat and frame.event is None for frame in frames))
        wait_for_snapshot(
            model=Attachment,
            instance_id=attachment.id,
            predicate=lambda value: value.status == ExecutionStatus.SUCCESS,
        )

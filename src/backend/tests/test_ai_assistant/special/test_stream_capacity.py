import pytest
from amqp.exceptions import ChannelError
from blueapps.core.celery import celery_app
from django.conf import settings
from django.test import TransactionTestCase, override_settings

from services.web.ai_assistant.constants import (
    AttachmentType,
    ExecutionStatus,
    MessageType,
    PlatformStreamEvent,
    StreamArchiveStatus,
)
from services.web.ai_assistant.handlers import attachment_handler_registry
from services.web.ai_assistant.models import Attachment, Conversation, Message
from services.web.ai_assistant.schemas import (
    UIStreamEvent,
    parse_stream_config,
    serialize_stream_event,
)
from services.web.ai_assistant.services import AttachmentService
from services.web.ai_assistant.streaming import RedisLiveStore
from services.web.ai_assistant.streaming.archive import _encoded_archive_bytes
from tests.test_ai_assistant.celery_integration import (
    running_celery_worker,
    wait_for_snapshot,
)
from tests.test_ai_assistant.special_handlers import (
    SPECIAL_CAPACITY_QUEUE,
    SpecialCapacityHandler,
)
from tests.test_ai_assistant.stream_cleanup import delete_attachment_stream_keys

pytestmark = pytest.mark.special


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


def stream_payload_size(data: object) -> int:
    return len(serialize_stream_event(UIStreamEvent(data=data), include_stream_id=False))


def data_with_payload_size(size: int) -> dict:
    data = {"p": ""}
    current = stream_payload_size(data)
    if current > size:
        raise ValueError(f"最小 payload {current} 已超过目标 {size}")
    data = {"p": "x" * (size - current)}
    actual = stream_payload_size(data)
    if actual != size:
        raise AssertionError(f"payload 大小 {actual} != {size}")
    return data


class StreamCapacitySpecialTest(TransactionTestCase):
    """线程 Worker 下验收四类容量边界的刚好等于与超过 1 字节/1 条。"""

    available_apps = ["services.web.ai_assistant"]
    reset_sequences = True

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.worker_context = running_celery_worker(queue_name=SPECIAL_CAPACITY_QUEUE)
        cls.worker_context.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.worker_context.__exit__(None, None, None)
        assert_queue_absent(SPECIAL_CAPACITY_QUEUE)
        super().tearDownClass()

    def setUp(self):
        self.user = "special-capacity-user"
        self.conversation = Conversation.objects.create(created_by=self.user, updated_by=self.user)
        attachment_handler_registry.register(SpecialCapacityHandler())

    def tearDown(self):
        leftovers = delete_attachment_stream_keys(
            attachment_uids=Attachment.objects.filter(is_stream=True).values_list("uid", flat=True)
        )
        attachment_handler_registry.unregister(AttachmentType.AI_ANALYSIS)
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

    def create_attachment(self, *, events: list) -> Attachment:
        return AttachmentService(user=self.user).create(
            source_message_uid=str(self.create_source_message().uid),
            attachment_type=AttachmentType.AI_ANALYSIS,
            input_data={"events": events},
        )

    def wait_success(self, attachment: Attachment) -> Attachment:
        return wait_for_snapshot(
            model=Attachment,
            instance_id=attachment.id,
            predicate=lambda value: value.status == ExecutionStatus.SUCCESS,
        )

    def redis_business_events(self, attachment: Attachment) -> list:
        config = parse_stream_config(attachment.stream_config)
        self.assertIsNotNone(config)
        events = RedisLiveStore().read(redis_key=config.redis_key, after_id="0-0", block_ms=1).events
        return [event for event in events if event.event is None]

    def archived_business(self, attachment: Attachment) -> list:
        return [event for event in attachment.stream_archive if event.get("event") is None]

    def assert_success_with_terminal(self, attachment: Attachment, *, archive_status: str) -> None:
        config = parse_stream_config(attachment.stream_config)
        self.assertEqual(attachment.status, ExecutionStatus.SUCCESS)
        self.assertEqual(attachment.output_data, {"content": "capacity:done"})
        self.assertEqual(config.archive_status, archive_status)
        self.assertEqual(attachment.stream_archive[-1]["event"], PlatformStreamEvent.STREAM_END)

    def test_max_event_bytes_equal_and_over_by_one(self):
        equal_data = data_with_payload_size(64)
        over_data = data_with_payload_size(65)

        with override_settings(AI_ASSISTANT_STREAM_MAX_EVENT_BYTES=64):
            equal = self.wait_success(self.create_attachment(events=[equal_data]))
            over = self.wait_success(self.create_attachment(events=[over_data]))

        self.assert_success_with_terminal(equal, archive_status=StreamArchiveStatus.COMPLETE)
        self.assertEqual([event["data"] for event in self.archived_business(equal)], [equal_data])
        self.assertEqual(len(self.redis_business_events(equal)), 1)

        self.assert_success_with_terminal(over, archive_status=StreamArchiveStatus.TRUNCATED)
        self.assertEqual(self.archived_business(over), [])
        self.assertEqual(self.redis_business_events(over), [])

    def test_max_events_equal_and_over_by_one(self):
        events = [{"index": index} for index in range(3)]

        with override_settings(AI_ASSISTANT_STREAM_MAX_EVENTS=2):
            equal = self.wait_success(self.create_attachment(events=events[:2]))
            over = self.wait_success(self.create_attachment(events=events))

        self.assert_success_with_terminal(equal, archive_status=StreamArchiveStatus.COMPLETE)
        self.assertEqual([event["data"]["index"] for event in self.archived_business(equal)], [0, 1])
        self.assertEqual(len(self.redis_business_events(equal)), 2)

        self.assert_success_with_terminal(over, archive_status=StreamArchiveStatus.TRUNCATED)
        self.assertEqual([event["data"]["index"] for event in self.archived_business(over)], [0, 1])
        self.assertEqual([event.data["index"] for event in self.redis_business_events(over)], [0, 1, 2])

    def test_redis_max_bytes_equal_and_over_by_one(self):
        first = data_with_payload_size(40)
        first_size = stream_payload_size(first)
        over = data_with_payload_size(first_size + 1)

        with override_settings(AI_ASSISTANT_STREAM_REDIS_MAX_BYTES=first_size):
            equal = self.wait_success(self.create_attachment(events=[first]))
            overflow = self.wait_success(self.create_attachment(events=[over]))

        self.assert_success_with_terminal(equal, archive_status=StreamArchiveStatus.COMPLETE)
        self.assertIsNotNone(self.redis_business_events(equal)[0].stream_id)
        self.assertEqual(len(self.archived_business(equal)), 1)

        self.assert_success_with_terminal(overflow, archive_status=StreamArchiveStatus.DEGRADED)
        self.assertEqual(self.redis_business_events(overflow), [])
        self.assertEqual([event["data"] for event in self.archived_business(overflow)], [over])
        self.assertIsNone(self.archived_business(overflow)[0].get("stream_id"))

    def test_archive_max_bytes_equal_and_over_by_one(self):
        payload = {"n": 1}
        probe = self.wait_success(self.create_attachment(events=[payload]))
        probe_events = [UIStreamEvent.model_validate(event) for event in self.archived_business(probe)]
        equal_bytes = _encoded_archive_bytes(probe_events)
        self.assertGreater(equal_bytes, 2)

        with override_settings(AI_ASSISTANT_STREAM_ARCHIVE_MAX_BYTES=equal_bytes):
            equal = self.wait_success(self.create_attachment(events=[payload]))
        with override_settings(AI_ASSISTANT_STREAM_ARCHIVE_MAX_BYTES=equal_bytes - 1):
            over = self.wait_success(self.create_attachment(events=[payload]))

        self.assert_success_with_terminal(equal, archive_status=StreamArchiveStatus.COMPLETE)
        self.assertEqual([event["data"] for event in self.archived_business(equal)], [payload])
        self.assertEqual(len(self.redis_business_events(equal)), 1)

        self.assert_success_with_terminal(over, archive_status=StreamArchiveStatus.TRUNCATED)
        self.assertEqual(self.archived_business(over), [])
        self.assertEqual(len(self.redis_business_events(over)), 1)
        self.assertEqual(over.output_data, {"content": "capacity:done"})

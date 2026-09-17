import os

import pytest
from django.conf import settings
from django.test import SimpleTestCase, TransactionTestCase

from services.web.ai_assistant.constants import (
    AttachmentType,
    ExecutionStatus,
    MessageType,
    PlatformStreamEvent,
)
from services.web.ai_assistant.handlers import attachment_handler_registry
from services.web.ai_assistant.models import Attachment, Conversation, Message
from services.web.ai_assistant.services import AttachmentService
from services.web.ai_assistant.streaming import RedisLiveStore
from tests.test_ai_assistant.celery_integration import wait_for_snapshot
from tests.test_ai_assistant.special.process_worker import (
    delete_worker_queue,
    kill_worker_process,
    running_worker_process,
    sanitize_special_worker_log_lines,
    using_test_broker,
)
from tests.test_ai_assistant.special_handlers import (
    SPECIAL_REDELIVERY_QUEUE,
    SpecialRedeliveryHandler,
    clear_redelivery_control,
    read_redelivery_execution_ids,
    read_redelivery_redis_keys,
    wait_for_redelivery_started,
)
from tests.test_ai_assistant.stream_cleanup import delete_attachment_stream_keys

pytestmark = pytest.mark.special


class WorkerProcessLifecycleTest(SimpleTestCase):
    def test_sanitize_special_worker_log_drops_payload_lines(self):
        self.assertEqual(
            sanitize_special_worker_log_lines(
                [
                    "ready.\n",
                    '{"data": {"step": 1}}\n',
                    "task data=secret\n",
                    "ok\n",
                ]
            ),
            ["ready.\n", "ok\n"],
        )

    def test_running_worker_process_can_be_killed_without_leaving_orphans(self):
        queue_name = f"{settings.CELERY_TEST_QUEUE_PREFIX}_{os.getpid()}_redelivery_lifecycle"
        with running_worker_process(queue_name=queue_name) as process:
            pid = process.pid
            kill_worker_process(process)
            self.assertIsNotNone(process.poll())
            self.assertNotEqual(process.returncode, 0)
        self.assertIsNotNone(process.poll())
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)
        delete_worker_queue(queue_name)


class WorkerRedeliveryTest(TransactionTestCase):
    """SIGKILL 后 RabbitMQ 重投同一 task_id，并切换到新的流式 execution。"""

    available_apps = ["services.web.ai_assistant"]
    reset_sequences = True

    def setUp(self):
        self.user = "special-redelivery-user"
        self.conversation = Conversation.objects.create(created_by=self.user, updated_by=self.user)
        attachment_handler_registry.unregister(AttachmentType.AI_ANALYSIS)
        attachment_handler_registry.register(SpecialRedeliveryHandler())
        self.broker_context = using_test_broker(queue_name=SPECIAL_REDELIVERY_QUEUE)
        self.broker_context.__enter__()

    def tearDown(self):
        leftovers = delete_attachment_stream_keys(
            attachment_uids=Attachment.objects.filter(is_stream=True).values_list("uid", flat=True)
        )
        for task_id in Attachment.objects.exclude(task_id="").values_list("task_id", flat=True):
            clear_redelivery_control(task_id)
        attachment_handler_registry.unregister(AttachmentType.AI_ANALYSIS)
        self.broker_context.__exit__(None, None, None)
        delete_worker_queue(SPECIAL_REDELIVERY_QUEUE)
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

    def test_sigkill_redelivers_same_task_and_rotates_execution(self):
        source_message = self.create_source_message()
        attachment = AttachmentService(user=self.user).create(
            source_message_uid=str(source_message.uid),
            attachment_type=AttachmentType.AI_ANALYSIS,
            input_data={"text": "redeliver"},
        )
        original_task_id = attachment.task_id
        self.assertEqual(attachment.status, ExecutionStatus.PROCESSING)

        with running_worker_process(queue_name=SPECIAL_REDELIVERY_QUEUE) as worker_a:
            wait_for_redelivery_started(task_id=original_task_id)
            old_execution_ids = read_redelivery_execution_ids(original_task_id)
            old_redis_keys = read_redelivery_redis_keys(original_task_id)
            self.assertEqual(len(old_execution_ids), 1)
            old_execution_id = old_execution_ids[0]
            old_redis_key = old_redis_keys[0]
            kill_worker_process(worker_a)

        with running_worker_process(queue_name=SPECIAL_REDELIVERY_QUEUE):
            completed = wait_for_snapshot(
                model=Attachment,
                instance_id=attachment.id,
                predicate=lambda value: value.status == ExecutionStatus.SUCCESS,
            )

        self.assertEqual(completed.task_id, original_task_id)
        execution_ids = read_redelivery_execution_ids(original_task_id)
        redis_keys = read_redelivery_redis_keys(original_task_id)
        self.assertGreaterEqual(len(execution_ids), 2)
        self.assertNotEqual(execution_ids[0], execution_ids[1])
        self.assertEqual(execution_ids[0], old_execution_id)

        old_events = RedisLiveStore().read(redis_key=old_redis_key, after_id="0-0", block_ms=1).events
        self.assertTrue(any(event.event == PlatformStreamEvent.STREAM_RESET for event in old_events))
        self.assertEqual(completed.output_data, {"content": "redelivery:success"})
        self.assertEqual(len(completed.stream_archive), 2)
        self.assertIsNone(completed.stream_archive[0]["event"])
        self.assertEqual(completed.stream_archive[0]["data"], {"attempt": 2})
        self.assertEqual(completed.stream_archive[-1]["event"], PlatformStreamEvent.STREAM_END)
        self.assertEqual(completed.stream_archive[-1]["data"], {"status": ExecutionStatus.SUCCESS})
        self.assertFalse(any(event.get("data") == {"attempt": 1} for event in completed.stream_archive))
        self.assertEqual(redis_keys[0], old_redis_key)
        self.assertNotEqual(redis_keys[1], old_redis_key)

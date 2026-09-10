from unittest import mock

import pytest
from django.conf import settings
from django.db import DatabaseError
from django.test import TransactionTestCase
from redis.exceptions import RedisError

from services.web.ai_assistant.constants import (
    AttachmentType,
    ExecutionStatus,
    MessageType,
    PlatformStreamEvent,
    StreamArchiveStatus,
)
from services.web.ai_assistant.handlers import attachment_handler_registry
from services.web.ai_assistant.models import Attachment, Conversation, Message
from services.web.ai_assistant.schemas import parse_stream_config
from services.web.ai_assistant.services import AttachmentService
from services.web.ai_assistant.streaming import (
    AttachmentArchiveStore,
    RedisLiveStore,
    UIStreamRuntime,
)
from tests.test_ai_assistant import special_handlers
from tests.test_ai_assistant.celery_integration import (
    once_then_original,
    reset_task_postrun,
    running_celery_worker,
    wait_for_snapshot,
    wait_for_task_postrun,
)
from tests.test_ai_assistant.special_handlers import (
    SPECIAL_FAILURE_QUEUE,
    SpecialCheckpointFailOnceHandler,
    SpecialFinalizeFailOnceHandler,
    SpecialRedisDegradedHandler,
    SpecialRetryRaceHandler,
    release_competition_observations,
    reset_checkpoint_observations,
    reset_competition_observations,
)
from tests.test_ai_assistant.stream_cleanup import delete_attachment_stream_keys

pytestmark = pytest.mark.special


class StreamFailureSpecialTest(TransactionTestCase):
    """线程 Worker 下验证 Redis/MySQL 故障降级与重试竞争收敛。"""

    available_apps = ["services.web.ai_assistant"]
    reset_sequences = True

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.worker_context = running_celery_worker(queue_name=SPECIAL_FAILURE_QUEUE)
        cls.worker_context.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.worker_context.__exit__(None, None, None)
        super().tearDownClass()

    def setUp(self):
        self.user = "special-failure-user"
        self.conversation = Conversation.objects.create(created_by=self.user, updated_by=self.user)
        reset_checkpoint_observations()
        reset_competition_observations()

    def tearDown(self):
        release_competition_observations()
        leftovers = delete_attachment_stream_keys(
            attachment_uids=Attachment.objects.filter(is_stream=True).values_list("uid", flat=True)
        )
        attachment_handler_registry.unregister(AttachmentType.AI_ANALYSIS)
        reset_checkpoint_observations()
        reset_competition_observations()
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

    def test_redis_append_failure_still_succeeds_with_degraded_archive(self):
        attachment_handler_registry.register(SpecialRedisDegradedHandler())
        with mock.patch.object(RedisLiveStore, "append", side_effect=RedisError("redis down")):
            attachment = self.create_attachment(text="redis")
            completed = wait_for_snapshot(
                model=Attachment,
                instance_id=attachment.id,
                predicate=lambda value: value.status == ExecutionStatus.SUCCESS,
            )

        config = parse_stream_config(completed.stream_config)
        self.assertEqual(completed.output_data, {"content": "redis-degraded:success"})
        self.assertEqual(config.archive_status, StreamArchiveStatus.DEGRADED)
        self.assertEqual(completed.stream_archive[0]["data"], {"step": 1})
        self.assertIsNone(completed.stream_archive[0]["stream_id"])
        self.assertEqual(completed.stream_archive[-1]["event"], PlatformStreamEvent.STREAM_END)
        self.assertTrue(all(event.get("stream_id") is None for event in completed.stream_archive))

    def test_checkpoint_first_failure_keeps_pending_and_finalizes_ordered_events(self):
        attachment_handler_registry.register(SpecialCheckpointFailOnceHandler())
        fail_once = once_then_original(
            AttachmentArchiveStore.checkpoint,
            exc=DatabaseError("temporary checkpoint failure"),
        )
        with mock.patch.object(AttachmentArchiveStore, "checkpoint", autospec=True, side_effect=fail_once):
            attachment = self.create_attachment(text="checkpoint")
            completed = wait_for_snapshot(
                model=Attachment,
                instance_id=attachment.id,
                predicate=lambda value: value.status == ExecutionStatus.SUCCESS,
            )

        self.assertGreaterEqual(fail_once.attempts["count"], 1)
        self.assertEqual(special_handlers.checkpoint_pending_after_send, UIStreamRuntime.CHECKPOINT_EVENT_COUNT)
        self.assertEqual(completed.output_data, {"content": "checkpoint:success"})
        business = [event for event in completed.stream_archive if event["event"] is None]
        self.assertEqual(
            [event["data"]["index"] for event in business], list(range(UIStreamRuntime.CHECKPOINT_EVENT_COUNT))
        )
        self.assertEqual(completed.stream_archive[-1]["event"], PlatformStreamEvent.STREAM_END)

    def test_finalize_first_failure_retries_with_new_execution(self):
        attachment_handler_registry.register(SpecialFinalizeFailOnceHandler())
        fail_once = once_then_original(
            AttachmentArchiveStore.finalize,
            exc=DatabaseError("temporary finalize failure"),
        )
        with mock.patch.object(AttachmentArchiveStore, "finalize", autospec=True, side_effect=fail_once):
            attachment = self.create_attachment(text="finalize")
            original_task_id = attachment.task_id
            completed = wait_for_snapshot(
                model=Attachment,
                instance_id=attachment.id,
                predicate=lambda value: value.status == ExecutionStatus.SUCCESS,
            )
            wait_for_task_postrun(task_id=original_task_id, expected_count=2)
            completed.refresh_from_db()

        self.assertEqual(fail_once.attempts["count"], 2)
        self.assertEqual(completed.task_id, original_task_id)
        self.assertEqual(completed.status, ExecutionStatus.SUCCESS)
        self.assertEqual(completed.output_data, {"content": "finalize:success"})
        business = [event for event in completed.stream_archive if event["event"] is None]
        self.assertEqual(len(business), 1)
        self.assertEqual(business[0]["data"], {"attempt": 1})
        self.assertEqual(completed.stream_archive[-1]["event"], PlatformStreamEvent.STREAM_END)

        self.assertGreaterEqual(len(set(special_handlers.competition_execution_ids)), 2)
        old_redis_key = special_handlers.competition_task_ids[0]
        old_events = RedisLiveStore().read(redis_key=old_redis_key, after_id="0-0", block_ms=1).events
        self.assertTrue(any(event.event == PlatformStreamEvent.STREAM_RESET for event in old_events))
        config = parse_stream_config(completed.stream_config)
        self.assertNotEqual(config.redis_key, old_redis_key)

    def test_manual_retry_fences_old_worker_and_keeps_new_execution(self):
        handler = attachment_handler_registry.register(SpecialRetryRaceHandler())
        attachment = self.create_attachment(text="race")
        old_task_id = attachment.task_id
        self.assertTrue(special_handlers.competition_hold.wait(timeout=settings.CELERY_TEST_TASK_TIMEOUT))

        reset_task_postrun(task_id=old_task_id)
        handler.async_task.apply_async(
            kwargs={"attachment_id": attachment.id, "task_id": old_task_id},
            task_id=old_task_id,
        )
        failed = wait_for_snapshot(
            model=Attachment,
            instance_id=attachment.id,
            predicate=lambda value: value.status == ExecutionStatus.FAILED,
        )
        self.assertEqual(failed.task_id, old_task_id)

        retried = AttachmentService(user=self.user).retry(attachment_uid=str(attachment.uid))
        self.assertNotEqual(retried.task_id, old_task_id)
        special_handlers.competition_release.set()
        completed = wait_for_snapshot(
            model=Attachment,
            instance_id=attachment.id,
            predicate=lambda value: value.status == ExecutionStatus.SUCCESS,
        )
        # 数据库已进入新任务终态时，旧 Worker 仍可能处于 stale 收尾阶段；等待所有
        # 同 task ID 投递退出后再清理共享观察量，避免污染后续专项用例。
        wait_for_task_postrun(task_id=old_task_id, expected_count=2)
        wait_for_task_postrun(task_id=retried.task_id)
        completed.refresh_from_db()

        self.assertEqual(completed.task_id, retried.task_id)
        self.assertEqual(completed.output_data, {"content": "race:new"})
        self.assertGreaterEqual(len(set(special_handlers.competition_execution_ids)), 2)
        self.assertIn(old_task_id, special_handlers.competition_task_ids)
        self.assertIn(retried.task_id, special_handlers.competition_task_ids)
        business = [event for event in completed.stream_archive if event["event"] is None]
        self.assertEqual(len(business), 1)
        self.assertEqual(business[0]["data"], {"delivery": 3})
        self.assertEqual(completed.stream_archive[-1]["event"], PlatformStreamEvent.STREAM_END)
        self.assertFalse(any(event.get("data") == {"delivery": 1} for event in completed.stream_archive))

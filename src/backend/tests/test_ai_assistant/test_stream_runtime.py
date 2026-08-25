from datetime import timedelta
from unittest import mock

from django.db import DatabaseError
from django.test import TransactionTestCase
from django.test.utils import override_settings
from django.utils import timezone
from redis.exceptions import RedisError

from services.web.ai_assistant.constants import (
    AttachmentType,
    ExecutionStatus,
    MessageType,
    PlatformStreamEvent,
    StreamArchiveStatus,
)
from services.web.ai_assistant.exceptions import (
    InvalidStreamEvent,
    StaleAttachmentTask,
    StreamRuntimeClosed,
)
from services.web.ai_assistant.models import Attachment, Conversation, Message
from services.web.ai_assistant.schemas import (
    UIStreamEvent,
    parse_stream_config,
    serialize_stream_event,
)
from services.web.ai_assistant.streaming import (
    AttachmentArchiveStore,
    RedisLiveStore,
    UIStreamRuntime,
)


class StreamRuntimeTestCase(TransactionTestCase):
    """Runtime 直连真实 Redis 与 MySQL；只有故障注入使用 mock。"""

    # Runtime 测试仅使用 AI 助手模型，禁止 flush 其他应用的迁移数据。
    available_apps = ["services.web.ai_assistant"]

    def setUp(self):
        self.user = "alice"
        self.redis_store = RedisLiveStore()
        self.archive_store = AttachmentArchiveStore()
        self.client = self.redis_store._client
        self.source_message = Message.objects.create(
            conversation=Conversation.objects.create(created_by=self.user, updated_by=self.user),
            message_type=MessageType.LOG_SEARCH,
            status=ExecutionStatus.SUCCESS,
            task_id="source-task",
            input_data={"text": "query"},
            context_data={"prefix": "source"},
            output_data={"content": "source"},
            created_by=self.user,
            updated_by=self.user,
        )
        self.attachment = self.create_attachment()
        self.started_runtimes: list[UIStreamRuntime] = []

    def tearDown(self):
        # 只清理本次测试涉及的 key，避免影响共享 Redis 中的其他数据。
        physical_keys = {
            self.redis_store.physical_key(runtime.binding.config.redis_key) for runtime in self.started_runtimes
        }
        if physical_keys:
            self.client.delete(*physical_keys)

    def create_attachment(
        self, *, task_id: str = "task-current", is_stream: bool = True, status: str = ExecutionStatus.PROCESSING
    ) -> Attachment:
        return Attachment.objects.create(
            source_message=self.source_message,
            attachment_type=AttachmentType.AI_ANALYSIS,
            title="AI 分析",
            status=status,
            task_id=task_id,
            input_data={"text": "hello"},
            context_data={"prefix": "async"},
            output_data=None,
            is_stream=is_stream,
            created_by=self.user,
            updated_by=self.user,
        )

    def start_runtime(self, *, attachment: Attachment | None = None, **kwargs) -> UIStreamRuntime:
        attachment = attachment or self.attachment
        runtime = UIStreamRuntime.start(
            attachment_id=attachment.id,
            task_id=attachment.task_id,
            redis_store=kwargs.pop("redis_store", self.redis_store),
            archive_store=kwargs.pop("archive_store", self.archive_store),
            **kwargs,
        )
        self.started_runtimes.append(runtime)
        return runtime

    def redis_events(self, runtime: UIStreamRuntime) -> list[UIStreamEvent]:
        return self.redis_store.read(
            redis_key=runtime.binding.config.redis_key,
            after_id="0-0",
            block_ms=1,
        ).events

    def send_and_checkpoint(self, runtime: UIStreamRuntime, data: dict) -> UIStreamEvent | None:
        """通过真实 ``send`` 自动阈值触发 checkpoint，不依赖测试专用生产接口。"""

        with mock.patch.object(runtime, "CHECKPOINT_EVENT_COUNT", 1):
            return runtime.send(data)

    def archived_events(self, attachment: Attachment | None = None) -> list[dict]:
        attachment = attachment or self.attachment
        attachment.refresh_from_db()
        return attachment.stream_archive


class StreamRuntimeStartTest(StreamRuntimeTestCase):
    def test_start_rotates_execution_without_creating_redis_stream_until_send(self):
        runtime = self.start_runtime()

        self.attachment.refresh_from_db()
        config = parse_stream_config(self.attachment.stream_config)
        self.assertEqual(runtime.binding.config, config)
        self.assertEqual(runtime.binding.task_id, self.attachment.task_id)
        self.assertFalse(self.client.exists(self.redis_store.physical_key(config.redis_key)))
        self.assertEqual(runtime.pending_count, 0)
        self.assertEqual(runtime.archive_status, StreamArchiveStatus.COMPLETE)
        self.assertFalse(runtime.closed)

    def test_start_rejects_non_stream_or_stale_attachment(self):
        cases = {
            "not_stream": self.create_attachment(task_id="task-sync", is_stream=False),
            "terminal": self.create_attachment(task_id="task-done", status=ExecutionStatus.SUCCESS),
        }
        for case_name, attachment in cases.items():
            with self.subTest(case=case_name):
                with self.assertRaises(StaleAttachmentTask):
                    self.start_runtime(attachment=attachment)

    def test_first_start_does_not_access_redis(self):
        with mock.patch.object(RedisLiveStore, "append", side_effect=RedisError("redis down")) as append:
            runtime = self.start_runtime()

        append.assert_not_called()
        self.assertEqual(runtime.archive_status, StreamArchiveStatus.COMPLETE)
        self.assertFalse(runtime.closed)
        self.attachment.refresh_from_db()
        self.assertEqual(self.attachment.status, ExecutionStatus.PROCESSING)

    def test_start_of_second_execution_resets_only_old_stream_and_keeps_new_archive_empty(self):
        runtime_a = self.start_runtime()
        self.send_and_checkpoint(runtime_a, {"content": "old"})

        runtime_b = self.start_runtime()

        old_events = self.redis_events(runtime_a)
        new_events = self.redis_events(runtime_b)
        self.assertEqual(old_events[-1].event, PlatformStreamEvent.STREAM_RESET)
        self.assertEqual(old_events[-1].data, {"reason": "execution_replaced"})
        self.assertNotIn("redis_key", old_events[-1].data)
        self.assertEqual(new_events, [])
        self.assertEqual(self.archived_events(), [])

        self.send_and_checkpoint(runtime_b, {"content": "new"})
        archived = self.archived_events()
        self.assertEqual(len(archived), 1)
        self.assertIsNone(archived[0]["event"])
        self.assertEqual(archived[0]["data"], {"content": "new"})

    def test_start_of_second_execution_survives_reset_publish_failure(self):
        runtime_a = self.start_runtime()

        with mock.patch.object(RedisLiveStore, "append", side_effect=RedisError("redis down")):
            runtime_b = self.start_runtime()

        self.assertEqual(runtime_b.archive_status, StreamArchiveStatus.DEGRADED)
        self.assertFalse(runtime_b.closed)
        self.assertEqual(self.redis_events(runtime_a), [])


class StreamRuntimeSendTest(StreamRuntimeTestCase):
    def test_send_writes_redis_immediately_and_buffers_for_archive(self):
        runtime = self.start_runtime()

        event = runtime.send({"content": "A"})

        self.assertIsNone(event.event)
        self.assertIsNotNone(event.stream_id)
        self.assertEqual(runtime.pending_count, 1)
        self.assertEqual(self.redis_events(runtime), [event])
        # 未达到自动 checkpoint 阈值前不落库，避免每条事件一次 UPDATE。
        self.assertEqual(self.archived_events(), [])

    def test_business_api_only_accepts_data(self):
        runtime = self.start_runtime()

        event = runtime.send({"content": "A"})

        self.assertIsNone(event.event)
        self.assertFalse(hasattr(runtime, "publish"))
        self.assertFalse(hasattr(runtime, "flush"))
        self.assertFalse(hasattr(runtime, "flush_best_effort"))

    def test_send_auto_checkpoints_when_event_count_threshold_reached(self):
        runtime = self.start_runtime()

        for index in range(UIStreamRuntime.CHECKPOINT_EVENT_COUNT - 1):
            runtime.send({"index": index})
        self.assertEqual(runtime.pending_count, UIStreamRuntime.CHECKPOINT_EVENT_COUNT - 1)
        self.assertEqual(self.archived_events(), [])

        runtime.send({"index": UIStreamRuntime.CHECKPOINT_EVENT_COUNT - 1})

        self.assertEqual(runtime.pending_count, 0)
        archived = self.archived_events()
        self.assertEqual(
            [item["data"]["index"] for item in archived],
            list(range(UIStreamRuntime.CHECKPOINT_EVENT_COUNT)),
        )
        self.assertTrue(all("type" not in item for item in archived))

    def test_send_auto_checkpoints_when_byte_threshold_reached(self):
        runtime = self.start_runtime()
        chunk = "x" * (100 * 1024)

        runtime.send({"content": chunk})
        runtime.send({"content": chunk})
        self.assertEqual(runtime.pending_count, 2)

        runtime.send({"content": chunk})

        self.assertGreater(UIStreamRuntime.CHECKPOINT_BYTES, 0)
        self.assertEqual(runtime.pending_count, 0)
        self.assertEqual(len(self.archived_events()), 3)

    def test_low_frequency_event_checkpoints_by_activity_interval(self):
        runtime = self.start_runtime()
        old_activity = timezone.now() - timedelta(hours=1)
        Attachment.objects.filter(id=self.attachment.id).update(last_activity_at=old_activity)
        runtime._last_activity_checkpoint_at -= 61

        with override_settings(AI_ASSISTANT_STREAM_ACTIVITY_INTERVAL_SECONDS=60):
            runtime.send({"content": "low frequency"})

        self.attachment.refresh_from_db()
        self.assertEqual(runtime.pending_count, 0)
        self.assertEqual(self.archived_events()[0]["data"], {"content": "low frequency"})
        self.assertGreater(self.attachment.last_activity_at, old_activity)

    def test_truncated_archive_still_refreshes_activity_for_live_events(self):
        runtime = self.start_runtime()
        old_activity = timezone.now() - timedelta(hours=1)
        Attachment.objects.filter(id=self.attachment.id).update(last_activity_at=old_activity)
        runtime._archive_stopped = True
        runtime._last_activity_checkpoint_at -= 61

        with override_settings(AI_ASSISTANT_STREAM_ACTIVITY_INTERVAL_SECONDS=60):
            runtime.send({"content": "still running"})

        self.attachment.refresh_from_db()
        self.assertEqual(self.archived_events(), [])
        self.assertGreater(self.attachment.last_activity_at, old_activity)

    def test_send_rejects_non_json_data_as_integration_error(self):
        runtime = self.start_runtime()

        for invalid_data in (object(), {"value": object()}, float("nan"), float("inf"), bytes(1)):
            with self.subTest(invalid_data=type(invalid_data).__name__):
                with self.assertRaises(InvalidStreamEvent):
                    runtime.send(invalid_data)

        # 接入错误不得污染缓冲或降级归档状态。
        self.assertEqual(runtime.pending_count, 0)
        self.assertEqual(runtime.archive_status, StreamArchiveStatus.COMPLETE)

    def test_send_after_close_raises_runtime_closed(self):
        runtime = self.start_runtime()
        runtime.finish_retry()

        with self.assertRaises(StreamRuntimeClosed):
            runtime.send({})


class StreamRuntimeDegradationTest(StreamRuntimeTestCase):
    def test_redis_error_from_business_append_degrades_but_keeps_event_in_archive(self):
        runtime = self.start_runtime()

        with mock.patch.object(RedisLiveStore, "append", side_effect=RedisError("redis down")):
            event = runtime.send({"content": "A"})

        # 实时推送失败的事件没有 Redis 游标，但仍必须落归档。
        self.assertIsNone(event.stream_id)
        self.assertEqual(runtime.archive_status, StreamArchiveStatus.DEGRADED)
        runtime.finish_retry()
        archived = self.archived_events()
        self.assertEqual(len(archived), 1)
        self.assertIsNone(archived[0]["stream_id"])

    def test_os_error_from_business_append_degrades_and_keeps_buffer(self):
        runtime = self.start_runtime()

        with mock.patch.object(RedisLiveStore, "append", side_effect=OSError("connection reset")):
            event = runtime.send({"content": "A"})

        self.assertIsNone(event.stream_id)
        self.assertEqual(runtime.pending_count, 1)
        self.assertEqual(runtime.archive_status, StreamArchiveStatus.DEGRADED)

    def test_business_append_implementation_error_propagates(self):
        runtime = self.start_runtime()

        with mock.patch.object(RedisLiveStore, "append", side_effect=ValueError("invalid redis payload")):
            with self.assertRaises(ValueError):
                runtime.send({"content": "A"})

        self.assertEqual(runtime.pending_count, 0)
        self.assertEqual(runtime.archive_status, StreamArchiveStatus.COMPLETE)

    def test_stale_from_automatic_checkpoint_propagates(self):
        runtime = self.start_runtime()
        with override_settings(AI_ASSISTANT_STREAM_MAX_EVENTS=100):
            with mock.patch.object(runtime, "CHECKPOINT_EVENT_COUNT", 1):
                with mock.patch.object(AttachmentArchiveStore, "checkpoint", side_effect=StaleAttachmentTask()):
                    with self.assertRaises(StaleAttachmentTask):
                        runtime.send({"content": "old"})

        self.assertEqual(runtime.pending_count, 1)
        self.assertEqual(runtime.archive_status, StreamArchiveStatus.COMPLETE)

    def test_database_error_from_automatic_checkpoint_degrades_and_keeps_buffer(self):
        runtime = self.start_runtime()
        with mock.patch.object(runtime, "CHECKPOINT_EVENT_COUNT", 1):
            with mock.patch.object(AttachmentArchiveStore, "checkpoint", side_effect=DatabaseError("db down")):
                event = runtime.send({"content": "A"})

        self.assertIsNotNone(event.stream_id)
        self.assertEqual(runtime.pending_count, 1)
        self.assertEqual(runtime.archive_status, StreamArchiveStatus.DEGRADED)

    def test_value_error_from_automatic_checkpoint_propagates(self):
        runtime = self.start_runtime()
        with mock.patch.object(runtime, "CHECKPOINT_EVENT_COUNT", 1):
            with mock.patch.object(AttachmentArchiveStore, "checkpoint", side_effect=ValueError("invalid archive")):
                with self.assertRaises(ValueError):
                    runtime.send({"content": "A"})

        self.assertEqual(runtime.pending_count, 1)
        self.assertEqual(runtime.archive_status, StreamArchiveStatus.COMPLETE)

    def test_old_execution_is_fenced_when_automatic_checkpoint_reaches_mysql(self):
        runtime_a = self.start_runtime()
        self.start_runtime()

        with mock.patch.object(runtime_a, "CHECKPOINT_EVENT_COUNT", 1):
            with self.assertRaises(StaleAttachmentTask):
                runtime_a.send({"content": "old"})

    def test_automatic_checkpoint_retries_buffer_without_duplication(self):
        runtime = self.start_runtime()

        with mock.patch.object(runtime, "CHECKPOINT_EVENT_COUNT", 1):
            with mock.patch.object(AttachmentArchiveStore, "checkpoint", side_effect=DatabaseError("db down")):
                runtime.send({"content": "A"})

        self.assertEqual(runtime.pending_count, 1)
        self.assertEqual(runtime.archive_status, StreamArchiveStatus.DEGRADED)

        self.send_and_checkpoint(runtime, {"content": "B"})

        self.assertEqual(runtime.pending_count, 0)
        self.assertEqual([item["data"]["content"] for item in self.archived_events()], ["A", "B"])


class StreamRuntimeCapacityTest(StreamRuntimeTestCase):
    def test_oversized_single_event_is_dropped_and_marks_truncated(self):
        runtime = self.start_runtime()

        with override_settings(AI_ASSISTANT_STREAM_MAX_EVENT_BYTES=1024):
            event = runtime.send({"content": "x" * 2048})

        self.assertIsNone(event)
        self.assertEqual(runtime.pending_count, 0)
        self.assertEqual(runtime.archive_status, StreamArchiveStatus.TRUNCATED)
        self.assertEqual(self.redis_events(runtime), [])

    def test_finalize_persists_runtime_archive_status_without_pending_events(self):
        runtime = self.start_runtime()

        with override_settings(AI_ASSISTANT_STREAM_MAX_EVENT_BYTES=1024):
            runtime.send({"content": "x" * 2048})
        runtime.finish_success(output_data={"content": "done"}, updated_by=self.user)

        self.attachment.refresh_from_db()
        config = parse_stream_config(self.attachment.stream_config)
        self.assertEqual(config.archive_status, StreamArchiveStatus.TRUNCATED)

    def test_business_event_count_cap_stops_archiving_without_failing_task(self):
        runtime = self.start_runtime()

        with override_settings(AI_ASSISTANT_STREAM_MAX_EVENTS=2):
            first = runtime.send({"index": 0})
            second = runtime.send({"index": 1})
            third = runtime.send({"index": 2})
            runtime.finish_success(output_data={"content": "done"}, updated_by=self.user)

        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        # 超过条数上限后停止归档，但实时流仍可继续观看。
        self.assertIsNotNone(third)
        self.assertEqual(runtime.archive_status, StreamArchiveStatus.TRUNCATED)
        business_events = [item for item in self.archived_events() if item["event"] is None]
        self.assertEqual([item["data"]["index"] for item in business_events], [0, 1])
        live_business_events = [event for event in self.redis_events(runtime) if event.event is None]
        self.assertEqual(len(live_business_events), 3)

    def test_redis_byte_cap_stops_live_write_but_keeps_archiving(self):
        runtime = self.start_runtime()
        first_data = {"content": "x" * 100}
        first_payload_size = len(serialize_stream_event(UIStreamEvent(data=first_data), include_stream_id=False))

        # 上限刚好容纳第一条事件，第二条触发实时写入停止。
        with override_settings(AI_ASSISTANT_STREAM_REDIS_MAX_BYTES=first_payload_size):
            first = runtime.send(first_data)
            second = runtime.send({"content": "tail"})
            runtime.finish_success(output_data={"content": "done"}, updated_by=self.user)

        self.assertIsNotNone(first.stream_id)
        self.assertIsNone(second.stream_id)
        self.assertEqual(runtime.archive_status, StreamArchiveStatus.DEGRADED)
        business_events = [event for event in self.redis_events(runtime) if event.event is None]
        self.assertEqual(len(business_events), 1)
        # 实时通道停写后归档仍要完整保留事件，刷新页面可看到全部内容。
        archived_business_events = [item for item in self.archived_events() if item["event"] is None]
        self.assertEqual(len(archived_business_events), 2)

    def test_archive_capacity_truncation_does_not_fail_final_output(self):
        runtime = self.start_runtime()

        with override_settings(AI_ASSISTANT_STREAM_ARCHIVE_MAX_BYTES=256):
            self.send_and_checkpoint(runtime, {"content": "x" * 512})
            runtime.finish_success(output_data={"content": "done"}, updated_by=self.user)

        self.attachment.refresh_from_db()
        self.assertEqual(self.attachment.status, ExecutionStatus.SUCCESS)
        self.assertEqual(self.attachment.output_data, {"content": "done"})
        self.assertEqual(runtime.archive_status, StreamArchiveStatus.TRUNCATED)

    def test_archive_capacity_truncation_stops_later_checkpoints(self):
        runtime = self.start_runtime()

        with override_settings(AI_ASSISTANT_STREAM_ARCHIVE_MAX_BYTES=256):
            self.send_and_checkpoint(runtime, {"content": "x" * 512})
            with mock.patch.object(
                runtime._archive_store,
                "checkpoint",
                wraps=runtime._archive_store.checkpoint,
            ) as checkpoint:
                for index in range(runtime.CHECKPOINT_EVENT_COUNT):
                    runtime.send({"index": index})

        # 容量已耗尽后业务事件仍可进入 Redis，但不应再反复锁行
        # 解析接近上限的完整 JSON 归档。
        checkpoint.assert_not_called()
        self.assertEqual(runtime.pending_count, 0)
        self.assertEqual(len(self.redis_events(runtime)), runtime.CHECKPOINT_EVENT_COUNT + 1)

    def test_platform_events_are_not_limited_by_business_event_cap(self):
        runtime = self.start_runtime()

        with override_settings(AI_ASSISTANT_STREAM_MAX_EVENTS=1):
            runtime.send({"index": 0})
            runtime.send({"index": 1})
            runtime.finish_success(output_data={"content": "done"}, updated_by=self.user)

        archived = self.archived_events()
        self.assertEqual(archived[-1]["event"], PlatformStreamEvent.STREAM_END)
        self.assertEqual(self.redis_events(runtime)[-1].event, PlatformStreamEvent.STREAM_END)

    def test_platform_terminal_is_not_blocked_by_redis_business_byte_cap(self):
        runtime = self.start_runtime()

        with override_settings(AI_ASSISTANT_STREAM_REDIS_MAX_BYTES=1):
            runtime.send({"content": "not-live"})
            runtime.finish_success(output_data={"content": "done"}, updated_by=self.user)

        self.assertEqual(self.redis_events(runtime)[-1].event, PlatformStreamEvent.STREAM_END)


class StreamRuntimeTerminalTest(StreamRuntimeTestCase):
    @mock.patch("services.web.ai_assistant.streaming.runtime.start_stream_span")
    def test_terminal_and_retry_use_stream_convergence_span(self, start_stream_span):
        success_runtime = self.start_runtime()
        success_runtime.finish_success(output_data={"content": "done"}, updated_by=self.user)

        retry_attachment = self.create_attachment(task_id="task-retry")
        retry_runtime = self.start_runtime(attachment=retry_attachment)
        retry_runtime.finish_retry()

        self.assertEqual(start_stream_span.call_count, 2)
        self.assertEqual(start_stream_span.call_args_list[0].kwargs["status"], ExecutionStatus.SUCCESS)
        self.assertEqual(start_stream_span.call_args_list[1].kwargs["status"], "RETRY")

    @mock.patch("services.web.ai_assistant.streaming.runtime.report_stream_execution")
    def test_success_reports_one_aggregate_summary(self, report_stream_execution):
        runtime = self.start_runtime()
        first_data = {"content": "A"}
        second_data = {"content": "B"}
        expected_bytes = sum(
            len(serialize_stream_event(UIStreamEvent(data=data), include_stream_id=False))
            for data in (first_data, second_data)
        )
        runtime.send(first_data)
        runtime.send(second_data)

        runtime.finish_success(output_data={"content": "done"}, updated_by=self.user)

        report_stream_execution.assert_called_once()
        snapshot = report_stream_execution.call_args.args[0]
        self.assertEqual(snapshot.status, ExecutionStatus.SUCCESS)
        self.assertEqual(snapshot.event_count, 2)
        self.assertEqual(snapshot.event_bytes, expected_bytes)
        self.assertFalse(snapshot.degraded)
        self.assertFalse(snapshot.truncated)

    @mock.patch("services.web.ai_assistant.streaming.runtime.report_stream_execution")
    def test_retry_reports_degraded_summary_once(self, report_stream_execution):
        runtime = self.start_runtime()
        with mock.patch.object(RedisLiveStore, "append", side_effect=RedisError("redis down")):
            runtime.send({"content": "A"})

        runtime.finish_retry()
        runtime.finish_retry()

        report_stream_execution.assert_called_once()
        snapshot = report_stream_execution.call_args.args[0]
        self.assertEqual(snapshot.status, "RETRY")
        self.assertTrue(snapshot.degraded)

    @mock.patch("services.web.ai_assistant.streaming.runtime.report_stream_execution")
    def test_truncation_is_distinct_from_transport_degradation(self, report_stream_execution):
        runtime = self.start_runtime()
        with override_settings(AI_ASSISTANT_STREAM_MAX_EVENT_BYTES=1):
            runtime.send({"content": "too large"})

        runtime.finish_success(output_data={"content": "done"}, updated_by=self.user)

        snapshot = report_stream_execution.call_args.args[0]
        self.assertTrue(snapshot.truncated)
        self.assertFalse(snapshot.degraded)

    def test_finish_success_persists_terminal_then_publishes_stream_end(self):
        runtime = self.start_runtime()
        runtime.send({"content": "A"})

        with mock.patch.object(
            runtime._archive_store,
            "finalize",
            wraps=runtime._archive_store.finalize,
        ) as finalize:
            runtime.finish_success(output_data={"content": "done"}, updated_by=self.user)

        finalize.assert_called_once()
        terminal_event = finalize.call_args.kwargs["terminal_event"]
        self.assertEqual(terminal_event.event, PlatformStreamEvent.STREAM_END)
        self.assertEqual(terminal_event.data, {"status": ExecutionStatus.SUCCESS})
        self.assertIsNone(terminal_event.stream_id)
        self.attachment.refresh_from_db()
        self.assertEqual(self.attachment.status, ExecutionStatus.SUCCESS)
        self.assertEqual(self.attachment.output_data, {"content": "done"})
        self.assertEqual(self.attachment.error_code, "")
        self.assertTrue(runtime.closed)
        self.assertEqual(runtime.pending_count, 0)
        archived = self.archived_events()
        self.assertEqual([item["data"].get("content") for item in archived[:1]], ["A"])
        self.assertEqual(archived[-1]["event"], PlatformStreamEvent.STREAM_END)
        self.assertEqual(archived[-1]["data"], {"status": ExecutionStatus.SUCCESS})
        self.assertEqual(self.redis_events(runtime)[-1].event, PlatformStreamEvent.STREAM_END)

    def test_finish_failure_persists_terminal_then_publishes_stream_end(self):
        runtime = self.start_runtime()
        runtime.send({"content": "partial"})

        updated = runtime.finish_failure(error_code="9999034", error_message="可公开的执行失败", updated_by=self.user)

        self.assertTrue(updated)
        self.attachment.refresh_from_db()
        self.assertEqual(self.attachment.status, ExecutionStatus.FAILED)
        self.assertIsNone(self.attachment.output_data)
        self.assertEqual(self.attachment.error_code, "9999034")
        self.assertEqual(self.attachment.error_message, "可公开的执行失败")
        self.assertTrue(runtime.closed)
        self.assertEqual(self.archived_events()[-1]["event"], PlatformStreamEvent.STREAM_END)
        self.assertEqual(self.archived_events()[-1]["data"], {"status": ExecutionStatus.FAILED})
        self.assertEqual(self.redis_events(runtime)[-1].event, PlatformStreamEvent.STREAM_END)

    def test_finish_retry_flushes_pending_and_closes_without_terminal(self):
        runtime = self.start_runtime()
        runtime.send({"content": "A"})

        runtime.finish_retry()

        self.attachment.refresh_from_db()
        self.assertEqual(self.attachment.status, ExecutionStatus.PROCESSING)
        self.assertIsNone(self.attachment.output_data)
        self.assertTrue(runtime.closed)
        archived = self.archived_events()
        self.assertEqual(len(archived), 1)
        self.assertEqual(archived[0]["data"], {"content": "A"})
        self.assertIsNone(archived[-1]["event"])

    def test_finish_retry_swallows_database_error_and_closes(self):
        runtime = self.start_runtime()
        runtime.send({"content": "A"})

        with mock.patch.object(AttachmentArchiveStore, "checkpoint", side_effect=DatabaseError("db down")):
            runtime.finish_retry()

        self.assertTrue(runtime.closed)
        self.attachment.refresh_from_db()
        self.assertEqual(self.attachment.status, ExecutionStatus.PROCESSING)

    def test_finish_retry_propagates_checkpoint_implementation_error_and_stays_open(self):
        runtime = self.start_runtime()
        runtime.send({"content": "A"})

        with mock.patch.object(AttachmentArchiveStore, "checkpoint", side_effect=ValueError("invalid archive")):
            with self.assertRaises(ValueError):
                runtime.finish_retry()

        self.assertFalse(runtime.closed)
        self.assertEqual(runtime.pending_count, 1)
        self.assertEqual(runtime.archive_status, StreamArchiveStatus.COMPLETE)

    def test_finish_of_stale_execution_does_not_overwrite_new_result(self):
        runtime_a = self.start_runtime()
        runtime_b = self.start_runtime()
        runtime_b.finish_success(output_data={"content": "new"}, updated_by=self.user)

        with self.assertRaises(StaleAttachmentTask):
            runtime_a.finish_success(output_data={"content": "old"}, updated_by=self.user)
        self.assertFalse(runtime_a.finish_failure(error_code="9999034", error_message="旧执行", updated_by=self.user))

        self.attachment.refresh_from_db()
        self.assertEqual(self.attachment.status, ExecutionStatus.SUCCESS)
        self.assertEqual(self.attachment.output_data, {"content": "new"})

    def test_terminal_redis_append_failure_does_not_roll_back_committed_result(self):
        runtime = self.start_runtime()

        with mock.patch.object(RedisLiveStore, "append", side_effect=RedisError("redis down")):
            runtime.finish_success(output_data={"content": "done"}, updated_by=self.user)

        self.attachment.refresh_from_db()
        self.assertEqual(self.attachment.status, ExecutionStatus.SUCCESS)
        self.assertEqual(self.attachment.output_data, {"content": "done"})
        self.assertEqual(self.attachment.stream_archive[-1]["event"], PlatformStreamEvent.STREAM_END)
        self.assertIsNone(self.attachment.stream_archive[-1]["stream_id"])
        self.assertTrue(runtime.closed)

    def test_final_transaction_error_propagates_and_keeps_processing(self):
        runtime = self.start_runtime()
        runtime.send({"content": "A"})

        with mock.patch.object(AttachmentArchiveStore, "finalize", side_effect=DatabaseError("db down")):
            with self.assertRaises(DatabaseError):
                runtime.finish_success(output_data={"content": "done"}, updated_by=self.user)

        # 终态事务失败必须让 Task 走 Retry，Runtime 不能提前关闭或丢缓冲。
        self.assertFalse(runtime.closed)
        self.assertEqual(runtime.pending_count, 1)
        self.attachment.refresh_from_db()
        self.assertEqual(self.attachment.status, ExecutionStatus.PROCESSING)

    def test_second_finish_call_after_close_raises_runtime_closed(self):
        runtime = self.start_runtime()
        runtime.finish_success(output_data={"content": "done"}, updated_by=self.user)

        with self.assertRaises(StreamRuntimeClosed):
            runtime.finish_success(output_data={"content": "again"}, updated_by=self.user)

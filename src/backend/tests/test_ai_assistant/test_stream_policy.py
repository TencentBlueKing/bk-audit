from contextlib import ExitStack, nullcontext
from unittest import mock
from uuid import uuid4

from django.test import SimpleTestCase, override_settings

from services.web.ai_assistant.constants import StreamArchiveStatus
from services.web.ai_assistant.schemas import (
    AttachmentStreamConfig,
    UIStreamEvent,
    serialize_stream_event,
)
from services.web.ai_assistant.streaming import (
    AttachmentArchiveStore,
    RedisLiveStore,
    StreamCheckpointResult,
    StreamExecutionBinding,
    UIStreamRuntime,
)


class CountingRuntime(UIStreamRuntime):
    """观察审计普通策略工厂，不覆盖组件的 policy 属性。"""

    def __init__(self, **kwargs):
        self.policy_reads = 0
        self.fail_policy = False
        super().__init__(**kwargs)

    def _build_policy(self):
        self.policy_reads += 1
        if self.fail_policy:
            raise AssertionError("unexpected policy evaluation")
        return super()._build_policy()


@override_settings(
    AI_ASSISTANT_STREAM_MAX_EVENT_BYTES=256 * 1024,
    AI_ASSISTANT_STREAM_MAX_EVENTS=10_000,
    AI_ASSISTANT_STREAM_REDIS_MAX_BYTES=10 * 1024 * 1024,
    AI_ASSISTANT_STREAM_ARCHIVE_MAX_BYTES=10 * 1024 * 1024,
    AI_ASSISTANT_STREAM_ACTIVITY_INTERVAL_SECONDS=60,
)
class StreamPolicyIntegrationTest(SimpleTestCase):
    """用真实发行组件验证审计工厂接法，端口为替身且禁止数据库访问。"""

    def setUp(self):
        self.enterContext(mock.patch.object(UIStreamRuntime, "_convergence_span", return_value=nullcontext()))
        self.enterContext(mock.patch.object(UIStreamRuntime, "_report_summary"))

    def make_runtime(self):
        """装配真实运行时和事件类型，存储与发布只记录调用。"""
        config = AttachmentStreamConfig(task_id="policy-test", execution_id=uuid4(), redis_key="policy-test")
        binding = StreamExecutionBinding(
            attachment_id=1, attachment_uid=uuid4(), business_type="policy-test", config=config
        )
        live = mock.Mock(spec=RedisLiveStore)
        live.append.side_effect = lambda *, redis_key, event: event.model_copy(
            update={"stream_id": f"{live.append.call_count}-0"}
        )
        archive = mock.Mock(spec=AttachmentArchiveStore)
        archive.checkpoint.return_value = StreamCheckpointResult(archive_status=StreamArchiveStatus.COMPLETE)
        archive.commit.return_value = StreamArchiveStatus.COMPLETE
        runtime = CountingRuntime(
            binding=binding, redis_store=live, archive_store=archive, archive_status=StreamArchiveStatus.COMPLETE
        )
        return runtime, live, archive

    def test_factory_is_deferred_and_evaluated_once_per_send(self):
        runtime, live, archive = self.make_runtime()
        self.assertEqual(runtime.policy_reads, 0)

        runtime.send({"delta": "first"})
        self.assertEqual(runtime.policy_reads, 1)
        with override_settings(AI_ASSISTANT_STREAM_MAX_EVENT_BYTES=1):
            self.assertIsNone(runtime.send({"delta": "too large"}))

        self.assertEqual(runtime.policy_reads, 2)
        live.append.assert_called_once()
        archive.checkpoint.assert_not_called()

    def test_settings_and_checkpoint_changes_during_send_apply_to_next_send(self):
        runtime, live, archive = self.make_runtime()
        runtime._last_activity_checkpoint_at -= 2
        original_publish = live.append.side_effect
        with ExitStack() as changes:

            def publish(**kwargs):
                event = original_publish(**kwargs)
                changes.enter_context(
                    override_settings(
                        AI_ASSISTANT_STREAM_MAX_EVENT_BYTES=1,
                        AI_ASSISTANT_STREAM_ARCHIVE_MAX_BYTES=1,
                        AI_ASSISTANT_STREAM_ACTIVITY_INTERVAL_SECONDS=1,
                    )
                )
                runtime.CHECKPOINT_EVENT_COUNT = 1
                runtime.CHECKPOINT_BYTES = 1
                return event

            live.append.side_effect = publish
            runtime.send({"delta": "current snapshot"})
            self.assertEqual(runtime.pending_count, 1)
            self.assertEqual(runtime.archive_status, StreamArchiveStatus.COMPLETE)
            archive.checkpoint.assert_not_called()
            self.assertIsNone(runtime.send({"delta": "new event limit"}))
            live.append.assert_called_once()

    def test_terminal_and_retry_paths_do_not_evaluate_factory(self):
        for outcome in ("success", "failure", "retry"):
            with self.subTest(outcome=outcome):
                runtime, live, archive = self.make_runtime()
                runtime.send({"delta": "pending"})
                self.assertEqual(runtime.policy_reads, 1)
                runtime.fail_policy = True

                if outcome == "success":
                    runtime.finish_success(output_data={"result": "done"}, updated_by="policy-test")
                elif outcome == "failure":
                    self.assertTrue(
                        runtime.finish_failure(
                            error_code="policy-test", error_message="failed", updated_by="policy-test"
                        )
                    )
                else:
                    runtime.close_for_retry()

                self.assertTrue(runtime.closed)
                self.assertEqual(runtime.policy_reads, 1)

    def test_invalid_settings_fail_before_publish_or_checkpoint(self):
        cases = (
            ("AI_ASSISTANT_STREAM_MAX_EVENT_BYTES", True, TypeError),
            ("AI_ASSISTANT_STREAM_MAX_EVENTS", 1.5, TypeError),
            ("AI_ASSISTANT_STREAM_REDIS_MAX_BYTES", "1024", TypeError),
            ("AI_ASSISTANT_STREAM_ARCHIVE_MAX_BYTES", -1, ValueError),
            ("AI_ASSISTANT_STREAM_ACTIVITY_INTERVAL_SECONDS", False, TypeError),
        )
        for setting, value, error in cases:
            with self.subTest(setting=setting, value=value):
                runtime, live, archive = self.make_runtime()
                with override_settings(**{setting: value}), self.assertRaises(error):
                    runtime.send({"delta": "invalid policy"})
                live.append.assert_not_called()
                archive.checkpoint.assert_not_called()
                self.assertEqual(runtime.pending_count, 0)

    def test_zero_byte_and_count_limits_keep_their_distinct_meanings(self):
        cases = (
            ("AI_ASSISTANT_STREAM_MAX_EVENT_BYTES", False, 0, 0, StreamArchiveStatus.TRUNCATED),
            ("AI_ASSISTANT_STREAM_MAX_EVENTS", True, 1, 0, StreamArchiveStatus.TRUNCATED),
            ("AI_ASSISTANT_STREAM_REDIS_MAX_BYTES", True, 0, 1, StreamArchiveStatus.DEGRADED),
            ("AI_ASSISTANT_STREAM_ARCHIVE_MAX_BYTES", True, 1, 0, StreamArchiveStatus.TRUNCATED),
        )
        for setting, accepted, published, pending, status in cases:
            with self.subTest(setting=setting), override_settings(**{setting: 0}):
                runtime, live, archive = self.make_runtime()
                event = runtime.send({"delta": "zero budget"})
                self.assertEqual(event is not None, accepted)
                self.assertEqual(live.append.call_count, published)
                self.assertEqual(runtime.pending_count, pending)
                self.assertEqual(runtime.archive_status, status)

    def test_zero_checkpoint_thresholds_checkpoint_each_event(self):
        for field in ("CHECKPOINT_EVENT_COUNT", "CHECKPOINT_BYTES", "activity_interval"):
            with self.subTest(field=field):
                runtime, live, archive = self.make_runtime()
                with ExitStack() as changes:
                    if field == "activity_interval":
                        changes.enter_context(override_settings(AI_ASSISTANT_STREAM_ACTIVITY_INTERVAL_SECONDS=0))
                    else:
                        changes.enter_context(mock.patch.object(runtime, field, 0))
                    runtime.send({"delta": "checkpoint"})
                archive.checkpoint.assert_called_once()
                self.assertEqual(runtime.pending_count, 0)

    def test_retry_close_keeps_trace_and_has_no_business_terminal(self):
        runtime, live, archive = self.make_runtime()
        runtime.send({"delta": "pending"})

        runtime.close_for_retry()
        runtime.close_for_retry()

        self.assertTrue(runtime.closed)
        archive.checkpoint.assert_called_once()
        archive.commit.assert_not_called()
        live.append.assert_called_once()
        UIStreamRuntime._convergence_span.assert_called_with(status="RETRY")
        UIStreamRuntime._report_summary.assert_called_once()
        self.assertEqual(UIStreamRuntime._report_summary.call_args.args[0].status, "RETRY")

    def test_reentrant_publish_propagates_degraded_without_charging_unacknowledged_live_bytes(self):
        runtime, live, archive = self.make_runtime()
        original_publish = live.append.side_effect
        effects = []

        def publish(**kwargs):
            receipt = original_publish(**kwargs)
            effects.append(receipt)
            if live.append.call_count == 1:
                runtime.send({"delta": "nested"})
            return receipt

        live.append.side_effect = publish
        with self.assertRaisesRegex(RuntimeError, "must not reenter"):
            runtime.send({"delta": "ack"})

        self.assertEqual(len(effects), 1)
        self.assertEqual(runtime.archive_status, StreamArchiveStatus.DEGRADED)
        self.assertFalse(runtime.closed)
        self.assertEqual(runtime.pending_count, 0)
        archive.checkpoint.assert_not_called()

        live.append.side_effect = original_publish
        live_bytes = len(serialize_stream_event(UIStreamEvent(data={"delta": "ack"}), include_stream_id=False))
        with override_settings(AI_ASSISTANT_STREAM_REDIS_MAX_BYTES=live_bytes):
            self.assertIsNotNone(runtime.send({"delta": "ack"}).stream_id)
            self.assertIsNone(runtime.send({"delta": "ack"}).stream_id)

        self.assertEqual(live.append.call_count, 2)
        runtime.close_for_retry()
        summary = UIStreamRuntime._report_summary.call_args.args[0]
        self.assertTrue(summary.degraded)
        self.assertEqual(summary.event_count, 3)

import json
from unittest import mock
from uuid import UUID, uuid4

from django.db import DatabaseError, connection
from django.test import SimpleTestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext, override_settings

from services.web.ai_assistant.constants import (
    AttachmentType,
    ExecutionStatus,
    MessageType,
    PlatformStreamEvent,
    StreamArchiveStatus,
)
from services.web.ai_assistant.exceptions import StaleAttachmentTask
from services.web.ai_assistant.models import Attachment, Conversation, Message
from services.web.ai_assistant.schemas import (
    AttachmentStreamConfig,
    UIStreamEvent,
    serialize_stream_event,
)
from services.web.ai_assistant.streaming import (
    AttachmentArchiveStore,
    StreamExecutionBinding,
    build_stream_key,
    fit_archive_events,
    merge_archive_status,
)


def business_event(text: str, *, stream_id: str | None = None) -> UIStreamEvent:
    return UIStreamEvent(stream_id=stream_id, data={"content": text})


def terminal_event(status: ExecutionStatus) -> UIStreamEvent:
    return UIStreamEvent(event=PlatformStreamEvent.STREAM_END, data={"status": status})


class ArchiveHelperTest(SimpleTestCase):
    """状态合并与容量裁剪必须是确定性纯函数，便于 Runtime 复用。"""

    def test_merge_archive_status_keeps_worst_observed_status(self):
        statuses = [StreamArchiveStatus.COMPLETE, StreamArchiveStatus.DEGRADED, StreamArchiveStatus.TRUNCATED]

        for index, current in enumerate(statuses):
            for other_index, incoming in enumerate(statuses):
                with self.subTest(current=current, incoming=incoming):
                    expected = statuses[max(index, other_index)]
                    self.assertEqual(merge_archive_status(current, incoming), expected)
                    self.assertEqual(merge_archive_status(incoming, current), expected)

    def test_fit_archive_events_accepts_all_events_within_capacity(self):
        existing = [business_event("a", stream_id="1-0")]
        incoming = [business_event("b", stream_id="2-0"), business_event("c", stream_id="3-0")]

        events, accepted, truncated = fit_archive_events(existing=existing, incoming=incoming, max_bytes=1024)

        self.assertEqual(events, existing + incoming)
        self.assertEqual(accepted, 2)
        self.assertFalse(truncated)

    def test_fit_archive_events_measures_final_json_array_bytes(self):
        existing = [business_event("a", stream_id="1-0")]
        incoming = [business_event("b", stream_id="2-0")]
        exact_bytes = len(
            json.dumps(
                [event.model_dump(mode="json") for event in existing + incoming],
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
        )

        self.assertEqual(
            fit_archive_events(existing=existing, incoming=incoming, max_bytes=exact_bytes),
            (existing + incoming, 1, False),
        )
        self.assertEqual(
            fit_archive_events(existing=existing, incoming=incoming, max_bytes=exact_bytes - 1),
            (existing, 0, True),
        )

    def test_fit_archive_events_keeps_acceptable_prefix_only(self):
        incoming = [business_event("a", stream_id="1-0"), business_event("b" * 512, stream_id="2-0")]
        first_only_bytes = len(
            json.dumps([incoming[0].model_dump(mode="json")], ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        )

        events, accepted, truncated = fit_archive_events(
            existing=[], incoming=incoming, max_bytes=first_only_bytes + 10
        )

        self.assertEqual(events, [incoming[0]])
        self.assertEqual(accepted, 1)
        self.assertTrue(truncated)

    def test_fit_archive_events_rejects_everything_when_existing_already_exceeds(self):
        existing = [business_event("a" * 256, stream_id="1-0")]

        events, accepted, truncated = fit_archive_events(
            existing=existing, incoming=[business_event("b", stream_id="2-0")], max_bytes=16
        )

        self.assertEqual(events, existing)
        self.assertEqual(accepted, 0)
        self.assertTrue(truncated)

    def test_fit_archive_events_without_incoming_never_truncates(self):
        existing = [business_event("a", stream_id="1-0")]

        self.assertEqual(
            fit_archive_events(existing=existing, incoming=[], max_bytes=1),
            (existing, 0, False),
        )

    def test_fit_archive_events_encodes_each_event_once_per_call(self):
        """裁剪必须是线性开销：归档已接近设计上限时仍不能重复编码整个数组。

        设计允许单次执行累积 10000 条事件，若每追加一条都全量 dumps，
        checkpoint 会在持有行锁的事务内退化成 O(n^2)。
        """

        existing = [business_event("x" * 200, stream_id=f"{index}-0") for index in range(5000)]
        incoming = [business_event("y" * 200, stream_id=f"{5000 + index}-0") for index in range(50)]

        with mock.patch.object(
            UIStreamEvent, "model_dump", autospec=True, side_effect=UIStreamEvent.model_dump
        ) as dump_spy:
            events, accepted, truncated = fit_archive_events(
                existing=existing, incoming=incoming, max_bytes=10 * 1024 * 1024
            )

        self.assertEqual(len(events), len(existing) + len(incoming))
        self.assertEqual(accepted, len(incoming))
        self.assertFalse(truncated)
        # 允许对最终结果各编码一次；O(n^2) 实现会达到 5000*50 量级。
        self.assertLessEqual(dump_spy.call_count, 2 * (len(existing) + len(incoming)))

    def test_fit_archive_events_byte_accounting_matches_final_json_array(self):
        """增量字节估算必须与最终落库 JSON 数组的实际编码长度完全一致。"""

        events = [
            business_event("纯中文内容", stream_id="1-0"),
            UIStreamEvent(stream_id=None, data=None),
            UIStreamEvent(
                event=PlatformStreamEvent.STREAM_RESET,
                stream_id="2-0",
                data=[1, 2, {"k": "v"}],
            ),
            UIStreamEvent(stream_id="3-0", data={"a": '含"引号\\转义', "enabled": True}),
        ]

        for index in range(len(events) + 1):
            with self.subTest(count=index):
                expected_bytes = len(
                    json.dumps(
                        [event.model_dump(mode="json") for event in events[:index]],
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ).encode("utf-8")
                )
                # 上限恰好等于实际字节时必须全部接受，说明估算没有偏大。
                self.assertEqual(
                    fit_archive_events(existing=[], incoming=events[:index], max_bytes=expected_bytes),
                    (events[:index], index, False),
                )
                if index:
                    # 上限少一个字节时必须截断，说明估算也没有偏小。
                    _, accepted, truncated = fit_archive_events(
                        existing=[], incoming=events[:index], max_bytes=expected_bytes - 1
                    )
                    self.assertLess(accepted, index)
                    self.assertTrue(truncated)


class AttachmentArchiveStoreTest(TransactionTestCase):
    """归档存储直接操作真实 MySQL，验证行锁、fencing 与终态原子性。"""

    # 只清理本模块表，避免 flush 删除其他应用由数据迁移写入的全局配置。
    available_apps = ["services.web.ai_assistant"]

    def setUp(self):
        self.user = "alice"
        self.store = AttachmentArchiveStore()
        self.conversation = Conversation.objects.create(created_by=self.user, updated_by=self.user)
        self.source_message = Message.objects.create(
            conversation=self.conversation,
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

    def create_attachment(
        self,
        *,
        task_id: str = "task-current",
        status: str = ExecutionStatus.PROCESSING,
        is_stream: bool = True,
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

    def start(self, attachment: Attachment | None = None):
        attachment = attachment or self.attachment
        return self.store.start_execution(attachment_id=attachment.id, task_id=attachment.task_id)

    def archived_events(self, attachment: Attachment | None = None) -> list[dict]:
        attachment = attachment or self.attachment
        attachment.refresh_from_db()
        return attachment.stream_archive

    @staticmethod
    def update_statements(captured: CaptureQueriesContext) -> list[str]:
        """只统计真正的 UPDATE 语句；``SELECT ... FOR UPDATE`` 不计入写操作。"""

        return [
            query["sql"] for query in captured.captured_queries if query["sql"].strip().upper().startswith("UPDATE")
        ]

    def test_start_execution_rotates_config_and_clears_previous_archive(self):
        rotation_a = self.start()
        self.store.checkpoint(
            binding=rotation_a.binding,
            events=[business_event("old", stream_id="1-0")],
            archive_status=StreamArchiveStatus.COMPLETE,
        )

        rotation_b = self.start()

        self.assertIsNone(rotation_a.previous_config)
        self.assertEqual(rotation_b.previous_config, rotation_a.binding.config)
        self.assertNotEqual(rotation_b.binding.config.execution_id, rotation_a.binding.config.execution_id)
        self.assertEqual(
            rotation_b.binding.config.redis_key,
            build_stream_key(
                attachment_uid=self.attachment.uid,
                execution_id=rotation_b.binding.config.execution_id,
            ),
        )
        self.assertEqual(rotation_b.binding.config.archive_status, StreamArchiveStatus.COMPLETE)
        self.attachment.refresh_from_db()
        self.assertEqual(self.attachment.stream_archive, [])
        self.assertEqual(self.attachment.stream_config, rotation_b.binding.config.model_dump(mode="json"))

    def test_start_execution_binding_carries_attachment_identity(self):
        rotation = self.start()

        self.assertEqual(rotation.binding.attachment_id, self.attachment.id)
        self.assertEqual(rotation.binding.attachment_uid, self.attachment.uid)
        self.assertEqual(rotation.binding.task_id, self.attachment.task_id)
        self.assertIsInstance(rotation.binding.config.execution_id, UUID)

    def test_start_execution_rejects_stale_task_wrong_state_or_non_stream(self):
        cases = {
            "wrong_task_id": (self.create_attachment(task_id="task-other"), "task-mismatch"),
            "not_processing": (self.create_attachment(task_id="task-done", status=ExecutionStatus.SUCCESS), None),
            "not_stream": (self.create_attachment(task_id="task-sync", is_stream=False), None),
        }
        for case_name, (attachment, task_id) in cases.items():
            with self.subTest(case=case_name):
                with self.assertRaises(StaleAttachmentTask):
                    self.store.start_execution(
                        attachment_id=attachment.id,
                        task_id=task_id or attachment.task_id,
                    )

        with self.assertRaises(StaleAttachmentTask):
            self.store.start_execution(attachment_id=self.attachment.id + 10_000, task_id="task-current")

    def test_old_execution_of_same_task_cannot_checkpoint_after_rotation(self):
        rotation_a = self.start()
        rotation_b = self.start()

        with self.assertRaises(StaleAttachmentTask):
            self.store.checkpoint(
                binding=rotation_a.binding,
                events=[business_event("old", stream_id="1-0")],
                archive_status=StreamArchiveStatus.COMPLETE,
            )
        self.store.checkpoint(
            binding=rotation_b.binding,
            events=[business_event("new", stream_id="2-0")],
            archive_status=StreamArchiveStatus.COMPLETE,
        )

        self.assertEqual(
            self.archived_events(),
            [business_event("new", stream_id="2-0").model_dump(mode="json")],
        )

    def test_is_current_reflects_task_execution_and_status_requirements(self):
        rotation = self.start()
        stale_binding = StreamExecutionBinding(
            attachment_id=rotation.binding.attachment_id,
            attachment_uid=rotation.binding.attachment_uid,
            config=AttachmentStreamConfig(
                task_id=rotation.binding.task_id,
                execution_id=uuid4(),
                redis_key=rotation.binding.config.redis_key,
            ),
        )

        self.assertTrue(self.store.is_current(binding=rotation.binding))
        self.assertFalse(self.store.is_current(binding=stale_binding))

        Attachment.objects.filter(id=self.attachment.id).update(status=ExecutionStatus.SUCCESS)
        self.assertFalse(self.store.is_current(binding=rotation.binding))
        self.assertTrue(self.store.is_current(binding=rotation.binding, require_processing=False))

    def test_is_current_does_not_trigger_extra_query_on_broken_config(self):
        """config 脏数据会走告警日志路径，该路径不得因延迟字段再查一次库。"""

        rotation = self.start()
        Attachment.objects.filter(id=self.attachment.id).update(stream_config={"broken": True})

        with CaptureQueriesContext(connection) as captured:
            self.assertFalse(self.store.is_current(binding=rotation.binding))

        self.assertEqual(len(captured.captured_queries), 1)

    def test_checkpoint_appends_events_in_order_and_returns_persisted_status(self):
        rotation = self.start()
        first = business_event("a", stream_id="1-0")
        second = business_event("b", stream_id="2-0")

        first_result = self.store.checkpoint(
            binding=rotation.binding, events=[first], archive_status=StreamArchiveStatus.COMPLETE
        )
        second_result = self.store.checkpoint(
            binding=rotation.binding, events=[second], archive_status=StreamArchiveStatus.COMPLETE
        )

        self.assertEqual(first_result.archive_status, StreamArchiveStatus.COMPLETE)
        self.assertFalse(first_result.capacity_exhausted)
        self.assertEqual(second_result.archive_status, StreamArchiveStatus.COMPLETE)
        self.assertFalse(second_result.capacity_exhausted)
        self.assertEqual(
            self.archived_events(),
            [first.model_dump(mode="json"), second.model_dump(mode="json")],
        )
        self.attachment.refresh_from_db()
        self.assertEqual(self.attachment.stream_config["archive_status"], StreamArchiveStatus.COMPLETE)

    def test_checkpoint_persists_incoming_degraded_status_into_config(self):
        rotation = self.start()

        result = self.store.checkpoint(
            binding=rotation.binding,
            events=[business_event("a")],
            archive_status=StreamArchiveStatus.DEGRADED,
        )

        self.assertEqual(result.archive_status, StreamArchiveStatus.DEGRADED)
        self.attachment.refresh_from_db()
        self.assertEqual(self.attachment.stream_config["archive_status"], StreamArchiveStatus.DEGRADED)
        # 状态一旦降级不得回升，避免前端在同一执行内反复切换提示。
        self.assertEqual(
            self.store.checkpoint(
                binding=rotation.binding,
                events=[business_event("b")],
                archive_status=StreamArchiveStatus.COMPLETE,
            ).archive_status,
            StreamArchiveStatus.DEGRADED,
        )

    def test_checkpoint_keeps_parsable_history_and_degrades_on_dirty_archive(self):
        rotation = self.start()
        valid = business_event("a", stream_id="1-0")
        Attachment.objects.filter(id=self.attachment.id).update(
            stream_archive=[valid.model_dump(mode="json"), {"unknown": True}, "broken"]
        )

        result = self.store.checkpoint(
            binding=rotation.binding,
            events=[business_event("b", stream_id="2-0")],
            archive_status=StreamArchiveStatus.COMPLETE,
        )

        self.assertEqual(result.archive_status, StreamArchiveStatus.DEGRADED)
        self.assertFalse(result.capacity_exhausted)
        self.assertEqual(
            self.archived_events(),
            [valid.model_dump(mode="json"), business_event("b", stream_id="2-0").model_dump(mode="json")],
        )

    def test_checkpoint_truncates_without_failing_business_task(self):
        rotation = self.start()
        first = business_event("a", stream_id="1-0")
        capacity = len(serialize_stream_event(first)) + 2

        with override_settings(AI_ASSISTANT_STREAM_ARCHIVE_MAX_BYTES=capacity):
            result = self.store.checkpoint(
                binding=rotation.binding,
                events=[first, business_event("b" * 256, stream_id="2-0")],
                archive_status=StreamArchiveStatus.COMPLETE,
            )

        self.assertEqual(result.archive_status, StreamArchiveStatus.TRUNCATED)
        self.assertTrue(result.capacity_exhausted)
        self.assertEqual(self.archived_events(), [first.model_dump(mode="json")])
        self.attachment.refresh_from_db()
        self.assertEqual(self.attachment.stream_config["archive_status"], StreamArchiveStatus.TRUNCATED)

    def test_checkpoint_without_events_is_noop_but_still_validates_binding(self):
        rotation_a = self.start()
        rotation_b = self.start()

        self.assertEqual(
            self.store.checkpoint(
                binding=rotation_b.binding,
                events=[],
                archive_status=StreamArchiveStatus.COMPLETE,
            ).archive_status,
            StreamArchiveStatus.COMPLETE,
        )
        with self.assertRaises(StaleAttachmentTask):
            self.store.checkpoint(binding=rotation_a.binding, events=[], archive_status=StreamArchiveStatus.COMPLETE)
        self.assertEqual(self.archived_events(), [])

    def test_checkpoint_only_locks_and_updates_target_attachment(self):
        other_attachment = self.create_attachment(task_id="task-other")
        rotation = self.start()

        with CaptureQueriesContext(connection) as captured:
            self.store.checkpoint(
                binding=rotation.binding,
                events=[business_event("a", stream_id="1-0")],
                archive_status=StreamArchiveStatus.COMPLETE,
            )

        update_sql = self.update_statements(captured)
        self.assertEqual(len(update_sql), 1)
        self.assertLessEqual(len(captured.captured_queries), 5)
        self.assertTrue(any("FOR UPDATE" in query["sql"].upper() for query in captured.captured_queries))
        other_attachment.refresh_from_db()
        self.assertEqual(other_attachment.stream_archive, [])

    def test_finalize_persists_pending_terminal_event_output_and_success_state(self):
        rotation = self.start()
        self.store.checkpoint(
            binding=rotation.binding,
            events=[business_event("a", stream_id="1-0")],
            archive_status=StreamArchiveStatus.COMPLETE,
        )
        last_delta = business_event("done", stream_id="2-0")

        self.store.finalize(
            binding=rotation.binding,
            events=[last_delta],
            terminal_event=terminal_event(ExecutionStatus.SUCCESS),
            status=ExecutionStatus.SUCCESS,
            output_data={"content": "done"},
            error_code="",
            error_message="",
            updated_by=self.user,
        )

        self.attachment.refresh_from_db()
        self.assertEqual(self.attachment.status, ExecutionStatus.SUCCESS)
        self.assertEqual(self.attachment.output_data, {"content": "done"})
        self.assertEqual(self.attachment.error_code, "")
        self.assertEqual(self.attachment.stream_archive[-2]["data"], last_delta.data)
        self.assertEqual(self.attachment.stream_archive[-1]["event"], PlatformStreamEvent.STREAM_END)
        self.assertEqual(self.attachment.stream_archive[-1]["data"], {"status": ExecutionStatus.SUCCESS})
        self.assertIsNone(self.attachment.stream_archive[-1]["stream_id"])
        self.assertEqual(len(self.attachment.stream_archive), 3)
        self.assertIsNotNone(self.attachment.content_updated_at)
        self.assertEqual(self.attachment.updated_by, self.user)

    def test_finalize_persists_failed_terminal_state_without_output(self):
        rotation = self.start()

        self.store.finalize(
            binding=rotation.binding,
            events=[business_event("partial", stream_id="1-0")],
            terminal_event=terminal_event(ExecutionStatus.FAILED),
            status=ExecutionStatus.FAILED,
            output_data=None,
            error_code="9999034",
            error_message="可公开的执行失败",
            updated_by=self.user,
        )

        self.attachment.refresh_from_db()
        self.assertEqual(self.attachment.status, ExecutionStatus.FAILED)
        self.assertIsNone(self.attachment.output_data)
        self.assertEqual(self.attachment.error_code, "9999034")
        self.assertEqual(self.attachment.error_message, "可公开的执行失败")
        self.assertEqual(len(self.attachment.stream_archive), 2)
        self.assertEqual(self.attachment.stream_archive[-1]["event"], PlatformStreamEvent.STREAM_END)

    def test_finalize_rejects_stale_execution_and_keeps_new_result(self):
        rotation_a = self.start()
        rotation_b = self.start()
        self.store.finalize(
            binding=rotation_b.binding,
            events=[business_event("new", stream_id="1-0")],
            terminal_event=terminal_event(ExecutionStatus.SUCCESS),
            status=ExecutionStatus.SUCCESS,
            output_data={"content": "new"},
            error_code="",
            error_message="",
            updated_by=self.user,
        )

        with self.assertRaises(StaleAttachmentTask):
            self.store.finalize(
                binding=rotation_a.binding,
                events=[business_event("old", stream_id="2-0")],
                terminal_event=terminal_event(ExecutionStatus.FAILED),
                status=ExecutionStatus.FAILED,
                output_data=None,
                error_code="9999034",
                error_message="旧执行失败",
                updated_by=self.user,
            )

        self.attachment.refresh_from_db()
        self.assertEqual(self.attachment.status, ExecutionStatus.SUCCESS)
        self.assertEqual(self.attachment.output_data, {"content": "new"})
        self.assertEqual(self.attachment.error_code, "")

    def test_finalize_rolls_back_archive_and_status_together_on_database_error(self):
        rotation = self.start()
        self.store.checkpoint(
            binding=rotation.binding,
            events=[business_event("a", stream_id="1-0")],
            archive_status=StreamArchiveStatus.COMPLETE,
        )

        with mock.patch.object(Attachment, "save", side_effect=DatabaseError("写入失败")):
            with self.assertRaises(DatabaseError):
                self.store.finalize(
                    binding=rotation.binding,
                    events=[business_event("done", stream_id="2-0")],
                    terminal_event=terminal_event(ExecutionStatus.SUCCESS),
                    status=ExecutionStatus.SUCCESS,
                    output_data={"content": "done"},
                    error_code="",
                    error_message="",
                    updated_by=self.user,
                )

        self.attachment.refresh_from_db()
        self.assertEqual(self.attachment.status, ExecutionStatus.PROCESSING)
        self.assertIsNone(self.attachment.output_data)
        self.assertEqual(
            self.attachment.stream_archive,
            [business_event("a", stream_id="1-0").model_dump(mode="json")],
        )

    def test_finalize_writes_terminal_state_in_single_update(self):
        rotation = self.start()

        with CaptureQueriesContext(connection) as captured:
            self.store.finalize(
                binding=rotation.binding,
                events=[business_event("done", stream_id="1-0")],
                terminal_event=terminal_event(ExecutionStatus.SUCCESS),
                status=ExecutionStatus.SUCCESS,
                output_data={"content": "done"},
                error_code="",
                error_message="",
                updated_by=self.user,
            )

        update_sql = self.update_statements(captured)
        self.assertEqual(len(update_sql), 1)
        self.assertIn("stream_archive", update_sql[0])
        self.assertIn("output_data", update_sql[0])
        self.assertIn("status", update_sql[0])

    def test_finalize_always_appends_terminal_event_after_archive_capacity_is_exhausted(self):
        rotation = self.start()
        first = business_event("a", stream_id="1-0")
        with override_settings(AI_ASSISTANT_STREAM_ARCHIVE_MAX_BYTES=len(serialize_stream_event(first)) + 2):
            self.store.checkpoint(
                binding=rotation.binding,
                events=[first, business_event("b" * 256, stream_id="2-0")],
                archive_status=StreamArchiveStatus.COMPLETE,
            )

            self.store.finalize(
                binding=rotation.binding,
                events=[business_event("tail" * 256, stream_id="3-0")],
                terminal_event=terminal_event(ExecutionStatus.SUCCESS),
                status=ExecutionStatus.SUCCESS,
                output_data={"content": "done"},
                error_code="",
                error_message="",
                updated_by=self.user,
            )

        archived = self.archived_events()
        self.assertEqual(len(archived), 2)
        self.assertEqual(archived[-1]["event"], PlatformStreamEvent.STREAM_END)
        self.assertEqual(archived[-1]["data"], {"status": ExecutionStatus.SUCCESS})
        self.assertIsNone(archived[-1]["stream_id"])
        self.attachment.refresh_from_db()
        self.assertEqual(self.attachment.status, ExecutionStatus.SUCCESS)
        self.assertEqual(self.attachment.output_data, {"content": "done"})

    def test_snapshot_returns_events_latest_cursor_and_effective_status(self):
        rotation = self.start()
        self.store.checkpoint(
            binding=rotation.binding,
            events=[business_event("a", stream_id="1-0"), business_event("b", stream_id="2-0")],
            archive_status=StreamArchiveStatus.COMPLETE,
        )
        self.attachment.refresh_from_db()

        snapshot = self.store.snapshot(attachment=self.attachment)

        self.assertEqual(
            snapshot.model_dump(mode="json"),
            {
                "events": [
                    business_event("a", stream_id="1-0").model_dump(mode="json"),
                    business_event("b", stream_id="2-0").model_dump(mode="json"),
                ],
                "execution_id": str(rotation.binding.config.execution_id),
                "latest_stream_id": "2-0",
                "archive_status": StreamArchiveStatus.COMPLETE,
            },
        )

    def test_snapshot_of_empty_or_dirty_archive_degrades_without_error(self):
        self.attachment.refresh_from_db()
        empty_snapshot = self.store.snapshot(attachment=self.attachment)

        self.assertEqual(empty_snapshot.events, [])
        self.assertIsNone(empty_snapshot.execution_id)
        self.assertIsNone(empty_snapshot.latest_stream_id)
        self.assertEqual(empty_snapshot.archive_status, StreamArchiveStatus.COMPLETE)

        valid = business_event("a", stream_id="1-0")
        Attachment.objects.filter(id=self.attachment.id).update(
            stream_archive=[valid.model_dump(mode="json"), "broken"]
        )
        self.attachment.refresh_from_db()

        dirty_snapshot = self.store.snapshot(attachment=self.attachment)

        self.assertEqual(dirty_snapshot.events, [valid])
        self.assertEqual(dirty_snapshot.latest_stream_id, "1-0")
        self.assertEqual(dirty_snapshot.archive_status, StreamArchiveStatus.DEGRADED)

    def test_snapshot_latest_stream_id_skips_trailing_events_without_cursor(self):
        rotation = self.start()
        self.store.checkpoint(
            binding=rotation.binding,
            events=[business_event("a", stream_id="1-0"), business_event("b")],
            archive_status=StreamArchiveStatus.DEGRADED,
        )
        self.attachment.refresh_from_db()

        snapshot = self.store.snapshot(attachment=self.attachment)

        self.assertEqual(len(snapshot.events), 2)
        self.assertEqual(snapshot.latest_stream_id, "1-0")
        self.assertEqual(snapshot.archive_status, StreamArchiveStatus.DEGRADED)

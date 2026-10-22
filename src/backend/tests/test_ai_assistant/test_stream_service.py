"""Audit live reads must converge on durable state without retaining DB connections."""

from types import SimpleNamespace
from unittest import mock
from uuid import uuid4

from django.test import SimpleTestCase, override_settings
from ui_stream.types import ReadBatch as StreamReadResult

from core.exceptions import PermissionException
from services.web.ai_assistant.constants import ExecutionStatus, PlatformStreamEvent
from services.web.ai_assistant.exceptions import AttachmentNotFound, InvalidStreamEvent
from services.web.ai_assistant.resources.stream import GetAttachmentStream
from services.web.ai_assistant.schemas import AttachmentStreamConfig, UIStreamEvent
from services.web.ai_assistant.services.attachment_stream import AttachmentStreamService
from services.web.common.scope_permission import ScopePermission


class ControlledLiveStore:
    """Advance a fake monotonic clock on completed reads, without real I/O."""

    def __init__(self, rounds):
        self.rounds = iter(rounds)
        self.now = 0.0
        self.blocks = []
        self.cursors = []

    def read(self, *, redis_key, after_id, block_ms):
        self.blocks.append(block_ms)
        self.cursors.append(after_id)
        elapsed, events = next(self.rounds)
        self.now += elapsed
        if isinstance(events, StreamReadResult):
            return events
        return StreamReadResult(events=events, last_seen_stream_id=events[-1].stream_id if events else None)


def progress(text, cursor):
    return UIStreamEvent(stream_id=cursor, data={"content": text})


def terminal():
    return UIStreamEvent(event=PlatformStreamEvent.STREAM_END, data={})


@override_settings(AI_ASSISTANT_STREAM_STATE_POLL_INTERVAL=1)
class AttachmentStreamDurableStateTest(SimpleTestCase):
    def setUp(self):
        self.uid = uuid4()
        self.execution_id = uuid4()
        self.config = AttachmentStreamConfig(
            task_id="synthetic-task", execution_id=self.execution_id, redis_key="test:stream"
        )
        self.attachment = self.make_attachment()
        self.connection = mock.Mock(in_atomic_block=False)
        self.connection.connection = object()
        self.patches = [
            mock.patch(
                "services.web.ai_assistant.services.attachment_stream.time.monotonic",
                side_effect=lambda: self.store.now,
            ),
            mock.patch(
                "services.web.ai_assistant.services.attachment_stream.db.transaction.get_connection",
                return_value=self.connection,
            ),
            mock.patch("services.web.ai_assistant.services.attachment_stream.db.close_old_connections"),
            mock.patch.object(ScopePermission, "check_scope_entry"),
        ]
        for patcher in self.patches:
            patcher.start()
            self.addCleanup(patcher.stop)

    def make_attachment(self, **changes):
        fields = dict(
            id=1,
            pk=1,
            uid=self.uid,
            task_id="synthetic-task",
            status=ExecutionStatus.PROCESSING,
            is_stream=True,
            stream_config=self.config.model_dump(mode="json"),
            source_message=SimpleNamespace(
                conversation=SimpleNamespace(scope_type="system", scope_id="synthetic-system")
            ),
        )
        fields.update(changes)
        return SimpleNamespace(**fields)

    def consume(self, rounds, current_states):
        self.store = ControlledLiveStore(rounds)
        service = AttachmentStreamService(user="synthetic-user", redis_store=self.store)
        service._attachment_service.get_for_stream = mock.Mock(side_effect=[current_states[0], *current_states])
        return service, service.iter_events(attachment_uid=self.uid, execution_id=self.execution_id)

    def test_revoked_scope_before_first_iteration_does_not_read_redis(self):
        _, events = self.consume([(0.1, [progress("forbidden", "1-0")])], [self.attachment])
        with mock.patch.object(ScopePermission, "check_scope_entry", side_effect=PermissionException("view", {})):
            self.assertEqual(list(events), [])
        self.assertEqual(self.store.blocks, [])
        self.connection.close.assert_called()

    def test_replaced_execution_before_first_iteration_resets_without_old_data(self):
        service, events = self.consume([(0.1, [progress("old", "1-0")])], [self.attachment])
        replaced = self.config.model_copy(update={"execution_id": uuid4(), "redis_key": "test:new-stream"})
        service._attachment_service.get_for_stream.side_effect = [
            self.make_attachment(stream_config=replaced.model_dump(mode="json"))
        ]
        first = next(events)
        self.assertEqual(first.event, PlatformStreamEvent.STREAM_RESET)
        self.assertEqual(first.data, {"reason": "execution_replaced"})
        self.assertEqual(list(events), [])
        self.assertEqual(self.store.blocks, [])

    def test_terminal_before_first_iteration_drains_same_execution_without_blocking(self):
        service, events = self.consume(
            [(0.1, [progress("A", "1-0")]), (0.1, [progress("B", "2-0")]), (1, [])],
            [self.attachment],
        )
        done = self.make_attachment(status=ExecutionStatus.SUCCESS)
        service._attachment_service.get_for_stream.return_value = done
        service._attachment_service.get_for_stream.side_effect = None
        received = list(events)
        self.assertEqual([e.data for e in received], [{"content": "A"}, {"content": "B"}, {"status": "SUCCESS"}])
        self.assertEqual(self.store.blocks, [0, 0, 0])

    def test_normal_progress_keeps_batch_order_and_identical_payloads(self):
        _, events = self.consume(
            [
                (0.1, [progress("A", "1-0"), progress("A", "2-0")]),
                (0.1, [progress("B", "3-0")]),
                (0.1, [terminal()]),
            ],
            [self.attachment],
        )

        received = list(events)

        self.assertEqual(
            [(event.event, event.stream_id, event.data) for event in received],
            [
                (None, "1-0", {"content": "A"}),
                (None, "2-0", {"content": "A"}),
                (None, "3-0", {"content": "B"}),
                (PlatformStreamEvent.STREAM_END, None, {}),
            ],
        )
        self.assertEqual(len(self.store.blocks), 3)

    def test_lost_terminal_is_synthesized_after_connection_is_established(self):
        _, events = self.consume(
            [(0.1, [progress("A", "1-0")]), (1, []), (1, [terminal()])],
            [self.attachment, self.make_attachment(status=ExecutionStatus.SUCCESS)],
        )

        received = list(events)

        self.assertEqual(
            [event.data if event is not None else None for event in received], [{"content": "A"}, {"status": "SUCCESS"}]
        )
        self.assertEqual(received[-1].event, PlatformStreamEvent.STREAM_END)
        self.assertIsNone(received[-1].stream_id)
        self.assertLessEqual(max(self.store.blocks), 1000)

    def test_continuous_live_cannot_hide_execution_replacement(self):
        replaced_config = self.config.model_copy(update={"execution_id": uuid4(), "redis_key": "test:new-stream"})
        _, events = self.consume(
            [(0.1, [progress("A", "1-0")]), (1, [progress("old-generation", "2-0")]), (1, [terminal()])],
            [self.attachment, self.make_attachment(stream_config=replaced_config.model_dump(mode="json"))],
        )

        received = list(events)

        self.assertEqual(
            [event.data if event is not None else None for event in received],
            [{"content": "A"}, {"reason": "execution_replaced"}],
        )
        self.assertEqual(received[-1].event, PlatformStreamEvent.STREAM_RESET)
        self.assertEqual(len(self.store.blocks), 2)

    def test_durable_terminal_drains_queued_progress_before_synthesizing_end(self):
        _, events = self.consume(
            [(0.1, [progress("A", "1-0")]), (1, [progress("B", "2-0")]), (0.1, [])],
            [self.attachment, self.make_attachment(status=ExecutionStatus.FAILED)],
        )

        received = list(events)

        self.assertEqual(
            [(event.event, event.stream_id, event.data) for event in received],
            [
                (None, "1-0", {"content": "A"}),
                (None, "2-0", {"content": "B"}),
                (PlatformStreamEvent.STREAM_END, None, {"status": "FAILED"}),
            ],
        )
        self.assertEqual(self.store.blocks[-1], 0)

    def test_durable_terminal_preserves_queued_redis_end_and_its_cursor(self):
        redis_end = UIStreamEvent(event=PlatformStreamEvent.STREAM_END, stream_id="3-0", data={"status": "SUCCESS"})
        _, events = self.consume(
            [(0.1, [progress("A", "1-0")]), (1, [progress("B", "2-0"), redis_end])],
            [self.attachment, self.make_attachment(status=ExecutionStatus.SUCCESS)],
        )

        self.assertEqual(
            [(event.event, event.stream_id, event.data) for event in events],
            [
                (None, "1-0", {"content": "A"}),
                (None, "2-0", {"content": "B"}),
                (PlatformStreamEvent.STREAM_END, "3-0", {"status": "SUCCESS"}),
            ],
        )

    def test_terminal_check_mid_batch_or_before_read_keeps_all_200_progress_events(self):
        for pause_after in (50, 100):
            with self.subTest(pause_after=pause_after):
                business = [progress(str(index), f"{index}-0") for index in range(1, 201)]
                redis_end = UIStreamEvent(
                    event=PlatformStreamEvent.STREAM_END, stream_id="201-0", data={"status": "SUCCESS"}
                )
                _, events = self.consume(
                    [(0.1, business[:100]), (0.1, business[100:]), (0.1, [redis_end])],
                    [self.attachment, self.make_attachment(status=ExecutionStatus.SUCCESS)],
                )
                received = [next(events) for _ in range(pause_after)]
                self.store.now += 1
                received.extend(events)

                self.assertEqual(received, [*business, redis_end])
                self.assertEqual(self.store.cursors, ["0-0", "100-0", "200-0"])
                self.assertEqual(self.store.blocks[1:], [0, 0])

    def test_terminal_drain_advances_past_dirty_only_batch_before_later_progress(self):
        _, events = self.consume(
            [
                (0.1, [progress("A", "1-0")]),
                (1, StreamReadResult(events=[], last_seen_stream_id="2-0")),
                (0.1, [progress("B", "3-0")]),
                (0.1, []),
            ],
            [self.attachment, self.make_attachment(status=ExecutionStatus.SUCCESS)],
        )

        self.assertEqual([event.data for event in events], [{"content": "A"}, {"content": "B"}, {"status": "SUCCESS"}])
        self.assertEqual(self.store.cursors, ["0-0", "1-0", "2-0", "3-0"])
        self.assertEqual(self.store.blocks[2:], [0, 0])

    def test_deleted_or_hidden_attachment_stops_without_leaking_queued_data(self):
        _, events = self.consume(
            [(0.1, [progress("A", "1-0")]), (1, [progress("hidden", "2-0")]), (1, [terminal()])],
            [self.attachment, AttachmentNotFound()],
        )

        self.assertEqual([event.data for event in events], [{"content": "A"}])

    def test_scope_revocation_stops_without_leaking_queued_data(self):
        _, events = self.consume(
            [(0.1, [progress("A", "1-0")]), (1, [progress("forbidden", "2-0")]), (1, [terminal()])],
            [self.attachment, self.attachment],
        )
        with mock.patch.object(
            ScopePermission, "check_scope_entry", side_effect=[None, PermissionException("view", {})]
        ):
            self.assertEqual([event.data for event in events], [{"content": "A"}])

    def test_healthy_db_connection_is_released_before_live_read_and_on_close(self):
        _, events = self.consume([(0.1, [progress("A", "1-0")])], [self.attachment])

        self.connection.close.assert_called_once_with()
        self.assertEqual(next(events).data, {"content": "A"})
        events.close()
        self.assertGreaterEqual(self.connection.close.call_count, 2)

    def test_refresh_failure_releases_connection_before_propagating(self):
        _, events = self.consume(
            [(0.1, [progress("A", "1-0")]), (1, [])],
            [self.attachment, RuntimeError("synthetic refresh failure")],
        )
        self.assertEqual(next(events).data, {"content": "A"})
        self.connection.close.reset_mock()

        with self.assertRaisesRegex(RuntimeError, "synthetic refresh failure"):
            next(events)

        self.connection.close.assert_called()

    def test_read_block_uses_remaining_state_poll_budget(self):
        _, events = self.consume(
            [(0.9, [progress("A", "1-0")]), (0.1, [terminal()])],
            [self.attachment, self.attachment],
        )

        list(events)

        self.assertLessEqual(self.store.blocks[1], 101)


class AttachmentStreamResourceCloseTest(SimpleTestCase):
    def setUp(self):
        username = mock.patch(
            "services.web.ai_assistant.resources.stream.get_request_username", return_value="synthetic-user"
        )
        username.start()
        self.addCleanup(username.stop)

    def request_stream(self, events):
        with mock.patch.object(AttachmentStreamService, "iter_events", return_value=events):
            return GetAttachmentStream().request(attachment_uid=str(uuid4()), execution_id=str(uuid4()))

    def test_resource_close_without_first_read_closes_source(self):
        source = mock.MagicMock()
        source.__iter__.side_effect = lambda: source
        source.__next__.side_effect = StopIteration
        response = self.request_stream(source)
        self.addCleanup(response.close)

        response.close()
        source.close.assert_called_once_with()

    def test_resource_propagates_visibility_failure_before_response(self):
        with mock.patch.object(AttachmentStreamService, "iter_events", side_effect=AttachmentNotFound()):
            with self.assertRaises(AttachmentNotFound):
                GetAttachmentStream().request(attachment_uid=str(uuid4()), execution_id=str(uuid4()))

    def test_direct_encoder_closes_source_on_exhaustion_and_error(self):
        def broken_events():
            yield progress("A", "1-0")
            raise RuntimeError("synthetic encoding source failure")

        for source_iterator, raises in ((iter([progress("A", "1-0")]), False), (broken_events(), True)):
            with self.subTest(raises=raises):
                source = mock.MagicMock()
                source.__iter__.side_effect = lambda: source
                source.__next__.side_effect = source_iterator.__next__
                encoded = GetAttachmentStream._encode(source)
                if raises:
                    with self.assertRaisesRegex(RuntimeError, "synthetic encoding source failure"):
                        list(encoded)
                else:
                    self.assertEqual(list(encoded), [b'id: 1-0\ndata: {"content":"A"}\n\n'])
                source.close.assert_called_once_with()

    def test_encoder_requires_iterator_ownership(self):
        with self.assertRaises(TypeError):
            GetAttachmentStream._encode([])

    def test_encoder_preserves_heartbeat_and_audit_error_mapping(self):
        invalid = UIStreamEvent(data={"invalid": float("nan")})
        source = mock.MagicMock()
        source.__iter__.side_effect = lambda: source
        source.__next__.side_effect = iter([None, invalid]).__next__
        encoded = GetAttachmentStream._encode(source)

        self.assertEqual(next(encoded), b": heartbeat\n\n")
        with self.assertRaises(InvalidStreamEvent):
            next(encoded)
        encoded.close()
        source.close.assert_called_once_with()

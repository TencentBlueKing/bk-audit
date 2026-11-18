"""Synthetic loopback HTTP exercises resource validation, SSE bytes, and durable recovery.

The live-store port deliberately loses terminal/reset notifications. Actual ORM reads,
resource serializers, WSGI output and client SSE parsing remain in the path.
"""

import json
import threading
import time
from socketserver import TCPServer
from unittest import mock
from urllib.parse import parse_qs
from uuid import uuid4
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

import requests
from django import db
from django.core.serializers.json import DjangoJSONEncoder
from django.http import HttpResponse
from django.test import TransactionTestCase, override_settings
from ui_stream.types import ReadBatch as StreamReadResult

from services.web.ai_assistant.constants import (
    AttachmentType,
    ExecutionStatus,
    MessageType,
)
from services.web.ai_assistant.models import Attachment, Message
from services.web.ai_assistant.resources.attachment import GetAttachment
from services.web.ai_assistant.resources.stream import (
    GetAttachmentStream,
    GetAttachmentStreamSnapshot,
)
from services.web.ai_assistant.schemas import AttachmentStreamConfig, UIStreamEvent
from services.web.ai_assistant.services.attachment_stream import AttachmentStreamService
from services.web.common.scope_permission import ScopePermission
from tests.test_ai_assistant.factories import create_conversation
from tests.test_ai_assistant.handlers import (
    EchoAttachmentStreamHandler,
    use_attachment_handler,
)
from tests.test_ai_assistant.http_integration import iter_http_sse_frames


class NotificationDroppingLiveStore:
    def __init__(self):
        self.release = threading.Event()
        self.reads = 0

    def read(self, *, redis_key, after_id, block_ms):
        self.reads += 1
        if self.reads == 1:
            event = UIStreamEvent(stream_id="1-0", data={"content": "live-prefix"})
        elif self.reads == 2:
            if not self.release.wait(3):
                raise AssertionError("HTTP consumer did not update durable state")
            time.sleep(0.06)
            event = UIStreamEvent(stream_id="2-0", data={"content": "queued-live-tail"})
        else:
            if self.reads > 3:
                raise AssertionError("empty terminal tail did not end the stream")
            return StreamReadResult(events=[], last_seen_stream_id=None)
        return StreamReadResult(events=[event], last_seen_stream_id=event.stream_id)


class LoopbackWSGIServer(WSGIServer):
    def server_bind(self):
        # Avoid reverse DNS while retaining a real standard-library WSGI/socket boundary.
        TCPServer.server_bind(self)
        self.server_name = "localhost"
        self.server_port = self.server_address[1]
        self.setup_environ()


class QuietWSGIHandler(WSGIRequestHandler):
    def log_message(self, format, *args):
        pass


@override_settings(AI_ASSISTANT_STREAM_STATE_POLL_INTERVAL=0.05)
class AttachmentStreamHttpRecoveryTest(TransactionTestCase):
    available_apps = ["services.web.ai_assistant"]

    def setUp(self):
        self.user = "synthetic-http-user"
        use_attachment_handler(self, EchoAttachmentStreamHandler())
        patchers = [
            mock.patch.object(ScopePermission, "check_scope_entry"),
            mock.patch("services.web.ai_assistant.resources.stream.get_request_username", return_value=self.user),
            mock.patch("services.web.ai_assistant.resources.attachment.get_request_username", return_value=self.user),
        ]
        for patcher in patchers:
            patcher.start()
            self.addCleanup(patcher.stop)
        conversation = create_conversation(created_by=self.user, updated_by=self.user)
        source = Message.objects.create(
            conversation=conversation,
            message_type=MessageType.LOG_SEARCH,
            status=ExecutionStatus.SUCCESS,
            input_data={"text": "synthetic-query"},
            context_data={"prefix": "synthetic"},
            output_data={"content": "synthetic-source"},
            created_by=self.user,
            updated_by=self.user,
        )
        self.config = AttachmentStreamConfig(task_id="synthetic-task", execution_id=uuid4(), redis_key="synthetic:http")
        self.attachment = Attachment.objects.create(
            source_message=source,
            attachment_type=AttachmentType.AI_ANALYSIS,
            title="Synthetic recovery",
            status=ExecutionStatus.PROCESSING,
            task_id=self.config.task_id,
            input_data={"text": "synthetic-input"},
            context_data={"prefix": "synthetic"},
            is_stream=True,
            stream_config=self.config.model_dump(mode="json"),
            created_by=self.user,
            updated_by=self.user,
        )
        self.live = NotificationDroppingLiveStore()
        redis = mock.patch.object(
            AttachmentStreamService, "redis_store", new_callable=mock.PropertyMock, return_value=self.live
        )
        redis.start()
        self.addCleanup(redis.stop)
        self.server = make_server(
            "127.0.0.1", 0, self.application, server_class=LoopbackWSGIServer, handler_class=QuietWSGIHandler
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"
        self.session = requests.Session()
        self.addCleanup(self.session.close)

    def stop_server(self):
        self.live.release.set()
        self.server.shutdown()
        self.thread.join(timeout=3)
        self.server.server_close()
        self.assertFalse(self.thread.is_alive())

    def application(self, environ, start_response):
        response = None
        try:
            params = {"attachment_uid": str(self.attachment.uid)}
            if environ["PATH_INFO"] == "/stream":
                params["execution_id"] = parse_qs(environ["QUERY_STRING"])["execution_id"][0]
                response = GetAttachmentStream().request(**params)
            else:
                resource = GetAttachmentStreamSnapshot() if environ["PATH_INFO"] == "/snapshot" else GetAttachment()
                data = resource.request(**params)
                response = HttpResponse(json.dumps(data, cls=DjangoJSONEncoder), content_type="application/json")
            start_response(f"{response.status_code} OK", list(response.items()))
            yield from response
        finally:
            if response is not None:
                response.close()
            db.connections.close_all()

    def open_stream(self):
        snapshot = self.session.get(f"{self.base_url}/snapshot", timeout=3).json()
        self.assertEqual(snapshot["execution_id"], str(self.config.execution_id))
        response = self.session.get(
            f"{self.base_url}/stream",
            params={"execution_id": snapshot["execution_id"]},
            headers={"Accept": "text/event-stream"},
            stream=True,
            timeout=(1, 3),
        )
        self.addCleanup(response.close)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Content-Type"], "text/event-stream")
        frames = iter_http_sse_frames(response, timeout=3)
        first = next(frames)
        self.assertEqual((first.event, first.stream_id, first.data), (None, "1-0", {"content": "live-prefix"}))
        return frames

    def test_lost_terminal_closes_http_stream_and_recovers_real_saved_result(self):
        frames = self.open_stream()
        Attachment.objects.filter(pk=self.attachment.pk).update(
            status=ExecutionStatus.SUCCESS,
            output_data={"content": "saved-result"},
        )
        self.live.release.set()

        received = list(frames)

        self.assertEqual(
            [(frame.event, frame.stream_id, frame.data) for frame in received],
            [
                (None, "2-0", {"content": "queued-live-tail"}),
                ("platform.stream_end", None, {"status": "SUCCESS"}),
            ],
        )
        detail_response = self.session.get(f"{self.base_url}/detail", timeout=3)
        self.assertEqual(detail_response.status_code, 200)
        detail = detail_response.json()
        self.assertEqual(detail["uid"], str(self.attachment.uid))
        self.assertEqual(detail["status"], "SUCCESS")
        self.assertEqual(detail["output_data"], {"content": "saved-result"})
        self.assertEqual(self.live.reads, 3)

    def test_lost_reset_closes_old_http_stream_and_reads_new_snapshot(self):
        frames = self.open_stream()
        replacement = self.config.model_copy(update={"execution_id": uuid4(), "redis_key": "synthetic:new-http"})
        Attachment.objects.filter(pk=self.attachment.pk).update(
            stream_config=replacement.model_dump(mode="json"),
            stream_archive=[{"event": None, "stream_id": "7-0", "data": {"content": "new-generation"}}],
        )
        self.live.release.set()

        received = list(frames)

        self.assertEqual(
            [(frame.event, frame.stream_id, frame.data) for frame in received],
            [
                ("platform.stream_reset", None, {"reason": "execution_replaced"}),
            ],
        )
        snapshot = self.session.get(f"{self.base_url}/snapshot", timeout=3).json()
        self.assertEqual(
            snapshot,
            {
                "events": [{"event": None, "stream_id": "7-0", "data": {"content": "new-generation"}}],
                "execution_id": str(replacement.execution_id),
                "latest_stream_id": "7-0",
                "archive_status": "COMPLETE",
            },
        )
        detail = self.session.get(f"{self.base_url}/detail", timeout=3).json()
        self.assertEqual((detail["status"], detail["output_data"]), ("PROCESSING", None))
        self.assertEqual(self.live.reads, 2)

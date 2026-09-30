import threading
from datetime import timedelta
from unittest import mock

import requests
from django.conf import settings
from django.test import LiveServerTestCase, SimpleTestCase, override_settings
from django.utils import timezone
from rest_framework.permissions import AllowAny

from core.exceptions import PermissionException
from services.web.ai_assistant.constants import (
    AttachmentType,
    ExecutionStatus,
    FeedbackSourceType,
    FeedbackType,
    MessageType,
    PlatformStreamEvent,
    SidebarNodeType,
)
from services.web.ai_assistant.models import Attachment
from services.web.ai_assistant.schemas import parse_stream_config
from services.web.ai_assistant.streaming import RedisLiveStore
from services.web.ai_assistant.views import (
    AttachmentsViewSet,
    ConversationGroupsViewSet,
    ConversationSidebarNodesViewSet,
    ConversationsViewSet,
    FeedbackViewSet,
    MessagesViewSet,
)
from services.web.common.constants import ScopeType
from services.web.common.scope_permission import ScopePermission
from tests.test_ai_assistant.celery_integration import running_celery_worker
from tests.test_ai_assistant.handlers import use_attachment_handler, use_message_handler
from tests.test_ai_assistant.http_integration import (
    iter_http_sse_frames,
    iter_sse_frames,
    start_http_sse_collector,
    wait_for_http_json,
)
from tests.test_ai_assistant.integration_handlers import (
    INTEGRATION_QUEUE,
    RealAttachmentHttpFailOnceHandler,
    RealAttachmentHttpStreamHandler,
    RealAttachmentHttpStreamRetryHandler,
    RealAttachmentSuccessHandler,
    RealMessageSuccessHandler,
    http_stream_release,
    http_stream_started,
    release_http_stream_events,
    reset_http_attachment_fail_once,
    reset_http_stream_events,
)
from tests.test_ai_assistant.stream_cleanup import delete_attachment_stream_keys

HTTP_USER = "alice"
INTERNAL_FIELDS = ("task_id", "context_data", "stream_config")
USERNAME_TARGETS = (
    "services.web.ai_assistant.permissions.get_request_username",
    "services.web.ai_assistant.resources.conversation.get_request_username",
    "services.web.ai_assistant.resources.message.get_request_username",
    "services.web.ai_assistant.resources.attachment.get_request_username",
    "services.web.ai_assistant.resources.feedback.get_request_username",
    "services.web.ai_assistant.resources.stream.get_request_username",
)


class SSEParserTest(SimpleTestCase):
    def test_iter_sse_frames_parses_default_named_id_json_and_heartbeat(self):
        frames = list(
            iter_sse_frames(
                [
                    b'data: {"delta":"hello"}\n',
                    b"\n",
                    b"event: platform.stream_end\n",
                    b"id: 2-0\n",
                    b'data: {"status":"SUCCESS"}\n',
                    b"\n",
                    b": heartbeat\n",
                    b"\n",
                    b"id: 1-0\n",
                    b'data: {"step":1}\n',
                    b"\n",
                    b"id: 1-1\n",
                    b'data: {"step":2}\n',
                    b"\n",
                ]
            )
        )

        self.assertEqual(len(frames), 4)
        self.assertIsNone(frames[0].event)
        self.assertIsNone(frames[0].stream_id)
        self.assertEqual(frames[0].data, {"delta": "hello"})
        self.assertEqual(frames[1].event, "platform.stream_end")
        self.assertEqual(frames[1].stream_id, "2-0")
        self.assertEqual(frames[1].data, {"status": "SUCCESS"})
        self.assertEqual(frames[2].stream_id, "1-0")
        self.assertEqual(frames[2].data, {"step": 1})
        self.assertEqual(frames[3].stream_id, "1-1")
        self.assertEqual(frames[3].data, {"step": 2})

    def test_iter_http_sse_frames_disables_requests_chunk_buffering(self):
        response = mock.Mock(url="http://test/stream")
        response.iter_lines.return_value = iter([b'data: {"step":1}', b""])

        frames = list(iter_http_sse_frames(response))

        response.iter_lines.assert_called_once_with(chunk_size=1)
        self.assertEqual(frames[0].data, {"step": 1})

    def test_iter_http_sse_frames_enforces_overall_deadline(self):
        response = mock.Mock(url="http://test/stream")
        response.iter_lines.return_value = iter([b": heartbeat"])

        with (
            mock.patch("tests.test_ai_assistant.http_integration.time.monotonic", side_effect=[0.0, 2.0]),
            self.assertRaisesRegex(TimeoutError, "SSE 读取超时"),
        ):
            list(iter_http_sse_frames(response, timeout=1))


class HttpIntegrationTest(LiveServerTestCase):
    """真实 HTTP 走中间件和 Worker，验证消息、附件与 SSE 主链路。"""

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
        cls._username_patchers = [mock.patch(target, return_value=HTTP_USER) for target in USERNAME_TARGETS]
        for patcher in cls._username_patchers:
            patcher.start()
        cls._scope_patchers = [
            mock.patch.object(ScopePermission, "check_scope_entry"),
            mock.patch.object(ScopePermission, "get_scene_ids", return_value=[1]),
            mock.patch.object(ScopePermission, "get_system_ids", return_value=["bk-audit"]),
        ]
        for patcher in cls._scope_patchers:
            patcher.start()
        cls._view_auth_originals = {}
        for viewset in (
            ConversationGroupsViewSet,
            ConversationsViewSet,
            ConversationSidebarNodesViewSet,
            FeedbackViewSet,
            MessagesViewSet,
            AttachmentsViewSet,
        ):
            cls._view_auth_originals[viewset] = (viewset.authentication_classes, viewset.permission_classes)
            viewset.authentication_classes = []
            viewset.permission_classes = [AllowAny]
        super().setUpClass()
        cls.worker_context = running_celery_worker(queue_name=INTEGRATION_QUEUE)
        cls.worker_context.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.worker_context.__exit__(None, None, None)
        for viewset, originals in cls._view_auth_originals.items():
            viewset.authentication_classes, viewset.permission_classes = originals
        for patcher in cls._username_patchers:
            patcher.stop()
        for patcher in cls._scope_patchers:
            patcher.stop()
        cls._settings_override.disable()
        super().tearDownClass()

    def setUp(self):
        reset_http_stream_events()
        reset_http_attachment_fail_once()
        self._sse_collectors: list[threading.Thread] = []
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    def tearDown(self):
        release_http_stream_events()
        for thread in self._sse_collectors:
            thread.join(timeout=settings.CELERY_TEST_TASK_TIMEOUT)
        leftovers = delete_attachment_stream_keys(
            attachment_uids=Attachment.objects.filter(is_stream=True).values_list("uid", flat=True)
        )
        self.session.close()
        reset_http_stream_events()
        if leftovers:
            raise AssertionError(f"专项 Redis key 残留: {leftovers}")

    def api_url(self, path: str) -> str:
        return f"{self.live_server_url}/api/v1/ai_assistant{path}"

    def unwrap(self, response) -> dict:
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertTrue(payload["result"], payload)
        self.assertEqual(payload["code"], 0)
        return payload["data"]

    def assert_public_envelope(self, data: dict) -> None:
        for field_name in INTERNAL_FIELDS:
            self.assertNotIn(field_name, data)

    def create_group(self, *, name: str, scope_type: str = "scene", scope_id: str = "1") -> dict:
        """通过真实 HTTP 创建绑定到具体 scope 的会话分组。"""

        return self.unwrap(
            self.session.post(
                self.api_url("/conversation_groups/"),
                json={"name": name, "scope_type": scope_type, "scope_id": scope_id},
            )
        )

    def create_conversation(
        self,
        *,
        scope_type: str = "scene",
        scope_id: str = "1",
        group_uid: str | None = None,
    ) -> dict:
        """通过真实 HTTP 创建绑定到具体 scope 的会话。"""

        data = {"scope_type": scope_type, "scope_id": scope_id}
        if group_uid:
            data["group_uid"] = group_uid
        return self.unwrap(self.session.post(self.api_url("/conversations/"), json=data))

    def create_message(self, *, conversation_uid: str, text: str) -> dict:
        return self.unwrap(
            self.session.post(
                self.api_url("/messages/"),
                json={
                    "conversation_uid": conversation_uid,
                    "message_type": MessageType.USER_INTENT,
                    "input_data": {"text": text},
                },
            )
        )

    def wait_status(self, path: str, status: str) -> dict:
        payload = wait_for_http_json(
            session=self.session,
            url=self.api_url(path),
            predicate=lambda data: data.get("status") == status,
        )
        self.assertTrue(payload["result"], payload)
        return payload["data"]

    def create_success_message(self, *, text: str = "query") -> dict:
        use_message_handler(self, RealMessageSuccessHandler())
        conversation = self.create_conversation()
        created = self.create_message(conversation_uid=conversation["uid"], text=text)
        self.assertEqual(created["status"], ExecutionStatus.PROCESSING)
        self.assert_public_envelope(created)
        completed = self.wait_status(f"/messages/{created['uid']}/", ExecutionStatus.SUCCESS)
        self.assert_public_envelope(completed)
        self.assertEqual(completed["output_data"], {"content": f"real:{text}"})
        return completed

    def first_live_stream_id(self, *, attachment_uid: str) -> str:
        """读取 Worker 已写入 Redis 的首条事件游标。

        LiveServer/wsgiref 会缓冲整段 ``StreamingHttpResponse``，测试进程无法在
        释放 Worker 前从 HTTP 响应里读到 SSE ``id``。该游标与首帧 ``id`` 同源。
        """

        attachment = Attachment.objects.get(uid=attachment_uid)
        config = parse_stream_config(attachment.stream_config)
        self.assertIsNotNone(config)
        result = RedisLiveStore().read(redis_key=config.redis_key, after_id="0-0", block_ms=100)
        self.assertTrue(result.events, "Redis 中应已有首条流式事件")
        cursor = result.events[0].stream_id
        self.assertTrue(cursor)
        return cursor

    def start_sse_request(
        self, *, attachment_uid: str, execution_id: str, last_event_id: str | None = None, terminal_event: str
    ):
        """在独立线程发起 SSE，避免 LiveServer 缓冲导致 get() 阻塞到流结束。"""

        headers = {}
        if last_event_id:
            headers["Last-Event-ID"] = last_event_id
        frames, done, thread, errors = start_http_sse_collector(
            session=self.session,
            url=self.api_url(f"/attachments/{attachment_uid}/stream/"),
            params={"execution_id": execution_id},
            headers=headers,
            terminal_event=terminal_event,
        )
        self._sse_collectors.append(thread)
        return frames, done, thread, errors

    def test_async_message_creates_and_reaches_success_over_http(self):
        completed = self.create_success_message(text="http-message")
        self.assertEqual(completed["message_type"], MessageType.USER_INTENT)
        self.assertEqual(completed["input_data"], {"text": "http-message"})

    def test_scope_bound_resources_are_isolated_and_rechecked_over_http(self):
        """验证 scope 从会话绑定派生，并贯穿列表、产物、反馈及权限变化。"""

        allowed_scenes = {1, 2}
        allowed_systems = {"bk-audit"}

        def permission_error():
            """创建 scope 权限被撤销时的公开异常。"""

            return PermissionException(action_name="访问 AI 助手资源", permission={}, apply_url="")

        def get_scene_ids(_permission, scope, _action):
            """按当前用例的授权场景集合返回 concrete/cross 可见范围。"""

            if not scope.is_scene_scope:
                return []
            if scope.is_cross_scope:
                return sorted(allowed_scenes)
            scene_id = int(scope.scope_id)
            return [scene_id] if scene_id in allowed_scenes else []

        def get_system_ids(_permission, scope, _action):
            """按当前用例的授权系统集合返回 concrete/cross 可见范围。"""

            if not scope.is_system_scope:
                return []
            if scope.is_cross_scope:
                return sorted(allowed_systems)
            return [scope.scope_id] if scope.scope_id in allowed_systems else []

        def check_scope_entry(_permission, scope, _action, raise_exception=True):
            """将直接资源访问限制在当前用例的可变授权集合中。"""

            if scope.is_scene_scope:
                permitted = bool(get_scene_ids(None, scope, None))
            else:
                permitted = bool(get_system_ids(None, scope, None))
            if not permitted and raise_exception:
                raise permission_error()
            return permitted

        class FeedbackEnabledMessageHandler(RealMessageSuccessHandler):
            supports_feedback = True

        with (
            mock.patch.object(ScopePermission, "get_scene_ids", new=get_scene_ids),
            mock.patch.object(ScopePermission, "get_system_ids", new=get_system_ids),
            mock.patch.object(ScopePermission, "check_scope_entry", new=check_scope_entry),
        ):
            use_message_handler(self, FeedbackEnabledMessageHandler())
            use_attachment_handler(self, RealAttachmentSuccessHandler())

            scene_one_group = self.create_group(name="scene 1 分组")
            scene_one = self.create_conversation(scope_type="scene", scope_id="1", group_uid=scene_one_group["uid"])
            self.assertEqual((scene_one["scope_type"], scene_one["scope_id"]), ("scene", "1"))

            # 消息请求只有 conversation_uid 和业务输入；scope 由会话绑定提供。
            scene_one_created = self.create_message(conversation_uid=scene_one["uid"], text="scene-one")
            scene_one_message = self.wait_status(f"/messages/{scene_one_created['uid']}/", ExecutionStatus.SUCCESS)
            self.assertEqual(scene_one_message["input_data"], {"text": "scene-one"})
            self.assertEqual(scene_one_message["output_data"], {"content": "real:scene-one"})
            stored_message = self.unwrap(self.session.get(self.api_url(f"/messages/{scene_one_created['uid']}/")))
            self.assertNotIn("scope_type", stored_message["input_data"])
            self.assertNotIn("scope_id", stored_message["input_data"])

            feedback = self.unwrap(
                self.session.post(
                    self.api_url("/feedback/"),
                    json={
                        "source_type": FeedbackSourceType.MESSAGE,
                        "source_uid": scene_one_created["uid"],
                        "feedback_type": FeedbackType.LIKE,
                    },
                )
            )
            self.assertEqual(feedback["source_uid"], scene_one_created["uid"])

            def create_attachment(message_uid: str, *, text: str) -> dict:
                """创建并等待来源消息的分析附件进入成功终态。"""

                created = self.unwrap(
                    self.session.post(
                        self.api_url(f"/messages/{message_uid}/attachments/"),
                        json={"attachment_type": AttachmentType.AI_ANALYSIS, "input_data": {"text": text}},
                    )
                )
                completed = self.wait_status(f"/attachments/{created['uid']}/", ExecutionStatus.SUCCESS)
                return completed

            scene_one_attachment = create_attachment(scene_one_created["uid"], text="scene-one-report")
            scene_two = self.create_conversation(scope_type="scene", scope_id="2")
            scene_two_created = self.create_message(conversation_uid=scene_two["uid"], text="scene-two")
            self.wait_status(f"/messages/{scene_two_created['uid']}/", ExecutionStatus.SUCCESS)
            scene_two_attachment = create_attachment(scene_two_created["uid"], text="scene-two-report")
            system_conversation = self.create_conversation(scope_type="system", scope_id="bk-audit")
            system_created = self.create_message(conversation_uid=system_conversation["uid"], text="system")
            self.wait_status(f"/messages/{system_created['uid']}/", ExecutionStatus.SUCCESS)
            system_attachment = create_attachment(system_created["uid"], text="system-report")

            # 固定更新时间以验证 cross_scene 聚合顺序，不依赖异步任务执行快慢。
            newest = timezone.now()
            Attachment.objects.filter(uid=scene_two_attachment["uid"]).update(content_updated_at=newest)
            Attachment.objects.filter(uid=scene_one_attachment["uid"]).update(
                content_updated_at=newest - timedelta(minutes=1)
            )
            Attachment.objects.filter(uid=system_attachment["uid"]).update(
                content_updated_at=newest + timedelta(minutes=1)
            )

            def attachment_list(scope_type: str, scope_id: str | None = None) -> list[dict]:
                """读取指定查询 scope 下的附件摘要列表。"""

                params = {"scope_type": scope_type}
                if scope_id is not None:
                    params["scope_id"] = scope_id
                return self.unwrap(self.session.get(self.api_url("/attachments/"), params=params))

            scene_one_list = attachment_list("scene", "1")
            self.assertEqual([item["uid"] for item in scene_one_list], [scene_one_attachment["uid"]])
            self.assertEqual(
                (scene_one_list[0]["scope_type"], scene_one_list[0]["scope_id"]),
                ("scene", "1"),
            )
            scene_two_list = attachment_list("scene", "2")
            self.assertEqual([item["uid"] for item in scene_two_list], [scene_two_attachment["uid"]])

            cross_scene_list = attachment_list("cross_scene")
            self.assertEqual(
                [item["uid"] for item in cross_scene_list],
                [scene_two_attachment["uid"], scene_one_attachment["uid"]],
            )
            self.assertEqual(
                {(item["scope_type"], item["scope_id"]) for item in cross_scene_list},
                {("scene", "1"), ("scene", "2")},
            )
            cross_system_list = attachment_list("cross_system")
            self.assertEqual([item["uid"] for item in cross_system_list], [system_attachment["uid"]])
            self.assertEqual(
                (cross_system_list[0]["scope_type"], cross_system_list[0]["scope_id"]), ("system", "bk-audit")
            )

            def sidebar_nodes(
                scope_type: str,
                scope_id: str | None = None,
                *,
                parent_node_uid: str | None = None,
            ) -> list[dict]:
                """读取指定查询 scope 和可选分组容器中的侧栏节点。"""

                params = {"scope_type": scope_type}
                if scope_id is not None:
                    params["scope_id"] = scope_id
                if parent_node_uid is not None:
                    params["parent_node_type"] = SidebarNodeType.GROUP
                    params["parent_node_uid"] = parent_node_uid
                data = self.unwrap(self.session.get(self.api_url("/conversation_sidebar/nodes/"), params=params))
                return data["results"]

            scene_two_nodes = sidebar_nodes("scene", "2")
            self.assertNotIn(scene_one["uid"], {node["node_uid"] for node in scene_two_nodes})
            cross_scene_nodes = sidebar_nodes("cross_scene")
            self.assertIn(scene_one_group["uid"], {node["node_uid"] for node in cross_scene_nodes})
            self.assertIn(scene_two["uid"], {node["node_uid"] for node in cross_scene_nodes})
            self.assertNotIn(system_conversation["uid"], {node["node_uid"] for node in cross_scene_nodes})
            cross_scene_group_nodes = sidebar_nodes("cross_scene", parent_node_uid=scene_one_group["uid"])
            self.assertEqual({node["node_uid"] for node in cross_scene_group_nodes}, {scene_one["uid"]})
            cross_system_nodes = sidebar_nodes("cross_system")
            self.assertEqual({node["node_uid"] for node in cross_system_nodes}, {system_conversation["uid"]})

            move_response = self.session.post(
                self.api_url("/conversation_sidebar/nodes/move/"),
                json={
                    "scope_type": ScopeType.CROSS_SCENE,
                    "scope_id": "",
                    "source_node_type": SidebarNodeType.CONVERSATION,
                    "source_node_uid": scene_one["uid"],
                },
            )
            self.assertNotEqual(move_response.status_code, 200, move_response.text)
            clear_response = self.session.post(
                self.api_url("/conversations/clear/"),
                json={"scope_type": ScopeType.CROSS_SCENE, "scope_id": ""},
            )
            self.assertNotEqual(clear_response.status_code, 200, clear_response.text)

            allowed_scenes.remove(1)
            revoked_cross_scene = attachment_list("cross_scene")
            self.assertEqual([item["uid"] for item in revoked_cross_scene], [scene_two_attachment["uid"]])
            revoked_sidebar = sidebar_nodes("cross_scene")
            self.assertNotIn(scene_one_group["uid"], {node["node_uid"] for node in revoked_sidebar})
            denied_conversation = self.session.get(self.api_url(f"/conversations/{scene_one['uid']}/"))
            self.assertEqual(denied_conversation.status_code, 403, denied_conversation.text)
            denied_detail = self.session.get(self.api_url(f"/attachments/{scene_one_attachment['uid']}/"))
            self.assertEqual(denied_detail.status_code, 403, denied_detail.text)
            allowed_scenes.add(1)
            restored_cross_scene = attachment_list("cross_scene")
            self.assertEqual(
                [item["uid"] for item in restored_cross_scene],
                [scene_two_attachment["uid"], scene_one_attachment["uid"]],
            )

    def test_async_attachment_creates_and_retries_after_failure_over_http(self):
        source = self.create_success_message(text="source")
        use_attachment_handler(self, RealAttachmentHttpFailOnceHandler())

        created = self.unwrap(
            self.session.post(
                self.api_url(f"/messages/{source['uid']}/attachments/"),
                json={"attachment_type": AttachmentType.AI_ANALYSIS, "input_data": {"text": "analyse"}},
            )
        )
        self.assertEqual(created["status"], ExecutionStatus.PROCESSING)
        self.assert_public_envelope(created)
        failed = self.wait_status(f"/attachments/{created['uid']}/", ExecutionStatus.FAILED)
        self.assert_public_envelope(failed)

        retried = self.unwrap(self.session.post(self.api_url(f"/attachments/{created['uid']}/retry/"), json={}))
        self.assertEqual(retried["status"], ExecutionStatus.PROCESSING)
        completed = self.wait_status(f"/attachments/{created['uid']}/", ExecutionStatus.SUCCESS)
        self.assertEqual(completed["output_data"], {"content": "http-retry:success"})
        self.assert_public_envelope(completed)

    def test_stream_attachment_emits_business_events_and_terminal_over_http(self):
        source = self.create_success_message(text="source")
        use_attachment_handler(self, RealAttachmentHttpStreamHandler())

        created = self.unwrap(
            self.session.post(
                self.api_url(f"/messages/{source['uid']}/attachments/"),
                json={"attachment_type": AttachmentType.AI_ANALYSIS, "input_data": {"text": "stream"}},
            )
        )
        self.assertTrue(http_stream_started.wait(settings.CELERY_TEST_TASK_TIMEOUT))
        snapshot = self.unwrap(self.session.get(self.api_url(f"/attachments/{created['uid']}/stream/snapshot/")))
        execution_id = snapshot["execution_id"]
        self.assertTrue(execution_id)

        frames, done, thread, errors = self.start_sse_request(
            attachment_uid=created["uid"],
            execution_id=execution_id,
            terminal_event=PlatformStreamEvent.STREAM_END,
        )
        http_stream_release.set()
        self.assertTrue(done.wait(settings.CELERY_TEST_TASK_TIMEOUT))
        thread.join(timeout=1)
        self.assertFalse(errors, errors)

        business = [frame.data for frame in frames if frame.event is None]
        self.assertEqual(business, [{"step": 1}, {"step": 2}])
        self.assertEqual(frames[-1].event, PlatformStreamEvent.STREAM_END)
        self.assertEqual(frames[-1].data, {"status": ExecutionStatus.SUCCESS})
        detail = self.wait_status(f"/attachments/{created['uid']}/", ExecutionStatus.SUCCESS)
        self.assertEqual(detail["output_data"], {"content": "http-stream:success"})
        self.assert_public_envelope(detail)

    def test_last_event_id_filters_consumed_event_over_http(self):
        source = self.create_success_message(text="source")
        use_attachment_handler(self, RealAttachmentHttpStreamHandler())
        created = self.unwrap(
            self.session.post(
                self.api_url(f"/messages/{source['uid']}/attachments/"),
                json={"attachment_type": AttachmentType.AI_ANALYSIS, "input_data": {"text": "resume"}},
            )
        )
        self.assertTrue(http_stream_started.wait(settings.CELERY_TEST_TASK_TIMEOUT))
        snapshot = self.unwrap(self.session.get(self.api_url(f"/attachments/{created['uid']}/stream/snapshot/")))
        cursor = self.first_live_stream_id(attachment_uid=created["uid"])
        frames, done, thread, errors = self.start_sse_request(
            attachment_uid=created["uid"],
            execution_id=snapshot["execution_id"],
            last_event_id=cursor,
            terminal_event=PlatformStreamEvent.STREAM_END,
        )
        http_stream_release.set()
        self.assertTrue(done.wait(settings.CELERY_TEST_TASK_TIMEOUT))
        thread.join(timeout=1)
        self.assertFalse(errors, errors)
        self.assertFalse(any(frame.data == {"step": 1} for frame in frames))
        self.assertEqual(frames[0].data, {"step": 2})
        self.assertEqual(frames[-1].event, PlatformStreamEvent.STREAM_END)

    def test_stream_retry_resets_old_execution_and_rebuilds_snapshot(self):
        source = self.create_success_message(text="source")
        use_attachment_handler(self, RealAttachmentHttpStreamRetryHandler())
        created = self.unwrap(
            self.session.post(
                self.api_url(f"/messages/{source['uid']}/attachments/"),
                json={"attachment_type": AttachmentType.AI_ANALYSIS, "input_data": {"text": "retry"}},
            )
        )
        self.assertTrue(http_stream_started.wait(settings.CELERY_TEST_TASK_TIMEOUT))
        snapshot = self.unwrap(self.session.get(self.api_url(f"/attachments/{created['uid']}/stream/snapshot/")))
        old_execution_id = snapshot["execution_id"]
        old_frames, done, thread, errors = self.start_sse_request(
            attachment_uid=created["uid"],
            execution_id=old_execution_id,
            terminal_event=PlatformStreamEvent.STREAM_RESET,
        )
        http_stream_release.set()
        self.assertTrue(done.wait(settings.CELERY_TEST_TASK_TIMEOUT))
        thread.join(timeout=1)
        self.assertFalse(errors, errors)
        self.assertEqual(old_frames[-1].event, PlatformStreamEvent.STREAM_RESET)

        detail = self.wait_status(f"/attachments/{created['uid']}/", ExecutionStatus.SUCCESS)
        new_snapshot = self.unwrap(self.session.get(self.api_url(f"/attachments/{created['uid']}/stream/snapshot/")))
        self.assertNotEqual(new_snapshot["execution_id"], old_execution_id)
        self.assertEqual(detail["output_data"], {"content": "http-stream:success"})
        self.assertTrue(any(event.get("data") == {"step": 2} for event in new_snapshot["events"]))
        self.assertEqual(new_snapshot["events"][-1]["event"], PlatformStreamEvent.STREAM_END)

"""程序统计公开创建、范围固化和用户可见生命周期。"""

import json
from copy import deepcopy
from unittest import mock

from django.urls import resolve
from rest_framework.test import APIRequestFactory, force_authenticate

from core.exceptions import PermissionException
from services.web.ai_assistant.constants import (
    AttachmentType,
    ExecutionStatus,
    MessageType,
)
from services.web.ai_assistant.exceptions import (
    AttachmentNotFound,
    AttachmentSnapshotValidationError,
    InvalidAttachmentSource,
    InvalidAttachmentState,
)
from services.web.ai_assistant.handlers.audit_statistics import (
    AIStatisticsAttachmentHandler,
    FieldStatisticsAttachmentHandler,
)
from services.web.ai_assistant.models import Attachment, Message
from services.web.ai_assistant.resources.attachment import (
    CreateAttachment,
    GetAttachment,
    ListAttachments,
    RetryAttachment,
)
from services.web.ai_assistant.schemas.audit_statistics import (
    AIStatisticsAttachmentContext,
    FieldStatisticsAttachmentInput,
)
from services.web.ai_assistant.services.conversation import ConversationService
from services.web.ai_assistant.tasks.audit_statistics import (
    build_statistics_agent_input,
)
from services.web.common.scope_permission import ScopePermission
from tests.test_ai_assistant.base import AIAssistantPlatformTestCase
from tests.test_ai_assistant.factories import create_conversation
from tests.test_ai_assistant.handlers import use_attachment_handler


class FieldStatisticsTestMixin:
    """程序统计测试共用的真实来源工厂与受控 Broker 边界。"""

    def setUp(self):
        super().setUp()
        self.handler = use_attachment_handler(self, FieldStatisticsAttachmentHandler())
        self.source = self.create_log_search_message()
        self.enterContext(
            mock.patch("services.web.ai_assistant.resources.attachment.get_request_username", return_value=self.user)
        )
        self.enterContext(mock.patch.object(self.handler.async_task, "apply_async"))

    def create(self, **input_overrides):
        """公开资源创建附件并执行提交后的投递回调。"""
        with self.captureOnCommitCallbacks(execute=True):
            return CreateAttachment().request(
                message_uid=str(self.source.uid),
                attachment_type=AttachmentType.FIELD_STATISTICS,
                input_data={"field": {"raw_name": "extend_data", "keys": ["method"]}, **input_overrides},
            )


class FieldStatisticsHandlerTest(FieldStatisticsTestMixin, AIAssistantPlatformTestCase):
    """真实 Resource/Service/数据库，只有 Broker 投递被替换。"""

    def test_unknown_custom_root_returns_http_field_error_without_creating_attachment(self):
        """自定义路径不允许任意日志列，拒绝时公开具体位置且不创建附件。"""
        self.enterContext(
            mock.patch("services.web.ai_assistant.permissions.get_request_username", return_value=self.user)
        )
        self.enterContext(mock.patch.object(ScopePermission, "get_scene_ids", return_value=[1]))
        path = f"/api/v1/ai_assistant/messages/{self.source.uid}/attachments/"
        request = APIRequestFactory().post(
            path,
            {"attachment_type": "FIELD_STATISTICS", "input_data": {"field": {"raw_name": "event_data", "keys": ["a"]}}},
            format="json",
        )
        force_authenticate(request, user=mock.Mock(username=self.user, is_authenticated=True))
        route = resolve(path)
        response = route.func(request, **route.kwargs)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "2908017")
        self.assertEqual(response.data["data"]["field_name"], "input_data")
        self.assertEqual(response.data["data"]["errors"][0]["loc"], ["field", "raw_name"])
        self.assertIn("日志根字段", response.data["data"]["errors"][0]["msg"])
        self.assertFalse(Attachment.objects.filter(source_message=self.source).exists())
        self.handler.async_task.apply_async.assert_not_called()

    def test_custom_nested_path_not_present_in_source_catalog_can_create_statistics(self):
        """用户直接提交三层对象路径，不要求来源字段目录中已发现该路径。"""
        created = self.create(field={"raw_name": "extend_data", "keys": ["custom", "branch", "leaf"]})
        attachment = Attachment.objects.get(uid=created["uid"])
        self.assertEqual(created["status"], "PROCESSING")
        self.assertEqual(
            attachment.context_data["field"],
            {"raw_name": "extend_data", "keys": ["custom", "branch", "leaf"], "display_name": "leaf"},
        )
        self.assertEqual(attachment.context_data["search_condition"], self.source.input_data["condition"])

    def test_creation_snapshots_full_source_and_disables_report_capabilities(self):
        created = self.create(field={"raw_name": "extend_data", "keys": ["method"], "field_type": "double"})
        attachment = Attachment.objects.get(uid=created["uid"])
        self.assertEqual(created["status"], "PROCESSING")
        self.assertFalse(created["is_stream"])
        self.assertFalse(created["supports_feedback"])
        self.assertEqual(created["export_formats"], [])
        self.assertFalse(self.handler.supports_output_edit())
        self.assertEqual(attachment.context_data["search_condition"], self.source.input_data["condition"])
        self.assertEqual(attachment.context_data["namespace"], "bkaudit")
        self.assertEqual(attachment.context_data["username"], self.user)
        self.assertEqual(
            attachment.context_data["field"], {"raw_name": "extend_data", "keys": ["method"], "display_name": "method"}
        )
        self.assertNotIn("samples", attachment.context_data)
        self.assertNotIn("execution_id", attachment.context_data)
        self.assertEqual(
            ListAttachments().request(
                scope_type=self.conversation.scope_type,
                scope_id=self.conversation.scope_id,
                attachment_type="AI_ANALYSIS",
            ),
            [],
        )
        self.assertEqual(GetAttachment().request(attachment_uid=created["uid"])["output_data"], None)

    def test_statistics_http_creation_and_scope_filtered_lists(self):
        """两种统计附件通过 HTTP 创建，列表归属由来源会话决定。"""
        ai_handler = use_attachment_handler(self, AIStatisticsAttachmentHandler())
        self.enterContext(mock.patch.object(ai_handler.async_task, "apply_async"))
        self.enterContext(
            mock.patch("services.web.ai_assistant.permissions.get_request_username", return_value=self.user)
        )
        self.enterContext(mock.patch.object(ScopePermission, "get_scene_ids", return_value=[1]))
        path = "/api/v1/ai_assistant/attachments/"
        create_path = f"/api/v1/ai_assistant/messages/{self.source.uid}/attachments/"
        factory = APIRequestFactory()
        user = mock.Mock(username=self.user, is_authenticated=True)
        created_uids = []
        for kind, data in (
            (AttachmentType.FIELD_STATISTICS, {"field": {"raw_name": "extend_data", "keys": ["method"]}}),
            (AttachmentType.AI_STATISTICS, {"instruction": "比较另一系统的操作趋势"}),
        ):
            with self.subTest(kind=kind), self.captureOnCommitCallbacks(execute=True):
                request = factory.post(
                    create_path,
                    {"attachment_type": kind, "input_data": data},
                    format="json",
                )
                force_authenticate(request, user=user)
                route = resolve(create_path)
                response = route.func(request, **route.kwargs)
                self.assertEqual(response.status_code, 200, response.data)
                created_uids.append(response.data["uid"])
        hidden_conversation = create_conversation(scope_id="2", created_by=self.user)
        hidden_source = Message.objects.create(
            conversation=hidden_conversation,
            message_type=MessageType.LOG_SEARCH,
            status=ExecutionStatus.SUCCESS,
            created_by=self.user,
        )
        Attachment.objects.create(
            source_message=hidden_source, attachment_type=AttachmentType.FIELD_STATISTICS, created_by=self.user
        )
        for scope in ({"scope_type": "scene", "scope_id": "1"}, {"scope_type": "cross_scene"}):
            with self.subTest(scope=scope):
                request = factory.get(path, scope)
                force_authenticate(request, user=user)
                response = resolve(path).func(request)
                self.assertEqual(response.status_code, 200, response.data)
                self.assertEqual({row["uid"] for row in response.data}, set(created_uids))
                self.assertEqual({(row["scope_type"], row["scope_id"]) for row in response.data}, {("scene", "1")})

    def test_creation_rejects_extra_range_and_identity(self):
        for extra in ({"condition": {}}, {"namespace": "other"}, {"username": "other"}, {"start_time": "bad"}):
            with self.subTest(extra=extra), self.assertRaises(AttachmentSnapshotValidationError):
                self.create(**extra)
        self.assertFalse(Attachment.objects.exists())

    def test_source_type_status_owner_and_snapshot_conflicts_rejected(self):
        original = deepcopy(self.source.context_data)
        for attr, value in (
            ("status", "FAILED"),
            ("message_type", "SYSTEM_SELECTION"),
            ("created_by", "other"),
            ("context_data", {**original, "username": "other"}),
            ("context_data", {**original, "system_id": "other"}),
        ):
            previous = getattr(self.source, attr)
            setattr(self.source, attr, value)
            with self.subTest(attr=attr), self.assertRaises(InvalidAttachmentSource):
                self.handler.prepare(
                    user=self.user,
                    source_message=self.source,
                    input_data=FieldStatisticsAttachmentInput(field={"raw_name": "username"}),
                )
            setattr(self.source, attr, previous)
        output = deepcopy(self.source.output_data)
        output["query_summary"]["scope_id"] = "other"
        self.source.output_data = output
        with self.assertRaises(AttachmentSnapshotValidationError):
            self.handler.prepare(
                user=self.user,
                source_message=self.source,
                input_data=FieldStatisticsAttachmentInput(field={"raw_name": "username"}),
            )

    def test_failed_generation_can_retry_original_or_create_new_attachment(self):
        """手动重试保留原附件身份，重新创建仍产生独立历史。"""
        first = self.create()
        Attachment.objects.filter(uid=first["uid"]).update(status=ExecutionStatus.FAILED)
        with self.captureOnCommitCallbacks(execute=True):
            retried = RetryAttachment().request(attachment_uid=first["uid"])
        self.assertEqual(retried["uid"], first["uid"])
        self.assertEqual(retried["status"], "PROCESSING")
        second = self.create()
        self.assertNotEqual(first["uid"], second["uid"])

    def test_edit_retry_materializes_complete_input_without_changing_source_or_siblings(self):
        first, sibling = self.create(), self.create()
        original = deepcopy(self.source.input_data)
        override = {**original["condition"], "conditions": [], "scope_id": "another-authorized-system"}
        Attachment.objects.filter(uid=first["uid"]).update(status="SUCCESS", output_data=None)
        with self.captureOnCommitCallbacks(execute=False):
            changed = RetryAttachment().request(
                attachment_uid=first["uid"],
                input_data={
                    "field": {"raw_name": "result_code"},
                    "interval": "MONTH",
                    "condition": override,
                },
            )
        attachment = Attachment.objects.get(uid=first["uid"])
        self.assertEqual(changed["input_data"]["condition"], override)
        self.assertEqual(attachment.context_data["search_condition"], override)
        self.assertEqual(attachment.context_data["field"]["raw_name"], "result_code")
        self.assertEqual(attachment.context_data["interval"], "MONTH")
        self.assertEqual(attachment.title, "操作结果统计")
        self.source.refresh_from_db()
        self.assertEqual(self.source.input_data, original)
        self.assertEqual(Attachment.objects.get(uid=sibling["uid"]).input_data, sibling["input_data"])
        Attachment.objects.filter(uid=first["uid"]).update(status="FAILED", title="自定义标题")
        with self.captureOnCommitCallbacks(execute=False):
            changed = RetryAttachment().request(
                attachment_uid=first["uid"], input_data={"field": {"raw_name": "username"}}
            )
        self.assertEqual(changed["title"], "自定义标题")
        self.assertEqual(changed["input_data"]["interval"], "AUTO")
        self.assertEqual(changed["input_data"]["condition"], original["condition"])
        with self.assertRaises(InvalidAttachmentState):
            RetryAttachment().request(attachment_uid=first["uid"], input_data={"field": {"raw_name": "username"}})

    def test_edit_retry_preserves_custom_title_saved_while_preparing_input(self):
        for custom_title in ("并发保存的自定义标题", "METHOD统计"):
            with self.subTest(title=custom_title):
                created = self.create()
                Attachment.objects.filter(uid=created["uid"]).update(status="FAILED")
                original_prepare = self.handler.prepare

                def prepare_and_rename(**kwargs):
                    """模拟输入准备期间另一个标题编辑请求成功落库。"""
                    preparation = original_prepare(**kwargs)
                    Attachment.objects.filter(uid=created["uid"]).update(title=custom_title)
                    return preparation

                with mock.patch.object(self.handler, "prepare", side_effect=prepare_and_rename):
                    with self.captureOnCommitCallbacks(execute=False):
                        changed = RetryAttachment().request(
                            attachment_uid=created["uid"], input_data={"field": {"raw_name": "result_code"}}
                        )
                self.assertEqual(changed["title"], custom_title)
                self.assertEqual(changed["input_data"]["field"]["raw_name"], "result_code")
                self.assertEqual(Attachment.objects.get(uid=created["uid"]).title, custom_title)

    def test_partial_retry_condition_is_rejected_without_replacing_saved_filters(self):
        created = self.create()
        Attachment.objects.filter(uid=created["uid"]).update(status="SUCCESS")
        before = Attachment.objects.get(uid=created["uid"])
        partial = {key: value for key, value in before.input_data["condition"].items() if key != "conditions"}
        with self.assertRaises(AttachmentSnapshotValidationError):
            RetryAttachment().request(
                attachment_uid=created["uid"], input_data={"field": {"raw_name": "username"}, "condition": partial}
            )
        after = Attachment.objects.get(uid=created["uid"])
        self.assertEqual(
            (after.input_data, after.context_data, after.output_data, after.status, after.task_id),
            (before.input_data, before.context_data, before.output_data, before.status, before.task_id),
        )

    def test_new_input_permission_failure_preserves_old_input_and_result(self):
        created = self.create()
        Attachment.objects.filter(uid=created["uid"]).update(status="FAILED")
        before = Attachment.objects.get(uid=created["uid"])
        with mock.patch(
            "services.web.ai_assistant.handlers.log_search_source.LogQueryContextService.build",
            side_effect=PermissionException(action_name="view_system", permission={}, apply_url=""),
        ):
            with self.assertRaises(PermissionException):
                RetryAttachment().request(
                    attachment_uid=created["uid"], input_data={"field": {"raw_name": "result_code"}}
                )
        after = Attachment.objects.get(uid=created["uid"])
        self.assertEqual(
            (after.input_data, after.context_data, after.status, after.task_id),
            (before.input_data, before.context_data, before.status, before.task_id),
        )

    def test_clear_and_delete_remove_visibility_and_reject_source(self):
        for action in ("clear", "delete"):
            with self.subTest(action=action):
                if action == "delete":
                    self.conversation = create_conversation(created_by=self.user, updated_by=self.user)
                    self.source = self.create_log_search_message()
                created = self.create()
                service = ConversationService(user=self.user)
                if action == "clear":
                    service.clear_conversations(
                        scope_type=self.conversation.scope_type, scope_id=self.conversation.scope_id
                    )
                else:
                    service.delete_conversation(conversation_uid=str(self.conversation.uid))
                with self.assertRaises(AttachmentNotFound):
                    GetAttachment().request(attachment_uid=created["uid"])
                with self.assertRaises(InvalidAttachmentSource):
                    self.create()


class AIStatisticsTestMixin:
    """AI 统计使用公开创建入口及独立生产注册恢复。"""

    def setUp(self):
        super().setUp()
        self.handler = use_attachment_handler(self, AIStatisticsAttachmentHandler())
        self.source = self.create_log_search_message()
        self.enterContext(
            mock.patch("services.web.ai_assistant.resources.attachment.get_request_username", return_value=self.user)
        )
        self.enterContext(mock.patch.object(self.handler.async_task, "apply_async"))

    def create(self, **input_overrides):
        """提交指令，保留真实 Resource 校验及来源快照。"""
        with self.captureOnCommitCallbacks(execute=True):
            return CreateAttachment().request(
                message_uid=str(self.source.uid),
                attachment_type=AttachmentType.AI_STATISTICS,
                input_data={"instruction": "比较另一系统最近一天的操作趋势", **input_overrides},
            )


class AIStatisticsHandlerTest(AIStatisticsTestMixin, AIAssistantPlatformTestCase):
    """确认统计能力独立，不因加入 AI 统计改变报告与程序统计。"""

    def test_creation_has_initial_scope_and_independent_capabilities(self):
        created = self.create()
        attachment = Attachment.objects.get(uid=created["uid"])
        self.assertEqual(created["status"], "PROCESSING")
        self.assertTrue(created["is_stream"])
        self.assertTrue(created["supports_feedback"])
        self.assertEqual(created["export_formats"], [])
        self.assertFalse(self.handler.supports_output_edit())
        self.assertEqual(attachment.context_data["initial_search_condition"], self.source.input_data["condition"])
        self.assertEqual(attachment.context_data["username"], self.user)
        self.assertEqual(attachment.context_data["namespace"], "bkaudit")
        self.assertNotIn("samples", attachment.context_data)
        self.assertEqual(
            ListAttachments().request(
                scope_type=self.conversation.scope_type,
                scope_id=self.conversation.scope_id,
                attachment_type="AI_ANALYSIS",
            ),
            [],
        )

    def test_edit_retry_uses_new_instruction_and_range_without_source_total(self):
        created = self.create()
        Attachment.objects.filter(uid=created["uid"]).update(status="FAILED")
        condition = {**self.source.input_data["condition"], "conditions": []}
        with self.captureOnCommitCallbacks(execute=False):
            changed = RetryAttachment().request(
                attachment_uid=created["uid"], input_data={"instruction": "新的统计要求", "condition": condition}
            )
        attachment = Attachment.objects.get(uid=created["uid"])
        self.assertEqual(changed["input_data"]["instruction"], "新的统计要求")
        self.assertEqual(attachment.context_data["instruction"], "新的统计要求")
        payload = json.loads(
            build_statistics_agent_input(AIStatisticsAttachmentContext.model_validate(attachment.context_data))
        )
        self.assertNotIn("query_summary", payload["context"])
        self.assertEqual(payload["context"]["initial_search_condition"], condition)

    def test_creation_rejects_overridden_identity_and_invalid_source(self):
        for extra in ({"username": "other"}, {"namespace": "other"}, {"condition": {}}):
            with self.subTest(extra=extra), self.assertRaises(AttachmentSnapshotValidationError):
                self.create(**extra)
        self.source.status = "FAILED"
        self.source.save(update_fields=["status"])
        with self.assertRaises(InvalidAttachmentSource):
            self.create()

    def test_manual_retry_keeps_attachment_but_rotates_task(self):
        created = self.create()
        attachment = Attachment.objects.get(uid=created["uid"])
        original_task_id = attachment.task_id
        Attachment.objects.filter(pk=attachment.pk).update(status=ExecutionStatus.FAILED)
        with self.captureOnCommitCallbacks(execute=True):
            retried = RetryAttachment().request(attachment_uid=created["uid"])
        attachment.refresh_from_db()
        self.assertEqual(retried["uid"], created["uid"])
        self.assertEqual(attachment.status, ExecutionStatus.PROCESSING)
        self.assertNotEqual(attachment.task_id, original_task_id)

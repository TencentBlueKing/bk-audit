"""程序统计公开创建、范围固化和用户可见生命周期。"""

from copy import deepcopy
from unittest import mock

from services.web.ai_assistant.constants import AttachmentType, ExecutionStatus
from services.web.ai_assistant.exceptions import (
    AttachmentNotFound,
    AttachmentSnapshotValidationError,
    InvalidAttachmentSource,
    InvalidAttachmentState,
)
from services.web.ai_assistant.handlers.audit_statistics import (
    FieldStatisticsAttachmentHandler,
)
from services.web.ai_assistant.models import Attachment, Conversation
from services.web.ai_assistant.resources.attachment import (
    CreateAttachment,
    GetAttachment,
    ListAttachments,
    RetryAttachment,
)
from services.web.ai_assistant.schemas.audit_statistics import (
    FieldStatisticsAttachmentInput,
)
from services.web.ai_assistant.services.conversation import ConversationService
from tests.test_ai_assistant.base import AIAssistantPlatformTestCase
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

    def test_creation_snapshots_full_source_and_disables_report_capabilities(self):
        created = self.create(field={"raw_name": "extend_data", "keys": ["method"], "field_type": "double"})
        attachment = Attachment.objects.get(uid=created["uid"])
        self.assertEqual(created["status"], "PROCESSING")
        self.assertFalse(created["is_stream"])
        self.assertFalse(created["supports_retry"])
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
        self.assertEqual(ListAttachments().request(attachment_type="AI_ANALYSIS"), [])
        self.assertEqual(GetAttachment().request(attachment_uid=created["uid"])["output_data"], None)

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

    def test_failed_generation_creates_new_attachment_and_cannot_retry(self):
        first = self.create()
        Attachment.objects.filter(uid=first["uid"]).update(status=ExecutionStatus.FAILED)
        with self.assertRaises(InvalidAttachmentState):
            RetryAttachment().request(attachment_uid=first["uid"])
        second = self.create()
        self.assertNotEqual(first["uid"], second["uid"])
        self.assertEqual(GetAttachment().request(attachment_uid=first["uid"])["status"], "FAILED")

    def test_clear_and_delete_remove_visibility_and_reject_source(self):
        for action in ("clear", "delete"):
            with self.subTest(action=action):
                if action == "delete":
                    self.conversation = Conversation.objects.create(created_by=self.user, updated_by=self.user)
                    self.source = self.create_log_search_message()
                created = self.create()
                service = ConversationService(user=self.user)
                if action == "clear":
                    service.clear_conversations()
                else:
                    service.delete_conversation(conversation_uid=str(self.conversation.uid))
                with self.assertRaises(AttachmentNotFound):
                    GetAttachment().request(attachment_uid=created["uid"])
                with self.assertRaises(InvalidAttachmentSource):
                    self.create()

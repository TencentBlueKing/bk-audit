"""附件 Admin 重试动作复用真实领域服务，只有 Celery 投递边界替换为测试替身。"""

from unittest import mock

from django.contrib import admin, messages
from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory, TransactionTestCase

from services.web.ai_assistant.admin import AttachmentAdmin
from services.web.ai_assistant.constants import (
    AttachmentType,
    ExecutionStatus,
    MessageType,
)
from services.web.ai_assistant.models import Attachment, Conversation, Message
from tests.test_ai_assistant.handlers import (
    EchoAttachmentAsyncHandler,
    use_attachment_handler,
)


class AttachmentAdminTest(TransactionTestCase):
    """管理员可按原用户身份重试失败附件，并获得准确反馈和操作日志。"""

    def setUp(self):
        """准备跨用户附件及 Admin 请求，使用真实提交回调验证投递结果。"""
        self.handler = use_attachment_handler(self, EchoAttachmentAsyncHandler())
        self.model_admin = AttachmentAdmin(Attachment, admin.site)
        self.request = RequestFactory().post("/admin/ai_assistant/attachment/")
        self.request.user = get_user_model().objects.create(username="retry-admin", is_staff=True, is_superuser=True)
        self.request.session = {}
        self.request._messages = FallbackStorage(self.request)
        conversation = Conversation.objects.create(created_by="alice", updated_by="alice")
        self.source = Message.objects.create(
            conversation=conversation,
            message_type=MessageType.LOG_SEARCH,
            status=ExecutionStatus.SUCCESS,
            created_by="alice",
            updated_by="alice",
        )

    def create_attachment(self, status=ExecutionStatus.FAILED):
        """创建原用户的附件，保留快照以验证重试没有重建输入。"""
        return Attachment.objects.create(
            source_message=self.source,
            attachment_type=AttachmentType.AI_ANALYSIS,
            status=status,
            task_id="old-task",
            input_data={"text": "hello"},
            context_data={"prefix": "alice"},
            error_code="OLD_ERROR",
            error_message="旧错误",
            created_by="alice",
            updated_by="alice",
        )

    def test_action_retries_failed_attachment_and_skips_other_states(self):
        """批量操作只重试失败附件，原快照/身份不变并记录实际管理员。"""
        failed = self.create_attachment()
        success = self.create_attachment(ExecutionStatus.SUCCESS)
        processing = self.create_attachment(ExecutionStatus.PROCESSING)
        with mock.patch.object(self.handler.async_task, "apply_async") as dispatch:
            self.model_admin.retry_attachments(self.request, Attachment.objects.all())
        failed.refresh_from_db()
        success.refresh_from_db()
        processing.refresh_from_db()
        self.assertEqual(failed.status, ExecutionStatus.PROCESSING)
        self.assertNotEqual(failed.task_id, "old-task")
        self.assertEqual(failed.input_data, {"text": "hello"})
        self.assertEqual(failed.context_data, {"prefix": "alice"})
        self.assertEqual(failed.created_by, "alice")
        self.assertEqual(failed.updated_by, "alice")
        self.assertEqual(failed.error_code, "")
        self.assertEqual(success.task_id, "old-task")
        self.assertEqual(processing.task_id, "old-task")
        dispatch.assert_called_once_with(
            kwargs={"attachment_id": failed.id, "task_id": failed.task_id}, task_id=failed.task_id
        )
        entry = LogEntry.objects.get(object_id=str(failed.pk))
        self.assertEqual(entry.user_id, self.request.user.pk)
        self.assertIn(failed.task_id, entry.change_message)
        notices = list(messages.get_messages(self.request))
        self.assertIn("已提交重试 1 个，未提交 2 个", str(notices[-1]))

    def test_broker_failure_is_reported_as_not_submitted(self):
        """投递失败后保留领域失败终态，Admin 不显示提交成功。"""
        attachment = self.create_attachment()
        with mock.patch.object(self.handler.async_task, "apply_async", side_effect=RuntimeError("broker unavailable")):
            self.model_admin.retry_attachments(self.request, Attachment.objects.all())
        attachment.refresh_from_db()
        self.assertEqual(attachment.status, ExecutionStatus.FAILED)
        notices = list(messages.get_messages(self.request))
        self.assertIn("已提交重试 0 个，未提交 1 个", str(notices[-1]))
        self.assertEqual(notices[-1].level, messages.WARNING)

    def test_action_requires_change_permission(self):
        """只读管理员不能看到重试动作。"""
        self.assertIn("retry_attachments", self.model_admin.get_actions(self.request))
        with mock.patch.object(self.request.user, "has_perm", return_value=False):
            self.assertNotIn("retry_attachments", self.model_admin.get_actions(self.request))

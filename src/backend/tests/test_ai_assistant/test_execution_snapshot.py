from django.test import TestCase
from django.utils import timezone

from services.web.ai_assistant.constants import (
    AttachmentType,
    ExecutionStatus,
    MessageType,
)
from services.web.ai_assistant.models import Attachment, Conversation, Message


class ExecutionSnapshotModelTest(TestCase):
    """验证消息和附件共享的执行状态 CAS 原语。"""

    def setUp(self):
        self.conversation = Conversation.objects.create(created_by="alice")
        self.message = Message.objects.create(
            conversation=self.conversation,
            message_type=MessageType.LOG_SEARCH,
            status=ExecutionStatus.PROCESSING,
            task_id="task-current",
            input_data={"query": "status:failed"},
            context_data={"system_id": "system-1"},
            created_by="alice",
        )
        self.attachment = Attachment.objects.create(
            source_message=self.message,
            attachment_type=AttachmentType.AI_ANALYSIS,
            status=ExecutionStatus.PROCESSING,
            task_id="task-current",
            input_data={"prompt": "分析失败日志"},
            context_data={"sample_size": 100},
            created_by="alice",
        )

    def test_finish_processing_only_updates_matching_processing_task_once(self):
        updated_at = timezone.now()

        updated = Message.finish_processing(
            instance_id=self.message.id,
            task_id="task-current",
            status=ExecutionStatus.SUCCESS,
            output_data={"content": "done"},
            error_code="",
            error_message="",
            extra_updates={"updated_by": "worker", "updated_at": updated_at},
        )

        self.assertTrue(updated)
        self.message.refresh_from_db()
        self.assertEqual(self.message.status, ExecutionStatus.SUCCESS)
        self.assertEqual(self.message.output_data, {"content": "done"})
        self.assertEqual(self.message.updated_by, "worker")
        self.assertEqual(self.message.updated_at, updated_at)
        self.assertFalse(
            Message.finish_processing(
                instance_id=self.message.id,
                task_id="task-current",
                status=ExecutionStatus.FAILED,
                output_data=None,
                error_code="FAILED",
                error_message="执行失败",
            )
        )

    def test_finish_processing_rejects_stale_task_and_invalid_terminal_status(self):
        self.assertFalse(
            Message.finish_processing(
                instance_id=self.message.id,
                task_id="task-stale",
                status=ExecutionStatus.SUCCESS,
                output_data={"content": "stale"},
                error_code="",
                error_message="",
            )
        )
        for status in (ExecutionStatus.PROCESSING, "UNKNOWN"):
            with self.subTest(status=status), self.assertRaises(ValueError):
                Message.finish_processing(
                    instance_id=self.message.id,
                    task_id="task-current",
                    status=status,
                    output_data=None,
                    error_code="",
                    error_message="",
                )

        self.message.refresh_from_db()
        self.assertEqual(self.message.status, ExecutionStatus.PROCESSING)
        self.assertEqual(self.message.task_id, "task-current")
        self.assertIsNone(self.message.output_data)

    def test_attachment_finish_processing_supports_domain_extra_updates(self):
        content_updated_at = timezone.now()

        updated = Attachment.finish_processing(
            instance_id=self.attachment.id,
            task_id="task-current",
            status=ExecutionStatus.FAILED,
            output_data=None,
            error_code="EXECUTION_FAILED",
            error_message="执行失败",
            extra_updates={"content_updated_at": content_updated_at},
        )

        self.assertTrue(updated)
        self.attachment.refresh_from_db()
        self.assertEqual(self.attachment.status, ExecutionStatus.FAILED)
        self.assertEqual(self.attachment.error_code, "EXECUTION_FAILED")
        self.assertEqual(self.attachment.error_message, "执行失败")
        self.assertEqual(self.attachment.content_updated_at, content_updated_at)

    def test_restart_failed_reuses_snapshot_and_clears_execution_result(self):
        for instance in (self.message, self.attachment):
            instance.status = ExecutionStatus.FAILED
            instance.task_id = "task-old"
            instance.output_data = {"content": "old"}
            instance.error_code = "OLD_ERROR"
            instance.error_message = "旧错误"
            instance.save(update_fields=["status", "task_id", "output_data", "error_code", "error_message"])

        content_updated_at = timezone.now()
        self.assertTrue(
            Message.restart_failed(
                instance_id=self.message.id,
                old_task_id="task-old",
                new_task_id="task-new",
                extra_updates={"updated_by": "alice"},
            )
        )
        self.assertTrue(
            Attachment.restart_failed(
                instance_id=self.attachment.id,
                old_task_id="task-old",
                new_task_id="task-new",
                extra_updates={
                    "stream_config": {},
                    "stream_archive": [],
                    "content_updated_at": content_updated_at,
                },
            )
        )

        self.message.refresh_from_db()
        self.attachment.refresh_from_db()
        for instance in (self.message, self.attachment):
            with self.subTest(model=type(instance).__name__):
                self.assertEqual(instance.status, ExecutionStatus.PROCESSING)
                self.assertEqual(instance.task_id, "task-new")
                self.assertIsNone(instance.output_data)
                self.assertEqual(instance.error_code, "")
                self.assertEqual(instance.error_message, "")
        self.assertEqual(self.message.input_data, {"query": "status:failed"})
        self.assertEqual(self.message.context_data, {"system_id": "system-1"})
        self.assertEqual(self.attachment.input_data, {"prompt": "分析失败日志"})
        self.assertEqual(self.attachment.context_data, {"sample_size": 100})
        self.assertEqual(self.attachment.content_updated_at, content_updated_at)

    def test_restart_failed_rejects_stale_task_or_non_failed_status(self):
        self.attachment.status = ExecutionStatus.FAILED
        self.attachment.task_id = "task-old"
        self.attachment.save(update_fields=["status", "task_id"])

        self.assertFalse(
            Attachment.restart_failed(
                instance_id=self.attachment.id,
                old_task_id="task-stale",
                new_task_id="task-new",
            )
        )
        self.assertFalse(
            Message.restart_failed(
                instance_id=self.message.id,
                old_task_id="task-current",
                new_task_id="task-new",
            )
        )
        self.attachment.refresh_from_db()
        self.message.refresh_from_db()
        self.assertEqual(self.attachment.task_id, "task-old")
        self.assertEqual(self.message.task_id, "task-current")

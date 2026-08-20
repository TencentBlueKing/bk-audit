from django.db import connection
from django.db.models.signals import pre_save
from django.test.utils import CaptureQueriesContext

from services.web.ai_assistant.constants import (
    AttachmentType,
    ExecutionStatus,
    FeedbackSourceType,
    FeedbackType,
    MessageType,
)
from services.web.ai_assistant.exceptions import (
    FeedbackNotSupported,
    FeedbackSourceNotFound,
    InvalidFeedbackSourceState,
)
from services.web.ai_assistant.handlers import (
    attachment_handler_registry,
    message_handler_registry,
)
from services.web.ai_assistant.models import Attachment, Conversation, Feedback, Message
from services.web.ai_assistant.services.feedback import FeedbackService
from tests.base import TestCase
from tests.test_ai_assistant.handlers import (
    EchoAttachmentSyncHandler,
    EchoSyncHandler,
    FeedbackAttachmentEchoHandler,
    FeedbackEchoSyncHandler,
)


class FeedbackServiceTest(TestCase):
    """验证反馈领域的用户边界、状态限制与批量绑定行为。"""

    def setUp(self):
        self.user = "alice"
        self.service = FeedbackService(user=self.user)
        self.conversation = Conversation.objects.create(created_by=self.user, updated_by=self.user)
        message_handler_registry.register(FeedbackEchoSyncHandler())
        attachment_handler_registry.register(FeedbackAttachmentEchoHandler())
        self.message = self.create_message()
        self.attachment = self.create_attachment()

    def tearDown(self):
        message_handler_registry.unregister(MessageType.SYSTEM_SELECTION)
        attachment_handler_registry.unregister(AttachmentType.FIELD_STATISTICS)

    def create_message(self, *, conversation=None, user=None, status=ExecutionStatus.SUCCESS):
        owner = user or self.user
        return Message.objects.create(
            conversation=conversation or self.conversation,
            message_type=MessageType.SYSTEM_SELECTION,
            status=status,
            input_data={"text": "feedback"},
            context_data={"prefix": "feedback"},
            output_data={"content": "feedback"} if status == ExecutionStatus.SUCCESS else None,
            created_by=owner,
            updated_by=owner,
        )

    def create_attachment(self, *, message=None, user=None, status=ExecutionStatus.SUCCESS):
        owner = user or self.user
        return Attachment.objects.create(
            source_message=message or self.message,
            attachment_type=AttachmentType.FIELD_STATISTICS,
            status=status,
            input_data={"text": "feedback"},
            context_data={"prefix": "feedback"},
            output_data={"content": "feedback"} if status == ExecutionStatus.SUCCESS else None,
            created_by=owner,
            updated_by=owner,
        )

    def test_upsert_creates_and_overwrites_same_user_source(self):
        created = self.service.upsert(
            source_type=FeedbackSourceType.MESSAGE,
            source_uid=str(self.message.uid),
            feedback_type=FeedbackType.LIKE,
            comment="有帮助",
        )
        overwritten = self.service.upsert(
            source_type=FeedbackSourceType.MESSAGE,
            source_uid=str(self.message.uid),
            feedback_type=FeedbackType.DISLIKE,
            comment="不够准确",
        )

        feedback = Feedback.objects.get()
        self.assertEqual(Feedback.objects.count(), 1)
        self.assertEqual(created.uid, overwritten.uid)
        self.assertEqual(feedback.uid, created.uid)
        self.assertEqual(feedback.feedback_type, FeedbackType.DISLIKE)
        self.assertEqual(feedback.comment, "不够准确")
        self.assertEqual(feedback.updated_by, self.user)
        self.assertEqual(overwritten.source_uid, self.message.uid)

    def test_upsert_keeps_different_users_and_source_types_isolated(self):
        self.service.upsert(
            source_type=FeedbackSourceType.MESSAGE,
            source_uid=str(self.message.uid),
            feedback_type=FeedbackType.LIKE,
        )
        Feedback.objects.create(
            source_type=FeedbackSourceType.MESSAGE,
            source_id=self.message.id,
            feedback_type=FeedbackType.DISLIKE,
            created_by="bob",
            updated_by="bob",
        )
        self.service.upsert(
            source_type=FeedbackSourceType.ATTACHMENT,
            source_uid=str(self.attachment.uid),
            feedback_type=FeedbackType.DISLIKE,
        )

        self.assertEqual(Feedback.objects.count(), 3)
        self.assertEqual(
            set(Feedback.objects.values_list("created_by", "source_type")),
            {
                ("alice", FeedbackSourceType.MESSAGE),
                ("alice", FeedbackSourceType.ATTACHMENT),
                ("bob", FeedbackSourceType.MESSAGE),
            },
        )

    def test_upsert_rejects_missing_foreign_and_soft_deleted_source(self):
        foreign_conversation = Conversation.objects.create(created_by="bob", updated_by="bob")
        foreign_message = self.create_message(conversation=foreign_conversation, user="bob")
        deleted_conversation = Conversation.objects.create(created_by=self.user, updated_by=self.user, is_deleted=True)
        deleted_message = self.create_message(conversation=deleted_conversation)

        for source_uid in ("not-a-uuid", str(foreign_message.uid), str(deleted_message.uid)):
            with self.subTest(source_uid=source_uid), self.assertRaises(FeedbackSourceNotFound):
                self.service.upsert(
                    source_type=FeedbackSourceType.MESSAGE,
                    source_uid=source_uid,
                    feedback_type=FeedbackType.LIKE,
                )

    def test_upsert_rejects_processing_failed_and_unsupported_source(self):
        for status in (ExecutionStatus.PROCESSING, ExecutionStatus.FAILED):
            message = self.create_message(status=status)
            with self.subTest(status=status), self.assertRaises(InvalidFeedbackSourceState):
                self.service.upsert(
                    source_type=FeedbackSourceType.MESSAGE,
                    source_uid=str(message.uid),
                    feedback_type=FeedbackType.LIKE,
                )

        message_handler_registry.unregister(MessageType.SYSTEM_SELECTION)
        message_handler_registry.register(EchoSyncHandler())
        with self.assertRaises(FeedbackNotSupported):
            self.service.upsert(
                source_type=FeedbackSourceType.MESSAGE,
                source_uid=str(self.message.uid),
                feedback_type=FeedbackType.LIKE,
            )

    def test_attachment_upsert_rejects_foreign_deleted_invalid_state_and_unsupported_source(self):
        foreign_conversation = Conversation.objects.create(created_by="bob", updated_by="bob")
        foreign_message = self.create_message(conversation=foreign_conversation, user="bob")
        foreign_attachment = self.create_attachment(message=foreign_message, user="bob")
        deleted_conversation = Conversation.objects.create(created_by=self.user, updated_by=self.user, is_deleted=True)
        deleted_message = self.create_message(conversation=deleted_conversation)
        deleted_attachment = self.create_attachment(message=deleted_message)

        for attachment in (foreign_attachment, deleted_attachment):
            with self.subTest(attachment_uid=attachment.uid), self.assertRaises(FeedbackSourceNotFound):
                self.service.upsert(
                    source_type=FeedbackSourceType.ATTACHMENT,
                    source_uid=str(attachment.uid),
                    feedback_type=FeedbackType.LIKE,
                )

        for status in (ExecutionStatus.PROCESSING, ExecutionStatus.FAILED):
            attachment = self.create_attachment(status=status)
            with self.subTest(status=status), self.assertRaises(InvalidFeedbackSourceState):
                self.service.upsert(
                    source_type=FeedbackSourceType.ATTACHMENT,
                    source_uid=str(attachment.uid),
                    feedback_type=FeedbackType.LIKE,
                )

        attachment_handler_registry.unregister(AttachmentType.FIELD_STATISTICS)
        attachment_handler_registry.register(EchoAttachmentSyncHandler())
        with self.assertRaises(FeedbackNotSupported):
            self.service.upsert(
                source_type=FeedbackSourceType.ATTACHMENT,
                source_uid=str(self.attachment.uid),
                feedback_type=FeedbackType.LIKE,
            )

    def test_resolve_sources_only_loads_feedback_decision_fields(self):
        large_snapshot_fields = {"input_data", "context_data", "output_data"}
        expected_deferred_fields = {
            FeedbackSourceType.MESSAGE: large_snapshot_fields,
            FeedbackSourceType.ATTACHMENT: large_snapshot_fields | {"stream_config", "stream_archive"},
        }

        for source_type, source_uid in (
            (FeedbackSourceType.MESSAGE, self.message.uid),
            (FeedbackSourceType.ATTACHMENT, self.attachment.uid),
        ):
            with self.subTest(source_type=source_type), CaptureQueriesContext(connection) as queries:
                source = self.service._resolve_source(source_type=source_type, source_uid=str(source_uid))

            self.assertEqual(len(queries), 1)
            self.assertTrue(expected_deferred_fields[source_type].issubset(source.get_deferred_fields()))

    def test_upsert_existing_source_inserts_then_updates_without_for_update(self):
        feedback = Feedback.objects.create(
            source_type=FeedbackSourceType.MESSAGE,
            source_id=self.message.id,
            feedback_type=FeedbackType.LIKE,
            created_by=self.user,
            updated_by=self.user,
        )
        insert_attempts = []

        def record_insert_attempt(sender, instance, **kwargs):
            insert_attempts.append(instance.pk)

        pre_save.connect(record_insert_attempt, sender=Feedback)
        try:
            with CaptureQueriesContext(connection) as queries:
                result = self.service.upsert(
                    source_type=FeedbackSourceType.MESSAGE,
                    source_uid=str(self.message.uid),
                    feedback_type=FeedbackType.DISLIKE,
                    comment="最新反馈",
                )
        finally:
            pre_save.disconnect(record_insert_attempt, sender=Feedback)

        feedback_queries = [
            query["sql"] for query in queries.captured_queries if "ai_assistant_feedback" in query["sql"].lower()
        ]
        # MySQL 驱动不会把失败的 INSERT 写入 connection.queries，使用 pre_save 观察插入尝试。
        self.assertEqual(insert_attempts, [None])
        self.assertTrue(any(query.lstrip().upper().startswith("UPDATE") for query in feedback_queries))
        self.assertFalse(any("FOR UPDATE" in query.upper() for query in feedback_queries))
        self.assertEqual(result.uid, feedback.uid)
        feedback.refresh_from_db()
        self.assertEqual(feedback.feedback_type, FeedbackType.DISLIKE)
        self.assertEqual(feedback.comment, "最新反馈")

    def test_delete_only_removes_current_users_feedback(self):
        current = self.service.upsert(
            source_type=FeedbackSourceType.MESSAGE,
            source_uid=str(self.message.uid),
            feedback_type=FeedbackType.LIKE,
        )
        foreign = Feedback.objects.create(
            source_type=FeedbackSourceType.MESSAGE,
            source_id=self.message.id,
            feedback_type=FeedbackType.DISLIKE,
            created_by="bob",
            updated_by="bob",
        )

        self.service.delete(feedback_uid=str(current.uid))
        self.assertFalse(Feedback.objects.filter(uid=current.uid).exists())
        self.assertTrue(Feedback.objects.filter(uid=foreign.uid).exists())
        with self.assertRaises(FeedbackSourceNotFound):
            self.service.delete(feedback_uid=str(foreign.uid))

    def test_bind_current_feedback_uses_one_query_for_many_sources(self):
        messages = [self.message] + [self.create_message() for _ in range(19)]
        self.service.upsert(
            source_type=FeedbackSourceType.MESSAGE,
            source_uid=str(messages[0].uid),
            feedback_type=FeedbackType.LIKE,
        )

        with CaptureQueriesContext(connection) as queries:
            self.service.bind_current_feedback(sources=messages, source_type=FeedbackSourceType.MESSAGE)

        feedback_selects = [
            query["sql"]
            for query in queries.captured_queries
            if "ai_assistant_feedback" in query["sql"].lower() and query["sql"].lstrip().upper().startswith("SELECT")
        ]
        self.assertEqual(len(feedback_selects), 1)
        self.assertEqual(messages[0]._current_feedback.source_uid, messages[0].uid)
        self.assertIsNone(messages[-1]._current_feedback)

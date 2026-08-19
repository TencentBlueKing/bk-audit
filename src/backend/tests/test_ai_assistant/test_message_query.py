from uuid import uuid4

from services.web.ai_assistant.constants import (
    AttachmentType,
    ExecutionStatus,
    MessageHistoryDirection,
    MessageType,
)
from services.web.ai_assistant.exceptions import (
    ConversationNotFound,
    InvalidMessageAnchor,
    MessageNotFound,
)
from services.web.ai_assistant.models import Attachment, Conversation, Message
from services.web.ai_assistant.services import MessageService
from tests.base import TestCase


class MessageQueryTest(TestCase):
    def setUp(self):
        self.user = "alice"
        self.conversation = Conversation.objects.create(created_by=self.user, updated_by=self.user)
        self.service = MessageService(user=self.user)

    def create_message(
        self,
        index: int,
        *,
        conversation: Conversation | None = None,
        user: str | None = None,
    ) -> Message:
        owner = user or self.user
        return Message.objects.create(
            conversation=conversation or self.conversation,
            message_type=MessageType.SYSTEM_SELECTION,
            status=ExecutionStatus.SUCCESS,
            input_data={"text": f"input-{index}"},
            context_data={"prefix": "system"},
            output_data={"content": f"output-{index}"},
            created_by=owner,
            updated_by=owner,
        )

    def test_without_anchor_returns_latest_messages_in_ascending_order(self):
        messages = [self.create_message(index) for index in range(25)]

        window = self.service.list(conversation_uid=str(self.conversation.uid), limit=20)

        self.assertEqual([message.id for message in window.results], [message.id for message in messages[-20:]])
        self.assertEqual(window.first_uid, str(messages[-20].uid))
        self.assertEqual(window.last_uid, str(messages[-1].uid))
        self.assertTrue(window.has_before)
        self.assertFalse(window.has_after)
        self.assertTrue(window.include_content)

    def test_service_caps_history_window_at_platform_maximum(self):
        [self.create_message(index) for index in range(105)]

        window = self.service.list(
            conversation_uid=str(self.conversation.uid),
            limit=1000,
        )

        self.assertEqual(len(window.results), 100)
        self.assertTrue(window.has_before)

    def test_before_and_after_use_anchor_but_return_ascending_results(self):
        messages = [self.create_message(index) for index in range(8)]

        before = self.service.list(
            conversation_uid=str(self.conversation.uid),
            anchor_uid=str(messages[4].uid),
            direction=MessageHistoryDirection.BEFORE,
            limit=2,
        )
        after = self.service.list(
            conversation_uid=str(self.conversation.uid),
            anchor_uid=str(messages[4].uid),
            direction=MessageHistoryDirection.AFTER,
            limit=2,
        )

        self.assertEqual([item.id for item in before.results], [messages[2].id, messages[3].id])
        self.assertTrue(before.has_before)
        self.assertTrue(before.has_after)
        self.assertEqual([item.id for item in after.results], [messages[5].id, messages[6].id])
        self.assertTrue(after.has_before)
        self.assertTrue(after.has_after)

    def test_empty_conversation_and_empty_anchor_windows_have_stable_boundaries(self):
        empty_conversation = Conversation.objects.create(created_by=self.user, updated_by=self.user)
        empty_window = self.service.list(conversation_uid=str(empty_conversation.uid))
        self.assertEqual(empty_window.results, [])
        self.assertIsNone(empty_window.first_uid)
        self.assertIsNone(empty_window.last_uid)
        self.assertFalse(empty_window.has_before)
        self.assertFalse(empty_window.has_after)

        messages = [self.create_message(index) for index in range(2)]
        before = self.service.list(
            conversation_uid=str(self.conversation.uid),
            anchor_uid=str(messages[0].uid),
            direction=MessageHistoryDirection.BEFORE,
        )
        after = self.service.list(
            conversation_uid=str(self.conversation.uid),
            anchor_uid=str(messages[-1].uid),
            direction=MessageHistoryDirection.AFTER,
        )
        self.assertEqual(before.results, [])
        self.assertFalse(before.has_before)
        self.assertTrue(before.has_after)
        self.assertEqual(after.results, [])
        self.assertTrue(after.has_before)
        self.assertFalse(after.has_after)

    def test_anchor_and_direction_must_be_supplied_together(self):
        anchor = self.create_message(0)
        invalid_parameters = (
            {"anchor_uid": str(anchor.uid)},
            {"direction": MessageHistoryDirection.BEFORE},
            {"anchor_uid": str(anchor.uid), "direction": "INVALID"},
        )

        for parameters in invalid_parameters:
            with self.subTest(parameters=parameters), self.assertRaises(InvalidMessageAnchor):
                self.service.list(conversation_uid=str(self.conversation.uid), **parameters)

    def test_anchor_must_belong_to_current_user_and_conversation(self):
        other_conversation = Conversation.objects.create(created_by=self.user, updated_by=self.user)
        foreign_conversation = Conversation.objects.create(created_by="bob", updated_by="bob")
        invalid_anchor_uids = (
            "not-a-uuid",
            str(uuid4()),
            str(self.create_message(1, conversation=other_conversation).uid),
            str(self.create_message(2, conversation=foreign_conversation, user="bob").uid),
        )

        for anchor_uid in invalid_anchor_uids:
            with self.subTest(anchor_uid=anchor_uid), self.assertRaises(InvalidMessageAnchor):
                self.service.list(
                    conversation_uid=str(self.conversation.uid),
                    anchor_uid=anchor_uid,
                    direction=MessageHistoryDirection.AFTER,
                )

    def test_missing_or_foreign_conversation_is_not_an_empty_window(self):
        foreign_conversation = Conversation.objects.create(created_by="bob", updated_by="bob")
        invalid_conversation_uids = ("not-a-uuid", str(uuid4()), str(foreign_conversation.uid))

        for conversation_uid in invalid_conversation_uids:
            with self.subTest(conversation_uid=conversation_uid), self.assertRaises(ConversationNotFound):
                self.service.list(conversation_uid=conversation_uid)

    def test_get_is_scoped_to_current_user_and_active_conversation(self):
        message = self.create_message(0)
        other_conversation = Conversation.objects.create(created_by="bob", updated_by="bob")
        foreign_message = self.create_message(1, conversation=other_conversation, user="bob")

        self.assertEqual(self.service.get(message_uid=str(message.uid)).id, message.id)
        for message_uid in ("not-a-uuid", str(uuid4()), str(foreign_message.uid)):
            with self.subTest(message_uid=message_uid), self.assertRaises(MessageNotFound):
                self.service.get(message_uid=message_uid)

        self.conversation.delete()
        with self.assertRaises(MessageNotFound):
            self.service.get(message_uid=str(message.uid))

    def test_message_window_prefetches_all_attachments_in_constant_queries(self):
        messages = [self.create_message(index) for index in range(20)]
        for message in messages:
            for attachment_index in range(2):
                Attachment.objects.create(
                    source_message=message,
                    attachment_type=AttachmentType.FIELD_STATISTICS,
                    status=ExecutionStatus.SUCCESS,
                    input_data={"field": "event_id"},
                    context_data={},
                    output_data={"value": attachment_index},
                    created_by=self.user,
                    updated_by=self.user,
                )

        # 会话校验、消息窗口、附件预取、前后边界及当前用户反馈各一次，共 6 次查询。
        with self.assertNumQueries(6):
            window = self.service.list(conversation_uid=str(self.conversation.uid), limit=20)
            attachments = [attachment for message in window.results for attachment in message.attachments.all()]
            attachment_uids = [str(attachment.uid) for attachment in attachments]

        self.assertEqual(len(attachment_uids), 40)
        large_snapshot_fields = {
            "input_data",
            "context_data",
            "output_data",
            "stream_config",
            "stream_archive",
        }
        for attachment in attachments:
            self.assertTrue(large_snapshot_fields.issubset(attachment.get_deferred_fields()))

    def test_anchored_window_prefetches_attachments_in_constant_queries(self):
        messages = [self.create_message(index) for index in range(3)]
        Attachment.objects.create(
            source_message=messages[-1],
            attachment_type=AttachmentType.AI_ANALYSIS,
            status=ExecutionStatus.PROCESSING,
            input_data={},
            context_data={},
            output_data=None,
            created_by=self.user,
            updated_by=self.user,
        )

        # 带锚点比无锚点多一次锚点归属查询，共 7 次查询。
        with self.assertNumQueries(7):
            window = self.service.list(
                conversation_uid=str(self.conversation.uid),
                anchor_uid=str(messages[1].uid),
                direction=MessageHistoryDirection.AFTER,
            )
            attachment_uids = [
                str(attachment.uid) for message in window.results for attachment in message.attachments.all()
            ]

        self.assertEqual(len(attachment_uids), 1)

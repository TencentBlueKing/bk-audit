from unittest import mock

from django.db import IntegrityError, connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext

from core.models import SoftDeleteQuerySet
from services.web.ai_assistant.constants import (
    ExecutionStatus,
    MessageType,
    SidebarNodeType,
)
from services.web.ai_assistant.exceptions import (
    ConversationGroupNotFound,
    ConversationNotFound,
)
from services.web.ai_assistant.handlers import message_handler_registry
from services.web.ai_assistant.models import (
    Conversation,
    ConversationGroup,
    ConversationSidebarNode,
    Message,
)
from services.web.ai_assistant.services import ConversationService
from tests.base import TestCase
from tests.test_ai_assistant.handlers import (
    EchoSyncHandler,
    SystemSelectionAsyncHandler,
)


class ConversationServiceTest(TestCase):
    def setUp(self):
        self.user = "alice"
        self.other_user = "bob"
        self.service = ConversationService(user=self.user)
        self.other_service = ConversationService(user=self.other_user)
        message_handler_registry.register(EchoSyncHandler())

    def tearDown(self):
        message_handler_registry.unregister(MessageType.SYSTEM_SELECTION)

    def test_create_group_and_conversation_with_root_nodes(self):
        first_group = self.service.create_group(name="待分析")
        second_group = self.service.create_group(name="待分析")
        conversation = self.service.create_conversation(title="新对话").conversation

        self.assertNotEqual(first_group.uid, second_group.uid)
        self.assertEqual(conversation.title, "新对话")
        self.assertEqual(first_group.sidebar_node.position, 1)
        self.assertEqual(second_group.sidebar_node.position, 2)
        self.assertEqual(conversation.sidebar_node.position, 3)
        self.assertEqual(first_group.created_by, self.user)
        self.assertEqual(conversation.created_by, self.user)

    def test_service_binds_user_context(self):
        service = ConversationService(user=self.user)

        conversation = service.create_conversation(title="新对话").conversation

        self.assertEqual(conversation.created_by, self.user)

    def test_create_conversation_accepts_explicit_title(self):
        conversation = self.service.create_conversation(title="自定义标题").conversation

        self.assertEqual(conversation.title, "自定义标题")

    def test_create_empty_conversation_returns_null_initial_message(self):
        result = self.service.create_conversation(title="新对话")

        self.assertIsNone(result.initial_message)
        self.assertTrue(Conversation.objects.filter(id=result.conversation.id).exists())
        self.assertTrue(ConversationSidebarNode.objects.filter(conversation=result.conversation).exists())

    def test_create_conversation_with_initial_message_is_atomic(self):
        result = self.service.create_conversation(
            title="新对话",
            initial_message={
                "message_type": MessageType.SYSTEM_SELECTION,
                "input_data": {"text": "system-a"},
            },
        )

        self.assertEqual(result.initial_message.conversation, result.conversation)
        self.assertEqual(result.initial_message.status, ExecutionStatus.SUCCESS)
        self.assertEqual(result.initial_message.output_data, {"content": "system:system-a"})

    def test_create_conversation_supports_async_initial_message(self):
        message_handler_registry.unregister(MessageType.SYSTEM_SELECTION)
        handler = SystemSelectionAsyncHandler()
        message_handler_registry.register(handler)

        with mock.patch.object(handler.async_task, "apply_async") as apply_async:
            with self.captureOnCommitCallbacks(execute=True):
                result = self.service.create_conversation(
                    title="新对话",
                    initial_message={
                        "message_type": MessageType.SYSTEM_SELECTION,
                        "input_data": {"text": "system-a"},
                    },
                )

        self.assertEqual(result.initial_message.conversation, result.conversation)
        self.assertEqual(result.initial_message.status, ExecutionStatus.PROCESSING)
        self.assertIsNone(result.initial_message.output_data)
        apply_async.assert_called_once_with(
            kwargs={"message_id": result.initial_message.id, "task_id": result.initial_message.task_id},
            task_id=result.initial_message.task_id,
        )

    def test_initial_message_prepare_failure_leaves_no_conversation(self):
        with mock.patch.object(
            self.service.message_service,
            "prepare_initial",
            side_effect=RuntimeError("metadata failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "metadata failed"):
                self.service.create_conversation(
                    title="新对话",
                    initial_message={
                        "message_type": MessageType.SYSTEM_SELECTION,
                        "input_data": {"text": "system-a"},
                    },
                )

        self.assertFalse(Conversation.objects.filter(created_by=self.user).exists())
        self.assertFalse(ConversationSidebarNode.objects.filter(created_by=self.user).exists())
        self.assertFalse(Message.objects.filter(created_by=self.user).exists())

    def test_initial_message_database_failure_rolls_back_conversation_and_node(self):
        with mock.patch.object(
            self.service.message_service,
            "create_prepared",
            side_effect=IntegrityError("message write failed"),
        ):
            with self.assertRaises(IntegrityError):
                self.service.create_conversation(
                    title="新对话",
                    initial_message={
                        "message_type": MessageType.SYSTEM_SELECTION,
                        "input_data": {"text": "system-a"},
                    },
                )

        self.assertFalse(Conversation.objects.filter(created_by=self.user).exists())
        self.assertFalse(ConversationSidebarNode.objects.filter(created_by=self.user).exists())

    def test_create_rolls_back_business_object_when_node_creation_fails(self):
        with mock.patch(
            "services.web.ai_assistant.services.conversation.ConversationSidebarService.create_node",
            side_effect=RuntimeError("node failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "node failed"):
                self.service.create_group(name="rollback-group")
            with self.assertRaisesRegex(RuntimeError, "node failed"):
                self.service.create_conversation(title="新对话")

        self.assertFalse(ConversationGroup.objects.filter(created_by=self.user).exists())
        self.assertFalse(Conversation.objects.filter(created_by=self.user).exists())

    def test_get_and_rename_are_scoped_to_current_user(self):
        group = self.service.create_group(name="old-group")
        conversation = self.service.create_conversation(title="新对话").conversation

        renamed_group = self.service.rename_group(
            group_uid=str(group.uid),
            name="new-group",
        )
        renamed_conversation = self.service.rename_conversation(
            conversation_uid=str(conversation.uid),
            title="new-title",
        )

        self.assertEqual(renamed_group.name, "new-group")
        self.assertEqual(renamed_group.updated_by, self.user)
        self.assertEqual(renamed_conversation.title, "new-title")
        self.assertEqual(renamed_conversation.updated_by, self.user)
        self.assertEqual(
            self.service.get_conversation(conversation_uid=str(conversation.uid)).id,
            conversation.id,
        )

        with self.assertRaises(ConversationGroupNotFound):
            self.other_service.rename_group(group_uid=str(group.uid), name="forbidden")
        with self.assertRaises(ConversationNotFound):
            self.other_service.get_conversation(
                conversation_uid=str(conversation.uid),
            )

    def test_rename_does_not_use_explicit_row_locks(self):
        service = ConversationService(user=self.user)
        group = service.create_group(name="old-group")
        conversation = service.create_conversation(title="新对话").conversation

        with CaptureQueriesContext(connection) as captured:
            service.rename_group(group_uid=str(group.uid), name="new-group")
            service.rename_conversation(conversation_uid=str(conversation.uid), title="new-title")

        lock_queries = [query["sql"] for query in captured.captured_queries if "FOR UPDATE" in query["sql"].upper()]
        self.assertEqual(lock_queries, [])

    def test_delete_conversation_soft_deletes_object_without_rewriting_other_positions(self):
        first = self.service.create_conversation(title="新对话").conversation
        second = self.service.create_conversation(title="新对话").conversation
        third = self.service.create_conversation(title="新对话").conversation

        with mock.patch("core.models.get_request_username", return_value=self.user):
            self.service.delete_conversation(conversation_uid=str(second.uid))

        deleted = Conversation._objects.get(id=second.id)
        self.assertTrue(deleted.is_deleted)
        self.assertEqual(deleted.updated_by, self.user)
        self.assertFalse(ConversationSidebarNode.objects.filter(conversation_id=second.id).exists())
        self.assertEqual(
            list(
                ConversationSidebarNode.objects.filter(created_by=self.user)
                .order_by("-position")
                .values_list("conversation_id", "position")
            ),
            [(third.id, 3), (first.id, 1)],
        )
        with self.assertRaises(ConversationNotFound):
            self.service.delete_conversation(conversation_uid=str(second.uid))

    def test_delete_conversation_reuses_soft_delete_queryset(self):
        service = ConversationService(user=self.user)
        conversation = service.create_conversation(title="新对话").conversation
        delete_calls = []
        original_delete = SoftDeleteQuerySet.delete

        def recording_delete(queryset):
            delete_calls.append(str(queryset.query))
            return original_delete(queryset)

        with mock.patch("core.models.get_request_username", return_value=self.user), mock.patch.object(
            SoftDeleteQuerySet,
            "delete",
            recording_delete,
        ):
            service.delete_conversation(conversation_uid=str(conversation.uid))

        self.assertEqual(len(delete_calls), 1)

    def test_delete_group_soft_deletes_children_and_keeps_ungrouped_conversation(self):
        group = self.service.create_group(name="delete-me")
        other_group = self.service.create_group(name="keep-group")
        child_a = self.service.create_conversation(title="新对话").conversation
        child_b = self.service.create_conversation(title="新对话").conversation
        ungrouped = self.service.create_conversation(title="新对话").conversation
        ConversationSidebarNode.objects.filter(conversation_id__in=[child_a.id, child_b.id]).update(
            parent_node=group.sidebar_node,
            position=1,
            updated_by=self.user,
        )

        with mock.patch("core.models.get_request_username", return_value=self.user):
            self.service.delete_group(group_uid=str(group.uid))

        self.assertFalse(ConversationGroup.objects.filter(id=group.id).exists())
        self.assertTrue(Conversation._objects.get(id=child_a.id).is_deleted)
        self.assertTrue(Conversation._objects.get(id=child_b.id).is_deleted)
        self.assertFalse(Conversation._objects.get(id=ungrouped.id).is_deleted)
        self.assertFalse(ConversationSidebarNode.objects.filter(parent_node_id=group.sidebar_node.id).exists())
        self.assertEqual(
            list(
                ConversationSidebarNode.objects.filter(created_by=self.user, parent_node_id__isnull=True)
                .order_by("-position")
                .values_list("node_type", "position")
            ),
            [(SidebarNodeType.CONVERSATION, 5), (SidebarNodeType.GROUP, 2)],
        )
        self.assertTrue(ConversationSidebarNode.objects.filter(group=other_group).exists())

    def test_clear_soft_deletes_all_conversations_but_keeps_empty_groups(self):
        group = self.service.create_group(name="keep")
        first = self.service.create_conversation(title="新对话").conversation
        second = self.service.create_conversation(title="新对话").conversation
        other = self.other_service.create_conversation(title="新对话").conversation

        with mock.patch("core.models.get_request_username", return_value=self.user):
            self.service.clear_conversations()

        self.assertTrue(Conversation._objects.get(id=first.id).is_deleted)
        self.assertTrue(Conversation._objects.get(id=second.id).is_deleted)
        self.assertFalse(Conversation._objects.get(id=other.id).is_deleted)
        self.assertFalse(
            ConversationSidebarNode.objects.filter(
                created_by=self.user,
                node_type=SidebarNodeType.CONVERSATION,
            ).exists()
        )
        group_node = ConversationSidebarNode.objects.get(group=group)
        self.assertEqual(group_node.position, 1)

    def test_node_hard_delete_is_split_into_bounded_batches(self):
        conversations = [self.service.create_conversation(title="新对话").conversation for _ in range(3)]
        queryset = ConversationSidebarNode.objects.filter(
            conversation_id__in=[conversation.id for conversation in conversations]
        )

        with override_settings(AI_ASSISTANT_SIDEBAR_NODE_DELETE_BATCH_SIZE=2):
            self.service._delete_nodes_in_batches(queryset)

        self.assertFalse(queryset.exists())

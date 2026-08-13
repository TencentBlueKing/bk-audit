import uuid

from django.apps import apps
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.utils import timezone

from core.models import OperateRecordModel, SoftDeleteModel
from services.web.ai_assistant import models as ai_models
from services.web.ai_assistant.constants import (
    DEFAULT_CONVERSATION_TITLE,
    AttachmentType,
    ExecutionStatus,
    FeedbackSourceType,
    FeedbackType,
    MessageType,
    SidebarNodeType,
)
from services.web.ai_assistant.models import (
    Attachment,
    Conversation,
    ConversationGroup,
    ConversationSidebarNode,
    ExecutionSnapshotModel,
    ExternalUIDModel,
    Feedback,
    Message,
)
from services.web.query.constants import LogExportSourceType, TaskEnum
from services.web.query.models import LogExportTask


class AIAssistantConstantsTest(SimpleTestCase):
    def test_app_and_model_constants(self):
        self.assertEqual(apps.get_app_config("ai_assistant").name, "services.web.ai_assistant")
        self.assertEqual(DEFAULT_CONVERSATION_TITLE, "新对话")
        self.assertEqual(set(ExecutionStatus.values), {"PROCESSING", "SUCCESS", "FAILED"})
        self.assertEqual(
            set(MessageType.values),
            {"SYSTEM_SELECTION", "NATURAL_LANGUAGE_SEARCH", "LOG_SEARCH"},
        )
        self.assertEqual(
            set(AttachmentType.values),
            {"FIELD_STATISTICS", "AI_STATISTICS", "AI_ANALYSIS"},
        )
        self.assertEqual(set(FeedbackSourceType.values), {"MESSAGE", "ATTACHMENT"})
        self.assertEqual(set(FeedbackType.values), {"LIKE", "DISLIKE"})
        self.assertEqual(set(SidebarNodeType.values), {"GROUP", "CONVERSATION"})
        self.assertEqual(set(LogExportSourceType.values), {"WEB_LOG_SEARCH", "AI_ASSISTANT_MESSAGE"})


class AbstractModelTest(TestCase):
    def test_abstract_model_structure(self):
        self.assertTrue(ExternalUIDModel._meta.abstract)
        self.assertTrue(ExecutionSnapshotModel._meta.abstract)
        self.assertEqual(
            {field.name for field in ExecutionSnapshotModel._meta.local_fields},
            {
                "status",
                "task_id",
                "input_data",
                "context_data",
                "output_data",
                "error_code",
                "error_message",
            },
        )
        self.assertFalse(hasattr(ai_models, "SourceModel"))

    def test_external_uid_is_unique_uuid4(self):
        first = ConversationGroup.objects.create(name="默认分组", created_by="alice")
        second = ConversationGroup.objects.create(name="默认分组", created_by="alice")

        self.assertIsInstance(first.uid, uuid.UUID)
        self.assertEqual(first.uid.version, 4)
        self.assertEqual(second.uid.version, 4)
        self.assertNotEqual(first.uid, second.uid)

    def test_concrete_models_use_confirmed_base_classes(self):
        expected_bases = {
            ConversationGroup: (ExternalUIDModel, OperateRecordModel),
            Conversation: (ExternalUIDModel, SoftDeleteModel),
            ConversationSidebarNode: (OperateRecordModel,),
            Message: (ExternalUIDModel, OperateRecordModel, ExecutionSnapshotModel),
            Attachment: (ExternalUIDModel, OperateRecordModel, ExecutionSnapshotModel),
            Feedback: (ExternalUIDModel, OperateRecordModel),
        }

        for model, bases in expected_bases.items():
            for base in bases:
                with self.subTest(model=model, base=base):
                    self.assertTrue(issubclass(model, base))
        self.assertFalse(issubclass(ConversationGroup, SoftDeleteModel))
        self.assertNotIn("uid", {field.name for field in ConversationSidebarNode._meta.fields})
        self.assertFalse(issubclass(Feedback, ExecutionSnapshotModel))

    def test_confirmed_composite_indexes_and_non_unique_position(self):
        expected_indexes = {
            Conversation: [("created_by", "is_deleted", "updated_at", "id")],
            ConversationSidebarNode: [
                ("created_by", "parent_node", "position", "id"),
                ("created_by", "pinned_at", "id"),
            ],
            Message: [
                ("conversation", "id"),
                ("parent_message", "message_type", "id"),
                ("status", "task_id"),
                ("status", "updated_at", "id"),
            ],
            Attachment: [
                ("source_message", "id"),
                ("status", "task_id"),
                ("status", "updated_at", "id"),
                ("created_by", "attachment_type", "status", "content_updated_at", "id"),
            ],
            Feedback: [("source_type", "source_id")],
            LogExportTask: [("source_type", "source_id")],
        }

        for model, expected in expected_indexes.items():
            with self.subTest(model=model):
                self.assertEqual([tuple(index.fields) for index in model._meta.indexes], expected)
        self.assertFalse(ConversationSidebarNode._meta.get_field("position").unique)


class ConversationModelTest(TestCase):
    def test_conversation_uses_default_title_and_soft_delete(self):
        conversation = Conversation.objects.create(created_by="alice")
        self.assertEqual(conversation.title, DEFAULT_CONVERSATION_TITLE)

        conversation.delete()

        self.assertFalse(Conversation.objects.filter(pk=conversation.pk).exists())
        self.assertTrue(Conversation._objects.get(pk=conversation.pk).is_deleted)

    def test_group_allows_duplicate_name_and_is_physically_deleted(self):
        first = ConversationGroup.objects.create(name="工作", created_by="alice")
        second = ConversationGroup.objects.create(name="工作", created_by="alice")
        self.assertNotEqual(first.pk, second.pk)

        first.delete()

        self.assertFalse(ConversationGroup.objects.filter(pk=first.pk).exists())
        self.assertTrue(ConversationGroup.objects.filter(pk=second.pk).exists())


class SidebarNodeModelTest(TestCase):
    def setUp(self):
        self.group = ConversationGroup.objects.create(name="工作", created_by="alice")
        self.conversation = Conversation.objects.create(created_by="alice")
        self.group_node = ConversationSidebarNode.objects.create(
            node_type=SidebarNodeType.GROUP,
            group=self.group,
            created_by="alice",
        )

    def test_valid_group_and_conversation_nodes(self):
        self.group_node.full_clean()
        conversation_node = ConversationSidebarNode(
            node_type=SidebarNodeType.CONVERSATION,
            conversation=self.conversation,
            parent_node=self.group_node,
            created_by="alice",
        )

        conversation_node.full_clean()

    def test_group_node_rejects_conversation_parent_and_pin(self):
        invalid_values = (
            {"conversation": self.conversation},
            {"parent_node": self.group_node},
            {"pinned_at": timezone.now()},
        )
        for values in invalid_values:
            with self.subTest(values=values):
                node = ConversationSidebarNode(
                    node_type=SidebarNodeType.GROUP,
                    group=ConversationGroup.objects.create(name="分组", created_by="alice"),
                    created_by="alice",
                    **values,
                )
                with self.assertRaises(ValidationError):
                    node.full_clean()

    def test_group_node_requires_group(self):
        with self.assertRaises(ValidationError):
            ConversationSidebarNode(
                node_type=SidebarNodeType.GROUP,
                created_by="alice",
            ).full_clean()

    def test_conversation_node_rejects_invalid_target_or_parent(self):
        with self.assertRaises(ValidationError):
            ConversationSidebarNode(
                node_type=SidebarNodeType.CONVERSATION,
                created_by="alice",
            ).full_clean()

        with self.assertRaises(ValidationError):
            ConversationSidebarNode(
                node_type=SidebarNodeType.CONVERSATION,
                group=self.group,
                conversation=self.conversation,
                created_by="alice",
            ).full_clean()

        parent_conversation = Conversation.objects.create(created_by="alice")
        conversation_parent_node = ConversationSidebarNode.objects.create(
            node_type=SidebarNodeType.CONVERSATION,
            conversation=parent_conversation,
            created_by="alice",
        )
        with self.assertRaises(ValidationError):
            ConversationSidebarNode(
                node_type=SidebarNodeType.CONVERSATION,
                conversation=self.conversation,
                parent_node=conversation_parent_node,
                created_by="alice",
            ).full_clean()

    def test_node_rejects_cross_user_target_and_parent(self):
        other_group = ConversationGroup.objects.create(name="其他", created_by="bob")
        with self.assertRaises(ValidationError):
            ConversationSidebarNode(
                node_type=SidebarNodeType.GROUP,
                group=other_group,
                created_by="alice",
            ).full_clean()

        other_conversation = Conversation.objects.create(created_by="bob")
        with self.assertRaises(ValidationError):
            ConversationSidebarNode(
                node_type=SidebarNodeType.CONVERSATION,
                conversation=other_conversation,
                created_by="alice",
            ).full_clean()

        other_group_node = ConversationSidebarNode.objects.create(
            node_type=SidebarNodeType.GROUP,
            group=other_group,
            created_by="bob",
        )
        with self.assertRaises(ValidationError):
            ConversationSidebarNode(
                node_type=SidebarNodeType.CONVERSATION,
                conversation=self.conversation,
                parent_node=other_group_node,
                created_by="alice",
            ).full_clean()

    def test_invalid_related_ids_raise_validation_error(self):
        invalid_nodes = (
            ConversationSidebarNode(
                node_type=SidebarNodeType.GROUP,
                group_id=999999999,
                created_by="alice",
            ),
            ConversationSidebarNode(
                node_type=SidebarNodeType.CONVERSATION,
                conversation_id=999999999,
                created_by="alice",
            ),
            ConversationSidebarNode(
                node_type=SidebarNodeType.CONVERSATION,
                conversation=self.conversation,
                parent_node_id=999999999,
                created_by="alice",
            ),
        )

        for node in invalid_nodes:
            with self.subTest(node_type=node.node_type), self.assertRaises(ValidationError):
                node.full_clean()

    def test_group_and_conversation_targets_are_one_to_one(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            ConversationSidebarNode.objects.create(
                node_type=SidebarNodeType.GROUP,
                group=self.group,
                created_by="alice",
            )

        ConversationSidebarNode.objects.create(
            node_type=SidebarNodeType.CONVERSATION,
            conversation=self.conversation,
            created_by="alice",
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            ConversationSidebarNode.objects.create(
                node_type=SidebarNodeType.CONVERSATION,
                conversation=self.conversation,
                created_by="alice",
            )

    def test_deleting_group_cascades_sidebar_nodes_only(self):
        conversation_node = ConversationSidebarNode.objects.create(
            node_type=SidebarNodeType.CONVERSATION,
            conversation=self.conversation,
            parent_node=self.group_node,
            created_by="alice",
        )

        self.group.delete()

        self.assertFalse(ConversationSidebarNode.objects.filter(pk=self.group_node.pk).exists())
        self.assertFalse(ConversationSidebarNode.objects.filter(pk=conversation_node.pk).exists())
        self.assertTrue(Conversation.objects.filter(pk=self.conversation.pk).exists())


class MessageModelTest(TestCase):
    def setUp(self):
        self.conversation = Conversation.objects.create(created_by="alice")

    def test_json_defaults_are_isolated_and_ids_are_increasing(self):
        first = Message.objects.create(
            conversation=self.conversation,
            message_type=MessageType.SYSTEM_SELECTION,
            created_by="alice",
        )
        second = Message.objects.create(
            conversation=self.conversation,
            message_type=MessageType.LOG_SEARCH,
            created_by="alice",
        )

        first.input_data["system_id"] = "bk-audit"

        self.assertEqual(second.input_data, {})
        self.assertEqual(second.context_data, {})
        self.assertIsNone(second.output_data)
        self.assertGreater(second.id, first.id)

    def test_deleting_parent_message_keeps_child(self):
        parent = Message.objects.create(
            conversation=self.conversation,
            message_type=MessageType.NATURAL_LANGUAGE_SEARCH,
            created_by="alice",
        )
        child = Message.objects.create(
            conversation=self.conversation,
            parent_message=parent,
            message_type=MessageType.LOG_SEARCH,
            created_by="alice",
        )

        parent.delete()

        child.refresh_from_db()
        self.assertIsNone(child.parent_message_id)


class AttachmentModelTest(TestCase):
    def setUp(self):
        self.conversation = Conversation.objects.create(created_by="alice")
        self.message = Message.objects.create(
            conversation=self.conversation,
            message_type=MessageType.LOG_SEARCH,
            created_by="alice",
        )

    def test_stream_archive_is_an_isolated_json_list(self):
        first = Attachment.objects.create(
            source_message=self.message,
            attachment_type=AttachmentType.AI_ANALYSIS,
            created_by="alice",
        )
        second = Attachment.objects.create(
            source_message=self.message,
            attachment_type=AttachmentType.AI_STATISTICS,
            created_by="alice",
        )
        first.stream_archive.append({"type": "TEXT_MESSAGE_CONTENT", "delta": "分析中"})
        first.save(update_fields=["stream_archive"])

        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.stream_archive, [{"type": "TEXT_MESSAGE_CONTENT", "delta": "分析中"}])
        self.assertEqual(second.stream_archive, [])

    def test_deleting_source_message_cascades_attachments(self):
        attachment = Attachment.objects.create(
            source_message=self.message,
            attachment_type=AttachmentType.FIELD_STATISTICS,
            created_by="alice",
        )

        self.message.delete()

        self.assertFalse(Attachment.objects.filter(pk=attachment.pk).exists())


class FeedbackModelTest(TestCase):
    def test_feedback_is_unique_per_user_and_source(self):
        Feedback.objects.create(
            source_type=FeedbackSourceType.MESSAGE,
            source_id=1,
            feedback_type=FeedbackType.LIKE,
            created_by="alice",
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            Feedback.objects.create(
                source_type=FeedbackSourceType.MESSAGE,
                source_id=1,
                feedback_type=FeedbackType.DISLIKE,
                created_by="alice",
            )

    def test_feedback_can_differ_by_user_type_or_source_id(self):
        values = (
            ("alice", FeedbackSourceType.MESSAGE, 1),
            ("bob", FeedbackSourceType.MESSAGE, 1),
            ("alice", FeedbackSourceType.ATTACHMENT, 1),
            ("alice", FeedbackSourceType.MESSAGE, 2),
        )
        for created_by, source_type, source_id in values:
            Feedback.objects.create(
                source_type=source_type,
                source_id=source_id,
                feedback_type=FeedbackType.LIKE,
                created_by=created_by,
            )

        self.assertEqual(Feedback.objects.count(), 4)


class LogExportTaskSourceTest(TestCase):
    def test_legacy_export_uses_web_source_defaults(self):
        task = LogExportTask.objects.create(namespace="default", status=TaskEnum.READY, created_by="alice")

        self.assertEqual(task.source_type, LogExportSourceType.WEB_LOG_SEARCH)
        self.assertIsNone(task.source_id)

    def test_ai_export_can_reference_message_internal_id(self):
        conversation = Conversation.objects.create(created_by="alice")
        message = Message.objects.create(
            conversation=conversation,
            message_type=MessageType.LOG_SEARCH,
            created_by="alice",
        )
        task = LogExportTask.objects.create(
            namespace="default",
            status=TaskEnum.READY,
            source_type=LogExportSourceType.AI_ASSISTANT_MESSAGE,
            source_id=message.id,
            created_by="alice",
        )

        self.assertEqual(task.source_type, LogExportSourceType.AI_ASSISTANT_MESSAGE)
        self.assertEqual(task.source_id, message.id)


class _AllowAllPermissionsUser:
    def has_perm(self, permission):
        return True


class AIAssistantAdminTest(SimpleTestCase):
    def setUp(self):
        self.request = RequestFactory().get("/admin/")
        self.request.user = _AllowAllPermissionsUser()

    def test_all_platform_models_are_registered(self):
        for model in (
            ConversationGroup,
            Conversation,
            ConversationSidebarNode,
            Message,
            Attachment,
            Feedback,
        ):
            with self.subTest(model=model):
                self.assertIn(model, admin.site._registry)

    def test_core_models_cannot_be_added_or_deleted_in_admin(self):
        for model in (ConversationGroup, Conversation, ConversationSidebarNode, Message, Attachment):
            with self.subTest(model=model):
                model_admin = admin.site._registry[model]
                self.assertFalse(model_admin.has_add_permission(self.request))
                self.assertFalse(model_admin.has_delete_permission(self.request))

    def test_feedback_keeps_delete_permission_and_protects_source_fields(self):
        feedback_admin = admin.site._registry[Feedback]

        self.assertTrue(feedback_admin.has_delete_permission(self.request))
        self.assertEqual(
            set(feedback_admin.get_readonly_fields(self.request)),
            {"uid", "source_type", "source_id", "created_by", "created_at", "updated_by", "updated_at"},
        )

    def test_log_export_admin_exposes_source_queries_and_keeps_actions(self):
        export_admin = admin.site._registry[LogExportTask]

        for field in ("source_type", "source_id"):
            self.assertIn(field, export_admin.list_display)
            self.assertIn(field, export_admin.list_filter)
            self.assertIn(field, export_admin.search_fields)
        self.assertEqual(set(export_admin.actions), {"mark_as_deleted", "restore_deleted"})

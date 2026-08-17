from uuid import uuid4

from services.web.ai_assistant.constants import SidebarNodeType
from services.web.ai_assistant.exceptions import (
    AIAssistantException,
    ConversationGroupNotFound,
    ConversationNotFound,
    InvalidSidebarAnchor,
    InvalidSidebarContainer,
    SidebarNodeNotFound,
    SidebarNodeNotMovable,
    SidebarNodeNotPinnable,
)
from services.web.ai_assistant.serializers import (
    ConversationCreateRequestSerializer,
    ConversationDetailRequestSerializer,
    ConversationGroupCreateRequestSerializer,
    ConversationGroupDetailRequestSerializer,
    ConversationGroupUpdateRequestSerializer,
    ConversationUpdateRequestSerializer,
    SidebarMoveRequestSerializer,
    SidebarNodeListRequestSerializer,
    SidebarPinRequestSerializer,
    SidebarSearchRequestSerializer,
)
from services.web.ai_assistant.serializers.conversation import (
    ConversationCreateResponseSerializer,
    ConversationGroupResponseSerializer,
    ConversationGroupSummarySerializer,
    ConversationResponseSerializer,
    ConversationSearchResponseSerializer,
    SidebarNodeResponseSerializer,
)
from tests.base import TestCase


class ConversationRequestSerializerTest(TestCase):
    def test_all_api_fields_have_swagger_descriptions(self):
        serializer_classes = (
            ConversationCreateRequestSerializer,
            ConversationCreateResponseSerializer,
            ConversationDetailRequestSerializer,
            ConversationGroupCreateRequestSerializer,
            ConversationGroupDetailRequestSerializer,
            ConversationGroupResponseSerializer,
            ConversationGroupUpdateRequestSerializer,
            ConversationGroupSummarySerializer,
            ConversationResponseSerializer,
            ConversationSearchResponseSerializer,
            ConversationUpdateRequestSerializer,
            SidebarMoveRequestSerializer,
            SidebarNodeListRequestSerializer,
            SidebarNodeResponseSerializer,
            SidebarPinRequestSerializer,
            SidebarSearchRequestSerializer,
        )

        for serializer_class in serializer_classes:
            for field_name, field in serializer_class().fields.items():
                with self.subTest(serializer=serializer_class.__name__, field=field_name):
                    self.assertTrue(field.help_text)

    def test_search_response_only_declares_conversation_fields(self):
        self.assertEqual(
            set(ConversationSearchResponseSerializer().fields),
            {"node_type", "node_uid", "title", "updated_at", "pinned_at", "group", "is_pinned"},
        )

    def test_group_name_is_trimmed_and_required(self):
        serializer = ConversationGroupCreateRequestSerializer(data={"name": "  生产排查  "})

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data, {"name": "生产排查"})

        for invalid_name in ("", "   ", "x" * 65):
            with self.subTest(name=invalid_name):
                serializer = ConversationGroupCreateRequestSerializer(data={"name": invalid_name})
                self.assertFalse(serializer.is_valid())

    def test_group_update_requires_uid_and_valid_name(self):
        group_uid = uuid4()
        serializer = ConversationGroupUpdateRequestSerializer(data={"group_uid": str(group_uid), "name": "  已处理  "})

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["group_uid"], group_uid)
        self.assertEqual(serializer.validated_data["name"], "已处理")

    def test_conversation_title_is_trimmed_and_limited(self):
        conversation_uid = uuid4()
        serializer = ConversationUpdateRequestSerializer(
            data={"conversation_uid": str(conversation_uid), "title": "  登录失败分析  "}
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["title"], "登录失败分析")

        for invalid_title in ("", "   ", "x" * 256):
            with self.subTest(title=invalid_title):
                serializer = ConversationUpdateRequestSerializer(
                    data={"conversation_uid": str(conversation_uid), "title": invalid_title}
                )
                self.assertFalse(serializer.is_valid())


class SidebarRequestSerializerTest(TestCase):
    def setUp(self):
        self.source_uid = str(uuid4())
        self.target_uid = str(uuid4())
        self.anchor_uid = str(uuid4())

    def test_node_list_parent_fields_must_be_paired_and_group(self):
        valid = SidebarNodeListRequestSerializer(
            data={"parent_node_type": SidebarNodeType.GROUP, "parent_node_uid": self.target_uid}
        )
        self.assertTrue(valid.is_valid(), valid.errors)

        for data in (
            {"parent_node_type": SidebarNodeType.GROUP},
            {"parent_node_uid": self.target_uid},
            {
                "parent_node_type": SidebarNodeType.CONVERSATION,
                "parent_node_uid": self.target_uid,
            },
        ):
            with self.subTest(data=data):
                serializer = SidebarNodeListRequestSerializer(data=data)
                self.assertFalse(serializer.is_valid())

    def test_move_accepts_root_or_group_container_and_optional_anchor(self):
        root_move = SidebarMoveRequestSerializer(
            data={
                "source_node_type": SidebarNodeType.CONVERSATION,
                "source_node_uid": self.source_uid,
            }
        )
        group_move = SidebarMoveRequestSerializer(
            data={
                "source_node_type": SidebarNodeType.CONVERSATION,
                "source_node_uid": self.source_uid,
                "target_node_type": SidebarNodeType.GROUP,
                "target_node_uid": self.target_uid,
                "before_node_type": SidebarNodeType.CONVERSATION,
                "before_node_uid": self.anchor_uid,
            }
        )

        self.assertTrue(root_move.is_valid(), root_move.errors)
        self.assertTrue(group_move.is_valid(), group_move.errors)

    def test_move_requires_paired_target_and_anchor_fields(self):
        base = {
            "source_node_type": SidebarNodeType.CONVERSATION,
            "source_node_uid": self.source_uid,
        }
        for extra in (
            {"target_node_type": SidebarNodeType.GROUP},
            {"target_node_uid": self.target_uid},
            {"before_node_type": SidebarNodeType.CONVERSATION},
            {"before_node_uid": self.anchor_uid},
        ):
            with self.subTest(extra=extra):
                serializer = SidebarMoveRequestSerializer(data={**base, **extra})
                self.assertFalse(serializer.is_valid())

    def test_move_rejects_conversation_container_and_nested_group(self):
        conversation_target = SidebarMoveRequestSerializer(
            data={
                "source_node_type": SidebarNodeType.CONVERSATION,
                "source_node_uid": self.source_uid,
                "target_node_type": SidebarNodeType.CONVERSATION,
                "target_node_uid": self.target_uid,
            }
        )
        nested_group = SidebarMoveRequestSerializer(
            data={
                "source_node_type": SidebarNodeType.GROUP,
                "source_node_uid": self.source_uid,
                "target_node_type": SidebarNodeType.GROUP,
                "target_node_uid": self.target_uid,
            }
        )

        self.assertFalse(conversation_target.is_valid())
        self.assertFalse(nested_group.is_valid())

    def test_group_container_only_accepts_conversation_anchor(self):
        serializer = SidebarMoveRequestSerializer(
            data={
                "source_node_type": SidebarNodeType.CONVERSATION,
                "source_node_uid": self.source_uid,
                "target_node_type": SidebarNodeType.GROUP,
                "target_node_uid": self.target_uid,
                "before_node_type": SidebarNodeType.GROUP,
                "before_node_uid": self.anchor_uid,
            }
        )

        self.assertFalse(serializer.is_valid())

    def test_pin_only_accepts_conversation_node(self):
        valid = SidebarPinRequestSerializer(
            data={
                "node_type": SidebarNodeType.CONVERSATION,
                "node_uid": self.source_uid,
                "is_pinned": True,
            }
        )
        invalid = SidebarPinRequestSerializer(
            data={
                "node_type": SidebarNodeType.GROUP,
                "node_uid": self.source_uid,
                "is_pinned": True,
            }
        )

        self.assertTrue(valid.is_valid(), valid.errors)
        self.assertFalse(invalid.is_valid())

    def test_search_keyword_is_trimmed_and_required(self):
        serializer = SidebarSearchRequestSerializer(data={"keyword": "  登录  "})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["keyword"], "登录")

        for keyword in ("", "  ", "x" * 256):
            with self.subTest(keyword=keyword):
                serializer = SidebarSearchRequestSerializer(data={"keyword": keyword})
                self.assertFalse(serializer.is_valid())


class ConversationExceptionContractTest(TestCase):
    def test_sidebar_exceptions_have_unique_stable_codes(self):
        exception_types = (
            ConversationNotFound,
            ConversationGroupNotFound,
            SidebarNodeNotFound,
            InvalidSidebarContainer,
            InvalidSidebarAnchor,
            SidebarNodeNotMovable,
            SidebarNodeNotPinnable,
        )

        codes = {exception_type().code for exception_type in exception_types}

        self.assertEqual(len(codes), len(exception_types))
        self.assertNotIn("", codes)

    def test_exception_classes_are_constructible_without_runtime_context(self):
        for exception_type in (
            ConversationNotFound,
            ConversationGroupNotFound,
            SidebarNodeNotFound,
            InvalidSidebarContainer,
            InvalidSidebarAnchor,
            SidebarNodeNotMovable,
            SidebarNodeNotPinnable,
        ):
            with self.subTest(exception_type=exception_type.__name__):
                self.assertIsInstance(exception_type(), AIAssistantException)

from django.db import connection
from django.test.utils import CaptureQueriesContext

from services.web.ai_assistant.constants import SidebarNodeType
from services.web.ai_assistant.exceptions import (
    InvalidSidebarAnchor,
    InvalidSidebarContainer,
    SidebarNodeNotFound,
    SidebarNodeNotMovable,
)
from services.web.ai_assistant.models import (
    Conversation,
    ConversationGroup,
    ConversationSidebarNode,
)
from services.web.ai_assistant.serializers.conversation import (
    ConversationSearchResponseSerializer,
    SidebarNodeResponseSerializer,
)
from services.web.ai_assistant.services import ConversationSidebarService
from tests.base import TestCase


class ConversationSidebarContainerTest(TestCase):
    def setUp(self):
        self.user = "alice"
        self.other_user = "bob"
        self.service = ConversationSidebarService(user=self.user)
        self.other_service = ConversationSidebarService(user=self.other_user)

    @staticmethod
    def create_group(*, user: str, name: str = "group") -> ConversationGroup:
        return ConversationGroup.objects.create(name=name, created_by=user, updated_by=user)

    @staticmethod
    def create_conversation(*, user: str, title: str = "conversation") -> Conversation:
        return Conversation.objects.create(title=title, created_by=user, updated_by=user)

    @staticmethod
    def create_raw_node(
        *,
        user: str,
        position: int,
        group: ConversationGroup | None = None,
        conversation: Conversation | None = None,
        parent_node: ConversationSidebarNode | None = None,
    ) -> ConversationSidebarNode:
        return ConversationSidebarNode.objects.create(
            node_type=SidebarNodeType.GROUP if group else SidebarNodeType.CONVERSATION,
            group=group,
            conversation=conversation,
            parent_node=parent_node,
            position=position,
            created_by=user,
            updated_by=user,
        )

    def positions(self, *, user: str, parent_node_id: int | None = None) -> list[int]:
        queryset = ConversationSidebarNode.objects.filter(created_by=user)
        if parent_node_id is None:
            queryset = queryset.filter(parent_node_id__isnull=True)
        else:
            queryset = queryset.filter(parent_node_id=parent_node_id)
        return list(queryset.order_by("-position", "-id").values_list("position", flat=True))

    def test_create_root_nodes_assigns_increasing_positions(self):
        group = self.create_group(user=self.user)
        conversation = self.create_conversation(user=self.user)

        group_node = self.service.create_node(group=group)
        conversation_node = self.service.create_node(conversation=conversation)

        self.assertEqual(group_node.position, 1)
        self.assertEqual(conversation_node.position, 2)
        self.assertEqual(group_node.updated_by, self.user)
        self.assertEqual(conversation_node.updated_by, self.user)
        self.assertEqual(self.positions(user=self.user), [2, 1])

    def test_create_node_requires_one_owned_business_object(self):
        group = self.create_group(user=self.user)
        conversation = self.create_conversation(user=self.user)
        other_conversation = self.create_conversation(user=self.other_user)

        for kwargs in (
            {},
            {"group": group, "conversation": conversation},
            {"conversation": other_conversation},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(InvalidSidebarContainer):
                    self.service.create_node(**kwargs)

    def test_create_node_uses_current_max_without_rewriting_existing_positions(self):
        old_group = self.create_group(user=self.user, name="old")
        old_conversation = self.create_conversation(user=self.user, title="old")
        self.create_raw_node(user=self.user, group=old_group, position=10)
        self.create_raw_node(user=self.user, conversation=old_conversation, position=10)

        other_group = self.create_group(user=self.other_user)
        self.create_raw_node(user=self.other_user, group=other_group, position=99)

        new_conversation = self.create_conversation(user=self.user, title="new")
        new_node = self.service.create_node(conversation=new_conversation)

        self.assertEqual(new_node.position, 11)
        self.assertEqual(self.positions(user=self.user), [11, 10, 10])
        self.assertEqual(self.positions(user=self.other_user), [99])


class ConversationSidebarBehaviorTest(ConversationSidebarContainerTest):
    """验证移动、置顶和读取都只作用于当前用户的精确容器。"""

    def ordered_node_uids(self, *, parent_node_id: int | None = None) -> list[str]:
        queryset = ConversationSidebarNode.objects.filter(created_by=self.user)
        if parent_node_id is None:
            queryset = queryset.filter(parent_node_id__isnull=True)
        else:
            queryset = queryset.filter(parent_node_id=parent_node_id)
        return [
            str(node.group.uid if node.node_type == SidebarNodeType.GROUP else node.conversation.uid)
            for node in queryset.order_by("-position", "-id")
        ]

    def create_conversation_node(
        self,
        *,
        title: str,
        parent_node: ConversationSidebarNode | None = None,
    ) -> ConversationSidebarNode:
        conversation = self.create_conversation(user=self.user, title=title)
        node = self.service.create_node(conversation=conversation)
        if parent_node is not None:
            node.parent_node = parent_node
            node.save(update_fields=["parent_node"])
        return node

    def test_move_root_node_before_anchor_keeps_relative_order(self):
        first = self.create_conversation_node(title="first")
        second = self.create_conversation_node(title="second")
        third = self.create_conversation_node(title="third")

        moved = self.service.move(
            source_node_type=SidebarNodeType.CONVERSATION,
            source_node_uid=str(first.conversation.uid),
            before_node_type=SidebarNodeType.CONVERSATION,
            before_node_uid=str(third.conversation.uid),
        )

        self.assertEqual(moved.id, first.id)
        self.assertEqual(
            self.ordered_node_uids(),
            [str(first.conversation.uid), str(third.conversation.uid), str(second.conversation.uid)],
        )
        self.assertEqual(self.positions(user=self.user), [4, 3, 2])

    def test_move_root_node_after_anchor_keeps_relative_order(self):
        first = self.create_conversation_node(title="first")
        second = self.create_conversation_node(title="second")
        third = self.create_conversation_node(title="third")

        moved = self.service.move(
            source_node_type=SidebarNodeType.CONVERSATION,
            source_node_uid=str(first.conversation.uid),
            after_node_type=SidebarNodeType.CONVERSATION,
            after_node_uid=str(third.conversation.uid),
        )

        self.assertEqual(moved.id, first.id)
        self.assertEqual(
            self.ordered_node_uids(),
            [str(third.conversation.uid), str(first.conversation.uid), str(second.conversation.uid)],
        )

    def test_move_after_anchor_uses_pinned_node_as_implicit_successor(self):
        anchor = self.create_conversation_node(title="anchor")
        pinned = self.create_conversation_node(title="pinned")
        source = self.create_conversation_node(title="source")
        tail = self.create_conversation_node(title="tail")
        for node, position in ((anchor, 4), (pinned, 3), (source, 2), (tail, 1)):
            ConversationSidebarNode.objects.filter(id=node.id).update(position=position)
        self.service.set_pinned(
            conversation_uid=str(pinned.conversation.uid),
            is_pinned=True,
        )

        self.service.move(
            source_node_type=SidebarNodeType.CONVERSATION,
            source_node_uid=str(source.conversation.uid),
            after_node_type=SidebarNodeType.CONVERSATION,
            after_node_uid=str(anchor.conversation.uid),
        )

        self.assertEqual(
            self.ordered_node_uids(),
            [
                str(anchor.conversation.uid),
                str(source.conversation.uid),
                str(pinned.conversation.uid),
                str(tail.conversation.uid),
            ],
        )
        self.assertEqual(
            [str(node.conversation.uid) for node in self.service.list_nodes()],
            [str(anchor.conversation.uid), str(source.conversation.uid), str(tail.conversation.uid)],
        )

        self.service.set_pinned(
            conversation_uid=str(pinned.conversation.uid),
            is_pinned=False,
        )
        self.assertEqual(
            self.ordered_node_uids(),
            [
                str(anchor.conversation.uid),
                str(source.conversation.uid),
                str(pinned.conversation.uid),
                str(tail.conversation.uid),
            ],
        )

    def test_move_after_last_anchor_places_node_at_container_end(self):
        first = self.create_conversation_node(title="first")
        second = self.create_conversation_node(title="second")
        third = self.create_conversation_node(title="third")

        self.service.move(
            source_node_type=SidebarNodeType.CONVERSATION,
            source_node_uid=str(third.conversation.uid),
            after_node_type=SidebarNodeType.CONVERSATION,
            after_node_uid=str(first.conversation.uid),
        )

        self.assertEqual(
            self.ordered_node_uids(),
            [str(second.conversation.uid), str(first.conversation.uid), str(third.conversation.uid)],
        )

    def test_move_after_last_anchor_is_idempotent_when_source_is_at_end(self):
        anchor = self.create_conversation_node(title="anchor")
        source = self.create_conversation_node(title="source")
        ConversationSidebarNode.objects.filter(id=anchor.id).update(position=2)
        ConversationSidebarNode.objects.filter(id=source.id).update(position=1)
        original_positions = self.positions(user=self.user)

        self.service.move(
            source_node_type=SidebarNodeType.CONVERSATION,
            source_node_uid=str(source.conversation.uid),
            after_node_type=SidebarNodeType.CONVERSATION,
            after_node_uid=str(anchor.conversation.uid),
        )

        self.assertEqual(
            self.ordered_node_uids(),
            [str(anchor.conversation.uid), str(source.conversation.uid)],
        )
        self.assertEqual(self.positions(user=self.user), original_positions)

    def test_move_conversation_between_root_and_group(self):
        group = self.create_group(user=self.user)
        group_node = self.service.create_node(group=group)
        existing = self.create_conversation_node(title="existing", parent_node=group_node)
        source = self.create_conversation_node(title="source")

        self.service.move(
            source_node_type=SidebarNodeType.CONVERSATION,
            source_node_uid=str(source.conversation.uid),
            target_node_type=SidebarNodeType.GROUP,
            target_node_uid=str(group.uid),
            before_node_type=SidebarNodeType.CONVERSATION,
            before_node_uid=str(existing.conversation.uid),
        )

        source.refresh_from_db()
        self.assertEqual(source.parent_node_id, group_node.id)
        self.assertEqual(
            self.ordered_node_uids(parent_node_id=group_node.id),
            [str(source.conversation.uid), str(existing.conversation.uid)],
        )
        self.assertEqual(self.positions(user=self.user), [1])

    def test_move_conversation_into_group_after_anchor(self):
        group = self.create_group(user=self.user)
        group_node = self.service.create_node(group=group)
        existing = self.create_conversation_node(title="existing", parent_node=group_node)
        source = self.create_conversation_node(title="source")

        self.service.move(
            source_node_type=SidebarNodeType.CONVERSATION,
            source_node_uid=str(source.conversation.uid),
            target_node_type=SidebarNodeType.GROUP,
            target_node_uid=str(group.uid),
            after_node_type=SidebarNodeType.CONVERSATION,
            after_node_uid=str(existing.conversation.uid),
        )

        source.refresh_from_db()
        self.assertEqual(source.parent_node_id, group_node.id)
        self.assertEqual(
            self.ordered_node_uids(parent_node_id=group_node.id),
            [str(existing.conversation.uid), str(source.conversation.uid)],
        )

    def test_move_without_anchor_places_node_at_container_start(self):
        group = self.create_group(user=self.user)
        group_node = self.service.create_node(group=group)
        existing = self.create_conversation_node(title="existing", parent_node=group_node)
        source = self.create_conversation_node(title="source")

        self.service.move(
            source_node_type=SidebarNodeType.CONVERSATION,
            source_node_uid=str(source.conversation.uid),
            target_node_type=SidebarNodeType.GROUP,
            target_node_uid=str(group.uid),
        )

        self.assertEqual(
            self.ordered_node_uids(parent_node_id=group_node.id),
            [str(source.conversation.uid), str(existing.conversation.uid)],
        )

    def test_move_to_itself_and_repeated_move_to_start_are_idempotent(self):
        first = self.create_conversation_node(title="first")
        latest = self.create_conversation_node(title="latest")
        original_order = self.ordered_node_uids()

        self.service.move(
            source_node_type=SidebarNodeType.CONVERSATION,
            source_node_uid=str(first.conversation.uid),
            before_node_type=SidebarNodeType.CONVERSATION,
            before_node_uid=str(first.conversation.uid),
        )
        self.service.move(
            source_node_type=SidebarNodeType.CONVERSATION,
            source_node_uid=str(latest.conversation.uid),
        )

        self.assertEqual(self.ordered_node_uids(), original_order)
        self.assertEqual(self.positions(user=self.user), [2, 1])

    def test_move_to_itself_does_not_normalize_existing_positions(self):
        first = self.create_conversation_node(title="first")
        second = self.create_conversation_node(title="second")
        ConversationSidebarNode.objects.filter(id__in=[first.id, second.id]).update(
            position=9,
            updated_by=self.user,
        )

        self.service.move(
            source_node_type=SidebarNodeType.CONVERSATION,
            source_node_uid=str(first.conversation.uid),
            before_node_type=SidebarNodeType.CONVERSATION,
            before_node_uid=str(first.conversation.uid),
        )

        self.assertEqual(self.positions(user=self.user), [9, 9])

    def test_move_only_updates_nodes_between_source_and_anchor(self):
        first = self.create_conversation_node(title="first")
        anchor = self.create_conversation_node(title="anchor")
        middle = self.create_conversation_node(title="middle")
        source = self.create_conversation_node(title="source")
        ConversationSidebarNode.objects.filter(id=first.id).update(position=100)
        ConversationSidebarNode.objects.filter(id=anchor.id).update(position=80)
        ConversationSidebarNode.objects.filter(id=middle.id).update(position=60)
        ConversationSidebarNode.objects.filter(id=source.id).update(position=40)

        self.service.move(
            source_node_type=SidebarNodeType.CONVERSATION,
            source_node_uid=str(source.conversation.uid),
            before_node_type=SidebarNodeType.CONVERSATION,
            before_node_uid=str(anchor.conversation.uid),
        )

        first.refresh_from_db()
        anchor.refresh_from_db()
        middle.refresh_from_db()
        source.refresh_from_db()
        self.assertEqual(first.position, 100)
        self.assertEqual(source.position, 81)
        self.assertEqual(anchor.position, 80)
        self.assertEqual(middle.position, 60)

    def test_move_to_later_anchor_does_not_update_nodes_after_anchor(self):
        source = self.create_conversation_node(title="source")
        middle = self.create_conversation_node(title="middle")
        anchor = self.create_conversation_node(title="anchor")
        tail = self.create_conversation_node(title="tail")
        ConversationSidebarNode.objects.filter(id=source.id).update(position=100)
        ConversationSidebarNode.objects.filter(id=middle.id).update(position=80)
        ConversationSidebarNode.objects.filter(id=anchor.id).update(position=60)
        ConversationSidebarNode.objects.filter(id=tail.id).update(position=40)

        self.service.move(
            source_node_type=SidebarNodeType.CONVERSATION,
            source_node_uid=str(source.conversation.uid),
            before_node_type=SidebarNodeType.CONVERSATION,
            before_node_uid=str(anchor.conversation.uid),
        )

        source.refresh_from_db()
        middle.refresh_from_db()
        anchor.refresh_from_db()
        tail.refresh_from_db()
        self.assertEqual(middle.position, 80)
        self.assertEqual(source.position, 61)
        self.assertEqual(anchor.position, 60)
        self.assertEqual(tail.position, 40)

    def test_move_with_duplicate_positions_uses_stable_id_order(self):
        anchor = self.create_conversation_node(title="anchor")
        middle = self.create_conversation_node(title="middle")
        source = self.create_conversation_node(title="source")
        ConversationSidebarNode.objects.filter(id__in=[anchor.id, middle.id, source.id]).update(position=9)

        # 即使三个节点 position 相同，也必须把 source 精确移动到 anchor 前。
        moved = self.service.move(
            source_node_type=SidebarNodeType.CONVERSATION,
            source_node_uid=str(source.conversation.uid),
            before_node_type=SidebarNodeType.CONVERSATION,
            before_node_uid=str(anchor.conversation.uid),
        )
        self.assertEqual(moved.position, 10)
        self.assertEqual(
            self.ordered_node_uids(),
            [str(middle.conversation.uid), str(source.conversation.uid), str(anchor.conversation.uid)],
        )

        # 较旧的 anchor 再移到 source 前时，继续保持稳定相对顺序。
        moved = self.service.move(
            source_node_type=SidebarNodeType.CONVERSATION,
            source_node_uid=str(anchor.conversation.uid),
            before_node_type=SidebarNodeType.CONVERSATION,
            before_node_uid=str(source.conversation.uid),
        )
        self.assertEqual(moved.position, 11)
        self.assertEqual(
            self.ordered_node_uids(),
            [str(middle.conversation.uid), str(anchor.conversation.uid), str(source.conversation.uid)],
        )

    def test_move_across_containers_before_anchor_with_duplicate_position(self):
        group = self.create_group(user=self.user)
        group_node = self.service.create_node(group=group)
        anchor = self.create_conversation_node(title="anchor", parent_node=group_node)
        duplicate = self.create_conversation_node(title="duplicate", parent_node=group_node)
        prefix = self.create_conversation_node(title="prefix", parent_node=group_node)
        source = self.create_conversation_node(title="source")
        ConversationSidebarNode.objects.filter(id__in=[anchor.id, duplicate.id]).update(position=9)
        ConversationSidebarNode.objects.filter(id=prefix.id).update(position=10)

        self.service.move(
            source_node_type=SidebarNodeType.CONVERSATION,
            source_node_uid=str(source.conversation.uid),
            target_node_type=SidebarNodeType.GROUP,
            target_node_uid=str(group.uid),
            before_node_type=SidebarNodeType.CONVERSATION,
            before_node_uid=str(anchor.conversation.uid),
        )

        self.assertEqual(
            self.ordered_node_uids(parent_node_id=group_node.id),
            [
                str(prefix.conversation.uid),
                str(duplicate.conversation.uid),
                str(source.conversation.uid),
                str(anchor.conversation.uid),
            ],
        )

    def test_sidebar_serialization_does_not_issue_per_node_queries(self):
        for index in range(5):
            group = self.create_group(user=self.user, name=f"group-{index}")
            group_node = self.service.create_node(group=group)
            self.create_conversation_node(title=f"conversation-{index}", parent_node=group_node)

        with self.assertNumQueries(1):
            data = SidebarNodeResponseSerializer(
                self.service.list_nodes(),
                many=True,
            ).data

        self.assertEqual(len(data), 5)

    def test_pinned_and_search_serialization_do_not_issue_per_node_queries(self):
        group = self.create_group(user=self.user)
        group_node = self.service.create_node(group=group)
        for index in range(5):
            node = self.create_conversation_node(title=f"Audit {index}", parent_node=group_node)
            self.service.set_pinned(
                conversation_uid=str(node.conversation.uid),
                is_pinned=True,
            )

        with self.assertNumQueries(1):
            pinned_data = SidebarNodeResponseSerializer(
                self.service.list_pinned(),
                many=True,
            ).data
        with self.assertNumQueries(1):
            search_data = ConversationSearchResponseSerializer(
                self.service.search_conversations(keyword="Audit"),
                many=True,
            ).data

        self.assertEqual(len(pinned_data), 5)
        self.assertEqual(len(search_data), 5)

    def test_move_rejects_cross_user_invalid_anchor_and_pinned_nodes(self):
        source = self.create_conversation_node(title="source")
        anchor = self.create_conversation_node(title="anchor")
        other = self.create_conversation(user=self.other_user)
        self.other_service.create_node(conversation=other)

        with self.assertRaises(SidebarNodeNotFound):
            self.service.move(
                source_node_type=SidebarNodeType.CONVERSATION,
                source_node_uid=str(other.uid),
            )

        group = self.create_group(user=self.user)
        self.service.create_node(group=group)
        with self.assertRaises(InvalidSidebarAnchor):
            self.service.move(
                source_node_type=SidebarNodeType.CONVERSATION,
                source_node_uid=str(source.conversation.uid),
                target_node_type=SidebarNodeType.GROUP,
                target_node_uid=str(group.uid),
                before_node_type=SidebarNodeType.CONVERSATION,
                before_node_uid=str(anchor.conversation.uid),
            )

        self.service.set_pinned(
            conversation_uid=str(source.conversation.uid),
            is_pinned=True,
        )
        with self.assertRaises(SidebarNodeNotMovable):
            self.service.move(
                source_node_type=SidebarNodeType.CONVERSATION,
                source_node_uid=str(source.conversation.uid),
            )
        with self.assertRaises(InvalidSidebarAnchor):
            self.service.move(
                source_node_type=SidebarNodeType.CONVERSATION,
                source_node_uid=str(anchor.conversation.uid),
                before_node_type=SidebarNodeType.CONVERSATION,
                before_node_uid=str(source.conversation.uid),
            )

    def test_pin_is_idempotent_and_unpin_keeps_container_position(self):
        first = self.create_conversation_node(title="first")
        second = self.create_conversation_node(title="second")

        pinned = self.service.set_pinned(
            conversation_uid=str(first.conversation.uid),
            is_pinned=True,
        )
        pinned_at = pinned.pinned_at
        self.assertEqual(pinned.updated_by, self.user)
        repeated = self.service.set_pinned(
            conversation_uid=str(first.conversation.uid),
            is_pinned=True,
        )

        self.assertEqual(repeated.pinned_at, pinned_at)
        self.assertEqual(
            list(self.service.list_pinned().values_list("id", flat=True)),
            [first.id],
        )
        self.assertEqual(
            list(self.service.list_nodes().values_list("id", flat=True)),
            [second.id],
        )

        unpinned = self.service.set_pinned(
            conversation_uid=str(first.conversation.uid),
            is_pinned=False,
        )
        self.assertIsNone(unpinned.pinned_at)
        self.assertEqual(unpinned.position, first.position)
        self.assertEqual(unpinned.updated_by, self.user)
        self.assertEqual(
            list(self.service.list_nodes().values_list("id", flat=True)),
            [second.id, first.id],
        )

    def test_pin_does_not_use_explicit_row_locks(self):
        node = self.create_conversation_node(title="lock scope")

        with CaptureQueriesContext(connection) as captured:
            self.service.set_pinned(
                conversation_uid=str(node.conversation.uid),
                is_pinned=True,
            )

        lock_queries = [query["sql"] for query in captured.captured_queries if "FOR UPDATE" in query["sql"].upper()]
        self.assertEqual(lock_queries, [])

    def test_list_nodes_and_search_are_scoped_and_stably_ordered(self):
        group = self.create_group(user=self.user)
        group_node = self.service.create_node(group=group)
        grouped = self.create_conversation_node(title="Audit grouped", parent_node=group_node)
        root = self.create_conversation_node(title="Audit root")
        other = self.create_conversation(user=self.other_user, title="Audit other")
        self.other_service.create_node(conversation=other)

        root_nodes = list(self.service.list_nodes())
        group_nodes = list(self.service.list_nodes(parent_group_uid=str(group.uid)))
        search_results = list(self.service.search_conversations(keyword="audit"))

        self.assertEqual([node.id for node in root_nodes], [root.id, group_node.id])
        self.assertEqual([node.id for node in group_nodes], [grouped.id])
        self.assertEqual(
            {conversation.id for conversation in search_results}, {root.conversation_id, grouped.conversation_id}
        )

        root.conversation.is_deleted = True
        root.conversation.save(update_fields=["is_deleted"])
        self.assertEqual(
            list(self.service.search_conversations(keyword="audit")),
            [grouped.conversation],
        )

    def test_group_counts_include_pinned_but_distinguish_regular_conversations(self):
        group = self.create_group(user=self.user)
        group_node = self.service.create_node(group=group)
        regular = self.create_conversation_node(title="regular", parent_node=group_node)
        pinned = self.create_conversation_node(title="pinned", parent_node=group_node)
        self.service.set_pinned(
            conversation_uid=str(pinned.conversation.uid),
            is_pinned=True,
        )

        listed_group = self.service.list_nodes().get(id=group_node.id)

        self.assertEqual(listed_group.conversation_count, 2)
        self.assertEqual(listed_group.unpinned_conversation_count, 1)
        self.assertEqual(
            list(
                self.service.list_nodes(
                    parent_group_uid=str(group.uid),
                ).values_list("id", flat=True)
            ),
            [regular.id],
        )

    def test_group_counts_ignore_malformed_cross_user_children(self):
        group = self.create_group(user=self.user)
        group_node = self.service.create_node(group=group)
        owned = self.create_conversation_node(title="owned", parent_node=group_node)
        foreign = self.create_conversation(user=self.other_user, title="foreign")
        self.create_raw_node(
            user=self.other_user,
            conversation=foreign,
            parent_node=group_node,
            position=2,
        )

        listed_group = self.service.list_nodes().get(id=group_node.id)

        self.assertEqual(listed_group.conversation_count, 1)
        self.assertEqual(listed_group.unpinned_conversation_count, 1)
        self.assertEqual(owned.created_by, self.user)

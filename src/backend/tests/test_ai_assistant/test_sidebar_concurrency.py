import threading
from unittest import mock

from django.db import close_old_connections
from django.test import TransactionTestCase

from services.web.ai_assistant.constants import SidebarNodeType
from services.web.ai_assistant.models import Conversation, ConversationSidebarNode
from services.web.ai_assistant.services import ConversationSidebarService


class ConversationSidebarConcurrencyTest(TransactionTestCase):
    """使用独立数据库连接验证 MySQL 真实行锁，避免普通 TestCase 外层事务掩盖问题。"""

    # 仅 flush 本模块表，避免清除其他应用由数据迁移写入的全局初始数据。
    available_apps = ["services.web.ai_assistant"]
    reset_sequences = True

    def setUp(self):
        self.user = "concurrent-user"
        self.service = ConversationSidebarService(user=self.user)

    def create_conversation(self, title: str, user: str | None = None) -> Conversation:
        user = user or self.user
        return Conversation.objects.create(
            title=title,
            created_by=user,
            updated_by=user,
        )

    @staticmethod
    def run_threads(*targets):
        errors = []

        def run(target):
            close_old_connections()
            try:
                target()
            except Exception as error:  # noqa: BLE001 - 测试需要保留线程中的原始数据库异常
                errors.append(error)
            finally:
                close_old_connections()

        threads = [threading.Thread(target=run, args=(target,)) for target in targets]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        return threads, errors

    def test_first_conversations_can_create_nodes_concurrently(self):
        first = self.create_conversation("first")
        second = self.create_conversation("second")
        barrier = threading.Barrier(2)
        original_full_clean = ConversationSidebarNode.full_clean

        def synchronized_full_clean(node, *args, **kwargs):
            # 两事务读取相同的空容器后同时插入，验证实现不依赖空范围 gap lock 串行化。
            barrier.wait(timeout=5)
            return original_full_clean(node, *args, **kwargs)

        with mock.patch.object(ConversationSidebarNode, "full_clean", synchronized_full_clean):
            threads, errors = self.run_threads(
                lambda: ConversationSidebarService(user=self.user).create_node(conversation=first),
                lambda: ConversationSidebarService(user=self.user).create_node(conversation=second),
            )

        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(errors, [])
        self.assertEqual(
            ConversationSidebarNode.objects.filter(created_by=self.user).count(),
            2,
        )

    def test_different_users_can_create_first_nodes_concurrently(self):
        first_user = "concurrent-a"
        second_user = "concurrent-b"
        first = self.create_conversation("first", first_user)
        second = self.create_conversation("second", second_user)
        barrier = threading.Barrier(2)
        original_full_clean = ConversationSidebarNode.full_clean

        def synchronized_full_clean(node, *args, **kwargs):
            barrier.wait(timeout=5)
            return original_full_clean(node, *args, **kwargs)

        with mock.patch.object(ConversationSidebarNode, "full_clean", synchronized_full_clean):
            threads, errors = self.run_threads(
                lambda: ConversationSidebarService(user=first_user).create_node(conversation=first),
                lambda: ConversationSidebarService(user=second_user).create_node(conversation=second),
            )

        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(errors, [])
        self.assertEqual(
            set(ConversationSidebarNode.objects.values_list("created_by", flat=True)),
            {first_user, second_user},
        )

    def test_inverse_moves_lock_nodes_in_stable_order(self):
        first = self.create_conversation("first")
        second = self.create_conversation("second")
        first_node = self.service.create_node(conversation=first)
        second_node = self.service.create_node(conversation=second)
        barrier = threading.Barrier(2)
        original_resolve_target_parent = ConversationSidebarService._resolve_target_parent

        def synchronized_resolve_target_parent(service, **kwargs):
            result = original_resolve_target_parent(service, **kwargs)
            # 两事务先解析相反的 source/anchor，再验证平台按主键统一顺序加锁。
            barrier.wait(timeout=5)
            return result

        with mock.patch.object(
            ConversationSidebarService,
            "_resolve_target_parent",
            synchronized_resolve_target_parent,
        ):
            threads, errors = self.run_threads(
                lambda: ConversationSidebarService(user=self.user).move(
                    source_node_type=SidebarNodeType.CONVERSATION,
                    source_node_uid=str(first.uid),
                    before_node_type=SidebarNodeType.CONVERSATION,
                    before_node_uid=str(second.uid),
                ),
                lambda: ConversationSidebarService(user=self.user).move(
                    source_node_type=SidebarNodeType.CONVERSATION,
                    source_node_uid=str(second.uid),
                    before_node_type=SidebarNodeType.CONVERSATION,
                    before_node_uid=str(first.uid),
                ),
            )

        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(errors, [])
        self.assertEqual(
            set(ConversationSidebarNode.objects.filter(created_by=self.user).values_list("id", flat=True)),
            {first_node.id, second_node.id},
        )

    def test_crossed_move_ranges_retry_after_database_deadlock(self):
        first = self.create_conversation("first")
        second = self.create_conversation("second")
        third = self.create_conversation("third")
        fourth = self.create_conversation("fourth")
        nodes = [self.service.create_node(conversation=conversation) for conversation in (first, second, third, fourth)]
        barrier = threading.Barrier(2)
        barrier_calls = 0
        barrier_calls_lock = threading.Lock()
        original_lock_move_nodes = ConversationSidebarService._lock_move_nodes

        def synchronized_lock_move_nodes(service, **kwargs):
            nonlocal barrier_calls
            result = original_lock_move_nodes(service, **kwargs)
            with barrier_calls_lock:
                barrier_calls += 1
                current_call = barrier_calls
            # 只同步首次两笔事务；发生死锁后的整事务重试不能再次等待已经结束的对端。
            if current_call <= 2:
                barrier.wait(timeout=5)
            return result

        with mock.patch.object(
            ConversationSidebarService,
            "_lock_move_nodes",
            synchronized_lock_move_nodes,
        ):
            threads, errors = self.run_threads(
                lambda: ConversationSidebarService(user=self.user).move(
                    source_node_type=SidebarNodeType.CONVERSATION,
                    source_node_uid=str(first.uid),
                    before_node_type=SidebarNodeType.CONVERSATION,
                    before_node_uid=str(third.uid),
                ),
                lambda: ConversationSidebarService(user=self.user).move(
                    source_node_type=SidebarNodeType.CONVERSATION,
                    source_node_uid=str(fourth.uid),
                    before_node_type=SidebarNodeType.CONVERSATION,
                    before_node_uid=str(second.uid),
                ),
            )

        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(errors, [])
        self.assertGreaterEqual(barrier_calls, 3)
        self.assertEqual(
            set(ConversationSidebarNode.objects.filter(created_by=self.user).values_list("id", flat=True)),
            {node.id for node in nodes},
        )

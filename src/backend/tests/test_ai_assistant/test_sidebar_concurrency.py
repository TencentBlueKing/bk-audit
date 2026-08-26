import threading
import time
from unittest import mock

from django.db import OperationalError, close_old_connections, connection
from django.db.models import QuerySet
from django.test import TransactionTestCase

from services.web.ai_assistant.constants import MessageType, SidebarNodeType
from services.web.ai_assistant.exceptions import (
    ConversationGroupNotFound,
    InvalidParentMessage,
    SidebarNodeNotFound,
    SidebarNodeNotMovable,
)
from services.web.ai_assistant.handlers import message_handler_registry
from services.web.ai_assistant.models import (
    Conversation,
    ConversationSidebarNode,
    Message,
)
from services.web.ai_assistant.services import (
    ConversationService,
    ConversationSidebarService,
    MessageService,
)
from tests.test_ai_assistant.handlers import EchoSyncHandler


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

    def test_group_delete_and_move_share_parent_node_lock(self):
        conversation_service = ConversationService(user=self.user)
        group = conversation_service.create_group(name="deleted")
        inside = self.create_conversation("inside")
        outside = self.create_conversation("outside")
        self.service.create_node(conversation=inside)
        outside_node = self.service.create_node(conversation=outside)
        self.service.move(
            source_node_type=SidebarNodeType.CONVERSATION,
            source_node_uid=str(inside.uid),
            target_node_type=SidebarNodeType.GROUP,
            target_node_uid=str(group.uid),
        )

        delete_paused = threading.Event()
        release_delete = threading.Event()
        move_finished = threading.Event()
        errors = []
        original_delete_batches = ConversationService._delete_nodes_in_batches

        def pause_before_node_delete(queryset):
            # 会话已软删除但事务尚未提交；此时删除方必须仍持有 Group Node 锁。
            delete_paused.set()
            release_delete.wait(timeout=5)
            original_delete_batches(queryset)

        def delete_group():
            close_old_connections()
            try:
                ConversationService(user=self.user).delete_group(group_uid=str(group.uid))
            except Exception as error:  # noqa: BLE001 - 保留并发线程原始异常
                errors.append(error)
            finally:
                close_old_connections()

        def move_into_group():
            close_old_connections()
            try:
                ConversationSidebarService(user=self.user).move(
                    source_node_type=SidebarNodeType.CONVERSATION,
                    source_node_uid=str(outside.uid),
                    target_node_type=SidebarNodeType.GROUP,
                    target_node_uid=str(group.uid),
                )
            except Exception as error:  # noqa: BLE001 - 删除获胜后目标分组应失效
                errors.append(error)
            finally:
                move_finished.set()
                close_old_connections()

        with mock.patch.object(ConversationService, "_delete_nodes_in_batches", side_effect=pause_before_node_delete):
            delete_thread = threading.Thread(target=delete_group)
            delete_thread.start()
            self.assertTrue(delete_paused.wait(timeout=5))

            move_thread = threading.Thread(target=move_into_group)
            move_thread.start()
            time.sleep(0.2)
            self.assertFalse(move_finished.is_set())
            release_delete.set()
            delete_thread.join(timeout=10)
            move_thread.join(timeout=10)

        self.assertFalse(delete_thread.is_alive())
        self.assertFalse(move_thread.is_alive())
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], ConversationGroupNotFound)
        outside.refresh_from_db()
        outside_node.refresh_from_db()
        self.assertFalse(outside.is_deleted)
        self.assertIsNone(outside_node.parent_node_id)

    def test_group_delete_and_move_out_converge_with_reverse_node_id_order(self):
        conversation_service = ConversationService(user=self.user)
        inside = self.create_conversation("inside")
        inside_node = self.service.create_node(conversation=inside)
        group = conversation_service.create_group(name="deleted")
        group_node = ConversationSidebarNode.objects.get(group=group)
        self.assertLess(inside_node.id, group_node.id)
        self.service.move(
            source_node_type=SidebarNodeType.CONVERSATION,
            source_node_uid=str(inside.uid),
            target_node_type=SidebarNodeType.GROUP,
            target_node_uid=str(group.uid),
        )

        source_locked = threading.Event()
        group_locked = threading.Event()
        source_observed_group_lock = []
        group_observed_source_lock = []
        outcomes = {}
        original_lock_node = ConversationSidebarService._lock_node
        original_queryset_first = QuerySet.first

        def pause_after_source_lock(service, *, node_id):
            node = original_lock_node(service, node_id=node_id)
            if node_id == inside_node.id and not source_locked.is_set():
                source_locked.set()
                source_observed_group_lock.append(group_locked.wait(timeout=5))
            return node

        def pause_after_group_node_lock(queryset):
            node = original_queryset_first(queryset)
            if threading.current_thread().name == "delete-group" and queryset.model is ConversationSidebarNode:
                group_locked.set()
                group_observed_source_lock.append(source_locked.wait(timeout=5))
            return node

        def move_out():
            close_old_connections()
            try:
                ConversationSidebarService(user=self.user).move(
                    source_node_type=SidebarNodeType.CONVERSATION,
                    source_node_uid=str(inside.uid),
                )
                outcomes["move"] = "success"
            except Exception as error:  # noqa: BLE001 - 断言并发收敛后的领域结果
                outcomes["move"] = error
            finally:
                close_old_connections()

        def delete_group():
            close_old_connections()
            try:
                ConversationService(user=self.user).delete_group(group_uid=str(group.uid))
                outcomes["delete"] = "success"
            except Exception as error:  # noqa: BLE001 - 禁止向调用方泄漏数据库死锁
                outcomes["delete"] = error
            finally:
                close_old_connections()

        with (
            mock.patch.object(ConversationSidebarService, "_lock_node", pause_after_source_lock),
            mock.patch.object(QuerySet, "first", pause_after_group_node_lock),
        ):
            delete_thread = threading.Thread(target=delete_group, name="delete-group")
            delete_thread.start()
            self.assertTrue(group_locked.wait(timeout=5))
            move_thread = threading.Thread(target=move_out)
            move_thread.start()
            self.assertTrue(source_locked.wait(timeout=5))
            move_thread.join(timeout=10)
            delete_thread.join(timeout=10)

        self.assertFalse(move_thread.is_alive())
        self.assertFalse(delete_thread.is_alive())
        self.assertEqual(source_observed_group_lock, [True])
        self.assertEqual(group_observed_source_lock, [True])
        self.assertEqual(set(outcomes), {"move", "delete"})
        self.assertIn("success", outcomes.values())
        for outcome in outcomes.values():
            self.assertNotIsInstance(outcome, OperationalError)
            if isinstance(outcome, Exception):
                self.assertIsInstance(
                    outcome,
                    (ConversationGroupNotFound, SidebarNodeNotFound, SidebarNodeNotMovable),
                )

        active_conversation_exists = Conversation.objects.filter(id=inside.id).exists()
        node = ConversationSidebarNode.objects.filter(conversation_id=inside.id).first()
        self.assertEqual(node is not None, active_conversation_exists)
        if node is not None:
            self.assertIsNone(node.parent_node_id)

    def test_clear_empty_sidebar_and_first_conversation_creation_converge(self):
        clear_reached_empty_node_delete = threading.Event()
        release_clear = threading.Event()
        create_started = threading.Event()
        create_finished = threading.Event()
        outcomes = {}
        original_delete_batches = ConversationService._delete_nodes_in_batches

        def pause_empty_node_delete(queryset):
            clear_reached_empty_node_delete.set()
            release_clear.wait(timeout=5)
            original_delete_batches(queryset)

        def clear_conversations():
            close_old_connections()
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED")
                ConversationService(user=self.user).clear_conversations()
                outcomes["clear"] = "success"
            except Exception as error:  # noqa: BLE001 - 并发测试保留原始数据库异常
                outcomes["clear"] = error
            finally:
                close_old_connections()

        def create_first_conversation():
            close_old_connections()
            create_started.set()
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED")
                result = ConversationService(user=self.user).create_conversation(title="first")
                outcomes["create"] = result.conversation.id
            except Exception as error:  # noqa: BLE001 - 并发测试保留原始数据库异常
                outcomes["create"] = error
            finally:
                create_finished.set()
                close_old_connections()

        with mock.patch.object(
            ConversationService,
            "_delete_nodes_in_batches",
            side_effect=pause_empty_node_delete,
        ):
            clear_thread = threading.Thread(target=clear_conversations)
            clear_thread.start()
            self.assertTrue(clear_reached_empty_node_delete.wait(timeout=5))

            create_thread = threading.Thread(target=create_first_conversation)
            create_thread.start()
            self.assertTrue(create_started.wait(timeout=5))
            # READ COMMITTED 下空范围不应阻塞新建；确保新会话已提交后再让 clear
            # 继续执行 Node 删除，稳定复现删除范围未绑定初始会话集合的问题。
            self.assertTrue(create_finished.wait(timeout=5))
            release_clear.set()
            clear_thread.join(timeout=10)
            create_thread.join(timeout=10)

        self.assertFalse(clear_thread.is_alive())
        self.assertFalse(create_thread.is_alive())
        self.assertEqual(outcomes["clear"], "success")
        self.assertIsInstance(outcomes["create"], int)
        active_conversations = Conversation.objects.filter(created_by=self.user)
        nodes = ConversationSidebarNode.objects.filter(created_by=self.user)
        self.assertEqual(active_conversations.count(), 1)
        self.assertEqual(nodes.count(), 1)
        self.assertEqual(nodes.get().conversation_id, active_conversations.get().id)

    def test_message_write_rechecks_conversation_after_delete(self):
        handler = EchoSyncHandler()
        message_handler_registry.register(handler)
        conversation = self.create_conversation("conversation")
        self.service.create_node(conversation=conversation)
        write_paused = threading.Event()
        release_write = threading.Event()
        errors = []
        original_lock = MessageService._lock_active_conversation

        def pause_before_lock(service, *, conversation):
            write_paused.set()
            release_write.wait(timeout=5)
            return original_lock(service, conversation=conversation)

        def create_message():
            close_old_connections()
            try:
                MessageService(user=self.user).create(
                    conversation=conversation,
                    message_type=MessageType.SYSTEM_SELECTION,
                    input_data={"text": "hello"},
                )
            except Exception as error:  # noqa: BLE001 - 线程中断言领域异常
                errors.append(error)
            finally:
                close_old_connections()

        try:
            with mock.patch.object(MessageService, "_lock_active_conversation", pause_before_lock):
                thread = threading.Thread(target=create_message)
                thread.start()
                self.assertTrue(write_paused.wait(timeout=5))
                ConversationService(user=self.user).delete_conversation(conversation_uid=str(conversation.uid))
                release_write.set()
                thread.join(timeout=10)
        finally:
            message_handler_registry.unregister(MessageType.SYSTEM_SELECTION)

        self.assertFalse(thread.is_alive())
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], InvalidParentMessage)
        self.assertFalse(Message.objects.filter(conversation_id=conversation.id).exists())

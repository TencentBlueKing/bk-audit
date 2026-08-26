import threading

from django.db import close_old_connections
from django.test import TransactionTestCase

from services.web.ai_assistant.constants import (
    ExecutionStatus,
    FeedbackSourceType,
    FeedbackType,
    MessageType,
)
from services.web.ai_assistant.handlers import message_handler_registry
from services.web.ai_assistant.models import Conversation, Feedback, Message
from services.web.ai_assistant.services.feedback import FeedbackService
from tests.test_ai_assistant.handlers import FeedbackEchoSyncHandler, register_test_message_handler


class FeedbackServiceConcurrencyTest(TransactionTestCase):
    """使用独立连接验证 MySQL 并发写入后的最终唯一性与线程收敛。"""

    available_apps = ["services.web.ai_assistant"]
    reset_sequences = True

    def setUp(self):
        self.user = "concurrent-user"
        self.conversation = Conversation.objects.create(created_by=self.user, updated_by=self.user)
        self.message = Message.objects.create(
            conversation=self.conversation,
            message_type=MessageType.SYSTEM_SELECTION,
            status=ExecutionStatus.SUCCESS,
            input_data={"text": "feedback"},
            context_data={"prefix": "feedback"},
            output_data={"content": "feedback"},
            created_by=self.user,
            updated_by=self.user,
        )
        register_test_message_handler(FeedbackEchoSyncHandler())

    def tearDown(self):
        message_handler_registry.unregister(MessageType.SYSTEM_SELECTION)

    @staticmethod
    def run_threads(*targets):
        errors = []

        def run(target):
            close_old_connections()
            try:
                target()
            except Exception as error:  # noqa: BLE001 - 保留线程中的原始数据库异常
                errors.append(error)
            finally:
                close_old_connections()

        threads = [threading.Thread(target=run, args=(target,)) for target in targets]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        return threads, errors

    def test_first_upserts_for_same_user_and_source_are_concurrent_safe(self):
        barrier = threading.Barrier(2)

        def upsert_once():
            # 仅对齐两个请求的起点，不依赖或断言具体的数据库竞争错误类型。
            barrier.wait(timeout=5)
            FeedbackService(user=self.user).upsert(
                source_type=FeedbackSourceType.MESSAGE,
                source_uid=str(self.message.uid),
                feedback_type=FeedbackType.LIKE,
            )

        threads, errors = self.run_threads(upsert_once, upsert_once)

        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(errors, [])
        self.assertEqual(
            Feedback.objects.filter(
                created_by=self.user,
                source_type=FeedbackSourceType.MESSAGE,
                source_id=self.message.id,
            ).count(),
            1,
        )

    def test_first_upserts_for_different_sources_do_not_block_each_other(self):
        second_message = Message.objects.create(
            conversation=self.conversation,
            message_type=MessageType.SYSTEM_SELECTION,
            status=ExecutionStatus.SUCCESS,
            input_data={"text": "second"},
            context_data={"prefix": "feedback"},
            output_data={"content": "feedback"},
            created_by=self.user,
            updated_by=self.user,
        )
        barrier = threading.Barrier(2)

        def upsert_once(message):
            barrier.wait(timeout=5)
            FeedbackService(user=self.user).upsert(
                source_type=FeedbackSourceType.MESSAGE,
                source_uid=str(message.uid),
                feedback_type=FeedbackType.LIKE,
            )

        threads, errors = self.run_threads(
            lambda: upsert_once(self.message),
            lambda: upsert_once(second_message),
        )

        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(errors, [])
        self.assertEqual(
            Feedback.objects.filter(
                created_by=self.user,
                source_type=FeedbackSourceType.MESSAGE,
                source_id__in=(self.message.id, second_message.id),
            ).count(),
            2,
        )

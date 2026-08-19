from urllib.parse import urlparse

from blueapps.core.celery import celery_app
from celery import states as celery_states
from celery._state import _apps
from django.conf import settings
from django.test import SimpleTestCase, TransactionTestCase

from services.web.ai_assistant.constants import (
    AttachmentType,
    ExecutionStatus,
    MessageType,
)
from services.web.ai_assistant.handlers import (
    attachment_handler_registry,
    message_handler_registry,
)
from services.web.ai_assistant.models import Attachment, Conversation, Message
from services.web.ai_assistant.services import AttachmentService, MessageService
from tests.test_ai_assistant import integration_handlers
from tests.test_ai_assistant.celery_integration import (
    reset_task_postrun,
    running_celery_worker,
    wait_for_snapshot,
    wait_for_task_postrun,
)
from tests.test_ai_assistant.integration_handlers import (
    INTEGRATION_QUEUE,
    RealAttachmentSuccessHandler,
    RealMessageAutoretryFailureHandler,
    RealMessageDuplicateHandler,
    RealMessageOldTaskHandler,
    RealMessageSelfRetryHandler,
    RealMessageSuccessHandler,
)


class CeleryIntegrationSettingsTest(SimpleTestCase):
    """冻结真实 Celery 测试所需的公共配置，避免只在个人配置中隐式存在。"""

    def test_celery_integration_settings_are_available(self):
        self.assertIn(urlparse(settings.CELERY_TEST_BROKER_URL).scheme, {"amqp", "amqps"})
        self.assertTrue(settings.CELERY_TEST_QUEUE_PREFIX)
        self.assertIsInstance(settings.CELERY_TEST_TASK_TIMEOUT, int)
        self.assertGreater(settings.CELERY_TEST_TASK_TIMEOUT, 0)


class CeleryWorkerContextIsolationTest(SimpleTestCase):
    """验证真实 Worker 上下文不会污染项目唯一 Celery App 的运行时状态。"""

    def test_worker_context_restores_celery_app_runtime_state(self):
        queue_name = f"{INTEGRATION_QUEUE}_isolation"
        queues = celery_app.amqp.queues
        original_queue_names = set(queues)
        original_aliases = dict(queues.aliases)
        original_consume_from = None if queues._consume_from is None else dict(queues._consume_from)
        original_registered = celery_app in _apps
        original_config = {
            "broker_url": celery_app.conf.broker_url,
            "task_always_eager": celery_app.conf.task_always_eager,
            "task_eager_propagates": celery_app.conf.task_eager_propagates,
            "task_default_queue": celery_app.conf.task_default_queue,
        }

        with running_celery_worker(queue_name=queue_name):
            self.assertIn(queue_name, queues)
            self.assertEqual(set(queues.consume_from), {queue_name})

        self.assertEqual(set(queues), original_queue_names)
        self.assertEqual(dict(queues.aliases), original_aliases)
        self.assertEqual(queues._consume_from, original_consume_from)
        self.assertEqual(celery_app in _apps, original_registered)
        self.assertEqual(
            {
                "broker_url": celery_app.conf.broker_url,
                "task_always_eager": celery_app.conf.task_always_eager,
                "task_eager_propagates": celery_app.conf.task_eager_propagates,
                "task_default_queue": celery_app.conf.task_default_queue,
            },
            original_config,
        )


class CeleryExecutionIntegrationTest(TransactionTestCase):
    """使用真实 RabbitMQ 和 Worker 验证平台服务到数据库终态的完整链路。

    使用 TransactionTestCase：Service 依赖 transaction.on_commit 投递任务，
    真实 Worker 在独立连接读取数据，必须真正提交事务而非包裹在回滚事务里。
    Worker 在整个用例类生命周期内只启动一次，直接 apply_async 的场景依赖它常驻。
    """

    # 集成任务只读写 AI 助手模型。限制 flush 范围，避免删除其他应用由数据迁移
    # 写入的全局配置，进而污染 Django test runner 中后续执行的测试。
    available_apps = ["services.web.ai_assistant"]
    reset_sequences = True

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.worker_context = running_celery_worker(queue_name=INTEGRATION_QUEUE)
        cls.worker_context.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.worker_context.__exit__(None, None, None)
        super().tearDownClass()

    def setUp(self):
        self.user = "celery-integration-user"
        self.conversation = Conversation.objects.create(created_by=self.user, updated_by=self.user)

    def tearDown(self):
        message_handler_registry.unregister(MessageType.NATURAL_LANGUAGE_SEARCH)
        attachment_handler_registry.unregister(AttachmentType.AI_ANALYSIS)

    def create_processing_message(self, *, task_id: str) -> Message:
        return Message.objects.create(
            conversation=self.conversation,
            message_type=MessageType.NATURAL_LANGUAGE_SEARCH,
            status=ExecutionStatus.PROCESSING,
            task_id=task_id,
            input_data={"text": "stale"},
            context_data={"prefix": "real"},
            output_data=None,
            created_by=self.user,
            updated_by=self.user,
        )

    def test_message_service_dispatches_real_task_and_persists_success(self):
        message_handler_registry.register(RealMessageSuccessHandler())

        message = MessageService(user=self.user).create(
            conversation=self.conversation,
            message_type=MessageType.NATURAL_LANGUAGE_SEARCH,
            input_data={"text": "query"},
        )

        self.assertEqual(message.status, ExecutionStatus.PROCESSING)
        completed = wait_for_snapshot(
            model=Message,
            instance_id=message.id,
            predicate=lambda value: value.status == ExecutionStatus.SUCCESS,
        )
        self.assertEqual(completed.task_id, message.task_id)
        self.assertEqual(completed.output_data, {"content": "real:query"})

    def test_attachment_service_dispatches_real_task_and_persists_success(self):
        attachment_handler_registry.register(RealAttachmentSuccessHandler())
        source_message = Message.objects.create(
            conversation=self.conversation,
            message_type=MessageType.LOG_SEARCH,
            status=ExecutionStatus.SUCCESS,
            input_data={"text": "source"},
            context_data={"prefix": "source"},
            output_data={"content": "source"},
            created_by=self.user,
            updated_by=self.user,
        )

        attachment = AttachmentService(user=self.user).create(
            source_message_uid=str(source_message.uid),
            attachment_type=AttachmentType.AI_ANALYSIS,
            input_data={"text": "analyse"},
        )

        self.assertEqual(attachment.status, ExecutionStatus.PROCESSING)
        completed = wait_for_snapshot(
            model=Attachment,
            instance_id=attachment.id,
            predicate=lambda value: value.status == ExecutionStatus.SUCCESS,
        )
        self.assertEqual(completed.task_id, attachment.task_id)
        self.assertEqual(completed.output_data, {"content": "real:analyse"})

    def test_self_retry_keeps_processing_and_reuses_business_task_id(self):
        integration_handlers.reset_retry_observations()
        handler = message_handler_registry.register(RealMessageSelfRetryHandler())
        message = MessageService(user=self.user).create(
            conversation=self.conversation,
            message_type=MessageType.NATURAL_LANGUAGE_SEARCH,
            input_data={"text": "retry"},
        )
        original_task_id = message.task_id

        completed = wait_for_snapshot(
            model=Message,
            instance_id=message.id,
            predicate=lambda value: value.status == ExecutionStatus.SUCCESS,
        )

        self.assertEqual(completed.task_id, original_task_id)
        self.assertEqual(completed.output_data, {"content": "retry:success"})
        self.assertEqual(
            list(integration_handlers.retry_statuses),
            [ExecutionStatus.PROCESSING, ExecutionStatus.PROCESSING],
        )
        self.assertEqual(handler.async_task.name, "tests.ai_assistant.integration.message_self_retry")

    def test_autoretry_exhaustion_marks_message_failed_once(self):
        integration_handlers.reset_retry_observations()
        message_handler_registry.register(RealMessageAutoretryFailureHandler())
        message = MessageService(user=self.user).create(
            conversation=self.conversation,
            message_type=MessageType.NATURAL_LANGUAGE_SEARCH,
            input_data={"text": "fail"},
        )

        failed = wait_for_snapshot(
            model=Message,
            instance_id=message.id,
            predicate=lambda value: value.status == ExecutionStatus.FAILED,
        )

        self.assertEqual(integration_handlers.autoretry_attempts, 2)
        self.assertTrue(failed.error_code)
        self.assertNotIn("autoretry private detail", failed.error_message or "")

    def test_old_task_id_is_ignored_before_business_execution(self):
        integration_handlers.reset_old_task_observations()
        handler = message_handler_registry.register(RealMessageOldTaskHandler())
        message = self.create_processing_message(task_id="current-task-id")

        reset_task_postrun(task_id="old-task-id")
        handler.async_task.apply_async(
            kwargs={"message_id": message.id, "task_id": "old-task-id"},
            task_id="old-task-id",
        )
        # 再投递一个合法任务作为队列栅栏；它成功时，先投递的旧任务已经被 Worker 接收处理。
        valid = self.create_processing_message(task_id="queue-fence-task-id")
        handler.async_task.apply_async(
            kwargs={"message_id": valid.id, "task_id": valid.task_id},
            task_id=valid.task_id,
        )
        wait_for_snapshot(
            model=Message,
            instance_id=valid.id,
            predicate=lambda value: value.status == ExecutionStatus.SUCCESS,
        )
        wait_for_task_postrun(task_id="old-task-id")

        message.refresh_from_db()
        self.assertEqual(message.status, ExecutionStatus.PROCESSING)
        self.assertEqual(message.task_id, "current-task-id")
        self.assertIsNone(message.output_data)
        self.assertNotIn("old-task-id", integration_handlers.old_task_execution_ids)

    def test_duplicate_delivery_allows_concurrent_execution_but_only_one_terminal_snapshot(self):
        integration_handlers.reset_duplicate_observations(parties=2)
        try:
            handler = message_handler_registry.register(RealMessageDuplicateHandler())
            message = self.create_processing_message(task_id="duplicate-task-id")
            kwargs = {"message_id": message.id, "task_id": message.task_id}

            reset_task_postrun(task_id=message.task_id)
            handler.async_task.apply_async(kwargs=kwargs, task_id=message.task_id)
            handler.async_task.apply_async(kwargs=kwargs, task_id=message.task_id)

            completed = wait_for_snapshot(
                model=Message,
                instance_id=message.id,
                predicate=lambda value: value.status == ExecutionStatus.SUCCESS,
            )
            postrun_states = wait_for_task_postrun(task_id=message.task_id, expected_count=2)

            self.assertEqual(integration_handlers.duplicate_executions, 2)
            self.assertEqual(completed.output_data, {"content": "duplicate:success"})
            self.assertCountEqual(
                postrun_states,
                [celery_states.SUCCESS, celery_states.IGNORED],
            )
        finally:
            integration_handlers.clear_duplicate_observations()

    def test_manual_retry_uses_new_task_id_and_old_task_cannot_overwrite(self):
        handler = message_handler_registry.register(RealMessageSuccessHandler())
        failed = Message.objects.create(
            conversation=self.conversation,
            message_type=MessageType.NATURAL_LANGUAGE_SEARCH,
            status=ExecutionStatus.FAILED,
            task_id="failed-old-task-id",
            input_data={"text": "retry"},
            context_data={"prefix": "real"},
            output_data=None,
            error_code="TASK_EXECUTION_FAILED",
            error_message="failed",
            created_by=self.user,
            updated_by=self.user,
        )

        retried = MessageService(user=self.user).retry(message_uid=str(failed.uid))
        self.assertNotEqual(retried.task_id, "failed-old-task-id")
        reset_task_postrun(task_id="failed-old-task-id")
        handler.async_task.apply_async(
            kwargs={"message_id": failed.id, "task_id": "failed-old-task-id"},
            task_id="failed-old-task-id",
        )

        completed = wait_for_snapshot(
            model=Message,
            instance_id=failed.id,
            predicate=lambda value: value.status == ExecutionStatus.SUCCESS,
        )
        wait_for_task_postrun(task_id="failed-old-task-id")

        self.assertEqual(completed.task_id, retried.task_id)
        self.assertEqual(completed.output_data, {"content": "real:retry"})

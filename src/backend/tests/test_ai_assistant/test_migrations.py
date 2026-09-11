"""AI 助手数据迁移回归测试。

迁移测试通过 MigrationExecutor 构造真实历史模型和数据，避免仅在最新模型上
直接调用迁移函数而遗漏字段状态、索引变更或 MySQL 兼容性问题。
"""

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class ExecutionTimestampMigrationTest(TransactionTestCase):
    """验证 0003 对历史执行快照的时间字段回填语义。"""

    available_apps = ["services.web.ai_assistant"]
    migrate_from = ("ai_assistant", "0002_alter_conversation_title")
    migrate_to = ("ai_assistant", "0003_execution_timestamps")

    def setUp(self):
        super().setUp()
        # 即使降级迁移中途失败，unittest cleanup 也会尝试恢复当前叶子 schema。
        self.addCleanup(self._migrate_to_leaf)
        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_from])
        old_apps = executor.loader.project_state([self.migrate_from]).apps

        Conversation = old_apps.get_model("ai_assistant", "Conversation")
        Message = old_apps.get_model("ai_assistant", "Message")
        Attachment = old_apps.get_model("ai_assistant", "Attachment")
        conversation = Conversation.objects.create(title="migration", created_by="alice", updated_by="alice")
        processing_message = Message.objects.create(
            conversation=conversation,
            message_type="LOG_SEARCH",
            status="PROCESSING",
            created_by="alice",
            updated_by="alice",
        )
        success_message = Message.objects.create(
            conversation=conversation,
            message_type="LOG_SEARCH",
            status="SUCCESS",
            created_by="alice",
            updated_by="alice",
        )
        processing_attachment = Attachment.objects.create(
            source_message=processing_message,
            attachment_type="AI_ANALYSIS",
            status="PROCESSING",
            created_by="alice",
            updated_by="alice",
        )
        success_attachment = Attachment.objects.create(
            source_message=success_message,
            attachment_type="AI_ANALYSIS",
            status="SUCCESS",
            created_by="alice",
            updated_by="alice",
        )
        self.object_ids = {
            "Message": {
                "processing": processing_message.id,
                "success": success_message.id,
            },
            "Attachment": {
                "processing": processing_attachment.id,
                "success": success_attachment.id,
            },
        }
        # 历史数据允许 updated_at 为空；显式写空可防止测试被模型 save 行为影响。
        Message.objects.filter(id__in=self.object_ids["Message"].values()).update(updated_at=None)
        Attachment.objects.filter(id__in=self.object_ids["Attachment"].values()).update(updated_at=None)

        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_to])
        self.apps = executor.loader.project_state([self.migrate_to]).apps

    @staticmethod
    def _migrate_to_leaf():
        """恢复到当前叶子迁移，避免本测试改变后续测试看到的数据库结构。"""

        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_null_updated_at_falls_back_to_created_at_for_processing_and_terminal_snapshots(self):
        for model_name in ("Message", "Attachment"):
            model = self.apps.get_model("ai_assistant", model_name)
            processing = model.objects.get(id=self.object_ids[model_name]["processing"])
            success = model.objects.get(id=self.object_ids[model_name]["success"])

            with self.subTest(model=model_name, status="PROCESSING"):
                self.assertEqual(processing.queued_at, processing.created_at)
                self.assertEqual(processing.last_activity_at, processing.created_at)
                self.assertIsNone(processing.finished_at)

            with self.subTest(model=model_name, status="SUCCESS"):
                self.assertIsNone(success.queued_at)
                self.assertEqual(success.last_activity_at, success.created_at)
                self.assertEqual(success.finished_at, success.created_at)

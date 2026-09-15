"""AI 助手数据迁移回归测试。

迁移测试通过 MigrationExecutor 构造真实历史模型和数据，避免仅在最新模型上
直接调用迁移函数而遗漏字段状态、索引变更或 MySQL 兼容性问题。
"""

from importlib import import_module

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class ExecutionTimestampMigrationTest(TransactionTestCase):
    """验证 0003 对历史执行快照的时间字段回填语义。"""

    # 0006 已声明 meta 迁移依赖，旧迁移用例也必须让 MigrationLoader 看见完整父节点。
    available_apps = ["services.web.ai_assistant", "apps.meta"]
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


class DefaultLogAnalysisPromptMigrationTest(TransactionTestCase):
    """验证 0006 使用历史 Meta 模型初始化非空分析标准。"""

    migrate_from = ("ai_assistant", "0005_user_column_preference")
    migrate_to = ("ai_assistant", "0006_init_log_analysis_prompt")
    meta_target = ("meta", "0025_alter_enummappingcollectionrelation_related_type")

    def setUp(self):
        super().setUp()
        self.addCleanup(self._migrate_to_leaf)
        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_from])
        old_apps = executor.loader.project_state([self.migrate_from, self.meta_target]).apps
        global_meta_config = old_apps.get_model("meta", "GlobalMetaConfig")
        global_meta_config.objects.filter(config_key="ai_assistant_log_analysis_default_prompt").delete()

        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_to])
        self.apps = executor.loader.project_state([self.migrate_to, self.meta_target]).apps

    @staticmethod
    def _migrate_to_leaf():
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_default_prompt_is_initialized_with_audit_analysis_boundaries(self):
        global_meta_config = self.apps.get_model("meta", "GlobalMetaConfig")
        prompt = global_meta_config.objects.get(
            config_level="global",
            instance_key="global",
            config_key="ai_assistant_log_analysis_default_prompt",
        ).config_value

        self.assertIn("风险与异常发现", prompt)
        self.assertIn("区分事实、推断和建议", prompt)
        self.assertIn("不得伪造", prompt)

    def test_forward_function_does_not_override_existing_prompt(self):
        """重复执行初始化逻辑时保留运营已调整的默认分析标准。"""

        migration = import_module("services.web.ai_assistant.migrations.0006_init_log_analysis_prompt")
        global_meta_config = self.apps.get_model("meta", "GlobalMetaConfig")
        config = global_meta_config.objects.get(
            config_level="global",
            instance_key="global",
            config_key="ai_assistant_log_analysis_default_prompt",
        )
        config.config_value = "运营自定义分析标准"
        config.save(update_fields=["config_value"])

        migration.init_log_analysis_prompt(self.apps, None)

        config.refresh_from_db()
        self.assertEqual(config.config_value, "运营自定义分析标准")

    def test_reverse_migration_is_noop_to_preserve_preexisting_prompt(self):
        """无法区分迁移创建与运营预置记录时，回滚不得删除同 key 配置。"""

        migration = import_module("services.web.ai_assistant.migrations.0006_init_log_analysis_prompt")

        self.assertIs(migration.Migration.operations[0].reverse_code, migration.migrations.RunPython.noop)

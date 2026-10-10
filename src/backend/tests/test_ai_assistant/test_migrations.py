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

    migrate_from = ("ai_assistant", "0002_alter_conversation_title")
    migrate_to = ("ai_assistant", "0003_execution_timestamps")
    scene_initial = ("scene", "0001_initial")

    def setUp(self):
        super().setUp()
        # 即使降级迁移中途失败，unittest cleanup 也会尝试恢复当前叶子 schema。
        self.addCleanup(self._migrate_to_leaf)
        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_from, self.scene_initial])
        old_apps = executor.loader.project_state([self.migrate_from, self.scene_initial]).apps

        Scene = old_apps.get_model("scene", "Scene")
        Scene.objects.using(connection.alias).get_or_create(scene_id=1, defaults={"name": "默认场景"})
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


class ConversationScopeMigrationTest(TransactionTestCase):
    """验证 0008 将旧会话资源和消息快照收敛到 scene:1。"""

    migrate_from = ("ai_assistant", "0007_remove_natural_language_search_message_type")
    migrate_to = ("ai_assistant", "0008_conversation_scope")
    scene_initial = ("scene", "0001_initial")

    def setUp(self):
        super().setUp()
        self.addCleanup(self._migrate_to_leaf)
        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_from, self.scene_initial])
        old_apps = executor.loader.project_state([self.migrate_from, self.scene_initial]).apps

        Scene = old_apps.get_model("scene", "Scene")
        Scene.objects.using(connection.alias).get_or_create(
            scene_id=1,
            defaults={"name": "默认场景"},
        )
        Conversation = old_apps.get_model("ai_assistant", "Conversation")
        ConversationGroup = old_apps.get_model("ai_assistant", "ConversationGroup")
        SidebarNode = old_apps.get_model("ai_assistant", "ConversationSidebarNode")
        Message = old_apps.get_model("ai_assistant", "Message")

        group = ConversationGroup.objects.create(name="旧分组", created_by="alice", updated_by="alice")
        conversation = Conversation.objects.create(title="旧会话", created_by="alice", updated_by="alice")
        group_node = SidebarNode.objects.create(
            node_type="GROUP",
            group=group,
            created_by="alice",
            updated_by="alice",
        )
        conversation_node = SidebarNode.objects.create(
            node_type="CONVERSATION",
            conversation=conversation,
            parent_node=group_node,
            created_by="alice",
            updated_by="alice",
        )
        selection = Message.objects.create(
            conversation=conversation,
            message_type="SYSTEM_SELECTION",
            input_data={"system_ids": ["bk_audit"], "scope_type": "cross_scene", "scope_id": ""},
            context_data={"username": "alice", "scope_type": "cross_scene", "scope_id": ""},
            created_by="alice",
            updated_by="alice",
        )
        intent = Message.objects.create(
            conversation=conversation,
            message_type="USER_INTENT",
            input_data={"query_text": "查询日志", "scope_type": "scene", "scope_id": "02"},
            context_data={"username": "alice", "scope_type": "scene", "scope_id": "02"},
            created_by="alice",
            updated_by="alice",
        )
        log_search = Message.objects.create(
            conversation=conversation,
            message_type="LOG_SEARCH",
            input_data={"condition": {"scope_type": "system", "scope_id": "bk_audit"}},
            context_data={"session_scope_type": "cross_scene", "session_scope_id": "", "system_id": "bk_audit"},
            created_by="alice",
            updated_by="alice",
        )
        self.object_ids = {
            "group": group.id,
            "conversation": conversation.id,
            "group_node": group_node.id,
            "conversation_node": conversation_node.id,
            "selection": selection.id,
            "intent": intent.id,
            "log_search": log_search.id,
        }

        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_to])
        self.apps = executor.loader.project_state([self.migrate_to]).apps

    def test_resources_backfill_scope_and_message_snapshots_keep_business_data(self):
        Conversation = self.apps.get_model("ai_assistant", "Conversation")
        ConversationGroup = self.apps.get_model("ai_assistant", "ConversationGroup")
        SidebarNode = self.apps.get_model("ai_assistant", "ConversationSidebarNode")
        Message = self.apps.get_model("ai_assistant", "Message")

        for model, object_id in (
            (Conversation, self.object_ids["conversation"]),
            (ConversationGroup, self.object_ids["group"]),
            (SidebarNode, self.object_ids["group_node"]),
            (SidebarNode, self.object_ids["conversation_node"]),
        ):
            with self.subTest(model=model.__name__, object_id=object_id):
                resource = model.objects.get(id=object_id)
                self.assertEqual((resource.scope_type, resource.scope_id), ("scene", "1"))

        selection = Message.objects.get(id=self.object_ids["selection"])
        intent = Message.objects.get(id=self.object_ids["intent"])
        log_search = Message.objects.get(id=self.object_ids["log_search"])
        self.assertEqual(selection.input_data, {"system_ids": ["bk_audit"]})
        self.assertEqual(intent.input_data, {"query_text": "查询日志"})
        self.assertEqual(selection.context_data, {"username": "alice", "scope_type": "scene", "scope_id": "1"})
        self.assertEqual(intent.context_data, {"username": "alice", "scope_type": "scene", "scope_id": "1"})
        self.assertEqual(
            log_search.input_data,
            {"condition": {"scope_type": "system", "scope_id": "bk_audit"}},
        )
        self.assertEqual(
            log_search.context_data,
            {"session_scope_type": "scene", "session_scope_id": "1", "system_id": "bk_audit"},
        )

    @staticmethod
    def _migrate_to_leaf():
        """恢复到当前叶子迁移，避免本测试改变后续测试看到的数据库结构。"""

        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())


class ConversationScopeMigrationGuardTest(TransactionTestCase):
    """验证有历史会话但缺少 scene:1 时迁移明确失败。"""

    migrate_from = ("ai_assistant", "0007_remove_natural_language_search_message_type")
    migrate_to = ("ai_assistant", "0008_conversation_scope")
    scene_initial = ("scene", "0001_initial")

    def test_migration_fails_when_default_scene_is_missing(self):
        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_from, self.scene_initial])
        old_apps = executor.loader.project_state([self.migrate_from, self.scene_initial]).apps
        Scene = old_apps.get_model("scene", "Scene")
        Scene.objects.filter(scene_id=1).delete()
        Conversation = old_apps.get_model("ai_assistant", "Conversation")
        conversation = Conversation.objects.create(title="旧会话", created_by="alice", updated_by="alice")
        self.conversation_id = conversation.id
        self.addCleanup(self._restore_schema)

        with self.assertRaisesRegex(RuntimeError, "scene_id=1"):
            MigrationExecutor(connection).migrate([self.migrate_to])

    def _restore_schema(self):
        """删除迁移前置数据并恢复最新 schema，避免影响其他测试。"""

        executor = MigrationExecutor(connection)
        old_apps = executor.loader.project_state([self.migrate_from, self.scene_initial]).apps
        old_apps.get_model("ai_assistant", "Conversation").objects.filter(id=self.conversation_id).delete()
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())


class ConversationScopeEmptyMigrationTest(TransactionTestCase):
    """验证全新安装无旧资源时，不依赖预先创建 scene:1。"""

    migrate_from = ("ai_assistant", "0007_remove_natural_language_search_message_type")
    migrate_to = ("ai_assistant", "0008_conversation_scope")
    scene_initial = ("scene", "0001_initial")

    def test_empty_database_does_not_require_default_scene(self):
        """空库可直接新增非空 scope 字段，由后续创建流程写入绑定。"""

        self.addCleanup(self._migrate_to_leaf)
        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_from, self.scene_initial])
        old_apps = executor.loader.project_state([self.migrate_from, self.scene_initial]).apps
        old_apps.get_model("scene", "Scene").objects.filter(scene_id=1).delete()
        for model_name in ("Conversation", "ConversationGroup", "ConversationSidebarNode", "Message"):
            self.assertFalse(old_apps.get_model("ai_assistant", model_name).objects.exists())

        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_to])
        apps = executor.loader.project_state([self.migrate_to]).apps
        self.assertFalse(apps.get_model("ai_assistant", "Conversation").objects.exists())

    @staticmethod
    def _migrate_to_leaf():
        """恢复最新 schema，避免影响其他迁移测试。"""

        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())


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

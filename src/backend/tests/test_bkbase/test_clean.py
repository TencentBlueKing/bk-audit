"""共享Clean删除顺序、规则转换与发布版本验证。"""
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase, override_settings

from services.web.bkbase import clean
from services.web.bkbase.constants import BKBASE_V4_MAX_POLLS, TaskState
from services.web.bkbase.exceptions import (
    BKBaseResourceMappingError,
    BKBaseSharedResourceProtected,
)
from services.web.databus.collector_plugin.handlers import PluginEtlHandler
from services.web.databus.constants import (
    DEFAULT_REPLICA_WRITE_STORAGE_CONFIG_KEY,
    DEFAULT_STORAGE_CONFIG_KEY,
)
from services.web.databus.models import PluginSceneChoices


@override_settings(BKBASE_API_VERSION="v4")
class CleanTests(SimpleTestCase):
    def setUp(self):
        self.context = {"version": "v4", "tenant": "tenant_a", "namespace": "audit"}
        self.ref = {"kind": "Clean", "tenant": "tenant_a", "namespace": "audit", "name": "clean_a"}

    def test_owner_and_unknown_guard_before_stop_or_delete(self):
        for role in ("owner", None):
            owner = SimpleNamespace(bkbase_v4_resources={"clean": self.ref, "clean_role": role})
            with mock.patch("services.web.bkbase.clean.api.bk_base_v4.clean_delete") as delete:
                with self.assertRaises(BKBaseSharedResourceProtected):
                    clean.delete_source_clean(self.context, owner)
                delete.assert_not_called()

    def test_explicit_delete_unblocks_failed_clean_for_polling(self):
        remote = {"spec": {"desired_status": "Stopped", "current_status": "Running"}, "status": {"phase": "Ok"}}

        def save_binding(instance, patch, **kwargs):
            instance.bkbase_v4_resources.update(patch)

        for pending_action in (None, "delete"):
            with self.subTest(pending_action=pending_action):
                owner = SimpleNamespace(
                    bkbase_v4_resources={
                        "clean": self.ref,
                        "clean_role": "existing",
                        "pending_action": pending_action,
                        "blocked": True,
                        "poll_count": BKBASE_V4_MAX_POLLS,
                        "clean_message": "previous timeout",
                    }
                )
                with mock.patch("services.web.bkbase.clean.update_owner_binding", side_effect=save_binding), mock.patch(
                    "services.web.bkbase.clean.resource_lock"
                ), mock.patch("services.web.bkbase.clean.get_resource_or_none", return_value=remote), mock.patch(
                    "services.web.bkbase.clean.api.bk_base_v4.clean_delete"
                ) as delete:
                    result = clean.delete_source_clean(self.context, owner)
                delete.assert_not_called()
                self.assertEqual(result["task_state"], TaskState.RUNNING)
                self.assertEqual(owner.bkbase_v4_resources["pending_action"], "delete")
                self.assertFalse(owner.bkbase_v4_resources["blocked"])
                self.assertEqual(owner.bkbase_v4_resources["poll_count"], 0)
                self.assertEqual(owner.bkbase_v4_resources["clean_message"], "")

    def test_inflight_delete_does_not_reset_poll_budget(self):
        owner = SimpleNamespace(
            bkbase_v4_resources={
                "clean": self.ref,
                "clean_role": "existing",
                "pending_action": "delete",
                "blocked": False,
                "poll_count": 7,
            }
        )
        remote = {"spec": {"desired_status": "Stopped", "current_status": "Running"}, "status": {"phase": "Ok"}}
        with mock.patch("services.web.bkbase.clean.update_owner_binding") as save, mock.patch(
            "services.web.bkbase.clean.resource_lock"
        ), mock.patch("services.web.bkbase.clean.get_resource_or_none", return_value=remote):
            clean.delete_source_clean(self.context, owner)
        self.assertEqual(save.call_args.args[1], {"pending_action": "delete"})

    def test_save_does_not_publish_and_does_not_mutate_input(self):
        original = {
            "kind": "Clean",
            "metadata": {"name": "clean_a"},
            "spec": {
                "config_revision": 10,
                "deploy_revision": 9,
                "rules": [],
                "desired_status": "Running",
                "untouched": True,
            },
            "status": {"phase": "Pending"},
        }
        with mock.patch("services.web.bkbase.clean.resource_lock"), mock.patch(
            "services.web.bkbase.clean.api.bk_base_v4.clean_get", return_value=original
        ), mock.patch(
            "services.web.bkbase.clean.api.bk_base_v4.clean_update",
            side_effect=lambda **kw: {"metadata": kw["metadata"], "spec": kw["spec"], "status": {"phase": "Pending"}},
        ) as update:
            result = clean.update_clean(self.context, self.ref, patch={"rules": []}, publish=False)
            payload = update.call_args.kwargs
            self.assertEqual(payload["spec"]["deploy_revision"], 9)
            self.assertGreater(payload["spec"]["config_revision"], 10)
            self.assertTrue(payload["spec"]["untouched"])
            self.assertEqual(original["spec"]["config_revision"], 10)
            self.assertIsNone(result["task_state"])

    def test_branch_fanout_and_json_assignment(self):
        config = {
            "extract": {
                "type": "fun",
                "method": "from_json",
                "result": "json_data",
                "args": [],
                "next": {
                    "type": "branch",
                    "next": [
                        {
                            "type": "assign",
                            "subtype": "assign_obj",
                            "assign": [{"key": "user", "assign_to": "user_id", "type": "string"}],
                        },
                        {
                            "type": "assign",
                            "subtype": "assign_obj",
                            "assign": [{"key": "count", "assign_to": "count", "type": "long"}],
                        },
                    ],
                },
            },
            "conf": {},
        }
        self.assertEqual(
            clean.convert_rules(config),
            [
                {"input_id": "__raw_data", "output_id": "json_data", "operator": {"type": "json_de"}},
                {
                    "input_id": "json_data",
                    "output_id": "user_id",
                    "operator": {"type": "assign", "key_index": "user", "output_type": "string"},
                },
                {
                    "input_id": "json_data",
                    "output_id": "count",
                    "operator": {"type": "assign", "key_index": "count", "output_type": "long"},
                },
            ],
        )

    def test_configure_keeps_dimension_joins_from_business_rules(self):
        rt = {**self.ref, "kind": "ResultTable", "name": "rt_a"}
        data_id = {**self.ref, "kind": "DataId", "name": "data_a"}
        owner = SimpleNamespace(processing_id=None, collector_plugin_id=7, bkbase_v4_resources={"data_id": data_id})
        joins = [
            {
                "result_table_id": "1_users",
                "join_on": [{"this_field": "username", "target_field": "id"}],
                "select": [{"field_name": "data", "type": "text", "as": "snapshot_user_info"}],
            }
        ]
        with mock.patch("services.web.bkbase.clean.get_bkbase_context", return_value=self.context), mock.patch(
            "services.web.bkbase.clean.CollectorPlugin.objects.get",
            return_value=SimpleNamespace(bkbase_v4_resources={"result_table": rt}),
        ), mock.patch("services.web.bkbase.clean.ensure_clean") as ensure:
            clean.configure_clean(
                owner,
                {"raw_data_id": 11, "result_table_name_alias": "test", "json_config": {"extract": None, "join": joins}},
            )
            self.assertEqual(ensure.call_args.kwargs["rules"]["join"], joins)


@override_settings(BKBASE_API_VERSION="v4")
class PluginStorageOrchestrationTests(SimpleTestCase):
    def setUp(self):
        self.plugin = SimpleNamespace(
            pk=1,
            namespace="audit",
            plugin_scene=PluginSceneChoices.COLLECTOR,
            collector_plugin_name_en="plugin_a",
            bkbase_v4_resources={},
            has_storage=False,
            has_replica_storage=False,
            save=mock.Mock(),
        )
        self.handler = PluginEtlHandler(plugin=self.plugin)
        self.enterContext(
            mock.patch("requests.sessions.Session.request", side_effect=AssertionError("Unexpected HTTP"))
        )
        self.enterContext(mock.patch.object(self.handler, "get_bk_data_id", return_value=11))
        self.enterContext(
            mock.patch(
                "services.web.bkbase.clean.update_owner_binding",
                side_effect=lambda owner, patch: owner.bkbase_v4_resources.update(patch),
            )
        )
        self.clean = self.enterContext(mock.patch("services.web.bkbase.clean.configure_clean"))
        self.storage = self.enterContext(mock.patch("services.web.bkbase.clean.storage_service.configure_storage"))
        self.config = {
            DEFAULT_STORAGE_CONFIG_KEY: 1,
            DEFAULT_REPLICA_WRITE_STORAGE_CONFIG_KEY: {"bkbase_cluster_id": "doris_a"},
        }
        self.enterContext(
            mock.patch(
                "services.web.databus.collector_plugin.handlers.GlobalMetaConfig.get",
                side_effect=lambda key, **kwargs: self.config[key],
            )
        )
        self.enterContext(
            mock.patch(
                "services.web.databus.collector_plugin.handlers.resource.databus.storage.storage_list",
                return_value=[{"cluster_config": {"cluster_id": 1, "custom_option": {"bkbase_cluster_id": "es_a"}}}],
            )
        )

    def test_clean_pending_does_not_configure_storage(self):
        self.clean.return_value = {"task_state": None}

        self.handler.create_or_update()

        self.storage.assert_not_called()
        self.assertFalse(self.plugin.bkbase_v4_resources["ready"])
        self.assertFalse(self.plugin.bkbase_v4_resources["blocked"])
        self.assertFalse(self.plugin.has_storage)

    def test_main_and_replica_must_both_run_before_plugin_ready(self):
        self.clean.return_value = {"task_state": TaskState.RUNNING}
        self.storage.side_effect = [
            {"task_state": TaskState.RUNNING},
            {"task_state": None},
            {"task_state": TaskState.RUNNING},
            {"task_state": TaskState.RUNNING},
        ]

        result = self.handler.create_or_update()
        self.assertFalse(self.plugin.bkbase_v4_resources["ready"])
        self.assertFalse(self.plugin.has_storage)
        self.assertFalse(self.plugin.has_replica_storage)
        self.assertIsNone(result["task_state"])

        self.handler.create_or_update()
        self.assertTrue(self.plugin.bkbase_v4_resources["ready"])
        self.assertTrue(self.plugin.has_storage)
        self.assertTrue(self.plugin.has_replica_storage)
        self.assertEqual(self.plugin.bkbase_v4_resources["poll_count"], 2)
        for main, replica in (
            (self.storage.call_args_list[0], self.storage.call_args_list[1]),
            (self.storage.call_args_list[2], self.storage.call_args_list[3]),
        ):
            self.assertEqual(main.args[1]["storage_type"], "es")
            self.assertEqual(main.args[1]["storage_cluster"], "es_a")
            self.assertEqual(main.kwargs["purpose"], "main")
            self.assertEqual(replica.args[1]["storage_type"], "doris")
            self.assertEqual(replica.args[1]["storage_cluster"], "doris_a")
            self.assertEqual(replica.kwargs["purpose"], "replica")

    def test_without_replica_configuration_only_main_is_required(self):
        self.config[DEFAULT_REPLICA_WRITE_STORAGE_CONFIG_KEY] = None
        self.clean.return_value = {"task_state": TaskState.RUNNING}
        self.storage.return_value = {"task_state": TaskState.RUNNING}

        self.handler.create_or_update()

        self.assertEqual(self.storage.call_count, 1)
        self.assertEqual(self.storage.call_args.kwargs["purpose"], "main")
        self.assertTrue(self.plugin.bkbase_v4_resources["ready"])
        self.assertTrue(self.plugin.has_storage)
        self.assertFalse(self.plugin.has_replica_storage)

    def test_main_pending_keeps_plugin_unready_when_replica_is_running(self):
        self.clean.return_value = {"task_state": TaskState.RUNNING}
        self.storage.side_effect = [
            {"task_state": None},
            {"task_state": TaskState.RUNNING},
        ]

        result = self.handler.create_or_update()

        self.assertIsNone(result["task_state"])
        self.assertFalse(self.plugin.bkbase_v4_resources["ready"])
        self.assertFalse(self.plugin.has_storage)
        self.assertFalse(self.plugin.has_replica_storage)

    def test_failed_replica_blocks_plugin_immediately(self):
        self.clean.return_value = {"task_state": TaskState.RUNNING}
        self.storage.side_effect = [
            {"task_state": TaskState.RUNNING},
            {"task_state": TaskState.FAILED, "message": "replica failed"},
        ]

        self.handler.create_or_update()

        self.assertFalse(self.plugin.bkbase_v4_resources["ready"])
        self.assertTrue(self.plugin.bkbase_v4_resources["blocked"])
        self.assertEqual(self.plugin.bkbase_v4_resources["message"], "replica failed")

    def test_failed_main_blocks_without_configuring_replica(self):
        self.clean.return_value = {"task_state": TaskState.RUNNING}
        self.storage.side_effect = [
            {"task_state": TaskState.FAILED, "message": "main failed"},
            {"task_state": TaskState.RUNNING},
        ]

        self.handler.create_or_update()

        self.assertFalse(self.plugin.bkbase_v4_resources["ready"])
        self.assertTrue(self.plugin.bkbase_v4_resources["blocked"])
        self.assertEqual(self.plugin.bkbase_v4_resources["message"], "main failed")
        self.assertEqual(self.storage.call_count, 1)

    def test_failed_main_is_not_masked_by_replica_error(self):
        self.clean.return_value = {"task_state": TaskState.RUNNING}
        self.storage.side_effect = [
            {"task_state": TaskState.FAILED, "message": "main failed"},
            BKBaseResourceMappingError(message="replica error"),
        ]

        result = self.handler.create_or_update()

        self.assertTrue(self.plugin.bkbase_v4_resources["blocked"])
        self.assertEqual(self.plugin.bkbase_v4_resources["message"], "main failed")
        self.assertEqual(result["task_state"], TaskState.FAILED)
        self.assertEqual(self.storage.call_count, 1)

    def test_failed_clean_blocks_without_configuring_storage(self):
        self.clean.return_value = {"task_state": TaskState.FAILED, "message": "clean failed"}

        self.handler.create_or_update()

        self.storage.assert_not_called()
        self.assertFalse(self.plugin.bkbase_v4_resources["ready"])
        self.assertTrue(self.plugin.bkbase_v4_resources["blocked"])
        self.assertEqual(self.plugin.bkbase_v4_resources["message"], "clean failed")

    def test_pending_operation_blocks_at_poll_limit(self):
        self.plugin.bkbase_v4_resources["poll_count"] = BKBASE_V4_MAX_POLLS - 2
        self.clean.return_value = {"task_state": None}

        self.handler.create_or_update()
        self.assertFalse(self.plugin.bkbase_v4_resources["blocked"])
        self.handler.create_or_update()
        self.assertTrue(self.plugin.bkbase_v4_resources["blocked"])
        self.assertFalse(self.plugin.bkbase_v4_resources["ready"])
        self.assertEqual(self.plugin.bkbase_v4_resources["poll_count"], BKBASE_V4_MAX_POLLS)
        self.assertIn("timed out", self.plugin.bkbase_v4_resources["message"])

    def test_success_at_poll_limit_does_not_block(self):
        self.plugin.bkbase_v4_resources["poll_count"] = BKBASE_V4_MAX_POLLS - 1
        self.clean.return_value = {"task_state": TaskState.RUNNING}
        self.storage.return_value = {"task_state": TaskState.RUNNING}

        self.handler.create_or_update()

        self.assertTrue(self.plugin.bkbase_v4_resources["ready"])
        self.assertFalse(self.plugin.bkbase_v4_resources["blocked"])

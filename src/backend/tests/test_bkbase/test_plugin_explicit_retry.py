"""真实编排与资源服务只重试锁内确认失败的步骤。"""
from contextlib import contextmanager
from copy import deepcopy
from types import SimpleNamespace
from unittest import mock

from bk_resource.exceptions import APIRequestError
from django.test import SimpleTestCase, override_settings

from services.web.bkbase import clean, storage
from services.web.bkbase.constants import CleanRole, TaskState
from services.web.databus import tasks
from services.web.databus.collector_plugin import resources as plugin_resources
from services.web.databus.constants import PluginSceneChoices


@override_settings(BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="tenant_a", BKBASE_V4_NAMESPACE="audit")
class PluginExplicitRetryTests(SimpleTestCase):
    def setUp(self):
        self.clean_ref = self.ref("Clean", "plugin_a")
        self.data_ref = self.ref("DataId", "data")
        self.rt = self.ref("ResultTable", "rt")
        self.plugin = SimpleNamespace(
            pk=1,
            collector_plugin_id=1,
            namespace="audit",
            plugin_scene=PluginSceneChoices.COLLECTOR,
            has_storage=False,
            has_replica_storage=False,
            save=mock.Mock(),
            bkbase_v4_resources={
                "blocked": True,
                "ready": False,
                "message": "original failure",
                "clean": self.clean_ref,
                "data_id": self.data_ref,
                "clean_role": CleanRole.OWNER,
                "result_table_id": "7_input",
                "result_table": self.rt,
            },
        )
        self.params = {"raw_data_id": 11, "json_config": {}}
        self.remote = {
            "clean": self.resource(
                self.clean_ref,
                {
                    "data_id": self.data_ref,
                    "raw_data_id": 11,
                    "result_table_id": "7_input",
                    "result_table_source": "new",
                    "rules": [],
                    "filter_rules": [],
                    "desired_status": "Running",
                    "current_status": "Running",
                    "config_revision": 9999999999999,
                    "deploy_revision": 9999999999999,
                },
            )
        }
        self.storage_params = {
            "main": {"storage_type": "es", "storage_cluster": "es_a"},
            "replica": {"storage_type": "doris", "storage_cluster": "doris_a"},
        }
        self.allowed_locked = set()
        self.writes = []
        self.enterContext(mock.patch.object(clean, "resource_lock", side_effect=self.lock))
        self.enterContext(mock.patch.object(storage, "resource_lock", side_effect=self.lock))
        self.enterContext(mock.patch.object(clean, "update_owner_binding", side_effect=self.save_binding))
        self.enterContext(mock.patch.object(storage, "update_owner_binding", side_effect=self.save_binding))
        self.verify_rt = self.enterContext(mock.patch.object(clean, "_verified_result_table_ref", return_value=self.rt))
        self.enterContext(
            mock.patch.object(
                clean,
                "build_clean_spec",
                return_value={
                    key: value
                    for key, value in self.remote["clean"]["spec"].items()
                    if key not in ("desired_status", "current_status", "config_revision", "deploy_revision")
                },
            )
        )
        self.enterContext(
            mock.patch.object(
                storage,
                "resolve_storage_cluster",
                side_effect=lambda *a, storage_type, **kw: self.ref(
                    "ElasticSearch" if storage_type == "es" else "Doris", storage_type
                ),
            )
        )
        for purpose, params in self.storage_params.items():
            cluster = self.ref("ElasticSearch" if purpose == "main" else "Doris", params["storage_type"])
            ref = self.ref("DataStorage", purpose)
            config = {"tableInfo": {"source": self.rt, "storage": cluster}}
            self.remote[purpose] = self.resource(ref, config)
        self.enterContext(
            mock.patch.object(
                storage, "storage_ref", side_effect=lambda *a, purpose, **kw: self.ref("DataStorage", purpose)
            )
        )
        self.enterContext(mock.patch.object(storage, "convert_storage_config", return_value={"tableInfo": {}}))
        self.enterContext(
            mock.patch.object(clean.api.bk_base_v4, "clean_get", side_effect=lambda **kw: self.get("clean"))
        )
        self.enterContext(
            mock.patch.object(storage.api.bk_base_v4, "data_storage_get", side_effect=lambda **kw: self.get(kw["name"]))
        )
        self.clean_put = self.enterContext(
            mock.patch.object(clean.api.bk_base_v4, "clean_update", side_effect=lambda **kw: self.put("clean", kw))
        )
        self.storage_put = self.enterContext(
            mock.patch.object(
                storage.api.bk_base_v4, "data_storage_update", side_effect=lambda **kw: self.put(kw["name"], kw)
            )
        )
        self.handler = SimpleNamespace(
            plugin=self.plugin,
            build_clean_config=lambda: self.params,
            build_storage_config=lambda: tuple(self.storage_params.values()),
        )

    @staticmethod
    def ref(kind, name):
        return {"kind": kind, "tenant": "tenant_a", "namespace": "audit", "name": name}

    @staticmethod
    def resource(ref, spec):
        return {
            "kind": ref["kind"],
            "metadata": {k: v for k, v in ref.items() if k != "kind"},
            "spec": spec,
            "status": {"phase": "Ok", "message": "running"},
        }

    def save_binding(self, plugin, patch, *, remove=()):
        plugin.bkbase_v4_resources.update(deepcopy(patch))
        for key in remove:
            plugin.bkbase_v4_resources.pop(key, None)

    def lock(self, context, ref):
        @contextmanager
        def locked():
            name = "clean" if ref["kind"] == "Clean" else ref["name"]
            self.allowed_locked.add(name)
            try:
                yield
            finally:
                self.allowed_locked.remove(name)

        return locked()

    def get(self, step):
        self.assertIn(step, self.allowed_locked)
        return deepcopy(self.remote[step])

    def put(self, step, payload):
        self.assertIn(step, self.allowed_locked)
        self.assertEqual(self.remote[step]["status"]["phase"], "Failed")
        self.writes.append(step)
        self.remote[step].update(spec=deepcopy(payload["spec"]), status={"phase": "Pending"})
        return deepcopy(self.remote[step])

    def phase(self, step, phase, message=""):
        self.remote[step]["status"] = {"phase": phase, "message": message}

    def test_explicit_retry_flows_from_failed_clean_through_both_storages_once(self):
        for step in self.remote:
            self.phase(step, "Failed", "old failure")
        clean.reset_plugin_operation(self.plugin)
        clean.configure_plugin(self.handler)
        self.assertEqual(self.writes, ["clean"])
        self.assertEqual(self.clean_put.call_args.kwargs["spec"]["config_revision"], 10000000000000)
        self.assertEqual(self.clean_put.call_args.kwargs["spec"]["deploy_revision"], 10000000000000)
        clean.configure_plugin(self.handler)
        self.assertEqual(self.writes, ["clean"])
        self.phase("clean", "Ok")
        clean.configure_plugin(self.handler)
        self.assertEqual(self.writes, ["clean", "main", "replica"])
        clean.configure_plugin(self.handler)
        self.assertEqual(self.writes, ["clean", "main", "replica"])
        for step in ("main", "replica"):
            self.phase(step, "Ok")
        clean.configure_plugin(self.handler)
        self.assertTrue(self.plugin.bkbase_v4_resources["ready"])

    def test_periodic_failed_resource_stops_and_keeps_evidence_without_retry(self):
        self.phase("clean", "Failed", "verified failure")
        result = clean.configure_plugin(self.handler)
        self.assertEqual(result["task_state"], TaskState.FAILED)
        self.assertEqual(self.writes, [])
        self.assertTrue(self.plugin.bkbase_v4_resources["blocked"])
        self.assertEqual(self.plugin.bkbase_v4_resources["message"], "verified failure")

    def test_clean_retry_success_ignores_old_failed_receipt_until_formal_get(self):
        self.phase("clean", "Failed", "old failure")
        self.clean_put.side_effect = lambda **payload: self.put_with_stale_failure("clean", payload)
        clean.reset_plugin_operation(self.plugin)

        result = clean.configure_plugin(self.handler)
        self.assertIsNone(result["task_state"])
        self.assertFalse(self.plugin.bkbase_v4_resources["blocked"])
        self.storage_put.assert_not_called()

        self.phase("clean", "Ok")
        clean.configure_plugin(self.handler)
        self.assertTrue(self.plugin.bkbase_v4_resources["ready"])
        self.clean_put.assert_called_once()

    def test_storage_retry_success_ignores_old_failed_receipt_until_formal_get(self):
        self.phase("replica", "Failed", "old failure")
        self.storage_put.side_effect = lambda **payload: self.put_with_stale_failure("replica", payload)
        clean.reset_plugin_operation(self.plugin)

        result = clean.configure_plugin(self.handler)
        self.assertIsNone(result["task_state"])
        self.assertFalse(self.plugin.bkbase_v4_resources["blocked"])
        clean.configure_plugin(self.handler)  # 正式 GET 尚为 Pending。
        self.assertFalse(self.plugin.bkbase_v4_resources["blocked"])

        self.phase("replica", "Failed", "new formal failure")
        result = clean.configure_plugin(self.handler)
        self.assertEqual(result["task_state"], TaskState.FAILED)
        self.assertTrue(self.plugin.bkbase_v4_resources["blocked"])
        self.assertEqual(self.plugin.bkbase_v4_resources["message"], "new formal failure")
        self.storage_put.assert_called_once()

    def put_with_stale_failure(self, step, payload):
        receipt = deepcopy(self.remote[step])
        self.put(step, payload)
        return receipt

    def test_pending_and_running_resources_are_not_written_on_explicit_retry(self):
        self.phase("main", "Pending")
        # Desired drift may exist, but pending must never be overwritten in a retry.
        self.remote["main"]["spec"]["taskFieldSetting"] = {"prior_setting": 1}
        clean.reset_plugin_operation(self.plugin)
        clean.configure_plugin(self.handler)
        self.assertEqual(self.writes, [])
        self.phase("main", "Failed", "later failure")
        clean.configure_plugin(self.handler)
        self.assertEqual(self.writes, [])
        self.assertEqual(self.plugin.bkbase_v4_resources["message"], "later failure")

    def test_timeout_does_not_resubmit_old_failed_revision_at_next_beat(self):
        self.phase("clean", "Failed", "old phase still visible")
        self.clean_put.side_effect = APIRequestError("bk_base_v4", "/clean", "unknown")
        clean.reset_plugin_operation(self.plugin)
        clean.configure_plugin(self.handler)
        clean.configure_plugin(self.handler)
        self.clean_put.assert_called_once()
        self.assertTrue(self.plugin.bkbase_v4_resources["blocked"])
        self.assertEqual(self.plugin.bkbase_v4_resources["message"], "old phase still visible")

    def test_failed_clean_may_retry_before_result_table_exists(self):
        self.plugin.bkbase_v4_resources.pop("result_table")
        self.verify_rt.side_effect = AssertionError("No formal output before Clean is running")
        self.phase("clean", "Failed", "initial publish failed")
        clean.reset_plugin_operation(self.plugin)
        clean.configure_plugin(self.handler)
        self.assertEqual(self.writes, ["clean"])
        self.verify_rt.assert_not_called()

    def test_storage_timeout_leaves_one_attempt_and_preserves_failure(self):
        self.phase("replica", "Failed", "formal replica failure")
        self.storage_put.side_effect = APIRequestError(module_name="bk_base_v4", url="/storage", result="unknown")
        clean.reset_plugin_operation(self.plugin)
        clean.configure_plugin(self.handler)
        clean.configure_plugin(self.handler)
        self.storage_put.assert_called_once()
        self.assertEqual(self.storage_put.call_args.kwargs["name"], "replica")
        self.clean_put.assert_not_called()
        self.assertTrue(self.plugin.bkbase_v4_resources["blocked"])
        self.assertEqual(self.plugin.bkbase_v4_resources["message"], "formal replica failure")

    def test_recovery_does_not_put_mismatched_storage_identity(self):
        self.phase("main", "Failed", "old failure")
        self.remote["main"]["metadata"]["namespace"] = "other"
        clean.reset_plugin_operation(self.plugin)
        self.assertIsNone(clean.configure_plugin(self.handler))
        self.storage_put.assert_not_called()
        self.assertIn("identity mismatch", self.plugin.bkbase_v4_resources["message"])

    def test_regular_targeted_configure_still_updates_a_healthy_changed_clean(self):
        self.plugin.bkbase_v4_resources["blocked"] = False
        self.remote["clean"]["spec"]["filter_rules"] = [{"prior": "rule"}]
        self.clean_put.side_effect = lambda **kwargs: {**self.remote["clean"], "status": {"phase": "Pending"}}
        clean.reset_plugin_operation(self.plugin)
        clean.configure_plugin(self.handler)
        self.clean_put.assert_called_once()
        self.assertEqual(self.clean_put.call_args.kwargs["spec"]["filter_rules"], [])
        self.storage_put.assert_not_called()

    def test_targeted_task_arms_retry_through_existing_reset_but_periodic_does_not(self):
        mocked = SimpleNamespace(create_or_update=mock.Mock())
        entry = tasks.create_or_update_plugin_etl.__wrapped__.__wrapped__
        with mock.patch.object(tasks.CollectorPlugin.objects, "filter", return_value=[self.plugin]), mock.patch.object(
            tasks, "PluginEtlHandler", return_value=mocked
        ), mock.patch.object(clean, "pending_plugins", return_value=[self.plugin]), mock.patch.object(
            clean, "reset_plugin_operation", wraps=clean.reset_plugin_operation
        ) as reset:
            entry()
            reset.assert_not_called()
            entry(1)
        reset.assert_called_once_with(self.plugin, retry_failed=None)

    def test_explicit_retry_can_check_remote_failure_when_local_ready_is_stale(self):
        self.plugin.bkbase_v4_resources.update(ready=True, blocked=False)
        self.phase("main", "Failed")
        clean.reset_plugin_operation(self.plugin, retry_failed=True)
        self.assertFalse(self.plugin.bkbase_v4_resources["ready"])
        clean.configure_plugin(self.handler)
        self.assertEqual(self.writes, ["main"])
        clean.reset_plugin_operation(self.plugin, retry_failed=True)
        self.phase("main", "Failed")
        clean.configure_plugin(self.handler)
        self.assertEqual(self.writes, ["main"])

    def test_new_downstream_create_with_unknown_outcome_is_not_repeated_by_beat(self):
        self.remote["main"] = None
        self.enterContext(mock.patch.object(storage, "normalize_physical_table_name"))
        self.handler.build_storage_config = lambda: (
            {"storage_type": "es", "storage_cluster": "es_a", "expires": 7},
            None,
        )
        create = self.enterContext(
            mock.patch.object(
                storage.api.bk_base_v4,
                "data_storage_create",
                side_effect=APIRequestError(module_name="bk_base_v4", url="/storage", result="unknown"),
            )
        )
        clean.reset_plugin_operation(self.plugin)
        clean.configure_plugin(self.handler)
        clean.configure_plugin(self.handler)
        create.assert_called_once()
        self.assertIn("unconfirmed", self.plugin.bkbase_v4_resources["message"])

    def save_from_product(self, field_path):
        """经更新资源、持久化和按 ID 的真实任务入口重放保存。"""
        plugin = self.plugin
        plugin.collector_plugin_name = "Synthetic plugin"
        plugin.collector_plugin_name_en = "synthetic_plugin"
        plugin.etl_config = "bk_log_json"
        plugin.etl_params = {"retain_original_text": True, "path": "original"}
        plugin.extra_fields = []
        storage_fields = {
            "retention": 7,
            "allocation_min_days": 0,
            "storage_replies": 1,
            "storage_shards_nums": 1,
            "storage_shards_size": 10,
        }
        vars(plugin).update(storage_fields)

        def save_config(**config):
            vars(plugin).update(deepcopy(config))
            return 1

        build_spec = clean.build_clean_spec.return_value
        clean.build_clean_spec.side_effect = lambda *args, **kwargs: {
            **build_spec,
            "filter_rules": [] if plugin.etl_params["path"] == "original" else [{"type": "new"}],
        }
        handler = SimpleNamespace(create_or_update=lambda: clean.configure_plugin(self.handler))
        entry = tasks.create_or_update_plugin_etl.__wrapped__.__wrapped__
        endpoint = plugin_resources.UpdatePluginResource()
        request = endpoint.RequestSerializer(
            data={
                "collector_plugin_id": 1,
                "namespace": "audit",
                "etl_config": "bk_log_json",
                "etl_params": {"path": field_path},
            }
        )
        request.is_valid(raise_exception=True)
        with mock.patch.object(tasks.CollectorPlugin.objects, "get", return_value=plugin), mock.patch.object(
            tasks.CollectorPlugin.objects, "filter"
        ) as plugins, mock.patch.object(tasks, "PluginEtlHandler", return_value=handler), mock.patch.object(
            endpoint, "build_in_config", return_value=storage_fields
        ), mock.patch.object(
            plugin_resources.GlobalMetaConfig, "get", return_value=1
        ), mock.patch.object(
            plugin_resources.api.bk_log, "update_collector_plugin", return_value={"collector_plugin_id": 1}
        ), mock.patch.object(
            plugin_resources.create_or_update_plugin_etl, "delay", side_effect=entry
        ) as enqueue:
            plugins.return_value.update.side_effect = save_config
            plugins.return_value.__iter__.side_effect = lambda: iter((plugin,))
            self.assertEqual(endpoint.perform_request(request.validated_data), {"collector_plugin_id": 1})
        return enqueue

    def test_product_changed_save_updates_healthy_clean_even_when_storage_failed(self):
        self.phase("main", "Failed", "storage configuration failed")
        self.plugin.bkbase_v4_resources["plugin_retry_steps"] = []
        self.clean_put.side_effect = lambda **kwargs: {
            **self.remote["clean"],
            "spec": kwargs["spec"],
            "status": {"phase": "Pending"},
        }
        self.save_from_product("updated")
        self.clean_put.assert_called_once()
        self.assertEqual(self.clean_put.call_args.kwargs["spec"]["filter_rules"], [{"type": "new"}])
        self.storage_put.assert_not_called()
        self.assertNotIn("plugin_retry_steps", self.plugin.bkbase_v4_resources)

    def test_product_same_config_save_retries_failed_storage_once_even_if_outcome_is_unknown(self):
        self.phase("replica", "Failed", "formal failure")
        self.storage_put.side_effect = APIRequestError(module_name="bk_base_v4", url="/storage", result="unknown")
        self.save_from_product("original")
        clean.configure_plugin(self.handler)
        self.clean_put.assert_not_called()
        self.storage_put.assert_called_once()
        self.assertEqual(self.storage_put.call_args.kwargs["name"], "replica")
        self.assertTrue(self.plugin.bkbase_v4_resources["blocked"])

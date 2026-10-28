"""资源异步推进、共享删除和状态超时的业务回归。"""
from copy import deepcopy
from types import SimpleNamespace
from unittest import mock

from django.test import TestCase, override_settings

from services.web.bkbase import clean, flow, source, storage
from services.web.bkbase.common import update_owner_binding
from services.web.bkbase.exceptions import BKBaseSharedResourceProtected
from services.web.databus.collector.resources import DeleteCollectorResource
from services.web.databus.constants import SourcePlatformChoices
from services.web.databus.models import CollectorConfig, Snapshot


@override_settings(BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="tenant_a", BKBASE_V4_NAMESPACE="audit")
class LifecycleTests(TestCase):
    def setUp(self):
        self.context = {"version": "v4", "tenant": "tenant_a", "namespace": "audit"}
        self.ref = {"kind": "Clean", "tenant": "tenant_a", "namespace": "audit", "name": "clean_a"}

    def test_null_default_retains_null_semantics(self):
        rules = clean.convert_rules(
            {"extract": {"type": "access", "key": "a", "result": "a", "default_type": "null", "default_value": ""}}
        )
        self.assertIsNone(rules[0]["operator"]["default"])

    def test_redis_fields_are_names_not_legacy_descriptors(self):
        params = {
            "key_fields": [{"field_name": "id", "field_type": "string"}],
            "value_fields": [{"field_name": "data"}],
        }
        result = storage.convert_storage_config(params)
        self.assertEqual(result["taskFieldSetting"], {"key_fields": ["id"], "value_fields": ["data"]})

    def test_snapshot_stop_waits_for_actual_source_stop(self):
        owner = Snapshot.objects.create(
            system_id="system_a", resource_type_id="resource_a", bkbase_data_id=10, status="running"
        )
        with mock.patch(
            "services.web.bkbase.source.stop_collector",
            return_value={"ref": {**self.ref, "kind": "DataSource"}, "task_state": "running"},
        ):
            self.assertFalse(source.stop_snapshot(owner, {}, multiple_storage=False))
        owner.refresh_from_db()
        self.assertEqual(owner.status, "running")
        self.assertEqual(owner.bkbase_v4_resources["pending_action"], "stop")

    def test_shared_clean_deletion_waits_for_remote_absence(self):
        owner = CollectorConfig.objects.create(
            source_platform=SourcePlatformChoices.BKBASE,
            system_id="system_a",
            bk_biz_id=1,
            collector_plugin_id=1,
            collector_config_id=1,
            collector_config_name="source",
            bkbase_table_id="legacy_rt",
            processing_id="legacy_clean",
            bkbase_v4_resources={"clean": self.ref, "clean_role": "existing"},
        )
        remote = {
            "metadata": {"name": "clean_a"},
            "spec": {"current_status": "Running", "desired_status": "Running"},
            "status": {"phase": "Ok"},
        }
        with mock.patch("services.web.bkbase.clean.resource_lock"), mock.patch(
            "services.web.bkbase.clean.get_resource_or_none", side_effect=lambda *a, **kw: deepcopy(remote)
        ), mock.patch(
            "services.web.bkbase.clean.api.bk_base_v4.clean_update",
            side_effect=lambda **kw: {"metadata": kw["metadata"], "spec": kw["spec"]},
        ), mock.patch(
            "services.web.bkbase.clean.api.bk_base_v4.clean_delete"
        ) as delete:
            clean.delete_collector(owner)
            delete.assert_not_called()
            self.assertTrue(CollectorConfig.objects.filter(pk=owner.pk).exists())
            remote["spec"]["current_status"] = "Stopped"
            remote["spec"]["desired_status"] = "Stopped"
            clean.delete_collector(owner)
            delete.assert_called_once()
            self.assertTrue(CollectorConfig.objects.filter(pk=owner.pk).exists())
        with mock.patch("services.web.bkbase.clean.resource_lock"), mock.patch(
            "services.web.bkbase.clean.get_resource_or_none", return_value=None
        ):
            clean.delete_collector(owner)
        self.assertFalse(CollectorConfig.objects.filter(pk=owner.pk).exists())
        self.assertEqual((owner.processing_id, owner.bkbase_table_id), ("legacy_clean", "legacy_rt"))

    def test_binding_merge_preserves_other_writer_and_old_ids(self):
        owner = Snapshot.objects.create(
            system_id="system_a",
            resource_type_id="resource_a",
            bkbase_data_id=10,
            bkbase_v4_resources={"storages": {"main": {"name": "main"}}},
        )
        stale = Snapshot.objects.get(pk=owner.pk)
        update_owner_binding(owner, {"data_id": {"name": "data"}})
        update_owner_binding(stale, {"storages": {"replica": {"name": "replica"}}})
        owner.refresh_from_db()
        self.assertEqual(owner.bkbase_data_id, 10)
        self.assertEqual(
            owner.bkbase_v4_resources,
            {"data_id": {"name": "data"}, "storages": {"main": {"name": "main"}, "replica": {"name": "replica"}}},
        )

    def test_restart_changed_position_updates_cr_instead_of_mcp(self):
        ref = {**self.ref, "kind": "Flow"}
        strategy = SimpleNamespace(backend_data={"bkbase_v4": {"flow": ref}})
        remote = {
            "metadata": {"name": ref["name"]},
            "spec": {"nodes": [{"name": "sql"}], "operation_config": {"start_position": "continue"}},
        }
        with mock.patch("services.web.bkbase.flow.resource_lock"), mock.patch(
            "services.web.bkbase.flow._save_binding"
        ) as save, mock.patch(
            "services.web.bkbase.flow.get_rule_flow_status", return_value={"task_state": "running", "engine_flow_id": 1}
        ), mock.patch(
            "services.web.bkbase.flow.api.bk_base_v4.flow_get", return_value=remote
        ), mock.patch(
            "services.web.bkbase.flow.api.bk_base_v4.flow_update",
            side_effect=lambda **kw: {"metadata": kw["metadata"], "spec": kw["spec"]},
        ) as update, mock.patch(
            "services.web.bkbase.flow.api.bk_base_v4.flow_restart"
        ) as restart:
            flow.operate_rule_flow(self.context, strategy, action="restart", start_position="from_head")
            restart.assert_not_called()
            self.assertEqual(update.call_args.kwargs["metadata"]["annotations"]["task_stopped"], "true")
            self.assertEqual(save.call_args.args[1]["pending_spec"]["operation_config"]["start_position"], "from_head")

    def test_flow_pending_observation_has_a_bound(self):
        strategy = SimpleNamespace(backend_data={"bkbase_v4": {"poll_count": 60}})
        with mock.patch("services.web.bkbase.flow._save_binding"), mock.patch(
            "services.web.bkbase.flow.advance_rule_flow", return_value={"task_state": None}
        ):
            result = flow.strategy_deploy_data(strategy)
        self.assertEqual(result["status"], "failure")
        self.assertIn("timed out", result["logs"][0]["message"])

    def test_log_collector_owner_is_protected_before_stopping_logging(self):
        owner = CollectorConfig.objects.create(
            system_id="system_a",
            bk_biz_id=1,
            collector_plugin_id=1,
            collector_config_id=2,
            collector_config_name="source",
            bkbase_v4_resources={"clean": self.ref, "clean_role": "owner"},
        )
        with mock.patch("bk_resource.api.bk_log.stop_subscription") as stop:
            with self.assertRaises(BKBaseSharedResourceProtected):
                DeleteCollectorResource().request({"collector_config_id": owner.collector_config_id})
            stop.assert_not_called()
        self.assertTrue(CollectorConfig.objects.filter(pk=owner.pk).exists())

"""对照真实业务配置生产者及V4文档验证业务适配。

所有上游调用模拟，禁止测试触达真实接口。
覆盖字段元信息、事件JSON存储，以及配置更新期间的启停意图。
"""
from copy import deepcopy
from types import SimpleNamespace
from unittest import mock

from django.test import TestCase, override_settings

from core.exceptions import LockError
from services.web.analyze.controls.base import BkbaseFlowController
from services.web.analyze.tasks import check_flow_status
from services.web.bkbase import clean, flow, storage
from services.web.bkbase.exceptions import BKBaseOperationSuperseded
from services.web.databus.collector_plugin.handlers import (
    EventCollectorEtlHandler,
    PluginEtlHandler,
)
from services.web.databus.models import CollectorConfig, CollectorPlugin
from services.web.strategy_v2.constants import StrategyStatusChoices
from services.web.strategy_v2.models import Strategy


@override_settings(BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="tenant_a", BKBASE_V4_NAMESPACE="audit")
class BusinessAdaptationTests(TestCase):
    def setUp(self):
        transport = mock.patch(
            "requests.sessions.Session.request", side_effect=AssertionError("Unexpected HTTP request")
        )
        transport.start()
        self.addCleanup(transport.stop)
        self.context = {"version": "v4", "tenant": "tenant_a", "namespace": "audit"}
        self.ref = {**self.context, "kind": "Flow", "name": "flow_a"}
        self.pending_spec = {"nodes": [{"name": "changed"}]}

    def make_controller(self, status, pending_spec=True):
        binding = {"flow": self.ref, "operation": "wait_stopped", "requested_action": "start"}
        if pending_spec:
            binding["pending_spec"] = deepcopy(self.pending_spec)
        strategy = Strategy.objects.create(
            namespace="audit", strategy_name="rule", status=status, backend_data={"bkbase_v4": binding}
        )
        return SimpleNamespace(strategy=strategy, check_flow_status=mock.Mock())

    def test_clean_assign_metadata_comes_from_actual_plugin_fields(self):
        plugin = CollectorPlugin.objects.create(
            namespace="audit",
            collector_plugin_id=1,
            collector_plugin_name="plugin",
            collector_plugin_name_en="plugin_a",
            bkdata_biz_id=1,
            table_id=1,
            index_set_id=1,
            bkbase_v4_resources={"data_id": {**self.context, "kind": "DataId", "name": "data_a"}},
        )
        handler = PluginEtlHandler(plugin.collector_plugin_id)
        with mock.patch.object(handler, "get_bk_data_id", return_value=11):
            params = handler.build_clean_config()
        with mock.patch("services.web.bkbase.clean.ensure_clean") as ensure:
            clean.configure_clean(plugin, params, rt_owner=True)
        rules = ensure.call_args.kwargs["rules"]["rules"]
        assigns = {r["output_id"]: r["operator"] for r in rules if r["operator"]["type"] == "assign"}
        expected = {f["field_name"]: f for f in params["fields"]}
        for name in set(assigns) & set(expected):
            with self.subTest(field=name):
                self.assertEqual(assigns[name].get("alias"), expected[name]["field_alias"])
                self.assertEqual(assigns[name].get("is_dimension"), expected[name]["is_dimension"])
        self.assertTrue(set(assigns) & set(expected))

    def test_event_dynamic_json_storage_uses_original_json_fields(self):
        fields = EventCollectorEtlHandler.get_doris_fields()
        expected = [f["field_name"] for f in fields if f.get("is_original_json")]
        self.assertTrue(expected)
        translated = storage.convert_storage_config({"fields": fields})["taskFieldSetting"]
        self.assertEqual(translated.get("original_json_fields"), expected)
        self.assertFalse(set(expected) & set(translated["json_fields"]))

    def test_flow_transitional_state_keeps_existing_operation_without_force(self):
        for status in (
            StrategyStatusChoices.STARTING,
            StrategyStatusChoices.STOPPING,
            StrategyStatusChoices.UPDATING,
            StrategyStatusChoices.FAILED,
        ):
            with self.subTest(status=status):
                controller = self.make_controller(status)
                before = deepcopy(controller.strategy.backend_data)
                with mock.patch("services.web.bkbase.flow.operate_rule_flow") as operate:
                    flow.toggle_controller(controller, "restart")
                    operate.assert_not_called()
                controller.check_flow_status.assert_not_called()
                controller.strategy.refresh_from_db()
                self.assertEqual(controller.strategy.backend_data, before)
                self.assertEqual(controller.strategy.status, status)

    def test_forced_stop_does_not_apply_queued_graph_but_keeps_it_for_next_start(self):
        controller = self.make_controller(StrategyStatusChoices.UPDATING)
        with mock.patch("services.web.bkbase.flow.operate_rule_flow", return_value={"task_state": None}):
            flow.toggle_controller(controller, "stop", force=True)
        with mock.patch("services.web.bkbase.flow.apply_rule_flow") as apply, mock.patch(
            "services.web.bkbase.flow.get_rule_flow_status", return_value={"task_state": "stopped"}
        ):
            self.assertEqual(flow.strategy_deploy_data(controller.strategy)["status"], "success")
            apply.assert_not_called()
        controller.strategy.refresh_from_db()
        self.assertEqual(controller.strategy.backend_data["bkbase_v4"]["pending_spec"], self.pending_spec)

    def test_start_applies_saved_graph_instead_of_starting_old_graph(self):
        controller = self.make_controller(StrategyStatusChoices.DISABLED)
        with mock.patch(
            "services.web.bkbase.flow.apply_rule_flow", return_value={"task_state": None}
        ) as apply, mock.patch("services.web.bkbase.flow.operate_rule_flow") as operate:
            flow.toggle_controller(controller, "start")
            apply.assert_called_once_with(mock.ANY, controller.strategy, self.pending_spec)
            operate.assert_not_called()
        controller.check_flow_status.assert_called_once()

    def test_clean_delete_waits_without_republishing_already_requested_stop(self):
        ref = {**self.ref, "kind": "Clean"}
        collector = CollectorConfig.objects.create(
            system_id="system_a",
            bk_biz_id=1,
            collector_plugin_id=1,
            collector_config_id=1,
            collector_config_name="source",
            bkbase_v4_resources={"clean": ref, "clean_role": "existing"},
        )
        for state in ("Running", "Stopped"):
            with self.subTest(state=state):
                remote = {
                    "metadata": {"name": "flow_a"},
                    "spec": {"current_status": state, "desired_status": "Stopped"},
                    "status": {"phase": "Pending"},
                }
                with mock.patch("services.web.bkbase.clean.resource_lock"), mock.patch(
                    "services.web.bkbase.clean.get_resource_or_none", return_value=remote
                ), mock.patch("services.web.bkbase.clean.api.bk_base_v4.clean_update") as update, mock.patch(
                    "services.web.bkbase.clean.api.bk_base_v4.clean_delete"
                ) as delete:
                    result = clean.delete_source_clean(self.context, collector)
                    update.assert_not_called()
                    delete.assert_not_called()
                    self.assertIsNone(result["task_state"])

    def test_late_update_callback_cannot_overwrite_completed_stop(self):
        controller = self.make_controller(StrategyStatusChoices.DISABLED)
        flow._save_binding(controller.strategy, {"operation_id": "current_stop", "requested_action": "stop"})
        with mock.patch(
            "services.web.analyze.tasks.bkbase_flow.strategy_deploy_data", return_value={"status": "success"}
        ) as observe, mock.patch("services.web.analyze.tasks.check_flow_status.apply_async") as retry:
            check_flow_status.run(
                controller.strategy.pk,
                success_status=StrategyStatusChoices.RUNNING,
                failed_status=StrategyStatusChoices.UPDATE_FAILED,
                other_status=StrategyStatusChoices.UPDATING,
                operation_id="old_update",
            )
            observe.assert_not_called()
            retry.assert_not_called()
        controller.strategy.refresh_from_db()
        self.assertEqual(controller.strategy.status, StrategyStatusChoices.DISABLED)

    def test_callback_started_before_stop_cannot_commit_stale_failure(self):
        controller = self.make_controller(StrategyStatusChoices.UPDATING)
        flow._save_binding(controller.strategy, {"operation_id": "old_update"})

        def complete_after_stop(strategy):
            flow._save_binding(strategy, {"operation_id": "current_stop", "requested_action": "stop"})
            Strategy.objects.filter(pk=strategy.pk).update(status=StrategyStatusChoices.DISABLED)
            return {"status": "failure", "logs": [{"level": "ERROR", "message": "obsolete update failure"}]}

        with mock.patch(
            "services.web.analyze.tasks.bkbase_flow.strategy_deploy_data", side_effect=complete_after_stop
        ), mock.patch("services.web.analyze.tasks.ErrorMsgHandler") as notify:
            check_flow_status.run(
                controller.strategy.pk,
                success_status=StrategyStatusChoices.RUNNING,
                failed_status=StrategyStatusChoices.UPDATE_FAILED,
                other_status=StrategyStatusChoices.UPDATING,
                operation_id="old_update",
            )
            notify.assert_not_called()
        controller.strategy.refresh_from_db()
        self.assertEqual(controller.strategy.status, StrategyStatusChoices.DISABLED)
        self.assertNotEqual(controller.strategy.status_msg, "obsolete update failure")

    def test_status_callback_and_retry_keep_operation_identity(self):
        controller = self.make_controller(StrategyStatusChoices.UPDATING)
        flow._save_binding(controller.strategy, {"operation_id": "current_update"})
        with mock.patch("services.web.analyze.controls.base.check_flow_status.delay") as queue:
            BkbaseFlowController.check_flow_status(
                controller,
                controller.strategy.pk,
                StrategyStatusChoices.RUNNING,
                StrategyStatusChoices.UPDATE_FAILED,
                StrategyStatusChoices.UPDATING,
            )
            self.assertEqual(queue.call_args.kwargs["operation_id"], "current_update")
        with mock.patch(
            "services.web.analyze.tasks.bkbase_flow.strategy_deploy_data", return_value={"status": "other"}
        ), mock.patch("services.web.analyze.tasks.check_flow_status.apply_async") as retry:
            check_flow_status.run(
                controller.strategy.pk,
                success_status=StrategyStatusChoices.RUNNING,
                failed_status=StrategyStatusChoices.UPDATE_FAILED,
                other_status=StrategyStatusChoices.UPDATING,
                operation_id="current_update",
            )
            self.assertEqual(retry.call_args.kwargs["kwargs"]["operation_id"], "current_update")

    def test_superseded_start_does_not_overwrite_or_enqueue_after_completed_stop(self):
        controller = self.make_controller(StrategyStatusChoices.DISABLED, pending_spec=False)
        started = []

        def new_stop_arrives(context, strategy, **kwargs):
            started.append(strategy.backend_data["bkbase_v4"]["operation_id"])
            flow._save_binding(strategy, {"operation_id": "superseding_stop", "requested_action": "stop"})
            Strategy.objects.filter(pk=strategy.pk).update(status=StrategyStatusChoices.DISABLED)
            return {"task_state": None}

        with mock.patch("services.web.bkbase.flow.operate_rule_flow", side_effect=new_stop_arrives):
            flow.toggle_controller(controller, "start")
        controller.check_flow_status.assert_not_called()
        controller.strategy.refresh_from_db()
        self.assertEqual(controller.strategy.status, StrategyStatusChoices.DISABLED)

    def test_enqueue_does_not_rebind_old_callback_to_newer_operation(self):
        controller = self.make_controller(StrategyStatusChoices.DISABLED, pending_spec=False)
        started = []

        def enqueue_after_new_stop(**kwargs):
            started.append(controller.strategy.backend_data["bkbase_v4"]["operation_id"])
            flow._save_binding(controller.strategy, {"operation_id": "new_stop", "requested_action": "stop"})
            BkbaseFlowController.check_flow_status(controller, **kwargs)

        controller.check_flow_status = enqueue_after_new_stop
        with mock.patch("services.web.bkbase.flow.operate_rule_flow", return_value={"task_state": None}), mock.patch(
            "services.web.analyze.controls.base.check_flow_status.delay"
        ) as queue:
            flow.toggle_controller(controller, "start")
            self.assertEqual(queue.call_args.kwargs["operation_id"], started[0])

    def test_superseded_poll_cannot_consume_new_stop_retry_budget(self):
        controller = self.make_controller(StrategyStatusChoices.UPDATING, pending_spec=False)
        flow._save_binding(controller.strategy, {"operation_id": "old_update", "poll_count": 59})

        def new_stop_during_observation(strategy_context, strategy):
            flow._save_binding(
                strategy,
                {
                    "operation_id": "new_stop",
                    "requested_action": "stop",
                    "operation": "wait_stopped",
                    "poll_count": 0,
                    "message": "new stop",
                },
            )
            return {"task_state": None, "message": "old update"}

        with mock.patch("services.web.bkbase.flow.advance_rule_flow", side_effect=new_stop_during_observation):
            result = flow.strategy_deploy_data(controller.strategy)
        controller.strategy.refresh_from_db()
        binding = controller.strategy.backend_data["bkbase_v4"]
        self.assertEqual(binding["poll_count"], 0)
        self.assertEqual(binding["message"], "new stop")
        self.assertEqual(result["status"], "superseded")
        with mock.patch("services.web.bkbase.flow.advance_rule_flow", return_value={"task_state": None}), mock.patch(
            "services.web.analyze.tasks.check_flow_status.apply_async"
        ) as retry:
            check_flow_status.run(
                controller.strategy.pk,
                success_status=StrategyStatusChoices.DISABLED,
                failed_status=StrategyStatusChoices.STOP_FAILED,
                other_status=StrategyStatusChoices.STOPPING,
                operation_id="new_stop",
            )
            retry.assert_called_once()
        controller.strategy.refresh_from_db()
        self.assertEqual(controller.strategy.status, StrategyStatusChoices.STOPPING)
        self.assertEqual(controller.strategy.backend_data["bkbase_v4"]["poll_count"], 1)

    def test_transient_observation_error_still_consumes_current_operation_retry_budget(self):
        controller = self.make_controller(StrategyStatusChoices.UPDATING, pending_spec=False)
        flow._save_binding(controller.strategy, {"operation_id": "current_update", "poll_count": 0})
        with mock.patch("services.web.bkbase.flow.advance_rule_flow", side_effect=LockError(message="busy")):
            for count in (1, 2):
                self.assertEqual(flow.strategy_deploy_data(controller.strategy)["status"], "other")
                controller.strategy.refresh_from_db()
                self.assertEqual(controller.strategy.backend_data["bkbase_v4"]["poll_count"], count)

    def test_stale_operation_cannot_replace_new_stage_or_remove_saved_graph(self):
        controller = self.make_controller(StrategyStatusChoices.STOPPING)
        flow._save_binding(
            controller.strategy, {"operation_id": "new_stop", "requested_action": "stop", "restart_waiting": True}
        )
        before = deepcopy(controller.strategy.backend_data)
        with self.assertRaises(BKBaseOperationSuperseded):
            flow._save_operation_binding(
                {**self.context, "operation_id": "old_update"},
                controller.strategy,
                {"operation": "wait_running", "requested_action": "start"},
                remove=["pending_spec", "restart_waiting"],
            )
        controller.strategy.refresh_from_db()
        self.assertEqual(controller.strategy.backend_data, before)

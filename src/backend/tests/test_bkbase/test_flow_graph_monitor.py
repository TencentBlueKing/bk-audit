"""整图运行确认后同步通知，未完成和过期回调不发布任务。"""
from copy import deepcopy
from types import SimpleNamespace
from unittest import mock

from django.db import connection, transaction
from django.test import TransactionTestCase, override_settings

from services.web.analyze import tasks
from services.web.bkbase import flow
from services.web.strategy_v2.constants import StrategyStatusChoices
from services.web.strategy_v2.models import Strategy
from tests.test_bkbase.test_flow_pure_operation import FlowFixture


@override_settings(BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="tenant_a", BKBASE_V4_NAMESPACE="audit")
class FlowGraphMonitorTests(FlowFixture, TransactionTestCase):
    def setUp(self):
        super().setUp()
        backend = deepcopy(self.strategy.backend_data)
        backend["bkbase_v4"]["operation_id"] = "graph_operation"
        self.strategy.backend_data = backend
        self.strategy.status = StrategyStatusChoices.STARTING
        self.strategy.save(update_fields=["backend_data", "status"])
        self.remote["metadata"]["annotations"]["task_stopped"] = "false"

    def check(self):
        tasks.check_flow_status.run(
            self.strategy.pk,
            StrategyStatusChoices.RUNNING,
            StrategyStatusChoices.UPDATE_FAILED,
            StrategyStatusChoices.UPDATING,
            operation_id="graph_operation",
        )

    def test_create_and_update_publish_monitor_only_after_running(self):
        for status in (StrategyStatusChoices.STARTING, StrategyStatusChoices.UPDATING):
            with self.subTest(status=status):
                Strategy.objects.filter(pk=self.strategy.pk).update(status=status)
                self.monitor.reset_mock()
                self.remote["status"]["phase"] = "Pending"
                self.check()
                self.monitor.assert_not_called()
                self.remote["status"]["phase"] = "Ok"

                def published(**params):
                    self.assertFalse(connection.in_atomic_block)
                    self.assertEqual(Strategy.objects.get(pk=self.strategy.pk).status, StrategyStatusChoices.RUNNING)

                self.monitor.side_effect = published
                self.check()
                self.monitor.assert_called_once_with(
                    strategy_id=self.strategy.pk, is_active=True, operation_id="graph_operation"
                )
                self.check()
                self.assertEqual(self.monitor.call_count, 1)

    def test_failed_graph_does_not_activate_monitor(self):
        self.remote["status"]["phase"] = "Failed"
        with mock.patch.object(tasks, "ErrorMsgHandler"):
            self.check()
        self.monitor.assert_not_called()
        self.assertEqual(Strategy.objects.get(pk=self.strategy.pk).status, StrategyStatusChoices.UPDATE_FAILED)

    def test_superseded_during_read_does_not_publish_monitor(self):
        def supersede():
            backend = deepcopy(self.strategy.backend_data)
            backend["bkbase_v4"]["operation_id"] = "new_operation"
            Strategy.objects.filter(pk=self.strategy.pk).update(backend_data=backend)

        self.read_hook = supersede
        self.check()
        self.monitor.assert_not_called()
        self.assertEqual(Strategy.objects.get(pk=self.strategy.pk).status, StrategyStatusChoices.STARTING)

    def test_rollback_does_not_publish_monitor(self):
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                flow.persist_operation_status(self.strategy, "graph_operation", StrategyStatusChoices.RUNNING)
                self.monitor.assert_not_called()
                raise RuntimeError("synthetic rollback")
        self.monitor.assert_not_called()
        self.assertEqual(Strategy.objects.get(pk=self.strategy.pk).status, StrategyStatusChoices.STARTING)

    def test_superseded_before_commit_callback_does_not_publish_monitor(self):
        with mock.patch("services.web.bkbase.flow_operation.transaction.on_commit") as callbacks:
            flow.persist_operation_status(self.strategy, "graph_operation", StrategyStatusChoices.RUNNING)
        pending = [call.args[0] for call in callbacks.call_args_list]
        self.assertEqual(len(pending), 1)
        backend = deepcopy(self.strategy.backend_data)
        backend["bkbase_v4"]["operation_id"] = "new_operation"
        Strategy.objects.filter(pk=self.strategy.pk).update(backend_data=backend)
        pending[0]()
        self.monitor.assert_not_called()

    def test_configuration_changed_before_commit_callback_does_not_publish_monitor(self):
        with mock.patch("services.web.bkbase.flow_operation.transaction.on_commit") as callbacks:
            flow.persist_operation_status(self.strategy, "graph_operation", StrategyStatusChoices.RUNNING)
        Strategy.objects.filter(pk=self.strategy.pk).update(sql="new configuration")
        callbacks.call_args.args[0]()
        self.monitor.assert_not_called()

    def test_status_changed_before_commit_callback_does_not_activate_monitor(self):
        with mock.patch("services.web.bkbase.flow_operation.transaction.on_commit") as callbacks:
            flow.persist_operation_status(self.strategy, "graph_operation", StrategyStatusChoices.RUNNING)
        Strategy.objects.filter(pk=self.strategy.pk).update(status=StrategyStatusChoices.UPDATE_FAILED)
        callbacks.call_args.args[0]()
        self.monitor.assert_not_called()

    def test_graph_notification_reaches_existing_consumer_with_current_operation(self):
        Strategy.objects.filter(pk=self.strategy.pk).update(notice_groups=[17])
        self.monitor.side_effect = tasks.toggle_monitor.run
        groups = [SimpleNamespace(notice_config=[{"msg_type": "mail"}])]
        with mock.patch.object(
            tasks.NoticeGroup.objects, "filter", return_value=groups
        ) as group_query, mock.patch.object(
            tasks.IgnoreMemberVariableParser, "parse_groups", return_value=["synthetic_receiver"]
        ), mock.patch.object(
            flow, "configure_monitor", return_value={"accepted": True}
        ) as configure:
            self.check()
        configure.assert_called_once()
        group_query.assert_called_once_with(group_id__in=[17])
        self.assertEqual(configure.call_args.args[0].status, StrategyStatusChoices.RUNNING)
        self.assertEqual(
            configure.call_args.kwargs,
            {
                "active": True,
                "receivers": [{"receiver_type": "user", "username": "synthetic_receiver"}],
                "notify_config": ["mail"],
                "operation_id": "graph_operation",
            },
        )

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_status_callback_does_not_add_another_monitor_producer(self):
        with mock.patch.object(flow, "get_flow_deploy_data", return_value={"status": "success"}):
            tasks.check_flow_status.run(
                self.strategy.pk,
                StrategyStatusChoices.RUNNING,
                StrategyStatusChoices.START_FAILED,
                StrategyStatusChoices.STARTING,
            )
        self.monitor.assert_not_called()

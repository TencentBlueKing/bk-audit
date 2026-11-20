"""版本切换后旧回调不得读取另一版本任务或回写策略。"""
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase, override_settings

from services.web.analyze import tasks
from services.web.bkbase import flow


class CallbackVersionSwitchTests(SimpleTestCase):
    def setUp(self):
        self.strategy = SimpleNamespace(
            pk=9,
            strategy_id=9,
            status="starting",
            status_msg="retained",
            save=mock.Mock(),
            backend_data={"flow_id": 123, "bkbase_v4": {"operation_id": "v4_operation_a"}},
        )
        self.enterContext(
            mock.patch.object(tasks.Strategy.objects, "filter")
        ).return_value.first.return_value = self.strategy
        self.deploy = self.enterContext(
            mock.patch.object(flow, "strategy_deploy_data", return_value={"status": "success"})
        )
        self.retry = self.enterContext(mock.patch.object(tasks.check_flow_status, "apply_async"))
        self.enterContext(
            mock.patch("requests.sessions.Session.request", side_effect=AssertionError("unexpected HTTP"))
        )

    def observe(self, operation_id=None):
        tasks.check_flow_status.run(9, "running", "failed", "starting", operation_id=operation_id)

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v4_callback_after_rollback_is_rejected_before_read_or_status_write(self):
        self.observe("v4_operation_a")
        self.deploy.assert_not_called()
        self.strategy.save.assert_not_called()
        self.retry.assert_not_called()
        self.assertEqual((self.strategy.status, self.strategy.status_msg), ("starting", "retained"))

    @override_settings(BKBASE_API_VERSION="v3")
    def test_status_persistence_itself_rejects_v4_operation_identity(self):
        self.assertFalse(flow.persist_operation_status(self.strategy, "v4_operation_a", "failed", "stale"))
        self.strategy.save.assert_not_called()
        self.assertEqual((self.strategy.status, self.strategy.status_msg), ("starting", "retained"))

    @override_settings(BKBASE_API_VERSION="v3")
    def test_legacy_v3_callback_and_status_persistence_remain_available(self):
        self.observe()
        self.deploy.assert_called_once_with(self.strategy)
        self.strategy.save.assert_called_once_with(update_record=False, update_fields=["status"])
        self.assertEqual(self.strategy.status, "running")
        self.retry.assert_not_called()

    @override_settings(BKBASE_API_VERSION="v4")
    def test_old_v3_callback_after_upgrade_is_rejected_before_read(self):
        self.observe()
        self.deploy.assert_not_called()
        self.strategy.save.assert_not_called()
        self.retry.assert_not_called()

    @override_settings(BKBASE_API_VERSION="v4")
    def test_v4_identity_still_requires_current_operation(self):
        self.assertTrue(flow.is_current_operation(self.strategy, "v4_operation_a"))
        self.assertFalse(flow.is_current_operation(self.strategy, "v4_operation_old"))
        self.assertFalse(flow.is_current_operation(self.strategy, None))

    def test_rollback_during_observation_cannot_write_or_requeue_old_v4_status(self):
        version = {"value": "v4"}

        def deploy(strategy):
            version["value"] = "v3"
            return {"status": "success"}

        with mock.patch.object(flow, "get_bkbase_version", side_effect=lambda: version["value"]):
            self.deploy.side_effect = deploy
            self.observe("v4_operation_a")
        self.deploy.assert_called_once()
        self.strategy.save.assert_not_called()
        self.retry.assert_not_called()
        self.assertEqual(self.strategy.status, "starting")

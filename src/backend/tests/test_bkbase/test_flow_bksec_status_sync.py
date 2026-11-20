"""纯Flow操作确认后联动真实自动规则，仅替换平台与队列边界。"""
import json
from copy import deepcopy
from unittest import mock

import requests
from django.db import connection
from django.test import TransactionTestCase, override_settings

from services.web.analyze import tasks
from services.web.analyze.controls.rule_audit import RuleAuditController
from services.web.risk.bksec import rules
from services.web.risk.models import ProcessApplication, RiskRule
from services.web.strategy_v2.constants import StrategyStatusChoices
from services.web.strategy_v2.models import Strategy
from tests.test_bkbase.test_flow_pure_operation import FlowFixture
from tests.test_bksec.test_bksec import BKSEC_CONFIG_DATA


@override_settings(
    BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="tenant_a", BKBASE_V4_NAMESPACE="audit", BKSEC_SOPS_TEMPLATE_ID="10001"
)
class FlowBksecStatusSyncTests(FlowFixture, TransactionTestCase):
    def setUp(self):
        super().setUp()
        self.missing_receipt = False
        self.remote["status"].update(version=1, history_id=1)
        self.strategy.bksec_config = deepcopy(BKSEC_CONFIG_DATA)
        self.strategy.save(update_fields=["bksec_config"])
        ProcessApplication.objects.create(
            name="synthetic preset", sops_template_id=10001, is_builtin=True, is_enabled=True, need_approve=False
        )
        self.enterContext(mock.patch.object(rules, "sync_plugin_config", return_value=(True, "ok")))
        original = tasks._sync_bksec_rule_after_status_change

        def sync(current):
            self.assertFalse(connection.in_atomic_block, "Flow row locks must be released before BKSEC sync")
            return original(current)

        self.sync = self.enterContext(
            mock.patch.object(tasks, "_sync_bksec_rule_after_status_change", side_effect=sync)
        )
        self.enterContext(mock.patch.object(tasks, "ErrorMsgHandler"))

    def transport(self, method, url, **kwargs):
        if method.upper() != "PUT":
            return super().transport(method, url, **kwargs)
        self.assertFalse(connection.in_atomic_block)
        self.calls.append((method.upper(), url, deepcopy(kwargs)))
        version = self.remote["status"]["version"] + 1
        self.remote.update(
            metadata=deepcopy(kwargs["json"]["metadata"]),
            spec=deepcopy(kwargs["json"]["spec"]),
            status={"phase": "Pending", "version": version, "history_id": version},
        )
        response = requests.Response()
        response.status_code = 200
        result = deepcopy(self.remote)
        if self.missing_receipt:
            result["status"].pop("phase")
        response._content = json.dumps({"result": True, "code": "00", "data": result}).encode()
        response.url = url
        return response

    def seed_rule(self, *, alive):
        rule = rules.sync_bksec_rule(self.strategy, strategy_alive=True)
        if not alive:
            rules.sync_bksec_rule(self.strategy, strategy_alive=False)
        return rule

    def start(self):
        self.strategy.status = StrategyStatusChoices.DISABLED
        self.strategy.save(update_fields=["status"])
        self.remote["metadata"]["annotations"]["task_stopped"] = "true"
        RuleAuditController(self.strategy.pk).enable()
        return self.binding()["operation_id"]

    def restart(self):
        RuleAuditController(self.strategy.pk).enable()
        return self.binding()["operation_id"]

    def check(self, operation_id=None):
        tasks.check_flow_status.run(
            self.strategy.pk,
            StrategyStatusChoices.RUNNING,
            StrategyStatusChoices.UPDATE_FAILED,
            StrategyStatusChoices.UPDATING,
            operation_id=operation_id or self.binding()["operation_id"],
        )

    def enabled(self):
        return RiskRule.objects.filter(auto_strategy_id=self.strategy.pk).latest("version").is_enabled

    def test_pure_start_running_immediately_enables_existing_auto_rule(self):
        original = self.seed_rule(alive=False)
        self.start()
        self.assertFalse(self.enabled())
        self.remote["status"]["phase"] = "Ok"
        self.check()
        self.assertEqual(Strategy.objects.get(pk=self.strategy.pk).status, StrategyStatusChoices.RUNNING)
        self.assertTrue(self.enabled())
        self.assertEqual(RiskRule.objects.filter(auto_strategy_id=self.strategy.pk).count(), 1)
        self.assertEqual(RiskRule.objects.get(pk=original.pk).version, original.version)

    def test_pure_restart_async_failure_disables_enabled_rule(self):
        self.seed_rule(alive=True)
        self.restart()
        self.remote["status"]["phase"] = "Failed"
        self.check()
        self.assertEqual(Strategy.objects.get(pk=self.strategy.pk).status, StrategyStatusChoices.UPDATE_FAILED)
        self.assertFalse(self.enabled())

    def test_pure_start_async_failure_disables_existing_auto_rule(self):
        original = self.seed_rule(alive=True)
        self.start()
        self.check()
        self.sync.assert_not_called()
        self.assertTrue(self.enabled())
        self.remote["status"]["phase"] = "Failed"
        self.check()
        self.assertEqual(Strategy.objects.get(pk=self.strategy.pk).status, StrategyStatusChoices.START_FAILED)
        original.refresh_from_db()
        self.assertFalse(original.is_enabled)
        self.assertEqual(RiskRule.objects.filter(auto_strategy_id=self.strategy.pk).count(), 1)
        self.sync.assert_called_once()

    def test_pure_restart_success_syncs_only_after_both_steps(self):
        self.seed_rule(alive=True)
        self.restart()
        self.check()
        self.sync.assert_not_called()
        self.remote["status"]["phase"] = "Ok"
        self.check()
        self.sync.assert_not_called()
        self.remote["status"]["phase"] = "Ok"
        self.check()
        self.assertEqual(Strategy.objects.get(pk=self.strategy.pk).status, StrategyStatusChoices.RUNNING)
        self.sync.assert_called_once()
        self.assertTrue(self.enabled())

    def test_pending_start_does_not_enable_rule(self):
        self.seed_rule(alive=False)
        self.start()
        self.check()
        self.sync.assert_not_called()
        self.assertFalse(self.enabled())

    def test_superseded_during_get_does_not_sync_rule(self):
        self.seed_rule(alive=False)
        operation_id = self.start()

        def supersede():
            current = Strategy.objects.get(pk=self.strategy.pk)
            current.backend_data["bkbase_v4"]["operation_id"] = "new_operation"
            Strategy.objects.filter(pk=current.pk).update(backend_data=current.backend_data)

        self.read_hook = supersede
        self.remote["status"]["phase"] = "Ok"
        self.check(operation_id)
        self.sync.assert_not_called()
        self.assertFalse(self.enabled())

    def test_flow_configuration_change_during_get_does_not_sync_rule(self):
        self.seed_rule(alive=False)
        self.start()
        self.read_hook = lambda: Strategy.objects.filter(pk=self.strategy.pk).update(sql="changed SQL")
        self.remote["status"]["phase"] = "Ok"
        self.check()
        self.sync.assert_not_called()
        self.assertFalse(self.enabled())

    def test_bksec_configuration_change_during_get_does_not_sync_old_rule(self):
        self.seed_rule(alive=False)
        self.start()
        changed = {**self.strategy.bksec_config, "risk_type_id": "changed_risk_type"}
        self.read_hook = lambda: Strategy.objects.filter(pk=self.strategy.pk).update(bksec_config=changed)
        self.remote["status"]["phase"] = "Ok"
        self.check()
        self.sync.assert_not_called()
        self.assertFalse(self.enabled())

    def test_version_rollback_rejects_v4_callback_before_rule_or_platform_read(self):
        self.seed_rule(alive=False)
        operation_id = self.start()
        calls = len(self.calls)
        with override_settings(BKBASE_API_VERSION="v3"):
            self.check(operation_id)
        self.sync.assert_not_called()
        self.assertFalse(self.enabled())
        self.assertEqual(len(self.calls), calls)

    def pending_rule_callback(self):
        self.seed_rule(alive=False)
        self.start()
        self.remote["status"]["phase"] = "Ok"
        with mock.patch.object(tasks.transaction, "on_commit") as callbacks:
            self.check()
        self.sync.assert_not_called()
        self.assertFalse(self.enabled())
        self.assertEqual(callbacks.call_count, 1)
        return callbacks.call_args.args[0]

    def test_operation_superseded_before_commit_callback_does_not_sync_rule(self):
        callback = self.pending_rule_callback()
        current = Strategy.objects.get(pk=self.strategy.pk)
        current.backend_data["bkbase_v4"]["operation_id"] = "new_operation"
        Strategy.objects.filter(pk=current.pk).update(backend_data=current.backend_data)
        callback()
        self.sync.assert_not_called()
        self.assertFalse(self.enabled())

    def test_configuration_changed_before_commit_callback_does_not_sync_rule(self):
        callback = self.pending_rule_callback()
        Strategy.objects.filter(pk=self.strategy.pk).update(sql="new configuration")
        callback()
        self.sync.assert_not_called()
        self.assertFalse(self.enabled())

    def test_version_rollback_before_commit_callback_does_not_sync_rule(self):
        callback = self.pending_rule_callback()
        with override_settings(BKBASE_API_VERSION="v3"):
            callback()
        self.sync.assert_not_called()
        self.assertFalse(self.enabled())

    def test_restart_unknown_write_does_not_disable_rule(self):
        self.seed_rule(alive=True)
        self.missing_receipt = True
        self.restart()
        self.assertTrue(self.binding()["pure_operation"]["outcome_unknown"])
        self.check()
        self.sync.assert_not_called()
        self.assertTrue(self.enabled())

    def test_v3_status_callback_still_enables_rule(self):
        self.seed_rule(alive=False)
        self.strategy.status = StrategyStatusChoices.STARTING
        self.strategy.save(update_fields=["status"])
        with override_settings(BKBASE_API_VERSION="v3"), mock.patch.object(
            tasks.bkbase_flow, "get_flow_deploy_data", return_value={"status": "success"}
        ):
            tasks.check_flow_status.run(
                self.strategy.pk,
                StrategyStatusChoices.RUNNING,
                StrategyStatusChoices.START_FAILED,
                StrategyStatusChoices.STARTING,
            )
        self.assertTrue(self.enabled())
        self.sync.assert_called_once()

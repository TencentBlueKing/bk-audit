"""V4 ES显式8到0切换：身份、最小配置变化、备份及未知写保护。"""

import json
import tempfile
from contextlib import nullcontext
from copy import deepcopy
from io import StringIO
from pathlib import Path
from unittest import mock

import requests
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TransactionTestCase, override_settings

from api.bk_base_v4.default import BkBaseV4Resource, FlowUpdate
from services.web.bkbase import flow, flow_es_timezone, flow_operation
from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.databus.management.commands import (
    migrate_bkbase_v4_flow_es_timezone as command_module,
)
from services.web.strategy_v2.constants import StrategyStatusChoices, StrategyType
from services.web.strategy_v2.models import Strategy


def ref(kind="Flow", name="actual_flow"):
    return {"kind": kind, "tenant": "tenant_a", "namespace": "audit", "name": name}


def spec(timezone=8):
    return {
        "description": "retain top-level option",
        "operation_config": {"start_position": "tail", "retained": True},
        "nodes": [
            {"kind": "StreamSourceNode", "name": "actual_source", "data": ref("ResultTable", "input")},
            {
                "kind": "StreamNode",
                "name": "actual_sql",
                "inputs": ["actual_source"],
                "output": "7_output",
                "config": {"sql": "SELECT * FROM input"},
            },
            {
                "kind": "EsStorageNode",
                "name": "actual_es",
                "input": "actual_sql",
                "storage": ref("ElasticSearch", "existing_es"),
                "write_alias": {
                    "TimeBased": {"format": "write_{yyyyMMdd}_events", "timezone": timezone, "retained": "nested"}
                },
                "expires": "7d",
                "retained": {"arbitrary": [1]},
            },
        ],
    }


class FlowTimezoneConversionTests(SimpleTestCase):
    def test_only_explicit_eight_changes_and_all_other_fields_are_preserved(self):
        before = spec()
        after, changes = flow_es_timezone.convert_spec(before)
        expected = deepcopy(before)
        expected["nodes"][2]["write_alias"]["TimeBased"]["timezone"] = 0
        self.assertEqual(after, expected)
        self.assertEqual(changes, [{"node": "actual_es", "from": 8, "to": 0}])
        self.assertEqual(before, spec())

    def test_zero_is_idempotent_and_fixed_is_untouched(self):
        for alias in ({"TimeBased": {"format": "write_%Y%m%d_events", "timezone": 0}}, {"Fixed": "fixed_events"}):
            before = spec()
            before["nodes"][2]["write_alias"] = alias
            self.assertEqual(flow_es_timezone.convert_spec(before), (before, []))

    def test_missing_other_or_noninteger_timezone_is_never_guessed(self):
        for timezone in (None, 1, -8, "8", "0", True, False):
            before = spec(timezone)
            with self.subTest(timezone=timezone), self.assertRaises(BKBaseResourceMappingError):
                flow_es_timezone.convert_spec(before)
        for alias in (
            None,
            {},
            {"TimeBased": {"format": "write_%Y%m%d_events"}},
            {"TimeBased": {"format": "literal", "timezone": 8}},
            {"TimeBased": {"format": "x_%Y%m%d", "timezone": 8}, "Fixed": "other"},
        ):
            before = spec()
            before["nodes"][2]["write_alias"] = alias
            with self.subTest(alias=alias), self.assertRaises(BKBaseResourceMappingError):
                flow_es_timezone.convert_spec(before)

    def test_ordinary_rebuild_preserves_eight_and_rejects_other_target_changes(self):
        before = spec()
        desired = deepcopy(before)
        desired["nodes"][2]["write_alias"]["TimeBased"]["timezone"] = 0
        result = flow._merged_spec(before, desired, preserve_storage_targets=True)
        self.assertEqual(result, before)
        self.assertEqual(desired["nodes"][2]["write_alias"]["TimeBased"]["timezone"], 0)
        for changed in ("different_%Y%m%d_events",):
            desired = spec(0)
            desired["nodes"][2]["write_alias"]["TimeBased"]["format"] = changed
            with self.assertRaises(BKBaseResourceMappingError):
                flow._merged_spec(spec(0), desired, preserve_storage_targets=True)

    def test_normal_zero_update_retains_real_node_names_and_undeclared_options(self):
        old = spec(0)
        desired = deepcopy(old)
        desired["nodes"][2].pop("retained")
        desired["nodes"][2]["name"] = "new_generated_name"
        desired["nodes"][2]["expires"] = "14d"
        result = flow._merged_spec(old, desired, preserve_storage_targets=True)
        expected = deepcopy(old)
        expected["nodes"][2]["expires"] = "14d"
        self.assertEqual(result, expected)


@override_settings(BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="tenant_a", BKBASE_V4_NAMESPACE="audit")
class FlowTimezoneReportFailureTests(SimpleTestCase):
    """命令边界替身：持续报告IO错误不能覆盖已受理或未知发送事实。"""

    def run_report_failure(self, *, unknown):
        with tempfile.TemporaryDirectory(prefix="flow-timezone-report-") as directory:
            plan = {"strategy_id": 123, "audit_namespace": "audit", "flow_ref": ref()}
            path = Path(directory) / "plan.json"
            path.write_text(json.dumps(plan))
            writes, events, fence = [], [], {}
            original = command_module._write_event

            def write_event(handle, event):
                events.append(event["event"])
                if writes:
                    raise OSError("synthetic persistent report failure")
                original(handle, event)

            def apply_plan(context, approved, *, before_write):
                self.assertEqual(approved, plan)
                before_write()
                writes.append("PUT")
                if unknown:
                    fence["flow_write"] = {"token": "synthetic", "outcome_unknown": True}
                    raise BKBaseResourceMappingError(message="synthetic unconfirmed PUT; retain flow_write")
                return "accepted"

            with mock.patch.object(command_module, "_write_event", side_effect=write_event), mock.patch.object(
                flow_es_timezone, "apply_plan", side_effect=apply_plan
            ) as apply, mock.patch.object(
                requests.Session, "request", side_effect=AssertionError("real network forbidden")
            ), mock.patch.object(
                requests.Session, "send", side_effect=AssertionError("real network forbidden")
            ):
                with self.assertRaises(CommandError) as caught:
                    call_command(
                        "migrate_bkbase_v4_flow_es_timezone",
                        strategy_id=123,
                        audit_namespace="audit",
                        flow_ref=json.dumps(ref()),
                        plan=str(path),
                        report=str(Path(directory) / "report.jsonl"),
                        apply=True,
                        stdout=StringIO(),
                    )
            apply.assert_called_once()
            self.assertEqual(writes, ["PUT"])
            self.assertEqual(events[:2], ["begin", "before_send"])
            self.assertNotIn("未继续发送", str(caught.exception))
            return str(caught.exception), caught.exception.__cause__, fence, events

    def test_accepted_put_and_persistent_report_failure_reports_receipt_not_unsent(self):
        message, cause, fence, events = self.run_report_failure(unknown=False)
        self.assertIn("PUT已受理", message)
        self.assertIn("报告落盘未确认", message)
        self.assertIn("只读", message)
        self.assertIn("勿按未发送重跑", message)
        self.assertIsInstance(cause, OSError)
        self.assertEqual(fence, {})
        self.assertEqual(events[2:], ["accepted", "error"])

    def test_unknown_put_and_persistent_report_failure_preserves_fence_and_readonly_advice(self):
        message, cause, fence, events = self.run_report_failure(unknown=True)
        self.assertIn("PUT发送阶段", message)
        self.assertIn("结果未确认", message)
        self.assertIn("保留flow_write", message)
        self.assertIn("只读", message)
        self.assertIn("勿按未发送重跑", message)
        self.assertIsInstance(cause, BKBaseResourceMappingError)
        self.assertEqual(fence, {"flow_write": {"token": "synthetic", "outcome_unknown": True}})
        self.assertEqual(events[2:], ["error"])


@override_settings(BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="tenant_a", BKBASE_V4_NAMESPACE="audit")
class FlowTimezoneCommandTests(TransactionTestCase):
    def setUp(self):
        self.strategy = Strategy.objects.create(
            namespace="audit",
            strategy_name="synthetic rule",
            strategy_type=StrategyType.RULE,
            status=StrategyStatusChoices.DISABLED,
            configs={"retained": True},
            backend_data={
                "retained": [1],
                "bkbase_v4": {"flow": ref(), "output_rt_id": "7_output", "operation_id": "existing"},
            },
        )
        self.remote = {
            "kind": "Flow",
            "metadata": {**ref(), "annotations": {"task_stopped": "true", "retained": "keep"}},
            "spec": spec(),
            "status": {"phase": "Ok"},
        }
        self.temp = self.enterContext(tempfile.TemporaryDirectory(prefix="flow-es-timezone-"))
        self.plan_path = Path(self.temp) / "plan.json"
        self.report_count = 0
        self.events = []
        self.enterContext(
            mock.patch.object(flow_es_timezone, "resource_lock", side_effect=lambda *a, **kw: nullcontext())
        )
        self.get = self.enterContext(
            mock.patch.object(
                flow_es_timezone.api.bk_base_v4, "flow_get", side_effect=lambda **kw: deepcopy(self.remote)
            )
        )
        self.put = self.enterContext(
            mock.patch.object(flow_es_timezone.api.bk_base_v4, "flow_update", side_effect=self.update)
        )
        self.enterContext(
            mock.patch.object(requests.Session, "request", side_effect=AssertionError("real network forbidden"))
        )

    def update(self, **params):
        self.assertTrue(self.events and self.events[-1]["event"] == "before_send")
        self.strategy.refresh_from_db()
        self.assertTrue(flow_operation.binding(self.strategy)["flow_write"]["token"])
        self.remote.update({k: deepcopy(params[k]) for k in ("metadata", "spec", "status")})
        self.remote["status"] = {"phase": "Pending"}
        return deepcopy(self.remote)

    def command(self, apply=False, **options):
        self.report_count += 1
        report = Path(self.temp) / f"report-{self.report_count}.jsonl"
        original = command_module._write_event

        def write(handle, event):
            original(handle, event)
            self.events.append(deepcopy(event))

        with mock.patch.object(command_module, "_write_event", side_effect=write):
            call_command(
                "migrate_bkbase_v4_flow_es_timezone",
                strategy_id=self.strategy.pk,
                audit_namespace="audit",
                flow_ref=json.dumps(ref()),
                plan=str(self.plan_path),
                report=str(report),
                apply=apply,
                stdout=StringIO(),
                **options,
            )
        return [json.loads(line) for line in report.read_text().splitlines()]

    def test_preview_then_explicit_apply_preserves_full_configuration_and_stays_stopped(self):
        original = deepcopy(self.remote)
        local = deepcopy(self.strategy.backend_data)
        events = self.command()
        self.put.assert_not_called()
        self.assertEqual(events[-1]["event"], "planned")
        self.assertEqual(self.plan_path.stat().st_mode & 0o777, 0o600)
        self.command(apply=True)
        self.put.assert_called_once()
        payload = self.put.call_args.kwargs
        expected = deepcopy(original["spec"])
        expected["nodes"][2]["write_alias"]["TimeBased"]["timezone"] = 0
        self.assertEqual(
            payload,
            {
                "tenant": "tenant_a",
                "namespace": "audit",
                "name": "actual_flow",
                "metadata": original["metadata"],
                "spec": expected,
                "status": None,
            },
        )
        self.strategy.refresh_from_db()
        self.assertEqual(self.strategy.backend_data, local)
        self.assertEqual(self.strategy.status, StrategyStatusChoices.DISABLED)

    def test_apply_releases_write_guard_when_sdk_receipt_includes_null_inactive_deployment(self):
        self.remote["spec"]["operation_config"]["stream_sql_deploy_config"] = {
            "cluster": "published_stream",
            "deploy_mode": "k8s-operator",
            "deploy_config": None,
        }
        expected = deepcopy(self.remote["spec"])
        expected["operation_config"]["batch_sql_deploy_config"] = None
        expected["nodes"][2]["write_alias"]["TimeBased"]["timezone"] = 0

        def transport(method, url, **kwargs):
            self.assertEqual(method, "PUT")
            payload = kwargs["json"]
            self.assertEqual(payload["spec"], expected)
            receipt = self.update(**payload)
            response = requests.Response()
            response.status_code = 200
            response.url = url
            response._content = json.dumps({"result": True, "code": "00", "data": receipt}).encode()
            return response

        self.command()
        self.put.side_effect = FlowUpdate().request
        with mock.patch.object(BkBaseV4Resource, "build_header", return_value={}), mock.patch.object(
            requests.Session, "request", side_effect=transport
        ):
            events = self.command(apply=True)

        self.put.assert_called_once()
        self.assertEqual(events[-1]["event"], "accepted")
        self.strategy.refresh_from_db()
        self.assertNotIn("flow_write", flow_operation.binding(self.strategy))
        self.assertEqual(self.strategy.status, StrategyStatusChoices.DISABLED)

    def test_zero_and_fixed_are_idempotent_without_any_remote_write(self):
        for alias in ({"TimeBased": {"format": "write_%Y%m%d_events", "timezone": 0}}, {"Fixed": "fixed_events"}):
            self.remote["spec"]["nodes"][2]["write_alias"] = alias
            if self.plan_path.exists():
                self.plan_path.unlink()
            self.command()
            self.assertEqual(self.command(apply=True)[-1]["event"], "unchanged")
        self.put.assert_not_called()

    def test_plan_tampering_local_change_or_remote_target_drift_blocks_all_writes(self):
        self.command()
        original = self.plan_path.read_text()
        changed = json.loads(original)
        changed["after_spec"]["nodes"][2]["storage"]["name"] = "different_es"
        self.plan_path.write_text(json.dumps(changed))
        with self.assertRaises(CommandError):
            self.command(apply=True)
        self.plan_path.write_text(original)
        self.remote["spec"]["nodes"][2]["write_alias"]["TimeBased"]["format"] = "different_%Y%m%d_events"
        with self.assertRaises(CommandError):
            self.command(apply=True)
        self.remote["spec"] = spec()
        self.strategy.configs = {"changed_after_preview": True}
        self.strategy.save(update_record=False, update_fields=["configs"])
        with self.assertRaises(CommandError):
            self.command(apply=True)
        self.put.assert_not_called()

    def test_shared_or_soft_deleted_alias_and_busy_strategy_are_refused(self):
        alias = Strategy.objects.create(
            namespace="audit",
            strategy_name="alias",
            strategy_type=StrategyType.RULE,
            status=StrategyStatusChoices.DISABLED,
            backend_data=deepcopy(self.strategy.backend_data),
            is_deleted=True,
        )
        with self.assertRaises(CommandError):
            self.command()
        alias.backend_data = {}
        alias.save(update_record=False, update_fields=["backend_data"])
        self.strategy.backend_data["bkbase_v4"]["pending_spec"] = spec()
        self.strategy.save(update_record=False, update_fields=["backend_data"])
        with self.assertRaises(CommandError):
            self.command()
        self.get.assert_not_called()
        self.put.assert_not_called()

    def test_wrong_ref_identity_running_failed_and_unknown_timezone_are_refused(self):
        original = deepcopy(self.remote)
        mutations = [
            lambda r: r["metadata"].update(name="other"),
            lambda r: r["metadata"]["annotations"].update(task_stopped="false"),
            lambda r: r["status"].update(phase="Failed"),
            lambda r: r["spec"]["nodes"][2]["write_alias"]["TimeBased"].pop("timezone"),
        ]
        for mutate in mutations:
            self.remote = deepcopy(original)
            mutate(self.remote)
            with self.assertRaises(CommandError):
                self.command()
        self.put.assert_not_called()

    def test_backup_failure_prevents_send_and_unknown_receipt_retains_existing_fence(self):
        self.command()
        plan = json.loads(self.plan_path.read_text())
        with self.assertRaises(OSError):
            flow_es_timezone.apply_plan(
                {"tenant": "tenant_a"}, plan, before_write=mock.Mock(side_effect=OSError("private report unavailable"))
            )
        self.put.assert_not_called()
        self.strategy.refresh_from_db()
        self.assertNotIn("flow_write", flow_operation.binding(self.strategy))
        self.put.side_effect = requests.ReadTimeout("synthetic unknown")
        with self.assertRaises(CommandError):
            self.command(apply=True)
        self.strategy.refresh_from_db()
        self.assertTrue(flow_operation.binding(self.strategy)["flow_write"]["outcome_unknown"])
        self.put.assert_called_once()
        with self.assertRaises(CommandError):
            self.command(apply=True)
        self.put.assert_called_once()

    def test_nonmatching_put_receipt_retains_fence_and_does_not_report_acceptance(self):
        self.command()
        response = deepcopy(self.remote)
        response["spec"]["nodes"][2]["write_alias"] = {"Fixed": "other_target"}
        self.put.side_effect = None
        self.put.return_value = response
        with self.assertRaises(CommandError):
            self.command(apply=True)
        self.strategy.refresh_from_db()
        self.assertTrue(flow_operation.binding(self.strategy)["flow_write"]["outcome_unknown"])
        self.assertFalse(any(event.get("event") == "accepted" for event in self.events))
        self.put.assert_called_once()

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_refuses_migration_before_platform_reads_or_writes(self):
        with self.assertRaises(CommandError):
            self.command()
        self.get.assert_not_called()
        self.put.assert_not_called()

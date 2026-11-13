"""已确认的离线历史与 DataStorage 控制面协议。"""
import datetime
from copy import deepcopy
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase, override_settings

from services.web.bkbase import flow, storage
from services.web.bkbase.common import operation_result
from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.strategy_v2.handlers.strategy_running_status import (
    RuleAuditBatchV2StrategyRunningStatusHandler,
)


@override_settings(BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="tenant_a", BKBASE_V4_NAMESPACE="project_a")
class ConfirmedBatchStorageTests(SimpleTestCase):
    def setUp(self):
        self.flow_ref = {"kind": "Flow", "tenant": "tenant_a", "namespace": "project_a", "name": "flow_a"}
        self.storage_ref = {"kind": "DataStorage", "tenant": "tenant_a", "namespace": "project_a", "name": "storage_a"}
        self.strategy = SimpleNamespace(strategy_id=1, backend_data={"bkbase_v4": {"flow": self.flow_ref}})
        self.flow_value = {
            "kind": "Flow",
            "metadata": {k: self.flow_ref[k] for k in ("tenant", "namespace", "name")},
            "spec": {"nodes": [{"kind": "BatchSqlNode", "name": "batch-a", "output": "47_job"}]},
            "status": {"phase": "Ok"},
        }

    def test_job_is_selected_from_applied_flow_output(self):
        with mock.patch.object(flow.api.bk_base_v4, "flow_get", return_value=self.flow_value):
            self.assertEqual(flow.batch_processing_id(self.strategy), "47_job")
            self.flow_value["spec"]["nodes"].append({"kind": "BatchSqlNode", "name": "batch-b", "output": "47_other"})
            with self.assertRaises(BKBaseResourceMappingError):
                flow.batch_processing_id(self.strategy)
            self.strategy.backend_data["bkbase_v4"]["output_rt_id"] = "47_job"
            self.assertEqual(flow.batch_processing_id(self.strategy), "47_job")
            self.flow_value["status"]["phase"] = "Pending"
            with self.assertRaises(BKBaseResourceMappingError):
                flow.batch_processing_id(self.strategy)

    def test_nonempty_page_uses_schedule_and_data_time_without_second_slice(self):
        handler = RuleAuditBatchV2StrategyRunningStatusHandler(
            self.strategy,
            datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc),
            datetime.datetime(2024, 1, 2, tzinfo=datetime.timezone.utc),
            2,
            3,
        )
        rows = [
            {
                "schedule_time": 1704067200000,
                "data_time": 1704063600000,
                "err_msg": "synthetic error",
                "status": "failed",
                "status_str": "失败",
            }
        ]
        with mock.patch.object(flow, "batch_processing_id", return_value="47_job"), mock.patch.object(
            flow, "dataflow_batch_status_list", return_value=rows
        ), mock.patch.object(handler, "get_risk_count_map", return_value={1704063600000: 7}):
            result = handler.get_strategy_running_status()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["risk_count"], 7)
        self.assertEqual(result[0]["status"], "failed")
        self.assertEqual(result[0]["err_msg"], "synthetic error")
        self.assertNotEqual(result[0]["schedule_time"], result[0]["data_time"])

    def test_history_without_data_time_keeps_status_and_has_no_risk(self):
        handler = RuleAuditBatchV2StrategyRunningStatusHandler(
            self.strategy,
            datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc),
            datetime.datetime(2024, 1, 2, tzinfo=datetime.timezone.utc),
            10,
            0,
        )
        rows = [
            {
                "schedule_time": 1704067200000,
                "data_time": None,
                "err_msg": "synthetic",
                "status": "failed",
                "status_str": "Execution failed",
            }
        ]
        with mock.patch.object(flow, "batch_processing_id", return_value="47_job"), mock.patch.object(
            flow, "dataflow_batch_status_list", return_value=rows
        ), mock.patch.object(handler, "get_risk_count_map", return_value={}):
            result = handler.get_strategy_running_status()
        self.assertEqual(result[0]["data_time"], "")
        self.assertEqual(result[0]["risk_count"], 0)
        self.assertEqual(result[0]["status"], "failed")

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_rule_history_keeps_legacy_consumer(self):
        self.strategy.backend_data = {"flow_id": 1}
        handler = RuleAuditBatchV2StrategyRunningStatusHandler(
            self.strategy,
            datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc),
            datetime.datetime(2024, 1, 2, tzinfo=datetime.timezone.utc),
            10,
            0,
        )
        row = {
            "schedule_time": 1704067200000,
            "data_time": 1704063600000,
            "err_msg": "",
            "status": "finished",
            "status_str": "ok",
        }
        with mock.patch.object(
            flow,
            "get_flow_graph",
            return_value={"nodes": [{"node_type": "batchv2", "result_table_ids": ["legacy_job"]}]},
        ), mock.patch.object(flow, "dataflow_batch_status_list", return_value=[row]) as history, mock.patch.object(
            handler, "get_risk_count_map", return_value={1704063600000: 5}
        ):
            result = handler.get_strategy_running_status()
        self.assertEqual(history.call_args.kwargs["processing_id"], "legacy_job")
        self.assertEqual(result[0]["risk_count"], 5)

    def test_storage_phase_and_exact_stop_marker(self):
        value = {"metadata": {"annotations": {}}, "spec": {}, "status": {"phase": "Ok", "message": ""}}
        self.assertEqual(operation_result(value, self.storage_ref, "observe")["task_state"], "running")
        value["metadata"]["annotations"]["task_stopped"] = "true"
        self.assertEqual(operation_result(value, self.storage_ref, "observe")["task_state"], "stopped")
        value["metadata"]["annotations"]["task_stopped"] = True
        self.assertEqual(operation_result(value, self.storage_ref, "observe")["task_state"], "running")
        for phase, expected in (("Pending", None), ("Reconciling", None), ("Failed", "failed")):
            value["status"]["phase"] = phase
            self.assertEqual(operation_result(value, self.storage_ref, "observe")["task_state"], expected)

    def test_storage_put_acceptance_does_not_claim_applied(self):
        resource = {
            "metadata": {**self.storage_ref, "annotations": {}},
            "spec": {},
            "status": {"phase": "Ok", "message": ""},
        }
        context = {"tenant": "tenant_a", "namespace": "project_a"}
        with mock.patch.object(storage, "resource_lock"), mock.patch.object(
            storage.api.bk_base_v4, "data_storage_get", return_value=resource
        ), mock.patch.object(storage.api.bk_base_v4, "data_storage_update", return_value=resource):
            self.assertIsNone(storage.set_storage_state(context, self.storage_ref, running=True)["task_state"])

    def test_changed_storage_waits_for_matching_applied_read(self):
        context = {"tenant": "tenant_a", "namespace": "project_a"}
        rt = {"kind": "ResultTable", "tenant": "tenant_a", "namespace": "project_a", "name": "rt"}
        cluster = {"kind": "Doris", "tenant": "tenant_a", "namespace": "project_a", "name": "cluster"}
        old = {
            "metadata": {**self.storage_ref, "annotations": {}},
            "spec": {"tableInfo": {"source": rt, "storage": cluster, "expire": 3}},
            "status": {"phase": "Ok", "message": ""},
        }
        accepted = {**old, "spec": {"tableInfo": {"source": rt, "storage": cluster, "expire": 7}}}
        owner = SimpleNamespace(bkbase_v4_resources={"storages": {"main": self.storage_ref}})
        with mock.patch.object(storage, "resource_lock"), mock.patch.object(
            storage, "update_owner_binding"
        ), mock.patch.object(storage, "get_resource_or_none", side_effect=[old, accepted]), mock.patch.object(
            storage.api.bk_base_v4, "data_storage_update", return_value=accepted
        ) as update:
            params = dict(rt_ref=rt, cluster_ref=cluster, purpose="main", config={"tableInfo": {"expire": 7}})
            self.assertIsNone(storage.ensure_storage(context, owner, **params)["task_state"])
            self.assertEqual(storage.ensure_storage(context, owner, **params)["task_state"], "running")
        update.assert_called_once()

    def test_primary_storage_converges_when_get_restores_null_index_fields(self):
        context = {"tenant": "tenant_a", "namespace": "project_a"}
        rt = {"kind": "ResultTable", "tenant": "tenant_a", "namespace": "project_a", "name": "rt"}
        cluster = {"kind": "Doris", "tenant": "tenant_a", "namespace": "project_a", "name": "cluster"}
        original = {
            "metadata": {**self.storage_ref, "annotations": {}},
            "spec": {
                "tableInfo": {"source": rt, "storage": cluster, "data_model": "primary_table", "expire": 3},
                "taskFieldSetting": {"index_fields": None},
            },
            "status": {"phase": "Ok", "message": ""},
        }
        applied = deepcopy(original)
        applied["spec"]["tableInfo"]["expire"] = 7
        owner = SimpleNamespace(bkbase_v4_resources={"storages": {"main": self.storage_ref}})
        with mock.patch.object(storage, "resource_lock"), mock.patch.object(
            storage, "update_owner_binding"
        ), mock.patch.object(storage, "get_resource_or_none", side_effect=[original, applied]), mock.patch.object(
            storage.api.bk_base_v4, "data_storage_update", return_value=applied
        ) as update:
            params = dict(
                rt_ref=rt,
                cluster_ref=cluster,
                purpose="main",
                config={"tableInfo": {"data_model": "primary_table", "expire": 7}},
            )
            self.assertIsNone(storage.ensure_storage(context, owner, **params)["task_state"])
            self.assertEqual(storage.ensure_storage(context, owner, **params)["task_state"], "running")
        update.assert_called_once()

    def test_primary_storage_removes_nonempty_legacy_index_fields(self):
        old = {"tableInfo": {"data_model": "primary_table"}, "taskFieldSetting": {"index_fields": ["obsolete"]}}
        merged = storage._merge_spec(old, {})
        self.assertNotIn("index_fields", merged["taskFieldSetting"])
        self.assertEqual(old["taskFieldSetting"]["index_fields"], ["obsolete"])

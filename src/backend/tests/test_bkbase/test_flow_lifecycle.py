"""整图创建重试、先停后改和历史部署隔离的回归。"""
from copy import deepcopy
from unittest import mock

from django.test import SimpleTestCase, TransactionTestCase, override_settings

from services.web.bkbase import flow
from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.strategy_v2.constants import StrategyStatusChoices
from services.web.strategy_v2.models import Strategy


@override_settings(BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="tenant_a", BKBASE_V4_NAMESPACE="audit")
class FlowLifecycleTests(TransactionTestCase):
    def setUp(self):
        transport = mock.patch(
            "requests.sessions.Session.request", side_effect=AssertionError("Unexpected unmocked HTTP request")
        )
        transport.start()
        self.addCleanup(transport.stop)
        self.context = {"version": "v4", "tenant": "tenant_a", "namespace": "audit"}
        self.strategy = Strategy.objects.create(namespace="audit", strategy_name="rule", backend_data={})
        self.spec = {
            "alias": "rule",
            "nodes": [{"name": "source"}, {"name": "sql", "inputs": ["source"]}],
            "operation_config": {"start_position": "continue"},
        }

    def test_retry_does_not_stop_unchanged_new_flow(self):
        remote = None

        def create(**kw):
            nonlocal remote
            remote = {"metadata": kw["metadata"], "spec": kw["spec"], "status": {"phase": "Pending"}}
            return deepcopy(remote)

        with mock.patch("services.web.bkbase.flow.resource_lock"), mock.patch(
            "services.web.bkbase.flow.get_resource_or_none", side_effect=lambda *a, **kw: deepcopy(remote)
        ), mock.patch("services.web.bkbase.flow.api.bk_base_v4.flow_create", side_effect=create) as post, mock.patch(
            "services.web.bkbase.flow.get_rule_flow_status", return_value={"task_state": None}
        ), mock.patch(
            "services.web.bkbase.flow.operate_rule_flow"
        ) as stop:
            flow.apply_rule_flow(self.context, self.strategy, self.spec)
            ref = deepcopy(self.strategy.backend_data["bkbase_v4"]["flow"])
            flow.apply_rule_flow(self.context, self.strategy, self.spec)
            post.assert_called_once()
            stop.assert_not_called()
            self.assertEqual(self.strategy.backend_data["bkbase_v4"]["flow"], ref)

    def test_graph_change_waits_for_stop_then_replaces_owned_whole_graph(self):
        ref = {"kind": "Flow", "tenant": "tenant_a", "namespace": "audit", "name": "flow_a"}
        self.strategy.backend_data = {"flow_id": 7, "bkbase_v4": {"flow": ref, "managed_nodes": ["source", "old_sql"]}}
        self.strategy.save(update_fields=["backend_data"])
        remote = {
            "metadata": {"name": "flow_a", "annotations": {"keep": "value"}},
            "spec": {
                "nodes": [{"name": "source"}, {"name": "old_sql", "inputs": ["source"]}, {"name": "other"}],
                "operation_config": {"keep": True},
                "unknown": True,
            },
            "status": {"phase": "Ok"},
        }
        with mock.patch("services.web.bkbase.flow.resource_lock"), mock.patch(
            "services.web.bkbase.flow.get_resource_or_none", return_value=remote
        ), mock.patch("services.web.bkbase.flow.api.bk_base_v4.flow_get", return_value=remote), mock.patch(
            "services.web.bkbase.flow.get_rule_flow_status",
            side_effect=[{"task_state": "running"}, {"task_state": "stopped"}, {"task_state": "stopped"}],
        ), mock.patch(
            "services.web.bkbase.flow.operate_rule_flow"
        ) as stop, mock.patch(
            "services.web.bkbase.flow.api.bk_base_v4.flow_update",
            side_effect=lambda **kw: {"metadata": kw["metadata"], "spec": kw["spec"]},
        ) as put:
            flow.apply_rule_flow(self.context, self.strategy, self.spec)
            stop.assert_called_once_with(self.context, self.strategy, action="stop")
            put.assert_not_called()
            remote["metadata"]["annotations"]["task_stopped"] = "true"
            flow.apply_rule_flow(self.context, self.strategy, self.spec)
            sent = put.call_args.kwargs
            self.assertEqual([n["name"] for n in sent["spec"]["nodes"]], ["source", "sql"])
            self.assertTrue(sent["spec"]["unknown"])
            self.assertTrue(sent["spec"]["operation_config"]["keep"])
            self.assertEqual(sent["metadata"]["annotations"], {"keep": "value", "task_stopped": "false"})
        self.strategy.refresh_from_db()
        self.assertEqual(self.strategy.backend_data["flow_id"], 7)

    def test_restart_does_not_reuse_previous_successful_deployment(self):
        """旧部署结果不能让详情读取报告本次成功或提前推进启动。"""
        ref = {"kind": "Flow", "tenant": "tenant_a", "namespace": "audit", "name": "flow_a"}
        self.strategy.backend_data = {"bkbase_v4": {"flow": ref, "requested_action": "restart"}}
        self.strategy.status = StrategyStatusChoices.RUNNING
        self.strategy.save(update_fields=["backend_data", "status"])
        old = {"task_state": "running", "engine_flow_id": 1, "deployment": {"status": "success", "id": 10}}
        remote = {"metadata": ref, "spec": self.spec, "status": {"phase": "Ok", "history_id": 10, "version": 10}}

        def receipt(**kwargs):
            return {
                **remote,
                "metadata": kwargs["metadata"],
                "status": {"phase": "Pending", "history_id": 11, "version": 11},
            }

        with mock.patch.object(flow, "resource_lock"), mock.patch.object(
            flow.api.bk_base_v4, "flow_get", return_value=remote
        ), mock.patch.object(flow.api.bk_base_v4, "flow_update", side_effect=receipt) as update, mock.patch.object(
            flow, "get_rule_flow_status", return_value=old
        ) as observe_old, mock.patch.object(
            flow.flow_operation, "enqueue"
        ):
            flow.operate_rule_flow(self.context, self.strategy, action="restart")
            self.assertEqual(flow.strategy_deploy_data(self.strategy)["status"], "other")
            update.assert_called_once()
            observe_old.assert_not_called()


@override_settings(BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="tenant_a", BKBASE_V4_NAMESPACE="audit")
class LegacyFlowBindingTests(TransactionTestCase):
    def test_old_flow_id_does_not_enable_v4_legacy_fallback(self):
        strategy = Strategy.objects.create(namespace="audit", strategy_name="rule", backend_data={"flow_id": 7})
        context = {"version": "v4", "tenant": "tenant_a", "namespace": "audit"}
        spec = {"nodes": [{"name": "source"}]}
        with mock.patch("services.web.bkbase.flow.api.bk_base.create_flow") as legacy, mock.patch(
            "services.web.bkbase.flow.api.bk_base_v4.flow_create"
        ) as create, mock.patch("services.web.bkbase.flow.api.bk_base_v4.flow_update") as update, mock.patch(
            "services.web.bkbase.flow.api.bk_base_v4.flow_get"
        ) as get:
            with self.assertRaises(BKBaseResourceMappingError):
                flow.apply_rule_flow(context, strategy, spec)
        legacy.assert_not_called()
        create.assert_not_called()
        update.assert_not_called()
        get.assert_not_called()
        strategy.refresh_from_db()
        self.assertEqual(strategy.backend_data["flow_id"], 7)
        self.assertEqual(strategy.backend_data, {"flow_id": 7})


class DorisConfigurationMergeTests(SimpleTestCase):
    def graph(self):
        return {
            "nodes": [
                {"name": "sql", "kind": "StreamNode", "config": {"sql": "SELECT old_value"}},
                {
                    "name": "store",
                    "kind": "DorisStorageNode",
                    "input": "sql",
                    "storage_config": {
                        "db": "audit",
                        "flush_timeout": 60,
                        "tokenizers": {"old": ","},
                        "support_hour_partition": True,
                    },
                },
            ]
        }

    def test_sql_only_change_preserves_undeclared_nonnull_doris_fields_without_mutating_inputs(self):
        old = self.graph()
        desired = deepcopy(old)
        desired["nodes"][0]["config"] = {"sql": "SELECT new_value"}
        desired["nodes"][1]["storage_config"] = {"db": "audit"}
        original = deepcopy((old, desired))
        result = flow._merged_spec(old, desired)
        self.assertEqual(
            result["nodes"][1]["storage_config"],
            {
                "db": "audit",
                "flush_timeout": 60,
                "tokenizers": {"old": ","},
                "support_hour_partition": True,
            },
        )
        self.assertEqual(result["nodes"][0]["config"], {"sql": "SELECT new_value"})
        self.assertEqual((old, desired), original)

    def test_explicit_values_override_old_configuration_including_empty_values(self):
        for value in (None, False, 0, [], {}):
            with self.subTest(value=value):
                desired = self.graph()
                desired["nodes"][1]["storage_config"] = {"flush_timeout": value}
                result = flow._merged_spec(self.graph(), desired)
                self.assertEqual(
                    result["nodes"][1]["storage_config"],
                    {
                        "db": "audit",
                        "flush_timeout": value,
                        "tokenizers": {"old": ","},
                        "support_hour_partition": True,
                    },
                )

    def test_nested_field_values_are_replaced_instead_of_deep_merged(self):
        desired = self.graph()
        desired["nodes"][1]["storage_config"] = {"tokenizers": {"new": ";"}}
        result = flow._merged_spec(self.graph(), desired)
        self.assertEqual(result["nodes"][1]["storage_config"]["tokenizers"], {"new": ";"})

    def test_kind_change_does_not_carry_doris_configuration_into_the_new_kind(self):
        desired = self.graph()
        desired["nodes"][1] = {"name": "store", "kind": "EsStorageNode", "input": "sql", "write_alias": None}
        result = flow._merged_spec(self.graph(), desired)
        self.assertNotIn("storage_config", result["nodes"][1])

    def test_other_storage_kind_is_not_merged_into_new_doris_configuration(self):
        old = self.graph()
        old["nodes"][1].update(kind="HdfsStorageNode", storage_config={"other": {"dataType": "parquet"}})
        desired = self.graph()
        desired["nodes"][1]["storage_config"] = {"db": "new_audit"}
        result = flow._merged_spec(old, desired)
        self.assertEqual(result["nodes"][1]["storage_config"], {"db": "new_audit"})

    def test_renaming_or_deleting_managed_doris_does_not_adopt_old_configuration(self):
        desired = self.graph()
        desired["nodes"][1].update(name="new_store", storage_config={"db": "new_audit"})
        result = flow._merged_spec(self.graph(), desired)
        self.assertEqual(result["nodes"][1]["storage_config"], {"db": "new_audit"})
        self.assertEqual([node["name"] for node in result["nodes"]], ["sql", "new_store"])
        old = self.graph()
        old["nodes"].append({"name": "external", "kind": "External"})
        result = flow._merged_spec(old, {"nodes": [old["nodes"][0]]})
        self.assertEqual([node["name"] for node in result["nodes"]], ["sql"])

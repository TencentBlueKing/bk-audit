"""V4新Doris节点的字段小写选项与存量正式配置保护。"""
from contextlib import nullcontext
from copy import deepcopy
from types import SimpleNamespace
from unittest import mock

from django.conf import settings
from django.test import SimpleTestCase, override_settings

from services.web.analyze.storage_node import DorisStorageNode
from services.web.bkbase import flow
from tests.test_bkbase import test_flow_graph_migration as graph_fixture


@override_settings(BKBASE_API_VERSION='v4')
class DorisLowercaseFieldTests(SimpleTestCase):
    def setUp(self):
        self.context = {'tenant': 'tenant_a', 'namespace': 'audit'}
        self.strategy = SimpleNamespace(namespace='audit', strategy_id=7)
        self.config = {'node_type': 'doris', 'cluster': 'legacy', 'expires': '7d'}
        self.enterContext(
            mock.patch.object(
                flow.storage_service,
                'resolve_storage_cluster',
                side_effect=lambda context, storage_type, **kwargs: graph_fixture.native_ref(
                    {'doris': 'Doris', 'es': 'ElasticSearch', 'hdfs': 'Hdfs', 'kafka': 'Kafka'}[storage_type],
                    storage_type,
                    'clusters',
                ),
            )
        )

    def build(self, existing=()):
        return flow._storage_node(
            self.context,
            self.strategy,
            self.config,
            {'doris_databases': {'doris': 'actual_db'}},
            existing_nodes=existing,
            output_rt_id='1_output',
        )

    def test_setting_is_a_boolean(self):
        self.assertIsInstance(settings.BKBASE_V4_DORIS_USE_LOWERCASE_FIELD, bool)

    def test_new_doris_flag_is_a_sibling_of_table_for_both_values(self):
        for enabled in (False, True):
            with self.subTest(enabled=enabled), override_settings(BKBASE_V4_DORIS_USE_LOWERCASE_FIELD=enabled):
                node = self.build()
                self.assertIs(node['storage_config']['use_lowercase_field'], enabled)
                self.assertIn('table', node['storage_config'])
                self.assertNotIn('use_lowercase_field', node)

    def test_existing_builder_never_defaults_or_changes_the_flag(self):
        for value in ('missing', None, False, True):
            previous, _ = graph_fixture.WholeFlowGraphTests().graph()
            config = previous['nodes'][2]['storage_config']
            if value != 'missing':
                config['use_lowercase_field'] = value
            for enabled in (True, False):
                with self.subTest(value=value, enabled=enabled), override_settings(
                    BKBASE_V4_DORIS_USE_LOWERCASE_FIELD=enabled
                ):
                    self.assertNotIn('use_lowercase_field', self.build(previous['nodes'])['storage_config'])

    def test_latest_same_target_merge_preserves_missing_null_false_true(self):
        for value in ('missing', None, False, True):
            previous, desired = graph_fixture.WholeFlowGraphTests().graph()
            old = previous['nodes'][2]['storage_config']
            if value != 'missing':
                old['use_lowercase_field'] = value
            desired['nodes'][2]['storage_config']['use_lowercase_field'] = True
            original = deepcopy((previous, desired))
            result = flow._merged_spec(previous, desired, preserve_storage_targets=True)['nodes'][2]['storage_config']
            with self.subTest(value=value):
                if value == 'missing':
                    self.assertNotIn('use_lowercase_field', result)
                else:
                    self.assertIs(result['use_lowercase_field'], value)
                self.assertEqual((previous, desired), original)

    def test_start_and_stop_keep_existing_flag_in_the_written_graph(self):
        ref = {"kind": "Flow", "tenant": "tenant_a", "namespace": "audit", "name": "existing"}
        self.strategy.backend_data = {"bkbase_v4": {"flow": ref}}
        for value in ("missing", None, False, True):
            for action in ("start", "stop"):
                spec, _ = graph_fixture.WholeFlowGraphTests().graph()
                if value != "missing":
                    spec["nodes"][2]["storage_config"]["use_lowercase_field"] = value
                current = {
                    "kind": "Flow",
                    "metadata": {**ref, "annotations": {}},
                    "spec": spec,
                    "status": {"phase": "Ok"},
                }
                original = deepcopy(current)
                with self.subTest(value=value, action=action), override_settings(
                    BKBASE_V4_DORIS_USE_LOWERCASE_FIELD=True
                ), mock.patch.object(flow, "resource_lock", side_effect=lambda *args: nullcontext()), mock.patch.object(
                    flow.api.bk_base_v4, "flow_get", return_value=current
                ), mock.patch.object(
                    flow, "_write_flow_request", return_value=current
                ) as write:
                    flow.operate_rule_flow(self.context, self.strategy, action=action)
                sent = write.call_args.kwargs["spec"]["nodes"][2]["storage_config"]
                if value == "missing":
                    self.assertNotIn("use_lowercase_field", sent)
                else:
                    self.assertIs(sent["use_lowercase_field"], value)
                self.assertEqual(current, original)

    def test_other_output_on_same_cluster_is_a_new_target(self):
        previous, _ = graph_fixture.WholeFlowGraphTests().graph()
        previous['nodes'][1]['output'] = '1_another_output'
        previous['nodes'][2]['storage_config']['use_lowercase_field'] = False
        with override_settings(BKBASE_V4_DORIS_USE_LOWERCASE_FIELD=True):
            self.assertIs(self.build(previous['nodes'])['storage_config']['use_lowercase_field'], True)

    def test_other_storage_kinds_do_not_receive_the_flag(self):
        for node_type in ('elastic_storage', 'hdfs_storage', 'queue_storage'):
            self.config['node_type'] = node_type
            with self.subTest(kind=node_type), override_settings(BKBASE_V4_DORIS_USE_LOWERCASE_FIELD=True):
                self.assertNotIn('use_lowercase_field', str(self.build()))

    @override_settings(BKBASE_API_VERSION='v3', BKBASE_V4_DORIS_USE_LOWERCASE_FIELD=True)
    def test_v3_business_storage_payload_is_unchanged(self):
        with mock.patch.object(
            DorisStorageNode, 'cluster', new_callable=mock.PropertyMock, return_value='legacy'
        ), mock.patch('services.web.analyze.storage_node.GlobalMetaConfig.get', return_value='db.events'):
            config = DorisStorageNode('audit').build_node_config(1, 'output', ['1_input'])
        self.assertNotIn('use_lowercase_field', str(config))

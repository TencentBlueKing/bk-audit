"""C57：项目可见视角、正式RT归属与输入Binding能力分别校验。"""
import json
from copy import deepcopy
from types import SimpleNamespace
from unittest import mock
from urllib.parse import urlparse

import requests
from bk_resource.exceptions import APIRequestError
from bk_resource.utils.cache import UsingCache
from django.test import SimpleTestCase, override_settings

from services.web.analyze.constants import FlowDataSourceNodeType
from services.web.analyze.controls.rule_audit import RuleAuditController
from services.web.bkbase import flow, metadata
from services.web.bkbase.exceptions import BKBaseReadTimeout, BKBaseResourceMappingError
from services.web.strategy_v2 import resources
from services.web.strategy_v2.constants import RuleAuditConfigType
from tests.test_bkbase import test_project_lazy_loading as project_fixtures


@override_settings(
    BKBASE_API_VERSION="v4",
    BKBASE_V4_TENANT="default",
    BKBASE_V4_NAMESPACE="audit",
    BKBASE_V4_RESULT_TABLE_NAMESPACES={},
    APP_CODE="synthetic_app",
    SECRET_KEY="synthetic_secret",
    PLATFORM_AUTH_ACCESS_USERNAME="synthetic_admin",
    BK_RESOURCE={
        "PLATFORM_AUTH_ENABLED": True,
        "PLATFORM_AUTH_ACCESS_USERNAME": "synthetic_admin",
        "PLATFORM_AUTH_ACCESS_TOKEN": "synthetic_platform_token",
    },
)
class CrossProjectCandidateTests(SimpleTestCase):
    sample = "2_jordan_test_split_v3_1"
    normal = "47_normal"
    rt_id = staticmethod(project_fixtures.ProjectLazyLoadingTests.rt_id)
    row = project_fixtures.ProjectLazyLoadingTests.row
    request_resource = project_fixtures.ProjectLazyLoadingTests.request_resource

    def setUp(self):
        project_fixtures.ProjectLazyLoadingTests.setUp(self)
        self.calls = []
        self.rows = {
            "bkbase": [
                self.dataset(self.sample, "channel"),
                self.dataset(self.sample, "tspider"),
                self.dataset(self.normal, "channel"),
            ]
        }
        self.formal = {
            self.sample: self.result(self.sample, "project_v3_1024", "TspiderBinding", binding_namespace="bkbase"),
            self.normal: self.result(self.normal, "bkbase", "ChannelBinding"),
        }
        self.failure = None
        self.page_incomplete = False

    @staticmethod
    def dataset(rt_id, storage, *, query=True):
        return {"dataset_name": rt_id, "dataset_alias": rt_id, "storage_type": storage, "permissions": {"query": query}}

    @staticmethod
    def result(rt_id, namespace, binding_kind, *, binding_namespace=None):
        # 精确现场样例没有root kind；Tspider的data Ref在bkbase，不能拿来证明channel。
        ref = {"kind": "ResultTable", "tenant": "default", "namespace": namespace, "name": rt_id}
        binding_namespace = binding_namespace or namespace
        return {
            "metadata": {
                "tenant": "default",
                "namespace": namespace,
                "name": rt_id,
                "labels": {"result_table_id": rt_id},
            },
            "spec": {"bizId": int(rt_id.split("_", 1)[0]), "predefiendResultTableId": rt_id},
            "status": {
                "phase": "Ok",
                "related": [
                    {
                        "kind": binding_kind,
                        "metadata": {"tenant": "default", "namespace": binding_namespace, "name": rt_id},
                        "spec": {"data": {**ref, "namespace": binding_namespace}},
                        "status": {"phase": "Ok"},
                    }
                ],
            },
        }

    def transport(self, method, url, **kwargs):
        self.assertEqual(method, "GET")
        auth = json.loads(kwargs["headers"]["x-bkapi-authorization"])
        self.assertEqual(auth["bk_username"], "synthetic_admin")
        self.assertNotIn("cookie", {key.lower() for key in kwargs["headers"]})
        self.assertEqual(kwargs["headers"]["X-Bk-Tenant-Id"], "default")
        path = urlparse(url).path
        params = kwargs.get("params", {})
        namespace, rt_id = None, None
        if "/v4/result_tables/" in path:
            kind = "formal"
            rt_id = path.rstrip("/").rsplit("/", 1)[1]
            data = deepcopy(self.formal[rt_id])
        else:
            namespace = path.split("/dataset/", 1)[1].split("/", 1)[0]
            if path.endswith("/dataset_list/"):
                kind = "page"
                if params.get("dataset_name"):
                    data_rows = [r for r in self.rows["bkbase"] if r["dataset_name"] == params["dataset_name"]]
                else:
                    self.assertEqual(namespace, "bkbase")
                    data_rows = self.rows["bkbase"]
                data = {"total": 101 if self.page_incomplete else len(data_rows), "list": deepcopy(data_rows)}
            else:
                kind = "channel" if params.get("storage_type") == "channel" else "detail"
                rt_id = path.rstrip("/").rsplit("/", 1)[1]
                self.assertEqual(namespace, self.formal[rt_id]["metadata"]["namespace"])
                binding = self.formal[rt_id]["status"]["related"][0]
                storage = "channel" if binding["kind"] == "ChannelBinding" else "tspider"
                data = {
                    "dataset_name": rt_id,
                    "dataset_alias": rt_id,
                    "fields": [],
                    "kind": binding["kind"] if storage == "channel" else None,
                    "storage_type": storage if storage == "channel" else None,
                }
        self.calls.append({"kind": kind, "rt_id": rt_id, "namespace": namespace, "params": deepcopy(params)})
        response = requests.Response()
        response.url = url
        response.request = requests.Request(method, url).prepare()
        if self.failure and (kind, rt_id) == self.failure[:2]:
            if self.failure[2] == "timeout":
                raise requests.Timeout("synthetic timeout")
            response.status_code = self.failure[2]
            payload = {
                "result": False,
                "code": "1558025" if response.status_code == 404 else "1500000",
                "data": {},
                "message": "synthetic failure",
            }
        else:
            response.status_code = 200
            payload = {"result": True, "code": "00", "data": data}
        response._content = json.dumps(payload).encode()
        return response

    def select(self, *, table_type="BizRt", **extra):
        return self.request_resource(
            "ListProjectTables", namespace="audit", bkbase_namespace="bkbase", table_type=table_type, **extra
        )

    def test_exact_cross_project_tspider_sample_does_not_break_healthy_same_project_table(self):
        with mock.patch("services.web.bkbase.metadata.logger.warning") as warning:
            result = self.select()
        self.assertEqual([r["value"] for r in result], [self.normal])
        self.assertEqual(sum(c["kind"] == "formal" and c["rt_id"] == self.sample for c in self.calls), 1)
        self.assertTrue(any(c["kind"] == "channel" and c["namespace"] == "project_v3_1024" for c in self.calls))
        self.assertTrue(warning.called)
        self.assertNotIn(self.sample, str(warning.call_args_list))

    def test_cross_project_supported_input_deduplicates_views_and_uses_formal_owner(self):
        self.formal[self.sample] = self.result(self.sample, "project_v3_1024", "ChannelBinding")
        result = self.select()
        self.assertEqual([r["value"] for r in result], [self.sample, self.normal])
        self.assertTrue(all(r["namespace"] == "bkbase" for r in result))
        self.assertEqual(sum(c["kind"] == "formal" and c["rt_id"] == self.sample for c in self.calls), 1)
        self.assertTrue(
            all(
                c["namespace"] == "project_v3_1024"
                for c in self.calls
                if c["rt_id"] == self.sample and c["kind"] in ("detail", "channel")
            )
        )

    def test_cross_project_asset_uses_valid_redis_binding(self):
        self.formal[self.sample] = self.result(self.sample, "project_v3_1024", "RedisBinding")
        self.assertEqual([r["value"] for r in self.select(table_type="BuildIn")], [self.sample])

    def test_project_isolates_wrong_binding_but_direct_capability_still_rejects_it(self):
        for kind in ("ChannelBinding", "RedisBinding", "HdfsBinding"):
            with self.subTest(kind=kind):
                self.formal[self.sample] = self.result(self.sample, "project_v3_1024", kind, binding_namespace="bkbase")
                self.assertEqual([r["value"] for r in self.select()], [self.normal])
                with self.assertRaises(BKBaseResourceMappingError):
                    metadata.get_source_capabilities(self.sample)

    def test_unconfirmed_formal_identity_is_isolated_and_not_cached_as_complete_project(self):
        self.formal[self.sample]["metadata"]["tenant"] = "other_tenant"
        store = {}
        with mock.patch.object(UsingCache, "get_value", side_effect=lambda key: store.get(key)), mock.patch.object(
            UsingCache, "set_value", side_effect=lambda key, value, timeout: store.update({key: value})
        ), mock.patch("services.web.bkbase.metadata.logger.warning") as warning:
            endpoint = resources.ListProjectTables()
            for _ in range(2):
                result = endpoint.request(namespace="audit", bkbase_namespace="bkbase", table_type="BizRt")
                self.assertEqual([r["value"] for r in result], [self.normal])
        self.assertEqual(store, {})
        self.assertEqual(sum(c["kind"] == "page" for c in self.calls), 2)
        self.assertTrue(warning.called)
        self.assertNotIn(self.sample, str(warning.call_args_list))
        self.assertNotIn("other_tenant", str(warning.call_args_list))

    def test_cache_modes_do_not_store_invalid_binding_and_recover_on_next_request(self):
        store = {}
        with mock.patch.object(UsingCache, "get_value", side_effect=lambda key: store.get(key)), mock.patch.object(
            UsingCache, "set_value", side_effect=lambda key, value, timeout: store.update({key: value})
        ):
            endpoint = resources.ListProjectTables()
            params = {"namespace": "audit", "bkbase_namespace": "bkbase", "table_type": "BizRt"}
            for mode in (
                endpoint.request,
                endpoint.request.cached,
                endpoint.request.refresh,
                endpoint.request.cacheless,
            ):
                self.formal[self.sample] = self.result(
                    self.sample, "project_v3_1024", "ChannelBinding", binding_namespace="bkbase"
                )
                self.assertEqual([r["value"] for r in mode(**params)], [self.normal])
                self.assertEqual(store, {})
            self.formal[self.sample] = self.result(self.sample, "project_v3_1024", "ChannelBinding")
            self.assertEqual([r["value"] for r in endpoint.request(**params)], [self.sample, self.normal])
            self.assertEqual(len(store), 1)
            self.calls.clear()
            self.assertEqual([r["value"] for r in endpoint.request(**params)], [self.sample, self.normal])
            self.assertEqual(self.calls, [])

    def test_missing_formal_or_dataset_is_local_but_permission_server_errors_and_timeouts_are_global(self):
        for stage in ("formal", "detail"):
            with self.subTest(missing=stage):
                self.failure = (stage, self.sample, 404)
                self.assertEqual([r["value"] for r in self.select()], [self.normal])
            for status in (403, 500, "timeout"):
                with self.subTest(stage=stage, status=status):
                    self.failure = (stage, self.sample, status)
                    with self.assertRaises((APIRequestError, BKBaseReadTimeout)):
                        self.select()

    def test_channel_list_entry_cannot_promote_tspider_and_missing_channel_keeps_other_tables(self):
        self.failure = ("channel", self.sample, 404)
        self.assertEqual([r["value"] for r in self.select()], [self.normal])

    def test_permissions_scene_intersection_and_page_failure_still_precede_candidate_expansion(self):
        self.rows["bkbase"][0]["permissions"]["query"] = False
        self.rows["bkbase"][1]["permissions"]["query"] = False
        self.assertEqual([r["value"] for r in self.select()], [self.normal])
        self.assertFalse(any(c["kind"] == "formal" and c["rt_id"] == self.sample for c in self.calls))
        self.calls.clear()
        with mock.patch("services.web.scene.data_filter.SceneDataFilter.get_table_ids", return_value=[]):
            self.assertEqual(self.select(scene_id=5), [])
        self.assertFalse(any(c["kind"] == "formal" for c in self.calls))
        self.page_incomplete = True
        self.calls.clear()
        with self.assertRaises(BKBaseResourceMappingError):
            self.select()
        self.assertFalse(any(c["kind"] == "formal" for c in self.calls))

    @override_settings(BKBASE_V4_STREAM_CLUSTER="synthetic_stream")
    def test_selected_cross_project_table_builds_graph_with_authoritative_ref(self):
        self.formal[self.sample] = self.result(self.sample, "project_v3_1024", "ChannelBinding")
        selected = self.select()
        self.assertIn(self.sample, [r["value"] for r in selected])
        context = {"version": "v4", "tenant": "default", "namespace": "bkbase", "rt_namespaces": {}}
        strategy = SimpleNamespace(
            strategy_id=7,
            strategy_name="synthetic",
            namespace="audit",
            sql=f"SELECT * FROM {self.sample}",
            backend_data={},
            configs={
                "config_type": RuleAuditConfigType.BIZ_RT.value,
                "data_source": {"source_type": FlowDataSourceNodeType.REALTIME},
            },
        )
        controller = SimpleNamespace(
            strategy=strategy,
            event_log_rt_id=self.normal,
            rt_ids=[self.sample],
            storage_nodes=[],
            _build_sql_node_config=lambda biz: {"node_type": "realtime"},
        )
        controller.check_source_type = lambda rt: RuleAuditController.check_source_type(controller, rt)
        with mock.patch.object(flow, "get_bkbase_context", return_value=context), mock.patch.object(
            flow.GlobalMetaConfig, "get", return_value={"operation_config": {"start_position": "continue"}}
        ), mock.patch.object(flow.CollectorPlugin.objects, "filter") as plugin, mock.patch.object(
            flow.CollectorConfig.objects, "filter"
        ) as collector, mock.patch.object(
            flow.Snapshot.objects, "filter"
        ) as snapshot, mock.patch.object(
            flow, "_save_operation_binding"
        ):
            for query in (plugin, collector, snapshot):
                query.return_value.values_list.return_value = []
            graph = flow.build_controller_spec(controller, context=context)
            self.formal[self.sample] = self.result(
                self.sample, "project_v3_1024", "ChannelBinding", binding_namespace="bkbase"
            )
            with self.assertRaises(BKBaseResourceMappingError):
                flow.build_controller_spec(controller, context=context)
        source = next(node for node in graph["nodes"] if node["kind"] == "StreamSourceNode")
        self.assertEqual(
            source["data"],
            {"kind": "ResultTable", "tenant": "default", "namespace": "project_v3_1024", "name": self.sample},
        )

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_new_project_api_still_does_not_read_v4(self):
        with self.assertRaises(BKBaseResourceMappingError):
            self.select()
        self.assertEqual(self.calls, [])

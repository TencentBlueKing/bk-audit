"""项目懒加载经 Resource、SDK 和隔离 HTTP 运输层验证。"""
import threading
import time
from unittest import mock

from bk_resource.exceptions import ValidateException
from bk_resource.utils.cache import UsingCache
from django.test import SimpleTestCase, override_settings
from rest_framework.request import Request

from apps.permission.handlers.actions import ActionEnum
from apps.permission.handlers.drf import InstanceActionPermission
from services.web.bkbase import metadata
from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.strategy_v2 import resources, views
from services.web.strategy_v2.utils import table
from tests.test_bkbase import test_list_performance as fixtures


@override_settings(
    BKBASE_API_VERSION="v4",
    BKBASE_V4_TENANT="tenant_a",
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
class ProjectLazyLoadingTests(SimpleTestCase):
    # 复用合成平台运输层，不继承旧类的全部测试。
    setUp = fixtures.ListPerformanceTests.setUp
    rt_id = staticmethod(fixtures.ListPerformanceTests.rt_id)
    row = fixtures.ListPerformanceTests.row
    transport = fixtures.ListPerformanceTests.transport

    def result_table(self, index):
        result = fixtures.ListPerformanceTests.result_table(self, index)
        namespace = "project_999" if index < 101 else "shared"
        result["metadata"]["namespace"] = namespace
        for binding in result["status"]["related"]:
            binding["spec"]["data"]["namespace"] = namespace
        return result

    def request_resource(self, name, **params):
        cls = getattr(resources, name)
        with mock.patch.object(cls, "_need_cache_wrap", return_value=False):
            return cls().request(**params)

    def test_directory_only_reads_namespaces_and_has_exact_contract(self):
        data = self.request_resource("ListTableProjects", namespace="default")
        self.assertEqual(
            data, [dict(label=n, value=n, namespace=n, node_type="project", leaf=False) for n in sorted(self.projects)]
        )
        self.assertEqual([c["kind"] for c in self.calls], ["NamespacesList"])

    def test_missing_or_invalid_project_never_calls_bkbase(self):
        for params in ({}, {"bkbase_namespace": ""}, {"bkbase_namespace": "a/b"}):
            with self.subTest(params=params), self.assertRaises(ValidateException):
                self.request_resource("ListProjectTables", namespace="default", table_type="BizRt", **params)
        self.assertEqual(self.calls, [])

    def test_single_project_complete_flat_response_and_shared_budget(self):
        data = self.request_resource(
            "ListProjectTables", namespace="default", table_type="BizRt", bkbase_namespace="project_999"
        )
        self.assertEqual(
            data,
            [
                dict(
                    label=f"Alias {i}",
                    value=self.rt_id(i),
                    table_id=self.rt_id(i),
                    namespace="project_999",
                    node_type="table",
                    leaf=True,
                )
                for i in range(62)
            ],
        )
        lists = [c for c in self.calls if c["kind"] == "DatasetList"]
        self.assertEqual([c["params"]["page"] for c in lists], [1, 2])
        self.assertTrue(all("/project_999/" in c["path"] for c in lists))
        self.assertFalse(any(c["kind"] == "NamespacesList" for c in self.calls))
        self.assertEqual(len({c["deadline"] for c in self.calls}), 1)
        self.assertIsNotNone(self.calls[0]["deadline"])

    def test_query_true_dedup_and_exclusions_precede_binding_reads(self):
        self.rows["project_999"] = [
            self.row(0),
            self.row(0, storage="hdfs"),
            self.row(1, query=False),
            self.row(2, query="true"),
            self.row(3),
        ]
        with mock.patch.object(table.BizRtTableHandler, "get_exclude_rt_ids", return_value={self.rt_id(3)}):
            data = self.request_resource(
                "ListProjectTables", namespace="default", table_type="BizRt", bkbase_namespace="project_999"
            )
        self.assertEqual([row["value"] for row in data], [self.rt_id(0)])
        details = [c["path"] for c in self.calls if c["kind"] == "ResultTableInfo"]
        self.assertEqual(len(details), 1)
        self.assertIn(self.rt_id(0), details[0])

    def test_later_page_failure_never_returns_partial_success(self):
        original = metadata._dataset_page

        def fail(*args, **kwargs):
            if args[1] == 2:
                raise BKBaseResourceMappingError(message="synthetic failure")
            return original(*args, **kwargs)

        with mock.patch.object(metadata, "_dataset_page", side_effect=fail), self.assertRaises(
            BKBaseResourceMappingError
        ):
            self.request_resource(
                "ListProjectTables", namespace="default", table_type="BizRt", bkbase_namespace="project_999"
            )

    def test_scene_intersection_is_applied_before_binding_reads(self):
        with mock.patch("services.web.scene.data_filter.SceneDataFilter.get_table_ids", return_value=[self.rt_id(1)]):
            data = self.request_resource(
                "ListProjectTables", namespace="default", table_type="BizRt", bkbase_namespace="project_999", scene_id=8
            )
        self.assertEqual([row["value"] for row in data], [self.rt_id(1)])
        self.assertEqual(len([c for c in self.calls if c["kind"] == "ResultTableInfo"]), 1)

    def test_scene_echo_reads_finite_ids_without_namespace_or_unfiltered_scan(self):
        # 精确查询的 API 可模糊匹配，服务必须再做逻辑 ID 和 query=True 校验。
        def exact_datasets(context, **kwargs):
            wanted = kwargs["dataset_name"]
            return [self.row(0), self.row(1), {**self.row(2), "dataset_name": wanted + "_suffix"}]

        with mock.patch(
            "services.web.scene.data_filter.SceneDataFilter.get_table_ids", return_value=[self.rt_id(1)]
        ), mock.patch.object(metadata, "list_datasets", side_effect=exact_datasets) as dataset:
            data = resources.GetScenePermissionTables().request(scene_id=8, table_type="BizRt")
        self.assertEqual(data[0]["children"], [dict(label="Alias 1", value=self.rt_id(1))])
        dataset.assert_called_once()
        self.assertEqual(dataset.call_args.kwargs["dataset_name"], self.rt_id(1))
        self.assertEqual(dataset.call_args.args[0]["namespace"], "project_999")
        self.assertFalse(any(c["kind"] in ("NamespacesList", "DatasetList") for c in self.calls))

    def test_scene_read_failure_propagates_and_empty_scene_reads_nothing(self):
        with mock.patch("services.web.scene.data_filter.SceneDataFilter.get_table_ids", return_value=[]):
            self.assertEqual(resources.GetScenePermissionTables().request(scene_id=8, table_type="BizRt"), [])
        self.assertEqual(self.calls, [])
        with mock.patch(
            "services.web.scene.data_filter.SceneDataFilter.get_table_ids", return_value=[self.rt_id(1)]
        ), mock.patch.object(metadata, "get_result_table_ref", side_effect=BKBaseResourceMappingError(message="fail")):
            with self.assertRaises(BKBaseResourceMappingError):
                resources.GetScenePermissionTables().request(scene_id=8, table_type="BizRt")

    def test_rt_meta_resolves_formal_namespace_despite_wrong_configured_mapping(self):
        with override_settings(BKBASE_V4_RESULT_TABLE_NAMESPACES={self.rt_id(1): "wrong_project"}):
            value = resources.GetRTMeta().get_meta(self.rt_id(1))
        self.assertEqual(value["bkbase_namespace"], "project_999")
        self.assertTrue(any("/project_999/" in c["path"] for c in self.calls if c["kind"] == "DatasetDetail"))

    @override_settings(BKBASE_API_VERSION="v3")
    def test_new_routes_do_not_probe_or_scan_in_v3(self):
        with self.assertRaises(BKBaseResourceMappingError):
            self.request_resource("ListTableProjects", namespace="default")
        self.assertEqual(self.calls, [])

    def test_buildin_uses_asset_bindings(self):
        data = self.request_resource(
            "ListProjectTables", namespace="default", table_type="BuildIn", bkbase_namespace="project_999"
        )
        self.assertEqual([rt["value"] for rt in data], [self.rt_id(i) for i in range(0, 101, 2)])

    def test_scene_query_denied_table_is_not_expanded_to_binding(self):
        with mock.patch(
            "services.web.scene.data_filter.SceneDataFilter.get_table_ids", return_value=[self.rt_id(1)]
        ), mock.patch.object(metadata, "list_datasets", return_value=[self.row(1, query=False)]), mock.patch.object(
            metadata, "get_result_tables_with_capabilities", wraps=metadata.get_result_tables_with_capabilities
        ) as caps:
            self.assertEqual(resources.GetScenePermissionTables().request(scene_id=8, table_type="BizRt"), [])
        self.assertEqual(caps.call_args.args[0], [])

    @override_settings(BKBASE_V4_LIST_READ_WORKERS=3)
    def test_binding_stage_is_bounded_and_uses_original_request_budget(self):
        active, peak, deadlines = 0, 0, set()
        lock = threading.Lock()
        original = metadata.get_source_capabilities

        def observe(*args, **kwargs):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
                deadlines.add(metadata.READ_DEADLINE.get())
            try:
                time.sleep(0.002)
                return original(*args, **kwargs)
            finally:
                with lock:
                    active -= 1

        with mock.patch.object(metadata, "get_source_capabilities", side_effect=observe):
            self.request_resource(
                "ListProjectTables", namespace="default", table_type="BizRt", bkbase_namespace="project_999"
            )
        self.assertGreater(peak, 1)
        self.assertLessEqual(peak, 3)
        self.assertEqual(active, 0)
        self.assertEqual(deadlines, {self.calls[0]["deadline"]})

    def test_resource_cache_partitions_all_scopes_and_does_not_store_failures(self):
        store = {}

        def save(key, value, timeout):
            store[key] = value

        with mock.patch.object(UsingCache, "get_value", side_effect=lambda key: store.get(key)), mock.patch.object(
            UsingCache, "set_value", side_effect=save
        ), mock.patch(
            "bk_resource.utils.cache.get_request_username", return_value="user_a"
        ) as username, mock.patch.object(
            resources, "list_scoped_v4_tables", return_value=[]
        ) as scoped:
            base = dict(namespace="default", table_type="BizRt", bkbase_namespace="project_999")
            endpoint = resources.ListProjectTables()
            endpoint.request(**base)
            endpoint.request(**base)
            self.assertEqual(scoped.call_count, 1)
            for changes in (
                {"namespace": "other"},
                {"table_type": "BuildIn"},
                {"bkbase_namespace": "shared"},
                {"scene_id": 8},
            ):
                endpoint.request(**{**base, **changes})
            username.return_value = "user_b"
            endpoint.request(**base)
            with override_settings(BKBASE_V4_TENANT="tenant_b"):
                resources.ListProjectTables().request(**base)
            with override_settings(BKBASE_API_VERSION="v3"):
                resources.ListProjectTables().request(**base)
            self.assertEqual(scoped.call_count, 8)
            self.assertEqual(len(store), 8)
            self.assertTrue(all("[user_" in key for key in store))
            before = len(store)
            scoped.side_effect = BKBaseResourceMappingError(message="fail")
            for _ in range(2):
                with self.assertRaises(BKBaseResourceMappingError):
                    endpoint.request(**{**base, "bkbase_namespace": "failed"})
            self.assertEqual(len(store), before)
            self.assertEqual(scoped.call_count, 10)

    def test_project_routes_use_scene_manage_permission_for_scene_requests(self):

        for action in ("projects", "project_tables"):
            view = views.StrategyTableViewSet()
            view.action = action
            self.request.GET = self.request.GET.copy()
            self.request.GET["scene_id"] = "8"
            view.request = Request(self.request)
            with mock.patch.object(views, "InstanceActionPermission", wraps=InstanceActionPermission) as permission:
                view.get_permissions()
            self.assertEqual(permission.call_args.kwargs["actions"], [ActionEnum.MANAGE_SCENE])
            self.assertEqual(permission.call_args.kwargs["get_instance_id"](), "8")
            self.request.GET.clear()
            with mock.patch.object(views, "InstanceActionPermission") as permission:
                view.get_permissions()
            permission.assert_not_called()

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_scene_endpoint_keeps_legacy_group_filter_and_error_behavior(self):
        groups = [
            {
                "label": "Biz",
                "value": "47",
                "children": [{"label": "Chosen", "value": self.rt_id(1)}, {"label": "Other", "value": self.rt_id(2)}],
            }
        ]
        with mock.patch(
            "services.web.scene.data_filter.SceneDataFilter.get_table_ids", return_value=[self.rt_id(1)]
        ), mock.patch.object(table.BizRtTableHandler, "list_tables", return_value=groups) as legacy:
            data = resources.GetScenePermissionTables().request(scene_id=8, table_type="BizRt")
            self.assertEqual(
                data, [{"label": "Biz", "value": "47", "children": [{"label": "Chosen", "value": self.rt_id(1)}]}]
            )
            legacy.side_effect = BKBaseResourceMappingError(message="legacy failure")
            self.assertEqual(resources.GetScenePermissionTables().request(scene_id=8, table_type="BizRt"), [])
        self.assertEqual(self.calls, [])

    def test_rt_meta_does_not_reuse_cached_v4_payload_without_formal_project(self):
        old_payload = {"fields": [], "formatted_fields": []}

        def read_cache(key):
            if key.startswith("web_cache:GetRTMeta:v4:tenant_a:services."):
                return old_payload
            return None

        with mock.patch.object(UsingCache, "get_value", side_effect=read_cache), mock.patch.object(
            UsingCache, "set_value"
        ), mock.patch.object(
            resources.GetRTMeta, "get_meta", return_value={"fields": [], "bkbase_namespace": "actual"}
        ), mock.patch.object(
            resources.GetRTMeta, "get_data_manager", return_value={}
        ), mock.patch.object(
            resources.GetRTMeta, "get_sensitivity_info", return_value={}
        ), mock.patch.object(
            table.GlobalMetaConfig, "get", return_value=None
        ):
            result = resources.GetRTMeta().request(table_id=self.rt_id(1))
        self.assertEqual(result["bkbase_namespace"], "actual")

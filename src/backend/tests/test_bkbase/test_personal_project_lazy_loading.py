"""个人项目选表通过真实Resource/SDK运输层验证，禁止全租户或平台回退。"""
from unittest import mock

from bk_resource.exceptions import ValidateException
from bk_resource.utils.cache import UsingCache
from django.core.exceptions import PermissionDenied
from django.test import SimpleTestCase, override_settings
from rest_framework.request import Request

from services.web.bkbase import metadata, permissions
from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.strategy_v2 import resources, views
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
class PersonalProjectLazyLoadingTests(SimpleTestCase):
    rt_id = staticmethod(fixtures.ListPerformanceTests.rt_id)
    row = fixtures.ListPerformanceTests.row
    result_table = fixtures.ListPerformanceTests.result_table
    transport = fixtures.ListPerformanceTests.transport

    def setUp(self):
        fixtures.ListPerformanceTests.setUp(self)
        self.enterContext(
            mock.patch.object(
                permissions, "get_request_username", create=True, side_effect=lambda: self.request.user.bk_username
            )
        )

    def request_resource(self, name, **params):
        cls = getattr(resources, name)
        with mock.patch.object(cls, "_need_cache_wrap", return_value=False):
            return cls().request(table_type="MineBizRt", namespace="default", **params)

    def test_directory_calls_only_user_namespaces_with_the_authenticated_request(self):
        result = self.request_resource("ListTableProjects")
        self.assertEqual(
            result,
            [dict(label=n, value=n, namespace=n, node_type="project", leaf=False) for n in sorted(self.projects)],
        )
        self.assertEqual([c["kind"] for c in self.calls], ["UserNamespacesList"])
        self.assertTrue(all(call.args[0] is self.request for call in self.auth.call_args_list))

    def test_single_project_fully_pages_as_same_user_without_binding_or_other_projects(self):
        result = self.request_resource("ListProjectTables", bkbase_namespace="project_999")
        self.assertEqual([row["value"] for row in result], [self.rt_id(i) for i in range(101)])
        self.assertTrue(all(row["namespace"] == "project_999" and row["table_id"] == row["value"] for row in result))
        self.assertEqual([c["kind"] for c in self.calls], ["UserNamespacesList", "UserDatasetList", "UserDatasetList"])
        datasets = [c for c in self.calls if c["kind"] == "UserDatasetList"]
        self.assertEqual([c["params"]["page"] for c in datasets], [1, 2])
        self.assertTrue(all('/project_999/' in c['path'] for c in datasets))
        self.assertTrue(all(call.args[0] is self.request for call in self.auth.call_args_list))
        self.assertEqual(len({c["deadline"] for c in self.calls}), 1)

    def test_strict_query_true_and_logical_id_dedup_preserve_personal_scope(self):
        self.rows["project_999"] = [
            self.row(0),
            self.row(0, storage="hdfs"),
            self.row(1, query=False),
            self.row(2, query="true"),
            self.row(3, query=1),
            self.row(4),
        ]
        result = self.request_resource("ListProjectTables", bkbase_namespace="project_999")
        self.assertEqual([row["value"] for row in result], [self.rt_id(0), self.rt_id(4)])
        self.assertFalse(any(c["kind"] in ("ResultTableInfo", "DatasetDetail", "ChannelDetail") for c in self.calls))

    def test_direct_unauthorized_namespace_is_rejected_before_any_dataset_read(self):
        for namespace in ("unlisted_actual_namespace", "47"):
            with self.subTest(namespace=namespace), self.assertRaises(PermissionDenied):
                self.request_resource("ListProjectTables", bkbase_namespace=namespace)
        self.assertEqual([c["kind"] for c in self.calls], ["UserNamespacesList", "UserNamespacesList"])

    def test_request_cannot_select_another_tenant_or_user(self):
        self.request_resource("ListTableProjects", tenant="other", bk_username="spoofed")
        self.assertEqual([c["kind"] for c in self.calls], ["UserNamespacesList"])
        # 合成运输层逐次断言tenant_a及当前user_a身份，不能使用外部参数身份。
        self.assertTrue(all(call.args[0] is self.request for call in self.auth.call_args_list))

    def test_missing_authentication_never_falls_back_to_platform(self):
        self.request.user.is_authenticated = False
        with self.assertRaises(PermissionDenied):
            self.request_resource("ListTableProjects")
        self.assertEqual(self.calls, [])

    def test_failure_of_later_page_is_not_partial_success(self):
        original = metadata._dataset_page

        def read(*args, **kwargs):
            if args[1] == 2:
                raise BKBaseResourceMappingError(message="synthetic page failure")
            return original(*args, **kwargs)

        with mock.patch.object(metadata, "_dataset_page", side_effect=read), self.assertRaises(
            BKBaseResourceMappingError
        ):
            self.request_resource("ListProjectTables", bkbase_namespace="project_999")

    def test_personal_tables_keep_existing_scene_outside_table_selection_semantics(self):
        with mock.patch(
            'services.web.scene.data_filter.SceneDataFilter.get_table_ids',
            side_effect=AssertionError('personal tables do not intersect scene'),
        ):
            result = self.request_resource("ListProjectTables", bkbase_namespace="project_999", scene_id=8)
        self.assertEqual(len(result), 101)

    def test_personal_project_routes_keep_existing_strategy_permission_in_scene(self):
        self.request.GET = self.request.GET.copy()
        self.request.GET.update(scene_id="8", table_type="MineBizRt")
        for action in ("projects", "project_tables"):
            view = views.StrategyTableViewSet()
            view.action = action
            view.request = Request(self.request)
            with mock.patch.object(views, "InstanceActionPermission") as scene_manage, mock.patch.object(
                views, "AnyOfPermissions"
            ) as strategy_permission:
                view.get_permissions()
            scene_manage.assert_not_called()
            strategy_permission.assert_called_once()

    def test_invalid_project_is_rejected_before_bkbase(self):
        for params in ({}, {"bkbase_namespace": ""}, {"bkbase_namespace": "a/b"}):
            with self.subTest(params=params), self.assertRaises(ValidateException):
                self.request_resource("ListProjectTables", **params)
        self.assertEqual(self.calls, [])

    def test_users_do_not_share_personal_permissions(self):
        self.request.user.bk_username = "user_b"
        result = self.request_resource("ListProjectTables", bkbase_namespace="project_999")
        self.assertEqual(result, [])
        self.assertTrue(all(c["kind"].startswith("User") for c in self.calls))

    def test_current_user_context_mismatch_is_rejected_without_bkbase(self):
        context = {"version": "v4", "tenant": "tenant_a", "user": "spoofed", "request": self.request}
        with self.assertRaises(PermissionDenied):
            permissions.list_user_namespace_result_tables("project_999", context=context)
        self.assertEqual(self.calls, [])

    def test_legacy_v4_non_ui_personal_endpoint_keeps_business_shape(self):
        result = resources.ListTables().request(table_type="MineBizRt", namespace="default", bk_biz_id="47")
        self.assertEqual(len(result), 152)
        self.assertTrue(all(set(row) == {"label", "value"} for row in result))
        self.assertTrue(all(call["kind"].startswith("User") for call in self.calls))

    def test_project_cache_separates_personal_and_platform_types_and_users(self):
        store = {}

        def save(key, value, timeout):
            store[key] = value

        with mock.patch.object(UsingCache, "get_value", side_effect=lambda key: store.get(key)), mock.patch.object(
            UsingCache, "set_value", side_effect=save
        ), mock.patch("bk_resource.utils.cache.get_request_username", return_value="user_a") as user, mock.patch.object(
            resources, "list_scoped_v4_tables", return_value=[]
        ) as scoped:
            endpoint = resources.ListProjectTables()
            base = dict(namespace="default", table_type="MineBizRt", bkbase_namespace="project_999")
            endpoint.request(**base)
            endpoint.request(**base)
            self.assertEqual(scoped.call_count, 1)
            endpoint.request(**{**base, "table_type": "BizRt"})
            endpoint.request(**{**base, "scene_id": 8})
            endpoint.request(**{**base, "bkbase_namespace": "shared"})
            endpoint.request(**{**base, "namespace": "other"})
            user.return_value = "user_b"
            endpoint.request(**base)
            with override_settings(BKBASE_V4_TENANT="tenant_b"):
                resources.ListProjectTables().request(**base)
            self.assertEqual(scoped.call_count, 7)
            self.assertEqual(len(store), 7)

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_legacy_personal_requests_keep_business_parameters_and_route(self):
        with mock.patch.object(
            permissions.api.bk_base, "get_bizs_list", return_value=[{"bk_biz_id": 47, "bk_biz_name": "biz"}]
        ) as biz, mock.patch.object(
            permissions.api.bk_base,
            "get_mine_result_tables",
            return_value=[{"result_table_id": "47_existing", "result_table_name": "Saved"}],
        ) as mine:
            result = resources.ListTables().request(table_type="MineBizRt", namespace="default", bk_biz_id="47")
        self.assertEqual(result, [{"label": "Saved", "value": "47_existing"}])
        self.assertEqual(biz.call_args.kwargs["bk_username"], "user_a")
        self.assertEqual(mine.call_args.kwargs["bk_biz_id"], "47")
        self.assertEqual(mine.call_args.kwargs["bk_username"], "user_a")
        self.assertEqual(self.calls, [])

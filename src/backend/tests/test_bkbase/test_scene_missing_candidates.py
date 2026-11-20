"""场景候选跳过明确缺失表，已选配置及整体读取故障保持严格语义。"""
import json
from copy import deepcopy
from unittest import mock
from urllib.parse import urlparse

import requests
from bk_resource.exceptions import APIRequestError
from django.test import SimpleTestCase, override_settings

from services.web.bkbase import metadata, permissions
from services.web.bkbase.exceptions import BKBaseReadTimeout, BKBaseResourceMappingError
from services.web.strategy_v2 import resources
from services.web.strategy_v2.utils import table
from tests.test_bkbase import test_project_lazy_loading as fixtures


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
class SceneMissingCandidateTests(SimpleTestCase):
    rt_id = staticmethod(fixtures.ProjectLazyLoadingTests.rt_id)
    row = fixtures.ProjectLazyLoadingTests.row

    def setUp(self):
        fixtures.ProjectLazyLoadingTests.setUp(self)
        self.projects = ["project_999"]
        self.rows = {"project_999": [self.row(0), self.row(2)], "shared": []}
        self.failure = None
        self.error_detail = "resource not exists"
        self.formal_reads = {}
        self.bindings = "normal"
        self.enterContext(
            mock.patch(
                "services.web.scene.data_filter.SceneDataFilter.get_table_ids",
                return_value=[self.rt_id(0), self.rt_id(2)],
            )
        )

    def result_table(self, index):
        result = fixtures.ProjectLazyLoadingTests.result_table(self, index)
        if self.bindings == "missing":
            result["status"]["related"] = []
        elif self.bindings == "wrong":
            result["status"]["related"][0]["spec"]["data"]["name"] = "wrong_rt"
        return result

    def transport(self, method, url, **kwargs):
        response = fixtures.ProjectLazyLoadingTests.transport(self, method, url, **kwargs)
        path, params = urlparse(url).path, kwargs.get("params", {})
        rt_id = path.rstrip("/").rsplit("/", 1)[-1]
        if "/result_tables/" in path:
            stage = "formal"
            self.formal_reads[rt_id] = self.formal_reads.get(rt_id, 0) + 1
        elif path.endswith("/dataset_list/"):
            stage, rt_id = "permission", params.get("dataset_name")
            if rt_id:
                rows = [r for r in self.rows["project_999"] if r["dataset_name"] == rt_id]
                response._content = json.dumps(
                    {"result": True, "code": "00", "data": {"total": len(rows), "list": rows}}
                ).encode()
        else:
            stage = "channel" if params.get("storage_type") == "channel" else "detail"
        if self.failure:
            wanted_stage, wanted_id, status, code, *options = self.failure
            matched = stage == wanted_stage and (wanted_id is None or wanted_id == rt_id)
            if options and options[0] == "second":
                matched = matched and self.formal_reads.get(rt_id, 0) == 2
            if matched:
                if status == "timeout":
                    raise requests.Timeout("synthetic timeout")
                response.status_code = status
                response._content = json.dumps(
                    {"result": False, "code": code, "data": {"err": self.error_detail}, "message": "synthetic failure"}
                ).encode()
        return response

    def scene(self, table_type="BizRt"):
        return resources.GetScenePermissionTables().request(scene_id=1, table_type=table_type)

    def assert_only_healthy(self, result):
        self.assertEqual(
            result,
            [{"label": "Synthetic(47)", "value": "47", "children": [{"label": "Alias 2", "value": self.rt_id(2)}]}],
        )

    def test_scene_skips_missing_formal_table_for_http_and_documented_platform_codes(self):
        for table_type in ("BizRt", "BuildIn"):
            for status, code in ((404, "1558025"), (200, "1558025"), (200, "1500102")):
                with self.subTest(table_type=table_type, status=status, code=code):
                    self.failure = ("formal", self.rt_id(0), status, code)
                    self.assert_only_healthy(self.scene(table_type))
        self.assertFalse(any(c["kind"] == "NamespacesList" for c in self.calls))

    def test_scene_skips_table_deleted_after_permission_lookup(self):
        for stage, options in (("formal", ["second"]), ("detail", [])):
            with self.subTest(stage=stage):
                self.formal_reads.clear()
                self.failure = (stage, self.rt_id(0), 200, "1558025", *options)
                self.assert_only_healthy(self.scene())

    def test_legacy_bizrt_list_keeps_missing_table_error(self):
        self.failure = ("formal", self.rt_id(0), 404, "1558025")
        with self.assertRaises(APIRequestError):
            resources.ListTables().request(table_type="BizRt", namespace="audit")

    def test_permission_endpoint_failure_and_global_failures_still_propagate(self):
        for stage in ("formal", "permission", "detail"):
            failures = [(403, "1558025"), (500, "1558025"), (200, "1500000"), ("timeout", None)]
            if stage == "permission":
                failures.extend([(404, "1558025"), (200, "1558025")])
            for status, code in failures:
                with self.subTest(stage=stage, status=status, code=code):
                    self.failure = (stage, self.rt_id(0), status, code)
                    with self.assertRaises((APIRequestError, BKBaseReadTimeout)):
                        self.scene()

    def test_ambiguous_platform_failure_is_not_treated_as_missing(self):
        self.failure = ("formal", self.rt_id(0), 200, "1500102")
        self.error_detail = "synthetic validation failure"
        with self.assertRaises(APIRequestError):
            self.scene()

    def test_query_denied_and_missing_binding_do_not_make_a_table_selectable(self):
        self.rows["project_999"][0]["permissions"]["query"] = False
        self.assert_only_healthy(self.scene())
        self.bindings = "missing"
        self.failure = ("channel", None, 404, "1558025")
        self.assertEqual(self.scene(), [])

    def test_wrong_binding_is_not_hidden_as_a_deleted_table(self):
        self.bindings = "wrong"
        with self.assertRaises(BKBaseResourceMappingError):
            self.scene()

    def test_selected_ids_direct_permission_and_metadata_remain_strict(self):
        self.failure = ("formal", self.rt_id(0), 200, "1558025")
        for read in (
            lambda: permissions.list_queryable_result_tables([self.rt_id(0)]),
            lambda: table.list_scoped_v4_tables(
                table_type="BizRt", namespace="audit", result_table_ids=[self.rt_id(0)]
            ),
            lambda: metadata.get_result_table(self.rt_id(0)),
        ):
            with self.subTest(read=read), self.assertRaises(APIRequestError):
                read()

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_scene_and_legacy_list_keep_existing_behavior(self):
        legacy = [
            {
                "label": "Legacy",
                "value": "47",
                "children": [{"label": "Selected", "value": self.rt_id(0)}, {"label": "Other", "value": "47_other"}],
            }
        ]
        with mock.patch.object(table.BizRtTableHandler, "list_tables", return_value=deepcopy(legacy)):
            self.assertEqual(
                self.scene(),
                [{"label": "Legacy", "value": "47", "children": [{"label": "Selected", "value": self.rt_id(0)}]}],
            )
            self.assertEqual(resources.ListTables().request(table_type="BizRt", namespace="audit"), legacy)
        self.assertEqual(self.calls, [])

"""数据源个人可见范围及声明式停止的契约。"""
from copy import deepcopy
from unittest import mock

from django.core.exceptions import PermissionDenied
from django.test import SimpleTestCase

from api.bk_base_v4.default import DataSourceUpdate
from services.web.bkbase import source
from services.web.bkbase.exceptions import BKBaseResourceMappingError


class SourceTests(SimpleTestCase):
    def setUp(self):
        self.context = {
            "version": "v4",
            "tenant": "tenant_a",
            "namespace": "audit",
            "user": "user_a",
            "request": mock.Mock(),
        }
        self.context["request"].user.bk_username = "user_a"
        self.resource = {
            "kind": "DataSource",
            "metadata": {
                "tenant": "tenant_a",
                "name": "source_a",
                "namespace": "audit",
                "labels": {"raw_data_id": "11"},
            },
            "spec": {"desired_status": "Running", "current_status": "Running", "preserve": {"value": 1}},
            "status": {"phase": "Ok"},
        }

    def test_personal_detail_must_be_in_user_list(self):
        with mock.patch(
            "services.web.bkbase.source.api.bk_base_v4.user_data_source_list", return_value=[self.resource]
        ):
            with self.assertRaises(BKBaseResourceMappingError):
                source.get_user_source(
                    self.context, {"kind": "DataSource", "tenant": "tenant_a", "namespace": "audit", "name": "other"}
                )

    def test_stop_preserves_resource_and_is_not_immediately_stopped(self):
        ref = {"kind": "DataSource", "tenant": "tenant_a", "namespace": "audit", "name": "source_a"}
        with mock.patch("services.web.bkbase.source.resource_lock"), mock.patch(
            "services.web.bkbase.source.api.bk_base_v4.data_source_get", return_value=self.resource
        ), mock.patch(
            "services.web.bkbase.source.api.bk_base_v4.data_source_update",
            side_effect=lambda **kw: {
                "kind": "DataSource",
                "metadata": kw["metadata"],
                "spec": kw["spec"],
                "status": {"phase": "Ok"},
            },
        ) as update:
            result = source.stop_source(self.context, ref)
            self.assertEqual(update.call_args.kwargs["spec"]["preserve"], {"value": 1})
            self.assertEqual(update.call_args.kwargs["spec"]["desired_status"], "Stopped")
            self.assertNotEqual(result["task_state"], "stopped")
            self.assertEqual(self.resource["spec"]["desired_status"], "Running")

    def test_stop_changes_desired_state_even_if_actual_state_is_stopped(self):
        ref = {"kind": "DataSource", "tenant": "tenant_a", "namespace": "audit", "name": "source_a"}
        self.resource["spec"]["current_status"] = "Stopped"
        with mock.patch("services.web.bkbase.source.resource_lock"), mock.patch(
            "services.web.bkbase.source.api.bk_base_v4.data_source_get", return_value=self.resource
        ), mock.patch(
            "services.web.bkbase.source.api.bk_base_v4.data_source_update",
            side_effect=lambda **kw: {"spec": kw["spec"], "status": {"phase": "Ok"}},
        ) as update:
            result = source.stop_source(self.context, ref)
        update.assert_called_once()
        self.assertEqual(update.call_args.kwargs["spec"]["desired_status"], "Stopped")
        self.assertIsNone(result["task_state"])

    def test_repeated_stop_observes_pending_without_reissuing_put(self):
        ref = {"kind": "DataSource", "tenant": "tenant_a", "namespace": "audit", "name": "source_a"}
        self.resource["spec"]["desired_status"] = "Stopped"
        with mock.patch("services.web.bkbase.source.resource_lock"), mock.patch(
            "services.web.bkbase.source.api.bk_base_v4.data_source_get", return_value=self.resource
        ), mock.patch("services.web.bkbase.source.api.bk_base_v4.data_source_update") as update:
            result = source.stop_source(self.context, ref)
        update.assert_not_called()
        self.assertEqual(result["task_state"], "running")

    def test_stop_passes_wire_state_through_resource_serializer(self):
        ref = {"kind": "DataSource", "tenant": "tenant_a", "namespace": "audit", "name": "source_a"}
        resource = DataSourceUpdate()
        response = mock.Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "result": True,
            "code": "00",
            "data": {
                "spec": {"desired_status": "Stopped", "current_status": "Running"},
                "status": {"phase": "Pending"},
            },
        }
        resource.session.request = mock.Mock(return_value=response)
        with mock.patch("services.web.bkbase.source.resource_lock"), mock.patch(
            "services.web.bkbase.source.api.bk_base_v4.data_source_get", return_value=self.resource
        ), mock.patch.object(resource, "build_header", return_value={}), mock.patch(
            "services.web.bkbase.source.api.bk_base_v4.data_source_update",
            side_effect=lambda **kw: resource.request(kw),
        ):
            result = source.stop_source(self.context, ref)
        request = resource.session.request.call_args.kwargs
        self.assertEqual(request["json"]["spec"]["desired_status"], "Stopped")
        self.assertEqual(request["json"]["metadata"]["name"], "source_a")
        self.assertEqual(request["json"]["metadata"]["tenant"], "tenant_a")
        self.assertEqual(request["json"]["metadata"]["namespace"], "audit")
        self.assertTrue(request["url"].endswith("/namespaces/audit/datasources/source_a/"))
        self.assertIsNone(result["task_state"])

    def test_cross_tenant_ref_rejected_before_api(self):
        with self.assertRaises(BKBaseResourceMappingError):
            source.stop_source(
                self.context, {"kind": "DataSource", "tenant": "tenant_b", "namespace": "audit", "name": "source_a"}
            )


class UserSourceApplyBindingTests(SimpleTestCase):
    """用户已授权来源可以来自其他项目，输出项目和来源身份各自保留。"""

    def setUp(self):
        self.request = mock.Mock()
        self.request.user.bk_username = "user_a"
        self.request.user.is_authenticated = True
        self.context = {
            "version": "v4",
            "tenant": "tenant_a",
            "namespace": "audit",
            "user": "user_a",
            "request": self.request,
        }
        self.native = {
            "kind": "DataSource",
            "metadata": {
                "tenant": "tenant_a",
                "namespace": "bklog",
                "name": "source_a",
                "labels": {"raw_data_id": "11", "bk_biz_id": "47"},
            },
            "spec": {
                "basic_info": {"bk_biz_id": 2, "data_source_name": "source_a"},
                "report_config": {"type": "log_collection"},
                "data_id": {"kind": "DataId", "tenant": "tenant_a", "namespace": "bklog", "name": "data_a"},
            },
        }
        self.rows = [deepcopy(self.native)]
        self.enterContext(mock.patch.object(source, "get_request_username", return_value="user_a"))
        self.enterContext(mock.patch.object(source, "get_bkbase_context", return_value=self.context))
        self.enterContext(
            mock.patch.object(source.api.bk_base_v4, "user_data_source_list", side_effect=lambda **kw: self.rows)
        )
        self.detail = self.enterContext(
            mock.patch.object(source.api.bk_base_v4, "user_data_source_get", side_effect=lambda **kw: self.native)
        )

    def test_authorized_other_project_source_keeps_exact_binding_and_output_context(self):
        raw_data, binding = source.get_user_source_for_apply(bk_data_id=11)
        self.assertEqual(raw_data["bk_biz_id"], 2)
        self.assertEqual(raw_data["data_scenario"], "log")
        self.assertEqual(
            binding,
            {
                "data_source": {"kind": "DataSource", "tenant": "tenant_a", "namespace": "bklog", "name": "source_a"},
                "data_id": {"kind": "DataId", "tenant": "tenant_a", "namespace": "bklog", "name": "data_a"},
                "source_raw_data_id": 11,
            },
        )
        self.assertEqual(self.context["namespace"], "audit")
        self.detail.assert_called_once_with(
            tenant="tenant_a", namespace="bklog", name="source_a", _request=self.request
        )

    def test_same_project_source_remains_supported(self):
        self.native["metadata"]["namespace"] = "audit"
        self.rows = [deepcopy(self.native)]
        _, binding = source.get_user_source_for_apply(bk_data_id=11)
        self.assertEqual(binding["data_source"]["namespace"], "audit")
        self.assertEqual(binding["data_id"]["namespace"], "bklog")

    def test_invisible_or_ambiguous_source_cannot_be_bound(self):
        for rows in ([], [deepcopy(self.native), deepcopy(self.native)]):
            with self.subTest(rows=rows):
                self.rows = rows
                with self.assertRaises(BKBaseResourceMappingError):
                    source.get_user_source_for_apply(bk_data_id=11)
        self.detail.assert_not_called()

    def test_user_visibility_revoked_before_detail_cannot_be_bound(self):
        with mock.patch.object(
            source.api.bk_base_v4, "user_data_source_list", side_effect=[[deepcopy(self.native)], []]
        ):
            with self.assertRaises(BKBaseResourceMappingError):
                source.get_user_source_for_apply(bk_data_id=11)
        self.detail.assert_not_called()

    def test_foreign_tenant_or_wrong_kind_in_list_cannot_be_bound(self):
        for key, value in (("tenant", "tenant_b"), ("kind", "DataId")):
            with self.subTest(key=key):
                row = deepcopy(self.native)
                if key == "kind":
                    row[key] = value
                else:
                    row["metadata"][key] = value
                self.rows = [row]
                with self.assertRaises(BKBaseResourceMappingError):
                    source.get_user_source_for_apply(bk_data_id=11)
        self.detail.assert_not_called()

    def test_unauthenticated_or_different_user_cannot_bind_source(self):
        for username, authenticated in (("other", True), ("user_a", False)):
            with self.subTest(username=username, authenticated=authenticated):
                self.request.user.bk_username = username
                self.request.user.is_authenticated = authenticated
                with self.assertRaises(PermissionDenied):
                    source.get_user_source_for_apply(bk_data_id=11)
        self.detail.assert_not_called()

    def test_changed_detail_identity_cannot_be_bound(self):
        original = deepcopy(self.native)
        for key, value in (("tenant", "tenant_b"), ("namespace", "other"), ("name", "other")):
            with self.subTest(key=key):
                self.native = deepcopy(original)
                self.native["metadata"][key] = value
                with self.assertRaises(BKBaseResourceMappingError):
                    source.get_user_source_for_apply(bk_data_id=11)
        for kind, raw_id in (("DataId", "11"), ("DataSource", "12"), ("DataSource", "0")):
            with self.subTest(kind=kind, raw_id=raw_id):
                self.native = deepcopy(original)
                self.native["kind"] = kind
                self.native["metadata"]["labels"]["raw_data_id"] = raw_id
                with self.assertRaises(BKBaseResourceMappingError):
                    source.get_user_source_for_apply(bk_data_id=11)

    def test_invalid_dataid_reference_cannot_be_bound(self):
        for key, value in (("tenant", "tenant_b"), ("kind", "DataSource"), ("name", ""), ("namespace", "")):
            with self.subTest(key=key):
                self.native["spec"]["data_id"] = {
                    "kind": "DataId",
                    "tenant": "tenant_a",
                    "namespace": "bklog",
                    "name": "data_a",
                    key: value,
                }
                with self.assertRaises(BKBaseResourceMappingError):
                    source.get_user_source_for_apply(bk_data_id=11)

    def test_owned_source_discovery_still_rejects_other_project(self):
        with self.assertRaises(BKBaseResourceMappingError):
            source._source_binding(self.context, self.native, 11)

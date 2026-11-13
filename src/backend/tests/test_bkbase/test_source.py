"""数据源个人可见范围及声明式停止的契约。"""
from unittest import mock

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

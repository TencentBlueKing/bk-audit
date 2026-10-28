"""数据源个人可见范围及声明式停止的契约。"""
from unittest import mock

from django.test import SimpleTestCase

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
            "metadata": {"name": "source_a", "namespace": "audit", "labels": {"raw_data_id": "11"}},
            "spec": {"desired_status": "running", "current_status": "running", "preserve": {"value": 1}},
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
            self.assertEqual(update.call_args.kwargs["spec"]["desired_status"], "stopped")
            self.assertNotEqual(result["task_state"], "stopped")
            self.assertEqual(self.resource["spec"]["desired_status"], "running")

    def test_cross_tenant_ref_rejected_before_api(self):
        with self.assertRaises(BKBaseResourceMappingError):
            source.stop_source(
                self.context, {"kind": "DataSource", "tenant": "tenant_b", "namespace": "audit", "name": "source_a"}
            )

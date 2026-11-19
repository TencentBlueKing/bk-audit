"""共享入库资源命名与配置保留验证。"""
from unittest import mock

from django.test import TestCase

from services.web.bkbase import storage
from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.databus.models import CollectorPlugin


class StorageTests(TestCase):
    def setUp(self):
        self.context = {"version": "v4", "tenant": "tenant_a", "namespace": "audit"}
        self.rt = {"kind": "ResultTable", "tenant": "tenant_a", "namespace": "audit", "name": "rt_a"}
        self.cluster = {"kind": "Doris", "tenant": "tenant_a", "namespace": "resources", "name": "cluster_a"}

    def test_missing_cluster_mapping_does_not_guess_numeric_name(self):
        with mock.patch("services.web.bkbase.storage.GlobalMetaConfig.get", return_value={}):
            with self.assertRaises(BKBaseResourceMappingError):
                storage.resolve_storage_cluster(
                    self.context, audit_namespace="audit", storage_type="doris", legacy_cluster_id=7
                )

    def test_existing_storage_keeps_unrelated_fields(self):
        ref = {"kind": "DataStorage", "tenant": "tenant_a", "namespace": "audit", "name": "storage_a"}
        owner = CollectorPlugin.objects.create(
            namespace="audit",
            collector_plugin_id=1,
            collector_plugin_name="plugin",
            bkdata_biz_id=1,
            table_id=1,
            index_set_id=1,
            bkbase_v4_resources={"storages": {"main": ref}},
        )
        original = {
            "kind": "DataStorage",
            "metadata": {"name": "storage_a", "annotations": {"keep": "value"}},
            "spec": {
                "tableInfo": {"expire": 7, "source": self.rt, "storage": self.cluster},
                "maintainers": ["operator"],
            },
            "status": {"phase": "Pending"},
        }
        with mock.patch("services.web.bkbase.storage.resource_lock"), mock.patch(
            "services.web.bkbase.storage.api.bk_base_v4.data_storage_get", return_value=original
        ), mock.patch(
            "services.web.bkbase.storage.api.bk_base_v4.data_storage_update",
            side_effect=lambda **kw: {"metadata": kw["metadata"], "spec": kw["spec"], "status": {"phase": "Pending"}},
        ) as put:
            result = storage.ensure_storage(
                self.context,
                owner,
                rt_ref=self.rt,
                cluster_ref=self.cluster,
                purpose="main",
                config={"tableInfo": {"expire": 14}},
            )
            self.assertEqual(put.call_args.kwargs["spec"]["maintainers"], ["operator"])
            self.assertEqual(put.call_args.kwargs["metadata"]["annotations"]["keep"], "value")
            self.assertEqual(original["spec"]["tableInfo"]["expire"], 7)
            self.assertIsNone(result["task_state"])

    def test_unchanged_storage_is_observed_without_new_put(self):
        owner = CollectorPlugin.objects.create(
            namespace="audit",
            collector_plugin_id=2,
            collector_plugin_name="plugin",
            bkdata_biz_id=1,
            table_id=1,
            index_set_id=1,
        )
        spec = {"tableInfo": {"expire": 14, "source": self.rt, "storage": self.cluster}}
        original = {"metadata": {"name": "s"}, "spec": spec, "status": {"phase": "Ok", "message": "running"}}
        with mock.patch("services.web.bkbase.storage.resource_lock"), mock.patch(
            "services.web.bkbase.storage.get_resource_or_none", return_value=original
        ), mock.patch("services.web.bkbase.storage.api.bk_base_v4.data_storage_update") as put:
            result = storage.ensure_storage(
                self.context,
                owner,
                rt_ref=self.rt,
                cluster_ref=self.cluster,
                purpose="main",
                config={"tableInfo": {"expire": 14}},
            )
            put.assert_not_called()
            self.assertEqual(result["task_state"], "running")

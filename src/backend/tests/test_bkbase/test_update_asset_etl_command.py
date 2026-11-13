"""通过真实管理命令验证V4组合维护的写前拒绝。

数据库选择、参数解析与业务handler保持启用，仅替换外部schema/API边界。
V3继续走原清洗、重启和入库流程，不把本阶段拒绝标为V4迁移完成。
"""
from io import StringIO
from unittest import mock

from bk_resource import api, resource
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings

from apps.meta.models import ResourceType, System
from services.web.databus.constants import SnapshotRunningStatus
from services.web.databus.models import Snapshot, SnapshotStorage


@override_settings(BKBASE_API_VERSION="v4")
class UpdateAssetEtlCommandTests(TestCase):
    def setUp(self):
        self.system = System.objects.create(
            system_id="clean_command_system",
            namespace="audit",
            callback_url="https://source.test",
            auth_token="synthetic",
        )
        self.resource_type = ResourceType.objects.create(
            system_id=self.system.system_id,
            resource_type_id="asset",
            unique_id="clean_command_system:asset",
            path="/resources",
        )
        self.snapshot = Snapshot.objects.create(
            system_id=self.system.system_id,
            resource_type_id="asset",
            status=SnapshotRunningStatus.RUNNING,
            bkbase_data_id=11,
            bkbase_processing_id="old_processing",
            bkbase_table_id="11_asset",
            custom_config={"retained": True},
            bkbase_v4_resources={"retained": {"value": 1}},
        )
        self.http = self.enterContext(
            mock.patch("requests.sessions.Session.request", side_effect=AssertionError("unexpected HTTP"))
        )
        self.schema = self.enterContext(
            mock.patch.object(
                resource.meta,
                "resource_type_schema",
                side_effect=AssertionError("preflight must precede external schema"),
            )
        )

    def run_command(self, custom_config=None):
        stdout = StringIO()
        error = None
        args = ["--system-id", self.system.system_id, "--resource-type-id", "asset"]
        if custom_config is not None:
            args.extend(["--custom-config", custom_config])
        try:
            call_command("update_asset_etl", *args, stdout=stdout)
        except Exception as caught:
            error = caught
        return stdout.getvalue(), error

    def assert_v4_rejected_without_changes(self, *, custom_config=None, reason):
        before = Snapshot.objects.filter(pk=self.snapshot.pk).values().get()
        output, error = self.run_command(custom_config)
        self.assertEqual(Snapshot.objects.filter(pk=self.snapshot.pk).values().get(), before)
        self.assertIsInstance(error, CommandError)
        self.assertIn(reason, str(error))
        self.assertNotIn("全部更新完成", output)
        self.assertNotIn("自定义配置已更新", output)
        self.http.assert_not_called()
        self.schema.assert_not_called()

    def test_missing_binding_refuses_before_custom_config_or_remote_write(self):
        for kind in ("hdfs", "redis"):
            with self.subTest(storage_type=kind):
                self.snapshot.storages.all().delete()
                SnapshotStorage.objects.create(snapshot=self.snapshot, storage_type=kind)
                self.assert_v4_rejected_without_changes(custom_config='{"new": "config"}', reason="资产维护未完成")

    def test_doris_missing_binding_rejects_before_any_write(self):
        SnapshotStorage.objects.create(snapshot=self.snapshot, storage_type="doris")
        self.assert_v4_rejected_without_changes(custom_config='{"new": "config"}', reason="资产维护未完成")
        _, error = self.run_command()
        self.assertNotIn("C14", str(error))

    def test_doris_plus_unresolved_storage_refuses_before_any_partial_write(self):
        for kind in ("doris", "hdfs"):
            SnapshotStorage.objects.create(snapshot=self.snapshot, storage_type=kind)
        self.assert_v4_rejected_without_changes(custom_config='{"new": "config"}', reason="资产维护未完成")

    def test_existing_configuration_is_unchanged_without_custom_argument(self):
        SnapshotStorage.objects.create(snapshot=self.snapshot, storage_type="hdfs")
        self.assert_v4_rejected_without_changes(reason="资产维护未完成")

    def test_no_storage_does_not_save_custom_configuration_or_claim_completion(self):
        self.assert_v4_rejected_without_changes(custom_config='{"new": "config"}', reason="存储")

    def test_no_storage_without_custom_argument_still_does_not_claim_completion(self):
        self.assert_v4_rejected_without_changes(reason="存储")

    def test_invalid_custom_json_is_rejected_without_side_effects(self):
        SnapshotStorage.objects.create(snapshot=self.snapshot, storage_type="hdfs")
        self.assert_v4_rejected_without_changes(custom_config="not json", reason="JSON")

    @override_settings(BKBASE_API_VERSION="v3", ASSET_RT_STORAGE_CLUSTER="synthetic_cluster", ASSET_RT_EXPIRE_TIME="7d")
    def test_v3_keeps_real_clean_restart_storage_and_configuration_flow(self):
        SnapshotStorage.objects.create(snapshot=self.snapshot, storage_type="hdfs")
        self.schema.side_effect = None
        self.schema.return_value = [{"id": "custom_attribute", "type": "string", "description": "attribute"}]
        with mock.patch.object(api.bk_base, "databus_cleans_put", return_value={}) as clean, mock.patch.object(
            api.bk_base, "databus_tasks_delete", return_value={}
        ) as stop, mock.patch.object(api.bk_base, "databus_tasks_post", return_value={}) as start, mock.patch.object(
            api.bk_base, "databus_storages_put", return_value={}
        ) as storage:
            output, error = self.run_command('{"retained": "changed"}')
        self.assertIsNone(error)
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.custom_config, {"retained": "changed"})
        self.assertIn("全部更新完成", output)
        self.assertEqual(clean.call_args.kwargs["raw_data_id"], 11)
        self.assertEqual(clean.call_args.kwargs["processing_id"], "old_processing")
        self.assertEqual(stop.call_args.kwargs["processing_id"], "old_processing")
        self.assertEqual(start.call_args.kwargs["processing_id"], "old_processing")
        self.assertEqual(storage.call_args.kwargs["result_table_id"], "11_asset")
        self.assertEqual(storage.call_args.kwargs["storage_cluster"], "synthetic_cluster")
        self.assertEqual(
            storage.call_args.kwargs["index_fields"],
            [
                {"index": 0, "physical_field": "id"},
                {"index": 0, "physical_field": "resource_type_id"},
                {"index": 0, "physical_field": "system_id"},
            ],
        )

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_zero_storage_behavior_is_preserved_in_this_bounded_fix(self):
        output, error = self.run_command('{"new": "config"}')
        self.assertIsNone(error)
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.custom_config, {"new": "config"})
        self.assertIn("全部更新完成", output)
        self.http.assert_not_called()

# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
Copyright (C) 2023 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

from datetime import timedelta
from typing import Dict
from unittest import mock

from bk_resource.exceptions import APIRequestError
from django.conf import settings
from django.utils import timezone

from api.bk_base.constants import StorageType
from apps.meta.models import ResourceType, System
from apps.permission.handlers.resource_types import ResourceEnum
from services.web.databus.constants import (
    ASSET_RISK_BKBASE_RT_ID_KEY,
    ASSET_STRATEGY_BKBASE_RT_ID_KEY,
    ASSET_STRATEGY_TAG_BKBASE_RT_ID_KEY,
    ASSET_TICKET_NODE_BKBASE_RT_ID_KEY,
    ASSET_TICKET_PERMISSION_BKBASE_RT_ID_KEY,
    AssetSyncAnomalyReason,
    JoinDataType,
    SnapshotRunningStatus,
)
from services.web.databus.models import (
    CollectorConfig,
    CollectorPlugin,
    Snapshot,
    SnapshotCheckStatistic,
)
from services.web.databus.tasks import (
    change_storage_cluster,
    create_api_push_etl,
    refresh_system_snapshots,
    report_asset_sync_count,
    report_asset_sync_status,
    sync_asset_bkbase_rt_ids,
)
from tests.base import TestCase


class SyncAssetBkbaseRtIdsTests(TestCase):
    def setUp(self) -> None:
        super().setUp()

    @mock.patch("services.web.databus.tasks.GlobalMetaConfig.set")
    @mock.patch("services.web.databus.tasks.GlobalMetaConfig.get")
    @mock.patch("services.web.databus.tasks.Snapshot.objects")
    def test_sync_asset_bkbase_rt_ids_success(self, snapshot_objects_mock, config_get_mock, config_set_mock):
        """当未配置结果表时，发现可用快照应写入 namespace 级别配置。"""
        config_get_mock.return_value = ""

        snapshots: Dict[ResourceEnum, mock.Mock] = {}
        for resource_cls in [
            ResourceEnum.RISK,
            ResourceEnum.STRATEGY,
            ResourceEnum.STRATEGY_TAG,
            ResourceEnum.TICKET_PERMISSION,
            ResourceEnum.TICKET_NODE,
        ]:
            snapshot_mock = mock.Mock(spec=Snapshot)
            snapshot_mock.system_id = resource_cls.system_id
            snapshot_mock.resource_type_id = resource_cls.id
            snapshot_mock.status = SnapshotRunningStatus.RUNNING.value
            snapshot_mock.join_data_type = JoinDataType.ASSET.value
            snapshot_mock.bkbase_data_id = 100
            snapshot_mock.bkbase_table_id = "result_table"
            snapshots[resource_cls] = snapshot_mock

        snapshot_objects_mock.filter.return_value.order_by.return_value.first.side_effect = [
            snapshots[ResourceEnum.RISK],
            snapshots[ResourceEnum.STRATEGY],
            snapshots[ResourceEnum.STRATEGY_TAG],
            snapshots[ResourceEnum.TICKET_PERMISSION],
            snapshots[ResourceEnum.TICKET_NODE],
        ]

        sync_asset_bkbase_rt_ids()

        expected_calls = [
            mock.call(
                ASSET_RISK_BKBASE_RT_ID_KEY,
                str(snapshots[ResourceEnum.RISK].bkbase_table_id),
                config_level=mock.ANY,
                instance_key=settings.DEFAULT_NAMESPACE,
            ),
            mock.call(
                ASSET_STRATEGY_BKBASE_RT_ID_KEY,
                str(snapshots[ResourceEnum.STRATEGY].bkbase_table_id),
                config_level=mock.ANY,
                instance_key=settings.DEFAULT_NAMESPACE,
            ),
            mock.call(
                ASSET_STRATEGY_TAG_BKBASE_RT_ID_KEY,
                str(snapshots[ResourceEnum.STRATEGY_TAG].bkbase_table_id),
                config_level=mock.ANY,
                instance_key=settings.DEFAULT_NAMESPACE,
            ),
            mock.call(
                ASSET_TICKET_PERMISSION_BKBASE_RT_ID_KEY,
                str(snapshots[ResourceEnum.TICKET_PERMISSION].bkbase_table_id),
                config_level=mock.ANY,
                instance_key=settings.DEFAULT_NAMESPACE,
            ),
            mock.call(
                ASSET_TICKET_NODE_BKBASE_RT_ID_KEY,
                str(snapshots[ResourceEnum.TICKET_NODE].bkbase_table_id),
                config_level=mock.ANY,
                instance_key=settings.DEFAULT_NAMESPACE,
            ),
        ]
        config_set_mock.assert_has_calls(expected_calls, any_order=True)

    @mock.patch("services.web.databus.tasks.GlobalMetaConfig.set")
    @mock.patch("services.web.databus.tasks.GlobalMetaConfig.get")
    @mock.patch("services.web.databus.tasks.Snapshot.objects")
    def test_sync_asset_bkbase_rt_ids_skip_when_already_configured(
        self, snapshot_objects_mock, config_get_mock, config_set_mock
    ):
        """已有配置的 namespace 应跳过，不再重复写入。"""
        config_get_mock.side_effect = ["existing_rt", "", "", "", ""]

        snapshot_mock = mock.Mock(spec=Snapshot)
        snapshot_mock.bkbase_data_id = 123
        snapshot_mock.bkbase_table_id = "result_table"
        snapshot_objects_mock.filter.return_value.order_by.return_value.first.return_value = snapshot_mock

        sync_asset_bkbase_rt_ids()

        # The first asset should be skipped because of existing config
        config_set_mock.assert_any_call(
            ASSET_STRATEGY_BKBASE_RT_ID_KEY,
            str(snapshot_mock.bkbase_table_id),
            config_level=mock.ANY,
            instance_key=settings.DEFAULT_NAMESPACE,
        )
        config_set_mock.assert_any_call(
            ASSET_STRATEGY_TAG_BKBASE_RT_ID_KEY,
            str(snapshot_mock.bkbase_table_id),
            config_level=mock.ANY,
            instance_key=settings.DEFAULT_NAMESPACE,
        )
        config_set_mock.assert_any_call(
            ASSET_TICKET_PERMISSION_BKBASE_RT_ID_KEY,
            str(snapshot_mock.bkbase_table_id),
            config_level=mock.ANY,
            instance_key=settings.DEFAULT_NAMESPACE,
        )
        config_set_mock.assert_any_call(
            ASSET_TICKET_NODE_BKBASE_RT_ID_KEY,
            str(snapshot_mock.bkbase_table_id),
            config_level=mock.ANY,
            instance_key=settings.DEFAULT_NAMESPACE,
        )
        # ensure risk not set again
        self.assertNotIn(
            mock.call(
                ASSET_RISK_BKBASE_RT_ID_KEY,
                str(snapshot_mock.bkbase_table_id),
                config_level=mock.ANY,
                instance_key=settings.DEFAULT_NAMESPACE,
            ),
            config_set_mock.call_args_list,
        )

    @mock.patch("services.web.databus.tasks.GlobalMetaConfig.set")
    @mock.patch("services.web.databus.tasks.GlobalMetaConfig.get", return_value="")
    @mock.patch("services.web.databus.tasks.Snapshot.objects")
    def test_sync_asset_bkbase_rt_ids_no_snapshot(self, snapshot_objects_mock, *_):
        """若不存在满足条件的快照，则不会写入新的配置。"""
        snapshot_objects_mock.filter.return_value.order_by.return_value.first.return_value = None

        sync_asset_bkbase_rt_ids()

        snapshot_objects_mock.filter.assert_called()


class DatabusTasksTests(TestCase):
    """覆盖 databus celery 任务里较易触达的核心逻辑。"""

    def setUp(self) -> None:
        super().setUp()
        self.system = System.objects.create(
            system_id="system", instance_id="inst", namespace=self.namespace, name="System"
        )

    @mock.patch("services.web.databus.tasks.EtlClean.get_instance")
    @mock.patch("services.web.databus.tasks.resource.databus.collector_plugin.update_plugin")
    @mock.patch("services.web.databus.tasks.GlobalMetaConfig.get")
    def test_change_storage_cluster_updates_flags(
        self,
        config_get_mock,
        update_plugin_mock,
        etl_clean_get_instance_mock,
    ):
        """当插件/采集项标记 storage_changed 时，应重建入库并清理标记位。"""
        plugin = CollectorPlugin.objects.create(
            namespace=self.namespace,
            collector_plugin_id=101,
            collector_plugin_name="Test Plugin",
            collector_plugin_name_en="test_plugin",
            bkdata_biz_id=1,
            table_id=1,
            index_set_id=1,
            etl_config="json",
            etl_params={"retain": True},
            storage_changed=True,
        )
        collector = CollectorConfig.objects.create(
            system_id=self.system.system_id,
            bk_biz_id=1,
            bk_data_id=1001,
            collector_plugin_id=plugin.collector_plugin_id,
            collector_config_id=2001,
            collector_config_name="Collector",
            collector_config_name_en="collector",
            fields=["field_a"],
            etl_config="bk_log",
            etl_params={"foo": "bar"},
            storage_changed=True,
        )

        config_get_mock.return_value = plugin.collector_plugin_id
        etl_clean_instance = mock.Mock()
        etl_clean_get_instance_mock.return_value = etl_clean_instance

        change_storage_cluster()

        update_plugin_mock.assert_called_once_with(
            namespace=self.namespace,
            etl_config="json",
            etl_params={"retain": True},
            is_default=True,
            collector_plugin_id=plugin.collector_plugin_id,
        )
        etl_clean_instance.update_or_create.assert_called_once_with(
            collector.collector_config_id,
            collector.etl_params,
            collector.fields,
            self.system.namespace,
        )
        plugin.refresh_from_db()
        collector.refresh_from_db()
        self.assertFalse(plugin.storage_changed)
        self.assertFalse(collector.storage_changed)

    @mock.patch("services.web.databus.tasks.time.sleep", return_value=None)
    @mock.patch("services.web.databus.tasks.resource.databus.collector.collector_etl")
    @mock.patch("services.web.databus.tasks.resource.meta.get_standard_fields")
    def test_create_api_push_etl_retries_on_api_error(
        self,
        standard_fields_mock,
        collector_etl_mock,
        _sleep_mock,
    ):
        """API PUSH 清洗创建失败后应因 APIRequestError 进行重试。"""
        plugin = CollectorPlugin.objects.create(
            namespace=self.namespace,
            collector_plugin_id=202,
            collector_plugin_name="API Plugin",
            collector_plugin_name_en="api_plugin",
            bkdata_biz_id=1,
            table_id=1,
            index_set_id=1,
        )
        collector = CollectorConfig.objects.create(
            system_id=self.system.system_id,
            bk_biz_id=1,
            bk_data_id=2001,
            collector_plugin_id=plugin.collector_plugin_id,
            collector_config_id=3001,
            collector_config_name="API Collector",
            collector_config_name_en="api_collector",
            etl_config="json",
            etl_params={},
        )

        standard_fields_mock.return_value = [{"field_name": "event_id"}]
        collector_etl_mock.side_effect = [APIRequestError("retry me"), None]

        create_api_push_etl(collector_config_id=collector.collector_config_id)

        self.assertEqual(collector_etl_mock.call_count, 2)
        standard_fields_mock.assert_called_once()

    def test_refresh_system_snapshots_updates_running(self):
        """刷新系统快照时，仅运行中的快照应被置为 PREPARING。"""
        ResourceType.objects.create(
            system_id=self.system.system_id,
            resource_type_id="rt_a",
            unique_id=f"{self.system.system_id}:rt_a",
            name="rt_a",
        )
        snapshot = Snapshot.objects.create(
            system_id=self.system.system_id,
            resource_type_id="rt_a",
            status=SnapshotRunningStatus.RUNNING.value,
            join_data_type=JoinDataType.ASSET.value,
        )

        refresh_system_snapshots(self.system.system_id)

        snapshot.refresh_from_db()
        self.assertEqual(snapshot.status, SnapshotRunningStatus.PREPARING.value)


class ReportAssetSyncStatusTests(TestCase):
    """资产同步「状态」上报任务（report_asset_sync_status）测试。"""

    def setUp(self) -> None:
        super().setUp()
        self.snapshot_running = Snapshot.objects.create(
            system_id="test_system",
            resource_type_id="rt_running",
            status=SnapshotRunningStatus.RUNNING.value,
            join_data_type=JoinDataType.ASSET.value,
        )
        self.snapshot_failed = Snapshot.objects.create(
            system_id="test_system",
            resource_type_id="rt_failed",
            status=SnapshotRunningStatus.FAILED.value,
            join_data_type=JoinDataType.ASSET.value,
        )
        self.snapshot_preparing = Snapshot.objects.create(
            system_id="test_system",
            resource_type_id="rt_preparing",
            status=SnapshotRunningStatus.PREPARING.value,
            join_data_type=JoinDataType.ASSET.value,
        )
        Snapshot.objects.create(
            system_id="test_system",
            resource_type_id="rt_closed",
            status=SnapshotRunningStatus.CLOSED.value,
            join_data_type=JoinDataType.ASSET.value,
        )

    @mock.patch("services.web.databus.tasks.Metric")
    @mock.patch("django.core.cache.cache.add")
    @mock.patch("services.web.databus.tasks.AssetSyncAnomalyEvent")
    def test_metric_reports_sync_health_per_status(self, event_class_mock, cache_add_mock, metric_class_mock):
        """不同状态资产应上报对应 sync_health，CLOSED 资产不上报"""
        metric_class_mock.return_value = mock.Mock()
        event_class_mock.return_value = mock.Mock()
        cache_add_mock.return_value = True

        report_asset_sync_status()

        metric_class_mock.assert_called_once()
        records = metric_class_mock.call_args[1]["records"]
        health = {r["dimension"]["resource_type_id"]: r["metrics"]["sync_health"] for r in records}
        self.assertEqual(health["rt_running"], 0)
        # rt_preparing 刚创建（updated_at 为近期），未超时，视为健康
        self.assertEqual(health["rt_preparing"], 0)
        self.assertEqual(health["rt_failed"], 1)
        self.assertNotIn("rt_closed", health)
        # 仪表盘可按状态status分组聚合
        status_dim = {r["dimension"]["resource_type_id"]: r["dimension"]["status"] for r in records}
        self.assertEqual(status_dim["rt_running"], SnapshotRunningStatus.RUNNING.value)
        self.assertEqual(status_dim["rt_preparing"], SnapshotRunningStatus.PREPARING.value)
        self.assertEqual(status_dim["rt_failed"], SnapshotRunningStatus.FAILED.value)

    @mock.patch("services.web.databus.tasks.Metric")
    @mock.patch("django.core.cache.cache.add")
    @mock.patch("services.web.databus.tasks.AssetSyncAnomalyEvent")
    def test_metric_sync_health_unhealthy_when_preparing_timeout(
        self, event_class_mock, cache_add_mock, metric_class_mock
    ):
        """PREPARING 超过阈值时 sync_health 应为 1（不健康），与事件口径一致。"""
        # 绕过 auto_now，将 updated_at 置为 7 小时前（默认阈值 6h）
        Snapshot.objects.filter(pk=self.snapshot_preparing.pk).update(updated_at=timezone.now() - timedelta(hours=7))
        metric_class_mock.return_value = mock.Mock()
        event_class_mock.return_value = mock.Mock()
        cache_add_mock.return_value = True

        report_asset_sync_status()

        records = metric_class_mock.call_args[1]["records"]
        health = {r["dimension"]["resource_type_id"]: r["metrics"]["sync_health"] for r in records}
        self.assertEqual(health["rt_preparing"], 1)
        self.assertEqual(health["rt_failed"], 1)

    @mock.patch("services.web.databus.tasks.Metric")
    def test_metric_skipped_when_all_closed(self, metric_class_mock):
        """全部资产为 CLOSED 时不应上报指标。"""
        Snapshot.objects.exclude(status=SnapshotRunningStatus.CLOSED.value).update(
            status=SnapshotRunningStatus.CLOSED.value
        )
        metric_class_mock.return_value = mock.Mock()

        report_asset_sync_status()

        metric_class_mock.assert_not_called()

    @mock.patch("services.web.databus.tasks.Metric")
    @mock.patch("django.core.cache.cache.add")
    @mock.patch("services.web.databus.tasks.AssetSyncAnomalyEvent")
    def test_event_status_failed(self, event_class_mock, cache_add_mock, metric_class_mock):
        """FAILED 状态资产应上报 STATUS_FAILED 异常事件。"""
        metric_class_mock.return_value = mock.Mock()
        event_class_mock.return_value = mock.Mock()
        cache_add_mock.return_value = True

        report_asset_sync_status()

        event_class_mock.assert_called_once()
        context = event_class_mock.call_args[1]["context"]
        self.assertEqual(context["reason"], AssetSyncAnomalyReason.STATUS_FAILED.value)
        self.assertEqual(context["resource_type_id"], "rt_failed")
        event_class_mock.return_value.report.assert_called_once()

    @mock.patch("services.web.databus.tasks.Metric")
    @mock.patch("django.core.cache.cache.add")
    @mock.patch("services.web.databus.tasks.AssetSyncAnomalyEvent")
    def test_event_preparing_timeout(self, event_class_mock, cache_add_mock, metric_class_mock):
        """PREPARING 超过阈值应上报 PREPARING_TIMEOUT 事件。"""
        # 绕过 auto_now，将 updated_at 置为 7 小时前（默认阈值 6h）
        Snapshot.objects.filter(pk=self.snapshot_preparing.pk).update(updated_at=timezone.now() - timedelta(hours=7))
        metric_class_mock.return_value = mock.Mock()
        event_class_mock.return_value = mock.Mock()
        cache_add_mock.return_value = True

        report_asset_sync_status()

        reasons = {call[1]["context"]["reason"] for call in event_class_mock.call_args_list}
        self.assertIn(AssetSyncAnomalyReason.PREPARING_TIMEOUT.value, reasons)

    @mock.patch("services.web.databus.tasks.Metric")
    @mock.patch("django.core.cache.cache.add")
    @mock.patch("services.web.databus.tasks.AssetSyncAnomalyEvent")
    def test_event_preparing_within_threshold_no_event(self, event_class_mock, cache_add_mock, metric_class_mock):
        """PREPARING 未超阈值不应触发 PREPARING_TIMEOUT 事件。"""
        # updated_at 为刚创建（近期），不触发超时
        metric_class_mock.return_value = mock.Mock()
        event_class_mock.return_value = mock.Mock()
        cache_add_mock.return_value = True

        report_asset_sync_status()

        # FAILED 仍会触发事件，但 PREPARING 不应触发
        reasons = {call[1]["context"]["reason"] for call in event_class_mock.call_args_list}
        self.assertNotIn(AssetSyncAnomalyReason.PREPARING_TIMEOUT.value, reasons)

    @mock.patch("services.web.databus.tasks.Metric")
    @mock.patch("django.core.cache.cache.add")
    @mock.patch("services.web.databus.tasks.AssetSyncAnomalyEvent")
    def test_no_event_for_running_snapshot(self, event_class_mock, cache_add_mock, metric_class_mock):
        """仅 RUNNING 状态资产时不应触发任何状态类异常事件。"""
        # 删除除 RUNNING 外的所有非 CLOSED 快照
        Snapshot.objects.filter(resource_type_id__in=["rt_failed", "rt_preparing"]).update(
            status=SnapshotRunningStatus.CLOSED.value
        )
        metric_class_mock.return_value = mock.Mock()
        event_class_mock.return_value = mock.Mock()
        cache_add_mock.return_value = True

        report_asset_sync_status()

        event_class_mock.assert_not_called()

    @mock.patch("services.web.databus.tasks.Metric")
    @mock.patch("django.core.cache.cache.add")
    @mock.patch("services.web.databus.tasks.AssetSyncAnomalyEvent")
    def test_event_dedup_suppresses_repeat(self, event_class_mock, cache_add_mock, metric_class_mock):
        """去重命中时同一异常事件不应重复上报。"""
        metric_class_mock.return_value = mock.Mock()
        event_class_mock.return_value = mock.Mock()

        # 第一次：缓存未命中 → FAILED 事件上报
        cache_add_mock.return_value = True
        report_asset_sync_status()
        self.assertEqual(event_class_mock.call_count, 1)

        # 第二次：缓存命中 → 事件被去重抑制
        cache_add_mock.return_value = False
        report_asset_sync_status()
        self.assertEqual(event_class_mock.call_count, 1)


class ReportAssetSyncCountTests(TestCase):
    """资产同步「数量差异」上报任务（report_asset_sync_count）测试。"""

    def setUp(self) -> None:
        super().setUp()
        self.snapshot_running = Snapshot.objects.create(
            system_id="test_system",
            resource_type_id="rt_running",
            status=SnapshotRunningStatus.RUNNING.value,
            join_data_type=JoinDataType.ASSET.value,
        )

    def _create_stat(self, resource_type_id="rt_running", **kwargs):
        defaults = dict(
            system_id="test_system",
            resource_type_id=resource_type_id,
            join_data_type=JoinDataType.ASSET.value,
            http_pull_count=100,
            doris_storage_count=100,
            hdfs_storage_count=100,
            result=True,
        )
        defaults.update(kwargs)
        return SnapshotCheckStatistic.objects.create(**defaults)

    @mock.patch("services.web.databus.tasks.Metric")
    def test_metric_calculates_diff_correctly(self, metric_class_mock):
        """数量差异指标（doris/hdfs）应计算正确。"""
        metric_class_mock.return_value = mock.Mock()
        self._create_stat(doris_storage_count=95, hdfs_storage_count=90)

        report_asset_sync_count()

        metric_class_mock.assert_called_once()
        records = metric_class_mock.call_args[1]["records"]
        self.assertEqual(len(records), 2)
        doris = next(r for r in records if r["dimension"]["storage_type"] == StorageType.DORIS.value)
        hdfs = next(r for r in records if r["dimension"]["storage_type"] == StorageType.HDFS.value)
        self.assertEqual(doris["metrics"]["diff_count"], 5)
        self.assertAlmostEqual(doris["metrics"]["diff_rate"], 0.05, places=4)
        self.assertEqual(hdfs["metrics"]["diff_count"], 10)
        self.assertAlmostEqual(hdfs["metrics"]["diff_rate"], 0.1, places=4)

    @mock.patch("services.web.databus.tasks.Metric")
    def test_metric_diff_rate_zero_when_pull_count_zero(self, metric_class_mock):
        """源端量为 0 时 diff_rate 应为 0，不应除零报错。"""
        metric_class_mock.return_value = mock.Mock()
        self._create_stat(http_pull_count=0, doris_storage_count=0, hdfs_storage_count=0)

        report_asset_sync_count()

        records = metric_class_mock.call_args[1]["records"]
        for record in records:
            self.assertEqual(record["metrics"]["diff_rate"], 0)

    @mock.patch("services.web.databus.tasks.Metric")
    def test_metric_diff_count_clamped_when_storage_exceeds_pull(self, metric_class_mock):
        """存储量大于源端量（增量拉取/历史残留）时 diff_count 应收敛为 0，不应为负。"""
        metric_class_mock.return_value = mock.Mock()
        # 源端 100，存储 150 → 原始差异 -50，应收敛为 0
        self._create_stat(http_pull_count=100, doris_storage_count=150, hdfs_storage_count=200)

        report_asset_sync_count()

        records = metric_class_mock.call_args[1]["records"]
        for record in records:
            self.assertGreaterEqual(record["metrics"]["diff_count"], 0)
            self.assertEqual(record["metrics"]["diff_count"], 0)
            self.assertEqual(record["metrics"]["diff_rate"], 0)

    @mock.patch("services.web.databus.tasks.Metric")
    def test_metric_excludes_closed_assets(self, metric_class_mock):
        """CLOSED 资产的统计记录不应上报。"""
        metric_class_mock.return_value = mock.Mock()
        # 将唯一的非 CLOSED 快照置为 CLOSED
        Snapshot.objects.filter(pk=self.snapshot_running.pk).update(status=SnapshotRunningStatus.CLOSED.value)
        self._create_stat()

        report_asset_sync_count()

        metric_class_mock.assert_not_called()

    @mock.patch("services.web.databus.tasks.Metric")
    def test_metric_not_called_when_no_statistics(self, metric_class_mock):
        """无统计记录时不应上报指标。"""
        metric_class_mock.return_value = mock.Mock()

        report_asset_sync_count()

        metric_class_mock.assert_not_called()

    @mock.patch("services.web.databus.tasks.Metric")
    @mock.patch("services.web.databus.tasks.AssetSyncAnomalyEvent")
    def test_event_source_pull_failed(self, event_class_mock, metric_class_mock):
        """error_type=source 应上报 SOURCE_PULL_FAILED 事件。"""
        metric_class_mock.return_value = mock.Mock()
        event_class_mock.return_value = mock.Mock()
        self._create_stat(
            http_pull_count=0, doris_storage_count=0, hdfs_storage_count=0, result=False, error_type="source"
        )

        report_asset_sync_count()

        event_class_mock.assert_called_once()
        context = event_class_mock.call_args[1]["context"]
        self.assertEqual(context["reason"], AssetSyncAnomalyReason.SOURCE_PULL_FAILED.value)
        event_class_mock.return_value.report.assert_called_once()

    @mock.patch("services.web.databus.tasks.Metric")
    @mock.patch("services.web.databus.tasks.AssetSyncAnomalyEvent")
    def test_event_storage_query_failed(self, event_class_mock, metric_class_mock):
        """error_type=storage 应上报 STORAGE_QUERY_FAILED 事件。"""
        metric_class_mock.return_value = mock.Mock()
        event_class_mock.return_value = mock.Mock()
        self._create_stat(
            http_pull_count=100, doris_storage_count=50, hdfs_storage_count=50, result=False, error_type="storage"
        )

        report_asset_sync_count()

        event_class_mock.assert_called_once()
        context = event_class_mock.call_args[1]["context"]
        self.assertEqual(context["reason"], AssetSyncAnomalyReason.STORAGE_QUERY_FAILED.value)

    @mock.patch("services.web.databus.tasks.Metric")
    @mock.patch("services.web.databus.tasks.AssetSyncAnomalyEvent")
    def test_event_storage_failed_when_source_count_zero(self, event_class_mock, metric_class_mock):
        """源端量=0 但 error_type=storage 时应上报 STORAGE_QUERY_FAILED"""
        metric_class_mock.return_value = mock.Mock()
        event_class_mock.return_value = mock.Mock()
        self._create_stat(
            http_pull_count=0, doris_storage_count=0, hdfs_storage_count=0, result=False, error_type="storage"
        )

        report_asset_sync_count()

        event_class_mock.assert_called_once()
        context = event_class_mock.call_args[1]["context"]
        self.assertEqual(context["reason"], AssetSyncAnomalyReason.STORAGE_QUERY_FAILED.value)

    @mock.patch("services.web.databus.tasks.Metric")
    @mock.patch("services.web.databus.tasks.AssetSyncAnomalyEvent")
    def test_no_event_when_result_true(self, event_class_mock, metric_class_mock):
        """检查通过（result=True）时不应上报数据类事件。"""
        metric_class_mock.return_value = mock.Mock()
        event_class_mock.return_value = mock.Mock()
        self._create_stat(result=True)

        report_asset_sync_count()

        event_class_mock.assert_not_called()

    @mock.patch("services.web.databus.tasks.Metric")
    @mock.patch("services.web.databus.tasks.AssetSyncAnomalyEvent")
    def test_no_event_for_basic_join_data_type(self, event_class_mock, metric_class_mock):
        """basic 类型（存 Redis，查 doris/hdfs 必然失败）不应产生误报事件"""
        metric_class_mock.return_value = mock.Mock()
        event_class_mock.return_value = mock.Mock()
        # basic 快照 RUNNING
        Snapshot.objects.create(
            system_id="test_system",
            resource_type_id="rt_basic",
            status=SnapshotRunningStatus.RUNNING.value,
            join_data_type=JoinDataType.BASIC.value,
        )
        # basic 的错误统计记录（模拟 check_join_data 对 basic 的无效存储查询结果）
        SnapshotCheckStatistic.objects.create(
            system_id="test_system",
            resource_type_id="rt_basic",
            join_data_type=JoinDataType.BASIC.value,
            http_pull_count=100,
            doris_storage_count=0,
            hdfs_storage_count=0,
            result=False,
            error_type="storage",
        )
        # asset 快照正常，确保 metric_records 非空、不触发 early-return
        self._create_stat(resource_type_id="rt_running", result=True)

        report_asset_sync_count()

        # basic 不应触发任何事件
        event_class_mock.assert_not_called()

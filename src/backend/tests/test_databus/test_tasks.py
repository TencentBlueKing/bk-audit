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

from typing import Dict
from unittest import mock

from bk_resource.exceptions import APIRequestError
from django.conf import settings

from apps.meta.models import ResourceType, System
from apps.permission.handlers.resource_types import ResourceEnum
from services.web.databus.constants import (
    ASSET_RISK_BKBASE_RT_ID_KEY,
    ASSET_STRATEGY_BKBASE_RT_ID_KEY,
    ASSET_STRATEGY_TAG_BKBASE_RT_ID_KEY,
    ASSET_TICKET_NODE_BKBASE_RT_ID_KEY,
    ASSET_TICKET_PERMISSION_BKBASE_RT_ID_KEY,
    JoinDataType,
    SnapshotRunningStatus,
)
from services.web.databus.models import CollectorConfig, CollectorPlugin, Snapshot
from services.web.databus.tasks import (
    change_storage_cluster,
    create_api_push_etl,
    refresh_system_snapshots,
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

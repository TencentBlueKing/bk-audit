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

from django.conf import settings

from apps.permission.handlers.resource_types import ResourceEnum
from services.web.databus.constants import (
    ASSET_RISK_BKBASE_RT_ID_KEY,
    ASSET_STRATEGY_BKBASE_RT_ID_KEY,
    ASSET_STRATEGY_TAG_BKBASE_RT_ID_KEY,
    ASSET_TICKET_PERMISSION_BKBASE_RT_ID_KEY,
    JoinDataType,
    SnapshotRunningStatus,
)
from services.web.databus.models import Snapshot
from services.web.databus.tasks import sync_asset_bkbase_rt_ids
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
        ]
        config_set_mock.assert_has_calls(expected_calls, any_order=True)

    @mock.patch("services.web.databus.tasks.GlobalMetaConfig.set")
    @mock.patch("services.web.databus.tasks.GlobalMetaConfig.get")
    @mock.patch("services.web.databus.tasks.Snapshot.objects")
    def test_sync_asset_bkbase_rt_ids_skip_when_already_configured(
        self, snapshot_objects_mock, config_get_mock, config_set_mock
    ):
        """已有配置的 namespace 应跳过，不再重复写入。"""
        config_get_mock.side_effect = ["existing_rt", "", "", ""]

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

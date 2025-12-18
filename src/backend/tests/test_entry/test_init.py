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
from django.test.utils import override_settings

from apps.permission.handlers.resource_types import ResourceEnum
from services.web.databus.constants import JoinDataType, SnapShotStorageChoices
from services.web.entry.constants import INIT_ASSET_FINISHED_KEY
from services.web.entry.init.base import SystemInitHandler
from tests.base import TestCase


@override_settings(BKAPP_INIT_SYSTEM="True")
class SystemInitAssetTests(TestCase):
    def setUp(self):
        super().setUp()
        self.handler = SystemInitHandler()

    @mock.patch("services.web.entry.init.base.GlobalMetaConfig.get")
    @mock.patch("services.web.entry.init.base.GlobalMetaConfig.set")
    @mock.patch("services.web.entry.init.base.resource.databus.collector.toggle_join_data")
    def test_init_asset_enable_new_assets(self, mock_toggle, mock_set, mock_get):
        mock_get.return_value = {}

        self.handler.init_asset()

        expected_calls = []
        for resource_cls in [ResourceEnum.RISK, ResourceEnum.STRATEGY, ResourceEnum.STRATEGY_TAG]:
            expected_calls.append(
                mock.call(
                    {
                        "system_id": resource_cls.system_id,
                        "resource_type_id": resource_cls.id,
                        "is_enabled": True,
                        "join_data_type": JoinDataType.ASSET.value,
                        "storage_type": [
                            SnapShotStorageChoices.HDFS.value,
                            SnapShotStorageChoices.DORIS.value,
                        ],
                    }
                )
            )

        mock_toggle.assert_has_calls(expected_calls, any_order=True)

        saved_status: Dict[str, bool] = mock_set.call_args.args[1]
        self.assertEqual(mock_set.call_args.args[0], INIT_ASSET_FINISHED_KEY)
        for resource_cls in [ResourceEnum.RISK, ResourceEnum.STRATEGY, ResourceEnum.STRATEGY_TAG]:
            key = f"{resource_cls.system_id}-{resource_cls.id}"
            self.assertTrue(saved_status.get(key))

    @mock.patch("services.web.entry.init.base.GlobalMetaConfig.get")
    @mock.patch("services.web.entry.init.base.GlobalMetaConfig.set")
    @mock.patch("services.web.entry.init.base.resource.databus.collector.toggle_join_data")
    def test_init_asset_skip_existing(self, mock_toggle, mock_set, mock_get):
        key = f"{settings.BK_IAM_SYSTEM_ID}-{ResourceEnum.RISK.id}"
        mock_get.return_value = {key: True}

        self.handler.init_asset()

        mock_toggle.assert_any_call(
            {
                "system_id": ResourceEnum.STRATEGY.system_id,
                "resource_type_id": ResourceEnum.STRATEGY.id,
                "is_enabled": True,
                "join_data_type": JoinDataType.ASSET.value,
                "storage_type": [
                    SnapShotStorageChoices.HDFS.value,
                    SnapShotStorageChoices.DORIS.value,
                ],
            }
        )
        mock_toggle.assert_any_call(
            {
                "system_id": ResourceEnum.STRATEGY_TAG.system_id,
                "resource_type_id": ResourceEnum.STRATEGY_TAG.id,
                "is_enabled": True,
                "join_data_type": JoinDataType.ASSET.value,
                "storage_type": [
                    SnapShotStorageChoices.HDFS.value,
                    SnapShotStorageChoices.DORIS.value,
                ],
            }
        )
        # ensure risk was skipped
        skipped_call = mock.call(
            {
                "system_id": ResourceEnum.RISK.system_id,
                "resource_type_id": ResourceEnum.RISK.id,
                "is_enabled": True,
                "join_data_type": JoinDataType.ASSET.value,
                "storage_type": [
                    SnapShotStorageChoices.HDFS.value,
                    SnapShotStorageChoices.DORIS.value,
                ],
            }
        )
        self.assertNotIn(skipped_call, mock_toggle.call_args_list)

    @mock.patch("services.web.entry.init.base.GlobalMetaConfig.get")
    @mock.patch("services.web.entry.init.base.GlobalMetaConfig.set")
    @mock.patch("services.web.entry.init.base.resource.databus.collector.toggle_join_data")
    def test_init_asset_failure_recorded(self, mock_toggle, mock_set, mock_get):
        error = RuntimeError("mock failure")
        mock_get.return_value = {}
        mock_toggle.side_effect = error

        self.handler.init_asset()

        saved_status = mock_set.call_args.args[1]
        for resource_cls in [ResourceEnum.RISK, ResourceEnum.STRATEGY, ResourceEnum.STRATEGY_TAG]:
            key = f"{resource_cls.system_id}-{resource_cls.id}"
            self.assertFalse(saved_status.get(key))

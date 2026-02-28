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
from services.web.databus.constants import (
    CLEAN_CONFIG_JSON_CONF_KEY,
    JoinDataType,
    SnapshotRunningStatus,
    SnapShotStorageChoices,
)
from services.web.databus.models import Snapshot
from services.web.entry.constants import (
    AUDIT_DOC_CONFIG_KEY,
    INIT_ASSET_FINISHED_KEY,
    INIT_SYSTEM_RULE_AUDIT_FINISHED_KEY,
    SDK_CONFIG_KEY,
)
from services.web.entry.init.base import SystemInitHandler
from services.web.strategy_v2.models import Strategy
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
        for resource_cls in [
            ResourceEnum.RISK,
            ResourceEnum.STRATEGY,
            ResourceEnum.STRATEGY_TAG,
            ResourceEnum.TICKET_NODE,
        ]:
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
        for resource_cls in [
            ResourceEnum.RISK,
            ResourceEnum.STRATEGY,
            ResourceEnum.STRATEGY_TAG,
            ResourceEnum.TICKET_NODE,
        ]:
            key = f"{resource_cls.system_id}-{resource_cls.id}"
            self.assertTrue(saved_status.get(key))

    @mock.patch("services.web.entry.init.base.GlobalMetaConfig.get")
    @mock.patch("services.web.entry.init.base.GlobalMetaConfig.set")
    @mock.patch("services.web.entry.init.base.resource.databus.collector.toggle_join_data")
    def test_init_asset_manual_event_with_custom_conf(self, mock_toggle, mock_set, mock_get):
        mock_get.return_value = {}

        self.handler.init_asset()

        manual_call = mock.call(
            {
                "system_id": ResourceEnum.MANUAL_EVENT.system_id,
                "resource_type_id": ResourceEnum.MANUAL_EVENT.id,
                "is_enabled": True,
                "join_data_type": JoinDataType.ASSET.value,
                "storage_type": [
                    SnapShotStorageChoices.HDFS.value,
                    SnapShotStorageChoices.DORIS.value,
                ],
                "custom_config": {
                    CLEAN_CONFIG_JSON_CONF_KEY: {
                        "time_format": "Unix Time Stamp(milliseconds)",
                        "timestamp_len": 13,
                        "timezone": 0,
                        "time_field_name": "event_time_timestamp",
                    }
                },
            }
        )
        self.assertIn(manual_call, mock_toggle.call_args_list)

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
        for resource_cls in [
            ResourceEnum.RISK,
            ResourceEnum.STRATEGY,
            ResourceEnum.STRATEGY_TAG,
            ResourceEnum.TICKET_NODE,
        ]:
            key = f"{resource_cls.system_id}-{resource_cls.id}"
            self.assertFalse(saved_status.get(key))


@override_settings(BKAPP_INIT_SYSTEM="True")
class SystemInitRuleAuditTests(TestCase):
    def setUp(self):
        super().setUp()
        self.handler = SystemInitHandler()

    @mock.patch("services.web.entry.init.base.resource.strategy_v2.create_strategy")
    @mock.patch("services.web.entry.init.base.GlobalMetaConfig.set")
    @mock.patch("services.web.entry.init.base.GlobalMetaConfig.get")
    def test_init_system_rule_audit_create(self, mock_get, mock_set, mock_create):
        mock_get.return_value = False
        snapshot = Snapshot.objects.create(
            system_id=ResourceEnum.MANUAL_EVENT.system_id,
            resource_type_id=ResourceEnum.MANUAL_EVENT.id,
            bkbase_table_id="test_rt_id",
            status=SnapshotRunningStatus.RUNNING.value,
            join_data_type=JoinDataType.ASSET.value,
        )

        self.handler.init_system_rule_audit()

        mock_create.assert_called_once()
        params = mock_create.call_args.kwargs
        self.assertEqual(params["configs"]["data_source"]["rt_id"], snapshot.bkbase_table_id)
        self.assertEqual(mock_set.call_args.args[0], INIT_SYSTEM_RULE_AUDIT_FINISHED_KEY)

    @mock.patch("services.web.entry.init.base.resource.strategy_v2.create_strategy")
    @mock.patch("services.web.entry.init.base.GlobalMetaConfig.set")
    @mock.patch("services.web.entry.init.base.GlobalMetaConfig.get")
    def test_init_system_rule_audit_skip_when_exists(self, mock_get, mock_set, mock_create):
        mock_get.return_value = False
        Snapshot.objects.create(
            system_id=ResourceEnum.MANUAL_EVENT.system_id,
            resource_type_id=ResourceEnum.MANUAL_EVENT.id,
            bkbase_table_id="test_rt_id",
            status=SnapshotRunningStatus.RUNNING.value,
            join_data_type=JoinDataType.ASSET.value,
        )
        Strategy.objects.create(namespace=settings.DEFAULT_NAMESPACE, strategy_name="手动新建风险", strategy_type="rule")

        self.handler.init_system_rule_audit()

        mock_create.assert_not_called()
        self.assertEqual(mock_set.call_args.args[0], INIT_SYSTEM_RULE_AUDIT_FINISHED_KEY)


@override_settings(BKAPP_INIT_SYSTEM="True")
class SystemInitSdkConfigTests(TestCase):
    """测试 init_sdk_config 方法"""

    def setUp(self):
        super().setUp()
        self.handler = SystemInitHandler()

    @mock.patch("services.web.entry.init.base.GlobalMetaConfig.set")
    @override_settings(
        BKAPP_GO_SDK_CONFIG='{"doc": "go_sdk_doc"}',
        BKAPP_JAVA_SDK_CONFIG='{"doc": "java_sdk_doc"}',
        BKAPP_PYTHON_SDK_CONFIG='{"doc": "python_sdk_doc"}',
    )
    def test_init_sdk_config_with_env(self, mock_set):
        """测试从 settings 读取 SDK 配置"""
        self.handler.init_sdk_config()

        mock_set.assert_called_once()
        call_args = mock_set.call_args
        self.assertEqual(call_args.args[0], SDK_CONFIG_KEY)
        sdk_config = call_args.args[1]
        self.assertEqual(sdk_config["go_sdk"], '{"doc": "go_sdk_doc"}')
        self.assertEqual(sdk_config["java_sdk"], '{"doc": "java_sdk_doc"}')
        self.assertEqual(sdk_config["python_sdk"], '{"doc": "python_sdk_doc"}')


@override_settings(BKAPP_INIT_SYSTEM="True")
class SystemInitDocConfigTests(TestCase):
    """测试 init_doc_config 方法"""

    def setUp(self):
        super().setUp()
        self.handler = SystemInitHandler()

    @mock.patch("services.web.entry.init.base.GlobalMetaConfig.set")
    @override_settings(
        BKAPP_AUDIT_ACCESS_GUIDE="https://example.com/guide",
        BKAPP_AUDIT_OPERATION_LOG_RECORD_STANDARDS="https://example.com/standards",
    )
    def test_init_doc_config_with_env(self, mock_set):
        """测试从 settings 读取文档配置"""
        self.handler.init_doc_config()

        mock_set.assert_called_once()
        call_args = mock_set.call_args
        self.assertEqual(call_args.args[0], AUDIT_DOC_CONFIG_KEY)
        doc_config = call_args.args[1]
        self.assertEqual(doc_config["audit_access_guide"], "https://example.com/guide")
        self.assertEqual(doc_config["audit_operation_log_record_standards"], "https://example.com/standards")

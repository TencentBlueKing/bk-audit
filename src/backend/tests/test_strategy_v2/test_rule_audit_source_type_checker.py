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

from unittest import mock
from unittest.mock import MagicMock

from django.conf import settings

from api.bk_base.default import GetResultTable, GetResultTables
from apps.meta.constants import ConfigLevelChoices
from apps.meta.models import GlobalMetaConfig
from services.web.databus.constants import COLLECTOR_PLUGIN_ID
from services.web.databus.models import CollectorConfig, CollectorPlugin
from services.web.strategy_v2.constants import RuleAuditSourceType
from services.web.strategy_v2.utils.table import RuleAuditSourceTypeChecker
from tests.base import TestCase
from tests.test_databus.collector.constants import (
    COLLECTOR_DATA,
    PLUGIN_DATA,
    PLUGIN_ID,
)
from tests.test_strategy_v2.constants import (
    ASSET_GET_RESULT_TABLE_DATA,
    COLLECTOR_GET_RESULT_TABLE_DATA,
    OTHERS_BATCH_GET_RESULT_TABLE_DATA,
    OTHERS_BATCH_REAL_GET_RESULT_TABLE_DATA,
    OTHERS_REAL_GET_RESULT_TABLE_DATA,
)


class TestRuleAuditSourceTypeChecker(TestCase):
    def setUp(self):
        self.checker = RuleAuditSourceTypeChecker(namespace=settings.DEFAULT_NAMESPACE)
        self.collector = CollectorConfig.objects.create(**COLLECTOR_DATA)
        CollectorPlugin.objects.create(**PLUGIN_DATA)
        GlobalMetaConfig.set(
            COLLECTOR_PLUGIN_ID,
            PLUGIN_ID,
            config_level=ConfigLevelChoices.NAMESPACE.value,
            instance_key=self.namespace,
        )

    @mock.patch.object(GetResultTable, "perform_request", lambda *args, **kwargs: COLLECTOR_GET_RESULT_TABLE_DATA)
    def test_rule_audit_source_type_check_log(self):
        """
        测试日志 RT
        """

        actual = self.checker.rt_support_source_types(rt_id="test")
        expect = [
            RuleAuditSourceType.REALTIME.value,
            RuleAuditSourceType.BATCH.value,
        ]
        self.assertEqual(actual, expect)

    @mock.patch.object(GetResultTable, "perform_request", lambda *args, **kwargs: ASSET_GET_RESULT_TABLE_DATA)
    def test_rule_audit_source_type_check_asset(self):
        """
        测试资产 RT
        """
        actual = self.checker.rt_support_source_types(rt_id="test")
        expect = [
            RuleAuditSourceType.REALTIME.value,
            RuleAuditSourceType.BATCH.value,
        ]
        self.assertEqual(actual, expect)

    def test_rule_audit_source_type_check_other(self):
        """
        测试其他数据
        """

        # 可实时
        with mock.patch.object(
            GetResultTable, "perform_request", lambda *args, **kwargs: OTHERS_REAL_GET_RESULT_TABLE_DATA
        ):
            actual = self.checker.rt_support_source_types(rt_id="test")
            expect = [
                RuleAuditSourceType.REALTIME.value,
            ]
            self.assertEqual(actual, expect)

        # 可离线
        with mock.patch.object(
            GetResultTable, "perform_request", lambda *args, **kwargs: OTHERS_BATCH_GET_RESULT_TABLE_DATA
        ):
            actual = self.checker.rt_support_source_types(rt_id="test")
            expect = [
                RuleAuditSourceType.BATCH.value,
            ]
            self.assertEqual(actual, expect)

        # 可实时，可离线
        with mock.patch.object(
            GetResultTable, "perform_request", lambda *args, **kwargs: OTHERS_BATCH_REAL_GET_RESULT_TABLE_DATA
        ):
            actual = self.checker.rt_support_source_types(rt_id="test")
            expect = [
                RuleAuditSourceType.REALTIME.value,
                RuleAuditSourceType.BATCH.value,
            ]
            self.assertEqual(actual, expect)

    def test_rule_audit_source_type_check_link_table(self):
        """
        测试联表
        """

        # 日志&资产联表 -> 实时&离线
        log_rt = CollectorPlugin.build_collector_rt(namespace=self.namespace)
        mock_link_table_obj = MagicMock()
        mock_link_table_obj.rt_ids = [log_rt, "asset_rt_2"]

        with mock.patch.object(
            GetResultTables,
            "perform_request",
            lambda *args, **kwargs: [
                ASSET_GET_RESULT_TABLE_DATA,
            ],
        ):
            with mock.patch("services.web.strategy_v2.resources.get_object_or_404", return_value=mock_link_table_obj):
                actual = self.checker.link_table_support_source_types(link_table=mock_link_table_obj)
                expect = [
                    RuleAuditSourceType.REALTIME,
                    RuleAuditSourceType.BATCH,
                ]
                self.assertEqual(actual, expect)

        # 资产联表 -> 离线
        mock_link_table_obj = MagicMock()
        mock_link_table_obj.rt_ids = ["asset_1", "asset_2"]

        with mock.patch.object(
            GetResultTables,
            "perform_request",
            lambda *args, **kwargs: [ASSET_GET_RESULT_TABLE_DATA, ASSET_GET_RESULT_TABLE_DATA],
        ):
            with mock.patch("services.web.strategy_v2.resources.get_object_or_404", return_value=mock_link_table_obj):
                actual = self.checker.link_table_support_source_types(link_table=mock_link_table_obj)
                expect = [
                    RuleAuditSourceType.BATCH,
                ]
                self.assertEqual(actual, expect)

        # 日志与其他资产数据联表 - > 实时&离线
        mock_link_table_obj = MagicMock()
        mock_link_table_obj.rt_ids = [log_rt, "asset_1"]

        with mock.patch.object(
            GetResultTables,
            "perform_request",
            lambda *args, **kwargs: [OTHERS_BATCH_REAL_GET_RESULT_TABLE_DATA],
        ):
            with mock.patch("services.web.strategy_v2.resources.get_object_or_404", return_value=mock_link_table_obj):
                actual = self.checker.link_table_support_source_types(link_table=mock_link_table_obj)
                expect = [
                    RuleAuditSourceType.REALTIME,
                    RuleAuditSourceType.BATCH,
                ]
                self.assertEqual(actual, expect)

        # 日志与其他非资产数据联表 -> 无
        mock_link_table_obj = MagicMock()
        mock_link_table_obj.rt_ids = [log_rt, "other_rt"]

        with mock.patch.object(
            GetResultTables,
            "perform_request",
            lambda *args, **kwargs: [OTHERS_REAL_GET_RESULT_TABLE_DATA, OTHERS_BATCH_GET_RESULT_TABLE_DATA],
        ):
            with mock.patch("services.web.strategy_v2.resources.get_object_or_404", return_value=mock_link_table_obj):
                actual = self.checker.link_table_support_source_types(link_table=mock_link_table_obj)
                expect = []
                self.assertEqual(actual, expect)

        # 日志与其他非资产数据联表
        mock_link_table_obj = MagicMock()
        mock_link_table_obj.rt_ids = [log_rt, "other_rt"]

        with mock.patch.object(
            GetResultTables,
            "perform_request",
            lambda *args, **kwargs: [OTHERS_REAL_GET_RESULT_TABLE_DATA, OTHERS_BATCH_GET_RESULT_TABLE_DATA],
        ):
            with mock.patch("services.web.strategy_v2.resources.get_object_or_404", return_value=mock_link_table_obj):
                actual = self.checker.link_table_support_source_types(link_table=mock_link_table_obj)
                expect = []
                self.assertEqual(actual, expect)

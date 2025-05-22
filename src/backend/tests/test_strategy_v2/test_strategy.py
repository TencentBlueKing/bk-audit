# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
Copyright (C) 2023 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at https://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

import copy
from unittest import mock

from bk_resource import resource
from django.conf import settings

from api.bk_base.default import GetResultTable
from api.bk_log.constants import INDEX_SET_ID
from apps.meta.constants import ConfigLevelChoices
from apps.meta.models import GlobalMetaConfig
from core.utils.tools import ordered_dict_to_json
from services.web.analyze.models import Control, ControlVersion
from services.web.strategy_v2.constants import RiskLevel, RuleAuditSourceType
from tests.base import TestCase
from tests.test_databus.collector_plugin.test_collector_plugin import (
    CollectorPluginTest,
)
from tests.test_strategy_v2.constants import (
    ASSET_GET_RESULT_TABLE_DATA,
    BKM_CONTROL_DATA,
    BKM_CONTROL_VERSION_DATA,
    BKM_STRATEGY_DATA,
    COLLECTOR_GET_RESULT_TABLE_DATA,
    CREATE_BKM_DATA_RESULT,
    MOCK_INDEX_SET_ID,
    OTHERS_BATCH_GET_RESULT_TABLE_DATA,
    OTHERS_BATCH_REAL_GET_RESULT_TABLE_DATA,
    OTHERS_REAL_GET_RESULT_TABLE_DATA,
    UPDATE_BKM_DATA_RESULT,
)


class StrategyTest(TestCase):
    def setUp(self) -> None:  # NOCC:invalid-name(单元测试)
        CollectorPluginTest().setUp()
        GlobalMetaConfig.set(
            INDEX_SET_ID,
            config_value=MOCK_INDEX_SET_ID,
            config_level=ConfigLevelChoices.NAMESPACE.value,
            instance_key=self.namespace,
        )
        self.c = Control.objects.create(**BKM_CONTROL_DATA)
        self.c_version = ControlVersion.objects.create(**{**BKM_CONTROL_VERSION_DATA, "control_id": self.c.control_id})

    @mock.patch("services.web.analyze.controls.bkm.api.bk_monitor.save_alarm_strategy", mock.Mock(return_value={}))
    def test_create_bkm_strategy(self) -> None:
        """CreateStrategy"""
        data = self._create_bkm_strategy()
        # Create a copy of expected result and update strategy_id dynamically
        expected_result = copy.deepcopy(CREATE_BKM_DATA_RESULT)
        expected_result["strategy_id"] = data["strategy_id"]
        self.assertEqual(ordered_dict_to_json(data), expected_result)

    @mock.patch("services.web.analyze.controls.bkm.api.bk_monitor.save_alarm_strategy", mock.Mock(return_value={}))
    def _create_bkm_strategy(self) -> dict:
        params = copy.deepcopy(BKM_STRATEGY_DATA)
        params.update(
            {
                "control_id": self.c_version.control_id,
                "control_version": self.c_version.control_version,
                "risk_level": RiskLevel.HIGH.value,
                "risk_hazard": "",
                "risk_guidance": "",
                "risk_title": "risk title",
                "processor_groups": ["123"],
            }
        )
        return resource.strategy_v2.create_strategy(**params)

    @mock.patch("services.web.analyze.controls.bkm.api.bk_monitor.save_alarm_strategy", mock.Mock(return_value={}))
    def test_update_bkm_strategy(self) -> None:
        """UpdateStrategy"""
        data = self._create_bkm_strategy()
        params = copy.deepcopy(BKM_STRATEGY_DATA)
        params.update(
            {
                "strategy_id": data["strategy_id"],
                "control_id": self.c_version.control_id,
                "control_version": self.c_version.control_version,
                "risk_level": RiskLevel.HIGH.value,
                "risk_hazard": "",
                "risk_guidance": "",
                "risk_title": "risk_title",
                "processor_groups": ["123"],
            }
        )
        data = resource.strategy_v2.update_strategy(**params)
        # Create a fresh copy of expected result for update test
        expected_result = copy.deepcopy(UPDATE_BKM_DATA_RESULT)
        expected_result["strategy_id"] = data["strategy_id"]
        self.assertEqual(data, expected_result)


class TestRuleAuditSourceTypeCheck(TestCase):
    @mock.patch.object(GetResultTable, "perform_request", lambda *args, **kwargs: COLLECTOR_GET_RESULT_TABLE_DATA)
    def test_rule_audit_source_type_check_log(self):
        """
        测试日志 RT
        """
        actual = resource.strategy_v2.rule_audit_source_type_check(
            {"namespace": settings.DEFAULT_NAMESPACE, "config_type": "EventLog", "rt_id": "test"}
        )
        expect = {
            "support_source_types": [
                RuleAuditSourceType.REALTIME.value,
                RuleAuditSourceType.BATCH.value,
            ]
        }
        self.assertEqual(actual, expect)

    @mock.patch.object(GetResultTable, "perform_request", lambda *args, **kwargs: ASSET_GET_RESULT_TABLE_DATA)
    def test_rule_audit_source_type_check_asset(self):
        """
        测试资产 RT
        """
        actual = resource.strategy_v2.rule_audit_source_type_check(
            {"namespace": settings.DEFAULT_NAMESPACE, "config_type": "BuildIn", "rt_id": "test"}
        )
        expect = {
            "support_source_types": [
                RuleAuditSourceType.REALTIME.value,
                RuleAuditSourceType.BATCH.value,
            ]
        }
        self.assertEqual(actual, expect)

    def test_rule_audit_source_type_check_other(self):
        """
        测试其他数据
        """

        # 可实时
        with mock.patch.object(
            GetResultTable, "perform_request", lambda *args, **kwargs: OTHERS_REAL_GET_RESULT_TABLE_DATA
        ):
            actual = resource.strategy_v2.rule_audit_source_type_check(
                {"namespace": settings.DEFAULT_NAMESPACE, "config_type": "BizRt", "rt_id": "test"}
            )
            expect = {
                "support_source_types": [
                    RuleAuditSourceType.REALTIME.value,
                ]
            }
            self.assertEqual(actual, expect)

        # 可离线
        with mock.patch.object(
            GetResultTable, "perform_request", lambda *args, **kwargs: OTHERS_BATCH_GET_RESULT_TABLE_DATA
        ):
            actual = resource.strategy_v2.rule_audit_source_type_check(
                {"namespace": settings.DEFAULT_NAMESPACE, "config_type": "BizRt", "rt_id": "test"}
            )
            expect = {
                "support_source_types": [
                    RuleAuditSourceType.BATCH.value,
                ]
            }
            self.assertEqual(actual, expect)

        # 可实时，可离线
        with mock.patch.object(
            GetResultTable, "perform_request", lambda *args, **kwargs: OTHERS_BATCH_REAL_GET_RESULT_TABLE_DATA
        ):
            actual = resource.strategy_v2.rule_audit_source_type_check(
                {"namespace": settings.DEFAULT_NAMESPACE, "config_type": "BizRt", "rt_id": "test"}
            )
            expect = {
                "support_source_types": [
                    RuleAuditSourceType.REALTIME.value,
                    RuleAuditSourceType.BATCH.value,
                ]
            }
            self.assertEqual(actual, expect)
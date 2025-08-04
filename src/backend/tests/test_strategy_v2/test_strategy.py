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
from core.utils.data import ordered_dict_to_json
from services.web.analyze.models import Control, ControlVersion
from services.web.strategy_v2.constants import RiskLevel, RuleAuditSourceType
from services.web.strategy_v2.models import StrategyTool
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

    def _inject_tool_config(self, data, field_name="field_1", field_source="basic"):
        key_map = {
            "basic": "event_basic_field_configs",
            "data": "event_data_field_configs",
            "evidence": "event_evidence_field_configs",
        }
        key = key_map.get(field_source, "event_basic_field_configs")
        data[key] = [
            {
                "field_name": field_name,
                "display_name": "字段名",
                "is_priority": True,
                "drill_config": {
                    "tool": {"uid": "fake_tool_uid", "version": 1, "params": {}},
                    "config": [],
                },
            }
        ]

    @mock.patch("services.web.analyze.controls.bkm.api.bk_monitor.save_alarm_strategy", mock.Mock(return_value={}))
    def test_create_bkm_strategy(self) -> None:
        """CreateStrategy"""
        data = self._create_bkm_strategy()
        # Create a copy of expected result and update strategy_id dynamically
        expected_result = copy.deepcopy(CREATE_BKM_DATA_RESULT)
        expected_result["strategy_id"] = data["strategy_id"]
        self.assertEqual(ordered_dict_to_json(data), expected_result)

        tools = StrategyTool.objects.filter(strategy_id=data["strategy_id"])
        self.assertEqual(len(tools), 1)
        tool = tools[0]
        self.assertEqual(tool.field_name, "field_1")
        self.assertEqual(tool.tool_uid, "fake_tool_uid")
        self.assertEqual(tool.tool_version, 1)
        self.assertEqual(tool.field_source, "basic")

    @mock.patch("services.web.analyze.controls.bkm.api.bk_monitor.save_alarm_strategy", mock.Mock(return_value={}))
    def _create_bkm_strategy(self, name_suffix="") -> dict:
        params = copy.deepcopy(BKM_STRATEGY_DATA)
        self._inject_tool_config(params)
        if name_suffix:
            params["strategy_name"] += f"_{name_suffix}"
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
        self._inject_tool_config(params, field_name="field_2", field_source="evidence")
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

        tools = StrategyTool.objects.filter(strategy_id=data["strategy_id"])
        self.assertEqual(len(tools), 1)
        tool = tools[0]
        self.assertEqual(tool.field_name, "field_2")
        self.assertEqual(tool.tool_uid, "fake_tool_uid")
        self.assertEqual(tool.tool_version, 1)
        self.assertEqual(tool.field_source, "evidence")

    @mock.patch("services.web.analyze.controls.bkm.api.bk_monitor.save_alarm_strategy", mock.Mock(return_value={}))
    def test_list_strategy(self):
        """ListStrategy"""
        data1 = self._create_bkm_strategy(name_suffix="11")
        data2 = self._create_bkm_strategy(name_suffix="22")

        result = resource.strategy_v2.list_strategy(namespace=self.namespace, order_field="-strategy_id")

        # 确保返回多个策略
        strategy_ids = [s["strategy_id"] for s in result]
        self.assertIn(data1["strategy_id"], strategy_ids)
        self.assertIn(data2["strategy_id"], strategy_ids)

        # 校验 tool 字段也在（工具数目等）
        for strategy_data in result:
            if strategy_data["strategy_id"] in [data1["strategy_id"], data2["strategy_id"]]:
                self.assertIn("tools", strategy_data)
                self.assertEqual(len(strategy_data["tools"]), 1)
                tool = strategy_data["tools"][0]
                self.assertEqual(tool["tool_uid"], "fake_tool_uid")


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


class StrategyEnumMappingTest(StrategyTest):
    def _create_bkm_strategy_with_enum(self, enum_mappings: dict) -> dict:
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
                "event_basic_field_configs": [
                    {
                        "field_name": "username",
                        "display_name": "username",
                        "is_priority": True,
                        "description": "",
                        "enum_mappings": enum_mappings,
                    }
                ],
            }
        )
        return resource.strategy_v2.create_strategy(**params)

    @mock.patch(
        "services.web.analyze.controls.bkm.api.bk_monitor.save_alarm_strategy",
        mock.Mock(return_value={}),
    )
    def test_create_strategy_enum_mappings(self) -> None:
        enum_mappings = {
            "collection_id": "test_collection",
            "mappings": [{"key": "1", "name": "one"}],
        }
        data = self._create_bkm_strategy_with_enum(enum_mappings)
        strategy_id = data["strategy_id"]
        result = resource.meta.get_enum_mapping_by_collection(
            collection_id=enum_mappings["collection_id"],
            related_type="strategy",
            related_object_id=strategy_id,
        )
        expected = [
            {
                "collection_id": enum_mappings["collection_id"],
                "key": enum_mappings["mappings"][0]["key"],
                "name": enum_mappings["mappings"][0]["name"],
            }
        ]
        self.assertEqual(result, expected)
        relation = resource.meta.get_enum_mappings_relation(related_type="strategy", related_object_id=strategy_id)
        self.assertEqual(relation, [enum_mappings["collection_id"]])

    @mock.patch(
        "services.web.analyze.controls.bkm.api.bk_monitor.save_alarm_strategy",
        mock.Mock(return_value={}),
    )
    def test_update_strategy_enum_mappings_delete(self) -> None:
        enum_mappings = {
            "collection_id": "test_collection",
            "mappings": [{"key": "1", "name": "one"}],
        }
        data = self._create_bkm_strategy_with_enum(enum_mappings)
        strategy_id = data["strategy_id"]
        params = copy.deepcopy(BKM_STRATEGY_DATA)
        params.update(
            {
                "strategy_id": strategy_id,
                "control_id": self.c_version.control_id,
                "control_version": self.c_version.control_version,
                "risk_level": RiskLevel.HIGH.value,
                "risk_hazard": "",
                "risk_guidance": "",
                "risk_title": "risk_title",
                "processor_groups": ["123"],
                "event_basic_field_configs": [
                    {
                        "field_name": "username",
                        "display_name": "username",
                        "is_priority": True,
                        "description": "",
                        "enum_mappings": {
                            "collection_id": enum_mappings["collection_id"],
                            "mappings": [],
                        },
                    }
                ],
            }
        )
        resource.strategy_v2.update_strategy(**params)
        relation = resource.meta.get_enum_mappings_relation(related_type="strategy", related_object_id=strategy_id)
        self.assertEqual(relation, [])


class StrategyEnumMappingResourceTest(TestCase):
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

    def _create_bkm_strategy_with_enum(self, enum_mappings: dict) -> dict:
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
                "event_basic_field_configs": [
                    {
                        "field_name": "username",
                        "display_name": "username",
                        "is_priority": True,
                        "description": "",
                        "enum_mappings": enum_mappings,
                    }
                ],
            }
        )
        return resource.strategy_v2.create_strategy(**params)

    def test_get_strategy_enum_mapping_by_collection_keys(self) -> None:
        resource.meta.batch_update_enum_mappings(
            collection_id="test",
            mappings=[{"key": "1", "name": "one"}],
            related_type="strategy",
            related_object_id=1,
        )
        resource.meta.batch_update_enum_mappings(
            collection_id="test2",
            mappings=[{"key": "2", "name": "two"}],
            related_type="strategy",
            related_object_id=1,
        )
        params = {
            "collection_keys": [
                {"collection_id": "test", "key": "1"},
                {"collection_id": "test2", "key": "2"},
            ],
            "related_type": "strategy",
            "related_object_id": 1,
        }
        result = resource.strategy_v2.get_strategy_enum_mapping_by_collection_keys(**params)
        result = sorted(result, key=lambda x: x["collection_id"])
        expected = [
            {"collection_id": "test", "key": "1", "name": "one"},
            {"collection_id": "test2", "key": "2", "name": "two"},
        ]
        self.assertEqual(result, expected)

    @mock.patch(
        "services.web.analyze.controls.bkm.api.bk_monitor.save_alarm_strategy",
        mock.Mock(return_value={}),
    )
    def test_get_strategy_enum_mapping_by_collection(self) -> None:
        enum_mappings = {
            "collection_id": "test",
            "mappings": [{"key": "1", "name": "one"}],
        }
        data = self._create_bkm_strategy_with_enum(enum_mappings)
        params = {
            "collection_id": enum_mappings["collection_id"],
            "related_type": "strategy",
            "related_object_id": data["strategy_id"],
        }
        result = resource.strategy_v2.get_strategy_enum_mapping_by_collection(**params)
        expected = [
            {
                "collection_id": enum_mappings["collection_id"],
                "key": enum_mappings["mappings"][0]["key"],
                "name": enum_mappings["mappings"][0]["name"],
            }
        ]
        self.assertEqual(result, expected)

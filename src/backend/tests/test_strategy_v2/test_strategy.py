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
from services.web.strategy_v2.constants import (
    RiskLevel,
    RuleAuditConfigType,
    RuleAuditFieldType,
    RuleAuditSourceType,
    StrategyReportStatus,
    StrategySource,
    StrategyStatusChoices,
)
from services.web.strategy_v2.models import Strategy, StrategyTool
from services.web.strategy_v2.resources import CreateStrategy, UpdateStrategy
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
            "risk_meta": "risk_meta_field_config",
        }
        key = key_map.get(field_source, "event_basic_field_configs")
        data[key] = [
            {
                "field_name": field_name,
                "display_name": "字段名",
                "is_priority": True,
                "duplicate_field": False,
                "drill_config": [
                    {"tool": {"uid": "fake_tool_uid", "version": 1, "params": {}}, "config": [], "drill_name": ""},
                ],
            }
        ]

    def _build_rule_strategy_payload(self, name_suffix=""):
        strategy_name = f"test_rule_strategy{name_suffix and '_' + name_suffix}"
        return {
            "namespace": settings.DEFAULT_NAMESPACE,
            "strategy_name": strategy_name,
            "strategy_type": "rule",
            "configs": {
                "config_type": RuleAuditConfigType.EVENT_LOG.value,
                "data_source": {
                    "source_type": RuleAuditSourceType.REALTIME.value,
                    "rt_id": "bklog.demo_table",
                    "system_ids": ["bklog"],
                },
                "select": [
                    {
                        "table": "bklog.demo_table",
                        "raw_name": "raw_event_id",
                        "display_name": "raw_event_id",
                        "field_type": RuleAuditFieldType.STRING.value,
                        "aggregate": None,
                    }
                ],
            },
            "tags": ["BkAudit"],
            "risk_level": RiskLevel.HIGH.value,
            "risk_hazard": "",
            "risk_guidance": "",
            "risk_title": "risk title",
            "processor_groups": ["123"],
            # 满足规则策略对基础字段映射的校验要求
            "event_basic_field_configs": [
                {
                    "field_name": "raw_event_id",
                    "display_name": "raw_event_id",
                    "is_priority": True,
                    "duplicate_field": False,
                    "map_config": {"source_field": "raw_event_id"},
                },
                {
                    "field_name": "event_source",
                    "display_name": "event_source",
                    "is_priority": False,
                    "duplicate_field": False,
                    "map_config": {"source_field": "raw_event_id"},
                },
                {
                    "field_name": "operator",
                    "display_name": "operator",
                    "is_priority": False,
                    "duplicate_field": False,
                    "map_config": {"source_field": "raw_event_id"},
                },
            ],
            "risk_meta_field_config": [
                {
                    "field_name": "risk_title",
                    "display_name": "风险标题",
                    "is_priority": True,
                    "description": "",
                    "duplicate_field": False,
                }
            ],
        }

    def _mark_strategy_running(self, strategy_id: int):
        Strategy.objects.filter(strategy_id=strategy_id).update(status=StrategyStatusChoices.RUNNING.value)

    def _build_update_request_from_strategy(self, strategy: Strategy) -> dict:
        return {
            "namespace": strategy.namespace,
            "strategy_name": strategy.strategy_name,
            "control_id": strategy.control_id,
            "control_version": strategy.control_version,
            "strategy_type": strategy.strategy_type,
            "sql": strategy.sql,
            "configs": copy.deepcopy(strategy.configs),
            "tags": [],
            "notice_groups": copy.deepcopy(strategy.notice_groups or []),
            "description": strategy.description or "",
            "risk_level": strategy.risk_level,
            "risk_hazard": strategy.risk_hazard or "",
            "risk_guidance": strategy.risk_guidance or "",
            "risk_title": strategy.risk_title or "",
            "processor_groups": copy.deepcopy(strategy.processor_groups or []),
            "event_basic_field_configs": copy.deepcopy(strategy.event_basic_field_configs or []),
            "event_data_field_configs": copy.deepcopy(strategy.event_data_field_configs or []),
            "event_evidence_field_configs": copy.deepcopy(strategy.event_evidence_field_configs or []),
            "risk_meta_field_config": copy.deepcopy(strategy.risk_meta_field_config or []),
        }

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

    @mock.patch("services.web.strategy_v2.resources.call_controller", mock.Mock(return_value=None))
    def _create_rule_strategy(self, name_suffix="") -> dict:
        params = self._build_rule_strategy_payload(name_suffix)
        return CreateStrategy()(**params)

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
        rule_data = self._create_rule_strategy(name_suffix="33")
        Strategy.objects.create(
            namespace=self.namespace,
            strategy_name="hidden_system_strategy",
            source=StrategySource.SYSTEM,
            configs={},
        )

        result = resource.strategy_v2.list_strategy(namespace=self.namespace, order_field="-strategy_id")

        # 确保返回多个策略
        strategy_ids = [s["strategy_id"] for s in result]
        self.assertIn(data1["strategy_id"], strategy_ids)
        self.assertIn(data2["strategy_id"], strategy_ids)
        self.assertIn(rule_data["strategy_id"], strategy_ids)
        self.assertNotIn("hidden_system_strategy", [item["strategy_name"] for item in result])

        # 校验 tool 字段也在（工具数目等）；规则策略包含 risk_field_config 信息
        for strategy_data in result:
            if strategy_data["strategy_id"] in [data1["strategy_id"], data2["strategy_id"]]:
                self.assertIn("tools", strategy_data)
                self.assertEqual(len(strategy_data["tools"]), 1)
                tool = strategy_data["tools"][0]
                self.assertEqual(tool["tool_uid"], "fake_tool_uid")
            if strategy_data["strategy_id"] == rule_data["strategy_id"]:
                # risk_field_config 透传出来
                self.assertIn("risk_meta_field_config", strategy_data)
                self.assertTrue(isinstance(strategy_data["risk_meta_field_config"], list))
                # 我们在创建时放了 risk_title 一项
                self.assertGreaterEqual(len(strategy_data["risk_meta_field_config"]), 1)
                self.assertEqual(strategy_data["risk_meta_field_config"][0]["field_name"], "risk_title")

    def test_list_strategy_report_status(self):
        """测试策略列表返回 report_status 字段"""
        # 创建三种不同报告状态的策略
        auto_strategy = Strategy.objects.create(
            namespace=self.namespace,
            strategy_name="auto_report_strategy",
            configs={},
            report_enabled=True,
            report_auto_render=True,
        )
        manual_strategy = Strategy.objects.create(
            namespace=self.namespace,
            strategy_name="manual_report_strategy",
            configs={},
            report_enabled=True,
            report_auto_render=False,
        )
        disabled_strategy = Strategy.objects.create(
            namespace=self.namespace,
            strategy_name="disabled_report_strategy",
            configs={},
            report_enabled=False,
            report_auto_render=True,  # 即使 auto_render=True，但 enabled=False 仍为未开启
        )

        result = resource.strategy_v2.list_strategy(namespace=self.namespace)
        result_map = {s["strategy_id"]: s for s in result}

        # 验证 report_status 字段返回正确
        self.assertEqual(result_map[auto_strategy.strategy_id]["report_status"], StrategyReportStatus.AUTO.value)
        self.assertEqual(result_map[manual_strategy.strategy_id]["report_status"], StrategyReportStatus.MANUAL.value)
        self.assertEqual(
            result_map[disabled_strategy.strategy_id]["report_status"], StrategyReportStatus.DISABLED.value
        )

    def test_list_strategy_filter_by_report_status(self):
        """测试策略列表按 report_status 筛选"""
        # 创建三种不同报告状态的策略
        auto_strategy = Strategy.objects.create(
            namespace=self.namespace,
            strategy_name="filter_auto_strategy",
            configs={},
            report_enabled=True,
            report_auto_render=True,
        )
        manual_strategy = Strategy.objects.create(
            namespace=self.namespace,
            strategy_name="filter_manual_strategy",
            configs={},
            report_enabled=True,
            report_auto_render=False,
        )
        disabled_strategy = Strategy.objects.create(
            namespace=self.namespace,
            strategy_name="filter_disabled_strategy",
            configs={},
            report_enabled=False,
        )

        # 测试筛选自动生成
        result = resource.strategy_v2.list_strategy(
            namespace=self.namespace, report_status=StrategyReportStatus.AUTO.value
        )
        strategy_ids = [s["strategy_id"] for s in result]
        self.assertIn(auto_strategy.strategy_id, strategy_ids)
        self.assertNotIn(manual_strategy.strategy_id, strategy_ids)
        self.assertNotIn(disabled_strategy.strategy_id, strategy_ids)

        # 测试筛选手动生成
        result = resource.strategy_v2.list_strategy(
            namespace=self.namespace, report_status=StrategyReportStatus.MANUAL.value
        )
        strategy_ids = [s["strategy_id"] for s in result]
        self.assertNotIn(auto_strategy.strategy_id, strategy_ids)
        self.assertIn(manual_strategy.strategy_id, strategy_ids)
        self.assertNotIn(disabled_strategy.strategy_id, strategy_ids)

        # 测试筛选未开启
        result = resource.strategy_v2.list_strategy(
            namespace=self.namespace, report_status=StrategyReportStatus.DISABLED.value
        )
        strategy_ids = [s["strategy_id"] for s in result]
        self.assertNotIn(auto_strategy.strategy_id, strategy_ids)
        self.assertNotIn(manual_strategy.strategy_id, strategy_ids)
        self.assertIn(disabled_strategy.strategy_id, strategy_ids)

        # 测试多选筛选（自动生成 + 手动生成）
        result = resource.strategy_v2.list_strategy(
            namespace=self.namespace,
            report_status=f"{StrategyReportStatus.AUTO.value},{StrategyReportStatus.MANUAL.value}",
        )
        strategy_ids = [s["strategy_id"] for s in result]
        self.assertIn(auto_strategy.strategy_id, strategy_ids)
        self.assertIn(manual_strategy.strategy_id, strategy_ids)
        self.assertNotIn(disabled_strategy.strategy_id, strategy_ids)

    def test_create_rule_strategy(self) -> None:
        """Create Rule Strategy with risk_field_config"""
        data = self._create_rule_strategy(name_suffix="create")
        self.assertIn("strategy_id", data)
        # 校验 DB 中策略可取且 risk_field_config 被保存
        s = Strategy.objects.get(strategy_id=data["strategy_id"])
        self.assertTrue(isinstance(s.risk_meta_field_config, list))
        self.assertGreaterEqual(len(s.risk_meta_field_config), 1)
        self.assertEqual(s.risk_meta_field_config[0]["field_name"], "risk_title")

    @mock.patch("services.web.strategy_v2.resources.call_controller")
    def test_create_rule_strategy_with_manual_sql(self, mock_call_controller):
        mock_call_controller.return_value = None
        params = self._build_rule_strategy_payload(name_suffix="manual")
        params["sql"] = "SELECT 1"
        with mock.patch("services.web.strategy_v2.resources.RuleAuditSQLBuilder.build_sql") as mock_build_sql:
            data = CreateStrategy()(**params)
        strategy = Strategy.objects.get(strategy_id=data["strategy_id"])
        self.assertEqual(strategy.sql, "SELECT 1")
        mock_build_sql.assert_not_called()
        mock_call_controller.assert_called_once()

    def test_update_rule_strategy_manual_sql_skips_auto_builder(self):
        created = self._create_rule_strategy()
        self._mark_strategy_running(created["strategy_id"])
        strategy = Strategy.objects.get(strategy_id=created["strategy_id"])
        update_data = self._build_update_request_from_strategy(strategy)
        update_data["sql"] = "SELECT custom_sql"
        update_data["configs"]["select"].append(
            {
                "table": "bklog.demo_table",
                "raw_name": "event_source",
                "display_name": "event_source",
                "field_type": RuleAuditFieldType.STRING.value,
                "aggregate": None,
            }
        )
        update_resource = UpdateStrategy()
        with mock.patch.object(UpdateStrategy, "build_rule_audit_sql") as mock_build_sql:
            need_remote = update_resource.update_db(
                strategy=strategy, validated_request_data=copy.deepcopy(update_data)
            )
        self.assertTrue(need_remote)
        mock_build_sql.assert_not_called()
        strategy.refresh_from_db()
        self.assertEqual(strategy.sql, "SELECT custom_sql")

    def test_update_rule_strategy_manual_sql_updates_remote_only_on_change(self):
        created = self._create_rule_strategy()
        strategy_id = created["strategy_id"]
        self._mark_strategy_running(strategy_id)
        strategy = Strategy.objects.get(strategy_id=strategy_id)
        params = self._build_update_request_from_strategy(strategy)
        update_resource = UpdateStrategy()
        with mock.patch.object(UpdateStrategy, "build_rule_audit_sql") as mock_build_sql:
            need_remote = update_resource.update_db(strategy=strategy, validated_request_data=copy.deepcopy(params))
        self.assertFalse(need_remote)
        mock_build_sql.assert_not_called()

        params["sql"] = "SELECT changed_sql"
        with mock.patch.object(UpdateStrategy, "build_rule_audit_sql") as mock_build_sql:
            need_remote = update_resource.update_db(strategy=strategy, validated_request_data=copy.deepcopy(params))
        self.assertTrue(need_remote)
        mock_build_sql.assert_not_called()
        strategy.refresh_from_db()
        self.assertEqual(strategy.sql, "SELECT changed_sql")


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
                        "duplicate_field": False,
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
        # omit collection_id, it will be auto-generated as strategy_id_basic_username
        enum_mappings = {
            "mappings": [{"key": "1", "name": "one"}],
        }
        data = self._create_bkm_strategy_with_enum(enum_mappings)
        strategy_id = data["strategy_id"]
        expected_collection = f"{strategy_id}_basic_username"
        result = resource.meta.get_enum_mapping_by_collection(
            collection_id=expected_collection,
            related_type="strategy",
            related_object_id=strategy_id,
        )
        expected = [
            {
                "collection_id": expected_collection,
                "key": enum_mappings["mappings"][0]["key"],
                "name": enum_mappings["mappings"][0]["name"],
            }
        ]
        self.assertEqual(result, expected)
        relation = resource.meta.get_enum_mappings_relation(related_type="strategy", related_object_id=strategy_id)
        self.assertEqual(relation, [expected_collection])

    @mock.patch(
        "services.web.analyze.controls.bkm.api.bk_monitor.save_alarm_strategy",
        mock.Mock(return_value={}),
    )
    def test_update_strategy_enum_mappings_delete(self) -> None:
        # omit collection_id, it will be auto-generated on create
        enum_mappings = {"mappings": [{"key": "1", "name": "one"}]}
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
                        "duplicate_field": False,
                        "enum_mappings": {"mappings": []},
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
                        "duplicate_field": False,
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
        # omit collection_id, it will be auto-generated as strategy_id_basic_username
        enum_mappings = {"mappings": [{"key": "1", "name": "one"}]}
        data = self._create_bkm_strategy_with_enum(enum_mappings)
        strategy_id = data["strategy_id"]
        expected_collection = f"{strategy_id}_basic_username"
        params = {
            "collection_id": expected_collection,
            "related_type": "strategy",
            "related_object_id": strategy_id,
        }
        result = resource.strategy_v2.get_strategy_enum_mapping_by_collection(**params)
        expected = [
            {
                "collection_id": expected_collection,
                "key": enum_mappings["mappings"][0]["key"],
                "name": enum_mappings["mappings"][0]["name"],
            }
        ]
        self.assertEqual(result, expected)

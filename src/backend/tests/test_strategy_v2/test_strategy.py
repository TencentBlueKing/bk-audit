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
from bk_resource.exceptions import ValidateException
from django.conf import settings
from django.http import Http404
from rest_framework import serializers

from api.bk_base.default import GetResultTable
from api.bk_log.constants import INDEX_SET_ID
from apps.meta.constants import ConfigLevelChoices
from apps.meta.models import GlobalMetaConfig
from apps.notice.models import NoticeGroup
from core.utils.data import ordered_dict_to_json
from services.web.analyze.models import Control, ControlVersion
from services.web.scene.constants import ResourceVisibilityType
from services.web.scene.filters import BindingMetadataHelper
from services.web.scene.models import ResourceBinding, Scene
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
from services.web.strategy_v2.resources import (
    CreateStrategy,
    DeleteStrategy,
    RetryStrategy,
    ToggleStrategy,
    UpdateStrategy,
)
from services.web.tool.constants import ToolTypeEnum
from services.web.tool.models import Tool
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


def create_bound_notice_group(scene_id: int, group_name: str) -> NoticeGroup:
    notice_group = NoticeGroup.objects.create(group_name=group_name, group_member=[], notice_config=[])
    BindingMetadataHelper.create_resource_binding(
        resource_id=str(notice_group.group_id),
        resource_type=ResourceVisibilityType.NOTICE_GROUP,
        scene_id=scene_id,
    )
    return notice_group


def create_bound_tool(scene_id: int) -> Tool:
    tool = Tool.objects.create(
        namespace=settings.DEFAULT_NAMESPACE,
        uid="fake_tool_uid",
        version=1,
        name="fake_tool",
        tool_type=ToolTypeEnum.API.value,
        permission_owner="admin",
    )
    BindingMetadataHelper.create_resource_binding(
        resource_id=tool.uid,
        resource_type=ResourceVisibilityType.TOOL,
        scene_id=scene_id,
    )
    return tool


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
        self.scene = Scene.objects.create(name="test_scene", description="test")
        self.scene_id = self.scene.scene_id
        self.notice_group = create_bound_notice_group(self.scene_id, "test_notice_group")
        self.tool = create_bound_tool(self.scene_id)

    def _bind_strategy_to_scene(self, strategy_id: int):
        BindingMetadataHelper.create_resource_binding(
            resource_id=str(strategy_id),
            resource_type=ResourceVisibilityType.STRATEGY,
            scene_id=self.scene_id,
        )

    def _list_strategy(self, **kwargs):
        return resource.strategy_v2.list_strategy(namespace=self.namespace, scene_id=self.scene_id, **kwargs)

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
        base_name = "test_rule"
        suffix = f"{name_suffix and '_' + name_suffix}"
        # 确保策略名称不超过64字符限制
        max_length = 64
        if len(base_name + suffix) > max_length:
            suffix = suffix[: max_length - len(base_name)]
        strategy_name = base_name + suffix
        return {
            "namespace": settings.DEFAULT_NAMESPACE,
            "strategy_name": strategy_name,
            "strategy_type": "rule",
            "scene_id": self.scene_id,
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
            "processor_groups": [self.notice_group.group_id],
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
        params["scene_id"] = self.scene_id
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
                "processor_groups": [self.notice_group.group_id],
            }
        )
        return resource.strategy_v2.create_strategy(**params)

    @mock.patch("services.web.strategy_v2.resources.call_controller", mock.Mock(return_value=None))
    @mock.patch("apps.meta.resources.SystemListAllResource")
    def _create_rule_strategy(self, mock_system_list, name_suffix="") -> dict:
        # 设置mock返回值，模拟授权的系统列表
        mock_system_list.return_value.request.return_value = [{"system_id": "bklog"}, {"system_id": "bkmonitor"}]
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
                "processor_groups": [self.notice_group.group_id],
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

        result = self._list_strategy(order_field="-strategy_id")

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
        self._bind_strategy_to_scene(auto_strategy.strategy_id)
        manual_strategy = Strategy.objects.create(
            namespace=self.namespace,
            strategy_name="manual_report_strategy",
            configs={},
            report_enabled=True,
            report_auto_render=False,
        )
        self._bind_strategy_to_scene(manual_strategy.strategy_id)
        disabled_strategy = Strategy.objects.create(
            namespace=self.namespace,
            strategy_name="disabled_report_strategy",
            configs={},
            report_enabled=False,
            report_auto_render=True,  # 即使 auto_render=True，但 enabled=False 仍为未开启
        )
        self._bind_strategy_to_scene(disabled_strategy.strategy_id)

        result = self._list_strategy()
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
        self._bind_strategy_to_scene(auto_strategy.strategy_id)
        manual_strategy = Strategy.objects.create(
            namespace=self.namespace,
            strategy_name="filter_manual_strategy",
            configs={},
            report_enabled=True,
            report_auto_render=False,
        )
        self._bind_strategy_to_scene(manual_strategy.strategy_id)
        disabled_strategy = Strategy.objects.create(
            namespace=self.namespace,
            strategy_name="filter_disabled_strategy",
            configs={},
            report_enabled=False,
        )
        self._bind_strategy_to_scene(disabled_strategy.strategy_id)

        # 测试筛选自动生成
        result = self._list_strategy(report_status=StrategyReportStatus.AUTO.value)
        strategy_ids = [s["strategy_id"] for s in result]
        self.assertIn(auto_strategy.strategy_id, strategy_ids)
        self.assertNotIn(manual_strategy.strategy_id, strategy_ids)
        self.assertNotIn(disabled_strategy.strategy_id, strategy_ids)

        # 测试筛选手动生成
        result = self._list_strategy(report_status=StrategyReportStatus.MANUAL.value)
        strategy_ids = [s["strategy_id"] for s in result]
        self.assertNotIn(auto_strategy.strategy_id, strategy_ids)
        self.assertIn(manual_strategy.strategy_id, strategy_ids)
        self.assertNotIn(disabled_strategy.strategy_id, strategy_ids)

        # 测试筛选未开启
        result = self._list_strategy(report_status=StrategyReportStatus.DISABLED.value)
        strategy_ids = [s["strategy_id"] for s in result]
        self.assertNotIn(auto_strategy.strategy_id, strategy_ids)
        self.assertNotIn(manual_strategy.strategy_id, strategy_ids)
        self.assertIn(disabled_strategy.strategy_id, strategy_ids)

        # 测试多选筛选（自动生成 + 手动生成）
        result = self._list_strategy(
            report_status=f"{StrategyReportStatus.AUTO.value},{StrategyReportStatus.MANUAL.value}"
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

    @mock.patch("services.web.strategy_v2.resources.call_controller", mock.Mock(return_value=None))
    def test_delete_strategy_cleans_scene_binding(self):
        data = self._create_rule_strategy(name_suffix="delete_binding")
        strategy_id = data["strategy_id"]
        self.assertTrue(
            ResourceBinding.objects.filter(
                resource_type=ResourceVisibilityType.STRATEGY,
                resource_id=str(strategy_id),
            ).exists()
        )

        resource.strategy_v2.delete_strategy(strategy_id=strategy_id)

        self.assertFalse(
            ResourceBinding.objects.filter(
                resource_type=ResourceVisibilityType.STRATEGY,
                resource_id=str(strategy_id),
            ).exists()
        )

    @mock.patch("services.web.strategy_v2.resources.call_controller")
    def test_delete_strategy_rejects_soft_deleted_scene_binding(self, mock_call_controller):
        data = self._create_rule_strategy(name_suffix="delete_soft_deleted_scene")
        strategy_id = data["strategy_id"]
        self.scene.delete()

        with self.assertRaises(Http404):
            DeleteStrategy().perform_request({"strategy_id": strategy_id})

        mock_call_controller.assert_not_called()
        self.assertTrue(Strategy.objects.filter(strategy_id=strategy_id).exists())
        self.assertTrue(
            ResourceBinding.objects.filter(
                resource_type=ResourceVisibilityType.STRATEGY,
                resource_id=str(strategy_id),
            ).exists()
        )

    @mock.patch("services.web.strategy_v2.resources.call_controller")
    def test_toggle_strategy_rejects_soft_deleted_scene_binding(self, mock_call_controller):
        data = self._create_rule_strategy(name_suffix="toggle_soft_deleted_scene")
        strategy_id = data["strategy_id"]
        self.scene.delete()

        with self.assertRaises(Http404):
            ToggleStrategy().perform_request({"strategy_id": strategy_id, "toggle": True})

        mock_call_controller.assert_not_called()

    @mock.patch("services.web.strategy_v2.resources.call_controller")
    def test_retry_strategy_rejects_soft_deleted_scene_binding(self, mock_call_controller):
        data = self._create_rule_strategy(name_suffix="retry_soft_deleted_scene")
        strategy_id = data["strategy_id"]
        self.scene.delete()

        with self.assertRaises(Http404):
            RetryStrategy().perform_request({"strategy_id": strategy_id})

        mock_call_controller.assert_not_called()

    def test_update_strategy_rejects_soft_deleted_scene_binding(self):
        data = self._create_rule_strategy(name_suffix="update_soft_deleted_scene")
        strategy = Strategy.objects.get(strategy_id=data["strategy_id"])
        params = self._build_update_request_from_strategy(strategy)
        params["strategy_id"] = strategy.strategy_id
        params["strategy_name"] = "不应更新"
        self.scene.delete()

        with self.assertRaises(Http404):
            UpdateStrategy().perform_request(params)

        strategy.refresh_from_db()
        self.assertNotEqual(strategy.strategy_name, "不应更新")

    @mock.patch("services.web.strategy_v2.resources.call_controller")
    @mock.patch("apps.meta.resources.SystemListAllResource")
    def test_create_rule_strategy_with_manual_sql(self, mock_system_list, mock_call_controller):
        # 设置mock返回值，模拟授权的系统列表
        mock_system_list.return_value.request.return_value = [{"system_id": "bklog"}, {"system_id": "bkmonitor"}]
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
        created = self._create_rule_strategy(name_suffix="skip_auto_builder")
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
        created = self._create_rule_strategy(name_suffix="remote_only_change")
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
        params["scene_id"] = self.scene_id
        params.update(
            {
                "control_id": self.c_version.control_id,
                "control_version": self.c_version.control_version,
                "risk_level": RiskLevel.HIGH.value,
                "risk_hazard": "",
                "risk_guidance": "",
                "risk_title": "risk title",
                "processor_groups": [self.notice_group.group_id],
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
                "processor_groups": [self.notice_group.group_id],
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
        self.scene = Scene.objects.create(name="test_scene_enum", description="test")
        self.scene_id = self.scene.scene_id
        self.notice_group = create_bound_notice_group(self.scene_id, "test_notice_group_enum")
        self.tool = create_bound_tool(self.scene_id)

    def _create_bkm_strategy_with_enum(self, enum_mappings: dict) -> dict:
        params = copy.deepcopy(BKM_STRATEGY_DATA)
        params["scene_id"] = self.scene_id
        params.update(
            {
                "control_id": self.c_version.control_id,
                "control_version": self.c_version.control_version,
                "risk_level": RiskLevel.HIGH.value,
                "risk_hazard": "",
                "risk_guidance": "",
                "risk_title": "risk title",
                "processor_groups": [self.notice_group.group_id],
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


class TestMineBizRtPermissionTest(StrategyTest):
    """
    测试 MINE_BIZ_RT 类型的权限验证逻辑
    """

    @mock.patch("services.web.strategy_v2.serializers.SceneDataFilter.get_table_ids")
    @mock.patch("services.web.strategy_v2.serializers.CreateStrategyRequestSerializer._ensure_project_permission")
    @mock.patch("services.web.strategy_v2.serializers.CreateStrategyRequestSerializer._check_user_table_permission")
    def test_ensure_project_permission_not_called_when_user_has_no_permission(
        self, mock_check_user_permission, mock_ensure_project_permission, mock_get_table_ids
    ):
        """
        测试：当用户对结果表没有权限时，_ensure_project_permission 不应被调用

        根据用户提供的代码逻辑：
        1. 如果 rt_id 在场景授权范围内，不需要校验用户权限，直接调用 _ensure_project_permission
        2. 如果 rt_id 不在场景授权范围内，需要校验用户权限
           - 如果用户有权限，调用 _ensure_project_permission
           - 如果用户无权限，抛出 ValidationError，_ensure_project_permission 不应被调用
        """
        # 模拟场景授权范围为空（rt_id 不在范围内）
        mock_get_table_ids.return_value = []
        # 模拟用户权限校验失败（抛出 ValidationError）
        mock_check_user_permission.side_effect = serializers.ValidationError(
            {"rt_id": "当前用户没有权限使用数据表[test_mine_biz_rt]"}
        )

        # 构建 MINE_BIZ_RT 类型的请求数据
        params = self._build_rule_strategy_payload(name_suffix="mine_biz_rt_permission_test")
        params["configs"]["config_type"] = RuleAuditConfigType.MINE_BIZ_RT.value
        params["configs"]["data_source"] = {
            "source_type": RuleAuditSourceType.REALTIME.value,
            "rt_id": "test_mine_biz_rt",
        }
        params["scene_id"] = self.scene_id

        # 验证创建策略时抛出 ValidateException
        with self.assertRaises(ValidateException):
            CreateStrategy()(**params)

        # 验证 _ensure_project_permission 没有被调用（因为用户无权限，在调用前就抛出了异常）
        mock_ensure_project_permission.assert_not_called()

    @mock.patch("services.web.strategy_v2.serializers.SceneDataFilter.get_table_ids")
    @mock.patch("services.web.strategy_v2.serializers.CreateStrategyRequestSerializer._ensure_project_permission")
    @mock.patch("services.web.strategy_v2.serializers.CreateStrategyRequestSerializer._check_user_table_permission")
    def test_ensure_project_permission_called_when_user_has_permission(
        self, mock_check_user_permission, mock_ensure_project_permission, mock_get_table_ids
    ):
        """
        测试：当用户对结果表有权限时，_ensure_project_permission 应该被调用
        """
        # 模拟场景授权范围为空（rt_id 不在范围内）
        mock_get_table_ids.return_value = []
        # 模拟用户权限校验通过
        mock_check_user_permission.return_value = None
        # 模拟项目权限授权通过
        mock_ensure_project_permission.return_value = None

        # 构建 MINE_BIZ_RT 类型的请求数据
        params = self._build_rule_strategy_payload(name_suffix="mine_biz_rt_permission_test_2")
        params["configs"]["config_type"] = RuleAuditConfigType.MINE_BIZ_RT.value
        params["configs"]["data_source"] = {
            "source_type": RuleAuditSourceType.REALTIME.value,
            "rt_id": "test_mine_biz_rt",
        }
        params["scene_id"] = self.scene_id

        # 由于还有其他校验可能会失败，我们只需验证 _check_user_table_permission 被调用后，
        # _ensure_project_permission 也会被调用
        try:
            CreateStrategy()(**params)
        except Exception:
            pass

        # 验证用户权限校验被调用
        mock_check_user_permission.assert_called()
        # 验证项目权限授权被调用
        mock_ensure_project_permission.assert_called()

    @mock.patch("services.web.strategy_v2.serializers.SceneDataFilter.get_table_ids")
    @mock.patch("services.web.strategy_v2.serializers.CreateStrategyRequestSerializer._ensure_project_permission")
    @mock.patch("services.web.strategy_v2.serializers.CreateStrategyRequestSerializer._check_user_table_permission")
    def test_no_permission_check_when_rt_in_scene_scope(
        self, mock_check_user_permission, mock_ensure_project_permission, mock_get_table_ids
    ):
        """
        测试：当 rt_id 在场景授权范围内时，不需要校验用户权限
        """
        # 模拟场景授权范围包含该 rt_id
        mock_get_table_ids.return_value = ["test_mine_biz_rt"]
        # 模拟项目权限授权通过
        mock_ensure_project_permission.return_value = None

        # 构建 MINE_BIZ_RT 类型的请求数据
        params = self._build_rule_strategy_payload(name_suffix="mine_biz_rt_in_scope_test")
        params["configs"]["config_type"] = RuleAuditConfigType.MINE_BIZ_RT.value
        params["configs"]["data_source"] = {
            "source_type": RuleAuditSourceType.REALTIME.value,
            "rt_id": "test_mine_biz_rt",
        }
        params["scene_id"] = self.scene_id

        # 由于还有其他校验可能会失败，我们只需验证权限校验的调用情况
        try:
            CreateStrategy()(**params)
        except Exception:
            pass

        # 验证用户权限校验没有被调用（因为在场景授权范围内）
        mock_check_user_permission.assert_not_called()
        # 验证项目权限授权被调用
        mock_ensure_project_permission.assert_called()

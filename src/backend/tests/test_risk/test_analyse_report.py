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

import datetime
import io
import json
import sys
import types
from pathlib import Path
from unittest import mock

from django.contrib import admin
from django.db.models import Q
from django.http import Http404
from django.test import override_settings
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from apps.permission.handlers.actions import ActionEnum
from services.web.risk.constants import (
    AnalyseReportStatus,
    AnalyseReportType,
    EventFilterOperator,
    RiskLabel,
    RiskStatus,
)
from services.web.risk.models import (
    AnalyseReport,
    AnalyseReportExtraInfo,
    AnalyseReportRisk,
    AnalyseReportScenario,
    Risk,
    RiskReport,
    TicketPermission,
    UserType,
)
from services.web.risk.serializers import (
    GenerateAnalyseReportRequestSerializer,
    ListAnalyseReportRequestSerializer,
    ListAnalyseReportRiskPageResponseSerializer,
    ListAnalyseReportRiskRequestSerializer,
    ListAnalyseReportRiskResponseSerializer,
    ListAnalyseReportScenarioResponseSerializer,
    RetrieveAnalyseReportResponseSerializer,
    UpdateAnalyseReportRequestSerializer,
)
from services.web.risk.views import AnalyseReportAPIGWViewSet
from services.web.strategy_v2.constants import RiskLevel
from services.web.strategy_v2.models import Strategy
from tests.base import TestCase


class AnalyseReportTestBase(TestCase):
    """Agent Report 测试基类，提供通用的 setUp"""

    def setUp(self):
        super().setUp()
        self.core_username_patcher = mock.patch("core.models.get_request_username", return_value="admin")
        self.core_username_patcher.start()
        self.addCleanup(self.core_username_patcher.stop)
        self.resource_username_patcher = mock.patch(
            "services.web.risk.resources.analyse_report.get_request_username",
            return_value="admin",
        )
        self.resource_username_patcher.start()
        self.addCleanup(self.resource_username_patcher.stop)

        # 创建策略
        self.strategy = Strategy.objects.create(
            namespace="default",
            strategy_name="test-strategy",
            risk_level=RiskLevel.HIGH.value,
        )
        # 创建风险
        self.risk1 = Risk.objects.create(
            risk_id="risk-agent-001",
            raw_event_id="raw-agent-001",
            strategy=self.strategy,
            status="new",
            title="Test Risk 1",
            event_time=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
        )
        self.risk2 = Risk.objects.create(
            risk_id="risk-agent-002",
            raw_event_id="raw-agent-002",
            strategy=self.strategy,
            status="new",
            title="Test Risk 2",
            event_time=datetime.datetime(2026, 1, 2, tzinfo=datetime.timezone.utc),
        )
        # 创建内置场景
        self.scenario_person, _ = AnalyseReportScenario.objects.update_or_create(
            scenario_key="person_investigation",
            defaults=dict(
                name="责任人行为调查分析报告",
                description="行为链分析、风险关联分析、意图判断",
                report_type=AnalyseReportType.SYSTEM,
                is_builtin=True,
                system_prompt="你是一个专业的审计安全分析师。请分析责任人行为。使用 with_detail 选项获取完整风险数据。",
                priority=100,
                is_enabled=True,
            ),
        )
        self.scenario_comprehensive, _ = AnalyseReportScenario.objects.update_or_create(
            scenario_key="comprehensive",
            defaults=dict(
                name="风险综合分析报告",
                description="根因归纳、风险聚类、异常识别",
                report_type=AnalyseReportType.SYSTEM,
                is_builtin=True,
                system_prompt="你是一个专业的审计安全分析师。请进行综合分析。使用 with_detail 选项获取完整风险数据。",
                priority=90,
                is_enabled=True,
            ),
        )
        self.scenario_disabled, _ = AnalyseReportScenario.objects.update_or_create(
            scenario_key="disabled_scenario",
            defaults=dict(
                name="已禁用的场景",
                description="不应在列表中出现",
                report_type=AnalyseReportType.SYSTEM,
                is_builtin=False,
                system_prompt="不应被使用",
                priority=10,
                is_enabled=False,
            ),
        )


class TestListAnalyseReportScenario(AnalyseReportTestBase):
    """测试获取AI报告场景列表"""

    def test_list_scenarios_returns_enabled_only(self):
        """测试只返回启用的场景"""
        result = self.resource.risk.list_analyse_report_scenario()
        scenario_keys = [s["scenario_key"] for s in result]
        self.assertIn("person_investigation", scenario_keys)
        self.assertIn("comprehensive", scenario_keys)
        self.assertNotIn("disabled_scenario", scenario_keys)

    def test_list_scenarios_ordered_by_priority(self):
        """测试场景按优先级排序"""
        result = self.resource.risk.list_analyse_report_scenario()
        priorities = [s["priority"] for s in result]
        # 应该从高到低排序（内置优先，然后按priority降序）
        self.assertEqual(priorities, sorted(priorities, reverse=True))

    def test_list_scenarios_serializer(self):
        """测试场景列表序列化器字段完整"""
        result = self.resource.risk.list_analyse_report_scenario()
        first = result[0]
        expected_fields = {
            "scenario_id",
            "scenario_key",
            "name",
            "description",
            "report_type",
            "is_builtin",
            "priority",
        }
        self.assertTrue(expected_fields.issubset(set(first.keys())))


class TestGenerateAnalyseReport(AnalyseReportTestBase):
    """测试生成AI分析报告"""

    @mock.patch("services.web.risk.resources.analyse_report.generate_analyse_report")
    def test_generate_report_with_scenario(self, mock_task):
        """测试使用内置场景生成报告"""
        mock_async_result = mock.MagicMock()
        mock_async_result.id = "celery-task-id-001"
        mock_task.delay.return_value = mock_async_result

        result = self.resource.risk.generate_analyse_report(
            {
                "scenario_key": "person_investigation",
                "report_type": AnalyseReportType.SYSTEM,
                "title": "张三行为调查分析报告",
                "analysis_scope": "责任人=张三，时间范围=近30天",
                "target_risks_filter": {
                    "start_time": "2025-09-16 20:04:51",
                    "end_time": "2026-03-16 20:04:51",
                    "operator": "zhangsan",
                    "use_bkbase": True,
                    "datetime_origin": "now-6M,now",
                },
            }
        )

        self.assertIn("report_id", result)
        self.assertEqual(result["task_id"], "celery-task-id-001")
        self.assertEqual(result["status"], "PENDING")

        # 验证数据库记录
        report = AnalyseReport.objects.get(report_id=result["report_id"])
        self.assertEqual(report.title, "张三行为调查分析报告")
        self.assertEqual(report.report_type, AnalyseReportType.SYSTEM)
        self.assertEqual(report.scenario, self.scenario_person)
        self.assertEqual(report.status, AnalyseReportStatus.GENERATING)

        # 验证过滤参数已存入 prompt_params
        self.assertEqual(report.prompt_params["operator"], "zhangsan")
        self.assertEqual(report.prompt_params["start_time"], "2025-09-16 20:04:51")
        self.assertTrue(report.prompt_params["use_bkbase"])

    @mock.patch("services.web.risk.resources.analyse_report.generate_analyse_report")
    def test_generate_report_custom_analysis(self, mock_task):
        """测试自定义分析生成报告"""
        mock_async_result = mock.MagicMock()
        mock_async_result.id = "celery-task-id-custom"
        mock_task.delay.return_value = mock_async_result

        result = self.resource.risk.generate_analyse_report(
            {
                "scenario_key": "",
                "report_type": AnalyseReportType.CUSTOM,
                "title": "自定义分析报告",
                "analysis_scope": "",
                "target_risks_filter": {
                    "start_time": "2025-09-16 20:04:51",
                    "end_time": "2026-03-16 20:04:51",
                    "operator": "admin",
                    "use_bkbase": True,
                    "datetime_origin": "now-6M,now",
                },
                "custom_prompt": "分析张三在英雄联盟业务的资产转移行为",
            }
        )

        report = AnalyseReport.objects.get(report_id=result["report_id"])
        self.assertEqual(report.report_type, AnalyseReportType.CUSTOM)
        self.assertIsNone(report.scenario)
        self.assertEqual(report.custom_prompt, "分析张三在英雄联盟业务的资产转移行为")

    def test_generate_report_serializer_validation(self):
        """测试请求序列化器校验"""
        # 缺少必填字段
        serializer = GenerateAnalyseReportRequestSerializer(data={})
        self.assertFalse(serializer.is_valid())
        self.assertIn("report_type", serializer.errors)
        self.assertIn("title", serializer.errors)

    def test_generate_report_serializer_invalid_report_type(self):
        """测试无效的报告类型"""
        serializer = GenerateAnalyseReportRequestSerializer(
            data={
                "report_type": "invalid_type",
                "title": "Test",
            }
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("report_type", serializer.errors)

    def test_generate_report_target_filter_uses_list_risk_validation(self):
        """target_risks_filter 使用 ListRisk 请求参数校验"""
        serializer = GenerateAnalyseReportRequestSerializer(
            data={
                "report_type": AnalyseReportType.SYSTEM,
                "title": "非法筛选报告",
                "target_risks_filter": {
                    "sort": ["event_data.foo"],
                },
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("target_risks_filter", serializer.errors)


class TestListAnalyseReport(AnalyseReportTestBase):
    """测试历史分析报告列表（默认按当前用户过滤）"""

    def setUp(self):
        super().setUp()
        # mock 当前用户
        self.username_patcher = mock.patch(
            "services.web.risk.resources.analyse_report.get_request_username",
            return_value="admin",
        )
        self.username_patcher.start()
        self.addCleanup(self.username_patcher.stop)

        # 创建当前用户的测试报告
        self.report1 = AnalyseReport.objects.create(
            title="张三行为调查分析报告",
            report_type=AnalyseReportType.SYSTEM,
            content=(
                "# 一、行为链分析\n\n"
                "通过对张三相关的5条风险单进行时序分析，发现以下行为模式：\n\n"
                "| 时间 | 操作 | 目标资源 | 风险等级 |\n"
                "|---|---|---|---|\n"
                "| 2026-01-15 09:30 | 数据导出 | 用户表 | 高 |\n"
                "| 2026-01-15 10:15 | 权限变更 | 管理后台 | 中 |\n\n"
                "## 二、风险关联分析\n\n"
                "张三在近30天内的操作行为呈现明显的异常模式，主要集中在敏感数据访问和权限提升两个维度。\n\n"
                "## 三、意图判断\n\n"
                "综合以上分析，张三的行为可能存在数据泄露风险，建议进一步调查。\n"
            ),
            analysis_scope="责任人=张三，时间范围=近30天",
            risk_count=5,
            status=AnalyseReportStatus.SUCCESS,
            prompt_params={},
            created_by="admin",
        )
        self.report2 = AnalyseReport.objects.create(
            title="风险综合分析报告",
            report_type=AnalyseReportType.CUSTOM,
            content=(
                "# 一、风险总览\n\n"
                "本报告对数据泄露类高/中风险进行综合分析，共涉及10条风险单。\n\n"
                "## 二、根因归纳\n\n"
                "经过聚类分析，10条风险可归纳为以下3类根因：\n\n"
                "1. **权限配置不当**（4条）：部分用户被授予了超出职责范围的数据访问权限\n"
                "2. **敏感数据外传**（3条）：通过API接口或文件导出方式将敏感数据传输至外部\n"
                "3. **异常登录行为**（3条）：非工作时间段或异常地理位置的登录操作\n\n"
                "## 三、处置建议\n\n"
                "- 立即收回超权限账号的敏感数据访问权限\n"
                "- 对外传数据进行内容审查，评估泄露影响范围\n"
                "- 加强登录行为监控，启用多因素认证\n"
            ),
            analysis_scope="风险类型=数据泄露，风险等级=高/中",
            risk_count=10,
            status=AnalyseReportStatus.SUCCESS,
            prompt_params={},
            created_by="admin",
        )
        self.report_generating = AnalyseReport.objects.create(
            title="生成中的报告",
            report_type=AnalyseReportType.SYSTEM,
            status=AnalyseReportStatus.GENERATING,
            prompt_params={},
            created_by="admin",
        )
        self.report_failed = AnalyseReport.objects.create(
            title="失败报告",
            report_type=AnalyseReportType.SYSTEM,
            status=AnalyseReportStatus.FAILED,
            prompt_params={},
            extra_info={"error_message": "生成失败"},
            created_by="admin",
        )
        # 创建其他用户的报告（不应出现在列表中）
        self.report_other_user = AnalyseReport.objects.create(
            title="其他用户的报告",
            report_type=AnalyseReportType.SYSTEM,
            content=("# 一、概述\n\n" "本报告由其他用户发起，对近期安全事件进行初步分析。\n\n" "## 二、发现\n\n" "共检测到3条中等风险，涉及文件权限变更和异常API调用。\n"),
            risk_count=3,
            status=AnalyseReportStatus.SUCCESS,
            prompt_params={},
            created_by="other_user",
        )

    def test_list_reports_filter_success_status(self):
        """测试按 success 状态过滤报告"""
        result = self.resource.risk.list_analyse_report({"status": AnalyseReportStatus.SUCCESS})
        titles = [r["title"] for r in result]
        self.assertIn("张三行为调查分析报告", titles)
        self.assertIn("风险综合分析报告", titles)
        self.assertNotIn("生成中的报告", titles)

    def test_list_reports_keyword_search(self):
        """测试关键词搜索"""
        result = self.resource.risk.list_analyse_report({"keyword": "张三"})
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "张三行为调查分析报告")

    def test_list_reports_type_filter(self):
        """测试报告类型筛选"""
        result = self.resource.risk.list_analyse_report(
            {
                "report_type": AnalyseReportType.CUSTOM,
            }
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["report_type"], AnalyseReportType.CUSTOM)

    def test_list_reports_sort_by_risk_count(self):
        """测试按关联风险数量排序"""
        result = self.resource.risk.list_analyse_report(
            {
                "sort": ["-risk_count"],
            }
        )
        risk_counts = [r["risk_count"] for r in result]
        self.assertEqual(risk_counts, sorted(risk_counts, reverse=True))

    def test_list_reports_keyword_search_by_scope(self):
        """测试通过分析范围搜索"""
        result = self.resource.risk.list_analyse_report({"keyword": "数据泄露"})
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "风险综合分析报告")

    def test_list_reports_only_current_user(self):
        """测试列表只返回当前用户的报告，不包含其他用户的报告"""
        result = self.resource.risk.list_analyse_report({})
        titles = [r["title"] for r in result]
        self.assertNotIn("其他用户的报告", titles)

    def test_list_reports_returns_all_status_by_default(self):
        """默认返回当前用户所有状态的报告，由前端按需筛选"""
        result = self.resource.risk.list_analyse_report({})
        statuses = {r["status"] for r in result}
        self.assertIn(AnalyseReportStatus.SUCCESS, statuses)
        self.assertIn(AnalyseReportStatus.FAILED, statuses)
        self.assertIn(AnalyseReportStatus.GENERATING, statuses)

    def test_list_reports_filter_by_status(self):
        """支持按报告状态过滤"""
        result = self.resource.risk.list_analyse_report({"status": AnalyseReportStatus.FAILED})

        self.assertEqual([item["report_id"] for item in result], [self.report_failed.report_id])
        self.assertEqual(result[0]["extra_info"]["error_message"], "生成失败")
        self.assertEqual(result[0]["error_message"], "生成失败")

    def test_list_reports_filter_generating_status(self):
        """显式传入状态时可查询生成中的报告"""
        result = self.resource.risk.list_analyse_report({"status": AnalyseReportStatus.GENERATING})

        self.assertEqual([item["report_id"] for item in result], [self.report_generating.report_id])


class TestRetrieveAnalyseReport(AnalyseReportTestBase):
    """测试AI报告详情"""

    def setUp(self):
        super().setUp()
        self.report = AnalyseReport.objects.create(
            title="测试报告详情",
            report_type=AnalyseReportType.SYSTEM,
            content=(
                "# 一、行为链分析\n\n"
                "通过对张三相关的11条风险单进行时序分析，发现存在明显的数据窃取行为链：\n\n"
                "1. 2026-01-10：张三首次访问敏感数据库，执行大批量查询操作\n"
                "2. 2026-01-12：通过API接口将查询结果导出至个人存储空间\n"
                "3. 2026-01-15：尝试修改审计日志以掩盖操作痕迹\n\n"
                "## 二、风险评估\n\n"
                "| 维度 | 评分 | 说明 |\n"
                "|---|---|---|\n"
                "| 数据敏感度 | 高 | 涉及用户PII数据 |\n"
                "| 行为意图性 | 高 | 存在刻意规避审计的行为 |\n"
                "| 影响范围 | 中 | 涉及约5000条用户记录 |\n\n"
                "## 三、处置建议\n\n"
                "建议立即冻结张三的系统访问权限，并启动数据泄露应急响应流程。\n"
            ),
            scenario=self.scenario_person,
            analysis_scope="责任人=张三",
            risk_count=2,
            status=AnalyseReportStatus.SUCCESS,
            prompt_params={"start_time": "2025-09-16", "end_time": "2026-03-16"},
        )
        AnalyseReportRisk.objects.create(report=self.report, risk_id=self.risk1.risk_id)
        AnalyseReportRisk.objects.create(report=self.report, risk_id=self.risk2.risk_id)

    def test_retrieve_report_detail(self):
        """测试获取报告详情"""
        result = self.resource.risk.retrieve_analyse_report(
            {
                "report_id": self.report.report_id,
            }
        )
        self.assertEqual(result["title"], "测试报告详情")
        self.assertEqual(result["report_type"], AnalyseReportType.SYSTEM)
        self.assertIn("行为链分析", result["content"])
        self.assertEqual(result["scenario_name"], "责任人行为调查分析报告")
        self.assertEqual(result["risk_count"], 2)
        self.assertIn(self.risk1.risk_id, result["risk_ids"])
        self.assertIn(self.risk2.risk_id, result["risk_ids"])
        self.assertIsNone(result["error_message"])

    def test_retrieve_failed_report_returns_error_message(self):
        """失败报告详情返回错误信息展示字段"""
        failed_report = AnalyseReport.objects.create(
            title="失败报告详情",
            report_type=AnalyseReportType.SYSTEM,
            status=AnalyseReportStatus.FAILED,
            prompt_params={},
            extra_info={
                "error": {
                    "error_type": "Exception",
                    "error_message": "API调用失败",
                    "retry_count": 3,
                    "max_retries": 3,
                }
            },
            created_by="admin",
        )

        result = self.resource.risk.retrieve_analyse_report({"report_id": failed_report.report_id})

        self.assertEqual(result["error_message"], "API调用失败")

    def test_retrieve_report_not_found(self):
        """测试获取不存在的报告"""
        with self.assertRaises(Http404):
            self.resource.risk.retrieve_analyse_report({"report_id": 99999})

    @mock.patch("services.web.risk.resources.analyse_report.get_request_username", return_value="admin")
    def test_retrieve_report_rejects_other_user_report(self, _mock_username):
        """测试不能查看其他用户创建的报告"""
        other_report = AnalyseReport.objects.create(
            title="其他用户报告",
            report_type=AnalyseReportType.SYSTEM,
            status=AnalyseReportStatus.SUCCESS,
            prompt_params={},
            created_by="other_user",
        )

        with self.assertRaises(Http404):
            self.resource.risk.retrieve_analyse_report({"report_id": other_report.report_id})


class TestUpdateAnalyseReport(AnalyseReportTestBase):
    """测试编辑AI报告"""

    def setUp(self):
        super().setUp()
        self.report = AnalyseReport.objects.create(
            title="原始标题",
            report_type=AnalyseReportType.SYSTEM,
            content=(
                "# 一、原始分析报告\n\n"
                "本报告对近期高风险事件进行了初步分析。\n\n"
                "## 二、风险概览\n\n"
                "共检测到12条风险单，其中高风险5条、中风险7条。\n\n"
                "## 三、后续计划\n\n"
                "建议对高风险事件优先进行人工审核确认。\n"
            ),
            status=AnalyseReportStatus.SUCCESS,
            prompt_params={},
        )

    def test_update_report_title(self):
        """测试更新报告标题"""
        result = self.resource.risk.update_analyse_report(
            {
                "report_id": self.report.report_id,
                "title": "修改后的标题",
            }
        )
        self.assertEqual(result["title"], "修改后的标题")
        self.report.refresh_from_db()
        self.assertEqual(self.report.title, "修改后的标题")

    def test_update_report_content(self):
        """测试更新报告内容"""
        new_content = (
            "# 一、修改后的分析报告\n\n"
            "经过人工审核和补充分析，更新以下内容：\n\n"
            "## 二、新增发现\n\n"
            "在原有12条风险单基础上，新发现3条关联风险，均与权限提升相关。\n\n"
            "## 三、更新后的处置建议\n\n"
            "- 扩大审查范围至关联账号\n"
            "- 对涉及的15条风险单逐一确认处置状态"
        )
        result = self.resource.risk.update_analyse_report(
            {
                "report_id": self.report.report_id,
                "content": new_content,
            }
        )
        self.assertEqual(result["content"], new_content)
        self.report.refresh_from_db()
        self.assertEqual(self.report.content, new_content)

    def test_update_report_both_fields(self):
        """测试同时更新标题和内容"""
        result = self.resource.risk.update_analyse_report(
            {
                "report_id": self.report.report_id,
                "title": "新标题",
                "content": (
                    "# 一、更新后的报告\n\n" "报告内容已全面更新，新增了根因分析和处置建议两个章节。\n\n" "## 二、根因分析\n\n" "经排查，本次风险事件的根因为权限管理流程存在漏洞。"
                ),
            }
        )
        new_content = "# 一、更新后的报告\n\n" "报告内容已全面更新，新增了根因分析和处置建议两个章节。\n\n" "## 二、根因分析\n\n" "经排查，本次风险事件的根因为权限管理流程存在漏洞。"
        self.assertEqual(result["title"], "新标题")
        self.assertEqual(result["content"], new_content)

    def test_update_report_not_found(self):
        """测试更新不存在的报告"""
        with self.assertRaises(Http404):
            self.resource.risk.update_analyse_report(
                {
                    "report_id": 99999,
                    "title": "Test",
                }
            )

    @mock.patch("services.web.risk.resources.analyse_report.get_request_username", return_value="admin")
    def test_update_report_rejects_other_user_report(self, _mock_username):
        """测试不能编辑其他用户创建的报告"""
        other_report = AnalyseReport.objects.create(
            title="其他用户报告",
            report_type=AnalyseReportType.SYSTEM,
            status=AnalyseReportStatus.SUCCESS,
            prompt_params={},
            created_by="other_user",
        )

        with self.assertRaises(Http404):
            self.resource.risk.update_analyse_report(
                {
                    "report_id": other_report.report_id,
                    "title": "非法修改",
                }
            )


class TestDeleteAnalyseReport(AnalyseReportTestBase):
    """测试删除AI报告"""

    def setUp(self):
        super().setUp()
        self.report = AnalyseReport.objects.create(
            title="待删除报告",
            report_type=AnalyseReportType.SYSTEM,
            status=AnalyseReportStatus.SUCCESS,
            prompt_params={},
        )
        AnalyseReportRisk.objects.create(report=self.report, risk_id=self.risk1.risk_id)

    def test_delete_report(self):
        """测试删除报告"""
        report_id = self.report.report_id
        self.resource.risk.delete_analyse_report({"report_id": report_id})

        # 验证报告已删除
        self.assertFalse(AnalyseReport.objects.filter(report_id=report_id).exists())
        # 验证关联关系已级联删除
        self.assertFalse(AnalyseReportRisk.objects.filter(report_id=report_id).exists())

    def test_delete_report_not_found(self):
        """测试删除不存在的报告"""
        with self.assertRaises(Http404):
            self.resource.risk.delete_analyse_report({"report_id": 99999})

    @mock.patch("services.web.risk.resources.analyse_report.get_request_username", return_value="admin")
    def test_delete_report_rejects_other_user_report(self, _mock_username):
        """测试不能删除其他用户创建的报告"""
        other_report = AnalyseReport.objects.create(
            title="其他用户报告",
            report_type=AnalyseReportType.SYSTEM,
            status=AnalyseReportStatus.SUCCESS,
            prompt_params={},
            created_by="other_user",
        )

        with self.assertRaises(Http404):
            self.resource.risk.delete_analyse_report({"report_id": other_report.report_id})
        self.assertTrue(AnalyseReport.objects.filter(report_id=other_report.report_id).exists())


class TestExportAnalyseReport(AnalyseReportTestBase):
    """测试导出AI报告"""

    @staticmethod
    def _read_fixture(filename):
        return (Path(__file__).parent / "fixtures" / filename).read_text(encoding="utf-8")

    @staticmethod
    def _extract_html_body(html):
        return html.split("<body>", 1)[1].split("</body>", 1)[0].strip()

    def setUp(self):
        super().setUp()
        self.report = AnalyseReport.objects.create(
            title="导出测试报告",
            report_type=AnalyseReportType.SYSTEM,
            content=self._read_fixture("analyse_report_export.md"),
            analysis_scope="风险类型=综合",
            risk_count=5,
            status=AnalyseReportStatus.SUCCESS,
            prompt_params={},
        )

    def test_export_markdown(self):
        """测试导出为Markdown"""
        result = self.resource.risk.export_analyse_report(
            {
                "report_id": self.report.report_id,
                "export_format": "markdown",
            }
        )
        self.assertEqual(result["Content-Type"], "text/markdown; charset=utf-8")
        self.assertIn("attachment", result["Content-Disposition"])
        self.assertEqual(result.content.decode("utf-8"), self._read_fixture("analyse_report_export.md"))

    def test_export_pdf(self):
        """测试导出为PDF（回退为HTML）"""
        result = self.resource.risk.export_analyse_report(
            {
                "report_id": self.report.report_id,
                "export_format": "pdf",
            }
        )
        # 可能回退为HTML（如果xhtml2pdf不可用）
        content_type = result["Content-Type"]
        self.assertTrue(
            content_type.startswith("application/pdf") or content_type.startswith("text/html"),
            f"Unexpected content type: {content_type}",
        )
        self.assertIn("attachment", result["Content-Disposition"])

    def test_export_markdown_filename_has_md_extension(self):
        """测试 Markdown 导出的文件名以 .md 结尾"""
        result = self.resource.risk.export_analyse_report(
            {
                "report_id": self.report.report_id,
                "export_format": "markdown",
            }
        )
        disposition = result["Content-Disposition"]
        # 文件名应包含 .md 扩展名
        self.assertIn(".md", disposition)
        self.assertNotIn(".pdf", disposition)
        self.assertNotIn(".html", disposition)
        self.assertIn("filename*=utf-8''", disposition)
        self.assertNotIn('filename="%E5', disposition)

    def test_export_pdf_filename_matches_content_type(self):
        """测试 PDF 导出的文件名扩展名与实际内容类型匹配"""
        result = self.resource.risk.export_analyse_report(
            {
                "report_id": self.report.report_id,
                "export_format": "pdf",
            }
        )
        content_type = result["Content-Type"]
        disposition = result["Content-Disposition"]
        if content_type.startswith("application/pdf"):
            # PDF 生成成功，文件名应以 .pdf 结尾
            self.assertIn(".pdf", disposition)
        else:
            # 回退为 HTML，文件名应以 .html 结尾
            self.assertIn(".html", disposition)
            self.assertNotIn(".pdf", disposition)
        self.assertIn("filename*=utf-8''", disposition)
        self.assertNotIn('filename="%E5', disposition)

    def test_export_pdf_renders_content_only(self):
        """测试 PDF 渲染内容与 Markdown 一致，不额外拼接标题和元信息"""
        with mock.patch("services.web.risk.resources.analyse_report.ExportAnalyseReport._create_pdf") as mock_create:
            mock_create.return_value = b"%PDF-1.4 fake content"
            self.resource.risk.export_analyse_report(
                {
                    "report_id": self.report.report_id,
                    "export_format": "pdf",
                }
            )

        full_html = mock_create.call_args.kwargs["html"]
        self.assertEqual(
            self._extract_html_body(full_html),
            self._read_fixture("analyse_report_export_body.html").strip(),
        )
        self.assertNotIn("<h1>导出测试报告</h1>", full_html)
        self.assertNotIn("报告类型:", full_html)
        self.assertNotIn("分析范围:", full_html)

    def test_export_pdf_table_styles_wrap_long_text(self):
        """测试 PDF 表格样式限制长文本跨列溢出"""
        with mock.patch("services.web.risk.resources.analyse_report.ExportAnalyseReport._create_pdf") as mock_create:
            mock_create.return_value = b"%PDF-1.4 fake content"
            self.resource.risk.export_analyse_report(
                {
                    "report_id": self.report.report_id,
                    "export_format": "pdf",
                }
            )

        full_html = mock_create.call_args.kwargs["html"]
        self.assertIn("-pdf-word-wrap: CJK", full_html)

    def test_export_pdf_text_styles_wrap_long_text(self):
        """测试 PDF 普通段落和列表项限制长文本跨页边界溢出"""
        with mock.patch("services.web.risk.resources.analyse_report.ExportAnalyseReport._create_pdf") as mock_create:
            mock_create.return_value = b"%PDF-1.4 fake content"
            self.resource.risk.export_analyse_report(
                {
                    "report_id": self.report.report_id,
                    "export_format": "pdf",
                }
            )

        full_html = mock_create.call_args.kwargs["html"]
        self.assertIn(
            "p, li {\n"
            "        -pdf-word-wrap: CJK;\n"
            "        word-break: break-word;\n"
            "        word-wrap: break-word;\n"
            "        overflow-wrap: anywhere;",
            full_html,
        )

    def test_export_pdf_heading_and_code_styles_wrap_long_text(self):
        """测试 PDF 标题、引用和代码块限制长文本跨页边界溢出"""
        with mock.patch("services.web.risk.resources.analyse_report.ExportAnalyseReport._create_pdf") as mock_create:
            mock_create.return_value = b"%PDF-1.4 fake content"
            self.resource.risk.export_analyse_report(
                {
                    "report_id": self.report.report_id,
                    "export_format": "pdf",
                }
            )

        full_html = mock_create.call_args.kwargs["html"]
        self.assertIn("h1, h2, h3, blockquote, code, pre {", full_html)
        self.assertIn("-pdf-word-wrap: CJK", full_html)
        self.assertIn("white-space: pre-wrap", full_html)

    def test_create_pdf_uses_xhtml2pdf(self):
        """测试 PDF 字节生成逻辑使用 xhtml2pdf"""
        pisa_status = mock.Mock(err=False)
        mock_create_pdf = mock.Mock(return_value=pisa_status)
        fake_module = types.SimpleNamespace(pisa=types.SimpleNamespace(CreatePDF=mock_create_pdf))
        with mock.patch.dict(sys.modules, {"xhtml2pdf": fake_module}):
            pdf_bytes = self.resource.risk.export_analyse_report._create_pdf(html="<html>报告</html>")

        self.assertEqual(pdf_bytes, b"")
        dest = mock_create_pdf.call_args.kwargs["dest"]
        self.assertIsInstance(dest, io.BytesIO)
        self.assertIn("link_callback", mock_create_pdf.call_args.kwargs)

    def test_pdf_resource_callback_rejects_local_file(self):
        """测试 PDF 资源回调拒绝读取服务器本地文件"""
        callback = self.resource.risk.export_analyse_report._resolve_pdf_resource

        for local_uri in ["/etc/passwd", "file:///etc/passwd"]:
            resolved_uri = callback(local_uri, None)
            self.assertNotEqual(resolved_uri, local_uri)
            self.assertTrue(resolved_uri.startswith("data:image/gif;base64,"))

    def test_pdf_resource_callback_allows_remote_images(self):
        """测试 PDF 资源回调允许外部和内网图片"""
        callback = self.resource.risk.export_analyse_report._resolve_pdf_resource

        self.assertEqual(callback("https://example.com/a.png", None), "https://example.com/a.png")
        self.assertEqual(callback("http://127.0.0.1/a.png", None), "http://127.0.0.1/a.png")

    def test_pdf_resource_callback_allows_builtin_font_only(self):
        """测试 PDF 资源回调仅允许内置字体本地路径"""
        export_resource = self.resource.risk.export_analyse_report

        self.assertEqual(
            export_resource._resolve_pdf_resource(export_resource._CJK_FONT_PATH, None),
            export_resource._CJK_FONT_PATH,
        )

    @mock.patch("services.web.risk.resources.analyse_report.ExportAnalyseReport._export_pdf")
    def test_export_pdf_success_filename_is_pdf(self, mock_export_pdf):
        """测试 PDF 生成成功时文件名为 .pdf"""
        from urllib.parse import quote

        from django.http import HttpResponse

        mock_response = HttpResponse(b"%PDF-1.4 fake content", content_type="application/pdf")
        filename = f"{self.report.title}.pdf"
        mock_response["Content-Disposition"] = f'attachment; filename="{quote(filename)}"'
        mock_export_pdf.return_value = mock_response

        result = self.resource.risk.export_analyse_report(
            {
                "report_id": self.report.report_id,
                "export_format": "pdf",
            }
        )
        self.assertIn(".pdf", result["Content-Disposition"])
        self.assertEqual(result["Content-Type"], "application/pdf")

    @mock.patch("services.web.risk.resources.analyse_report.ExportAnalyseReport._export_pdf")
    def test_export_pdf_fallback_filename_is_html(self, mock_export_pdf):
        """测试 PDF 生成失败回退为 HTML 时文件名为 .html"""
        from urllib.parse import quote

        from django.http import HttpResponse

        mock_response = HttpResponse("<html>fallback</html>", content_type="text/html; charset=utf-8")
        filename = f"{self.report.title}.html"
        mock_response["Content-Disposition"] = f'attachment; filename="{quote(filename)}"'
        mock_export_pdf.return_value = mock_response

        result = self.resource.risk.export_analyse_report(
            {
                "report_id": self.report.report_id,
                "export_format": "pdf",
            }
        )
        self.assertIn(".html", result["Content-Disposition"])
        self.assertNotIn(".pdf", result["Content-Disposition"])

    def test_export_not_found(self):
        """测试导出不存在的报告"""
        with self.assertRaises(Http404):
            self.resource.risk.export_analyse_report(
                {
                    "report_id": 99999,
                    "export_format": "markdown",
                }
            )

    @mock.patch("services.web.risk.resources.analyse_report.get_request_username", return_value="admin")
    def test_export_report_rejects_other_user_report(self, _mock_username):
        """测试不能导出其他用户创建的报告"""
        other_report = AnalyseReport.objects.create(
            title="其他用户报告",
            report_type=AnalyseReportType.SYSTEM,
            content="other content",
            status=AnalyseReportStatus.SUCCESS,
            prompt_params={},
            created_by="other_user",
        )

        with self.assertRaises(Http404):
            self.resource.risk.export_analyse_report(
                {
                    "report_id": other_report.report_id,
                    "export_format": "markdown",
                }
            )


class TestListAnalyseReportRisk(AnalyseReportTestBase):
    """测试报告关联风险列表"""

    def setUp(self):
        super().setUp()
        self.report = AnalyseReport.objects.create(
            title="关联风险测试",
            report_type=AnalyseReportType.SYSTEM,
            risk_count=2,
            status=AnalyseReportStatus.SUCCESS,
            prompt_params={},
        )
        AnalyseReportRisk.objects.create(report=self.report, risk_id=self.risk1.risk_id)
        AnalyseReportRisk.objects.create(report=self.report, risk_id=self.risk2.risk_id)

    def test_list_report_risks(self):
        """测试获取报告关联的风险列表，返回完整风险信息"""
        result = self.resource.risk.list_analyse_report_risk(
            {
                "report_id": self.report.report_id,
            }
        )
        self.assertEqual(len(result), 2)
        risk_ids = [r["risk_id"] for r in result]
        self.assertIn(self.risk1.risk_id, risk_ids)
        self.assertIn(self.risk2.risk_id, risk_ids)

    def test_list_report_risks_contains_title(self):
        """测试返回结果包含风险标题"""
        result = self.resource.risk.list_analyse_report_risk(
            {
                "report_id": self.report.report_id,
            }
        )
        titles = [r["title"] for r in result]
        self.assertIn("Test Risk 1", titles)
        self.assertIn("Test Risk 2", titles)

    def test_list_report_risks_contains_risk_level(self):
        """测试返回结果包含风险等级（来自关联策略）"""
        result = self.resource.risk.list_analyse_report_risk(
            {
                "report_id": self.report.report_id,
            }
        )
        for risk_data in result:
            self.assertEqual(risk_data["risk_level"], RiskLevel.HIGH.value)

    def test_list_report_risks_contains_expected_fields(self):
        """测试返回结果包含所有预期字段"""
        result = self.resource.risk.list_analyse_report_risk(
            {
                "report_id": self.report.report_id,
            }
        )
        expected_fields = {
            "risk_id",
            "title",
            "risk_level",
            "status",
            "event_time",
            "event_end_time",
            "operator",
            "current_operator",
            "strategy_id",
            "risk_label",
        }
        for risk_data in result:
            self.assertTrue(
                expected_fields.issubset(set(risk_data.keys())),
                f"Missing fields: {expected_fields - set(risk_data.keys())}",
            )

    def test_list_report_risks_contains_status(self):
        """测试返回结果包含风险状态"""
        result = self.resource.risk.list_analyse_report_risk(
            {
                "report_id": self.report.report_id,
            }
        )
        for risk_data in result:
            self.assertEqual(risk_data["status"], "new")

    def test_list_report_risks_contains_strategy_id(self):
        """测试返回结果包含策略ID"""
        result = self.resource.risk.list_analyse_report_risk(
            {
                "report_id": self.report.report_id,
            }
        )
        for risk_data in result:
            self.assertEqual(risk_data["strategy_id"], self.strategy.strategy_id)

    def test_list_report_risks_filters_by_risk_id(self):
        """测试报告关联风险列表支持按风险ID过滤"""
        result = self.resource.risk.list_analyse_report_risk.request(
            {"report_id": self.report.report_id, "risk_id": self.risk1.risk_id}
        )

        self.assertEqual([item["risk_id"] for item in result], [self.risk1.risk_id])

    def test_list_report_risks_filters_by_status(self):
        """测试报告关联风险列表支持按风险状态过滤"""
        self.risk2.status = RiskStatus.CLOSED
        self.risk2.save(update_fields=["status"])

        result = self.resource.risk.list_analyse_report_risk.request(
            {"report_id": self.report.report_id, "status": RiskStatus.NEW}
        )

        self.assertEqual([item["risk_id"] for item in result], [self.risk1.risk_id])

    def test_list_report_risks_filters_by_keyword(self):
        """测试报告关联风险列表支持按关键词过滤"""
        result = self.resource.risk.list_analyse_report_risk.request(
            {"report_id": self.report.report_id, "keyword": "Test Risk 1"}
        )

        self.assertEqual([item["risk_id"] for item in result], [self.risk1.risk_id])

    def test_list_report_risks_filters_by_risk_level(self):
        """测试报告关联风险列表支持按风险等级过滤"""
        low_strategy = Strategy.objects.create(
            namespace="default",
            strategy_name="test-low-strategy",
            risk_level=RiskLevel.LOW.value,
        )
        self.risk2.strategy = low_strategy
        self.risk2.save(update_fields=["strategy"])

        result = self.resource.risk.list_analyse_report_risk.request(
            {"report_id": self.report.report_id, "risk_level": RiskLevel.HIGH.value}
        )

        self.assertEqual([item["risk_id"] for item in result], [self.risk1.risk_id])

    def test_list_report_risks_filters_by_risk_label(self):
        """测试报告关联风险列表支持按风险标签过滤"""
        self.risk1.risk_label = RiskLabel.MISREPORT
        self.risk1.save(update_fields=["risk_label"])
        self.risk2.risk_label = RiskLabel.NORMAL
        self.risk2.save(update_fields=["risk_label"])

        result = self.resource.risk.list_analyse_report_risk.request(
            {"report_id": self.report.report_id, "risk_label": RiskLabel.MISREPORT}
        )

        self.assertEqual([item["risk_id"] for item in result], [self.risk1.risk_id])

    def test_list_report_risks_empty_report(self):
        """测试没有关联风险的报告返回空列表"""
        empty_report = AnalyseReport.objects.create(
            title="无关联风险",
            report_type=AnalyseReportType.SYSTEM,
            risk_count=0,
            status=AnalyseReportStatus.SUCCESS,
            prompt_params={},
        )
        result = self.resource.risk.list_analyse_report_risk(
            {
                "report_id": empty_report.report_id,
            }
        )
        self.assertEqual(len(result), 0)

    def test_list_report_risks_response_serializer(self):
        """测试响应序列化器字段定义正确"""
        risk = Risk.objects.select_related("strategy").get(risk_id=self.risk1.risk_id)
        serializer = ListAnalyseReportRiskResponseSerializer(risk)
        data = serializer.data
        self.assertEqual(data["risk_id"], self.risk1.risk_id)
        self.assertEqual(data["title"], "Test Risk 1")
        self.assertEqual(data["risk_level"], RiskLevel.HIGH.value)
        self.assertEqual(data["strategy_id"], self.strategy.strategy_id)

    def test_list_report_risks_request_limits_page_size(self):
        """关联风险列表单页最多返回 100 条"""
        serializer = ListAnalyseReportRiskRequestSerializer(
            data={
                "report_id": self.report.report_id,
                "page": 1,
                "page_size": 101,
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("page_size", serializer.errors)

    def test_list_report_risks_uses_subquery_for_report_risks(self):
        """关联风险列表不预先拉取全部 risk_id 到内存"""
        from services.web.risk.resources.analyse_report import ListAnalyseReportRisk

        queryset = ListAnalyseReportRisk().perform_request({"report_id": self.report.report_id})

        self.assertIn("SELECT", str(queryset.query).upper())
        self.assertIn("risk_analysereportrisk", str(queryset.query))

    @mock.patch("services.web.risk.resources.analyse_report.get_request_username", return_value="admin")
    def test_list_report_risks_rejects_other_user_report(self, _mock_username):
        """测试不能查看其他用户报告关联的风险"""
        other_report = AnalyseReport.objects.create(
            title="其他用户报告",
            report_type=AnalyseReportType.SYSTEM,
            risk_count=1,
            status=AnalyseReportStatus.SUCCESS,
            prompt_params={},
            created_by="other_user",
        )
        AnalyseReportRisk.objects.create(report=other_report, risk_id=self.risk1.risk_id)

        with self.assertRaises(Http404):
            self.resource.risk.list_analyse_report_risk({"report_id": other_report.report_id})


class TestListAnalyseReportRiskAPIGW(AnalyseReportTestBase):
    """测试报告关联风险 APIGW 列表"""

    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.report = AnalyseReport.objects.create(
            title="APIGW关联风险测试",
            report_type=AnalyseReportType.SYSTEM,
            risk_count=2,
            status=AnalyseReportStatus.SUCCESS,
            prompt_params={},
            created_by="other_user",
        )
        AnalyseReportRisk.objects.create(report=self.report, risk_id=self.risk1.risk_id)
        AnalyseReportRisk.objects.create(report=self.report, risk_id=self.risk2.risk_id)

    def request_apigw_resource(self, request_data=None, query_string="page=1&page_size=100"):
        request_data = request_data or {}
        request = Request(
            self.factory.post(
                f"/api/v1/analyse_report_apigw/{self.report.report_id}/risks/?{query_string}",
                request_data,
                format="json",
            )
        )
        return self.resource.risk.list_analyse_report_risk_apigw.request(
            {"report_id": self.report.report_id, **request_data},
            _request=request,
        )

    def test_apigw_request_serializer_normalizes_csv_fields(self):
        """APIGW请求序列化器负责拆分多值筛选参数"""
        serializer = ListAnalyseReportRiskRequestSerializer(
            data={
                "report_id": self.report.report_id,
                "risk_id": "risk-agent-001,risk-agent-002",
                "status": "new,closed",
                "risk_level": "HIGH,LOW",
                "risk_label": "normal,misreport",
                "keyword": " Test Risk ",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["risk_id"], ["risk-agent-001", "risk-agent-002"])
        self.assertEqual(serializer.validated_data["status"], ["new", "closed"])
        self.assertEqual(serializer.validated_data["risk_level"], ["HIGH", "LOW"])
        self.assertEqual(serializer.validated_data["risk_label"], ["normal", "misreport"])
        self.assertEqual(serializer.validated_data["keyword"], "Test Risk")

    @mock.patch("services.web.risk.resources.analyse_report.get_request_username", return_value="admin")
    def test_apigw_list_report_risks_skips_owner_check_but_limits_bound_risks(self, _mock_username):
        """APIGW跳过报告归属校验，但只能返回报告已绑定风险"""
        unbound_risk = Risk.objects.create(
            risk_id="risk-agent-unbound",
            raw_event_id="raw-agent-unbound",
            strategy=self.strategy,
            status=RiskStatus.NEW,
            title="Unbound Risk",
            event_time=datetime.datetime(2026, 1, 3, tzinfo=datetime.timezone.utc),
        )

        result = self.request_apigw_resource()

        self.assertEqual(result["total"], 2)
        risk_ids = {item["risk_id"] for item in result["results"]}
        self.assertEqual(risk_ids, {self.risk1.risk_id, self.risk2.risk_id})
        self.assertNotIn(unbound_risk.risk_id, risk_ids)

    def test_apigw_with_detail_excludes_risk_report(self):
        """APIGW风险详情不返回风险报告内容"""
        RiskReport.objects.create(risk=self.risk1, content="sensitive report content")

        result = self.request_apigw_resource({"risk_id": self.risk1.risk_id, "with_detail": True})

        self.assertEqual(result["total"], 1)
        self.assertEqual(len(result["results"]), 1)
        self.assertIn("detail", result["results"][0])
        self.assertNotIn("report", result["results"][0]["detail"])

    def test_apigw_response_serializer_matches_paginated_response(self):
        """APIGW响应序列化器与分页响应结构一致"""
        result = self.request_apigw_resource()
        serializer = ListAnalyseReportRiskPageResponseSerializer(data=result)

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["total"], 2)

    @mock.patch("core.permissions.get_app_info")
    def test_apigw_viewset_paginates_before_returning_detail(self, mock_get_app_info):
        """APIGW HTTP链路按分页返回当前页风险详情"""
        RiskReport.objects.create(risk=self.risk1, content="risk1 report content")
        RiskReport.objects.create(risk=self.risk2, content="risk2 report content")
        view = AnalyseReportAPIGWViewSet.as_view({"post": "risks"})
        request = self.factory.post(
            f"/api/v1/analyse_report_apigw/{self.report.report_id}/risks/?page=1&page_size=1",
            {"with_detail": True},
            format="json",
        )

        response = view(request, report_id=self.report.report_id)

        self.assertEqual(response.status_code, 200)
        mock_get_app_info.assert_called_once()
        data = response.data
        self.assertEqual(data["total"], 2)
        self.assertEqual(len(data["results"]), 1)
        self.assertIn("detail", data["results"][0])
        self.assertNotIn("report", data["results"][0]["detail"])


class TestListAnalyseReportByRisk(AnalyseReportTestBase):
    """测试通过风险ID反查报告"""

    def setUp(self):
        super().setUp()
        self.report1 = AnalyseReport.objects.create(
            title="反查报告1",
            report_type=AnalyseReportType.SYSTEM,
            risk_count=1,
            status=AnalyseReportStatus.SUCCESS,
            prompt_params={},
        )
        self.report2 = AnalyseReport.objects.create(
            title="反查报告2",
            report_type=AnalyseReportType.SYSTEM,
            risk_count=1,
            status=AnalyseReportStatus.SUCCESS,
            prompt_params={},
        )
        self.report_failed = AnalyseReport.objects.create(
            title="失败的报告",
            report_type=AnalyseReportType.SYSTEM,
            risk_count=1,
            status=AnalyseReportStatus.FAILED,
            prompt_params={},
        )
        # risk1 关联3个报告（2个成功，1个失败）
        AnalyseReportRisk.objects.create(report=self.report1, risk_id=self.risk1.risk_id)
        AnalyseReportRisk.objects.create(report=self.report2, risk_id=self.risk1.risk_id)
        AnalyseReportRisk.objects.create(report=self.report_failed, risk_id=self.risk1.risk_id)

    def test_list_reports_by_risk(self):
        """测试通过风险ID反查报告"""
        result = self.resource.risk.list_analyse_report_by_risk(
            {
                "risk_id": self.risk1.risk_id,
            }
        )
        # 只返回成功的报告
        self.assertEqual(len(result), 2)
        titles = [r["title"] for r in result]
        self.assertIn("反查报告1", titles)
        self.assertIn("反查报告2", titles)
        self.assertNotIn("失败的报告", titles)

    def test_list_reports_by_risk_empty(self):
        """测试没有关联报告的风险"""
        result = self.resource.risk.list_analyse_report_by_risk(
            {
                "risk_id": self.risk2.risk_id,
            }
        )
        self.assertEqual(len(result), 0)

    @mock.patch("services.web.risk.resources.analyse_report.get_request_username", return_value="admin")
    def test_list_reports_by_risk_only_returns_current_user_reports(self, _mock_username):
        """测试风险反查报告时只返回当前用户创建的报告"""
        self.report2.created_by = "other_user"
        self.report2.save(update_fields=["created_by"])

        result = self.resource.risk.list_analyse_report_by_risk(
            {
                "risk_id": self.risk1.risk_id,
            }
        )

        titles = [r["title"] for r in result]
        self.assertIn("反查报告1", titles)
        self.assertNotIn("反查报告2", titles)


class TestGenerateAnalyseReportTask(AnalyseReportTestBase):
    """测试 generate_analyse_report Celery 任务"""

    def setUp(self):
        super().setUp()
        self.report = AnalyseReport.objects.create(
            title="异步生成测试",
            report_type=AnalyseReportType.SYSTEM,
            scenario=self.scenario_person,
            risk_count=2,
            status=AnalyseReportStatus.GENERATING,
            prompt_params={
                "start_time": "2025-09-16 20:04:51",
                "end_time": "2026-03-16 20:04:51",
                "operator": "zhangsan",
                "use_bkbase": True,
                "datetime_origin": "now-6M,now",
            },
            created_by="admin",
        )

    @mock.patch("services.web.risk.tasks.timezone.now")
    @mock.patch("services.web.risk.tasks.api.bk_plugins_ai_audit_analyse.chat_completion")
    def test_task_success_with_scenario(self, mock_chat, mock_now):
        """测试使用场景配置成功生成报告"""
        start_time = datetime.datetime(2026, 6, 5, 10, 0, 0, tzinfo=datetime.timezone.utc)
        end_time = datetime.datetime(2026, 6, 5, 10, 0, 3, 250000, tzinfo=datetime.timezone.utc)
        mock_now.side_effect = [start_time, start_time, end_time, end_time, end_time]
        mock_chat.return_value = (
            "# 一、行为链分析\n\n"
            "通过对张三相关风险单的时序分析，发现以下行为模式：\n\n"
            "1. 集中在非工作时间段进行敏感数据查询\n"
            "2. 多次尝试修改自身权限配置\n"
            "3. 存在向外部IP传输数据的记录\n\n"
            "## 二、处置建议\n\n"
            "建议立即冻结相关账号并启动安全调查流程。\n"
        )

        from services.web.risk.tasks import generate_analyse_report

        result = generate_analyse_report(report_id=self.report.report_id)

        self.report.refresh_from_db()
        self.assertEqual(self.report.status, AnalyseReportStatus.SUCCESS)
        self.assertIn("行为链分析", self.report.content)
        self.assertIn("处置建议", self.report.content)
        self.assertEqual(result["report_id"], self.report.report_id)

        # 验证调用参数：只传递报告参数配置，不再传 chat_history 或原始筛选条件
        mock_chat.assert_called_once()
        call_kwargs = mock_chat.call_args[1]
        self.assertEqual(call_kwargs["user"], "admin")
        agent_input = json.loads(call_kwargs["input"])
        self.assertEqual(agent_input["报告ID"], self.report.report_id)
        self.assertEqual(agent_input["场景标识"], self.scenario_person.scenario_key)
        self.assertIn("请分析责任人行为", agent_input["分析要求"])
        self.assertNotIn("analysis_scope", agent_input)
        self.assertNotIn("分析范围", agent_input)
        self.assertNotIn("list_analyse_report_risk_apigw", call_kwargs["input"])
        self.assertNotIn("operator", agent_input)
        self.assertNotIn("zhangsan", call_kwargs["input"])
        self.assertNotIn("chat_history", call_kwargs)

        self.assertEqual(self.report.extra_info["agent_request"]["user"], "admin")
        self.assertEqual(self.report.extra_info["agent_request"]["input"], agent_input)
        self.assertEqual(self.report.extra_info["agent_request"]["execute_kwargs"], {"stream": True})
        self.assertEqual(self.report.extra_info["execution"]["started_at"], start_time.isoformat())
        self.assertEqual(self.report.extra_info["execution"]["ended_at"], end_time.isoformat())
        self.assertEqual(self.report.extra_info["execution"]["duration_seconds"], 3.25)
        extra_info = AnalyseReportExtraInfo.model_validate(self.report.extra_info)
        self.assertEqual(extra_info.agent_request.input["报告ID"], self.report.report_id)
        self.assertIsNone(extra_info.error)
        self.assertEqual(AnalyseReportExtraInfo.model_fields["agent_request"].description, "报告生成时传给 Agent 的请求信息")
        self.assertEqual(AnalyseReportExtraInfo.model_fields["execution"].description, "报告生成任务执行耗时信息")

    @mock.patch("services.web.risk.tasks.api.bk_plugins_ai_audit_analyse.chat_completion")
    def test_task_success_custom_analysis(self, mock_chat):
        """测试自定义分析成功生成报告"""
        # 修改为自定义分析
        self.report.scenario = None
        self.report.report_type = AnalyseReportType.CUSTOM
        self.report.custom_prompt = "分析张三在英雄联盟业务的资产转移行为"
        self.report.save()

        mock_chat.return_value = (
            "# 自定义分析报告\n\n"
            "## 一、资产转移行为概述\n\n"
            "张三在英雄联盟业务中存在多次异常资产转移操作，涉及虚拟道具和游戏币。\n\n"
            "## 二、详细分析\n\n"
            "| 时间 | 操作类型 | 涉及资产 | 金额(元) |\n"
            "|---|---|---|---|\n"
            "| 2026-01-10 | 道具转移 | 限定皮肤 | 500 |\n"
            "| 2026-01-12 | 游戏币转出 | 金币 | 10000 |\n\n"
            "## 三、风险判定\n\n"
            "上述行为存在利用职务便利进行虚拟资产侵占的嫌疑，建议深入调查。\n"
        )

        from services.web.risk.tasks import generate_analyse_report

        generate_analyse_report(report_id=self.report.report_id)

        self.report.refresh_from_db()
        self.assertEqual(self.report.status, AnalyseReportStatus.SUCCESS)
        self.assertIn("自定义分析报告", self.report.content)
        self.assertEqual(self.report.extra_info["agent_request"]["input"]["报告ID"], self.report.report_id)
        self.assertEqual(self.report.extra_info["agent_request"]["input"]["分析要求"], self.report.custom_prompt)
        self.assertIn("started_at", self.report.extra_info["execution"])
        self.assertIn("ended_at", self.report.extra_info["execution"])
        self.assertIn("duration_seconds", self.report.extra_info["execution"])

    @mock.patch("services.web.risk.tasks.api.bk_plugins_ai_audit_analyse.chat_completion")
    def test_task_links_risks_before_chat_completion(self, mock_chat):
        """调用 Agent 前先关联风险并填充 risk_count"""
        self.report.risk_count = 0
        self.report.prompt_params = {"risk_id": self.risk1.risk_id}
        self.report.save(update_fields=["risk_count", "prompt_params"])

        def assert_risk_count_filled(**kwargs):
            self.report.refresh_from_db()
            self.assertEqual(self.report.risk_count, 1)
            self.assertTrue(AnalyseReportRisk.objects.filter(report=self.report, risk_id=self.risk1.risk_id).exists())
            return "# 已生成报告"

        mock_chat.side_effect = assert_risk_count_filled

        from services.web.risk.tasks import generate_analyse_report

        generate_analyse_report(report_id=self.report.report_id)

        self.report.refresh_from_db()
        self.assertEqual(self.report.status, AnalyseReportStatus.SUCCESS)
        self.assertEqual(self.report.risk_count, 1)

    @mock.patch("services.web.risk.tasks.api.bk_plugins_ai_audit_analyse.chat_completion")
    def test_task_saves_agent_request_before_chat_completion(self, mock_chat):
        """调用 Agent 前先记录已确定的请求上下文"""

        def assert_agent_request_saved(**kwargs):
            self.report.refresh_from_db()
            self.assertEqual(self.report.extra_info["agent_request"]["user"], "admin")
            self.assertEqual(self.report.extra_info["agent_request"]["input"]["报告ID"], self.report.report_id)
            self.assertIn("started_at", self.report.extra_info["execution"])
            self.assertNotIn("ended_at", self.report.extra_info["execution"])
            self.assertNotIn("duration_seconds", self.report.extra_info["execution"])
            self.assertNotIn("error", self.report.extra_info)
            extra_info = AnalyseReportExtraInfo.model_validate(self.report.extra_info)
            self.assertIsNone(extra_info.execution.ended_at)
            return "# 已生成报告"

        mock_chat.side_effect = assert_agent_request_saved

        from services.web.risk.tasks import generate_analyse_report

        generate_analyse_report(report_id=self.report.report_id)

    @mock.patch("services.web.risk.tasks.timezone.now")
    @mock.patch("services.web.risk.tasks.api.bk_plugins_ai_audit_analyse.chat_completion")
    def test_task_failure(self, mock_chat, mock_now):
        """测试达到最大重试次数后标记为失败"""
        start_time = datetime.datetime(2026, 6, 5, 11, 0, 0, tzinfo=datetime.timezone.utc)
        end_time = datetime.datetime(2026, 6, 5, 11, 0, 1, 500000, tzinfo=datetime.timezone.utc)
        mock_now.side_effect = [start_time, start_time, end_time, end_time, end_time]
        mock_chat.side_effect = Exception("API调用失败")

        from services.web.risk.tasks import generate_analyse_report

        original_retries = generate_analyse_report.request.retries
        generate_analyse_report.request.retries = generate_analyse_report.max_retries
        try:
            with self.assertRaisesRegex(Exception, "API调用失败"):
                generate_analyse_report(report_id=self.report.report_id)
        finally:
            generate_analyse_report.request.retries = original_retries

        self.report.refresh_from_db()
        self.assertEqual(self.report.status, AnalyseReportStatus.FAILED)
        self.assertEqual(self.report.extra_info["agent_request"]["input"]["报告ID"], self.report.report_id)
        self.assertEqual(self.report.extra_info["execution"]["started_at"], start_time.isoformat())
        self.assertEqual(self.report.extra_info["execution"]["ended_at"], end_time.isoformat())
        self.assertEqual(self.report.extra_info["execution"]["duration_seconds"], 1.5)
        self.assertEqual(self.report.extra_info["error"]["error_type"], "Exception")
        self.assertEqual(self.report.extra_info["error"]["error_message"], "API调用失败")
        self.assertEqual(self.report.extra_info["error"]["retry_count"], generate_analyse_report.max_retries)
        extra_info = AnalyseReportExtraInfo.model_validate(self.report.extra_info)
        self.assertEqual(extra_info.error.error_message, "API调用失败")
        self.assertEqual(AnalyseReportExtraInfo.model_fields["error"].description, "报告最终失败时的错误信息")

    @mock.patch("services.web.risk.tasks.api.bk_plugins_ai_audit_analyse.chat_completion")
    def test_task_keeps_generating_status_before_max_retries(self, mock_chat):
        """未达到最大重试次数前，报告状态保持生成中"""
        mock_chat.side_effect = Exception("API调用失败")

        from celery.exceptions import Retry

        from services.web.risk.tasks import generate_analyse_report

        with self.assertRaises((Exception, Retry)):
            generate_analyse_report(report_id=self.report.report_id)

        self.report.refresh_from_db()
        self.assertEqual(self.report.status, AnalyseReportStatus.GENERATING)


class TestAnalyseReportModel(AnalyseReportTestBase):
    """测试 Agent Report 数据模型"""

    def test_create_analyse_report_scenario(self):
        """测试创建场景配置"""
        scenario = AnalyseReportScenario.objects.create(
            scenario_key="test_custom_scenario",
            name="测试自定义场景",
            description="用于测试的自定义场景",
            report_type=AnalyseReportType.CUSTOM,
            is_builtin=False,
            system_prompt="你是一个测试分析师",
            priority=10,
        )
        self.assertIsNotNone(scenario.scenario_id)
        self.assertEqual(scenario.is_enabled, True)

    def test_analyse_report_scenario_unique_key(self):
        """测试场景标识唯一约束"""
        from django.db import IntegrityError

        with self.assertRaises(IntegrityError):
            AnalyseReportScenario.objects.create(
                scenario_key="person_investigation",  # 已存在
                name="重复的场景",
                report_type=AnalyseReportType.SYSTEM,
                system_prompt="test",
            )

    def test_analyse_report_risk_relation(self):
        """测试报告-风险关联关系"""
        report = AnalyseReport.objects.create(
            title="关联测试",
            report_type=AnalyseReportType.SYSTEM,
            status=AnalyseReportStatus.SUCCESS,
            prompt_params={},
        )
        AnalyseReportRisk.objects.create(report=report, risk_id=self.risk1.risk_id)
        AnalyseReportRisk.objects.create(report=report, risk_id=self.risk2.risk_id)

        # 正向查询
        risk_ids = list(report.report_risks.values_list("risk_id", flat=True))
        self.assertEqual(len(risk_ids), 2)

        # 反向查询
        report_ids = list(
            AnalyseReportRisk.objects.filter(risk_id=self.risk1.risk_id).values_list("report_id", flat=True)
        )
        self.assertIn(report.report_id, report_ids)

    def test_analyse_report_risk_unique_together(self):
        """测试关联关系唯一约束"""
        from django.db import IntegrityError

        report = AnalyseReport.objects.create(
            title="唯一约束测试",
            report_type=AnalyseReportType.SYSTEM,
            status=AnalyseReportStatus.SUCCESS,
            prompt_params={},
        )
        AnalyseReportRisk.objects.create(report=report, risk_id=self.risk1.risk_id)

        with self.assertRaises(IntegrityError):
            AnalyseReportRisk.objects.create(report=report, risk_id=self.risk1.risk_id)

    def test_analyse_report_cascade_delete(self):
        """测试报告删除时级联删除关联关系"""
        report = AnalyseReport.objects.create(
            title="级联删除测试",
            report_type=AnalyseReportType.SYSTEM,
            status=AnalyseReportStatus.SUCCESS,
            prompt_params={},
        )
        AnalyseReportRisk.objects.create(report=report, risk_id=self.risk1.risk_id)
        report_id = report.report_id

        report.delete()
        self.assertFalse(AnalyseReportRisk.objects.filter(report_id=report_id).exists())


class TestAnalyseReportSerializer(AnalyseReportTestBase):
    """测试 Agent Report 序列化器"""

    def test_list_scenario_serializer(self):
        """测试场景列表序列化器"""
        serializer = ListAnalyseReportScenarioResponseSerializer(self.scenario_person)
        data = serializer.data
        self.assertEqual(data["scenario_key"], "person_investigation")
        self.assertEqual(data["name"], "责任人行为调查分析报告")
        self.assertTrue(data["is_builtin"])

    def test_retrieve_report_serializer_with_risk_ids(self):
        """测试报告详情序列化器包含风险ID列表"""
        report = AnalyseReport.objects.create(
            title="序列化器测试",
            report_type=AnalyseReportType.SYSTEM,
            scenario=self.scenario_person,
            status=AnalyseReportStatus.SUCCESS,
            prompt_params={},
        )
        AnalyseReportRisk.objects.create(report=report, risk_id=self.risk1.risk_id)

        serializer = RetrieveAnalyseReportResponseSerializer(report)
        data = serializer.data
        self.assertIn(self.risk1.risk_id, data["risk_ids"])
        self.assertEqual(data["scenario_name"], "责任人行为调查分析报告")

    def test_retrieve_report_serializer_no_scenario(self):
        """测试无场景的报告详情序列化器"""
        report = AnalyseReport.objects.create(
            title="无场景报告",
            report_type=AnalyseReportType.CUSTOM,
            status=AnalyseReportStatus.SUCCESS,
            prompt_params={},
        )
        serializer = RetrieveAnalyseReportResponseSerializer(report)
        data = serializer.data
        self.assertEqual(data["scenario_name"], "")

    def test_list_report_request_serializer_defaults(self):
        """测试列表请求序列化器默认值"""
        serializer = ListAnalyseReportRequestSerializer(data={})
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["keyword"], "")
        self.assertEqual(serializer.validated_data["status"], "")
        self.assertEqual(serializer.validated_data["sort"], ["-created_at"])

    def test_list_report_request_serializer_rejects_invalid_sort(self):
        """测试列表请求序列化器拒绝非报告字段排序"""
        serializer = ListAnalyseReportRequestSerializer(data={"sort": ["-event_time"]})
        self.assertFalse(serializer.is_valid())
        self.assertIn("sort", serializer.errors)

    def test_update_report_serializer_partial(self):
        """测试编辑请求序列化器支持部分更新"""
        serializer = UpdateAnalyseReportRequestSerializer(
            data={
                "report_id": 1,
                "title": "新标题",
            }
        )
        self.assertTrue(serializer.is_valid())
        self.assertNotIn("content", serializer.validated_data)


class TestGetAnalyseReportTaskResult(AnalyseReportTestBase):
    """测试查询任务状态"""

    def create_task_report(self, task_id):
        return AnalyseReport.objects.create(
            title="当前用户任务",
            report_type=AnalyseReportType.SYSTEM,
            status=AnalyseReportStatus.GENERATING,
            task_id=task_id,
            prompt_params={},
            created_by="admin",
        )

    @mock.patch("services.web.risk.resources.analyse_report.AsyncResult")
    def test_task_pending(self, mock_async_result_cls):
        """测试任务待处理状态"""
        self.create_task_report("test-task-001")
        mock_result = mock.MagicMock()
        mock_result.status = "PENDING"
        mock_result.result = None
        mock_async_result_cls.return_value = mock_result

        result = self.resource.risk.get_analyse_report_task_result({"task_id": "test-task-001"})
        self.assertEqual(result["status"], "PENDING")
        self.assertIsNone(result["result"])

    @mock.patch("services.web.risk.resources.analyse_report.AsyncResult")
    def test_task_success(self, mock_async_result_cls):
        """测试任务成功状态"""
        self.create_task_report("test-task-002")
        mock_result = mock.MagicMock()
        mock_result.status = "SUCCESS"
        mock_result.result = {"report_id": 1}
        mock_async_result_cls.return_value = mock_result

        result = self.resource.risk.get_analyse_report_task_result({"task_id": "test-task-002"})
        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(result["result"]["report_id"], 1)

    @mock.patch("services.web.risk.resources.analyse_report.AsyncResult")
    def test_task_failure(self, mock_async_result_cls):
        """测试任务失败状态"""
        self.create_task_report("test-task-003")
        mock_result = mock.MagicMock()
        mock_result.status = "FAILURE"
        mock_result.result = Exception("Something went wrong")
        mock_async_result_cls.return_value = mock_result

        result = self.resource.risk.get_analyse_report_task_result({"task_id": "test-task-003"})
        self.assertEqual(result["status"], "FAILURE")
        self.assertIn("error", result["result"])

    @mock.patch("services.web.risk.resources.analyse_report.AsyncResult")
    def test_task_running(self, mock_async_result_cls):
        """测试任务运行中状态"""
        self.create_task_report("test-task-004")
        mock_result = mock.MagicMock()
        mock_result.status = "STARTED"
        mock_result.result = None
        mock_async_result_cls.return_value = mock_result

        result = self.resource.risk.get_analyse_report_task_result({"task_id": "test-task-004"})
        self.assertEqual(result["status"], "RUNNING")

    @mock.patch("services.web.risk.resources.analyse_report.AsyncResult")
    def test_task_rejects_other_user_report_task(self, mock_async_result_cls):
        """不能查询其他用户报告的异步任务结果"""
        AnalyseReport.objects.create(
            title="其他用户任务",
            report_type=AnalyseReportType.SYSTEM,
            status=AnalyseReportStatus.GENERATING,
            task_id="other-user-task",
            prompt_params={},
            created_by="other_user",
        )

        with self.assertRaises(Http404):
            self.resource.risk.get_analyse_report_task_result({"task_id": "other-user-task"})
        mock_async_result_cls.assert_not_called()


class TestBuildRiskQueryFromPromptParams(AnalyseReportTestBase):
    """测试 _build_risk_query_from_prompt_params 辅助函数"""

    def _call(self, prompt_params):
        from services.web.risk.tasks import _build_risk_query_from_prompt_params

        return _build_risk_query_from_prompt_params(prompt_params)

    def test_empty_params_returns_all(self):
        """空参数应返回空 Q（匹配所有记录）"""
        q = self._call({})
        self.assertEqual(Risk.objects.filter(q).count(), Risk.objects.count())

    def test_none_params_returns_all(self):
        """None 参数应返回空 Q"""
        q = self._call(None)
        self.assertEqual(Risk.objects.filter(q).count(), Risk.objects.count())

    def test_filter_by_start_time(self):
        """测试按 start_time 过滤"""
        # risk1: 2026-01-01, risk2: 2026-01-02
        q = self._call({"start_time": "2026-01-02"})
        risk_ids = list(Risk.objects.filter(q).values_list("risk_id", flat=True))
        self.assertNotIn(self.risk1.risk_id, risk_ids)
        self.assertIn(self.risk2.risk_id, risk_ids)

    def test_filter_by_end_time(self):
        """测试按 end_time 过滤（不包含 end_time）"""
        q = self._call({"end_time": "2026-01-02"})
        risk_ids = list(Risk.objects.filter(q).values_list("risk_id", flat=True))
        self.assertIn(self.risk1.risk_id, risk_ids)
        self.assertNotIn(self.risk2.risk_id, risk_ids)

    def test_filter_by_time_range(self):
        """测试按时间范围过滤"""
        q = self._call(
            {
                "start_time": "2026-01-01",
                "end_time": "2026-01-03",
            }
        )
        risk_ids = list(Risk.objects.filter(q).values_list("risk_id", flat=True))
        self.assertIn(self.risk1.risk_id, risk_ids)
        self.assertIn(self.risk2.risk_id, risk_ids)

    def test_filter_by_operator(self):
        """测试按 operator 模糊匹配过滤"""
        self.risk1.operator = ["zhangsan", "lisi"]
        self.risk1.save(update_fields=["operator"])
        self.risk2.operator = ["wangwu"]
        self.risk2.save(update_fields=["operator"])

        q = self._call({"operator": "zhangsan"})
        risk_ids = list(Risk.objects.filter(q).values_list("risk_id", flat=True))
        self.assertIn(self.risk1.risk_id, risk_ids)
        self.assertNotIn(self.risk2.risk_id, risk_ids)

    def test_filter_by_risk_id(self):
        """测试按 risk_id 精确匹配过滤"""
        q = self._call({"risk_id": self.risk1.risk_id})
        risk_ids = list(Risk.objects.filter(q).values_list("risk_id", flat=True))
        self.assertEqual(risk_ids, [self.risk1.risk_id])

    def test_filter_by_multiple_risk_ids(self):
        """测试按多个 risk_id 过滤（逗号分隔）"""
        q = self._call({"risk_id": f"{self.risk1.risk_id},{self.risk2.risk_id}"})
        risk_ids = set(Risk.objects.filter(q).values_list("risk_id", flat=True))
        self.assertEqual(risk_ids, {self.risk1.risk_id, self.risk2.risk_id})

    def test_filter_by_strategy_id(self):
        """测试按 strategy_id 过滤"""
        q = self._call({"strategy_id": str(self.strategy.strategy_id)})
        risk_ids = list(Risk.objects.filter(q).values_list("risk_id", flat=True))
        self.assertIn(self.risk1.risk_id, risk_ids)
        self.assertIn(self.risk2.risk_id, risk_ids)

    def test_filter_by_risk_level(self):
        """测试按 risk_level 过滤"""
        q = self._call({"risk_level": RiskLevel.HIGH.value})
        risk_ids = list(Risk.objects.filter(q).values_list("risk_id", flat=True))
        # strategy 的 risk_level 是 HIGH，应匹配到所有风险
        self.assertIn(self.risk1.risk_id, risk_ids)
        self.assertIn(self.risk2.risk_id, risk_ids)

    def test_filter_by_nonexistent_risk_level(self):
        """测试按不存在的 risk_level 过滤，应无结果"""
        q = self._call({"risk_level": RiskLevel.LOW.value})
        risk_ids = list(Risk.objects.filter(q).values_list("risk_id", flat=True))
        self.assertEqual(risk_ids, [])

    def test_combined_filters(self):
        """测试组合多个过滤条件"""
        self.risk1.operator = ["zhangsan"]
        self.risk1.save(update_fields=["operator"])

        q = self._call(
            {
                "start_time": "2026-01-01",
                "end_time": "2026-01-03",
                "operator": "zhangsan",
            }
        )
        risk_ids = list(Risk.objects.filter(q).values_list("risk_id", flat=True))
        self.assertIn(self.risk1.risk_id, risk_ids)
        # risk2 没有 zhangsan 作为 operator
        self.assertNotIn(self.risk2.risk_id, risk_ids)

    def test_ignores_non_filter_params(self):
        """测试非过滤参数（如 use_bkbase、datetime_origin）不影响查询"""
        q = self._call(
            {
                "use_bkbase": True,
                "datetime_origin": "now-6M,now",
            }
        )
        # 不应报错，且应返回所有记录
        self.assertEqual(Risk.objects.filter(q).count(), Risk.objects.count())


class TestLinkRisksToReport(AnalyseReportTestBase):
    """测试 _link_risks_to_report 辅助函数"""

    def setUp(self):
        super().setUp()
        self.iam_patcher = mock.patch.object(
            Risk,
            "iam_risk_filter",
            return_value=Q(risk_id__in=[self.risk1.risk_id, self.risk2.risk_id]),
        )
        self.iam_filter_mock = self.iam_patcher.start()
        self.addCleanup(self.iam_patcher.stop)
        self.grant_list_risk_permission(self.risk1.risk_id)
        self.grant_list_risk_permission(self.risk2.risk_id)

    def grant_list_risk_permission(self, risk_id, username="admin"):
        TicketPermission.objects.get_or_create(
            risk_id=risk_id,
            action=ActionEnum.LIST_RISK.id,
            user=username,
            user_type=UserType.OPERATOR,
        )

    def _call(self, report):
        from services.web.risk.tasks import _link_risks_to_report

        return _link_risks_to_report(report)

    def test_link_risks_with_matching_params(self):
        """测试根据 prompt_params 关联风险"""
        self.risk1.operator = ["zhangsan"]
        self.risk1.save(update_fields=["operator"])
        self.risk2.operator = ["lisi"]
        self.risk2.save(update_fields=["operator"])

        report = AnalyseReport.objects.create(
            title="关联测试",
            report_type=AnalyseReportType.SYSTEM,
            status=AnalyseReportStatus.SUCCESS,
            prompt_params={
                "operator": "zhangsan",
                "start_time": "2025-01-01",
                "end_time": "2027-01-01",
            },
            created_by="admin",
        )

        count = self._call(report)

        self.assertEqual(count, 1)
        risk_ids = list(AnalyseReportRisk.objects.filter(report=report).values_list("risk_id", flat=True))
        self.assertIn(self.risk1.risk_id, risk_ids)
        self.assertNotIn(self.risk2.risk_id, risk_ids)

        # 验证 risk_count 已更新
        report.refresh_from_db()
        self.assertEqual(report.risk_count, 1)

    def test_link_risks_with_empty_params(self):
        """测试空 prompt_params 关联所有风险"""
        report = AnalyseReport.objects.create(
            title="空参数关联测试",
            report_type=AnalyseReportType.SYSTEM,
            status=AnalyseReportStatus.SUCCESS,
            prompt_params={},
            created_by="admin",
        )

        count = self._call(report)

        self.assertEqual(count, Risk.objects.count())
        report.refresh_from_db()
        self.assertEqual(report.risk_count, Risk.objects.count())

    def test_link_risks_no_match(self):
        """测试无匹配风险时返回 0"""
        report = AnalyseReport.objects.create(
            title="无匹配关联测试",
            report_type=AnalyseReportType.SYSTEM,
            status=AnalyseReportStatus.SUCCESS,
            prompt_params={
                "risk_id": "nonexistent-risk-id",
            },
            created_by="admin",
        )

        count = self._call(report)

        self.assertEqual(count, 0)
        self.assertFalse(AnalyseReportRisk.objects.filter(report=report).exists())

    def test_link_risks_ignore_conflicts(self):
        """测试重复调用不会报错（ignore_conflicts）"""
        report = AnalyseReport.objects.create(
            title="重复关联测试",
            report_type=AnalyseReportType.SYSTEM,
            status=AnalyseReportStatus.SUCCESS,
            prompt_params={
                "risk_id": self.risk1.risk_id,
            },
            created_by="admin",
        )

        # 第一次关联
        count1 = self._call(report)
        self.assertEqual(count1, 1)

        # 第二次关联，不应报错
        count2 = self._call(report)
        self.assertEqual(count2, 1)

        # 关联记录不应重复
        self.assertEqual(AnalyseReportRisk.objects.filter(report=report).count(), 1)

    def test_link_risks_updates_risk_count(self):
        """测试关联后更新 risk_count 字段"""
        report = AnalyseReport.objects.create(
            title="更新计数测试",
            report_type=AnalyseReportType.SYSTEM,
            status=AnalyseReportStatus.SUCCESS,
            risk_count=0,
            prompt_params={
                "start_time": "2025-01-01",
                "end_time": "2027-01-01",
            },
            created_by="admin",
        )

        count = self._call(report)

        report.refresh_from_db()
        self.assertEqual(report.risk_count, count)
        self.assertGreater(count, 0)

    def test_link_risks_only_links_report_creator_authed_risks(self):
        """测试后台关联风险时只关联报告创建人实际有权限的风险"""
        self.iam_filter_mock.return_value = Q(risk_id=self.risk1.risk_id)
        report = AnalyseReport.objects.create(
            title="权限过滤关联测试",
            report_type=AnalyseReportType.SYSTEM,
            status=AnalyseReportStatus.SUCCESS,
            prompt_params={
                "start_time": "2025-01-01",
                "end_time": "2027-01-01",
            },
            created_by="admin",
        )

        count = self._call(report)

        self.assertEqual(count, 1)
        risk_ids = list(AnalyseReportRisk.objects.filter(report=report).values_list("risk_id", flat=True))
        self.assertEqual(risk_ids, [self.risk1.risk_id])

    def test_link_risks_reuses_list_risk_filter_logic(self):
        """关联风险复用 ListRisk 的筛选逻辑，支持 risk_label 等列表接口参数"""
        self.risk1.risk_label = "misreport"
        self.risk1.save(update_fields=["risk_label"])
        self.risk2.risk_label = "normal"
        self.risk2.save(update_fields=["risk_label"])
        report = AnalyseReport.objects.create(
            title="复用列表筛选测试",
            report_type=AnalyseReportType.SYSTEM,
            status=AnalyseReportStatus.SUCCESS,
            prompt_params={
                "risk_label": "misreport",
            },
            created_by="admin",
        )

        count = self._call(report)

        self.assertEqual(count, 1)
        risk_ids = list(AnalyseReportRisk.objects.filter(report=report).values_list("risk_id", flat=True))
        self.assertEqual(risk_ids, [self.risk1.risk_id])

    @mock.patch("services.web.risk.resources.risk.ListRisk.retrieve_via_db")
    @mock.patch("services.web.risk.resources.risk.ListRisk.retrieve_via_bkbase")
    def test_link_risks_reuses_list_risk_bkbase_result(self, mock_retrieve_via_bkbase, mock_retrieve_via_db):
        """事件字段筛选时，关联风险使用 ListRisk 的 BKBase 最终结果"""
        self.strategy.event_data_field_configs = [{"field_name": "ip", "display_name": "IP"}]
        self.strategy.save(update_fields=["event_data_field_configs"])
        mock_retrieve_via_bkbase.return_value = ([self.risk2], mock.MagicMock(), [])
        report = AnalyseReport.objects.create(
            title="复用BKBase结果测试",
            report_type=AnalyseReportType.SYSTEM,
            status=AnalyseReportStatus.SUCCESS,
            prompt_params={
                "event_filters": [
                    {
                        "field": "ip",
                        "display_name": "IP",
                        "operator": EventFilterOperator.EQUAL,
                        "value": "127.0.0.1",
                    }
                ],
            },
            created_by="admin",
        )

        count = self._call(report)

        self.assertEqual(count, 1)
        risk_ids = list(AnalyseReportRisk.objects.filter(report=report).values_list("risk_id", flat=True))
        self.assertEqual(risk_ids, [self.risk2.risk_id])
        mock_retrieve_via_bkbase.assert_called_once()
        mock_retrieve_via_db.assert_not_called()

    @override_settings(ANALYSE_REPORT_RISK_LIMIT=1)
    def test_link_risks_respects_configured_limit(self):
        """关联风险数量受配置上限限制"""
        report = AnalyseReport.objects.create(
            title="关联数量限制测试",
            report_type=AnalyseReportType.SYSTEM,
            status=AnalyseReportStatus.SUCCESS,
            prompt_params={
                "start_time": "2025-01-01",
                "end_time": "2027-01-01",
            },
            created_by="admin",
        )

        count = self._call(report)

        self.assertEqual(count, 1)
        self.assertEqual(AnalyseReportRisk.objects.filter(report=report).count(), 1)


class TestGenerateAnalyseReportTaskLinkRisks(AnalyseReportTestBase):
    """测试 generate_analyse_report 任务中关联风险的集成行为"""

    def setUp(self):
        super().setUp()
        self.iam_patcher = mock.patch.object(
            Risk,
            "iam_risk_filter",
            return_value=Q(risk_id__in=[self.risk1.risk_id, self.risk2.risk_id]),
        )
        self.iam_patcher.start()
        self.addCleanup(self.iam_patcher.stop)
        TicketPermission.objects.get_or_create(
            risk_id=self.risk1.risk_id,
            action=ActionEnum.LIST_RISK.id,
            user="admin",
            user_type=UserType.OPERATOR,
        )
        TicketPermission.objects.get_or_create(
            risk_id=self.risk2.risk_id,
            action=ActionEnum.LIST_RISK.id,
            user="admin",
            user_type=UserType.OPERATOR,
        )
        # 设置风险的 operator
        self.risk1.operator = ["zhangsan"]
        self.risk1.save(update_fields=["operator"])
        self.risk2.operator = ["lisi"]
        self.risk2.save(update_fields=["operator"])

        self.report = AnalyseReport.objects.create(
            title="集成测试-关联风险",
            report_type=AnalyseReportType.SYSTEM,
            scenario=self.scenario_person,
            risk_count=0,
            status=AnalyseReportStatus.GENERATING,
            prompt_params={
                "start_time": "2025-01-01",
                "end_time": "2027-01-01",
                "operator": "zhangsan",
            },
            created_by="admin",
        )

    @mock.patch("services.web.risk.tasks.api.bk_plugins_ai_audit_analyse.chat_completion")
    def test_task_creates_report_risk_records(self, mock_chat):
        """测试任务成功后自动创建 AnalyseReportRisk 关联记录"""
        mock_chat.return_value = (
            "# 分析结果\n\n"
            "## 一、关联风险分析\n\n"
            "基于风险过滤条件，共发现与张三相关的异常操作风险。\n\n"
            "## 二、关键发现\n\n"
            "1. 张三在近30天内的敏感数据访问频次显著高于同岗位平均水平\n"
            "2. 多次在非授权时间段执行数据导出操作\n\n"
            "## 三、建议\n\n"
            "建议加强对张三账号的实时监控，并通知其直属主管进行约谈。\n"
        )

        from services.web.risk.tasks import generate_analyse_report

        result = generate_analyse_report(report_id=self.report.report_id)

        self.assertEqual(result["report_id"], self.report.report_id)
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, AnalyseReportStatus.SUCCESS)

        # 验证 AnalyseReportRisk 关联记录已创建
        linked_risk_ids = list(AnalyseReportRisk.objects.filter(report=self.report).values_list("risk_id", flat=True))
        self.assertIn(self.risk1.risk_id, linked_risk_ids)
        self.assertNotIn(self.risk2.risk_id, linked_risk_ids)

        # 验证 risk_count 已更新
        self.assertEqual(self.report.risk_count, 1)

    @mock.patch("services.web.risk.tasks.api.bk_plugins_ai_audit_analyse.chat_completion")
    def test_task_links_all_risks_with_empty_params(self, mock_chat):
        """测试 prompt_params 为空时关联所有风险"""
        self.report.prompt_params = {}
        self.report.save(update_fields=["prompt_params"])

        mock_chat.return_value = (
            "# 全量风险分析报告\n\n"
            "## 一、概述\n\n"
            "本报告对所有风险进行了全面扫描和分类分析。\n\n"
            "## 二、风险分类统计\n\n"
            "| 类别 | 数量 | 占比 |\n"
            "|---|---|---|\n"
            "| 数据安全 | 15 | 30% |\n"
            "| 权限管理 | 20 | 40% |\n"
            "| 异常行为 | 15 | 30% |\n\n"
            "## 三、建议\n\n"
            "建议按风险等级优先处理高危事件，加强日常安全巡检。\n"
        )

        from services.web.risk.tasks import generate_analyse_report

        generate_analyse_report(report_id=self.report.report_id)

        self.report.refresh_from_db()
        linked_count = AnalyseReportRisk.objects.filter(report=self.report).count()
        self.assertEqual(linked_count, Risk.objects.count())
        self.assertEqual(self.report.risk_count, Risk.objects.count())

    @mock.patch("services.web.risk.tasks.generate_analyse_report.retry")
    @mock.patch("services.web.risk.tasks.api.bk_plugins_ai_audit_analyse.chat_completion")
    def test_task_retries_when_agent_returns_empty_content(self, mock_chat, mock_retry):
        """Agent 返回空报告时触发重试，不写入成功报告"""
        mock_chat.return_value = "   "
        mock_retry.side_effect = RuntimeError("retry called")

        from services.web.risk.tasks import generate_analyse_report

        with self.assertRaisesRegex(RuntimeError, "retry called"):
            generate_analyse_report(report_id=self.report.report_id)

        mock_retry.assert_called_once()
        self.report.refresh_from_db()
        self.assertNotEqual(self.report.status, AnalyseReportStatus.SUCCESS)

    @mock.patch("services.web.risk.tasks.generate_analyse_report.retry")
    @mock.patch("services.web.risk.tasks.api.bk_plugins_ai_audit_analyse.chat_completion")
    def test_task_retries_when_agent_returns_loading_content(self, mock_chat, mock_retry):
        """Agent 返回正在思考占位内容时触发重试，不写入成功报告"""
        mock_chat.return_value = "正在思考..."
        mock_retry.side_effect = RuntimeError("retry called")

        from services.web.risk.tasks import generate_analyse_report

        with self.assertRaisesRegex(RuntimeError, "retry called"):
            generate_analyse_report(report_id=self.report.report_id)

        mock_retry.assert_called_once()
        self.report.refresh_from_db()
        self.assertNotEqual(self.report.status, AnalyseReportStatus.SUCCESS)

    @mock.patch("services.web.risk.tasks._link_risks_to_report", side_effect=Exception("关联失败"))
    @mock.patch("services.web.risk.tasks.api.bk_plugins_ai_audit_analyse.chat_completion")
    def test_task_fails_before_chat_if_link_fails_on_max_retry(self, mock_chat, mock_link):
        """风险关联失败时不调用 Agent，最终重试失败后记录错误信息"""
        from services.web.risk.tasks import generate_analyse_report

        original_retries = generate_analyse_report.request.retries
        generate_analyse_report.request.retries = generate_analyse_report.max_retries
        try:
            with self.assertRaisesRegex(Exception, "关联失败"):
                generate_analyse_report(report_id=self.report.report_id)
        finally:
            generate_analyse_report.request.retries = original_retries

        self.report.refresh_from_db()
        self.assertEqual(self.report.status, AnalyseReportStatus.FAILED)
        self.assertNotIn("agent_request", self.report.extra_info)
        self.assertIn("execution", self.report.extra_info)
        self.assertEqual(self.report.extra_info["error"]["error_message"], "关联失败")
        mock_chat.assert_not_called()


class TestAnalyseReportAdmin(AnalyseReportTestBase):
    """测试 AI 分析报告相关模型已注册 admin"""

    def test_analyse_report_models_registered(self):
        self.assertIn(AnalyseReportScenario, admin.site._registry)
        self.assertIn(AnalyseReport, admin.site._registry)
        self.assertIn(AnalyseReportRisk, admin.site._registry)

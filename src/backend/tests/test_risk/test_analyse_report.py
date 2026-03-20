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
from unittest import mock

from django.http import Http404

from services.web.risk.constants import AnalyseReportStatus, AnalyseReportType
from services.web.risk.models import (
    AnalyseReport,
    AnalyseReportRisk,
    AnalyseReportScenario,
    Risk,
)
from services.web.risk.serializers import (
    GenerateAnalyseReportRequestSerializer,
    ListAnalyseReportRequestSerializer,
    ListAnalyseReportScenarioResponseSerializer,
    RetrieveAnalyseReportResponseSerializer,
    UpdateAnalyseReportRequestSerializer,
)
from services.web.strategy_v2.constants import RiskLevel
from services.web.strategy_v2.models import Strategy
from tests.base import TestCase


class AnalyseReportTestBase(TestCase):
    """Agent Report 测试基类，提供通用的 setUp"""

    def setUp(self):
        super().setUp()
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
            content="# 分析报告\n内容...",
            analysis_scope="责任人=张三，时间范围=近30天",
            risk_count=5,
            status=AnalyseReportStatus.SUCCESS,
            prompt_params={},
            created_by="admin",
        )
        self.report2 = AnalyseReport.objects.create(
            title="风险综合分析报告",
            report_type=AnalyseReportType.CUSTOM,
            content="# 综合分析\n内容...",
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
        # 创建其他用户的报告（不应出现在列表中）
        self.report_other_user = AnalyseReport.objects.create(
            title="其他用户的报告",
            report_type=AnalyseReportType.SYSTEM,
            content="# 其他用户报告",
            risk_count=3,
            status=AnalyseReportStatus.SUCCESS,
            prompt_params={},
            created_by="other_user",
        )

    def test_list_reports_only_success(self):
        """测试列表只返回成功的报告"""
        result = self.resource.risk.list_analyse_report({})
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


class TestRetrieveAnalyseReport(AnalyseReportTestBase):
    """测试AI报告详情"""

    def setUp(self):
        super().setUp()
        self.report = AnalyseReport.objects.create(
            title="测试报告详情",
            report_type=AnalyseReportType.SYSTEM,
            content="# 一、行为链分析\n通过对张三相关的11条风险单进行时序分析...",
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

    def test_retrieve_report_not_found(self):
        """测试获取不存在的报告"""
        with self.assertRaises(Http404):
            self.resource.risk.retrieve_analyse_report({"report_id": 99999})


class TestUpdateAnalyseReport(AnalyseReportTestBase):
    """测试编辑AI报告"""

    def setUp(self):
        super().setUp()
        self.report = AnalyseReport.objects.create(
            title="原始标题",
            report_type=AnalyseReportType.SYSTEM,
            content="# 原始内容",
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
        new_content = "# 修改后的内容\n新增加的分析..."
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
                "content": "新内容",
            }
        )
        self.assertEqual(result["title"], "新标题")
        self.assertEqual(result["content"], "新内容")

    def test_update_report_not_found(self):
        """测试更新不存在的报告"""
        with self.assertRaises(Http404):
            self.resource.risk.update_analyse_report(
                {
                    "report_id": 99999,
                    "title": "Test",
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


class TestExportAnalyseReport(AnalyseReportTestBase):
    """测试导出AI报告"""

    def setUp(self):
        super().setUp()
        self.report = AnalyseReport.objects.create(
            title="导出测试报告",
            report_type=AnalyseReportType.SYSTEM,
            content="# 一、总览\n\n风险数据分析结果...\n\n## 二、详情\n\n| 指标 | 值 |\n|---|---|\n| 总数 | 100 |",
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
                "format": "markdown",
            }
        )
        self.assertEqual(result["Content-Type"], "text/markdown; charset=utf-8")
        self.assertIn("attachment", result["Content-Disposition"])
        self.assertEqual(result.content.decode("utf-8"), self.report.content)

    def test_export_pdf(self):
        """测试导出为PDF（回退为HTML）"""
        result = self.resource.risk.export_analyse_report(
            {
                "report_id": self.report.report_id,
                "format": "pdf",
            }
        )
        # 可能回退为HTML（如果weasyprint不可用）
        content_type = result["Content-Type"]
        self.assertTrue(
            content_type.startswith("application/pdf") or content_type.startswith("text/html"),
            f"Unexpected content type: {content_type}",
        )
        self.assertIn("attachment", result["Content-Disposition"])

    def test_export_not_found(self):
        """测试导出不存在的报告"""
        with self.assertRaises(Http404):
            self.resource.risk.export_analyse_report(
                {
                    "report_id": 99999,
                    "format": "markdown",
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
        """测试获取报告关联的风险列表"""
        result = self.resource.risk.list_analyse_report_risk(
            {
                "report_id": self.report.report_id,
            }
        )
        self.assertEqual(len(result), 2)
        self.assertIn(self.risk1.risk_id, result)
        self.assertIn(self.risk2.risk_id, result)


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

    @mock.patch("services.web.risk.tasks.api.bk_plugins_ai_audit_analyse.chat_completion")
    def test_task_success_with_scenario(self, mock_chat):
        """测试使用场景配置成功生成报告"""
        mock_chat.return_value = "# 一、行为链分析\n分析结果..."

        from services.web.risk.tasks import generate_analyse_report

        result = generate_analyse_report(report_id=self.report.report_id)

        self.report.refresh_from_db()
        self.assertEqual(self.report.status, AnalyseReportStatus.SUCCESS)
        self.assertEqual(self.report.content, "# 一、行为链分析\n分析结果...")
        self.assertEqual(result["report_id"], self.report.report_id)

        # 验证调用参数：直接传递 prompt 文本，不再传 chat_history
        mock_chat.assert_called_once()
        call_kwargs = mock_chat.call_args[1]
        self.assertEqual(call_kwargs["user"], "admin")
        # input 是完整的文本字符串，包含场景 system_prompt 内容
        self.assertIn("请分析责任人行为", call_kwargs["input"])
        self.assertNotIn("chat_history", call_kwargs)

    @mock.patch("services.web.risk.tasks.api.bk_plugins_ai_audit_analyse.chat_completion")
    def test_task_success_custom_analysis(self, mock_chat):
        """测试自定义分析成功生成报告"""
        # 修改为自定义分析
        self.report.scenario = None
        self.report.report_type = AnalyseReportType.CUSTOM
        self.report.custom_prompt = "分析张三在英雄联盟业务的资产转移行为"
        self.report.save()

        mock_chat.return_value = "# 自定义分析报告\n分析结果..."

        from services.web.risk.tasks import generate_analyse_report

        generate_analyse_report(report_id=self.report.report_id)

        self.report.refresh_from_db()
        self.assertEqual(self.report.status, AnalyseReportStatus.SUCCESS)
        self.assertIn("自定义分析报告", self.report.content)

    @mock.patch("services.web.risk.tasks.api.bk_plugins_ai_audit_analyse.chat_completion")
    def test_task_failure(self, mock_chat):
        """测试生成报告失败"""
        mock_chat.side_effect = Exception("API调用失败")

        from celery.exceptions import Retry

        from services.web.risk.tasks import generate_analyse_report

        # 任务在直接调用时会抛出 Retry 异常（因为 max_retries=2）
        with self.assertRaises((Exception, Retry)):
            generate_analyse_report(report_id=self.report.report_id)

        self.report.refresh_from_db()
        self.assertEqual(self.report.status, AnalyseReportStatus.FAILED)


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
        self.assertEqual(serializer.validated_data["sort"], ["-created_at"])

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

    @mock.patch("services.web.risk.resources.analyse_report.AsyncResult")
    def test_task_pending(self, mock_async_result_cls):
        """测试任务待处理状态"""
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
        mock_result = mock.MagicMock()
        mock_result.status = "STARTED"
        mock_result.result = None
        mock_async_result_cls.return_value = mock_result

        result = self.resource.risk.get_analyse_report_task_result({"task_id": "test-task-004"})
        self.assertEqual(result["status"], "RUNNING")

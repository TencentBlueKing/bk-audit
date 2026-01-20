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

from django.utils import timezone

from services.web.risk.constants import RiskReportStatus, RiskStatus
from services.web.risk.models import Risk, RiskReport
from services.web.strategy_v2.constants import RiskLevel
from services.web.strategy_v2.models import Strategy
from tests.base import TestCase


class TestUpdateRisk(TestCase):
    """测试编辑风险接口"""

    def setUp(self):
        super().setUp()
        self.strategy = Strategy.objects.create(
            namespace="default",
            strategy_name="test-strategy",
            risk_level=RiskLevel.HIGH.value,
        )
        self.risk = Risk.objects.create(
            risk_id="risk-update-test",
            raw_event_id="raw-update",
            strategy=self.strategy,
            status=RiskStatus.NEW,
            title="Original Title",
            event_time=datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc),
        )

    def test_update_risk_title(self):
        """测试更新风险标题"""
        new_title = "Updated Title"
        result = self.resource.risk.update_risk({"risk_id": self.risk.risk_id, "title": new_title})

        self.risk.refresh_from_db()
        self.assertEqual(self.risk.title, new_title)
        self.assertEqual(result["title"], new_title)

    def test_update_risk_no_change(self):
        """测试更新风险时值未变化"""
        original_title = self.risk.title
        result = self.resource.risk.update_risk({"risk_id": self.risk.risk_id, "title": original_title})

        self.risk.refresh_from_db()
        self.assertEqual(self.risk.title, original_title)
        self.assertEqual(result["title"], original_title)

    def test_update_risk_not_found(self):
        """测试更新不存在的风险"""
        from django.http import Http404

        with self.assertRaises(Http404):
            self.resource.risk.update_risk({"risk_id": "non-existent-risk", "title": "New Title"})


class TestCreateRiskReport(TestCase):
    """测试创建风险报告接口"""

    def setUp(self):
        super().setUp()
        self.strategy = Strategy.objects.create(
            namespace="default",
            strategy_name="test-strategy",
            risk_level=RiskLevel.HIGH.value,
            report_enabled=True,
            report_config={"template": "Test template"},
        )
        self.risk = Risk.objects.create(
            risk_id="risk-report-test",
            raw_event_id="raw-report",
            strategy=self.strategy,
            status=RiskStatus.NEW,
            title="Risk for Report",
            event_time=datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc),
            auto_generate_report=False,
        )

    def test_create_risk_report(self):
        """测试创建风险报告"""
        content = "Test report content"
        result = self.resource.risk.create_risk_report(
            {
                "risk_id": self.risk.risk_id,
                "content": content,
                "auto_generate": True,
            }
        )

        self.assertEqual(result["content"], content)
        self.assertEqual(result["status"], RiskReportStatus.MANUAL.value)

        # 验证报告已创建
        report = RiskReport.objects.get(risk=self.risk)
        self.assertEqual(report.content, content)
        self.assertEqual(report.status, RiskReportStatus.MANUAL)

        # 验证风险的 auto_generate_report 已更新
        self.risk.refresh_from_db()
        self.assertTrue(self.risk.auto_generate_report)

    def test_create_risk_report_update_existing(self):
        """测试创建报告时更新已存在的报告"""
        # 先创建一个报告
        RiskReport.objects.create(
            risk=self.risk,
            content="Old content",
            status=RiskReportStatus.AUTO,
        )

        new_content = "New report content"
        result = self.resource.risk.create_risk_report(
            {
                "risk_id": self.risk.risk_id,
                "content": new_content,
                "auto_generate": False,
            }
        )

        self.assertEqual(result["content"], new_content)
        self.assertEqual(result["status"], RiskReportStatus.MANUAL.value)

        # 验证报告数量仍为1
        self.assertEqual(RiskReport.objects.filter(risk=self.risk).count(), 1)


class TestUpdateRiskReport(TestCase):
    """测试编辑风险报告接口"""

    def setUp(self):
        super().setUp()
        self.strategy = Strategy.objects.create(
            namespace="default",
            strategy_name="test-strategy",
            risk_level=RiskLevel.HIGH.value,
        )
        self.risk = Risk.objects.create(
            risk_id="risk-update-report-test",
            raw_event_id="raw-update-report",
            strategy=self.strategy,
            status=RiskStatus.NEW,
            title="Risk for Update Report",
            event_time=datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc),
            auto_generate_report=True,
        )
        self.report = RiskReport.objects.create(
            risk=self.risk,
            content="Original content",
            status=RiskReportStatus.AUTO,
        )

    def test_update_risk_report_content(self):
        """测试更新报告内容"""
        new_content = "Updated content"
        result = self.resource.risk.update_risk_report(
            {
                "risk_id": self.risk.risk_id,
                "content": new_content,
            }
        )

        self.assertEqual(result["content"], new_content)
        self.assertEqual(result["status"], RiskReportStatus.MANUAL.value)

        self.report.refresh_from_db()
        self.assertEqual(self.report.content, new_content)
        self.assertEqual(self.report.status, RiskReportStatus.MANUAL)

    def test_update_risk_report_with_auto_generate(self):
        """测试更新报告时同时更新自动生成标记"""
        self.resource.risk.update_risk_report(
            {
                "risk_id": self.risk.risk_id,
                "content": "New content",
                "auto_generate": False,
            }
        )

        self.risk.refresh_from_db()
        self.assertFalse(self.risk.auto_generate_report)

    def test_update_risk_report_not_found(self):
        """测试更新不存在的报告"""
        from django.http import Http404

        # 创建一个没有报告的风险
        risk_no_report = Risk.objects.create(
            risk_id="risk-no-report",
            raw_event_id="raw-no-report",
            strategy=self.strategy,
            status=RiskStatus.NEW,
            title="Risk without Report",
            event_time=datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc),
        )

        with self.assertRaises(Http404):
            self.resource.risk.update_risk_report(
                {
                    "risk_id": risk_no_report.risk_id,
                    "content": "New content",
                }
            )


class TestGenerateRiskReport(TestCase):
    """测试生成风险报告接口"""

    def setUp(self):
        super().setUp()
        self.strategy = Strategy.objects.create(
            namespace="default",
            strategy_name="test-strategy",
            risk_level=RiskLevel.HIGH.value,
            report_enabled=True,
            report_config={
                "template": "Risk: {{ risk.title }}",
                "ai_variables": [],
            },
        )
        self.risk = Risk.objects.create(
            risk_id="risk-generate-test",
            raw_event_id="raw-generate",
            strategy=self.strategy,
            status=RiskStatus.NEW,
            title="Risk for Generate",
            event_time=datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc),
        )

    def test_generate_risk_report(self):
        """测试生成报告返回任务ID"""
        with mock.patch("services.web.risk.resources.report.submit_render_task") as mock_submit:
            mock_async_result = mock.MagicMock()
            mock_async_result.id = "new_task_id_456"
            mock_submit.return_value = mock_async_result

            result = self.resource.risk.generate_risk_report({"risk_id": self.risk.risk_id})

        self.assertEqual(result["task_id"], "new_task_id_456")
        self.assertEqual(result["status"], "PENDING")

    def test_generate_risk_report_calls_submit_render_task(self):
        """测试生成报告调用 submit_render_task"""
        with mock.patch("services.web.risk.resources.report.submit_render_task") as mock_submit:
            mock_submit.return_value = mock.MagicMock(id="task_123")

            self.resource.risk.generate_risk_report({"risk_id": self.risk.risk_id})

            mock_submit.assert_called_once()
            call_kwargs = mock_submit.call_args[1]
            # 新签名使用 risk 和 report_config 参数
            self.assertEqual(call_kwargs["risk"].risk_id, self.risk.risk_id)
            self.assertIsNotNone(call_kwargs["report_config"])

    def test_generate_risk_report_disabled(self):
        """测试策略未启用报告时生成报告"""
        self.strategy.report_enabled = False
        self.strategy.save(update_fields=["report_enabled"])

        with self.assertRaises(ValueError):
            self.resource.risk.generate_risk_report({"risk_id": self.risk.risk_id})


class TestListRiskBrief(TestCase):
    """测试获取风险简要列表接口"""

    def setUp(self):
        super().setUp()
        self.strategy = Strategy.objects.create(
            namespace="default",
            strategy_name="test-strategy",
            risk_level=RiskLevel.HIGH.value,
        )
        self.now = timezone.now()
        # 注意：ListRiskBrief 使用 created_at 进行时间过滤
        self.risk1 = Risk.objects.create(
            risk_id="risk-brief-1",
            raw_event_id="raw-brief-1",
            strategy=self.strategy,
            status=RiskStatus.NEW,
            title="Risk 1",
            event_time=self.now - datetime.timedelta(days=1),
        )
        self.risk2 = Risk.objects.create(
            risk_id="risk-brief-2",
            raw_event_id="raw-brief-2",
            strategy=self.strategy,
            status=RiskStatus.NEW,
            title="Risk 2",
            event_time=self.now,
        )

    def test_list_risk_brief(self):
        """测试获取风险简要列表"""
        result = self.resource.risk.list_risk_brief(
            {
                "start_time": (self.now - datetime.timedelta(days=2)).isoformat(),
                "end_time": (self.now + datetime.timedelta(days=1)).isoformat(),
            }
        )

        self.assertEqual(len(result), 2)
        risk_ids = [r["risk_id"] for r in result]
        self.assertIn(self.risk1.risk_id, risk_ids)
        self.assertIn(self.risk2.risk_id, risk_ids)

    def test_list_risk_brief_with_strategy_filter(self):
        """测试按策略筛选风险简要列表"""
        other_strategy = Strategy.objects.create(
            namespace="default",
            strategy_name="other-strategy",
            risk_level=RiskLevel.LOW.value,
        )
        Risk.objects.create(
            risk_id="risk-other-strategy",
            raw_event_id="raw-other",
            strategy=other_strategy,
            status=RiskStatus.NEW,
            title="Other Risk",
            event_time=self.now,
        )

        result = self.resource.risk.list_risk_brief(
            {
                "strategy_id": self.strategy.strategy_id,
                "start_time": (self.now - datetime.timedelta(days=2)).isoformat(),
                "end_time": (self.now + datetime.timedelta(days=1)).isoformat(),
            }
        )

        self.assertEqual(len(result), 2)
        for r in result:
            self.assertEqual(r["strategy_id"], self.strategy.strategy_id)

    def test_list_risk_brief_empty_when_out_of_time_range(self):
        """测试时间范围外没有结果"""
        # 查询过去很久的时间范围，应该没有结果
        result = self.resource.risk.list_risk_brief(
            {
                "start_time": (self.now - datetime.timedelta(days=100)).isoformat(),
                "end_time": (self.now - datetime.timedelta(days=99)).isoformat(),
            }
        )

        self.assertEqual(len(result), 0)


class TestReportEnabled(TestCase):
    """测试 report_enabled 字段序列化"""

    def setUp(self):
        super().setUp()
        self.strategy_enabled = Strategy.objects.create(
            namespace="default",
            strategy_name="strategy-report-enabled",
            risk_level=RiskLevel.HIGH.value,
            report_enabled=True,
            report_config={"template": "Test"},
        )
        self.strategy_disabled = Strategy.objects.create(
            namespace="default",
            strategy_name="strategy-report-disabled",
            risk_level=RiskLevel.LOW.value,
            report_enabled=False,
        )
        self.risk_with_enabled = Risk.objects.create(
            risk_id="risk-report-enabled",
            raw_event_id="raw-enabled",
            strategy=self.strategy_enabled,
            status=RiskStatus.NEW,
            title="Risk with report enabled",
            event_time=datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc),
        )
        self.risk_with_disabled = Risk.objects.create(
            risk_id="risk-report-disabled",
            raw_event_id="raw-disabled",
            strategy=self.strategy_disabled,
            status=RiskStatus.NEW,
            title="Risk with report disabled",
            event_time=datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc),
        )

    def test_report_enabled_true_when_strategy_enabled(self):
        """测试策略启用报告时，风险的 report_enabled 为 True"""
        from services.web.risk.serializers import RiskInfoSerializer

        # 使用 select_related 预加载策略
        risk = Risk.objects.select_related("strategy").get(risk_id=self.risk_with_enabled.risk_id)
        serializer = RiskInfoSerializer(risk)
        self.assertTrue(serializer.data["report_enabled"])

    def test_report_enabled_false_when_strategy_disabled(self):
        """测试策略禁用报告时，风险的 report_enabled 为 False"""
        from services.web.risk.serializers import RiskInfoSerializer

        risk = Risk.objects.select_related("strategy").get(risk_id=self.risk_with_disabled.risk_id)
        serializer = RiskInfoSerializer(risk)
        self.assertFalse(serializer.data["report_enabled"])

    def test_multiple_risks_report_enabled(self):
        """测试多个风险的 report_enabled 字段正确序列化"""
        from services.web.risk.serializers import RiskInfoSerializer

        # 使用 select_related 预加载策略
        risks = Risk.objects.select_related("strategy").filter(
            risk_id__in=[self.risk_with_enabled.risk_id, self.risk_with_disabled.risk_id]
        )
        serializer = RiskInfoSerializer(risks, many=True)
        data_map = {item["risk_id"]: item for item in serializer.data}

        self.assertTrue(data_map[self.risk_with_enabled.risk_id]["report_enabled"])
        self.assertFalse(data_map[self.risk_with_disabled.risk_id]["report_enabled"])


class TestRiskReportRenderFailedEvent(TestCase):
    """测试风险报告渲染失败事件"""

    def test_event_attributes(self):
        """测试事件类属性定义正确"""
        from services.web.common.monitor import RiskReportRenderFailedEvent

        self.assertEqual(RiskReportRenderFailedEvent.name, "risk_report_render_failed")
        self.assertEqual(RiskReportRenderFailedEvent.documentation, "风险报告渲染失败")
        self.assertEqual(RiskReportRenderFailedEvent.labelnames, ["risk_id", "task_id"])

    def test_event_to_json(self):
        """测试事件 to_json 方法返回正确结构"""
        from services.web.common.monitor import RiskReportRenderFailedEvent

        event = RiskReportRenderFailedEvent(
            target="risk_test123",
            context={"risk_id": "test123", "task_id": "task456"},
            extra={"error": "Test error message"},
        )
        result = event.to_json()

        # to_json 返回包含 data_id, access_token, data 的字典
        self.assertIn("data_id", result)
        self.assertIn("access_token", result)
        self.assertIn("data", result)
        self.assertEqual(len(result["data"]), 1)

        # 实际事件数据在 data[0] 中
        event_data = result["data"][0]
        self.assertEqual(event_data["target"], "risk_test123")
        self.assertEqual(event_data["event_name"], "risk_report_render_failed")
        self.assertIn("dimension", event_data)
        self.assertEqual(event_data["dimension"]["risk_id"], "test123")
        self.assertEqual(event_data["dimension"]["task_id"], "task456")
        self.assertIn("event", event_data)
        self.assertIn("error", event_data["event"]["content"])


class TestRiskReportHandlerMaxRetries(TestCase):
    """测试风险报告处理器最大重试次数处理"""

    def setUp(self):
        super().setUp()
        self.strategy = Strategy.objects.create(
            namespace="default",
            strategy_name="test-strategy",
            risk_level=RiskLevel.HIGH.value,
            report_enabled=True,
            report_config={"template": "Test template"},
        )
        self.risk = Risk.objects.create(
            risk_id="risk-max-retries-test",
            raw_event_id="raw-max-retries",
            strategy=self.strategy,
            status=RiskStatus.NEW,
            title="Risk for Max Retries Test",
            event_time=datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc),
        )

    def test_handle_max_retries_exceeded_reports_event(self):
        """测试达到最大重试次数时上报监控事件"""
        from services.web.risk.handlers.report import RiskReportHandler

        handler = RiskReportHandler(risk_id=self.risk.risk_id, task_id="test-task-123")
        test_exception = Exception("Test render error")

        with mock.patch("services.web.risk.handlers.report.api.bk_monitor.report_event") as mock_report_event:
            handler.handle_max_retries_exceeded(test_exception)

            # 验证 report_event 被调用
            mock_report_event.assert_called_once()

            # 验证调用参数（to_json 返回的结构）
            call_args = mock_report_event.call_args[0][0]
            self.assertIn("data", call_args)
            event_data = call_args["data"][0]
            self.assertEqual(event_data["target"], f"risk_{self.risk.risk_id}")
            self.assertEqual(event_data["event_name"], "risk_report_render_failed")
            self.assertEqual(event_data["dimension"]["risk_id"], self.risk.risk_id)
            self.assertEqual(event_data["dimension"]["task_id"], "test-task-123")

    def test_handle_max_retries_exceeded_logs_error(self):
        """测试达到最大重试次数时记录错误日志"""
        from services.web.risk.handlers.report import RiskReportHandler

        handler = RiskReportHandler(risk_id=self.risk.risk_id, task_id="test-task-456")
        test_exception = ValueError("Specific error")

        with mock.patch("services.web.risk.handlers.report.api.bk_monitor.report_event"):
            with mock.patch("services.web.risk.handlers.report.logger") as mock_logger:
                handler.handle_max_retries_exceeded(test_exception)

                # 验证错误日志被记录
                mock_logger.error.assert_called()
                error_call = mock_logger.error.call_args_list[0]
                self.assertIn("Max retries reached", error_call[0][0])
                self.assertIn(self.risk.risk_id, error_call[0][1:])

    def test_handle_max_retries_exceeded_continues_on_report_failure(self):
        """测试上报失败时不影响后续处理"""
        from core.exceptions import ApiRequestError
        from services.web.risk.handlers.report import RiskReportHandler

        handler = RiskReportHandler(risk_id=self.risk.risk_id, task_id="test-task-789")
        test_exception = Exception("Render failed")

        with mock.patch("services.web.risk.handlers.report.api.bk_monitor.report_event") as mock_report_event:
            # 模拟上报失败
            mock_report_event.side_effect = ApiRequestError("API error")

            with mock.patch("services.web.risk.handlers.report.logger") as mock_logger:
                # 不应该抛出异常
                handler.handle_max_retries_exceeded(test_exception)

                # 验证上报失败的错误日志被记录
                error_calls = [call for call in mock_logger.error.call_args_list if "Report event failed" in call[0][0]]
                self.assertEqual(len(error_calls), 1)

    def test_handle_max_retries_exceeded_triggers_tail_check(self):
        """测试达到最大重试次数后检查尾部触发"""
        from services.web.risk.handlers.report import RiskReportHandler

        handler = RiskReportHandler(risk_id=self.risk.risk_id, task_id="test-task-tail")
        test_exception = Exception("Render failed")

        with mock.patch("services.web.risk.handlers.report.api.bk_monitor.report_event"):
            with mock.patch.object(handler, "_handle_tail_trigger") as mock_tail:
                handler.handle_max_retries_exceeded(test_exception)

                # 验证尾部触发检查被调用
                mock_tail.assert_called_once()

    def test_handle_max_retries_exceeded_event_contains_error_info(self):
        """测试事件包含错误信息"""
        from services.web.risk.handlers.report import RiskReportHandler

        handler = RiskReportHandler(risk_id=self.risk.risk_id, task_id="test-task-error")
        error_message = "Connection timeout to render service"
        test_exception = TimeoutError(error_message)

        with mock.patch("services.web.risk.handlers.report.api.bk_monitor.report_event") as mock_report_event:
            handler.handle_max_retries_exceeded(test_exception)

            call_args = mock_report_event.call_args[0][0]
            event_data = call_args["data"][0]
            # 验证事件内容包含错误信息
            self.assertIn(error_message, event_data["event"]["content"])

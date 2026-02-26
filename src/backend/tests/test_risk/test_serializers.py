# -*- coding: utf-8 -*-
"""
risk serializers 单测
"""
from datetime import datetime
from types import SimpleNamespace

from django.conf import settings
from django.utils import timezone

from services.web.risk.models import Risk, RiskReport
from services.web.risk.serializers import (
    CreateRiskSerializer,
    ListEventResponseSerializer,
    ListRiskResponseSerializer,
    RiskInfoSerializer,
    RiskProviderSerializer,
)
from services.web.strategy_v2.models import Strategy
from tests.base import TestCase


class RiskSerializersTest(TestCase):
    def test_create_risk_serializer_parses_event_data(self):
        data = {
            "strategy_id": 1,
            "event_data": '{"foo": "bar"}',
            "dtEventTimeStamp": 1700000000000,
        }
        serializer = CreateRiskSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["event_data"], {"foo": "bar"})
        self.assertEqual(serializer.validated_data["event_time"], data["dtEventTimeStamp"])

    def test_list_event_response_serializer_rounds_microseconds(self):
        serializer = ListEventResponseSerializer()
        dt = timezone.make_aware(datetime(2024, 1, 1, 12, 0, 0, 500000))
        value = serializer.get_event_end_time(SimpleNamespace(event_end_time=dt))
        self.assertEqual(value, "2024-01-01 12:00:01")


# ---------------------------------------------------------------------------
# has_report 字段测试
# ---------------------------------------------------------------------------


class HasReportSerializerTestBase(TestCase):
    """创建测试所需的 Strategy / Risk / RiskReport 数据库对象"""

    def setUp(self):
        super().setUp()
        self.strategy = Strategy.objects.create(
            namespace=settings.DEFAULT_NAMESPACE,
            strategy_name="test-strategy-has-report",
        )
        self.risk_no_report = Risk.objects.create(
            risk_id="risk-no-report",
            raw_event_id="raw-no-report",
            strategy=self.strategy,
            event_time=timezone.now(),
        )
        self.risk_with_report = Risk.objects.create(
            risk_id="risk-with-report",
            raw_event_id="raw-with-report",
            strategy=self.strategy,
            event_time=timezone.now(),
            has_report=True,
        )
        self.report = RiskReport.objects.create(
            risk=self.risk_with_report,
            content="测试报告内容",
        )


class TestRiskProviderSerializerHasReport(HasReportSerializerTestBase):
    """RiskProviderSerializer 包含 has_report 字段的测试"""

    def test_has_report_field_present_in_output(self):
        """序列化输出中必须包含 has_report 字段"""
        data = RiskProviderSerializer(instance=self.risk_no_report).data
        self.assertIn("has_report", data)

    def test_has_report_false_when_no_report(self):
        """未生成报告时 has_report 应为 False"""
        data = RiskProviderSerializer(instance=self.risk_no_report).data
        self.assertFalse(data["has_report"])

    def test_has_report_true_when_report_exists(self):
        """已生成报告时 has_report 应为 True"""
        data = RiskProviderSerializer(instance=self.risk_with_report).data
        self.assertTrue(data["has_report"])

    def test_strategy_field_excluded(self):
        """strategy 字段应被排除（exclude = ['strategy']）"""
        data = RiskProviderSerializer(instance=self.risk_no_report).data
        self.assertNotIn("strategy", data)


class TestRiskInfoSerializerHasReport(HasReportSerializerTestBase):
    """RiskInfoSerializer.get_has_report() 的测试"""

    def test_has_report_false_when_no_related_report(self):
        """风险没有关联报告时 has_report 应为 False"""
        # 使用 select_related 确保 report 反向关系被访问
        risk = Risk.objects.get(risk_id=self.risk_no_report.risk_id)
        data = RiskInfoSerializer(instance=risk).data
        self.assertFalse(data["has_report"])

    def test_has_report_true_when_related_report_exists(self):
        """风险有关联报告时 has_report 应为 True"""
        risk = Risk.objects.select_related("report").get(risk_id=self.risk_with_report.risk_id)
        data = RiskInfoSerializer(instance=risk).data
        self.assertTrue(data["has_report"])


class TestListRiskResponseSerializerHasReport(HasReportSerializerTestBase):
    """ListRiskResponseSerializer.get_has_report() 使用 _has_report 注解的测试"""

    def _make_risk_obj(self, risk: Risk, has_report_annotated: bool) -> Risk:
        """模拟 annotated_queryset 给 Risk 对象附加 _has_report 属性"""
        risk._has_report = has_report_annotated
        risk.event_content_short = ""
        risk.filtered_event_data = {}
        return risk

    def test_has_report_false_via_annotation(self):
        """_has_report 注解为 False 时序列化结果应为 False"""
        risk = self._make_risk_obj(self.risk_no_report, has_report_annotated=False)
        data = ListRiskResponseSerializer(instance=risk).data
        self.assertFalse(data["has_report"])

    def test_has_report_true_via_annotation(self):
        """_has_report 注解为 True 时序列化结果应为 True"""
        risk = self._make_risk_obj(self.risk_with_report, has_report_annotated=True)
        data = ListRiskResponseSerializer(instance=risk).data
        self.assertTrue(data["has_report"])

    def test_has_report_defaults_false_when_annotation_missing(self):
        """未附加 _has_report 注解时应默认返回 False（getattr fallback）"""
        risk = self.risk_no_report
        risk.event_content_short = ""
        risk.filtered_event_data = {}
        # 不设置 _has_report，验证 getattr 默认值
        if hasattr(risk, "_has_report"):
            del risk._has_report
        data = ListRiskResponseSerializer(instance=risk).data
        self.assertFalse(data["has_report"])

    def test_has_report_field_in_meta_fields(self):
        """has_report 必须出现在 ListRiskResponseSerializer.Meta.fields 中"""
        self.assertIn("has_report", ListRiskResponseSerializer.Meta.fields)


class TestSyncRiskHasReportSignal(HasReportSerializerTestBase):
    """post_save 信号：创建 RiskReport 后自动将 Risk.has_report 置为 True"""

    def test_signal_sets_has_report_on_report_create(self):
        """新建 RiskReport 后，关联 Risk.has_report 应自动变为 True"""
        # risk_no_report 初始 has_report=False
        self.assertFalse(Risk.objects.get(risk_id=self.risk_no_report.risk_id).has_report)

        RiskReport.objects.create(
            risk=self.risk_no_report,
            content="新报告",
        )

        self.assertTrue(Risk.objects.get(risk_id=self.risk_no_report.risk_id).has_report)

    def test_signal_idempotent_on_report_update(self):
        """更新已有 RiskReport 时，Risk.has_report 仍保持 True"""
        self.assertTrue(Risk.objects.get(risk_id=self.risk_with_report.risk_id).has_report)

        self.report.content = "更新后的内容"
        self.report.save()

        self.assertTrue(Risk.objects.get(risk_id=self.risk_with_report.risk_id).has_report)

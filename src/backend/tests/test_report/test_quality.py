# -*- coding: utf-8 -*-
from unittest.mock import patch

from django.test import override_settings

from core.exceptions import ApiRequestError
from services.web.risk.constants import ContentQualityIssueType
from services.web.risk.report.quality import (
    ContentQualityChecker,
    check_and_report_quality,
)


class TestContentQualityChecker:
    """ContentQualityChecker 单元测试"""

    # ========== empty 类型 ==========

    def test_empty_none(self):
        """None 内容应检出 empty"""
        issues = ContentQualityChecker.check(None)
        assert len(issues) == 1
        assert issues[0].issue_type == ContentQualityIssueType.EMPTY

    def test_empty_string(self):
        """空字符串应检出 empty"""
        issues = ContentQualityChecker.check("")
        assert len(issues) == 1
        assert issues[0].issue_type == ContentQualityIssueType.EMPTY

    def test_empty_whitespace(self):
        """纯空白字符应检出 empty"""
        issues = ContentQualityChecker.check("   \n\t  ")
        assert len(issues) == 1
        assert issues[0].issue_type == ContentQualityIssueType.EMPTY

    def test_empty_short_circuit(self):
        """空内容应直接返回，不继续检测其他类型"""
        issues = ContentQualityChecker.check("")
        assert len(issues) == 1  # 只有 empty，没有 too_short

    # ========== too_short 类型 ==========

    @override_settings(REPORT_CONTENT_MIN_LENGTH=10)
    def test_too_short(self):
        """内容长度 < 阈值应检出 too_short"""
        issues = ContentQualityChecker.check("abc")
        types = [i.issue_type for i in issues]
        assert ContentQualityIssueType.TOO_SHORT in types

    @override_settings(REPORT_CONTENT_MIN_LENGTH=10)
    def test_exactly_min_length(self):
        """内容长度恰好等于阈值不应检出 too_short"""
        issues = ContentQualityChecker.check("a" * 10)
        types = [i.issue_type for i in issues]
        assert ContentQualityIssueType.TOO_SHORT not in types

    @override_settings(REPORT_CONTENT_MIN_LENGTH=5)
    def test_too_short_custom_threshold(self):
        """自定义阈值=5，长度为 3 应检出"""
        issues = ContentQualityChecker.check("abc")
        types = [i.issue_type for i in issues]
        assert ContentQualityIssueType.TOO_SHORT in types

    # ========== ai_error 类型 ==========

    def test_ai_error_detected(self):
        """包含 AI 错误标记应检出 ai_error"""
        content = "报告内容 [AI生成失败: timeout] 后续内容"
        issues = ContentQualityChecker.check(content)
        types = [i.issue_type for i in issues]
        assert ContentQualityIssueType.AI_ERROR in types

    def test_ai_error_multiple(self):
        """多次出现应 count > 1"""
        content = "[AI生成失败: err1] 中间 [AI生成失败: err2]"
        issues = ContentQualityChecker.check(content)
        ai_issues = [i for i in issues if i.issue_type == ContentQualityIssueType.AI_ERROR]
        assert ai_issues[0].count == 2

    # ========== ai_thinking 类型 ==========

    def test_ai_thinking_detected(self):
        """包含 '正在思考...' 应检出 ai_thinking"""
        content = "## 分析报告\n正在思考...\n后续内容正在思考..."
        issues = ContentQualityChecker.check(content)
        ai_thinking = [i for i in issues if i.issue_type == ContentQualityIssueType.AI_THINKING]
        assert len(ai_thinking) == 1
        assert ai_thinking[0].count == 2

    # ========== provider_error 类型 ==========

    def test_provider_error_detected(self):
        """包含 Provider 错误标记应检出 provider_error"""
        content = "报告 [Error: connection timeout] 内容"
        issues = ContentQualityChecker.check(content)
        types = [i.issue_type for i in issues]
        assert ContentQualityIssueType.PROVIDER_ERROR in types

    # ========== render_error 类型 ==========

    def test_render_error_detected(self):
        """包含渲染错误标记应检出 render_error"""
        content = "报告 [Render Error: undefined var] 内容"
        issues = ContentQualityChecker.check(content)
        types = [i.issue_type for i in issues]
        assert ContentQualityIssueType.RENDER_ERROR in types

    # ========== event_query_failed 类型 ==========

    def test_event_query_failed_detected(self):
        """包含事件查询失败标记应检出 event_query_failed"""
        content = "事件数量: 查询失败"
        issues = ContentQualityChecker.check(content)
        types = [i.issue_type for i in issues]
        assert ContentQualityIssueType.EVENT_QUERY_FAILED in types

    # ========== 正常内容 ==========

    @override_settings(REPORT_CONTENT_MIN_LENGTH=10)
    def test_normal_content_no_issues(self):
        """正常内容应无任何问题"""
        content = "## 风险分析报告\n\n这是一段正常的报告内容，包含详细的分析说明。"
        issues = ContentQualityChecker.check(content)
        assert issues == []

    # ========== 多种问题同时存在 ==========

    @override_settings(REPORT_CONTENT_MIN_LENGTH=100)
    def test_multiple_issues(self):
        """一段内容可以同时检出多种问题"""
        content = "[AI生成失败: x] 正在思考... [Error: y]"
        issues = ContentQualityChecker.check(content)
        types = {i.issue_type for i in issues}
        assert ContentQualityIssueType.TOO_SHORT in types
        assert ContentQualityIssueType.AI_ERROR in types
        assert ContentQualityIssueType.AI_THINKING in types
        assert ContentQualityIssueType.PROVIDER_ERROR in types


class TestCheckAndReportQuality:
    """check_and_report_quality 公共函数单元测试"""

    MOCK_REPORT_EVENT = "services.web.risk.report.quality.api.bk_monitor.report_event"
    MOCK_LOGGER = "services.web.risk.report.quality.logger"

    # ========== 质量正常：不上报 ==========

    @override_settings(REPORT_CONTENT_MIN_LENGTH=10)
    def test_no_issues_no_report(self):
        """质量正常时不上报监控事件，仅输出 info 日志"""
        with patch(self.MOCK_REPORT_EVENT) as mock_report, patch(self.MOCK_LOGGER) as mock_logger:
            content = "这是一段足够长的正常报告内容，没有任何错误标记。"
            issues = check_and_report_quality(content=content, risk_id="R001", task_id="T001")

            assert issues == []
            mock_logger.info.assert_called_once()
            mock_report.assert_not_called()

    # ========== 有问题：逐条上报 ==========

    @override_settings(REPORT_CONTENT_MIN_LENGTH=10)
    def test_issues_reported_per_type(self):
        """检出多种问题时，每种 issue_type 单独上报一次"""
        with patch(self.MOCK_REPORT_EVENT) as mock_report, patch(self.MOCK_LOGGER) as mock_logger:
            content = "[AI生成失败: timeout] 正在思考..."
            issues = check_and_report_quality(content=content, risk_id="R002", task_id="T002")

            # 应检出 ai_error 和 ai_thinking 两种问题
            types = {i.issue_type for i in issues}
            assert ContentQualityIssueType.AI_ERROR in types
            assert ContentQualityIssueType.AI_THINKING in types

            # 每种问题上报一次
            assert mock_report.call_count == len(issues)

            # 验证 warning 日志
            mock_logger.warning.assert_called_once()

    @override_settings(REPORT_CONTENT_MIN_LENGTH=10)
    def test_empty_content_reports_single_event(self):
        """空内容只检出 empty，上报一次"""
        with patch(self.MOCK_REPORT_EVENT) as mock_report:
            issues = check_and_report_quality(content="", risk_id="R003", task_id="T003")

            assert len(issues) == 1
            assert issues[0].issue_type == ContentQualityIssueType.EMPTY
            mock_report.assert_called_once()

    # ========== 上报失败：不影响返回值 ==========

    @override_settings(REPORT_CONTENT_MIN_LENGTH=10)
    def test_report_failure_does_not_affect_result(self):
        """上报监控事件失败时，函数仍正常返回问题列表"""
        with patch(self.MOCK_REPORT_EVENT) as mock_report, patch(self.MOCK_LOGGER) as mock_logger:
            mock_report.side_effect = ApiRequestError("mock error")

            issues = check_and_report_quality(content="", risk_id="R004", task_id="T004")

            assert len(issues) == 1
            assert issues[0].issue_type == ContentQualityIssueType.EMPTY

            # 上报失败应记录 error 日志
            mock_logger.error.assert_called_once()

    # ========== 上报事件参数验证 ==========

    @override_settings(REPORT_CONTENT_MIN_LENGTH=10)
    def test_report_event_payload(self):
        """验证上报事件的 target 和 context 参数正确"""
        with patch(self.MOCK_REPORT_EVENT) as mock_report:
            content = "[Render Error: undefined var]" + "x" * 50
            issues = check_and_report_quality(content=content, risk_id="R005", task_id="T005")

            assert len(issues) == 1
            assert issues[0].issue_type == ContentQualityIssueType.RENDER_ERROR

            # 获取 report_event 的调用参数
            call_args = mock_report.call_args
            event_json = call_args[0][0]  # 第一个位置参数

            # 验证事件结构
            assert "data_id" in event_json
            assert "data" in event_json
            data = event_json["data"][0]
            assert data["target"] == "risk_R005"
            assert data["dimension"]["risk_id"] == "R005"
            assert data["dimension"]["task_id"] == "T005"
            assert data["dimension"]["issue_type"] == ContentQualityIssueType.RENDER_ERROR

# -*- coding: utf-8 -*-
from django.test import override_settings

from services.web.risk.constants import ContentQualityIssueType
from services.web.risk.report.quality import ContentQualityChecker


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

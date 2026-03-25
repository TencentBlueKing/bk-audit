# -*- coding: utf-8 -*-
"""
风险报告内容质量检测器

在渲染完成、写入 DB 之前检测报告内容质量。
检测到问题后按 issue_type 维度上报监控事件，不阻断写入。

检测规则（共 7 种）：
1. empty            — 内容为空
2. too_short        — 内容过短（阈值通过 REPORT_CONTENT_MIN_LENGTH 配置，默认 10）
3. ai_error         — 包含 AI 错误标记 "[AI生成失败: "
4. ai_thinking      — 包含 AI 思考中间态 "正在思考..."
5. provider_error   — 包含 Provider 错误标记 "[Error: "
6. render_error     — 包含渲染错误标记 "[Render Error: "
7. event_query_failed — 包含事件查询失败占位符 "查询失败"
"""

from dataclasses import dataclass
from typing import List

from django.conf import settings

from services.web.risk.constants import (
    AI_ERROR_PREFIX,
    AI_THINKING_PATTERN,
    EVENT_QUERY_FAILED,
    ContentQualityIssueType,
)


@dataclass
class ContentQualityIssue:
    """内容质量问题"""

    issue_type: str  # ContentQualityIssueType 枚举值
    detail: str  # 问题详情
    count: int = 1  # 出现次数（错误标记扫描时使用）


class ContentQualityChecker:
    """报告内容质量检测器

    检测规则：
    1. 空内容 → empty（直接返回，不继续检测）
    2. 内容过短 → too_short（阈值通过 settings.REPORT_CONTENT_MIN_LENGTH 配置）
    3. 错误标记扫描 → ai_error / ai_thinking / provider_error / render_error / event_query_failed
    """

    # 已知的错误标记模式：(issue_type, 检测字符串)
    ERROR_PATTERNS: List[tuple] = [
        (ContentQualityIssueType.AI_ERROR, AI_ERROR_PREFIX),
        (ContentQualityIssueType.AI_THINKING, AI_THINKING_PATTERN),
        (ContentQualityIssueType.PROVIDER_ERROR, "[Error: "),
        (ContentQualityIssueType.RENDER_ERROR, "[Render Error: "),
        (ContentQualityIssueType.EVENT_QUERY_FAILED, str(EVENT_QUERY_FAILED)),
    ]

    @classmethod
    def check(cls, content: str) -> List[ContentQualityIssue]:
        """检测报告内容质量

        Args:
            content: 渲染后的报告内容

        Returns:
            问题列表，空列表表示质量正常
        """
        issues: List[ContentQualityIssue] = []

        # 1. 空内容检测
        if not content or not content.strip():
            issues.append(ContentQualityIssue(issue_type=ContentQualityIssueType.EMPTY, detail="报告内容为空"))
            return issues  # 空内容不需要继续检测

        stripped = content.strip()

        # 2. 过短内容检测
        min_length = settings.REPORT_CONTENT_MIN_LENGTH
        if len(stripped) < min_length:
            issues.append(
                ContentQualityIssue(
                    issue_type=ContentQualityIssueType.TOO_SHORT,
                    detail=f"报告内容过短({len(stripped)}/{min_length})",
                )
            )

        # 3. 错误标记扫描
        for issue_type, pattern in cls.ERROR_PATTERNS:
            count = content.count(pattern)
            if count > 0:
                issues.append(ContentQualityIssue(issue_type=issue_type, detail=pattern, count=count))

        return issues

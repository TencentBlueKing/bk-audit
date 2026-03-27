# -*- coding: utf-8 -*-
"""
风险报告内容质量检测器

在渲染完成后检测报告内容质量。

- ContentQualityChecker：纯检测器，返回问题列表，不产生副作用。
- check_and_report_quality()：公共函数，封装检测 + 监控事件上报，
  按 issue_type 维度逐条上报。调用方根据返回值自行决定后续行为
  （如 RiskReportHandler 会抛出 ContentQualityError 触发 Celery 重试）。

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

from bk_resource import api
from blueapps.utils.logger import logger
from django.conf import settings

from core.exceptions import ApiRequestError
from services.web.common.monitor import RiskReportContentQualityEvent
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


def check_and_report_quality(content: str, risk_id: str) -> List[ContentQualityIssue]:
    """检测报告内容质量，有问题则上报监控事件

    公共函数，供各报告生成入口调用。调用方根据返回值自行决定后续行为（重试/忽略等）。

    Args:
        content: 渲染后的报告内容
        risk_id: 风险ID

    Returns:
        问题列表，空列表表示质量正常
    """
    issues = ContentQualityChecker.check(content)
    if not issues:
        logger.info(
            "[ContentQualityCheck] Passed. risk_id=%s",
            risk_id,
        )
        return issues

    # 汇总日志
    issue_summary = "; ".join(f"{issue.issue_type}(x{issue.count}): {issue.detail}" for issue in issues)
    logger.warning(
        "[ContentQualityCheck] Issues detected. risk_id=%s, issues=%s",
        risk_id,
        issue_summary,
    )

    # 每种问题类型单独上报（便于监控平台按 issue_type 维度配置告警策略）
    for issue in issues:
        event = RiskReportContentQualityEvent(
            target=f"risk_{risk_id}",
            context={
                "risk_id": risk_id,
                "issue_type": issue.issue_type,
            },
            extra={
                "detail": issue.detail,
                "count": str(issue.count),
            },
        )
        try:
            api.bk_monitor.report_event(event.to_json())
        except ApiRequestError as e:
            logger.error(
                "[ContentQualityCheck] Report event failed. risk_id=%s, issue_type=%s, error=%s",
                risk_id,
                issue.issue_type,
                e,
            )

    return issues

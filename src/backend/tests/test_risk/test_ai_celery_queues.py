# -*- coding: utf-8 -*-
"""AI Celery 队列隔离：标题共用，单/多风险分析独立，预览与编排留在 risk_report。

助手会话标题与风险报告标题共用 ai_title；意图识别等 Message Task 仍走 default。
日志分析 / 统计专属队列不在本分支，合入后再补五类互异断言。
"""

from pathlib import Path

import yaml
from django.conf import settings

from services.web.ai_assistant.tasks.audit_search import (
    execute_log_search,
    execute_system_selection,
    execute_user_intent,
)
from services.web.ai_assistant.tasks.conversation import generate_conversation_title
from services.web.risk.constants import RiskAICeleryQueue
from services.web.risk.report.renderer import render_template
from services.web.risk.tasks import (
    generate_analyse_report,
    generate_analyse_report_title,
    render_ai_variable,
    render_risk_report,
)
from tests.base import TestCase

APP_DESC = Path(__file__).resolve().parents[2] / "app_desc.yaml"
# 蓝鲸 PaaS / Heroku 对 process type 的硬限制
PAAS_PROC_TYPE_MAX_LENGTH = 12


class TestAICeleryQueueIsolation(TestCase):
    """校验 AI 队列拆分：标题共用，重能力独立，助手 Message Task 仍走 default。"""

    def test_title_uses_shared_queue_with_rate_limit(self):
        self.assertEqual(generate_analyse_report_title.queue, RiskAICeleryQueue.TITLE)
        self.assertEqual(generate_analyse_report_title.rate_limit, settings.AI_TITLE_TASK_RATE_LIMIT)
        self.assertEqual(generate_conversation_title.queue, RiskAICeleryQueue.TITLE)
        self.assertEqual(generate_conversation_title.rate_limit, settings.AI_TITLE_TASK_RATE_LIMIT)
        self.assertEqual(generate_conversation_title.queue, generate_analyse_report_title.queue)
        self.assertEqual(generate_conversation_title.time_limit, settings.DEFAULT_CACHE_LOCK_TIMEOUT)
        self.assertEqual(generate_conversation_title.time_limit, generate_analyse_report_title.time_limit)
        self.assertTrue(generate_conversation_title.acks_late)

    def test_single_risk_analyse_has_dedicated_queue(self):
        self.assertEqual(render_template.queue, RiskAICeleryQueue.SINGLE_ANALYSE)
        self.assertEqual(render_template.rate_limit, settings.RISK_SINGLE_ANALYSE_TASK_RATE_LIMIT)

    def test_multi_risk_analyse_has_dedicated_queue(self):
        self.assertEqual(generate_analyse_report.queue, RiskAICeleryQueue.MULTI_ANALYSE)
        self.assertEqual(generate_analyse_report.rate_limit, settings.RISK_MULTI_ANALYSE_TASK_RATE_LIMIT)

    def test_preview_and_orchestrator_stay_on_risk_report(self):
        self.assertEqual(render_ai_variable.queue, RiskAICeleryQueue.RISK_REPORT)
        self.assertEqual(render_risk_report.queue, RiskAICeleryQueue.RISK_REPORT)
        self.assertEqual(render_ai_variable.rate_limit, settings.RENDER_TASK_RATE_LIMIT)
        self.assertEqual(render_risk_report.rate_limit, settings.RENDER_TASK_RATE_LIMIT)

    def test_title_single_and_multi_queues_are_distinct(self):
        self.assertEqual(
            {
                generate_analyse_report_title.queue,
                generate_conversation_title.queue,
                render_template.queue,
                generate_analyse_report.queue,
                render_risk_report.queue,
            },
            {
                RiskAICeleryQueue.TITLE,
                RiskAICeleryQueue.SINGLE_ANALYSE,
                RiskAICeleryQueue.MULTI_ANALYSE,
                RiskAICeleryQueue.RISK_REPORT,
            },
        )

    def test_message_tasks_stay_off_isolated_ai_queues(self):
        isolated = {
            RiskAICeleryQueue.TITLE,
            RiskAICeleryQueue.SINGLE_ANALYSE,
            RiskAICeleryQueue.MULTI_ANALYSE,
            RiskAICeleryQueue.RISK_REPORT,
        }
        for task in (
            execute_system_selection,
            execute_user_intent,
            execute_log_search,
        ):
            with self.subTest(task=task.name):
                queue = getattr(task, "queue", None)
                self.assertNotIn(queue, isolated)
                self.assertIn(queue, {None, "celery", "default"})

    def test_app_desc_declares_merged_ai_worker_and_drops_risk_render(self):
        """合并后所有 AI 队列由单一 audit-ai 进程消费，不再有独立 Worker。"""
        content = APP_DESC.read_text()
        # audit-ai 进程存在且监听全部 4 个队列
        self.assertIn("audit-ai:", content)
        self.assertIn("ai_title", content)
        self.assertIn("risk_single_analyse", content)
        self.assertIn("risk_multi_analyse", content)
        self.assertIn("risk_report", content)
        self.assertIn("BKAPP_AUDIT_AI_CONCURRENCY", content)
        # 旧的独立 Worker 进程已移除
        self.assertNotIn("risk-single:", content)
        self.assertNotIn("risk-multi:", content)
        self.assertNotIn("ai-title:", content)
        self.assertNotIn("risk-report:", content)
        self.assertNotIn("-Q risk_render", content)
        self.assertNotIn("risk-render:", content)

    def test_app_desc_process_types_fit_paas_length_limit(self):
        desc = yaml.safe_load(APP_DESC.read_text())
        oversize = []
        for module_name, module in desc["modules"].items():
            for proc_type in module.get("processes") or {}:
                if len(proc_type) > PAAS_PROC_TYPE_MAX_LENGTH:
                    oversize.append(f"{module_name}.{proc_type}({len(proc_type)})")
        self.assertEqual(
            oversize,
            [],
            msg=(
                "processes: Invalid proc type, cannot be longer than "
                f"{PAAS_PROC_TYPE_MAX_LENGTH} characters: {oversize}"
            ),
        )

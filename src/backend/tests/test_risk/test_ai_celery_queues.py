"""AI Celery workload 路由契约。"""

from pathlib import Path

import yaml
from django.conf import settings

from services.web.ai_assistant.tasks.audit_analysis import (
    execute_log_analysis,
    generate_log_analysis_title,
)
from services.web.ai_assistant.tasks.audit_search import (
    execute_log_search,
    execute_system_selection,
    execute_user_intent,
)
from services.web.ai_assistant.tasks.audit_statistics import (
    generate_ai_statistics,
    generate_field_statistics,
)
from services.web.ai_assistant.tasks.conversation import generate_conversation_title
from services.web.common.ai import AIAgentTask, AIWorkloadQueue
from services.web.risk.report.renderer import render_template
from services.web.risk.tasks import (
    generate_analyse_report,
    generate_analyse_report_title,
    render_ai_variable,
    render_risk_report,
)
from tests.base import TestCase

APP_DESC = Path(__file__).resolve().parents[2] / "app_desc.yaml"
PAAS_PROC_TYPE_MAX_LENGTH = 12


class TestAICeleryWorkloadRouting(TestCase):
    """队列只表达执行特征，不与 Agent Code 或业务类型一一绑定。"""

    def test_non_agent_tasks_use_general_default_workload(self):
        for task in (
            execute_system_selection,
            execute_log_search,
            generate_field_statistics,
            render_risk_report,
        ):
            with self.subTest(task=task.name):
                self.assertIn(getattr(task, "queue", None), {None, "celery", "default"})

    def test_regular_agent_tasks_share_ai_default_workload(self):
        for task in (
            execute_user_intent,
            generate_analyse_report,
            generate_analyse_report_title,
            generate_conversation_title,
            generate_log_analysis_title,
            render_ai_variable,
            execute_log_analysis,
            generate_ai_statistics,
        ):
            with self.subTest(task=task.name):
                self.assertEqual(task.queue, AIWorkloadQueue.DEFAULT)
                self.assertIsNone(task.rate_limit)
                self.assertIsInstance(task, AIAgentTask)

    def test_single_risk_report_keeps_legacy_queue_and_rate_limit(self):
        self.assertEqual(render_template.queue, AIWorkloadQueue.RISK_SINGLE)
        self.assertEqual(render_template.rate_limit, settings.RISK_SINGLE_ANALYSE_TASK_RATE_LIMIT)
        self.assertNotIsInstance(render_template, AIAgentTask)
        self.assertNotEqual(generate_analyse_report.queue, render_template.queue)

    def test_app_desc_workers_consume_workload_queues(self):
        desc = yaml.safe_load(APP_DESC.read_text())
        processes = desc["modules"]["api"]["processes"]
        self.assertIn("ai-default", processes)
        self.assertIn("risk-single", processes)
        self.assertIn(f"-Q {AIWorkloadQueue.DEFAULT}", processes["ai-default"]["command"])
        self.assertIn(f"-Q {AIWorkloadQueue.RISK_SINGLE}", processes["risk-single"]["command"])
        self.assertNotIn(AIWorkloadQueue.RISK_SINGLE, processes["ai-default"]["command"])
        self.assertNotIn(AIWorkloadQueue.DEFAULT, processes["risk-single"]["command"])
        self.assertNotIn("audit-ai", processes)
        self.assertNotIn("ai-batch", processes)

    def test_app_desc_process_types_fit_paas_length_limit(self):
        desc = yaml.safe_load(APP_DESC.read_text())
        oversize = []
        for module_name, module in desc["modules"].items():
            for proc_type in module.get("processes") or {}:
                if len(proc_type) > PAAS_PROC_TYPE_MAX_LENGTH:
                    oversize.append(f"{module_name}.{proc_type}({len(proc_type)})")
        self.assertEqual(oversize, [])

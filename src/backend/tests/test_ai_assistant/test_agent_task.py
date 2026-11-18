import time
from unittest import mock

from blueapps.core.celery import celery_app
from celery.exceptions import Retry
from django.conf import settings
from django.test import SimpleTestCase, override_settings

from api.bk_plugins_ai_agent.exceptions import AgentRateLimited
from api.constants import AIAgentCode
from services.web.common.ai import AIAgentTask


@celery_app.task(bind=True, base=AIAgentTask, name="tests.ai_assistant.rate_limited_agent")
def rate_limited_agent(self):
    raise AgentRateLimited(AIAgentCode.USER_INTENT)


class AIAgentTaskTest(SimpleTestCase):
    def test_default_retry_budget_is_ten(self):
        self.assertEqual(settings.AI_AGENT_TASK_MAX_RETRIES, 10)

    @override_settings(
        AI_AGENT_TASK_MAX_RETRIES=4,
        AI_AGENT_TASK_RETRY_BASE_SECONDS=2,
        AI_AGENT_TASK_RETRY_MAX_SECONDS=30,
        AI_AGENT_TASK_RETRY_JITTER_SECONDS=1,
        AI_AGENT_TASK_RETRY_DEADLINE_SECONDS=120,
    )
    @mock.patch("services.web.common.ai.random.uniform", return_value=0.5)
    def test_rate_limit_uses_delayed_retry_with_backoff_and_jitter(self, _uniform):
        rate_limited_agent.push_request(id="task-id", retries=2, headers={})
        try:
            with mock.patch.object(rate_limited_agent, "retry", side_effect=Retry()) as retry:
                with self.assertRaises(Retry):
                    rate_limited_agent()
        finally:
            rate_limited_agent.pop_request()

        self.assertEqual(retry.call_args.kwargs["countdown"], 8.5)
        self.assertEqual(retry.call_args.kwargs["max_retries"], 4)
        self.assertIn("ai_agent_retry_started_at", retry.call_args.kwargs["headers"])

    @override_settings(AI_AGENT_TASK_MAX_RETRIES=2, AI_AGENT_TASK_RETRY_DEADLINE_SECONDS=60)
    def test_retry_stops_after_max_retries(self):
        rate_limited_agent.push_request(id="task-id", retries=2, headers={})
        try:
            with mock.patch.object(rate_limited_agent, "retry") as retry, self.assertRaises(AgentRateLimited):
                rate_limited_agent()
        finally:
            rate_limited_agent.pop_request()

        retry.assert_not_called()

    @override_settings(
        AI_AGENT_TASK_MAX_RETRIES=4,
        AI_AGENT_TASK_RETRY_BASE_SECONDS=2,
        AI_AGENT_TASK_RETRY_MAX_SECONDS=30,
        AI_AGENT_TASK_RETRY_JITTER_SECONDS=0,
        AI_AGENT_TASK_RETRY_DEADLINE_SECONDS=10,
    )
    def test_retry_stops_when_next_delivery_would_exceed_deadline(self):
        headers = {"ai_agent_retry_started_at": time.time() - 9}
        rate_limited_agent.push_request(id="task-id", retries=1, headers=headers)
        try:
            with mock.patch.object(rate_limited_agent, "retry") as retry, self.assertRaises(AgentRateLimited):
                rate_limited_agent()
        finally:
            rate_limited_agent.pop_request()

        retry.assert_not_called()

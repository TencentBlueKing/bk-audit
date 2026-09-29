import os
from unittest import mock

from client_throttler.exceptions import RetryTimeout, TooManyRequests, TooManyRetries
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings

from api.bk_plugins_ai_agent.default import ChatCompletion as GenericChatCompletion
from api.bk_plugins_ai_agent.exceptions import AgentRateLimited
from api.bk_plugins_ai_agent.rate_limiter import AgentRateLimiter
from api.bk_plugins_ai_audit_analyse.default import (
    ChatCompletion as AnalyseChatCompletion,
)
from api.bk_plugins_ai_audit_report.default import (
    ChatCompletion as ReportChatCompletion,
)
from api.constants import AIAgentCode


class AgentRateLimiterTest(SimpleTestCase):
    def test_phase_two_agent_codes_extend_common_enum(self):
        self.assertEqual(len(AIAgentCode), 7)
        self.assertEqual(AIAgentCode.AUDIT_LOG_STATISTICS.value, "bp-ai-log-stats")
        self.assertEqual(AIAgentCode.AUDIT_LOG_ANALYSIS.value, "bp-ai-log-analyse")

    def test_migrated_agent_limits_keep_legacy_defaults(self):
        cases = (
            (AIAgentCode.AUDIT_REPORT, "BKAPP_RENDER_TASK_RATE_LIMIT"),
            (AIAgentCode.ALS_TITLE_SUM, "BKAPP_AI_TITLE_TASK_RATE_LIMIT"),
            (AIAgentCode.AUDIT_ANALYSE, "BKAPP_RISK_MULTI_ANALYSE_TASK_RATE_LIMIT"),
        )
        global_default = os.getenv("BKAPP_AI_AGENT_DEFAULT_RATE_LIMIT", "").strip()

        for agent_code, legacy_env_name in cases:
            with self.subTest(agent_code=agent_code):
                expected = os.getenv(
                    f"BKAPP_AI_{agent_code.name}_RATE_LIMIT",
                    global_default or os.getenv(legacy_env_name, "10/m"),
                ).strip()
                self.assertEqual(settings.AI_AGENT_RATE_LIMITS[agent_code.value]["rate"], expected)

    @override_settings(
        AI_AGENT_RATE_LIMITS={
            AIAgentCode.USER_INTENT.value: {"rate": "2/s", "max_wait_seconds": 0.5},
            AIAgentCode.RISK_SEARCH.value: {"rate": "3/s", "max_wait_seconds": 1.0},
        }
    )
    @mock.patch("api.bk_plugins_ai_agent.rate_limiter.Throttler")
    def test_each_agent_uses_an_isolated_redis_key(self, throttler_cls):
        limiter = AgentRateLimiter()

        limiter.acquire(AIAgentCode.USER_INTENT)
        limiter.acquire(AIAgentCode.RISK_SEARCH)

        configs = [call.args[0] for call in throttler_cls.call_args_list]
        self.assertEqual(
            [config.key for config in configs], [AIAgentCode.USER_INTENT.value, AIAgentCode.RISK_SEARCH.value]
        )
        self.assertEqual([config.rate for config in configs], ["2/s", "3/s"])
        self.assertEqual([config.max_retry_duration for config in configs], [0.5, 1.0])
        self.assertTrue(all(config.enable_sleep_wait for config in configs))

    @override_settings(AI_AGENT_RATE_LIMITS={AIAgentCode.USER_INTENT.value: {"rate": "1/s", "max_wait_seconds": 0.1}})
    @mock.patch("api.bk_plugins_ai_agent.rate_limiter.Throttler")
    def test_throttler_rejections_are_converted_to_public_rate_limit_error(self, throttler_cls):
        errors = (
            TooManyRequests(),
            TooManyRetries("request", 2),
            RetryTimeout("request", 1.0, 2.0),
        )
        for error in errors:
            with self.subTest(error=error.__class__.__name__):
                throttler_cls.return_value.wait.side_effect = error
                with self.assertRaises(AgentRateLimited) as context:
                    AgentRateLimiter().acquire(AIAgentCode.USER_INTENT)

                self.assertEqual(context.exception.agent_code, AIAgentCode.USER_INTENT)
                self.assertEqual(context.exception.STATUS_CODE, 429)
                self.assertEqual(context.exception.render_data()["agent_code"], AIAgentCode.USER_INTENT.value)

    @override_settings(AI_AGENT_RATE_LIMITS={})
    @mock.patch("api.bk_plugins_ai_agent.rate_limiter.Throttler")
    def test_unconfigured_agent_disables_rate_limit(self, throttler_cls):
        self.assertEqual(AgentRateLimiter().acquire(AIAgentCode.USER_INTENT), 0.0)
        throttler_cls.assert_not_called()

    @mock.patch("api.bk_plugins_ai_agent.rate_limiter.Throttler")
    def test_enabled_rate_limit_requires_positive_max_wait(self, throttler_cls):
        for max_wait_seconds in (0, -1, "invalid", "nan", "inf"):
            with self.subTest(max_wait_seconds=max_wait_seconds), override_settings(
                AI_AGENT_RATE_LIMITS={
                    AIAgentCode.USER_INTENT.value: {
                        "rate": "1/s",
                        "max_wait_seconds": max_wait_seconds,
                    }
                }
            ):
                with self.assertRaises(ImproperlyConfigured):
                    AgentRateLimiter().acquire(AIAgentCode.USER_INTENT)

        throttler_cls.assert_not_called()


class AgentClientRateLimitTest(SimpleTestCase):
    @mock.patch("api.bk_plugins_ai_agent.default.BkApiResource.perform_request", return_value="ok")
    @mock.patch("api.bk_plugins_ai_agent.default.agent_rate_limiter.acquire", return_value=0.0)
    def test_regular_clients_share_limiter_while_legacy_report_client_bypasses_it(self, acquire, perform_request):
        clients = (
            (GenericChatCompletion(), {"agent_code": AIAgentCode.USER_INTENT}),
            (ReportChatCompletion(), {}),
            (AnalyseChatCompletion(), {}),
        )

        for client, request_data in clients:
            with self.subTest(client=client.__class__.__module__):
                self.assertEqual(client.perform_request(request_data), "ok")
                self.assertIsNone(client._current_agent_code)

        self.assertEqual(
            [call.args[0] for call in acquire.call_args_list],
            [AIAgentCode.USER_INTENT, AIAgentCode.AUDIT_ANALYSE],
        )
        self.assertEqual(perform_request.call_count, 3)

    @mock.patch("api.bk_plugins_ai_agent.default.BkApiResource.perform_request", return_value="ok")
    @mock.patch("api.bk_plugins_ai_agent.default.agent_rate_limiter.acquire", return_value=0.0)
    def test_legacy_report_client_can_opt_in_for_regular_ai_workloads(self, acquire, perform_request):
        client = ReportChatCompletion()

        self.assertEqual(client.request(_enable_agent_rate_limit=True), "ok")

        acquire.assert_called_once_with(AIAgentCode.AUDIT_REPORT)
        self.assertNotIn("_enable_agent_rate_limit", perform_request.call_args.args[0])
        self.assertIsNone(client._current_agent_code)

    @mock.patch("api.bk_plugins_ai_agent.default.BkApiResource.perform_request", return_value="ok")
    @mock.patch("api.bk_plugins_ai_agent.default.agent_rate_limiter.acquire", return_value=0.0)
    def test_regular_client_cannot_opt_out_of_global_rate_limit(self, acquire, perform_request):
        client = GenericChatCompletion()

        self.assertEqual(
            client.request(agent_code=AIAgentCode.USER_INTENT, _enable_agent_rate_limit=False),
            "ok",
        )

        acquire.assert_called_once_with(AIAgentCode.USER_INTENT)
        self.assertNotIn("_enable_agent_rate_limit", perform_request.call_args.args[0])
        self.assertIsNone(client._current_agent_code)

    @mock.patch("api.bk_plugins_ai_agent.default.BkApiResource.perform_request")
    @mock.patch(
        "api.bk_plugins_ai_agent.default.agent_rate_limiter.acquire",
        side_effect=AgentRateLimited(AIAgentCode.USER_INTENT),
    )
    def test_rate_limit_rejection_happens_before_http_request(self, acquire, perform_request):
        client = GenericChatCompletion()
        with self.assertRaises(AgentRateLimited):
            client.perform_request({"agent_code": AIAgentCode.USER_INTENT})

        acquire.assert_called_once_with(AIAgentCode.USER_INTENT)
        perform_request.assert_not_called()
        self.assertIsNone(client._current_agent_code)

    @mock.patch("api.bk_plugins_ai_agent.default.BkApiResource.perform_request", side_effect=RuntimeError("failed"))
    @mock.patch("api.bk_plugins_ai_agent.default.agent_rate_limiter.acquire", return_value=0.0)
    def test_downstream_failure_clears_agent_context(self, acquire, perform_request):
        client = GenericChatCompletion()

        with self.assertRaises(RuntimeError):
            client.perform_request({"agent_code": AIAgentCode.USER_INTENT})

        acquire.assert_called_once_with(AIAgentCode.USER_INTENT)
        perform_request.assert_called_once()
        self.assertIsNone(client._current_agent_code)

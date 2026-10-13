import os
from unittest import mock

from bk_resource import api as bk_api
from bk_resource.exceptions import APIRequestError
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
from config import default as default_settings


class CapturingRequestLogHandler:
    """捕获 Resource 公共调用入口产生的请求日志。"""

    records = []

    def __init__(self, resource_name, start_time, end_time, request_data, response_data):
        self.record_data = {
            "resource_name": resource_name,
            "request_data": request_data,
            "response_data": response_data,
        }

    def record(self):
        """保存本次请求日志，供集成契约断言。"""

        self.records.append(self.record_data)


class AgentRateLimiterTest(SimpleTestCase):
    def test_phase_two_agent_codes_extend_common_enum(self):
        self.assertEqual(len(AIAgentCode), 7)
        self.assertEqual(AIAgentCode.AUDIT_LOG_STATISTICS.value, "bp-ai-log-stats")
        self.assertEqual(AIAgentCode.AUDIT_LOG_ANALYSIS.value, "bp-ai-log-analyse")

    def test_all_agent_codes_have_a_safe_default_rate_limit(self):
        configured_default = os.getenv("BKAPP_AI_AGENT_DEFAULT_RATE_LIMIT", "").strip() or "10/m"

        self.assertEqual(settings.AI_AGENT_DEFAULT_RATE_LIMIT, configured_default)
        self.assertEqual(set(settings.AI_AGENT_RATE_LIMITS), {agent_code.value for agent_code in AIAgentCode})

    def test_rate_limit_configuration_precedence_keeps_legacy_compatibility(self):
        resolver = getattr(default_settings, "_resolve_ai_agent_rate_limit", None)
        self.assertIsNotNone(resolver)

        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(resolver(AIAgentCode.AUDIT_REPORT), "10/m")

        with mock.patch.dict(os.environ, {"BKAPP_RENDER_TASK_RATE_LIMIT": "4/m"}, clear=True):
            self.assertEqual(resolver(AIAgentCode.AUDIT_REPORT), "4/m")

        with mock.patch.dict(
            os.environ,
            {
                "BKAPP_RENDER_TASK_RATE_LIMIT": "4/m",
                "BKAPP_AI_AGENT_DEFAULT_RATE_LIMIT": "20/m",
            },
            clear=True,
        ):
            self.assertEqual(resolver(AIAgentCode.AUDIT_REPORT), "20/m")

        with mock.patch.dict(
            os.environ,
            {
                "BKAPP_AI_AGENT_DEFAULT_RATE_LIMIT": "20/m",
                "BKAPP_AI_AUDIT_REPORT_RATE_LIMIT": "30/m",
            },
            clear=True,
        ):
            self.assertEqual(resolver(AIAgentCode.AUDIT_REPORT), "30/m")

        with mock.patch.dict(os.environ, {"BKAPP_AI_AUDIT_REPORT_RATE_LIMIT": ""}, clear=True):
            self.assertEqual(resolver(AIAgentCode.AUDIT_REPORT), "")

    def test_legacy_agent_specific_environment_variables_remain_compatible(self):
        cases = (
            (AIAgentCode.AUDIT_REPORT, "BKAPP_RENDER_TASK_RATE_LIMIT"),
            (AIAgentCode.ALS_TITLE_SUM, "BKAPP_AI_TITLE_TASK_RATE_LIMIT"),
            (AIAgentCode.AUDIT_ANALYSE, "BKAPP_RISK_MULTI_ANALYSE_TASK_RATE_LIMIT"),
        )
        global_override = os.getenv("BKAPP_AI_AGENT_DEFAULT_RATE_LIMIT", "").strip()

        for agent_code, legacy_env_name in cases:
            with self.subTest(agent_code=agent_code):
                agent_env_name = f"BKAPP_AI_{agent_code.name}_RATE_LIMIT"
                expected = (
                    os.environ[agent_env_name].strip()
                    if agent_env_name in os.environ
                    else global_override or os.getenv(legacy_env_name, "").strip() or "10/m"
                )
                self.assertEqual(settings.AI_AGENT_RATE_LIMITS[agent_code.value]["rate"], expected)

    @override_settings(
        AI_AGENT_RATE_LIMITS={
            AIAgentCode.AUDIT_REPORT.value: {"rate": "1/s", "max_wait_seconds": 0.1},
            AIAgentCode.RISK_SEARCH.value: {"rate": "2/s", "max_wait_seconds": 0.2},
            AIAgentCode.ALS_TITLE_SUM.value: {"rate": "3/s", "max_wait_seconds": 0.3},
            AIAgentCode.AUDIT_ANALYSE.value: {"rate": "4/s", "max_wait_seconds": 0.4},
            AIAgentCode.USER_INTENT.value: {"rate": "5/s", "max_wait_seconds": 0.5},
            AIAgentCode.AUDIT_LOG_STATISTICS.value: {"rate": "6/s", "max_wait_seconds": 0.6},
            AIAgentCode.AUDIT_LOG_ANALYSIS.value: {"rate": "7/s", "max_wait_seconds": 0.7},
        }
    )
    @mock.patch("api.bk_plugins_ai_agent.rate_limiter.Throttler")
    def test_all_agent_codes_use_isolated_redis_keys(self, throttler_cls):
        limiter = AgentRateLimiter()

        for agent_code in AIAgentCode:
            limiter.acquire(agent_code)

        configs = [call.args[0] for call in throttler_cls.call_args_list]
        self.assertEqual(
            [config.key for config in configs],
            [
                AIAgentCode.AUDIT_REPORT.value,
                AIAgentCode.RISK_SEARCH.value,
                AIAgentCode.ALS_TITLE_SUM.value,
                AIAgentCode.AUDIT_ANALYSE.value,
                AIAgentCode.USER_INTENT.value,
                AIAgentCode.AUDIT_LOG_STATISTICS.value,
                AIAgentCode.AUDIT_LOG_ANALYSIS.value,
            ],
        )
        self.assertEqual([config.rate for config in configs], ["1/s", "2/s", "3/s", "4/s", "5/s", "6/s", "7/s"])
        self.assertEqual([config.max_retry_duration for config in configs], [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7])
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
    def setUp(self):
        CapturingRequestLogHandler.records.clear()

    @mock.patch("api.bk_plugins_ai_agent.default.BkApiResource.perform_request", return_value="ok")
    @mock.patch("api.bk_plugins_ai_agent.default.agent_rate_limiter.acquire", return_value=0.0)
    def test_generic_client_applies_limiter_to_all_agent_codes(self, acquire, perform_request):
        client = GenericChatCompletion()

        for agent_code in AIAgentCode:
            with self.subTest(agent_code=agent_code):
                self.assertEqual(client.perform_request({"agent_code": agent_code}), "ok")
                self.assertIsNone(client._current_agent_code)

        self.assertEqual([call.args[0] for call in acquire.call_args_list], list(AIAgentCode))
        self.assertEqual(perform_request.call_count, len(AIAgentCode))

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

    @mock.patch("api.bk_plugins_ai_agent.default.BkApiResource.perform_request", return_value="agent-success-body")
    @mock.patch("api.bk_plugins_ai_agent.default.agent_rate_limiter.acquire", return_value=0.0)
    def test_public_agent_interface_records_request_and_success_response(self, acquire, _perform_request):
        payload = {
            "agent_code": AIAgentCode.USER_INTENT,
            "input": "diagnostic-request-body",
            "chat_history": [],
            "execute_kwargs": {"stream": False},
        }

        with mock.patch(
            "bk_resource.base.bk_resource_settings.REQUEST_LOG_HANDLER",
            CapturingRequestLogHandler,
        ):
            result = bk_api.bk_plugins_ai_agent.chat_completion(**payload)

        self.assertEqual(result, "agent-success-body")
        acquire.assert_called_once_with(AIAgentCode.USER_INTENT)
        self.assertEqual(len(CapturingRequestLogHandler.records), 1)
        record = CapturingRequestLogHandler.records[0]
        self.assertEqual(record["resource_name"], "api.bk_plugins_ai_agent.default.ChatCompletion")
        self.assertEqual(record["request_data"]["kwargs"], payload)
        self.assertEqual(record["response_data"], "agent-success-body")

    @mock.patch(
        "api.bk_plugins_ai_agent.default.BkApiResource.perform_request",
        side_effect=APIRequestError(result={"message": "diagnostic-upstream-error"}),
    )
    @mock.patch("api.bk_plugins_ai_agent.default.agent_rate_limiter.acquire", return_value=0.0)
    def test_public_agent_interface_records_failure_body(self, acquire, _perform_request):
        with mock.patch(
            "bk_resource.base.bk_resource_settings.REQUEST_LOG_HANDLER",
            CapturingRequestLogHandler,
        ), self.assertRaises(APIRequestError):
            bk_api.bk_plugins_ai_agent.chat_completion(
                agent_code=AIAgentCode.AUDIT_LOG_ANALYSIS,
                input="diagnostic-failure-request",
                chat_history=[],
                execute_kwargs={"stream": False},
            )

        acquire.assert_called_once_with(AIAgentCode.AUDIT_LOG_ANALYSIS)
        self.assertEqual(len(CapturingRequestLogHandler.records), 1)
        self.assertEqual(CapturingRequestLogHandler.records[0]["response_data"], "diagnostic-upstream-error")

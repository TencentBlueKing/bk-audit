"""日志分析报告业务 Task 的 Agent 协议与平台生命周期测试。"""

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

import yaml
from bk_resource import api
from celery.exceptions import Ignore, Retry
from django.conf import settings
from django.test import override_settings

from api.bk_plugins_ai_agent.agui import AGUIStreamResponse
from api.constants import AIAgentCode
from services.web.ai_assistant import exceptions as ai_assistant_exceptions
from services.web.ai_assistant.constants import (
    AnalysisMode,
    AttachmentErrorCode,
    AttachmentType,
    ExecutionStatus,
    PlatformStreamEvent,
)
from services.web.ai_assistant.exceptions import (
    AIAssistantException,
    AttachmentOutputValidationError,
    AttachmentSnapshotValidationError,
    LogAnalysisTimeout,
)
from services.web.ai_assistant.handlers import attachment_handler_registry
from services.web.ai_assistant.handlers.audit_analysis import AIAnalysisHandler
from services.web.ai_assistant.models import Attachment
from services.web.ai_assistant.schemas.audit_analysis import (
    AIAnalysisContextSchema,
    AIAnalysisInputSchema,
)
from services.web.ai_assistant.services.attachment_execution import AttachmentExecution
from services.web.ai_assistant.streaming import RedisLiveStore
from services.web.ai_assistant.tasks.audit_analysis import (
    build_agent_input,
    execute_log_analysis,
)
from tests.test_ai_assistant.base import AIAssistantPlatformTestCase, make_condition
from tests.test_ai_assistant.test_attachment_task import invoke_task


class AIAnalysisTaskTest(AIAssistantPlatformTestCase):
    def setUp(self):
        super().setUp()
        original_handler = attachment_handler_registry.unregister(AttachmentType.AI_ANALYSIS)
        self.addCleanup(self._restore_handler, original_handler)
        self.addCleanup(self._clear_streams)
        self.handler = attachment_handler_registry.register(AIAnalysisHandler())
        self.source_message = self.create_log_search_message()
        self.input_data = AIAnalysisInputSchema(
            analysis_mode=AnalysisMode.CUSTOM,
            instruction="按操作人汇总风险",
        )
        self.context_data = AIAnalysisContextSchema(
            effective_instruction="按操作人汇总风险",
            search_condition=make_condition(),
            query_summary={"total": 2, "took_ms": 12, "executed_at": "2026-08-24T12:00:00+08:00"},
            username=self.user,
            namespace="bkaudit",
            timezone="Asia/Shanghai",
            language="zh-cn",
        )

    @staticmethod
    def _restore_handler(original_handler) -> None:
        """恢复测试前注册项，避免用例顺序影响生产 Handler 契约。"""

        attachment_handler_registry.unregister(AttachmentType.AI_ANALYSIS)
        if original_handler is not None:
            attachment_handler_registry.register(original_handler)

    @staticmethod
    def _clear_streams() -> None:
        """清理本类真实流式生命周期测试创建的 Redis Stream。"""

        redis_store = RedisLiveStore()
        keys = []
        for attachment_uid in Attachment.objects.values_list("uid", flat=True):
            pattern = redis_store.physical_key(f"ai_assistant:attachment_stream:{attachment_uid}:*")
            keys.extend(redis_store._client.scan_iter(match=pattern))
        if keys:
            redis_store._client.delete(*keys)

    def create_attachment(self, *, status=ExecutionStatus.PROCESSING, task_id="analysis-task") -> Attachment:
        return Attachment.objects.create(
            source_message=self.source_message,
            attachment_type=AttachmentType.AI_ANALYSIS,
            title="智能分析报告",
            status=status,
            task_id=task_id,
            input_data=self.input_data.model_dump(mode="json"),
            context_data=self.context_data.model_dump(mode="json"),
            output_data=None,
            is_stream=True,
            created_by=self.user,
            updated_by=self.user,
        )

    def make_execution(self):
        stream = mock.Mock()
        return AttachmentExecution(
            attachment=self.create_attachment(),
            input_data=self.input_data,
            context_data=self.context_data,
            _stream=stream,
        )

    @staticmethod
    def _run_cold_import(code: str, *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
        """在无当前进程模块缓存的环境中验证 Worker 冷启动导入。"""

        backend_root = Path(__file__).resolve().parents[2]
        return subprocess.run(
            [sys.executable, "manage.py", "shell", "-c", code],
            cwd=backend_root,
            env={**os.environ, **(env or {})},
            capture_output=True,
            text=True,
            check=False,
        )

    def test_audit_analysis_task_supports_cold_import(self):
        result = self._run_cold_import(
            "from services.web.ai_assistant.tasks.audit_analysis import execute_log_analysis; "
            "assert execute_log_analysis.name == 'ai_assistant.execute_log_analysis'"
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_task_package_cold_import_registers_worker_task(self):
        result = self._run_cold_import(
            "from blueapps.core.celery import celery_app; "
            "import services.web.ai_assistant.tasks; "
            "assert 'ai_assistant.execute_log_analysis' in celery_app.tasks"
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_business_timeout_precedes_celery_hard_limit(self):
        self.assertGreater(settings.AI_ASSISTANT_LOG_ANALYSIS_BUSINESS_TIMEOUT, 0)
        self.assertLess(
            settings.AI_ASSISTANT_LOG_ANALYSIS_BUSINESS_TIMEOUT,
            settings.AI_ASSISTANT_LOG_ANALYSIS_TASK_TIMEOUT,
        )

    def test_invalid_timeout_configuration_fails_during_startup(self):
        result = self._run_cold_import(
            "from django.conf import settings; settings.AI_ASSISTANT_LOG_ANALYSIS_BUSINESS_TIMEOUT",
            env={
                "BKAPP_AI_ASSISTANT_LOG_ANALYSIS_BUSINESS_TIMEOUT": "1800",
                "BKAPP_AI_ASSISTANT_LOG_ANALYSIS_TASK_TIMEOUT": "1800",
            },
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("BUSINESS_TIMEOUT", result.stdout + result.stderr)

    def test_business_timeout_uses_catchable_platform_exception(self):
        timeout_error = getattr(ai_assistant_exceptions, "LogAnalysisTimeout", None)

        self.assertIsNotNone(timeout_error)
        self.assertTrue(issubclass(timeout_error, Exception))
        self.assertTrue(issubclass(timeout_error, AIAssistantException))

    def test_business_timeout_marks_attachment_failed_and_ends_stream(self):
        attachment = self.create_attachment()
        timeout_context = mock.MagicMock()
        timeout_context.__enter__.side_effect = LogAnalysisTimeout()

        with (
            mock.patch(
                "services.web.ai_assistant.tasks.audit_analysis.Timeout",
                return_value=timeout_context,
            ) as timeout,
            mock.patch.object(
                api.bk_plugins_ai_agent,
                "agui_chat_completion",
                return_value=AGUIStreamResponse(events=(), final_content="# 不应执行"),
            ) as agent,
            self.assertRaises(LogAnalysisTimeout),
        ):
            invoke_task(execute_log_analysis, attachment=attachment)

        attachment.refresh_from_db()
        timeout.assert_called_once()
        timeout_seconds, timeout_exception = timeout.call_args.args
        self.assertEqual(timeout_seconds, settings.AI_ASSISTANT_LOG_ANALYSIS_BUSINESS_TIMEOUT)
        self.assertIsInstance(timeout_exception, LogAnalysisTimeout)
        agent.assert_not_called()
        self.assertEqual(attachment.status, ExecutionStatus.FAILED)
        self.assertEqual(attachment.error_code, LogAnalysisTimeout().code)
        self.assertEqual(attachment.error_message, "日志分析超时，请重试")
        self.assertEqual(attachment.stream_archive[-1]["event"], PlatformStreamEvent.STREAM_END)
        self.assertEqual(attachment.stream_archive[-1]["data"], {"status": ExecutionStatus.FAILED})

    def test_agent_input_is_compact_and_contains_no_preview_or_internal_identifiers(self):
        payload = json.loads(build_agent_input(self.context_data))

        self.assertEqual(set(payload), {"instruction", "context"})
        self.assertEqual(payload["instruction"], "按操作人汇总风险")
        self.assertEqual(
            set(payload["context"]),
            {"search_condition", "query_summary", "user"},
        )
        self.assertEqual(
            payload["context"]["user"],
            {"username": self.user, "timezone": "Asia/Shanghai", "language": "zh-cn"},
        )
        serialized = json.dumps(payload, ensure_ascii=False)
        for forbidden in ("samples", "columns", "sql", "message_id", "attachment_id"):
            self.assertNotIn(forbidden, serialized)

    def test_task_forwards_all_events_and_uses_only_final_content(self):
        execution = self.make_execution()
        events = [
            {"type": "TOOL_CALL_START", "toolCallId": "c1", "toolCallName": "search_logs"},
            {"type": "RUN_FINISHED", "result": {"ignored": True}},
        ]

        def agent_call(**kwargs):
            for event in events:
                kwargs["on_event"](event)
            return AGUIStreamResponse(
                events=tuple(events),
                final_content="# 结论\n\n存在异常登录。",
                final_result={"must_not_persist": True},
            )

        with mock.patch.object(api.bk_plugins_ai_agent, "agui_chat_completion", side_effect=agent_call) as agent:
            output = execute_log_analysis.run(execution)

        self.assertEqual(output.markdown, "# 结论\n\n存在异常登录。")
        self.assertEqual([call.args[0] for call in execution.stream.send.call_args_list], events)
        request = agent.call_args.kwargs
        self.assertEqual(request["agent_code"], AIAgentCode.AUDIT_LOG_ANALYSIS)
        self.assertEqual(request["user"], self.user)
        self.assertEqual(request["chat_history"], [])
        self.assertEqual(request["execute_kwargs"], {"stream": True})
        self.assertEqual(json.loads(request["input"]), json.loads(build_agent_input(self.context_data)))

    def test_agent_exception_and_invalid_final_content_propagate_to_platform(self):
        execution = self.make_execution()
        with mock.patch.object(
            api.bk_plugins_ai_agent,
            "agui_chat_completion",
            side_effect=RuntimeError("agent unavailable"),
        ):
            with self.assertRaises(RuntimeError):
                execute_log_analysis.run(execution)

        for final_content in ("", "   "):
            with self.subTest(content=final_content):
                with mock.patch.object(
                    api.bk_plugins_ai_agent,
                    "agui_chat_completion",
                    return_value=AGUIStreamResponse(events=(), final_content=final_content),
                ):
                    with self.assertRaises(AttachmentOutputValidationError) as caught:
                        execute_log_analysis.run(execution)
                self.assertIsInstance(caught.exception.__cause__, AttachmentSnapshotValidationError)
                self.assertIsNone(caught.exception.__cause__.__cause__)

    @override_settings(AI_ASSISTANT_ATTACHMENT_MARKDOWN_MAX_BYTES=16)
    def test_oversized_agent_output_is_sanitized_before_platform_logging(self):
        sentinel = "PRIVATE_REPORT_SENTINEL"
        attachment = self.create_attachment()

        with (
            mock.patch.object(
                api.bk_plugins_ai_agent,
                "agui_chat_completion",
                return_value=AGUIStreamResponse(events=(), final_content=sentinel),
            ),
            self.assertLogs("services.web.ai_assistant.tasks.base", level="ERROR") as captured,
            self.assertRaises(AttachmentOutputValidationError) as caught,
        ):
            invoke_task(execute_log_analysis, attachment=attachment)

        attachment.refresh_from_db()
        log_output = "\n".join(captured.output)
        self.assertNotIn(sentinel, log_output)
        self.assertNotIn("input_value", log_output)
        self.assertNotIn(sentinel, str(caught.exception))
        self.assertNotIn("input_value", str(caught.exception))
        self.assertIsInstance(caught.exception.__cause__, AttachmentSnapshotValidationError)
        self.assertIsNone(caught.exception.__cause__.__cause__)
        self.assertEqual(attachment.status, ExecutionStatus.FAILED)
        self.assertEqual(attachment.error_code, AttachmentErrorCode.OUTPUT_VALIDATION_FAILED)
        self.assertNotIn(sentinel, attachment.error_message)
        self.assertNotIn("input_value", attachment.error_message)
        self.assertEqual(attachment.stream_archive[-1]["event"], PlatformStreamEvent.STREAM_END)

    def test_task_celery_configuration_matches_dedicated_worker(self):
        self.assertEqual(AIAgentCode.AUDIT_LOG_ANALYSIS.value, "bp-ai-log-analyse")
        self.assertEqual(execute_log_analysis.queue, "ai_assistant_log_analysis")
        self.assertEqual(execute_log_analysis.rate_limit, settings.AI_ASSISTANT_LOG_ANALYSIS_TASK_RATE_LIMIT)
        self.assertEqual(execute_log_analysis.time_limit, settings.AI_ASSISTANT_LOG_ANALYSIS_TASK_TIMEOUT)
        self.assertTrue(execute_log_analysis.acks_late)

        with open("app_desc.yaml", encoding="utf-8") as stream:
            process = yaml.safe_load(stream)["modules"]["api"]["processes"]["ai-log-analysis"]
        self.assertIn("-Q ai_assistant_log_analysis", process["command"])
        self.assertIn("-P gevent", process["command"])
        self.assertIn("--prefetch-multiplier=1", process["command"])
        self.assertIn("BKAPP_AI_ASSISTANT_LOG_ANALYSIS_CONCURRENCY", process["command"])
        self.assertEqual(process["replicas"], 2)

    def test_retry_keeps_processing_and_flushes_current_stream(self):
        attachment = self.create_attachment()
        runtime = mock.Mock()
        with (
            mock.patch(
                "services.web.ai_assistant.services.attachment_execution.UIStreamRuntime.start",
                return_value=runtime,
            ),
            mock.patch.object(execute_log_analysis, "run", side_effect=Retry("temporary")),
            self.assertRaises(Retry),
        ):
            invoke_task(execute_log_analysis, attachment=attachment)

        attachment.refresh_from_db()
        self.assertEqual(attachment.status, ExecutionStatus.PROCESSING)
        runtime.finish_retry.assert_called_once_with()

    def test_stale_task_is_ignored_before_agent_call(self):
        attachment = self.create_attachment(status=ExecutionStatus.SUCCESS)
        with (
            mock.patch.object(api.bk_plugins_ai_agent, "agui_chat_completion") as agent,
            self.assertRaises(Ignore),
        ):
            invoke_task(execute_log_analysis, attachment=attachment)
        agent.assert_not_called()

    # 生产 Handler 契约清单复用这些真实业务用例。
    test_success_contract = test_task_forwards_all_events_and_uses_only_final_content
    test_failure_contract = test_agent_exception_and_invalid_final_content_propagate_to_platform
    test_retry_contract = test_retry_keeps_processing_and_flushes_current_stream
    test_stale_task_contract = test_stale_task_is_ignored_before_agent_call
    test_stream_success_contract = test_task_forwards_all_events_and_uses_only_final_content
    test_stream_retry_contract = test_retry_keeps_processing_and_flushes_current_stream

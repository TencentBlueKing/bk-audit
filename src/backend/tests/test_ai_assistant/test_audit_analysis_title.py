"""日志分析报告标题旁路测试。

标题生成只增强报告可读性：失败不得改变报告终态，迟到任务不得覆盖用户编辑，
重复投递通过默认标题条件更新自然幂等。
"""

from unittest import mock

from django.db import transaction

from api.bk_plugins_ai_agent.default import ChatCompletion
from api.constants import AIAgentCode
from services.web.ai_assistant.constants import (
    AI_CONVERSATION_TITLE_MAX_LENGTH,
    DEFAULT_AI_ANALYSIS_TITLE,
    AnalysisMode,
    AttachmentType,
    ExecutionStatus,
)
from services.web.ai_assistant.exceptions import AttachmentOutputValidationError
from services.web.ai_assistant.models import Attachment
from services.web.ai_assistant.schemas.audit_analysis import (
    AIAnalysisContextSchema,
    AIAnalysisInputSchema,
    AIAnalysisOutputSchema,
)
from services.web.ai_assistant.services.attachment import AttachmentService
from services.web.ai_assistant.services.attachment_execution import AttachmentExecution
from services.web.ai_assistant.services.title_agent import TitleAgentService
from services.web.ai_assistant.tasks.attachment import AttachmentExecutionTask
from services.web.ai_assistant.tasks.audit_analysis import (
    execute_log_analysis,
    generate_log_analysis_title,
)
from tests.test_ai_assistant.base import AIAssistantPlatformTestCase, make_condition


class LogAnalysisTitleTaskTest(AIAssistantPlatformTestCase):
    """验证标题任务的条件更新、失败降级和模块化 Agent 输入。"""

    def setUp(self):
        super().setUp()
        self.source_message = self.create_log_search_message()
        self.context_data = AIAnalysisContextSchema(
            effective_instruction="分析高风险操作",
            search_condition=make_condition(),
            query_summary={"total": 2, "took_ms": 12, "executed_at": "2026-08-24T12:00:00+08:00"},
            username=self.user,
            namespace="bkaudit",
            timezone="Asia/Shanghai",
            language="zh-cn",
        )
        self.attachment = Attachment.objects.create(
            source_message=self.source_message,
            attachment_type=AttachmentType.AI_ANALYSIS,
            title=DEFAULT_AI_ANALYSIS_TITLE,
            status=ExecutionStatus.SUCCESS,
            input_data={},
            context_data=self.context_data.model_dump(mode="json"),
            output_data={"markdown": "# 分析结论"},
            created_by=self.user,
            updated_by=self.user,
        )

    def test_task_has_stable_celery_name_and_ignores_result_backend(self):
        self.assertEqual(generate_log_analysis_title.name, "ai_assistant.generate_log_analysis_title")
        self.assertTrue(generate_log_analysis_title.ignore_result)
        self.assertTrue(execute_log_analysis.ignore_result)

    def test_agent_resources_do_not_collect_prompt_or_response_body(self):
        self.assertFalse(ChatCompletion.support_data_collect)

    def test_default_title_is_replaced_by_shared_title_agent(self):
        with mock.patch.object(TitleAgentService, "generate_analysis_title", return_value="高风险操作分析") as generate:
            result = generate_log_analysis_title.run(self.attachment.id)

        self.attachment.refresh_from_db()
        self.assertEqual(result, {"updated": True, "skipped": False})
        self.assertEqual(self.attachment.title, "高风险操作分析")
        generate.assert_called_once_with(
            input_text="分析高风险操作",
            username=self.user,
        )

    def test_shared_title_agent_uses_log_analysis_context(self):
        with mock.patch(
            "services.web.ai_assistant.services.title_agent.api.bk_plugins_ai_agent.chat_completion",
            return_value="高风险操作分析",
        ) as chat:
            title = TitleAgentService.generate_analysis_title(
                input_text="分析高风险操作",
                username=self.user,
            )

        self.assertEqual(title, "高风险操作分析")
        request = chat.call_args.kwargs
        self.assertEqual(request["agent_code"], AIAgentCode.ALS_TITLE_SUM)
        self.assertIn("AI审计日志分析", request["input"])
        self.assertIn("根据日志检索条件和分析要求生成审计报告", request["input"])
        self.assertIn("报告标题", request["input"])
        self.assertIn("分析高风险操作", request["input"])
        self.assertLessEqual(len(title), AI_CONVERSATION_TITLE_MAX_LENGTH)

    def test_late_or_duplicate_task_never_overwrites_existing_title(self):
        Attachment.objects.filter(id=self.attachment.id).update(title="用户自定义标题")

        with mock.patch.object(TitleAgentService, "generate_analysis_title") as generate:
            result = generate_log_analysis_title.run(self.attachment.id)

        self.attachment.refresh_from_db()
        self.assertEqual(result, {"updated": False, "skipped": True})
        self.assertEqual(self.attachment.title, "用户自定义标题")
        generate.assert_not_called()

    def test_user_edit_during_agent_call_prevents_title_update(self):
        def edit_title(**kwargs):
            Attachment.objects.filter(id=self.attachment.id).update(title="用户编辑")
            return "不应写入的标题"

        with mock.patch.object(TitleAgentService, "generate_analysis_title", side_effect=edit_title):
            result = generate_log_analysis_title.run(self.attachment.id)

        self.attachment.refresh_from_db()
        self.assertEqual(result, {"updated": False, "skipped": False})
        self.assertEqual(self.attachment.title, "用户编辑")

    def test_title_generation_does_not_depend_on_report_status(self):
        """排队中或失败的报告也有标题，标题任务不更改正文状态。"""

        for status in (ExecutionStatus.PROCESSING, ExecutionStatus.FAILED):
            with self.subTest(status=status):
                Attachment.objects.filter(id=self.attachment.id).update(status=status, title=DEFAULT_AI_ANALYSIS_TITLE)
                with mock.patch.object(TitleAgentService, "generate_analysis_title", return_value="分析标题"):
                    result = generate_log_analysis_title.run(self.attachment.id)
                self.attachment.refresh_from_db()
                self.assertEqual(result, {"updated": True, "skipped": False})
                self.assertEqual(self.attachment.status, status)
                self.assertEqual(self.attachment.title, "分析标题")

    def test_duplicate_delivery_updates_only_once(self):
        with mock.patch.object(TitleAgentService, "generate_analysis_title", return_value="高风险操作分析") as generate:
            first = generate_log_analysis_title.run(self.attachment.id)
            second = generate_log_analysis_title.run(self.attachment.id)

        self.assertEqual(first, {"updated": True, "skipped": False})
        self.assertEqual(second, {"updated": False, "skipped": True})
        generate.assert_called_once()

    def test_analysis_title_uses_shared_length_limit(self):
        max_length = AI_CONVERSATION_TITLE_MAX_LENGTH
        with mock.patch(
            "services.web.ai_assistant.services.title_agent.api.bk_plugins_ai_agent.chat_completion",
            return_value="超" * (max_length + 10),
        ):
            title = TitleAgentService.generate_analysis_title(
                input_text="分析高风险操作",
                username=self.user,
            )

        self.assertEqual(title, "超" * max_length)

    def test_missing_attachment_is_skipped(self):
        with mock.patch.object(TitleAgentService, "generate_analysis_title") as generate:
            result = generate_log_analysis_title.run(self.attachment.id + 999)

        self.assertEqual(result, {"updated": False, "skipped": True})
        generate.assert_not_called()

    def test_non_analysis_attachment_is_skipped(self):
        Attachment.objects.filter(id=self.attachment.id).update(attachment_type=AttachmentType.FIELD_STATISTICS)

        with mock.patch.object(TitleAgentService, "generate_analysis_title") as generate:
            result = generate_log_analysis_title.run(self.attachment.id)

        self.assertEqual(result, {"updated": False, "skipped": True})
        generate.assert_not_called()

    def test_agent_failure_keeps_default_title_without_logging_input(self):
        private_input = "PRIVATE_ANALYSIS_INSTRUCTION"
        self.context_data = self.context_data.model_copy(update={"effective_instruction": private_input})
        Attachment.objects.filter(id=self.attachment.id).update(context_data=self.context_data.model_dump(mode="json"))
        with mock.patch.object(
            TitleAgentService,
            "generate_analysis_title",
            side_effect=RuntimeError(private_input),
        ), self.assertLogs(
            "services.web.ai_assistant.tasks.audit_analysis",
            level="WARNING",
        ) as captured:
            result = generate_log_analysis_title.run(self.attachment.id)

        self.attachment.refresh_from_db()
        self.assertEqual(result, {"updated": False, "skipped": False})
        self.assertEqual(self.attachment.title, DEFAULT_AI_ANALYSIS_TITLE)
        self.assertNotIn(private_input, "\n".join(captured.output))

    def test_empty_agent_title_keeps_default_title(self):
        with mock.patch.object(TitleAgentService, "generate_analysis_title", return_value=""), self.assertLogs(
            "services.web.ai_assistant.tasks.audit_analysis",
            level="WARNING",
        ) as captured:
            result = generate_log_analysis_title.run(self.attachment.id)

        self.attachment.refresh_from_db()
        self.assertEqual(result, {"updated": False, "skipped": False})
        self.assertEqual(self.attachment.title, DEFAULT_AI_ANALYSIS_TITLE)
        self.assertIn("标题生成结果为空", "\n".join(captured.output))

    def test_default_mode_title_uses_resolved_default_instruction(self):
        self.context_data = self.context_data.model_copy(update={"effective_instruction": "默认分析模板"})
        Attachment.objects.filter(id=self.attachment.id).update(context_data=self.context_data.model_dump(mode="json"))

        with mock.patch.object(TitleAgentService, "generate_analysis_title", return_value="默认日志分析") as generate:
            generate_log_analysis_title.run(self.attachment.id)

        generate.assert_called_once_with(
            input_text="默认分析模板",
            username=self.user,
        )


class LogAnalysisTitleDispatchTest(AIAssistantPlatformTestCase):
    """创建提交后并行派发标题，正文结束不再重复派发。"""

    def setUp(self):
        super().setUp()
        source_message = self.create_log_search_message()
        self.context_data = AIAnalysisContextSchema(
            effective_instruction="按操作人汇总风险",
            search_condition=make_condition(),
            query_summary={"total": 2, "took_ms": 12, "executed_at": "2026-08-24T12:00:00+08:00"},
            username=self.user,
            namespace="bkaudit",
            timezone="Asia/Shanghai",
            language="zh-cn",
        )
        attachment = Attachment.objects.create(
            source_message=source_message,
            attachment_type=AttachmentType.AI_ANALYSIS,
            title=DEFAULT_AI_ANALYSIS_TITLE,
            status=ExecutionStatus.PROCESSING,
            task_id="analysis-task",
            input_data=AIAnalysisInputSchema(
                analysis_mode=AnalysisMode.CUSTOM,
                instruction="按操作人汇总风险",
            ).model_dump(mode="json"),
            context_data=self.context_data.model_dump(mode="json"),
            output_data=None,
            is_stream=True,
            created_by=self.user,
            updated_by=self.user,
        )
        self.execution = AttachmentExecution(
            attachment=attachment,
            input_data=AIAnalysisInputSchema(
                analysis_mode=AnalysisMode.CUSTOM,
                instruction="按操作人汇总风险",
            ),
            context_data=self.context_data,
            _stream=mock.Mock(),
        )

    @staticmethod
    def _agent_call(markdown="# 结论"):
        """构造按 AG-UI 回调交付正文的 Agent 测试替身。"""

        def call(**kwargs):
            events = [
                {"type": "TEXT_MESSAGE_START", "messageId": "report", "role": "assistant"},
                {"type": "TEXT_MESSAGE_CONTENT", "messageId": "report", "delta": markdown},
                {"type": "TEXT_MESSAGE_END", "messageId": "report"},
            ]
            for event in events:
                kwargs["on_event"](event)
            return None

        return call

    def _make_non_stream_execution(self):
        Attachment.objects.filter(id=self.execution.attachment.id).update(is_stream=False)
        self.execution.attachment.refresh_from_db()
        return AttachmentExecution(
            attachment=self.execution.attachment,
            input_data=self.execution.input_data,
            context_data=self.execution.context_data,
            _stream=None,
        )

    def test_report_execution_does_not_dispatch_before_success_is_persisted(self):
        with (
            mock.patch(
                "services.web.ai_assistant.tasks.audit_analysis.api.bk_plugins_ai_agent.chat_completion",
                side_effect=self._agent_call(),
            ),
            mock.patch("services.web.ai_assistant.tasks.audit_analysis.generate_log_analysis_title.delay") as delay,
        ):
            output = execute_log_analysis.run(self.execution)

        self.assertEqual(output.markdown, "# 结论")
        delay.assert_not_called()

    def test_success_transition_does_not_dispatch_title_again(self):
        execution = self._make_non_stream_execution()

        with mock.patch(
            "services.web.ai_assistant.tasks.audit_analysis.generate_log_analysis_title.delay",
        ) as delay:
            result = execute_log_analysis._finish_success(
                execution=execution,
                task_id=execution.attachment.task_id,
                output_data=AIAnalysisOutputSchema(markdown="# 结论"),
            )

        self.assertEqual(result, {"status": ExecutionStatus.SUCCESS})
        delay.assert_not_called()

    def test_title_dispatch_failure_does_not_break_report(self):
        """标题 Broker 失败不能将已入队的分析任务误判为派发失败。"""

        with (
            mock.patch.object(AttachmentExecutionTask, "apply_async") as publish,
            mock.patch(
                "services.web.ai_assistant.tasks.audit_analysis.generate_log_analysis_title.delay",
                side_effect=RuntimeError("broker unavailable"),
            ) as title,
        ):
            result = execute_log_analysis.apply_async(
                kwargs={"attachment_id": self.execution.attachment.id, "task_id": "analysis-task"},
                task_id="analysis-task",
            )

        self.assertIs(result, publish.return_value)
        title.assert_called_once_with(attachment_id=self.execution.attachment.id)
        self.execution.attachment.refresh_from_db()
        self.assertEqual(self.execution.attachment.status, ExecutionStatus.PROCESSING)

    def test_analysis_publish_failure_does_not_dispatch_title(self):
        with (
            mock.patch.object(AttachmentExecutionTask, "apply_async", side_effect=RuntimeError("broker unavailable")),
            mock.patch.object(generate_log_analysis_title, "delay") as title,
            self.assertRaises(RuntimeError),
        ):
            execute_log_analysis.apply_async(
                kwargs={"attachment_id": self.execution.attachment.id, "task_id": "analysis-task"},
                task_id="analysis-task",
            )
        title.assert_not_called()

    def test_manual_retry_can_dispatch_title_again(self):
        """失败正文重试复用上下文，默认标题仍可由旁路补全。"""

        attachment = self.execution.attachment
        Attachment.objects.filter(id=attachment.id).update(status=ExecutionStatus.FAILED)
        with (
            mock.patch.object(AttachmentExecutionTask, "apply_async") as publish,
            mock.patch.object(generate_log_analysis_title, "delay") as title,
            self.captureOnCommitCallbacks(execute=True),
        ):
            retried = AttachmentService(user=self.user).retry(attachment_uid=str(attachment.uid))
            title.assert_not_called()
        self.assertEqual(retried.id, attachment.id)
        self.assertEqual(retried.status, ExecutionStatus.PROCESSING)
        self.assertNotEqual(retried.task_id, attachment.task_id)
        publish.assert_called_once()
        title.assert_called_once_with(attachment_id=attachment.id)

    def test_creation_dispatches_title_after_commit_while_report_is_processing(self):
        """使用平台创建入口，仅替换 Broker；验证正文与标题在同次提交后独立投递。"""

        with (
            mock.patch.object(AttachmentExecutionTask, "apply_async") as publish,
            mock.patch.object(generate_log_analysis_title, "delay") as title,
            self.captureOnCommitCallbacks(execute=True),
        ):
            attachment = AttachmentService(user=self.user).create(
                source_message_uid=str(self.execution.attachment.source_message.uid),
                attachment_type=AttachmentType.AI_ANALYSIS,
                input_data=self.execution.input_data.model_dump(mode="json"),
            )
            publish.assert_not_called()
            title.assert_not_called()
        publish.assert_called_once()
        title.assert_called_once_with(attachment_id=attachment.id)
        attachment.refresh_from_db()
        self.assertEqual(attachment.status, ExecutionStatus.PROCESSING)
        self.assertIsNone(attachment.output_data)

    def test_creation_rollback_does_not_dispatch_either_task(self):
        with (
            mock.patch.object(AttachmentExecutionTask, "apply_async") as publish,
            mock.patch.object(generate_log_analysis_title, "delay") as title,
            self.captureOnCommitCallbacks(execute=True),
        ):
            with self.assertRaises(RuntimeError), transaction.atomic():
                AttachmentService(user=self.user).create(
                    source_message_uid=str(self.execution.attachment.source_message.uid),
                    attachment_type=AttachmentType.AI_ANALYSIS,
                    input_data=self.execution.input_data.model_dump(mode="json"),
                )
                raise RuntimeError("rollback")
        publish.assert_not_called()
        title.assert_not_called()

    def test_invalid_markdown_does_not_dispatch_title(self):
        with (
            mock.patch(
                "services.web.ai_assistant.tasks.audit_analysis.api.bk_plugins_ai_agent.chat_completion",
                side_effect=self._agent_call(""),
            ),
            mock.patch("services.web.ai_assistant.tasks.audit_analysis.generate_log_analysis_title.delay") as delay,
            self.assertRaises(AttachmentOutputValidationError),
        ):
            execute_log_analysis.run(self.execution)

        delay.assert_not_called()

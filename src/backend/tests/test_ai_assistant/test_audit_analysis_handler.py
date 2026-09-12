"""日志分析报告 Handler 的来源、快照、编辑、反馈和导出测试。"""

from copy import deepcopy
from unittest import mock

from django.conf import settings

from apps.meta.models import GlobalMetaConfig
from services.web.ai_assistant.constants import (
    AI_ASSISTANT_LOG_ANALYSIS_PROMPT_KEY,
    AnalysisMode,
    AttachmentExportFormat,
    AttachmentType,
    ExecutionMode,
    ExecutionStatus,
    FeedbackSourceType,
    FeedbackType,
    MessageType,
)
from services.web.ai_assistant.exceptions import (
    AttachmentSnapshotValidationError,
    InvalidAttachmentSource,
    UnsupportedLogAnalysisCondition,
)
from services.web.ai_assistant.handlers import attachment_handler_registry
from services.web.ai_assistant.handlers.audit_analysis import AIAnalysisHandler
from services.web.ai_assistant.models import Attachment, Conversation, Message
from services.web.ai_assistant.schemas.audit_analysis import (
    AIAnalysisContextSchema,
    AIAnalysisInputSchema,
    AIAnalysisOutputSchema,
)
from services.web.ai_assistant.services.attachment import AttachmentService
from services.web.ai_assistant.services.attachment_execution import (
    load_attachment_execution,
)
from services.web.ai_assistant.services.feedback import FeedbackService
from tests.test_ai_assistant.base import AIAssistantPlatformTestCase


def ensure_analysis_handler_registered() -> AIAnalysisHandler:
    handler = attachment_handler_registry.unregister(AttachmentType.AI_ANALYSIS) or AIAnalysisHandler()
    attachment_handler_registry.register(handler)
    return handler


class AIAnalysisHandlerTest(AIAssistantPlatformTestCase):
    def setUp(self):
        super().setUp()
        self.handler = ensure_analysis_handler_registered()
        self.log_search = self.create_log_search_message()
        GlobalMetaConfig.set(
            config_key=AI_ASSISTANT_LOG_ANALYSIS_PROMPT_KEY,
            config_value="默认审计分析标准 v1",
        )

    def test_production_handler_declares_platform_capabilities(self):
        self.assertEqual(self.handler.attachment_type, AttachmentType.AI_ANALYSIS)
        self.assertEqual(self.handler.execution_mode, ExecutionMode.ASYNC)
        self.assertTrue(self.handler.is_stream)
        self.assertTrue(self.handler.supports_feedback)
        self.assertEqual(
            self.handler.export_formats,
            (AttachmentExportFormat.MARKDOWN, AttachmentExportFormat.PDF),
        )
        self.assertIs(self.handler.input_model, AIAnalysisInputSchema)
        self.assertIs(self.handler.context_model, AIAnalysisContextSchema)
        self.assertIs(self.handler.output_model, AIAnalysisOutputSchema)

    def test_custom_analysis_snapshots_only_minimal_context(self):
        preparation = self.handler.prepare(
            user=self.user,
            source_message=self.log_search,
            input_data=AIAnalysisInputSchema(
                analysis_mode=AnalysisMode.CUSTOM,
                instruction="按操作人汇总异常行为",
            ),
        )

        snapshot = preparation.context_data.model_dump(mode="json")
        self.assertEqual(preparation.title, "智能分析报告")
        self.assertEqual(snapshot["effective_instruction"], "按操作人汇总异常行为")
        self.assertEqual(snapshot["query_summary"]["total"], self.log_search.output_data["total"])
        self.assertEqual(snapshot["username"], self.user)
        self.assertEqual(snapshot["namespace"], "bkaudit")
        self.assertEqual(snapshot["timezone"], settings.TIME_ZONE)
        self.assertEqual(snapshot["language"], settings.LANGUAGE_CODE)
        self.assertNotIn("samples", snapshot)
        self.assertNotIn("columns", snapshot)
        self.assertNotIn("sql", snapshot)

    def test_default_analysis_snapshots_global_prompt(self):
        preparation = self.handler.prepare(
            user=self.user,
            source_message=self.log_search,
            input_data=AIAnalysisInputSchema(analysis_mode=AnalysisMode.DEFAULT),
        )
        self.assertEqual(preparation.context_data.effective_instruction, "默认审计分析标准 v1")

    def test_default_analysis_can_load_persisted_execution(self):
        # 走真实创建与 Worker 快照加载链路，不能只验证 prepare 的内存模型。
        with mock.patch.object(self.handler.async_task, "apply_async"), self.captureOnCommitCallbacks(execute=True):
            attachment = AttachmentService(user=self.user).create(
                source_message_uid=str(self.log_search.uid),
                attachment_type=AttachmentType.AI_ANALYSIS,
                input_data={"analysis_mode": AnalysisMode.DEFAULT},
            )
        with mock.patch("services.web.ai_assistant.services.attachment_execution.UIStreamRuntime.start"):
            execution = load_attachment_execution(
                attachment_id=attachment.id, task_id=attachment.task_id, celery_task_id=attachment.task_id
            )
        self.assertEqual(execution.input_data.analysis_mode, AnalysisMode.DEFAULT)
        self.assertEqual(execution.context_data.effective_instruction, "默认审计分析标准 v1")

    def test_prepare_rejects_non_log_search_or_invisible_source(self):
        wrong_type = self.create_selection_message()
        other_conversation = Conversation.objects.create(created_by="other", updated_by="other")
        other_message = Message.objects.create(
            conversation=other_conversation,
            message_type=MessageType.LOG_SEARCH,
            status=ExecutionStatus.SUCCESS,
            input_data=self.log_search.input_data,
            context_data={**self.log_search.context_data, "username": "other"},
            output_data=self.log_search.output_data,
            created_by="other",
            updated_by="other",
        )
        analysis_input = AIAnalysisInputSchema(analysis_mode=AnalysisMode.DEFAULT)

        for source_message in (wrong_type, other_message):
            with self.subTest(message_type=source_message.message_type), self.assertRaises(InvalidAttachmentSource):
                self.handler.prepare(user=self.user, source_message=source_message, input_data=analysis_input)

    def test_service_rejects_non_success_source(self):
        self.log_search.status = ExecutionStatus.FAILED
        self.log_search.save(update_record=False, update_fields=["status"])

        with self.assertRaises(InvalidAttachmentSource):
            AttachmentService(user=self.user).create(
                source_message_uid=str(self.log_search.uid),
                attachment_type=AttachmentType.AI_ANALYSIS,
                input_data={"analysis_mode": AnalysisMode.DEFAULT},
            )

    def test_prepare_rejects_corrupted_log_search_snapshots(self):
        invalid_snapshots = (
            ("input_data", {"condition": {"scope_id": "broken"}}),
            ("context_data", {"username": self.user}),
            ("output_data", {"total": "broken"}),
        )
        for field_name, value in invalid_snapshots:
            with self.subTest(field=field_name):
                original = getattr(self.log_search, field_name)
                setattr(self.log_search, field_name, value)
                with self.assertRaises(AttachmentSnapshotValidationError):
                    self.handler.prepare(
                        user=self.user,
                        source_message=self.log_search,
                        input_data=AIAnalysisInputSchema(analysis_mode=AnalysisMode.DEFAULT),
                    )
                setattr(self.log_search, field_name, original)

    def test_prepare_rejects_source_condition_outside_agent_tool_budget(self):
        input_data = deepcopy(self.log_search.input_data)
        input_data["condition"]["conditions"] = [
            {
                "field": {"raw_name": "username", "keys": []},
                "operator": "eq",
                "filters": ["alice"],
            }
        ] * 101
        self.log_search.input_data = input_data

        with self.assertRaisesRegex(UnsupportedLogAnalysisCondition, "当前日志检索条件暂不支持智能分析"):
            self.handler.prepare(
                user=self.user,
                source_message=self.log_search,
                input_data=AIAnalysisInputSchema(analysis_mode=AnalysisMode.DEFAULT),
            )

    def test_prepare_rejects_conflicts_between_log_search_snapshots(self):
        """同一检索的输入、上下文和输出摘要不能被跨消息拼接。"""

        original_context = deepcopy(self.log_search.context_data)
        original_output = deepcopy(self.log_search.output_data)
        conflicts = {
            "scope_type": lambda context, output: output["query_summary"].update(scope_type="other"),
            "scope_id": lambda context, output: output["query_summary"].update(scope_id="other"),
            "time_range": lambda context, output: output["query_summary"].update(
                time_range={**output["query_summary"]["time_range"], "start_time": "2026-08-23T00:00:00+08:00"}
            ),
            "source": lambda context, output: output["query_summary"].update(source="natural_language"),
            "negative_condition_count": lambda context, output: output["query_summary"].update(condition_count=-1),
            "excessive_condition_count": lambda context, output: output["query_summary"].update(
                condition_count=len(self.log_search.input_data["condition"]["conditions"]) + 1
            ),
        }

        for dimension, mutate in conflicts.items():
            with self.subTest(dimension=dimension):
                context_data = deepcopy(original_context)
                output_data = deepcopy(original_output)
                mutate(context_data, output_data)
                self.log_search.context_data = context_data
                self.log_search.output_data = output_data
                with self.assertRaises(AttachmentSnapshotValidationError):
                    self.handler.prepare(
                        user=self.user,
                        source_message=self.log_search,
                        input_data=AIAnalysisInputSchema(analysis_mode=AnalysisMode.DEFAULT),
                    )

        self.log_search.context_data = original_context
        self.log_search.output_data = original_output

    def test_manual_retry_reuses_effective_instruction_snapshot(self):
        service = AttachmentService(user=self.user)
        with mock.patch.object(self.handler.async_task, "apply_async"):
            with self.captureOnCommitCallbacks(execute=True):
                attachment = service.create(
                    source_message_uid=str(self.log_search.uid),
                    attachment_type=AttachmentType.AI_ANALYSIS,
                    input_data={"analysis_mode": AnalysisMode.DEFAULT},
                )
        Attachment.objects.filter(id=attachment.id).update(status=ExecutionStatus.FAILED)
        GlobalMetaConfig.set(
            config_key=AI_ASSISTANT_LOG_ANALYSIS_PROMPT_KEY,
            config_value="默认审计分析标准 v2",
        )

        with mock.patch.object(self.handler.async_task, "apply_async"):
            with self.captureOnCommitCallbacks(execute=True):
                retried = service.retry(attachment_uid=str(attachment.uid))

        self.assertEqual(retried.context_data["effective_instruction"], "默认审计分析标准 v1")
        self.assertEqual(retried.status, ExecutionStatus.PROCESSING)
        self.assertNotEqual(retried.task_id, attachment.task_id)

    def test_markdown_output_is_editable_feedbackable_and_exportable(self):
        attachment = Attachment.objects.create(
            source_message=self.log_search,
            attachment_type=AttachmentType.AI_ANALYSIS,
            title="智能分析报告",
            status=ExecutionStatus.SUCCESS,
            input_data={"analysis_mode": AnalysisMode.CUSTOM, "instruction": "分析异常"},
            context_data={},
            output_data={"markdown": "# 原始结论"},
            created_by=self.user,
            updated_by=self.user,
        )
        service = AttachmentService(user=self.user)

        updated = service.update(
            attachment_uid=str(attachment.uid),
            output_data={"markdown": "# 修订结论"},
        )
        feedback = FeedbackService(user=self.user).upsert(
            source_type=FeedbackSourceType.ATTACHMENT,
            source_uid=str(attachment.uid),
            feedback_type=FeedbackType.LIKE,
        )
        markdown_file = service.export(
            attachment_uid=str(attachment.uid),
            export_format=AttachmentExportFormat.MARKDOWN,
        )
        with mock.patch(
            "services.web.ai_assistant.exporters.markdown.MarkdownDocumentExporter._create_pdf",
            return_value=b"%PDF-test",
        ):
            pdf_file = service.export(
                attachment_uid=str(attachment.uid),
                export_format=AttachmentExportFormat.PDF,
            )

        self.assertEqual(updated.output_data, {"markdown": "# 修订结论"})
        self.assertEqual(feedback.feedback_type, FeedbackType.LIKE)
        self.assertEqual(markdown_file.content, "# 修订结论".encode("utf-8"))
        self.assertTrue(pdf_file.content.startswith(b"%PDF"))

"""日志分析报告 Attachment 的类型化快照协议测试。"""

import subprocess
import sys
import textwrap

from django.conf import settings
from django.test import SimpleTestCase, override_settings
from pydantic import ValidationError

from services.web.ai_assistant.constants import AnalysisMode, AttachmentType
from services.web.ai_assistant.schemas.audit_analysis import (
    AIAnalysisContextSchema,
    AIAnalysisInputSchema,
    AIAnalysisOutputSchema,
    AIAnalysisQuerySummary,
)
from tests.test_ai_assistant.base import make_condition
from tests.test_ai_assistant.production_handler_contracts import (
    captured_attachment_handlers,
)


class AIAnalysisSchemaTest(SimpleTestCase):
    def test_default_input_snapshot_roundtrip(self):
        input_data = AIAnalysisInputSchema(analysis_mode=AnalysisMode.DEFAULT)
        self.assertEqual(AIAnalysisInputSchema.model_validate(input_data.model_dump(mode="json")), input_data)
        self.assertEqual(AIAnalysisInputSchema.model_validate_json(input_data.model_dump_json()), input_data)
        self.assertEqual(input_data.model_dump(mode="json"), {"analysis_mode": AnalysisMode.DEFAULT})

    def test_input_json_schema_preserves_fields_after_custom_serialization(self):
        # wrap serializer 只调整 DEFAULT 的输出字段，不得把 Swagger 协议退化为任意字典。
        for mode in ("validation", "serialization"):
            with self.subTest(mode=mode):
                schema = AIAnalysisInputSchema.model_json_schema(mode=mode)
                self.assertEqual(set(schema["properties"]), {"analysis_mode", "instruction"})
                self.assertEqual(schema["required"], ["analysis_mode"])
                instruction_types = schema["properties"]["instruction"]["anyOf"]
                string_schema = next(item for item in instruction_types if item["type"] == "string")
                self.assertEqual(string_schema["maxLength"], settings.AI_ASSISTANT_LOG_ANALYSIS_PROMPT_MAX_LENGTH)

    def test_default_mode_rejects_any_explicit_client_instruction(self):
        for instruction in (None, "", "   ", "自行覆盖默认标准"):
            with self.subTest(instruction=instruction), self.assertRaises(ValidationError):
                AIAnalysisInputSchema(analysis_mode=AnalysisMode.DEFAULT, instruction=instruction)

        omitted = AIAnalysisInputSchema(analysis_mode=AnalysisMode.DEFAULT)
        self.assertNotIn("instruction", omitted.model_fields_set)

    def test_custom_mode_requires_non_blank_instruction(self):
        for instruction in (None, "", "   "):
            with self.subTest(instruction=instruction), self.assertRaises(ValidationError):
                AIAnalysisInputSchema(analysis_mode=AnalysisMode.CUSTOM, instruction=instruction)

    def test_custom_instruction_uses_configured_length_limit(self):
        AIAnalysisInputSchema(
            analysis_mode=AnalysisMode.CUSTOM,
            instruction="x" * settings.AI_ASSISTANT_LOG_ANALYSIS_PROMPT_MAX_LENGTH,
        )
        with self.assertRaises(ValidationError):
            AIAnalysisInputSchema(
                analysis_mode=AnalysisMode.CUSTOM,
                instruction="x" * (settings.AI_ASSISTANT_LOG_ANALYSIS_PROMPT_MAX_LENGTH + 1),
            )

        self.assertEqual(
            AIAnalysisInputSchema.drf_serializer().fields["instruction"].max_length,
            settings.AI_ASSISTANT_LOG_ANALYSIS_PROMPT_MAX_LENGTH,
        )

    def test_production_handler_exposes_typed_swagger_models(self):
        handler = captured_attachment_handlers()[AttachmentType.AI_ANALYSIS]

        self.assertIs(handler.input_model, AIAnalysisInputSchema)
        self.assertIs(handler.output_model, AIAnalysisOutputSchema)

    @override_settings(ROOT_URLCONF="urls")
    def test_real_openapi_exposes_production_analysis_input_and_output(self):
        # drf-spectacular 会冻结首次生成的多态 schema；独立进程准确模拟生产冷启动，
        # 避免同一测试进程内 Echo Handler 生成过的 schema 缓存干扰生产契约断言。
        script = textwrap.dedent(
            """
            import django
            import yaml
            from unittest import mock

            django.setup()

            from drf_spectacular.views import SpectacularAPIView
            from rest_framework.test import APIRequestFactory

            request = APIRequestFactory().get("/api/schema/")
            request.user = mock.Mock(is_staff=True, is_authenticated=True)
            response = SpectacularAPIView.as_view()(request)
            response.render()
            components = yaml.safe_load(response.content)["components"]["schemas"]

            assert components["AIAttachmentInputDataRequest"]["oneOf"] == [
                {"$ref": "#/components/schemas/AIAnalysisInputSchemaRequest"}
            ]
            assert components["AIAttachmentOutputData"]["oneOf"] == [
                {"$ref": "#/components/schemas/AIAnalysisOutputSchema"}
            ]
            assert components["EditableAIAttachmentOutputDataRequest"]["oneOf"] == [
                {"$ref": "#/components/schemas/AIAnalysisOutputSchemaRequest"}
            ]
            """
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_context_is_minimal_and_rejects_samples_or_sql(self):
        payload = {
            "effective_instruction": "按默认审计标准分析",
            "search_condition": make_condition().model_dump(mode="json"),
            "query_summary": {"total": 2, "took_ms": 12, "executed_at": "2026-08-24T12:00:00+08:00"},
            "username": "alice",
            "namespace": "bkaudit",
            "timezone": "Asia/Shanghai",
            "language": "zh-cn",
        }
        context = AIAnalysisContextSchema.model_validate(payload)

        self.assertEqual(context.query_summary.total, 2)
        self.assertEqual(
            set(context.model_dump(mode="json")),
            {
                "effective_instruction",
                "search_condition",
                "query_summary",
                "username",
                "namespace",
                "timezone",
                "language",
            },
        )
        for unexpected_field in ("samples", "sql", "message_id", "attachment_id"):
            with self.subTest(field=unexpected_field), self.assertRaises(ValidationError):
                AIAnalysisContextSchema.model_validate({**payload, unexpected_field: []})

    def test_query_summary_rejects_negative_values(self):
        for field_name in ("total", "took_ms"):
            with self.subTest(field=field_name), self.assertRaises(ValidationError):
                AIAnalysisQuerySummary.model_validate({"total": 1, "took_ms": 1, "executed_at": "now", field_name: -1})

    @override_settings(AI_ASSISTANT_ATTACHMENT_MARKDOWN_MAX_BYTES=5)
    def test_output_rejects_blank_and_oversized_markdown(self):
        for markdown in ("", "   ", "你好"):
            with self.subTest(markdown=markdown), self.assertRaises(ValidationError):
                AIAnalysisOutputSchema(markdown=markdown)

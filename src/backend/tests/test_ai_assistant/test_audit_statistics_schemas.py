"""程序统计附件协议：拒绝越权范围和非法预算，保留路径原文。"""

from django.test import SimpleTestCase, override_settings
from pydantic import ValidationError

from services.web.ai_assistant.schemas.audit_statistics import (
    AIStatisticsAttachmentInput,
    AIStatisticsAttachmentOutput,
    FieldStatisticsAttachmentInput,
)


class FieldStatisticsSchemaTest(SimpleTestCase):
    """输入不能为统计服务引入第二份范围或可信类型。"""

    def test_defaults_and_literal_path(self):
        value = FieldStatisticsAttachmentInput(field={"raw_name": "extend_data", "keys": [" 方法 "]})
        self.assertEqual(value.field.keys, [" 方法 "])
        self.assertEqual(value.top_n, 100)
        self.assertEqual(value.interval, "AUTO")

    def test_rejects_invalid_budget_field_and_range(self):
        for patch in (
            {"top_n": 0},
            {"top_n": 501},
            {"top_n": True},
            {"top_n": "2"},
            {"top_n": None},
            {"interval": "WEEK"},
            {"condition": {}},
            {"namespace": "other"},
            {"username": "other"},
            {"start_time": "2026-01-01"},
            {"field": {"raw_name": "password"}},
            {"field": {"raw_name": "username", "keys": ["bad"]}},
        ):
            with self.subTest(patch=patch), self.assertRaises(ValidationError):
                FieldStatisticsAttachmentInput.model_validate({"field": {"raw_name": "username"}, **patch})

    @override_settings(AI_LOG_AGGREGATION_MAX_TOP_N=3)
    def test_configured_budget_applies_at_creation(self):
        with self.assertRaises(ValidationError):
            FieldStatisticsAttachmentInput(field={"raw_name": "username"}, top_n=4)


class AIStatisticsSchemaTest(SimpleTestCase):
    """AI 正文不解释格式；指令和字节预算在独立边界验证。"""

    def test_preserves_any_nonblank_content_exactly(self):
        for content in ("  ```custom-chart\nnot-json\n```\n", "无法满足需求", "{invalid JSON", "\t无数据\n"):
            with self.subTest(content=content):
                self.assertEqual(AIStatisticsAttachmentOutput(content=content).model_dump(), {"content": content})

    @override_settings(AI_ASSISTANT_AI_STATISTICS_CONTENT_MAX_BYTES=6)
    def test_empty_and_utf8_budget_rejected(self):
        self.assertEqual(AIStatisticsAttachmentOutput(content="中文").content, "中文")
        for content in ("", " \n\t", "中文字"):
            with self.subTest(content=content), self.assertRaises(ValidationError):
                AIStatisticsAttachmentOutput(content=content)

    def test_instruction_required_nonblank_bounded_and_identity_forbidden(self):
        for data in (
            {},
            {"instruction": " \n"},
            {"instruction": "x" * 2049},
            {"instruction": "统计", "username": "other"},
            {"instruction": "统计", "condition": {}},
            {"instruction": "统计", "namespace": "other"},
        ):
            with self.subTest(data=data), self.assertRaises(ValidationError):
                AIStatisticsAttachmentInput.model_validate(data)

"""程序统计附件协议：拒绝越权范围和非法预算，保留路径原文。"""

from django.test import SimpleTestCase, override_settings
from pydantic import ValidationError

from services.web.ai_assistant.schemas.audit_statistics import (
    AIStatisticsAttachmentInput,
    AIStatisticsAttachmentOutput,
    FieldStatisticsAttachmentInput,
)
from services.web.query.ai_assistant.log_tools.field_statistics_schemas import (
    FieldDistributionGroup,
    FieldStatisticsOverview,
)
from services.web.query.ai_assistant.log_tools.schemas import AggregationGroupKind


class FieldStatisticsSchemaTest(SimpleTestCase):
    """输入不能为统计服务引入第二份范围或可信类型。"""

    def test_program_ratios_round_four_decimal_places_only_on_output(self):
        """概览和分布输出遵守同一精度，保留计数、空值和内部比例。"""
        for count, total, expected in ((7, 11, 0.6364), (1, 100000, 0.0), (0, 1, 0.0), (0, 0, None)):
            ratio = count / total if total else None
            overview = FieldStatisticsOverview(
                total_count=total, present_count=count, missing_count=total - count, present_ratio=ratio
            )
            group = FieldDistributionGroup(
                group_id="g1",
                kind=AggregationGroupKind.VALUE,
                value_type="string",
                value="value",
                count=count,
                ratio=ratio,
            )
            self.assertEqual(overview.model_dump()["present_ratio"], expected)
            self.assertEqual(group.model_dump()["ratio"], expected)
            self.assertEqual(group.model_dump()["count"], count)
            self.assertEqual(overview.present_ratio, ratio)

    def test_defaults_and_literal_path(self):
        value = FieldStatisticsAttachmentInput(field={"raw_name": "extend_data", "keys": [" 方法 "]})
        self.assertEqual(value.field.keys, [" 方法 "])
        self.assertEqual(value.top_n, 10)
        self.assertEqual(value.interval, "AUTO")

    @override_settings(AI_LOG_AGGREGATION_DEFAULT_TOP_N=7)
    def test_default_uses_shared_setting_and_explicit_value_survives(self):
        """仅缺省输入跟随共享配置，历史快照及显式参数不改写。"""
        self.assertEqual(FieldStatisticsAttachmentInput(field={"raw_name": "username"}).top_n, 7)
        self.assertEqual(FieldStatisticsAttachmentInput(field={"raw_name": "username"}, top_n=100).top_n, 100)

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

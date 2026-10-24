"""程序统计附件协议：拒绝越权范围和非法预算，保留路径原文。"""

from django.test import SimpleTestCase, override_settings
from pydantic import ValidationError

from services.web.ai_assistant.schemas.audit_analysis import AIAnalysisInputSchema
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
        value = FieldStatisticsAttachmentInput(field={"raw_name": "extend_data", "keys": ["请求-方法"]})
        self.assertEqual(value.field.keys, ["请求-方法"])
        self.assertNotIn("top_n", value.model_dump())
        self.assertEqual(value.interval, "AUTO")

    def test_month_and_complete_condition_are_supported_but_null_is_invalid(self):
        condition = dict(
            scope_type="system",
            scope_id="example",
            start_time="2026-01-01T00:00:00+08:00",
            end_time="2026-02-01T00:00:00+08:00",
            conditions=[],
        )
        value = FieldStatisticsAttachmentInput(field={"raw_name": "username"}, interval="MONTH", condition=condition)
        self.assertEqual(value.condition.scope_id, "example")
        self.assertEqual(value.interval, "MONTH")
        with self.assertRaises(ValidationError):
            FieldStatisticsAttachmentInput(field={"raw_name": "username"}, condition=None)

    def test_explicit_condition_requires_scope_and_filter_list_for_all_three_inputs(self):
        condition = dict(
            scope_type="system",
            scope_id="example",
            start_time="2026-01-01T00:00:00+08:00",
            end_time="2026-02-01T00:00:00+08:00",
            conditions=[],
        )
        for model, payload in (
            (FieldStatisticsAttachmentInput, {"field": {"raw_name": "username"}}),
            (AIStatisticsAttachmentInput, {"instruction": "统计"}),
            (AIAnalysisInputSchema, {"analysis_mode": "DEFAULT"}),
        ):
            for key in ("scope_type", "scope_id", "start_time", "end_time", "conditions"):
                partial = {name: value for name, value in condition.items() if name != key}
                with self.subTest(model=model.__name__, missing=key), self.assertRaises(ValidationError):
                    model.model_validate({**payload, "condition": partial})

    def test_override_condition_schema_requires_the_same_complete_fields(self):
        schema = FieldStatisticsAttachmentInput.model_json_schema(mode="validation")
        condition_schema = schema["$defs"]["LogAttachmentCondition"]
        self.assertEqual(
            set(condition_schema["required"]), {"scope_type", "scope_id", "start_time", "end_time", "conditions"}
        )

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


class AIStatisticsSchemaTest(SimpleTestCase):
    """输出 Schema 不解释已提取内容。"""

    def test_preserves_any_nonblank_content_exactly(self):
        for content in ('{"x": 1}', '[{"x": 1}]', "{invalid JSON", "\t无数据\n"):
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

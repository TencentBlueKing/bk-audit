from django.db.models import TextChoices
from django.test import SimpleTestCase

from services.web.ai_assistant import constants as ai_assistant_constants
from services.web.ai_assistant.ai_statistics_artifact import (
    AIStatisticsArtifactErrorReason,
    AIStatisticsArtifactExtractionError,
    extract_ai_statistics_chart_config,
)


class AIStatisticsArtifactTest(SimpleTestCase):
    start_tag = "<!--DASH_AI_CHART_CONFIG-->"
    end_tag = "<!--/DASH_AI_CHART_CONFIG-->"

    def extract(self, content):
        return extract_ai_statistics_chart_config(content, start_tag=self.start_tag, end_tag=self.end_tag)

    def test_error_reasons_are_labeled_choices_in_shared_constants(self):
        """标签失败原因提供可读说明并保持原有稳定值。"""

        self.assertIs(
            getattr(ai_assistant_constants, "AIStatisticsArtifactErrorReason", None),
            AIStatisticsArtifactErrorReason,
        )
        self.assertTrue(issubclass(AIStatisticsArtifactErrorReason, TextChoices))
        self.assertEqual(
            [reason.value for reason in AIStatisticsArtifactErrorReason],
            ["START_TAG_COUNT_INVALID", "END_TAG_COUNT_INVALID", "TAG_ORDER_INVALID", "EMPTY_CONTENT"],
        )
        for reason in AIStatisticsArtifactErrorReason:
            with self.subTest(reason=reason):
                self.assertRegex(str(reason.label), r"[\u4e00-\u9fff]")

    def test_extracts_only_inner_text_without_interpreting_it(self):
        for inner in ('  {"series": []}\n', '[{"type":"bar"}]', 'not-json'):
            with self.subTest(inner=inner):
                content = f"前置说明\n{self.start_tag}{inner}{self.end_tag}\n后置说明"
                self.assertEqual(self.extract(content), inner)

    def test_rejects_missing_duplicate_reversed_and_blank_blocks(self):
        cases = (
            ("无标签", AIStatisticsArtifactErrorReason.START_TAG_COUNT_INVALID),
            (f"{self.start_tag}x", AIStatisticsArtifactErrorReason.END_TAG_COUNT_INVALID),
            (f"{self.end_tag}x{self.start_tag}", AIStatisticsArtifactErrorReason.TAG_ORDER_INVALID),
            (
                f"{self.start_tag}a{self.end_tag}{self.start_tag}b{self.end_tag}",
                AIStatisticsArtifactErrorReason.START_TAG_COUNT_INVALID,
            ),
            (f"{self.start_tag} \n\t {self.end_tag}", AIStatisticsArtifactErrorReason.EMPTY_CONTENT),
        )
        for content, reason in cases:
            with self.subTest(content=content), self.assertRaises(AIStatisticsArtifactExtractionError) as caught:
                self.extract(content)
            self.assertEqual(caught.exception.reason, reason)
            self.assertNotIn(content, str(caught.exception))

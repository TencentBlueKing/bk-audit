# -*- coding: utf-8 -*-
"""多风险分析报告：只拆 Final Answer / action_input 与 markdown 围栏。"""

import unittest

from services.web.risk.report.markdown_extract import extract_markdown_report_body


class TestExtractMarkdownReportBody(unittest.TestCase):
    def test_keeps_normal_h1_report_unchanged(self):
        content = "# 风险态势总结报告\n\n## 概述\n\n正文\n"
        self.assertIs(extract_markdown_report_body(content), content)

    def test_keeps_report_that_does_not_start_with_h1(self):
        content = "概述：本周风险集中在登录异常。\n\n## 明细\n\n正文\n"
        self.assertIs(extract_markdown_report_body(content), content)

    def test_keeps_prose_before_h1_without_wrapper(self):
        content = "现在我已经收集了足够的数据，可以开始撰写最终报告了。让我整理一下关键发现：\n\n" "- 点1\n\n" "# 风险态势总结报告\n\n" "## 一、概述\n"
        self.assertIs(extract_markdown_report_body(content), content)

    def test_keeps_inner_code_fence_when_report_has_no_wrapper(self):
        content = "# 标题\n\n示例：\n\n```json\n{\"a\": 1}\n```\n"
        self.assertIs(extract_markdown_report_body(content), content)

    def test_keeps_json_without_final_answer(self):
        content = '{"summary": "ok"}\n'
        self.assertIs(extract_markdown_report_body(content), content)

    def test_keeps_tool_call_json_instead_of_treating_as_report(self):
        content = '```json\n{"action": "workspace_list", "action_input": {}}\n```\n'
        self.assertIs(extract_markdown_report_body(content), content)

    def test_keeps_plain_text_without_wrapper(self):
        content = "现在我已经收集了足够的数据，可以开始撰写最终报告了。\n"
        self.assertIs(extract_markdown_report_body(content), content)

    def test_does_not_extract_inner_markdown_example_shorter_than_prefix(self):
        content = "# 标题\n\n示例：\n\n```markdown\n# 示例标题\n```\n"
        self.assertIs(extract_markdown_report_body(content), content)

    def test_unwraps_markdown_fence_and_action_input(self):
        content = "```markdown\naction_input\n# 责任人行为调查报告\n\n正文\n```\n"
        result = extract_markdown_report_body(content)
        self.assertEqual(result, "# 责任人行为调查报告\n\n正文\n")
        self.assertNotIn("action_input", result)
        self.assertNotIn("```", result)

    def test_extracts_markdown_fence_after_thinking(self):
        content = "根据已获取的数据，我来撰写报告。\n" "```markdown\n" "action_input\n" "# 责任人行为调查报告\n\n" "## 分析\n"
        result = extract_markdown_report_body(content)
        self.assertEqual(result, "# 责任人行为调查报告\n\n## 分析\n")
        self.assertNotIn("action_input", result)
        self.assertNotIn("```", result)

    def test_keeps_inner_code_fence_after_unwrapping_markdown(self):
        content = "思考过程\n" "```markdown\n" "# 标题\n\n" "示例：\n\n" "```python\n" "print(1)\n" "```\n" "```\n"
        result = extract_markdown_report_body(content)
        self.assertEqual(result, "# 标题\n\n示例：\n\n```python\nprint(1)\n```\n")

    def test_extracts_last_final_answer_json(self):
        content = "\n".join(
            [
                '```json\n{"action": "workspace_list", "action_input": {}}\n```',
                '```json\n{"action": "Final Answer", "action_input": "# 策略分析报告\\n正文"}\n```',
            ]
        )
        self.assertEqual(extract_markdown_report_body(content), "# 策略分析报告\n正文")

    def test_extracts_bare_final_answer_label(self):
        content = "Thought: 数据已齐。\nFinal Answer:\n概述：登录异常集中。\n"
        self.assertEqual(extract_markdown_report_body(content), "概述：登录异常集中。\n")

    def test_extracts_xml_final_answer(self):
        content = "过程说明\n<final_answer>\n概述：登录异常集中。\n</final_answer>\n"
        self.assertEqual(extract_markdown_report_body(content).strip(), "概述：登录异常集中。")

    def test_keeps_h1_report_with_embedded_final_answer_json(self):
        content = (
            "# 风险态势总结报告\n\n"
            "## 概述\n\n"
            "```json\n"
            '{"action": "Final Answer", "action_input": "# 被误抽的附录"}\n'
            "```\n\n"
            "## 结论\n\n"
            "真实结论\n"
        )
        self.assertIs(extract_markdown_report_body(content), content)

    def test_keeps_h1_report_with_embedded_final_answer_xml(self):
        content = "# 风险态势总结报告\n\n<final_answer>错误内容</final_answer>\n\n真实结论\n"
        self.assertIs(extract_markdown_report_body(content), content)

    def test_keeps_prose_report_with_inline_action_input_line(self):
        content = "本次分析关注工具参数。\n\naction_input: {\"risk_id\": \"R123\"}\n\n建议：冻结账号。\n"
        self.assertIs(extract_markdown_report_body(content), content)

    def test_keeps_short_report_with_longer_markdown_appendix(self):
        content = "# 标题\n\n" "简短结论。\n\n" "```markdown\n" "# 示例报告模板\n\n" "这里是一段明显长于前文的附录模板，用来说明章节写法。\n" "```\n"
        self.assertIs(extract_markdown_report_body(content), content)

    def test_unwraps_markdown_fence_with_inner_bare_code_fence(self):
        content = "思考过程\n" "```markdown\n" "# 标题\n\n" "命令：\n\n" "```\n" "ls\n" "```\n\n" "更多正文\n" "```\n"
        result = extract_markdown_report_body(content)
        self.assertEqual(result, "# 标题\n\n命令：\n\n```\nls\n```\n\n更多正文\n")

    def test_keeps_empty_final_answer_json(self):
        content = '{"action": "Final Answer", "action_input": "   "}'
        self.assertIs(extract_markdown_report_body(content), content)

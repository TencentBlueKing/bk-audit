#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
promptfoo 评估结果分析脚本

解析 promptfoo eval -o 导出的 JSON 文件，生成结构化的失败分析报告。
支持单次分析和两轮对比。

用法：
  # 单次分析
  python analyze_results.py results.json

  # 两轮对比（调优前 vs 调优后）
  python analyze_results.py before.json after.json

  # 输出到文件
  python analyze_results.py results.json -o report.md
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path


def _get_description(row: dict) -> str:
    """从 row 中提取用例描述，兼容 results 列表和 table body 两种格式"""
    desc = row.get("description")
    if not desc:
        desc = (row.get("testCase") or {}).get("description")
    if not desc:
        desc = (row.get("test") or {}).get("description")
    return desc or "未命名"


def _is_failing(row: dict) -> bool:
    """判断行是否失败，兼容 results 列表和 table body 两种格式"""
    if "success" in row:
        return not row["success"]
    if "pass" in row:
        return not row["pass"]
    outputs = row.get("outputs", [])
    if outputs:
        return not outputs[0].get("pass", True)
    return False


def _get_response(row: dict) -> dict:
    """提取 response 信息，兼容两种格式"""
    if "response" in row:
        return row.get("response") or {}
    outputs = row.get("outputs", [])
    if outputs:
        return outputs[0]
    return {}


def _get_grading(row: dict) -> dict:
    """提取 gradingResult，兼容两种格式"""
    if "gradingResult" in row:
        return row.get("gradingResult") or {}
    outputs = row.get("outputs", [])
    if outputs:
        return outputs[0].get("gradingResult") or {}
    return {}


def _get_output_text(row: dict) -> str:
    """提取模型输出文本"""
    resp = _get_response(row)
    return resp.get("output") or resp.get("text") or ""


def load_results(path: str) -> dict:
    """加载 promptfoo 输出 JSON，兼容不同版本的输出格式"""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    results_root = data.get("results", data)

    stats = results_root.get("stats", {})

    rows = []
    if "results" in results_root and isinstance(results_root["results"], list):
        rows = results_root["results"]
    elif "table" in results_root:
        table = results_root["table"]
        if "body" in table:
            rows = table["body"]

    return {"stats": stats, "rows": rows, "raw": data}


def classify_failure(row: dict) -> str:
    """根据失败特征分类

    优先检查 gradingResult（断言失败），只有在无断言结果时才检查 error（真正的 provider 错误）。
    """
    response = _get_response(row)
    output = _get_output_text(row)
    grading = _get_grading(row)
    components = grading.get("componentResults", [])

    if components:
        for comp in components:
            if comp.get("pass"):
                continue
            assertion_type = (comp.get("assertion") or {}).get("type", "")
            reason = comp.get("reason", "")

            if assertion_type == "python" and "serializer" in reason.lower():
                return "格式错误"
            if assertion_type in ("llm-rubric", "factuality", "answer-relevance"):
                return "语义不符"
            if "expected" in reason.lower() and "key" in reason.lower():
                return "字段缺失"
            if "value" in reason.lower() or "mismatch" in reason.lower():
                return "值错误"
            if assertion_type == "is-json":
                return "格式错误"

        return "其他"

    error = row.get("error") or response.get("error", "")
    if error:
        error_lower = str(error).lower()
        if any(k in error_lower for k in ["timeout", "timed out"]):
            return "超时"
        if any(k in error_lower for k in ["connect", "connection", "network"]):
            return "网络错误"
        return "Provider 错误"

    if not output or output.strip() in ("", "{}", "null", "None"):
        return "空输出"

    return "其他"


_CATEGORY_SUGGESTIONS = {
    "Provider 错误": "检查 AI 服务可用性和 .env 配置",
    "超时": "检查 AI 服务响应时间，考虑增加 timeout",
    "网络错误": "检查网络连通性和服务地址配置",
    "空输出": "检查 prompt 是否覆盖该查询类型，或模型是否理解意图",
    "格式错误": "检查 prompt 中的输出格式约束，增加格式示例",
    "字段缺失": "在 prompt 中明确必填字段，增加 few-shot 示例",
    "值错误": "检查枚举映射是否完整，增加枚举值说明",
    "语义不符": "增加相关场景的 few-shot 示例，细化 prompt 规则",
    "其他": "需要人工逐个分析失败原因",
}


def analyze_single(data: dict) -> str:
    """单次结果分析"""
    stats = data["stats"]
    rows = data["rows"]

    total = stats.get("successes", 0) + stats.get("failures", 0) + stats.get("errors", 0)
    successes = stats.get("successes", 0)
    failures = stats.get("failures", 0)
    errors = stats.get("errors", 0)
    pass_rate = (successes / total * 100) if total > 0 else 0

    lines = [
        "## 评估结果摘要\n",
        f"- 总断言数: {total}",
        f"- 通过: {successes} ({pass_rate:.1f}%)",
        f"- 失败: {failures}",
        f"- 错误: {errors}",
        "",
    ]

    token_usage = stats.get("tokenUsage", {})
    if token_usage and token_usage.get("total", 0) > 0:
        lines.append(
            f"- Token 消耗: 总计 {token_usage.get('total', 0)}"
            f" (prompt: {token_usage.get('prompt', 0)},"
            f" completion: {token_usage.get('completion', 0)})"
        )
        lines.append("")

    failure_groups = defaultdict(list)
    for row in rows:
        if not _is_failing(row):
            continue

        category = classify_failure(row)
        desc = _get_description(row)
        output_text = _get_output_text(row)[:200]

        grading = _get_grading(row)
        failed_assertions = []
        for comp in grading.get("componentResults", []):
            if not comp.get("pass"):
                failed_assertions.append(comp.get("reason", "未知原因")[:150])

        error = row.get("error") or _get_response(row).get("error", "")
        if error and not failed_assertions:
            failed_assertions.append(str(error)[:150])

        failure_groups[category].append(
            {
                "description": desc,
                "output_preview": output_text,
                "reasons": failed_assertions,
            }
        )

    if not failure_groups:
        lines.append("**全部通过，无失败用例。**\n")
        return "\n".join(lines)

    lines.append("## 失败用例分析\n")
    for category, items in sorted(failure_groups.items(), key=lambda x: -len(x[1])):
        lines.append(f"### {category} ({len(items)} 个)\n")
        for item in items:
            lines.append(f"- **{item['description']}**")
            if item["output_preview"]:
                lines.append(f"  - 输出预览: `{item['output_preview']}`")
            for reason in item["reasons"][:3]:
                lines.append(f"  - 失败原因: {reason}")
            lines.append("")

    lines.append("## 根因总结\n")
    for category, items in sorted(failure_groups.items(), key=lambda x: -len(x[1])):
        suggestion = _CATEGORY_SUGGESTIONS.get(category, "需要人工分析")
        lines.append(f"- **{category}** ({len(items)} 个): {suggestion}")

    return "\n".join(lines)


def analyze_comparison(before: dict, after: dict) -> str:
    """两轮对比分析"""
    bs, ars = before["stats"], after["stats"]

    def _total(s):
        return s.get("successes", 0) + s.get("failures", 0) + s.get("errors", 0)

    bt, at = _total(bs), _total(ars)
    bp = (bs.get("successes", 0) / bt * 100) if bt > 0 else 0
    ap = (ars.get("successes", 0) / at * 100) if at > 0 else 0

    lines = [
        "## 评估对比\n",
        "| 指标 | 上轮 | 本轮 | 变化 |",
        "|------|------|------|------|",
        f"| 通过率 | {bp:.1f}% ({bs.get('successes', 0)}/{bt})"
        f" | {ap:.1f}% ({ars.get('successes', 0)}/{at}) | {ap - bp:+.1f}% |",
        f"| 失败数 | {bs.get('failures', 0)} | {ars.get('failures', 0)}"
        f" | {ars.get('failures', 0) - bs.get('failures', 0):+d} |",
        f"| 错误数 | {bs.get('errors', 0)} | {ars.get('errors', 0)}"
        f" | {ars.get('errors', 0) - bs.get('errors', 0):+d} |",
        "",
    ]

    before_fail = {}
    for r in before["rows"]:
        if _is_failing(r):
            before_fail[_get_description(r)] = r
    after_fail = {}
    for r in after["rows"]:
        if _is_failing(r):
            after_fail[_get_description(r)] = r

    before_descs = set(before_fail.keys())
    after_descs = set(after_fail.keys())

    newly_passed = sorted(before_descs - after_descs)
    newly_failed = sorted(after_descs - before_descs)
    still_failing = sorted(before_descs & after_descs)

    if newly_passed:
        lines.append(f"### 新增通过 ({len(newly_passed)} 个)\n")
        for d in newly_passed:
            lines.append(f"- {d}")
        lines.append("")

    if newly_failed:
        lines.append(f"### 新增失败（回归） ({len(newly_failed)} 个)\n")
        for d in newly_failed:
            cat = classify_failure(after_fail[d])
            lines.append(f"- {d} [{cat}]")
        lines.append("")

    if still_failing:
        lines.append(f"### 持续失败 ({len(still_failing)} 个)\n")
        for d in still_failing:
            cat = classify_failure(after_fail[d])
            lines.append(f"- {d} [{cat}]")
        lines.append("")

    if not newly_passed and not newly_failed and not still_failing:
        lines.append("两轮均全部通过。\n")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="promptfoo 评估结果分析")
    parser.add_argument(
        "results",
        nargs="+",
        help="promptfoo 输出 JSON 文件（1 个为单次分析，2 个为对比）",
    )
    parser.add_argument("-o", "--output", help="输出报告文件路径（默认输出到 stdout）")
    args = parser.parse_args()

    if len(args.results) == 1:
        data = load_results(args.results[0])
        report = analyze_single(data)
    elif len(args.results) == 2:
        before = load_results(args.results[0])
        after = load_results(args.results[1])
        report = analyze_comparison(before, after)
        report += "\n---\n\n" + analyze_single(after)
    else:
        print("错误: 最多支持 2 个文件（单次分析或对比分析）", file=sys.stderr)
        sys.exit(1)

    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"报告已写入: {args.output}")
    else:
        print(report)


if __name__ == "__main__":
    main()

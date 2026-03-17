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
    """根据失败特征分类"""
    response = row.get("response") or {}
    output = response.get("output", "")
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

    grading = row.get("gradingResult") or {}
    components = grading.get("componentResults", [])
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

    return "其他"


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

    failure_groups = defaultdict(list)
    for row in rows:
        is_pass = row.get("success", row.get("pass", True))
        if is_pass:
            continue

        category = classify_failure(row)
        desc = row.get("description", "未命名")
        response = row.get("response") or {}
        output_text = (response.get("output") or "")[:200]

        grading = row.get("gradingResult") or {}
        failed_assertions = []
        for comp in grading.get("componentResults", []):
            if not comp.get("pass"):
                failed_assertions.append(comp.get("reason", "未知原因")[:150])

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
        lines.append(f"- **{category}** ({len(items)} 个): 需要进一步排查")

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
        f"| 错误数 | {bs.get('errors', 0)} | {ars.get('errors', 0)} | {ars.get('errors', 0) - bs.get('errors', 0):+d} |",
        "",
    ]

    before_descs = {r.get("description") for r in before["rows"] if not r.get("success", r.get("pass", True))}
    after_descs = {r.get("description") for r in after["rows"] if not r.get("success", r.get("pass", True))}

    newly_passed = before_descs - after_descs
    newly_failed = after_descs - before_descs
    still_failing = before_descs & after_descs

    if newly_passed:
        lines.append(f"### 新增通过 ✅ ({len(newly_passed)} 个)\n")
        for d in sorted(newly_passed):
            lines.append(f"- {d}")
        lines.append("")

    if newly_failed:
        lines.append(f"### 新增失败（回归）❌ ({len(newly_failed)} 个)\n")
        for d in sorted(newly_failed):
            lines.append(f"- {d}")
        lines.append("")

    if still_failing:
        lines.append(f"### 持续失败 ⚠️ ({len(still_failing)} 个)\n")
        for d in sorted(still_failing):
            lines.append(f"- {d}")
        lines.append("")

    if not newly_passed and not newly_failed and not still_failing:
        lines.append("两轮均全部通过。\n")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="promptfoo 评估结果分析")
    parser.add_argument("results", nargs="+", help="promptfoo 输出 JSON 文件（1 个为单次分析，2 个为对比）")
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

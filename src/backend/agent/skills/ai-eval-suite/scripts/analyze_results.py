#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
promptfoo 评估结果分析脚本

解析 promptfoo eval -o 导出的 JSON，生成失败分析报告。
支持单次分析、两轮纵向对比、多 provider 横向对比。

用法：
  python analyze_results.py evals/<suite>/output/结果文件.json                     # 单次分析
  python analyze_results.py evals/<suite>/output/结果文件.json --by-provider       # 多 provider 横向对比
  python analyze_results.py evals/<suite>/output/before.json evals/<suite>/output/after.json  # 两轮纵向对比
  python analyze_results.py evals/<suite>/output/结果文件.json -o evals/<suite>/output/report.md  # 输出到文件
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

# ---------------------------------------------------------------------------
# JSON 解析（兼容 promptfoo 多种输出格式）
# ---------------------------------------------------------------------------


def _get_description(row: dict) -> str:
    for path in [
        lambda r: r.get("description"),
        lambda r: (r.get("testCase") or {}).get("description"),
        lambda r: (r.get("test") or {}).get("description"),
    ]:
        desc = path(row)
        if desc:
            return desc
    return "未命名"


def _get_provider_label(row: dict) -> str:
    """提取 provider label，兼容 results 列表和 table body"""
    # results 列表格式
    provider = row.get("provider") or {}
    if isinstance(provider, dict):
        return provider.get("label") or provider.get("id") or "unknown"
    if isinstance(provider, str):
        return provider
    # table body 格式 — provider 信息可能在 outputs 的外层 header
    return "unknown"


def _is_failing(row: dict) -> bool:
    if "success" in row:
        return not row["success"]
    if "pass" in row:
        return not row["pass"]
    outputs = row.get("outputs", [])
    return bool(outputs) and not outputs[0].get("pass", True)


def _get_response(row: dict) -> dict:
    if "response" in row:
        return row.get("response") or {}
    outputs = row.get("outputs", [])
    return outputs[0] if outputs else {}


def _get_grading(row: dict) -> dict:
    if "gradingResult" in row:
        return row.get("gradingResult") or {}
    outputs = row.get("outputs", [])
    return outputs[0].get("gradingResult") or {} if outputs else {}


def _get_output_text(row: dict) -> str:
    resp = _get_response(row)
    return resp.get("output") or resp.get("text") or ""


def _get_latency_ms(row: dict) -> float | None:
    """提取延迟（毫秒）"""
    lat = row.get("latencyMs")
    if lat is not None:
        return float(lat)
    resp = _get_response(row)
    meta = resp.get("metadata") or row.get("metadata") or {}
    lat = meta.get("latency_ms") or meta.get("latencyMs")
    return float(lat) if lat is not None else None


def load_results(path: str) -> dict:
    """加载 promptfoo 输出 JSON"""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    root = data.get("results", data)
    stats = root.get("stats", {})

    rows = []
    if "results" in root and isinstance(root["results"], list):
        rows = root["results"]
    elif "table" in root:
        table = root["table"]
        # table body 格式：每行包含 outputs 列表（每个 provider 一列）
        # 需要展平为独立 row
        if "body" in table:
            headers = table.get("head", {}).get("prompts", [])
            for body_row in table["body"]:
                outputs = body_row.get("outputs", [])
                desc = body_row.get("description") or "未命名"
                v = body_row.get("vars", {})
                for i, out in enumerate(outputs):
                    provider_label = "unknown"
                    if i < len(headers):
                        provider_label = headers[i].get("label") or headers[i].get("provider") or "unknown"
                    rows.append(
                        {
                            "description": desc,
                            "vars": v,
                            "success": out.get("pass", True),
                            "response": out,
                            "gradingResult": out.get("gradingResult") or {},
                            "provider": {"label": provider_label},
                            "latencyMs": out.get("latencyMs"),
                        }
                    )

    return {"stats": stats, "rows": rows, "raw": data}


# ---------------------------------------------------------------------------
# 失败分类
# ---------------------------------------------------------------------------


def classify_failure(row: dict) -> str:
    output = _get_output_text(row)
    grading = _get_grading(row)
    components = grading.get("componentResults", [])

    if components:
        for comp in components:
            if comp.get("pass"):
                continue
            atype = (comp.get("assertion") or {}).get("type", "")
            reason = (comp.get("reason") or "").lower()

            if atype in ("llm-rubric", "factuality", "answer-relevance"):
                return "语义不符"
            if "expected" in reason and "key" in reason:
                return "字段缺失"
            if "value" in reason or "mismatch" in reason:
                return "值错误"
            if atype == "is-json":
                return "格式错误"
        return "其他"

    error = row.get("error") or _get_response(row).get("error", "")
    if error:
        el = str(error).lower()
        if any(k in el for k in ("timeout", "timed out")):
            return "超时"
        if any(k in el for k in ("connect", "connection", "network")):
            return "网络错误"
        return "Provider 错误"

    if not output or output.strip() in ("", "{}", "null", "None"):
        return "空输出"

    return "其他"


# ---------------------------------------------------------------------------
# 单次分析
# ---------------------------------------------------------------------------


def analyze_single(data: dict) -> str:
    stats = data["stats"]
    rows = data["rows"]

    total = stats.get("successes", 0) + stats.get("failures", 0) + stats.get("errors", 0)
    successes = stats.get("successes", 0)
    failures = stats.get("failures", 0)
    errors = stats.get("errors", 0)
    pass_rate = (successes / total * 100) if total > 0 else 0

    lines = [
        "## 评估结果摘要\n",
        f"- 总评估数: {total}（断言级别）",
        f"- 通过: {successes} ({pass_rate:.1f}%)",
        f"- 失败: {failures}",
        f"- 错误: {errors}",
        "",
    ]

    token_usage = stats.get("tokenUsage", {})
    if token_usage and token_usage.get("total", 0) > 0:
        lines.append(
            f"- Token: 总计 {token_usage['total']}"
            f" (prompt: {token_usage.get('prompt', 0)},"
            f" completion: {token_usage.get('completion', 0)})"
        )
        lines.append("")

    # 按 (description, provider) 复合 key 分组，处理 repeat > 1
    failure_groups = defaultdict(list)
    for row in rows:
        if not _is_failing(row):
            continue
        category = classify_failure(row)
        desc = _get_description(row)
        provider = _get_provider_label(row)
        output_text = _get_output_text(row)[:200]

        grading = _get_grading(row)
        reasons = [
            comp.get("reason", "未知原因")[:150] for comp in grading.get("componentResults", []) if not comp.get("pass")
        ]
        error = row.get("error") or _get_response(row).get("error", "")
        if error and not reasons:
            reasons.append(str(error)[:150])

        failure_groups[category].append(
            {
                "description": desc,
                "provider": provider,
                "output_preview": output_text,
                "reasons": reasons,
            }
        )

    if not failure_groups:
        lines.append("**全部通过，无失败用例。**\n")
        return "\n".join(lines)

    lines.append("## 失败用例分析\n")
    for category, items in sorted(failure_groups.items(), key=lambda x: -len(x[1])):
        lines.append(f"### {category} ({len(items)} 个)\n")
        for item in items:
            tag = f" [{item['provider']}]" if item["provider"] != "unknown" else ""
            lines.append(f"- **{item['description']}**{tag}")
            if item["output_preview"]:
                lines.append(f"  - 输出: `{item['output_preview']}`")
            for reason in item["reasons"][:3]:
                lines.append(f"  - 原因: {reason}")
            lines.append("")

    lines.append("## 失败分类统计\n")
    for category, items in sorted(failure_groups.items(), key=lambda x: -len(x[1])):
        lines.append(f"- **{category}**: {len(items)} 个")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 两轮纵向对比（使用复合 key）
# ---------------------------------------------------------------------------


def _build_fail_map(rows: list) -> dict[tuple[str, str], dict]:
    """用 (description, provider) 复合 key 构建失败映射。
    repeat > 1 时同一 key 可能出现多次，取最后一次。"""
    fail_map = {}
    for row in rows:
        if _is_failing(row):
            key = (_get_description(row), _get_provider_label(row))
            fail_map[key] = row
    return fail_map


def analyze_comparison(before: dict, after: dict) -> str:
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

    before_fail = _build_fail_map(before["rows"])
    after_fail = _build_fail_map(after["rows"])

    before_keys = set(before_fail.keys())
    after_keys = set(after_fail.keys())

    newly_passed = sorted(before_keys - after_keys)
    newly_failed = sorted(after_keys - before_keys)
    still_failing = sorted(before_keys & after_keys)

    if newly_passed:
        lines.append(f"### 新增通过 ({len(newly_passed)} 个)\n")
        for desc, prov in newly_passed:
            tag = f" [{prov}]" if prov != "unknown" else ""
            lines.append(f"- {desc}{tag}")
        lines.append("")

    if newly_failed:
        lines.append(f"### 新增失败（回归） ({len(newly_failed)} 个)\n")
        for key in newly_failed:
            desc, prov = key
            cat = classify_failure(after_fail[key])
            tag = f" [{prov}]" if prov != "unknown" else ""
            lines.append(f"- {desc}{tag} [{cat}]")
        lines.append("")

    if still_failing:
        lines.append(f"### 持续失败 ({len(still_failing)} 个)\n")
        for key in still_failing:
            desc, prov = key
            cat = classify_failure(after_fail[key])
            tag = f" [{prov}]" if prov != "unknown" else ""
            lines.append(f"- {desc}{tag} [{cat}]")
        lines.append("")

    if not newly_passed and not newly_failed and not still_failing:
        lines.append("两轮均全部通过。\n")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 多 provider 横向对比（--by-provider）
# ---------------------------------------------------------------------------


def analyze_by_provider(data: dict) -> str:
    """按 provider 维度横向对比：通过率、独有失败、延迟"""
    rows = data["rows"]

    # 按 provider 聚合
    provider_stats: dict[str, dict] = defaultdict(
        lambda: {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "fail_descs": set(),
            "latencies": [],
        }
    )

    for row in rows:
        prov = _get_provider_label(row)
        ps = provider_stats[prov]
        ps["total"] += 1
        if _is_failing(row):
            ps["failed"] += 1
            ps["fail_descs"].add(_get_description(row))
        else:
            ps["passed"] += 1
        lat = _get_latency_ms(row)
        if lat is not None:
            ps["latencies"].append(lat)

    if not provider_stats:
        return "无 provider 数据。\n"

    providers = sorted(provider_stats.keys())

    # 汇总表
    lines = ["## 多模型横向对比\n"]
    header = "| 模型 | 通过率 | 通过 | 失败 |"
    sep = "|------|--------|------|------|"
    has_latency = any(provider_stats[p]["latencies"] for p in providers)
    if has_latency:
        header += " 平均延迟 | P95 延迟 |"
        sep += "----------|---------|"

    lines.extend([header, sep])

    for prov in providers:
        ps = provider_stats[prov]
        rate = (ps["passed"] / ps["total"] * 100) if ps["total"] > 0 else 0
        row_str = f"| {prov} | {rate:.1f}% | {ps['passed']} | {ps['failed']} |"
        if has_latency:
            lats = ps["latencies"]
            if lats:
                avg = sum(lats) / len(lats)
                p95 = sorted(lats)[int(len(lats) * 0.95)] if len(lats) >= 2 else lats[-1]
                row_str += f" {avg:.0f}ms | {p95:.0f}ms |"
            else:
                row_str += " - | - |"
        lines.append(row_str)

    lines.append("")

    # 独有失败分析
    all_fail_sets = {p: provider_stats[p]["fail_descs"] for p in providers}
    lines.append("### 独有失败（仅该模型失败的用例）\n")

    has_unique = False
    for prov in providers:
        others = set()
        for other_prov in providers:
            if other_prov != prov:
                others |= all_fail_sets[other_prov]
        unique = all_fail_sets[prov] - others
        if unique:
            has_unique = True
            lines.append(f"**{prov}** ({len(unique)} 个):")
            for desc in sorted(unique):
                lines.append(f"- {desc}")
            lines.append("")

    if not has_unique:
        lines.append("无独有失败（所有失败在多个模型中共现）。\n")

    # 共同失败
    if len(providers) > 1:
        common = (
            set.intersection(*(all_fail_sets[p] for p in providers))
            if all(all_fail_sets[p] for p in providers)
            else set()
        )
        if common:
            lines.append(f"### 共同失败（所有模型均失败，{len(common)} 个）\n")
            for desc in sorted(common):
                lines.append(f"- {desc}")
            lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="promptfoo 评估结果分析")
    parser.add_argument("results", nargs="+", help="JSON 文件（1个单次，2个对比）")
    parser.add_argument("-o", "--output", help="输出报告路径（默认 stdout）")
    parser.add_argument("--by-provider", action="store_true", help="按 provider 维度横向对比（通过率/独有失败/延迟）")
    args = parser.parse_args()

    if len(args.results) == 1:
        data = load_results(args.results[0])
        report = analyze_single(data)
        if args.by_provider:
            report += "\n---\n\n" + analyze_by_provider(data)
    elif len(args.results) == 2:
        before = load_results(args.results[0])
        after = load_results(args.results[1])
        report = analyze_comparison(before, after)
        report += "\n---\n\n" + analyze_single(after)
        if args.by_provider:
            report += "\n---\n\n" + analyze_by_provider(after)
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

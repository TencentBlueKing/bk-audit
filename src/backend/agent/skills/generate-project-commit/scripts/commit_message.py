#!/usr/bin/env python3
"""保留 Python 渲染及旧命令入口，标题规则委托给同目录 sh 校验器。

提交 hook 直接运行 shell，不需要项目 Python；正文 bullet 仅为生成建议。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

TYPES = ("feat", "fix", "docs", "style", "refactor", "perf", "test", "chore")
VALIDATOR = Path(__file__).with_suffix(".sh")


def normalize_body_item(item: str) -> str:
    """将生成正文规范为 bullet，忽略空内容。"""
    item = item.strip()
    if not item:
        return ""
    if item.startswith("- "):
        return item
    if item.startswith("-"):
        return f"- {item[1:].strip()}"
    return f"- {item}"


def build_subject(commit_type: str, summary: str, tracker: str) -> str:
    """生成单行标题并通过共享 shell 规则验证，非法输入抛出 ValueError。"""
    commit_type = commit_type.strip()
    summary = summary.strip()
    tracker = tracker.strip()

    if commit_type not in TYPES:
        raise ValueError(f"invalid type: {commit_type}")
    if not summary or "\n" in summary:
        raise ValueError("summary must be a non-empty single line")
    if not tracker or "\n" in tracker:
        raise ValueError("tracker must be a non-empty single line")
    if any(character.isspace() for character in tracker):
        raise ValueError("tracker must be a single token")

    subject = f"{commit_type}: {summary} {tracker}"
    validate_message(subject, allow_merge=False)
    return subject


def render_message(args: argparse.Namespace) -> str:
    """渲染合法标题及可选 bullet 正文。"""
    subject = build_subject(args.type, args.summary, args.tracker)
    body_items = [normalize_body_item(item) for item in args.body]
    body_items = [item for item in body_items if item]

    message = subject
    if body_items:
        message = f"{message}\n\n" + "\n".join(body_items)

    validate_message(message, allow_merge=False)
    return message


def classify_subject(subject: str, allow_merge: bool) -> str | None:
    """委托 shell 返回标题类型，非法标题返回 None。"""
    arguments = ["sh", str(VALIDATOR), "classify"]
    if allow_merge:
        arguments.append("--allow-merge")
    result = subprocess.run(arguments, input=subject, text=True, capture_output=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def validate_message(message: str, allow_merge: bool) -> None:
    """校验标题，不限制正文组织；空标题或非法标题抛出 ValueError。"""
    lines = message.splitlines()
    if not lines or not lines[0].strip():
        raise ValueError("commit message is empty")

    subject = lines[0].strip()
    if not classify_subject(subject, allow_merge):
        raise ValueError(f"invalid subject: {subject}")


def read_message(args: argparse.Namespace) -> str:
    """读取旧 CLI 支持的 message 文件、参数或 stdin。"""
    if args.message_file:
        return Path(args.message_file).read_text(encoding="utf-8")
    if args.message:
        return args.message
    return sys.stdin.read()


def validate_command(args: argparse.Namespace) -> int:
    """执行兼容校验入口，成功返回 0。"""
    message = read_message(args)
    validate_message(message, allow_merge=args.allow_merge)
    print("Valid commit message")
    return 0


def check_log_command(args: argparse.Namespace) -> int:
    """逐项检查最近的提交标题，首个非法标题返回 1。"""
    result = subprocess.run(
        ["git", "log", "-n", str(args.limit), "--pretty=format:%s"],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    for index, subject in enumerate(result.stdout.splitlines(), start=1):
        kind = classify_subject(subject, allow_merge=True)
        if not kind:
            print(f"[{index}] Invalid: {subject}", file=sys.stderr)
            return 1
        print(f"[{index}] {kind}: {subject}")
    return 0


def parse_args() -> argparse.Namespace:
    """解析兼容渲染、校验和历史检查参数。"""
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    render = subparsers.add_parser("render", help="render a compliant commit message")
    render.add_argument("--type", required=True, choices=TYPES)
    render.add_argument("--summary", required=True)
    render.add_argument("--tracker", required=True, help="#1234 or --story=1234")
    render.add_argument("--body", action="append", default=[], help="body bullet; repeatable")

    validate = subparsers.add_parser("validate", help="validate a commit message")
    validate.add_argument("--message")
    validate.add_argument("--message-file")
    validate.add_argument("--allow-merge", action="store_true")

    check_log = subparsers.add_parser("check-log", help="validate recent git commit subjects")
    check_log.add_argument("-n", "--limit", type=int, default=20)

    return parser.parse_args()


def main() -> int:
    """执行兼容命令，预期校验失败返回非零状态。"""
    args = parse_args()
    try:
        if args.command == "render":
            print(render_message(args))
            return 0
        if args.command == "validate":
            return validate_command(args)
        if args.command == "check-log":
            return check_log_command(args)
    except (subprocess.CalledProcessError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Render and validate bk-audit commit messages."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

TYPES = ("feat", "fix", "docs", "style", "refactor", "perf", "test", "chore")
TYPE_PATTERN = "|".join(TYPES)
GITHUB_PATTERN = re.compile(rf"^({TYPE_PATTERN}):\s.+\s#[0-9]+$")
TAPD_PATTERN = re.compile(rf"^({TYPE_PATTERN}):\s.+\s--[^=\s]+=[0-9]+$")
MERGE_PATTERN = re.compile(r"^Merge")


def normalize_body_item(item: str) -> str:
    item = item.strip()
    if not item:
        return ""
    if item.startswith("- "):
        return item
    if item.startswith("-"):
        return f"- {item[1:].strip()}"
    return f"- {item}"


def build_subject(commit_type: str, summary: str, tracker: str) -> str:
    commit_type = commit_type.strip()
    summary = summary.strip()
    tracker = tracker.strip()

    if commit_type not in TYPES:
        raise ValueError(f"invalid type: {commit_type}")
    if not summary or "\n" in summary:
        raise ValueError("summary must be a non-empty single line")
    if not tracker or "\n" in tracker:
        raise ValueError("tracker must be a non-empty single line")

    if tracker.startswith("#"):
        if not re.fullmatch(r"#[0-9]+", tracker):
            raise ValueError("github tracker must look like #1234")
    elif tracker.startswith("--"):
        if not re.fullmatch(r"--[^=\s]+=[0-9]+", tracker):
            raise ValueError("tapd tracker must look like --story=1234")
    else:
        raise ValueError("tracker must start with # or --")

    return f"{commit_type}: {summary} {tracker}"


def render_message(args: argparse.Namespace) -> str:
    subject = build_subject(args.type, args.summary, args.tracker)
    body_items = [normalize_body_item(item) for item in args.body]
    body_items = [item for item in body_items if item]

    message = subject
    if body_items:
        message = f"{message}\n\n" + "\n".join(body_items)

    validate_message(message, allow_merge=False)
    return message


def classify_subject(subject: str, allow_merge: bool) -> str | None:
    if GITHUB_PATTERN.match(subject):
        return "Github Type"
    if TAPD_PATTERN.match(subject):
        return "TAPD Type"
    if allow_merge and MERGE_PATTERN.match(subject):
        return "Merge Type"
    return None


def validate_message(message: str, allow_merge: bool) -> None:
    lines = message.splitlines()
    if not lines or not lines[0].strip():
        raise ValueError("commit message is empty")

    subject = lines[0].strip()
    subject_kind = classify_subject(subject, allow_merge)
    if not subject_kind:
        raise ValueError(f"invalid subject: {subject}")

    if subject_kind == "Merge Type":
        return
    if len(lines) == 1:
        raise ValueError("commit message body must contain at least one bullet")
    if lines[1].strip():
        raise ValueError("second line must be blank before body")

    has_body_bullet = False
    for line_no, line in enumerate(lines[2:], start=3):
        if not line.strip():
            continue
        if not line.startswith("- "):
            raise ValueError(f"body line {line_no} must start with '- '")
        has_body_bullet = True
    if not has_body_bullet:
        raise ValueError("commit message body must contain at least one bullet")


def read_message(args: argparse.Namespace) -> str:
    if args.message_file:
        return Path(args.message_file).read_text(encoding="utf-8")
    if args.message:
        return args.message
    return sys.stdin.read()


def validate_command(args: argparse.Namespace) -> int:
    message = read_message(args)
    validate_message(message, allow_merge=args.allow_merge)
    print("Valid commit message")
    return 0


def check_log_command(args: argparse.Namespace) -> int:
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

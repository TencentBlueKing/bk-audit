# -*- coding: utf-8 -*-
"""从 agent 最终输出中抽出用户可见正文。

只拆两类通用包装：LangChain Final Answer / action_input，以及 ```markdown / ```md 整篇围栏。
没有这些包装时原样返回，不依赖一级标题或中文思考句。
"""

import json
import re

_FINAL_ANSWER_ACTIONS = {"final answer", "final_answer"}
_MARKDOWN_FENCE_LANGS = frozenset({"markdown", "md"})
_JSON_FENCE_PATTERN = re.compile(r"```json\s*(.*?)```", re.DOTALL | re.IGNORECASE)
_PROTOCOL_PREFIX_LINE_PATTERN = re.compile(r"^(?:Thought|Action|Observation)\s*:", re.IGNORECASE)
_XML_FINAL_ANSWER_PATTERN = re.compile(
    r"<final_answer>\s*(.*?)\s*</final_answer>",
    re.DOTALL | re.IGNORECASE,
)
_FINAL_ANSWER_LABEL_PATTERN = re.compile(r"(?im)^(?:Final\s+Answer|action_input)\s*:\s*")
_WRAPPER_ONLY_LINE_PATTERN = re.compile(
    r"^(?:" r"action_input" r"|final\s+answer" r"|action\s*:\s*final\s+answer" r")\s*:?\s*$",
    re.IGNORECASE,
)
_FENCE_LINE_PATTERN = re.compile(r"^```([\w+-]*)[ \t]*$")
_DOCUMENT_SIGNAL_PATTERN = re.compile(r"(?m)^[ \t]{0,3}#{1,6}\s+\S|^\s*\|.+\|")


def extract_markdown_report_body(content: str) -> str:
    """抽出 Final Answer / markdown 围栏中的正文；无包装则原样返回。"""
    if not isinstance(content, str) or not content:
        return content
    current = content
    for _ in range(4):
        nxt = _extract_once(current)
        if nxt == current:
            break
        if not str(nxt).strip():
            return content
        current = nxt
    return current


def _extract_once(content: str) -> str:
    extracted = _extract_final_answer_payload(content)
    if extracted is not None:
        return extracted
    extracted = _extract_wrapping_markdown_fence(content)
    if extracted is not None:
        return extracted
    return _strip_leading_wrapper_lines(content)


def _extract_final_answer_payload(content: str) -> str | None:
    payload = _extract_final_answer_json(content)
    if payload is not None:
        return payload
    payload = _extract_final_answer_xml(content)
    if payload is not None:
        return payload
    return _extract_final_answer_label(content)


def _is_embedded_in_document(prefix: str) -> bool:
    return bool(prefix.strip() and _looks_like_document(prefix))


def _extract_final_answer_json(content: str) -> str | None:
    last = None
    decoder = json.JSONDecoder()
    for start in _json_object_starts(content):
        try:
            payload, _ = decoder.raw_decode(content[start:])
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        action = str(payload.get("action") or "").strip().lower()
        if action not in _FINAL_ANSWER_ACTIONS:
            continue
        if _is_embedded_in_document(content[:start]):
            continue
        action_input = payload.get("action_input", "")
        if isinstance(action_input, str):
            last = action_input
        elif action_input:
            last = json.dumps(action_input, ensure_ascii=False)
    if last is not None and last.strip() and last != content:
        return last
    return None


def _extract_final_answer_xml(content: str) -> str | None:
    last = None
    for match in _XML_FINAL_ANSWER_PATTERN.finditer(content):
        if _is_embedded_in_document(content[: match.start()]):
            continue
        inner = match.group(1)
        if inner.strip():
            last = inner
    if last is not None and last != content:
        return last
    return None


def _json_object_starts(content: str) -> list[int]:
    starts = []
    for match in _JSON_FENCE_PATTERN.finditer(content):
        idx = match.group(1).find("{")
        if idx >= 0:
            starts.append(match.start(1) + idx)
    if re.search(r"Final\s+Answer|final_answer", content, re.IGNORECASE):
        starts.extend(match.start() for match in re.finditer(r"\{", content))
    return starts


def _extract_final_answer_label(content: str) -> str | None:
    matches = list(_FINAL_ANSWER_LABEL_PATTERN.finditer(content))
    if not matches:
        return None
    match = matches[-1]
    rest = content[match.end() :]
    prefix = content[: match.start()]
    if not rest.strip():
        return None
    if prefix.strip() and not _is_protocol_prefix(prefix):
        return None
    return rest


def _is_protocol_prefix(prefix: str) -> bool:
    for line in prefix.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if _WRAPPER_ONLY_LINE_PATTERN.match(stripped):
            continue
        if _PROTOCOL_PREFIX_LINE_PATTERN.match(stripped):
            continue
        return False
    return True


def _looks_like_document(text: str) -> bool:
    return bool(_DOCUMENT_SIGNAL_PATTERN.search(text))


def _extract_wrapping_markdown_fence(content: str) -> str | None:
    lines = content.splitlines(keepends=True)
    opens = [index for index, line in enumerate(lines) if _fence_language(line) in _MARKDOWN_FENCE_LANGS]
    if not opens:
        return None
    start = opens[-1]
    close = None
    for index in range(start + 1, len(lines)):
        if _fence_language(lines[index]) == "":
            close = index
    if close is None:
        end = len(lines)
    else:
        if "".join(lines[close + 1 :]).strip():
            return None
        end = close
    prefix = "".join(lines[:start])
    payload = "".join(lines[start + 1 : end])
    if not payload.strip():
        return None
    if prefix.strip() and _looks_like_document(prefix):
        return None
    return payload


def _fence_language(line: str) -> str | None:
    match = _FENCE_LINE_PATTERN.match(line.strip())
    if not match:
        return None
    return (match.group(1) or "").lower()


def _strip_leading_wrapper_lines(content: str) -> str:
    lines = content.splitlines(keepends=True)
    index = 0
    changed = False
    while index < len(lines):
        stripped = lines[index].strip()
        if not stripped:
            index += 1
            continue
        if _WRAPPER_ONLY_LINE_PATTERN.match(stripped):
            index += 1
            changed = True
            continue
        break
    if not changed:
        return content
    return "".join(lines[index:])

# -*- coding: utf-8 -*-
"""
promptfoo 自定义断言函数集 — NL2RiskFilter

每个函数签名：(output: str, context: dict) -> dict | bool | float
  - output : provider 返回的 output 字符串（JSON 格式的 filter_conditions）
  - context: 包含 vars（测试变量）、test（测试定义）、prompt 等

返回值约定（promptfoo GradingResult）：
  {"pass": bool, "score": float, "reason": str}

用法（promptfooconfig.yaml）：
  assert:
    - type: python
      value: file://assertions/check_filters.py:has_expected_keys
"""

import json
import os
import sys
import warnings

warnings.filterwarnings("ignore", message="pkg_resources is deprecated")

_backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
if _backend_root not in sys.path:
    sys.path.insert(0, _backend_root)

_django_ready = False


def _ensure_django():
    global _django_ready
    if _django_ready:
        return
    os.chdir(_backend_root)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")
    import django

    django.setup()
    _django_ready = True


def _parse_output(output):
    if not output:
        return {}
    if isinstance(output, dict):
        return output
    try:
        result = json.loads(output)
        return result if isinstance(result, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def has_expected_keys(output, context):
    """验证 filter_conditions 包含 vars.expected_keys 指定的所有顶层字段"""
    filters = _parse_output(output)
    expected_raw = context.get("vars", {}).get("expected_keys", "[]")
    expected_keys = json.loads(expected_raw) if isinstance(expected_raw, str) else expected_raw

    if not expected_keys:
        return {"pass": True, "score": 1.0, "reason": "无需检查的字段"}

    missing = [k for k in expected_keys if k not in filters]
    if missing:
        return {
            "pass": False,
            "score": round(1 - len(missing) / len(expected_keys), 2),
            "reason": f"缺少字段: {missing}，实际字段: {list(filters.keys())}",
        }
    return {"pass": True, "score": 1.0, "reason": "所有期望字段均存在"}


def field_value_match(output, context):
    """验证指定字段的值与期望匹配"""
    filters = _parse_output(output)
    expected_raw = context.get("vars", {}).get("expected_values", "{}")
    expected_values = json.loads(expected_raw) if isinstance(expected_raw, str) else expected_raw

    if not expected_values:
        return {"pass": True, "score": 1.0, "reason": "无需检查的字段值"}

    total = len(expected_values)
    matched = 0
    mismatches = []

    for key, expected_val in expected_values.items():
        actual_val = filters.get(key)
        if actual_val == expected_val:
            matched += 1
        else:
            mismatches.append(f"{key}: 期望={expected_val!r}, 实际={actual_val!r}")

    score = round(matched / total, 2) if total else 1.0
    if mismatches:
        return {"pass": False, "score": score, "reason": "; ".join(mismatches)}
    return {"pass": True, "score": 1.0, "reason": "所有字段值匹配"}


def has_event_filter_field(output, context):
    """验证 event_filters 数组中存在指定 field 的条目

    同时匹配 field 名和 display_name，两者都视为正确。
    """
    filters = _parse_output(output)
    event_filters = filters.get("event_filters", [])

    expected_raw = context.get("vars", {}).get("expected_event_fields", "[]")
    expected_fields = json.loads(expected_raw) if isinstance(expected_raw, str) else expected_raw

    if not expected_fields:
        return {"pass": True, "score": 1.0, "reason": "无需检查的事件字段"}

    actual_fields = set()
    actual_display_names = set()
    for ef in event_filters:
        if isinstance(ef, dict):
            actual_fields.add(ef.get("field", ""))
            dn = ef.get("display_name", "")
            actual_display_names.add(dn)
            if "(" in dn:
                actual_display_names.add(dn.split("(")[0])

    all_identifiers = actual_fields | actual_display_names
    missing = [f for f in expected_fields if f not in all_identifiers]

    if missing:
        return {
            "pass": False,
            "score": round(1 - len(missing) / len(expected_fields), 2),
            "reason": f"event_filters 缺少字段: {missing}，实际: field={sorted(actual_fields)}, "
            f"display={sorted(actual_display_names)}",
        }
    return {"pass": True, "score": 1.0, "reason": "event_filters 包含所有期望字段"}


def is_non_empty_filter(output, context):
    """验证 AI 返回了有效的 filter_conditions（非空 dict）"""
    filters = _parse_output(output)
    if filters:
        return {"pass": True, "score": 1.0, "reason": f"返回了 {len(filters)} 个筛选字段"}
    return {"pass": False, "score": 0.0, "reason": "filter_conditions 为空，AI 可能未理解查询"}


def expect_empty_or_message(output, context):
    """验证无效/模糊输入时，AI 不会生成错误的筛选条件"""
    filters = _parse_output(output)
    if not filters:
        return {"pass": True, "score": 1.0, "reason": "正确返回空条件"}
    return {
        "pass": False,
        "score": 0.0,
        "reason": f"无效输入不应生成筛选条件，但得到: {list(filters.keys())}",
    }


def passes_serializer_validation(output, context):
    """验证 filter_conditions 能通过 ListRiskRequestSerializer 校验"""
    filters = _parse_output(output)
    if not filters:
        return {"pass": True, "score": 1.0, "reason": "空条件无需校验"}

    try:
        _ensure_django()
        from services.web.risk.serializers import ListRiskRequestSerializer

        serializer = ListRiskRequestSerializer(data=filters)
        if serializer.is_valid():
            return {"pass": True, "score": 1.0, "reason": "通过 ListRiskRequestSerializer 校验"}
        errors = serializer.errors
        return {
            "pass": False,
            "score": 0.0,
            "reason": f"Serializer 校验失败: {errors}",
        }
    except Exception as exc:
        return {"pass": False, "score": 0.0, "reason": f"校验异常: {exc}"}


def check_message_on_empty(output, context):
    """当 filter_conditions 为空时，验证 provider 返回的 metadata.message 非空"""
    filters = _parse_output(output)
    if filters:
        return {"pass": True, "score": 1.0, "reason": "有筛选条件，无需检查 message"}

    provider_resp = context.get("providerResponse", {}) or {}
    metadata = provider_resp.get("metadata", {}) or {}
    message = metadata.get("message", "")
    if message:
        return {"pass": True, "score": 1.0, "reason": f"message 非空: {message[:50]}..."}
    return {
        "pass": False,
        "score": 0.5,
        "reason": "filter_conditions 为空但 message 也为空，AI 未提供有用信息",
    }


def partial_match(output, context):
    """综合评分断言：对 expected_keys 和 expected_values 做部分匹配评分

    评分规则：
      - 每个 expected_key 存在 +1 分
      - 每个 expected_value 匹配 +1 分
      - pass = 总分 >= 0.5
    """
    filters = _parse_output(output)

    expected_keys_raw = context.get("vars", {}).get("expected_keys", "[]")
    expected_keys = json.loads(expected_keys_raw) if isinstance(expected_keys_raw, str) else expected_keys_raw
    expected_values_raw = context.get("vars", {}).get("expected_values", "{}")
    expected_values = json.loads(expected_values_raw) if isinstance(expected_values_raw, str) else expected_values_raw

    total = 0
    scored = 0
    details = []

    for k in expected_keys or []:
        total += 1
        if k in filters:
            scored += 1
            details.append(f"✓ 字段 {k} 存在")
        else:
            details.append(f"✗ 字段 {k} 缺失")

    for k, v in (expected_values or {}).items():
        total += 1
        actual = filters.get(k)
        if actual == v:
            scored += 1
            details.append(f"✓ {k}={v!r}")
        else:
            details.append(f"✗ {k}: 期望={v!r}, 实际={actual!r}")

    if total == 0:
        return {"pass": True, "score": 1.0, "reason": "无需检查"}

    score = round(scored / total, 2)
    passed = score >= 0.5
    return {
        "pass": passed,
        "score": score,
        "reason": f"部分匹配 {scored}/{total}: " + "; ".join(details),
    }

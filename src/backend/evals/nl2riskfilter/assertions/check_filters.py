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

    匹配策略（由宽到严）：
      1. 精确匹配 field 或 display_name
      2. 模糊匹配：期望值是实际值的子串，或实际值是期望值的子串
         例如期望"操作人"能匹配到"操作人账号"
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

    missing = []
    for expected in expected_fields:
        # 精确匹配
        if expected in all_identifiers:
            continue
        # 模糊匹配：期望值包含在实际值中，或实际值包含在期望值中
        fuzzy_matched = any(expected in actual or actual in expected for actual in all_identifiers if actual)
        if not fuzzy_matched:
            missing.append(expected)

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


def check_time_range(output, context):
    """验证 start_time/end_time 是否在合理范围内

    通过 vars 配置：
      expected_time_delta_days: start_time 距今的天数（如 "7" 表示最近一周）
      time_tolerance_hours: 容差小时数（默认 "2"）

    验证逻辑：
      - start_time 应接近 now - delta_days（±tolerance）
      - end_time 应接近 now（±tolerance）
    """
    from datetime import datetime, timedelta

    filters = _parse_output(output)
    vars_ = context.get("vars", {})

    delta_days_str = vars_.get("expected_time_delta_days")
    if not delta_days_str:
        return {"pass": True, "score": 1.0, "reason": "未配置 expected_time_delta_days，跳过时间验证"}

    delta_days = float(delta_days_str)
    tolerance_hours = float(vars_.get("time_tolerance_hours", "2"))
    tolerance = timedelta(hours=tolerance_hours)
    now = datetime.now()

    details = []
    total = 0
    passed = 0

    start_str = filters.get("start_time")
    if start_str:
        total += 1
        try:
            start_time = datetime.fromisoformat(start_str)
            expected_start = now - timedelta(days=delta_days)
            diff = abs(start_time - expected_start)
            if diff <= tolerance:
                passed += 1
                details.append(f"✓ start_time 偏差 {diff} 在容差 ±{tolerance_hours}h 内")
            else:
                details.append(f"✗ start_time={start_str}, 期望≈{expected_start.isoformat()}, 偏差 {diff}")
        except ValueError:
            details.append(f"✗ start_time 格式无效: {start_str}")
    else:
        total += 1
        details.append("✗ start_time 缺失")

    end_str = filters.get("end_time")
    if end_str:
        total += 1
        try:
            end_time = datetime.fromisoformat(end_str)
            diff = abs(end_time - now)
            if diff <= tolerance:
                passed += 1
                details.append(f"✓ end_time 偏差 {diff} 在容差 ±{tolerance_hours}h 内")
            else:
                details.append(f"✗ end_time={end_str}, 期望≈{now.isoformat()}, 偏差 {diff}")
        except ValueError:
            details.append(f"✗ end_time 格式无效: {end_str}")
    else:
        total += 1
        details.append("✗ end_time 缺失")

    score = round(passed / total, 2) if total else 1.0
    return {
        "pass": score >= 0.5,
        "score": score,
        "reason": f"时间验证 {passed}/{total}: " + "; ".join(details),
    }


def check_event_content(output, context):
    """验证 event_content 字段存在且包含期望关键词

    通过 vars 配置：
      expected_event_content: 期望 event_content 包含的关键词
    """
    filters = _parse_output(output)
    vars_ = context.get("vars", {})

    expected_keyword = vars_.get("expected_event_content", "")
    if not expected_keyword:
        return {"pass": True, "score": 1.0, "reason": "未配置 expected_event_content，跳过"}

    event_content = filters.get("event_content", "")
    if not event_content:
        return {
            "pass": False,
            "score": 0.0,
            "reason": f"event_content 缺失，期望含 '{expected_keyword}'，实际字段: {list(filters.keys())}",
        }

    if expected_keyword.lower() in event_content.lower():
        return {
            "pass": True,
            "score": 1.0,
            "reason": f"event_content='{event_content}' 包含 '{expected_keyword}'",
        }
    return {
        "pass": False,
        "score": 0.5,
        "reason": f"event_content='{event_content}' 不含期望关键词 '{expected_keyword}'",
    }


def check_has_report(output, context):
    """验证 has_report 字段存在且值正确

    通过 vars 配置：
      expected_has_report: "true" 或 "false"
    """
    filters = _parse_output(output)
    vars_ = context.get("vars", {})

    expected_raw = vars_.get("expected_has_report", "")
    if not expected_raw:
        return {"pass": True, "score": 1.0, "reason": "未配置 expected_has_report，跳过"}

    expected_val = expected_raw.lower() == "true"
    actual_val = filters.get("has_report")

    if actual_val is None:
        return {
            "pass": False,
            "score": 0.0,
            "reason": f"has_report 缺失，期望 {expected_val}，实际字段: {list(filters.keys())}",
        }

    if actual_val == expected_val or str(actual_val).lower() == str(expected_val).lower():
        return {"pass": True, "score": 1.0, "reason": f"has_report={actual_val} 匹配"}
    return {
        "pass": False,
        "score": 0.0,
        "reason": f"has_report 期望={expected_val}, 实际={actual_val}",
    }


def check_sort(output, context):
    """验证 sort 数组包含期望的排序字段

    通过 vars 配置：
      expected_sort: JSON 数组字符串，如 '["-risk_level"]'
    """
    filters = _parse_output(output)
    vars_ = context.get("vars", {})

    expected_raw = vars_.get("expected_sort")
    if not expected_raw:
        return {"pass": True, "score": 1.0, "reason": "未配置 expected_sort，跳过排序验证"}

    expected_sort = json.loads(expected_raw) if isinstance(expected_raw, str) else expected_raw
    actual_sort = filters.get("sort", [])

    if not isinstance(actual_sort, list):
        return {"pass": False, "score": 0.0, "reason": f"sort 不是数组: {actual_sort!r}"}

    missing = [s for s in expected_sort if s not in actual_sort]
    if missing:
        return {
            "pass": False,
            "score": round(1 - len(missing) / len(expected_sort), 2),
            "reason": f"sort 缺少: {missing}，实际: {actual_sort}",
        }
    return {"pass": True, "score": 1.0, "reason": f"sort 匹配: {actual_sort}"}

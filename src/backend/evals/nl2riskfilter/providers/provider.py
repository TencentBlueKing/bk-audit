# -*- coding: utf-8 -*-
"""
promptfoo custom provider — NL2RiskFilter

直接调用 NL2RiskFilter().request()，走完整业务链路：
  RequestSerializer → perform_request → build_nl2risk_user_message
  → chat_completion → extract_json_from_text → ResponseSerializer

用法（promptfooconfig.yaml）：
  providers:
    - id: python:providers/provider.py
      label: NL2RiskFilter-Real
      config:
        username: '{{env.EVAL_USERNAME}}'
"""

import json
import os
import sys
import time
import warnings

warnings.filterwarnings("ignore", message="pkg_resources is deprecated")

_backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
if _backend_root not in sys.path:
    sys.path.insert(0, _backend_root)

os.chdir(_backend_root)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")

import django  # noqa: E402

django.setup()

from unittest.mock import patch  # noqa: E402

from services.web.risk.resources.risk import NL2RiskFilter  # noqa: E402


def call_api(prompt, options, context):
    """promptfoo 调用入口"""
    vars_ = context.get("vars", {})
    config = options.get("config", {})

    query = vars_.get("query", prompt)
    tags = json.loads(vars_.get("tags", "[]"))
    strategies = json.loads(vars_.get("strategies", "[]"))
    thread_id = vars_.get("thread_id", "")

    request_data = {"query": query, "tags": tags, "strategies": strategies}
    if thread_id:
        request_data["thread_id"] = thread_id

    username = config.get("username") or os.environ.get("EVAL_USERNAME")
    if not username:
        return {"error": "EVAL_USERNAME 环境变量未设置，请 export EVAL_USERNAME=your_rtx"}

    resource = NL2RiskFilter()

    start = time.time()
    try:
        with patch(
            "services.web.risk.resources.risk.get_request_username",
            return_value=username,
        ):
            result = resource.request(request_data)
    except Exception as exc:
        return {"error": f"NL2RiskFilter 调用失败: {exc}"}
    latency_ms = round((time.time() - start) * 1000)

    filter_conditions = result.get("filter_conditions", {})
    return {
        "output": json.dumps(filter_conditions, ensure_ascii=False) if filter_conditions else "",
        "metadata": {
            "thread_id": result.get("thread_id", ""),
            "message": result.get("message", ""),
            "latency_ms": latency_ms,
            "raw_result": result,
        },
    }

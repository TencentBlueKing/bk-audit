# -*- coding: utf-8 -*-
"""
promptfoo custom provider — NL2RiskFilter

直接调用 NL2RiskFilter().request()，走完整业务链路：
  RequestSerializer → perform_request → build_nl2risk_user_message
  → chat_completion → extract_json_from_text → ResponseSerializer

支持通过 config 注入 model / non_thinking_llm / system_prompt 到 execute_kwargs，
用于多模型对比评测（不修改业务代码）。

system_prompt 默认自动读取 services/web/ai/prompts/nl2riskfilter/system_prompt.md，
确保评测始终使用最新的本地 prompt 版本。

用法（promptfooconfig.yaml）：
  providers:
    - id: python:providers/provider.py
      label: dsv32
      config:
        username: '{{env.BKAPP_EVAL_USERNAME}}'
        model: 'dsv32'
        non_thinking_llm: 'dsv32'

    - id: python:providers/provider.py
      label: qwen3-235B
      config:
        username: '{{env.BKAPP_EVAL_USERNAME}}'
        model: 'qwen3-235B'
        non_thinking_llm: 'qwen3-235B'
"""

import json
import os
import sys
import time
import warnings
from functools import wraps

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

_CHAT_COMPLETION_PATH = "services.web.risk.resources.risk.api.bk_plugins_ai_agent.chat_completion"

_SYSTEM_PROMPT_PATH = os.path.join(_backend_root, "services/web/ai/prompts/nl2riskfilter/system_prompt.md")


def _load_system_prompt() -> str:
    with open(_SYSTEM_PROMPT_PATH, encoding="utf-8") as f:
        return f.read()


def _make_chat_completion_wrapper(original_fn, model=None, non_thinking_llm=None, system_prompt=None):
    """包装 chat_completion，注入 model / non_thinking_llm / system_prompt 到 execute_kwargs"""

    @wraps(original_fn)
    def wrapper(*args, **kwargs):
        execute_kwargs = kwargs.get("execute_kwargs") or {}
        if model:
            execute_kwargs["model"] = model
        if non_thinking_llm:
            execute_kwargs["non_thinking_llm"] = non_thinking_llm
        if system_prompt:
            execute_kwargs["system_prompt"] = system_prompt
        kwargs["execute_kwargs"] = execute_kwargs
        return original_fn(*args, **kwargs)

    return wrapper


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

    username = config.get("username") or os.environ.get("BKAPP_EVAL_USERNAME")
    if not username:
        return {"error": "BKAPP_EVAL_USERNAME 环境变量未设置，请 export BKAPP_EVAL_USERNAME=your_rtx"}

    model = config.get("model")
    non_thinking_llm = config.get("non_thinking_llm")
    system_prompt = config.get("system_prompt") or _load_system_prompt()

    resource = NL2RiskFilter()

    start = time.time()
    try:
        with patch(
            "services.web.risk.resources.risk.get_request_username",
            return_value=username,
        ):
            import services.web.risk.resources.risk as _risk_mod

            original_fn = _risk_mod.api.bk_plugins_ai_agent.chat_completion
            with patch(
                _CHAT_COMPLETION_PATH,
                _make_chat_completion_wrapper(
                    original_fn, model=model, non_thinking_llm=non_thinking_llm, system_prompt=system_prompt
                ),
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
            "model": model or "platform-default",
            "raw_result": result,
        },
    }

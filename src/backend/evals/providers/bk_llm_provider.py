# -*- coding: utf-8 -*-
"""
promptfoo 公共 provider — 蓝鲸 LLM 网关（OpenAI 标准协议）

通过蓝鲸 AIDev LLM 网关调用大模型，接口完全兼容 OpenAI /chat/completions。
可用于：
  - llm-rubric (LLM-as-Judge) 评分
  - 独立的模型调用评测
  - 任何需要标准 OpenAI chat completion 的场景

环境变量（在 .env 中配置）：
  BKAPP_LLM_GW_ENDPOINT — LLM 网关 base URL（必填）
  BKAPP_LLM_APP_CODE    — 蓝鲸应用 code（缺省 fallback BKPAAS_APP_ID）
  BKAPP_LLM_APP_SECRET  — 蓝鲸应用 secret（缺省 fallback BKPAAS_APP_SECRET）

用法（在各评测套件的 promptfooconfig.yaml 中引用）：
  # 作为 LLM-as-Judge grader
  defaultTest:
    options:
      provider:
        id: 'python:../providers/bk_llm_provider.py'
        config:
          model: 'dsv32'

  # 作为独立 provider
  providers:
    - id: 'python:../providers/bk_llm_provider.py'
      label: 'dsv32-direct'
      config:
        model: 'dsv32'
"""

import json
import os

import requests


def call_api(prompt, options, context):
    """promptfoo 调用入口 — OpenAI chat/completions 标准协议"""
    config = options.get("config", {})

    base_url = config.get("base_url") or os.environ.get("BKAPP_LLM_GW_ENDPOINT", "")
    if not base_url:
        return {"error": "BKAPP_LLM_GW_ENDPOINT 未配置"}

    model = config.get("model", "dsv32")
    temperature = config.get("temperature", 0)

    app_code = os.environ.get("BKAPP_LLM_APP_CODE") or os.environ.get("BKPAAS_APP_ID", "")
    app_secret = os.environ.get("BKAPP_LLM_APP_SECRET") or os.environ.get("BKPAAS_APP_SECRET", "")

    headers = {"Content-Type": "application/json"}
    if app_code:
        headers["X-Bkapi-Authorization"] = json.dumps({"bk_app_code": app_code, "bk_app_secret": app_secret})

    if isinstance(prompt, list):
        messages = prompt
    elif isinstance(prompt, str):
        messages = [{"role": "user", "content": prompt}]
    else:
        messages = [{"role": "user", "content": str(prompt)}]

    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=120)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        return {"error": f"LLM 网关调用失败: {exc}"}

    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    return {"output": content}

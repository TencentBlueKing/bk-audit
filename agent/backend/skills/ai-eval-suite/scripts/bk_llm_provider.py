# -*- coding: utf-8 -*-
"""
promptfoo 公共 provider — 蓝鲸 LLM 网关（OpenAI 标准协议）

通过蓝鲸 AIDev LLM 网关调用大模型，接口完全兼容 OpenAI /v1/chat/completions。
可用于：
  - llm-rubric (LLM-as-Judge) 评分
  - 独立的模型调用评测
  - 任何需要标准 OpenAI chat completion 的场景

环境变量（在 .env 中配置）：
  BKAPP_LLM_GW_ENDPOINT — LLM 网关 base URL（必填，如 bkaidev 的网关地址）
  BKAPP_LLM_APP_CODE    — 蓝鲸应用 code（缺省 fallback BKPAAS_APP_ID）
  BKAPP_LLM_APP_SECRET  — 蓝鲸应用 secret（缺省 fallback BKPAAS_APP_SECRET）

用法（在各评测套件的 promptfooconfig.yaml 中引用）：

  # 作为 LLM-as-Judge grader
  defaultTest:
    options:
      provider:
        id: 'python:../providers/bk_llm_provider.py'
        config:
          model: 'your-model-name'

  # 作为独立 provider
  providers:
    - id: 'python:../providers/bk_llm_provider.py'
      label: 'model-direct'
      config:
        model: 'your-model-name'
        temperature: 0

部署方式：
  初始化评估套件时，将此文件复制到项目的 evals/providers/ 目录下。
  各 suite 通过相对路径 python:../providers/bk_llm_provider.py 引用。
"""

import json
import os

import requests


def call_api(prompt, options, context):
    """promptfoo 调用入口 — OpenAI chat/completions 标准协议"""
    config = options.get("config", {})

    base_url = config.get("base_url") or os.environ.get("BKAPP_LLM_GW_ENDPOINT", "")
    if not base_url:
        return {"error": "BKAPP_LLM_GW_ENDPOINT 未配置，请在 .env 中设置 LLM 网关地址"}

    model = config.get("model", "")
    if not model:
        return {"error": "provider config 中未指定 model"}

    temperature = config.get("temperature", 0)
    timeout = config.get("timeout", 120)

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
        resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.Timeout:
        return {"error": f"LLM 网关调用超时（{timeout}s），可通过 config.timeout 调整"}
    except requests.exceptions.ConnectionError as exc:
        return {"error": f"LLM 网关连接失败，请检查 BKAPP_LLM_GW_ENDPOINT 是否正确: {exc}"}
    except requests.exceptions.HTTPError:
        return {"error": f"LLM 网关返回错误 {resp.status_code}: {resp.text[:500]}"}
    except Exception as exc:
        return {"error": f"LLM 网关调用失败: {exc}"}

    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    token_usage = data.get("usage", {})

    result = {"output": content}
    if token_usage:
        result["tokenUsage"] = {
            "total": token_usage.get("total_tokens", 0),
            "prompt": token_usage.get("prompt_tokens", 0),
            "completion": token_usage.get("completion_tokens", 0),
        }
    return result

# -*- coding: utf-8 -*-
"""promptfoo 业务 Provider：审计 AI 日志检索。

直接调用 ``NL2JSONService.convert``，复用生产的 User Message、AIDev Agent
调用、JSON 提取、语义校验与受控条件组装链路。评测字段上下文为固定合成夹具，
不访问真实审计日志或元数据服务。
"""

import json
import os
import sys
import time
import warnings
from datetime import datetime
from functools import wraps
from unittest.mock import patch

warnings.filterwarnings("ignore", message="pkg_resources is deprecated")
warnings.filterwarnings("ignore", message=".*is not supported by DRF.*")

_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

os.chdir(_BACKEND_ROOT)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")

import django  # noqa: E402

django.setup()

from services.web.query.ai_assistant.schemas import (  # noqa: E402
    SelectionFieldMeta,
    SelectionFieldOption,
    SelectionSystem,
    SystemSelectionOutput,
)
from services.web.query.ai_assistant.services.nl2json import (  # noqa: E402
    NL2JSONService,
)

_CHAT_COMPLETION_PATH = "services.web.query.ai_assistant.services.nl2json.api.bk_plugins_ai_agent.chat_completion"
_LOCALTIME_PATH = "services.web.query.ai_assistant.services.nl2json.timezone.localtime"
_NOW_PATH = "services.web.query.ai_assistant.services.nl2json.timezone.now"

_FIXED_SCOPE_ID = "eval_audit_system"

# 进度双通道：stderr 实时透传到控制台（promptfoo 转发 Python worker stderr），
# progress.log 供后台运行时轮询（启动评估前应清空该文件）
_PROGRESS_LOG = os.path.join(_BACKEND_ROOT, "evals", "audit-log-search", "output", "progress.log")


def _log_progress(query: str, status: str, latency_ms: int | None = None) -> None:
    """每次 AIDev 调用前后输出进度行（控制台静默期的唯一进度信号）。"""

    line = (
        f"{time.strftime('%H:%M:%S')} [{status}] " f"{f'{latency_ms}ms ' if latency_ms is not None else ''}{query[:40]}"
    )
    print(f"[progress] {line}", file=sys.stderr, flush=True)
    try:
        with open(_PROGRESS_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def _build_selection() -> SystemSelectionOutput:
    """构造稳定、无生产数据的字段上下文夹具。"""

    standard_fields = [
        SelectionFieldMeta(
            raw_name="username",
            field_type="string",
            display_name="操作人",
            nl_name="操作人",
            allow_operators=["eq", "include"],
            sample_value="张三",
        ),
        SelectionFieldMeta(
            raw_name="action_id",
            field_type="string",
            display_name="操作类型",
            nl_name="操作类型",
            allow_operators=["eq", "include"],
            sample_value="create",
        ),
        SelectionFieldMeta(
            raw_name="resource_type_id",
            field_type="string",
            display_name="资源类型",
            nl_name="资源类型",
            allow_operators=["eq", "include"],
            sample_value="host",
        ),
        SelectionFieldMeta(
            raw_name="instance_id",
            field_type="string",
            display_name="实例 ID",
            nl_name="实例 ID",
            allow_operators=["eq", "include"],
            sample_value="10001",
        ),
        SelectionFieldMeta(
            raw_name="instance_name",
            field_type="string",
            display_name="实例名称",
            nl_name="实例名称",
            allow_operators=["like"],
            sample_value="test-vm",
        ),
        SelectionFieldMeta(
            raw_name="access_source_ip",
            field_type="string",
            display_name="来源 IP",
            nl_name="来源 IP",
            allow_operators=["eq", "include"],
            sample_value="192.0.2.10",
        ),
        SelectionFieldMeta(
            raw_name="request_id",
            field_type="string",
            display_name="请求 ID",
            nl_name="请求 ID",
            allow_operators=["eq", "include"],
            sample_value="request-001",
        ),
        SelectionFieldMeta(
            raw_name="access_type",
            field_type="string",
            display_name="访问类型",
            nl_name="访问类型",
            allow_operators=["eq", "include"],
            sample_value="WEB",
            options=[
                SelectionFieldOption(id="WEB", name="Web控制台"),
                SelectionFieldOption(id="API", name="API调用"),
            ],
        ),
        SelectionFieldMeta(
            raw_name="result_code",
            field_type="string",
            display_name="执行结果",
            nl_name="执行结果",
            allow_operators=["include"],
            sample_value=-1,
            options=[
                SelectionFieldOption(id="0", name="成功(0)"),
                SelectionFieldOption(id="-1", name="失败(-1)"),
            ],
        ),
        SelectionFieldMeta(
            raw_name="log",
            field_type="string",
            display_name="日志内容",
            nl_name="日志内容",
            allow_operators=["match_any", "match_all"],
            sample_value="权限变更",
        ),
    ]
    extension_fields = [
        SelectionFieldMeta(
            raw_name="extend_data",
            keys=["ticket_id"],
            field_type="string",
            display_name="工单号",
            nl_name="extend.工单号",
            description="业务工单编号",
            allow_operators=["eq", "neq", "include", "exclude", "like"],
            sample_value="Story-3000",
            system_id=_FIXED_SCOPE_ID,
        )
    ]
    return SystemSelectionOutput(
        systems=[
            SelectionSystem(
                system_id=_FIXED_SCOPE_ID,
                name="评估用审计系统",
                standard_fields=standard_fields,
                extension_fields=extension_fields,
            )
        ]
    )


def _parse_current_time(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    current_time = datetime.fromisoformat(normalized)
    if current_time.tzinfo is None:
        raise ValueError("current_time 必须携带时区")
    return current_time


def _make_chat_completion_wrapper(original_fn, model: str | None):
    """可选注入模型名，默认保持 AIDev Agent 的线上模型配置。"""

    @wraps(original_fn)
    def wrapper(*args, **kwargs):
        if model:
            execute_kwargs = dict(kwargs.get("execute_kwargs") or {})
            execute_kwargs["model"] = model
            kwargs["execute_kwargs"] = execute_kwargs
        return original_fn(*args, **kwargs)

    return wrapper


def _get_username(config: dict) -> str:
    username = config.get("username") or ""
    if not username or str(username).startswith("{{"):
        username = os.environ.get("BKAPP_EVAL_USERNAME", "")
    return username


def call_api(prompt, options, context):
    """promptfoo 入口：返回生产链路组装后的协议响应。"""

    vars_ = context.get("vars", {})
    config = options.get("config", {})
    username = _get_username(config)
    if not username:
        return {"error": "BKAPP_EVAL_USERNAME 环境变量未设置"}

    query = vars_.get("query", prompt)
    current_time_text = vars_.get("current_time", "2026-08-31T18:00:00+08:00")
    try:
        current_time = _parse_current_time(current_time_text)
    except (TypeError, ValueError) as exc:
        return {"error": f"current_time 无效: {exc}"}

    model = config.get("model") or None
    start = time.perf_counter()
    _log_progress(query, "START")
    try:
        original_fn = NL2JSONService._call_agent.__func__.__globals__["api"].bk_plugins_ai_agent.chat_completion
        with (
            patch(_CHAT_COMPLETION_PATH, _make_chat_completion_wrapper(original_fn, model)),
            patch(_LOCALTIME_PATH, return_value=current_time),
            patch(_NOW_PATH, return_value=current_time),
        ):
            condition = NL2JSONService.convert(
                query_text=query,
                selection=_build_selection(),
                scope_id=_FIXED_SCOPE_ID,
                username=username,
            )
        payload = {"status": "success", "condition": condition.model_dump(mode="json")}
    except Exception as exc:  # 业务异常须进入评测输出，由断言判定预期行为
        payload = {
            "status": "error",
            "error_code": getattr(exc, "error_code", "UNEXPECTED_ERROR"),
            "message": str(exc),
        }

    latency_ms = round((time.perf_counter() - start) * 1000)
    _log_progress(query, payload.get("status", "unknown").upper(), latency_ms)

    return {
        "output": json.dumps(payload, ensure_ascii=False),
        "metadata": {
            "latency_ms": latency_ms,
            "agent_code": getattr(NL2JSONService.agent_code, "value", str(NL2JSONService.agent_code)),
            "model": model or "platform-default",
        },
    }

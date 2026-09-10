# -*- coding: utf-8 -*-
"""promptfoo 业务 Provider：AI 用户意图判断。

两种评测模式：
- recognize（默认）：直接调用 IntentRecognitionService.recognize，复用生产的
  User Message 模板（含 IntentPayload schema 注入）、AIDev 调用、JSON 提取闸门
  与候选白名单校验。
- chain（vars.chain=true）：复刻 execute_user_intent 任务的 LLM 编排路径——
  意图识别 → 系统路由（select_system 取命中 / log_search 复用当前）→
  SYSTEM_REQUIRED 平台守门形态 → 条件识别（NL2JSON，目标系统字段上下文），
  两段均为真实 AIDev 调用；建链/续链等确定性编排由单测覆盖不在本层评估。

候选系统与字段上下文均为固定合成夹具，不访问真实权限/元数据服务。
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

from services.web.query.ai_assistant.exceptions import AIAssistantError  # noqa: E402
from services.web.query.ai_assistant.schemas import (  # noqa: E402
    SelectionFieldMeta,
    SelectionFieldOption,
    SelectionSystem,
    SystemSelectionOutput,
)
from services.web.query.ai_assistant.services.intent import (  # noqa: E402
    IntentRecognitionService,
)
from services.web.query.ai_assistant.services.nl2json import (  # noqa: E402
    NL2JSONService,
)

_CHAT_COMPLETION_PATH = "services.web.query.ai_assistant.services.intent.api.bk_plugins_ai_agent.chat_completion"
_LOCALTIME_PATH = "services.web.query.ai_assistant.services.intent.timezone.localtime"
_NL2JSON_CHAT_PATH = "services.web.query.ai_assistant.services.nl2json.api.bk_plugins_ai_agent.chat_completion"
_NL2JSON_LOCALTIME_PATH = "services.web.query.ai_assistant.services.nl2json.timezone.localtime"
_NL2JSON_NOW_PATH = "services.web.query.ai_assistant.services.nl2json.timezone.now"

# 固定候选系统夹具（稳定无生产数据）
CANDIDATES = [
    {"system_id": "eval_audit_system", "name": "审计中心"},
    {"system_id": "eval_bcs_system", "name": "蓝盾"},
    {"system_id": "eval_config_system", "name": "配置平台"},
    {"system_id": "eval_monitor_system", "name": "监控平台"},
]

# 线上形态候选夹具（2026-09-07 事故回归用）：贴近生产规模与干扰形态——
# 含 system_id/名称带 "audit" 字样的干扰系统 iam_v4_bk-audit、dry_test 等
LINE_CANDIDATES = [
    {"system_id": "bk-audit", "name": "审计中心"},
    {"system_id": "iam_v4_bk-audit", "name": "iam v4 bk audit"},
    {"system_id": "bk-ci", "name": "蓝盾"},
    {"system_id": "bk_sops", "name": "标准运维"},
    {"system_id": "bk_cmdb", "name": "配置平台"},
    {"system_id": "bk_monitorv3", "name": "监控平台"},
    {"system_id": "bk_userman", "name": "用户管理"},
    {"system_id": "bk_iam", "name": "权限中心"},
    {"system_id": "bk_nodeman", "name": "节点管理"},
    {"system_id": "dry_test", "name": "dry_test"},
    {"system_id": "bk_ops_base", "name": "运维基础计算平台"},
]


def _resolve_candidates(raw):
    """用例级候选清单取值："line"（线上形态夹具）/ 内联清单 / 缺省默认夹具。"""

    if raw == "line":
        return LINE_CANDIDATES
    if isinstance(raw, list) and raw:
        return [
            {"system_id": str(c.get("system_id") or ""), "name": str(c.get("name") or "")}
            for c in raw
            if isinstance(c, dict)
        ]
    return CANDIDATES


_PROGRESS_LOG = os.path.join(_BACKEND_ROOT, "evals", "intent-recognition", "output", "progress.log")


def _log_progress(query, status, latency_ms=None):
    line = (
        f"{time.strftime('%H:%M:%S')} [{status}] " f"{f'{latency_ms}ms ' if latency_ms is not None else ''}{query[:40]}"
    )
    print(f"[progress] {line}", file=sys.stderr, flush=True)
    try:
        os.makedirs(os.path.dirname(_PROGRESS_LOG), exist_ok=True)
        with open(_PROGRESS_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def _parse_current_time(value):
    normalized = value.replace("Z", "+00:00")
    current_time = datetime.fromisoformat(normalized)
    if current_time.tzinfo is None:
        raise ValueError("current_time 必须携带时区")
    return current_time


def _make_chat_completion_wrapper(original_fn, model):
    @wraps(original_fn)
    def wrapper(*args, **kwargs):
        if model:
            execute_kwargs = dict(kwargs.get("execute_kwargs") or {})
            execute_kwargs["model"] = model
            kwargs["execute_kwargs"] = execute_kwargs
        return original_fn(*args, **kwargs)

    return wrapper


def _get_username(config):
    username = config.get("username") or ""
    if not username or str(username).startswith("{{"):
        username = os.environ.get("BKAPP_EVAL_USERNAME", "")
    return username


def _build_chain_selection(scope_id: str) -> SystemSelectionOutput:
    """chain 模式字段上下文夹具：与 audit-log-search 套件同构的合成字段清单。"""

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
            system_id=scope_id,
        ),
    ]
    return SystemSelectionOutput(
        systems=[
            SelectionSystem(
                system_id=scope_id,
                name="评估用审计系统",
                standard_fields=standard_fields,
                extension_fields=extension_fields,
            )
        ]
    )


def _run_chain(query, current_system_id, current_time, model, username, original_fn, candidates):
    """复刻 execute_user_intent 的 LLM 编排：意图识别 → 路由 → 守门 → 条件识别。

    平台守门（SYSTEM_REQUIRED）与确定性失败分支以协议形态复刻；
    建链/复用/续链等 DB 编排由单测覆盖，不进入本层。
    """

    wrapper = _make_chat_completion_wrapper(original_fn, model)
    with (
        patch(_CHAT_COMPLETION_PATH, wrapper),
        patch(_LOCALTIME_PATH, return_value=current_time),
        patch(_NL2JSON_CHAT_PATH, wrapper),
        patch(_NL2JSON_LOCALTIME_PATH, return_value=current_time),
        patch(_NL2JSON_NOW_PATH, return_value=current_time),
    ):
        # ① 意图识别（真实 LLM）
        payload_model = IntentRecognitionService.recognize(
            query_text=query,
            candidates=candidates,
            current_system_id=current_system_id,
            username=username,
        )
        # ② 无法识别：结构化 unrecognized 协议
        if payload_model.intent == "unrecognized":
            return {
                "intent": "unrecognized",
                "system_id": "",
                "message": payload_model.message,
                "condition": None,
                "error": {
                    "error_code": "UNRECOGNIZED_INTENT",
                    "error_message": payload_model.message or "未能理解您的需求，请描述要查询的系统或日志内容",
                },
            }
        # ③ 系统路由：select_system 取命中系统；log_search 复用当前系统（缺系统守门）
        system_id = current_system_id
        if payload_model.intent == "select_system":
            system_id = payload_model.system_id
        elif not current_system_id:
            return {
                "intent": "log_search",
                "system_id": "",
                "message": payload_model.message,
                "condition": None,
                "error": {
                    "error_code": "SYSTEM_REQUIRED",
                    "error_message": "请先告诉我要查哪个系统的日志，您有权限的系统：" + "、".join(c["name"] for c in candidates),
                    "candidates": [c["name"] for c in candidates],
                },
            }
        # ④ 条件识别（真实 LLM，目标系统字段上下文；确定性失败走结构化 error）
        try:
            condition = NL2JSONService.convert(
                query_text=query,
                selection=_build_chain_selection(system_id),
                scope_id=system_id,
                username=username,
            )
        except AIAssistantError as error:
            return {
                "intent": payload_model.intent,
                "system_id": system_id,
                "message": payload_model.message,
                "condition": None,
                "error": {"error_code": error.error_code, "error_message": error.message},
            }
        return {
            "intent": payload_model.intent,
            "system_id": system_id,
            "message": payload_model.message,
            "condition": condition.model_dump(mode="json"),
            "error": None,
        }


def call_api(prompt, options, context):
    """promptfoo 入口：返回意图识别链路的协议响应。"""

    vars_ = context.get("vars", {})
    config = options.get("config", {})
    username = _get_username(config)
    if not username:
        return {"error": "BKAPP_EVAL_USERNAME 环境变量未设置"}

    query = vars_.get("query", prompt)
    current_system_id = vars_.get("current_system_id", "")
    # 用例级候选系统覆盖："line" 取线上形态夹具；不传时用默认夹具
    candidates = _resolve_candidates(vars_.get("candidates"))
    current_time_text = vars_.get("current_time", "2026-09-04T18:00:00+08:00")
    try:
        current_time = _parse_current_time(current_time_text)
    except (TypeError, ValueError) as exc:
        return {"error": f"current_time 无效: {exc}"}

    model = config.get("model") or None
    start = time.perf_counter()
    _log_progress(query, "START")
    try:
        original_fn = IntentRecognitionService._call_agent.__func__.__globals__[
            "api"
        ].bk_plugins_ai_agent.chat_completion
        if vars_.get("chain"):
            # 串联编排模式（意图识别 + 条件识别两段真实 LLM）
            payload = {
                "status": "success",
                **_run_chain(
                    query,
                    current_system_id,
                    current_time,
                    model,
                    username,
                    original_fn,
                    candidates,
                ),
            }
        else:
            with (
                patch(_CHAT_COMPLETION_PATH, _make_chat_completion_wrapper(original_fn, model)),
                patch(_LOCALTIME_PATH, return_value=current_time),
            ):
                payload_model = IntentRecognitionService.recognize(
                    query_text=query,
                    candidates=candidates,
                    current_system_id=current_system_id,
                    username=username,
                )
            payload = {
                "status": "success",
                "intent": payload_model.intent,
                "system_id": payload_model.system_id,
                "message": payload_model.message,
            }
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
            "agent_code": getattr(
                IntentRecognitionService.agent_code, "value", str(IntentRecognitionService.agent_code)
            ),
            "model": model or "platform-default",
        },
    }

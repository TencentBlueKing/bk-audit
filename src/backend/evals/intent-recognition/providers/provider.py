# -*- coding: utf-8 -*-
"""promptfoo Provider：复用生产 MessagePlanningService 评估单 Agent 消息计划。

评测输入包含用户原话、当前系统、授权系统及字段上下文；Agent 一次返回
MessagePlan，Provider 再运行与生产一致的 Pydantic、系统白名单和检索条件校验。
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

from services.web.query.ai_assistant.exceptions import (  # noqa: E402
    AIOutputInvalidError,
    AIOutputParseFailedError,
    QueryNotRecognizedError,
)
from services.web.query.ai_assistant.schemas import (  # noqa: E402
    MessagePlan,
    SelectionFieldMeta,
    SelectionFieldOption,
    SelectionSystem,
    SystemSelectionOutput,
)
from services.web.query.ai_assistant.services.intent import (  # noqa: E402
    MessagePlanningService,
)
from services.web.query.ai_assistant.services.nl2json import (  # noqa: E402
    NL2JSONService,
)

_CHAT_COMPLETION_PATH = "services.web.query.ai_assistant.services.intent.api.bk_plugins_ai_agent.chat_completion"

CANDIDATES = [
    {"system_id": "eval_audit_system", "name": "审计中心", "description": "审计日志与操作记录"},
    {"system_id": "eval_bcs_system", "name": "蓝盾", "description": "持续集成与发布流水线"},
    {"system_id": "eval_config_system", "name": "配置平台", "description": "配置与资源管理"},
    {"system_id": "eval_monitor_system", "name": "监控平台", "description": "监控告警与观测数据"},
]

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

_PROGRESS_LOG = os.path.join(_BACKEND_ROOT, "evals", "intent-recognition", "output", "progress.log")


def _resolve_candidates(raw):
    """解析用例候选系统，保留可选 description。"""

    if raw == "line":
        candidates = LINE_CANDIDATES
    elif isinstance(raw, list):
        candidates = raw
    else:
        candidates = CANDIDATES
    return [
        {
            "system_id": str(candidate.get("system_id") or ""),
            "name": str(candidate.get("name") or ""),
            "description": str(candidate.get("description") or ""),
        }
        for candidate in candidates
        if isinstance(candidate, dict) and candidate.get("system_id")
    ]


def _log_progress(query, status, latency_ms=None):
    line = f"{time.strftime('%H:%M:%S')} [{status}] {f'{latency_ms}ms ' if latency_ms is not None else ''}{query[:40]}"
    print(f"[progress] {line}", file=sys.stderr, flush=True)
    try:
        os.makedirs(os.path.dirname(_PROGRESS_LOG), exist_ok=True)
        with open(_PROGRESS_LOG, "a", encoding="utf-8") as file:
            file.write(line + "\n")
    except OSError:
        pass


def _parse_current_time(value):
    current_time = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if current_time.tzinfo is None:
        raise ValueError("current_time 必须携带时区")
    return current_time


def _make_chat_completion_wrapper(original_fn, model):
    """仅覆盖模型参数，保留生产 role/user/thread_id 请求形态。"""

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


def _build_fields(system_id: str):
    """构造贴近真实检索的稳定字段上下文。"""

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
            display_name="操作事件名(ID)",
            nl_name="操作事件名(ID)",
            description="别名：操作ID",
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
            system_id=system_id,
        )
    ]
    return standard_fields, extension_fields


def _build_system_context(candidates) -> SystemSelectionOutput:
    systems = []
    for candidate in candidates:
        standard_fields, extension_fields = _build_fields(candidate["system_id"])
        systems.append(
            SelectionSystem(
                system_id=candidate["system_id"],
                name=candidate["name"],
                description=candidate.get("description", ""),
                standard_fields=standard_fields,
                extension_fields=extension_fields,
            )
        )
    return SystemSelectionOutput(systems=systems)


def _resolve_system_context(variables) -> SystemSelectionOutput:
    """优先解析生产同构系统快照，未提供时使用简化候选构造基础字段。"""

    if "authorized_systems" in variables:
        return SystemSelectionOutput.model_validate({"systems": variables["authorized_systems"]})
    return _build_system_context(_resolve_candidates(variables.get("candidates")))


def _materialize_output(
    *,
    plan: MessagePlan,
    system_context: SystemSelectionOutput,
    current_system_id: str,
    reference_time: datetime,
) -> dict:
    """补跑确定性条件校验，并输出计划主协议及兼容评测维度。"""

    selection = next((message for message in plan.messages if message.message_type == "SYSTEM_SELECTION"), None)
    log_search = next((message for message in plan.messages if message.message_type == "LOG_SEARCH"), None)
    target_system_id = selection.message_input.system_ids[0] if selection is not None else current_system_id
    condition = None
    if log_search is not None:
        candidate_map = {system.system_id: system for system in system_context.systems}
        target = candidate_map[target_system_id]
        condition = NL2JSONService.validate_and_assemble(
            payload=log_search.message_input.condition,
            selection=SystemSelectionOutput(systems=[target]),
            scope_id=target_system_id,
            reference_time=reference_time,
            allow_empty=True,
        ).model_dump(mode="json")

    if plan.outcome == "error":
        intent = "unrecognized" if plan.error_code == "UNRECOGNIZED_INTENT" else "log_search"
    else:
        intent = "select_system" if selection is not None else "log_search"
    return {
        "status": "success",
        "outcome": plan.outcome,
        "messages": [message.model_dump(mode="json") for message in plan.messages],
        "error_code": plan.error_code,
        "intent": intent,
        "system_id": target_system_id if plan.outcome == "dispatch" else "",
        "condition": condition,
        "error": (
            {
                "error_code": plan.error_code,
                "error_message": plan.error_code,
                "candidates": [system.name for system in system_context.systems],
            }
            if plan.outcome == "error"
            else None
        ),
    }


def call_api(prompt, options, context):
    """promptfoo 入口：执行一次生产消息规划 Agent 调用。"""

    vars_ = context.get("vars", {})
    config = options.get("config", {})
    username = _get_username(config)
    if not username:
        return {"error": "BKAPP_EVAL_USERNAME 环境变量未设置"}

    query = vars_.get("query", prompt)
    current_system_id = vars_.get("current_system_id", "")
    scope_type = vars_.get("scope_type", "cross_system")
    scope_id = vars_.get("scope_id", "")
    try:
        current_time = _parse_current_time(vars_.get("current_time", "2026-09-04T18:00:00+08:00"))
    except (TypeError, ValueError) as error:
        return {"error": f"current_time 无效: {error}"}

    model = config.get("model") or None
    max_attempts = max(1, int(vars_.get("max_attempts") or config.get("max_attempts") or 3))
    system_context = _resolve_system_context(vars_)
    start = time.perf_counter()
    attempt_count = 0
    _log_progress(query, "START")
    try:
        original_fn = MessagePlanningService._call_agent.__func__.__globals__["api"].bk_plugins_ai_agent.chat_completion
        with patch(_CHAT_COMPLETION_PATH, _make_chat_completion_wrapper(original_fn, model)):
            for attempt_count in range(1, max_attempts + 1):
                try:
                    plan = MessagePlanningService.plan(
                        query_text=query,
                        system_context=system_context,
                        current_system_id=current_system_id,
                        username=username,
                        scope_type=scope_type,
                        scope_id=scope_id,
                        reference_time=current_time,
                    )
                    payload = _materialize_output(
                        plan=plan,
                        system_context=system_context,
                        current_system_id=current_system_id,
                        reference_time=current_time,
                    )
                    break
                except (AIOutputParseFailedError, AIOutputInvalidError, QueryNotRecognizedError):
                    if attempt_count >= max_attempts:
                        raise
    except Exception as error:  # 业务异常进入评测输出，由断言判定是否符合预期
        extra = getattr(error, "extra", {}) or {}
        payload = {
            "status": "error",
            "error_code": str(getattr(error, "error_code", "UNEXPECTED_ERROR")),
            "message": str(error),
            "diagnostic": {
                "validation_error": str(extra.get("validation_error") or ""),
                "reason": str(extra.get("reason") or ""),
                "raw_output": str(extra.get("raw_output") or "")[:2048],
            },
        }

    latency_ms = round((time.perf_counter() - start) * 1000)
    _log_progress(query, payload.get("status", "unknown").upper(), latency_ms)
    return {
        "output": json.dumps(payload, ensure_ascii=False),
        "metadata": {
            "latency_ms": latency_ms,
            "agent_code": getattr(MessagePlanningService.agent_code, "value", str(MessagePlanningService.agent_code)),
            "model": model or "platform-default",
            "attempt_count": attempt_count,
        },
    }

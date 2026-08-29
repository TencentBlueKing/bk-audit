# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
Copyright (C) 2023 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

import abc
import json
import os
import threading
from contextvars import ContextVar
from enum import StrEnum
from typing import Any, Callable

from bk_resource import BkApiResource
from bk_resource.exceptions import APIRequestError, IAMNoPermission
from blueapps.utils.logger import logger
from django.conf import settings
from django.utils.translation import gettext_lazy
from requests.exceptions import HTTPError

from api.bk_plugins_ai_agent.agui import AGUIFinalMessageParser, AGUIStreamResponse
from api.bk_plugins_ai_agent.constants import AI_THINKING_PLACEHOLDERS
from api.bk_plugins_ai_agent.exceptions import (
    AGUIStreamCapacityExceeded,
    AGUIStreamProtocolError,
)
from api.constants import AI_AGENT_APP_CODE_TMPL, AI_AGENT_SECRET_KEY_TMPL, AIAgentCode
from api.utils import get_agent_base_url


class _AGUIRunState(StrEnum):
    WAITING = "WAITING"
    RUNNING = "RUNNING"
    TERMINAL = "TERMINAL"


class _AGUIRunLifecycle:
    """以唯一 RUN_STARTED 开启副作用；RUNNING 后不限制合法过程事件。"""

    def __init__(self):
        self.state = _AGUIRunState.WAITING
        self.thread_id = ""
        self.run_id = ""

    @staticmethod
    def _identity(event: dict[str, Any]) -> tuple[str, str]:
        thread_id = event.get("threadId")
        run_id = event.get("runId")
        if not isinstance(thread_id, str) or not thread_id.strip():
            raise AGUIStreamProtocolError("AG-UI RUN 事件缺少 threadId")
        if not isinstance(run_id, str) or not run_id.strip():
            raise AGUIStreamProtocolError("AG-UI RUN 事件缺少 runId")
        return thread_id, run_id

    def consume(self, event: dict[str, Any]) -> bool:
        event_type = event["type"]
        if event_type == "RUN_STARTED":
            if self.state != _AGUIRunState.WAITING:
                raise AGUIStreamProtocolError("AG-UI 流重复收到 RUN_STARTED")
            self.thread_id, self.run_id = self._identity(event)
            self.state = _AGUIRunState.RUNNING
            return False

        if self.state == _AGUIRunState.WAITING:
            raise AGUIStreamProtocolError("AG-UI RUN_STARTED 前收到过程事件")
        if event_type not in {"RUN_FINISHED", "RUN_ERROR"}:
            return False
        thread_id, run_id = self._identity(event)
        if (thread_id, run_id) != (self.thread_id, self.run_id):
            raise AGUIStreamProtocolError("AG-UI RUN 终态身份不匹配")
        self.state = _AGUIRunState.TERMINAL
        return True

    def ensure_terminal(self) -> None:
        if self.state == _AGUIRunState.WAITING:
            raise AGUIStreamProtocolError("AG-UI 流未收到有效 RUN_STARTED")
        if self.state != _AGUIRunState.TERMINAL:
            raise AGUIStreamProtocolError("AG-UI 连接结束时未收到 RUN 终态")


class AIAgentBase(BkApiResource, abc.ABC):
    """AI 智能体通用 API 基类

    与 AIAuditReport 共享相同的认证逻辑，但 URL 通过 get_agent_base_url 动态路由。
    不直接继承 AIAuditReport 以避免循环导入（bk_resource 按字母序扫描 api/ 目录）。

    凭证解析（原有全局链保持不变，per-agent 为新增覆盖）：
      - 带 agent_code 的资源（ChatCompletion）优先读 BKAPP_AI_{AGENT}_APP_CODE/_SECRET_KEY，
        为需要独立凭证的智能体（如上云版的日志检索）提供与 URL 路由同作用域的专属凭证；
      - 未配置 per-agent 凭证时走原有全局链，行为与历史版本完全一致：
        AI_AGENT_APP_CODE/_SECRET_KEY → AI_AUDIT_REPORT_APP_CODE/_SECRET_KEY → APP_CODE/SECRET_KEY。
    """

    module_name = "bk_plugins_ai_agent"
    base_url = ""
    platform_authorization = True
    tags = ["AIAgent"]
    # 单次智能体调用超时（秒）：默认 300 保持历史行为；环境可经 BKAPP_AI_AGENT_API_TIMEOUT_SECONDS
    # 收紧（如 60）——NL 链路重试预算的 deadline 只能在两次调用之间检查，正在进行的
    # 调用不可中断，单次超时是链路总时长的实际上限闸门（部署反馈：AIDev 慢时单次
    # 调用可拖数分钟且无拦截）
    TIMEOUT = getattr(settings, "AI_AGENT_API_TIMEOUT_SECONDS", 300)
    app_code_setting_names = ("AI_AGENT_APP_CODE", "AI_AUDIT_REPORT_APP_CODE")
    secret_key_setting_names = ("AI_AGENT_SECRET_KEY", "AI_AUDIT_REPORT_SECRET_KEY")
    # 资源为进程级单例，agent 状态按线程隔离（gevent 部署下为 greenlet 隔离）
    _agent_ctx = threading.local()

    @property
    def _current_agent_code(self):
        return getattr(self._agent_ctx, "agent_code", None)

    @_current_agent_code.setter
    def _current_agent_code(self, agent_code):
        self._agent_ctx.agent_code = agent_code

    @staticmethod
    def _get_first_setting(setting_names: tuple[str, ...], default_setting_name: str) -> str:
        for setting_name in setting_names:
            setting_value = getattr(settings, setting_name, "")
            if setting_value:
                return setting_value
        return getattr(settings, default_setting_name)

    def _get_agent_scoped_credential(self, is_app_code: bool) -> str:
        """per-agent 应用凭证：BKAPP_AI_{AGENT}_APP_CODE / BKAPP_AI_{AGENT}_SECRET_KEY

        与 get_agent_base_url 的 URL 路由作用域一致，仅影响当前 agent，不影响其它智能体。
        """
        agent_code = self._current_agent_code
        if agent_code is None:
            return ""
        tmpl = AI_AGENT_APP_CODE_TMPL if is_app_code else AI_AGENT_SECRET_KEY_TMPL
        return os.getenv(tmpl.format(agent_code.name), "").strip()

    @property
    def app_code(self) -> str:
        agent_scoped_credential = self._get_agent_scoped_credential(is_app_code=True)
        if agent_scoped_credential:
            return agent_scoped_credential
        return self._get_first_setting(self.app_code_setting_names, "APP_CODE")

    @property
    def secret_key(self) -> str:
        agent_scoped_credential = self._get_agent_scoped_credential(is_app_code=False)
        if agent_scoped_credential:
            return agent_scoped_credential
        return self._get_first_setting(self.secret_key_setting_names, "SECRET_KEY")

    def add_esb_info_before_request(self, params: dict) -> dict:
        """仅传递 Agent 应用态接口所需的应用凭证。"""
        params.pop("_is_backend", None)
        params.pop("_request", None)
        params.pop("bk_username", None)
        params.pop("access_token", None)
        oauth_params = self.oath_cookies_params
        oauth_keys = oauth_params.keys() if isinstance(oauth_params, dict) else (oauth_params,)
        for key in oauth_keys:
            params.pop(key, None)
        params["bk_app_code"] = self.app_code
        params["bk_app_secret"] = self.secret_key
        return params


class ChatCompletion(AIAgentBase):
    """通用 AI Agent 对话接口，通过 agent_code 参数路由到不同智能体。

    Agent 输入和响应可能包含审计日志、用户提示词及分析结论，因此禁止
    ``ResourceRequestLog`` 采集正文；请求规模、路由和响应元信息仍由本类的
    结构化日志及 OpenTelemetry span 记录。
    """

    name = gettext_lazy("通用智能体对话")
    method = "POST"
    action = "/bk_plugin/openapi/agent/chat_completion/"
    support_data_collect = False

    def build_url(self, validated_request_data):
        agent_code = validated_request_data.pop("agent_code", None)
        if not agent_code:
            raise ValueError("agent_code is required for bk_plugins_ai_agent.ChatCompletion")
        if isinstance(agent_code, str):
            agent_code = AIAgentCode(agent_code)
        # 记录本次请求的 agent，供 per-agent 凭证解析（build_url 先于 build_header 执行）
        self._current_agent_code = agent_code
        base_url = get_agent_base_url(agent_code)
        return base_url.rstrip("/") + "/" + self.action.lstrip("/")

    def perform_request(self, validated_request_data):
        # 请求结束后清理线程内 agent 状态，避免残留影响同线程后续请求（如审计报告等无 agent 的资源）
        try:
            return super().perform_request(validated_request_data)
        finally:
            self._current_agent_code = None

    def build_header(self, validated_request_data):
        headers = super().build_header(validated_request_data)
        user = validated_request_data.pop("user", None)
        if user:
            headers["X-BKAIDEV-USER"] = user
        return headers

    def before_request(self, kwargs):
        request_data = kwargs.get("json") or kwargs.get("data") or {}
        if isinstance(request_data, dict):
            execute_kwargs = request_data.get("execute_kwargs") or {}
            logger.info(
                "AI agent request prepared: agent_code=%s, stream=%s, input_size=%s, chat_history_count=%s",
                self._current_agent_code,
                bool(execute_kwargs.get("stream")),
                len(request_data.get("input") or ""),
                len(request_data.get("chat_history") or []),
            )
            if execute_kwargs.get("stream"):
                kwargs["stream"] = True
        return kwargs

    def postprocess_agui_final_content(self, content: str) -> tuple[str, str]:
        """允许子类处理已确认完整的 AG-UI assistant 正文。"""
        return content, ""

    def _is_stream_response(self, response) -> bool:
        content_type = (response.headers.get("Content-Type") or response.headers.get("content-type") or "").lower()
        if "text/event-stream" in content_type:
            return True
        try:
            body = getattr(response.request, "body", None)
            if not body:
                return False
            if isinstance(body, (bytes, bytearray)):
                body = body.decode("utf-8")
            if isinstance(body, str):
                body = json.loads(body)
            if not isinstance(body, dict):
                return False
            execute_kwargs = body.get("execute_kwargs") or {}
            return bool(execute_kwargs.get("stream"))
        except Exception:
            return False

    @staticmethod
    def _clean_final_content(content: str) -> str:
        cleaned_content = content or ""
        for placeholder in AI_THINKING_PLACEHOLDERS:
            cleaned_content = cleaned_content.replace(placeholder, "")
        return cleaned_content if cleaned_content.strip() else ""

    def _parse_stream_response(self, response) -> str:
        # text event 是前端增量渲染内容；done event 在部分 agent 实现中承载最终完整结果。
        done_content = None
        text_content = ""
        agui_final_message_parser = None
        ag_ui_event_seen = False
        line_count = 0
        data_line_count = 0
        invalid_json_count = 0
        event_counts: dict[str, int] = {}
        stream_done = False
        event_done = False
        ag_ui_finished = False
        for raw_line in response.iter_lines(decode_unicode=False):
            line_count += 1
            if isinstance(raw_line, (bytes, bytearray)):
                line = raw_line.decode("utf-8", errors="replace")
            else:
                line = raw_line
            if not line or not line.startswith("data:"):
                continue
            data_line_count += 1
            data = line[len("data:") :].strip()
            if data == "[DONE]":
                event_counts["[DONE]"] = event_counts.get("[DONE]", 0) + 1
                stream_done = True
                break
            try:
                event = json.loads(data)
            except json.JSONDecodeError:
                invalid_json_count += 1
                continue
            if not isinstance(event, dict):
                invalid_json_count += 1
                continue
            event_type = event.get("event")
            ag_ui_event_type = event.get("type")
            event_type = event_type if isinstance(event_type, str) else ""
            ag_ui_event_type = ag_ui_event_type if isinstance(ag_ui_event_type, str) else ""
            event_key = event_type or ag_ui_event_type or "unknown"
            event_counts[event_key] = event_counts.get(event_key, 0) + 1
            content = event.get("content", "")
            content = content if isinstance(content, str) else ""
            cover = event.get("cover", False)
            if event_type == "error":
                error_code = event.get("code", 500)
                error_message = event.get("message", content or "智能体流式响应异常")
                logger.error(
                    "AI stream error event: code=%s, message_size=%s",
                    error_code,
                    len(str(error_message)),
                )
                raise APIRequestError(
                    module_name=self.module_name,
                    url=self.action,
                    status_code=error_code,
                    result=error_message,
                )
            if ag_ui_event_type:
                ag_ui_event_seen = True
                if agui_final_message_parser is None:
                    agui_final_message_parser = AGUIFinalMessageParser()
                agui_final_message_parser.consume(event)
                if ag_ui_event_type == "RUN_ERROR":
                    error_message = event.get("message") or event.get("error") or content or "智能体流式响应异常"
                    logger.error(
                        "AI AG-UI stream error event: message_size=%s",
                        len(str(error_message)),
                    )
                    raise APIRequestError(
                        module_name=self.module_name,
                        url=self.action,
                        status_code=500,
                        result=error_message,
                    )
                if ag_ui_event_type == "RUN_FINISHED":
                    ag_ui_finished = True
                    break
            if event_type == "done":
                done_content = content
                event_done = True
            elif event_type == "text":
                text_content = content if cover else text_content + content
            elif ag_ui_event_type == "TEXT_MESSAGE_CONTENT":
                delta = event.get("delta", "")
                text_content += delta if isinstance(delta, str) else ""
        terminal_seen = stream_done or event_done or ag_ui_finished
        clean_text_content = self._clean_final_content(text_content)
        clean_done_content = self._clean_final_content(done_content or "")
        final_content = clean_text_content or clean_done_content
        final_source = "text" if clean_text_content else "done" if clean_done_content else "empty"
        agui_final_message_required = ag_ui_event_seen
        agui_error_reason = ""
        if agui_final_message_required:
            if ag_ui_finished:
                final_content = agui_final_message_parser.get_final_content()
                agui_error_reason = agui_final_message_parser.error_reason
                if final_content:
                    final_content, agui_error_reason = self.postprocess_agui_final_content(final_content)
                final_source = "agui_final_message" if final_content else "agui_final_message_invalid"
            else:
                final_content = ""
                final_source = "agui_final_message_incomplete"
                agui_error_reason = "未收到 RUN_FINISHED"
        logger.info(
            "AI stream parsed: status_code=%s, line_count=%s, data_line_count=%s, invalid_json_count=%s, "
            "event_counts=%s, terminal_seen=%s, stream_done=%s, event_done=%s, ag_ui_finished=%s, "
            "text_size=%s, done_size=%s, final_size=%s, final_source=%s",
            getattr(response, "status_code", None),
            line_count,
            data_line_count,
            invalid_json_count,
            event_counts,
            terminal_seen,
            stream_done,
            event_done,
            ag_ui_finished,
            len(text_content),
            len(done_content or ""),
            len(final_content),
            final_source,
        )
        if not terminal_seen:
            error_message = (
                "智能体流式响应未完整结束，请稍后重试；"
                f"event_counts={event_counts}, text_size={len(text_content)}, done_size={len(done_content or '')}"
            )
            logger.error(
                "AI stream incomplete: status_code=%s, line_count=%s, data_line_count=%s, "
                "invalid_json_count=%s, event_counts=%s, text_size=%s, done_size=%s",
                getattr(response, "status_code", None),
                line_count,
                data_line_count,
                invalid_json_count,
                event_counts,
                len(text_content),
                len(done_content or ""),
            )
            raise APIRequestError(
                module_name=self.module_name,
                url=self.action,
                status_code=502,
                result=error_message,
            )
        if not final_content.strip():
            if agui_final_message_required:
                error_message = (
                    "AI AG-UI 流未得到最终 assistant 响应，请稍后重试；" f"reason={agui_error_reason}, event_counts={event_counts}"
                )
            else:
                error_message = (
                    "智能体流式响应内容为空，请稍后重试；"
                    f"event_counts={event_counts}, text_size={len(text_content)}, done_size={len(done_content or '')}"
                )
            logger.error(
                "AI stream parsed empty content: status_code=%s, headers=%s, event_counts=%s, "
                "text_size=%s, done_size=%s, agui_final_message_required=%s",
                getattr(response, "status_code", None),
                dict(getattr(response, "headers", {}) or {}),
                event_counts,
                len(text_content),
                len(done_content or ""),
                agui_final_message_required,
            )
            raise APIRequestError(
                module_name=self.module_name,
                url=self.action,
                status_code=502,
                result=error_message,
            )
        return final_content

    def parse_response(self, response):
        is_stream_response = self._is_stream_response(response)
        self._log_response_received(response, is_stream_response=is_stream_response)
        if is_stream_response:
            try:
                response.raise_for_status()
            except HTTPError as err:
                try:
                    result_json = response.json()
                except Exception:
                    result_json = {}
                content = str(err.response.content)
                if isinstance(result_json, dict):
                    content = "[{code}] {message}".format(
                        code=result_json.get("code"),
                        message=result_json.get("message"),
                    )
                raise APIRequestError(
                    module_name=self.module_name,
                    url=self.action,
                    status_code=response.status_code,
                    result=content,
                )
            return self._parse_stream_response(response)

        self._raise_standard_error_without_logging(response)
        data = super().parse_response(response)
        if isinstance(data, dict):
            logger.info("AI agent non-stream response parsed: keys=%s", list(data.keys()))
            if "content" in data:
                return data["content"]
            choices = data.get("choices")
            if choices and isinstance(choices, list):
                first = choices[0]
                if isinstance(first, dict):
                    delta = first.get("delta") or first.get("message") or {}
                    if isinstance(delta, dict) and "content" in delta:
                        return delta["content"]
        return data

    @staticmethod
    def _log_response_received(response, *, is_stream_response: bool) -> None:
        """记录响应传输元数据，禁止读取或输出业务正文。"""

        logger.info(
            "AI agent response received: status_code=%s, content_type=%s, stream_response=%s",
            getattr(response, "status_code", None),
            (response.headers.get("Content-Type") or response.headers.get("content-type") or "")
            if getattr(response, "headers", None)
            else "",
            is_stream_response,
        )

    def _raise_standard_error_without_logging(self, response) -> None:
        """在父类解析前抛出标准业务错误，避免其将错误正文写入普通日志。"""

        if not self.IS_STANDARD_FORMAT:
            return
        status_code = getattr(response, "status_code", None)
        # requests.Response 一定提供整数状态码；测试替身可能未设置该属性，
        # 此时交由父类的 raise_for_status() 维持原有 HTTP 错误处理语义。
        if not isinstance(status_code, int):
            return
        # 与 requests.Response.raise_for_status() 保持一致，仅 4xx/5xx
        # 由父类按 HTTP 错误处理，其余状态仍需在此拦截标准业务错误正文。
        if 400 <= status_code < 600:
            return
        try:
            result_json = response.json()
        except Exception:
            return
        if not isinstance(result_json, dict):
            return
        if result_json.get("result", True) or result_json.get("code") == 0:
            return
        # IAM 无权限响应由 BkApiResource 转换为 IAMNoPermission，并保留 permission/data 契约。
        if str(result_json.get("code")) == IAMNoPermission().code:
            return
        # 对齐父类异常协议，仅移除其本就不会放入 result 的 request_id。
        error_result = dict(result_json)
        error_result.pop("request_id", None)
        raise APIRequestError(
            module_name=self.module_name,
            url=self.action,
            result=error_result,
        )


class AGUIChatCompletion(ChatCompletion):
    """AG-UI 专用流式资源：透传过程事件并返回完整结果。

    Resource 是进程级单例，回调仅通过 ContextVar 在当前请求上下文传播，避免 gevent
    并发调用之间相互覆盖。事件正文和工具参数不写入普通日志。
    """

    name = gettext_lazy("AG-UI 智能体流式对话")
    _on_event_context: ContextVar[Callable[[dict[str, Any]], None] | None] = ContextVar("agui_on_event", default=None)

    def perform_request(self, validated_request_data):
        # bk_resource 允许调用方复用请求字典；回调只能从本次调用副本中剥离。
        request_data = dict(validated_request_data)
        token = self._on_event_context.set(request_data.pop("on_event", None))
        try:
            return super().perform_request(request_data)
        finally:
            self._on_event_context.reset(token)

    def parse_response(self, response):
        self._log_response_received(response, is_stream_response=True)
        response.raise_for_status()
        result = self._parse_agui_stream_response(response, on_event=self._on_event_context.get())
        logger.info(
            "AI AG-UI response parsed: event_count=%s, final_content_size=%s, final_result_type=%s",
            len(result.events),
            len(result.final_content),
            type(result.final_result).__name__,
        )
        return result

    @staticmethod
    def _parse_event(raw_line) -> dict[str, Any] | None:
        """解析单行 SSE data 帧，只接受含非空 type 的 AG-UI 对象事件。"""
        if isinstance(raw_line, (bytes, bytearray)):
            line = raw_line.decode("utf-8", errors="replace")
        else:
            line = raw_line
        if not line or not line.startswith("data:"):
            return None
        try:
            event = json.loads(line[len("data:") :].strip())
        except (TypeError, json.JSONDecodeError) as error:
            raise AGUIStreamProtocolError("AG-UI 事件不是 JSON 对象") from error
        if not isinstance(event, dict) or not isinstance(event.get("type"), str) or not event["type"]:
            raise AGUIStreamProtocolError("AG-UI 事件缺少 type")
        return event

    def _parse_agui_stream_response(self, response, on_event=None) -> AGUIStreamResponse:
        """解析完整 AG-UI 流，并在通过形态与容量校验后同步回调每个事件。"""
        events: list[dict[str, Any]] = []
        final_message_parser = AGUIFinalMessageParser()
        lifecycle = _AGUIRunLifecycle()
        # 容量上限约束返回的完整 JSON 数组，初始即包含空数组的 `[]`。
        serialized_bytes = 2
        run_finished = False
        final_result = None

        for raw_line in response.iter_lines(decode_unicode=False):
            event = self._parse_event(raw_line)
            if event is None:
                continue

            # 生命周期是所有事件副作用的前置门禁，非法事件不得进入归档、正文解析或业务回调。
            terminal = lifecycle.consume(event)
            event_count = len(events) + 1
            serialized_bytes += len(json.dumps(event, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
            if events:
                serialized_bytes += 1
            if event_count > settings.AI_ASSISTANT_STREAM_MAX_EVENTS:
                raise AGUIStreamCapacityExceeded("AG-UI 事件数超过上限")
            if serialized_bytes > settings.AI_ASSISTANT_STREAM_ARCHIVE_MAX_BYTES:
                raise AGUIStreamCapacityExceeded("AG-UI 事件体积超过上限")

            events.append(event)
            final_message_parser.consume(event)
            if on_event is not None:
                on_event(event)

            if event["type"] == "RUN_ERROR":
                raise AGUIStreamProtocolError("AG-UI 上游执行失败")
            if terminal:
                run_finished = True
                final_result = event.get("result")
                break

        lifecycle.ensure_terminal()
        if not run_finished:
            raise AGUIStreamProtocolError("AG-UI 流未收到 RUN_FINISHED")
        final_content = final_message_parser.get_final_content()
        if not final_content:
            raise AGUIStreamProtocolError(final_message_parser.error_reason)
        return AGUIStreamResponse(events=tuple(events), final_content=final_content, final_result=final_result)

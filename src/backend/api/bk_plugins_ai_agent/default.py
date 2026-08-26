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

from bk_resource import BkApiResource
from bk_resource.exceptions import APIRequestError
from blueapps.utils.logger import logger
from django.conf import settings
from django.utils.translation import gettext_lazy
from requests.exceptions import HTTPError

from api.bk_plugins_ai_agent.agui import AGUIFinalMessageParser
from api.bk_plugins_ai_agent.constants import (
    AI_STREAM_PREVIEW_LIMIT,
    AI_THINKING_PLACEHOLDERS,
)
from api.constants import AIAgentCode
from api.constants import AI_AGENT_APP_CODE_TMPL
from api.constants import AI_AGENT_SECRET_KEY_TMPL
from api.utils import get_agent_base_url


class AIAgentBase(BkApiResource, abc.ABC):
    """AI 智能体通用 API 基类

    与 AIAuditReport 共享相同的认证逻辑，但 URL 通过 get_agent_base_url 动态路由。
    不直接继承 AIAuditReport 以避免循环导入（bk_resource 按字母序扫描 api/ 目录）。

    凭证作用域与 URL 路由作用域保持一致（per-agent）：
      - 带 agent_code 的资源（ChatCompletion）优先读 BKAPP_AI_{AGENT}_APP_CODE/_SECRET_KEY；
      - 未命中时回退 AI_AUDIT_REPORT_APP_CODE/_SECRET_KEY → APP_CODE/SECRET_KEY；
      - 全局 BKAPP_AI_AGENT_APP_CODE/_SECRET_KEY 已废弃（2026-08-26 事故：全局凭证会把
        存量内网 agent 的凭证一并切换，与其内网网关路由错配，AIDev 返回 app not found）。
    """

    module_name = "bk_plugins_ai_agent"
    base_url = ""
    platform_authorization = True
    tags = ["AIAgent"]
    TIMEOUT = 300
    app_code_setting_names = ("AI_AUDIT_REPORT_APP_CODE",)
    secret_key_setting_names = ("AI_AUDIT_REPORT_SECRET_KEY",)
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
    """通用 AI Agent 对话接口，通过 agent_code 参数路由到不同智能体"""

    name = gettext_lazy("通用智能体对话")
    method = "POST"
    action = "/bk_plugin/openapi/agent/chat_completion/"

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
                request_data.get("agent_code"),
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
    def _content_preview(content: str, limit: int = AI_STREAM_PREVIEW_LIMIT) -> str:
        return (content or "").replace("\n", "\\n").replace("\r", "\\r")[:limit]

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
                logger.error("AI stream error event: code=%s, message=%s", error_code, error_message)
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
                    logger.error("AI AG-UI stream error event: message=%s", error_message)
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
            "text_size=%s, done_size=%s, final_size=%s, final_source=%s, preview_limit=%s",
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
            AI_STREAM_PREVIEW_LIMIT,
        )
        for part, content in (("text", text_content), ("done", done_content or ""), ("final", final_content)):
            logger.info(
                "AI stream content preview: part=%s, size=%s, preview=%s",
                part,
                len(content),
                self._content_preview(content),
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
        logger.info(
            "AI agent response received: status_code=%s, content_type=%s, stream_response=%s",
            getattr(response, "status_code", None),
            (response.headers.get("Content-Type") or response.headers.get("content-type") or "")
            if getattr(response, "headers", None)
            else "",
            is_stream_response,
        )
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

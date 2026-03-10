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

from bk_resource import BkApiResource
from bk_resource.exceptions import APIRequestError
from bk_resource.utils.common_utils import is_backend
from blueapps.utils.logger import logger
from django.conf import settings
from django.core.handlers.wsgi import WSGIRequest
from django.utils.translation import gettext_lazy
from requests.exceptions import HTTPError

from api.constants import AIAgentCode
from api.utils import get_agent_base_url


class AIAgentBase(BkApiResource, abc.ABC):
    """AI 智能体通用 API 基类

    与 AIAuditReport 共享相同的认证逻辑，但 URL 通过 get_agent_base_url 动态路由。
    不直接继承 AIAuditReport 以避免循环导入（bk_resource 按字母序扫描 api/ 目录）。
    """

    module_name = "bk_plugins_ai_agent"
    base_url = ""
    platform_authorization = True
    tags = ["AIAgent"]
    TIMEOUT = 300

    @property
    def app_code(self) -> str:
        return settings.AI_AGENT_APP_CODE or settings.AI_AUDIT_REPORT_APP_CODE or settings.APP_CODE

    @property
    def secret_key(self) -> str:
        return settings.AI_AGENT_SECRET_KEY or settings.AI_AUDIT_REPORT_SECRET_KEY or settings.SECRET_KEY

    def add_esb_info_before_request(self, params: dict) -> dict:
        params["bk_app_code"] = self.app_code
        params["bk_app_secret"] = self.secret_key

        if params.pop("_is_backend", False) or is_backend():
            params.pop("_request", None)
            params = self.add_platform_auth_params(params, force_platform_auth=True)
            return params

        from blueapps.utils.request_provider import get_local_request

        _request = params.pop("_request", None)
        req: WSGIRequest = _request or get_local_request()

        auth_info = self.build_auth_args(req)
        params.update(auth_info)
        if req is not None:
            user = getattr(req, "user", None)
            if user:
                params["bk_username"] = getattr(user, "bk_username", None) or getattr(user, "username", None) or ""

        params = self.add_platform_auth_params(params)
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
        base_url = get_agent_base_url(agent_code)
        return base_url.rstrip("/") + "/" + self.action.lstrip("/")

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
            if execute_kwargs.get("stream"):
                kwargs["stream"] = True
        return kwargs

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

    def _parse_stream_response(self, response) -> str:
        # done event 仅用于日志记录（平台元数据），实际内容始终从 text event 拼接
        done_content = None
        text_content = ""
        for line in response.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data:"):
                continue
            data = line[len("data:") :].strip()
            if data == "[DONE]":
                break
            try:
                event = json.loads(data)
            except json.JSONDecodeError:
                continue
            event_type = event.get("event")
            content = event.get("content", "")
            cover = event.get("cover", False)
            if event_type == "done":
                done_content = content
            elif event_type == "text":
                text_content = content if cover else text_content + content
        if done_content is not None:
            logger.debug("AI stream done content: %s", done_content)
        logger.debug("AI stream text content: %s", text_content)
        return text_content

    def parse_response(self, response):
        if self._is_stream_response(response):
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

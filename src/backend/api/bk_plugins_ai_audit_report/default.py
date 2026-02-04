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
from django.conf import settings
from django.core.handlers.wsgi import WSGIRequest
from django.utils.translation import gettext_lazy
from requests.exceptions import HTTPError

from api.domains import AI_AUDIT_REPORT_API_URL


class AIAuditReport(BkApiResource, abc.ABC):
    """AI审计报告智能体API基类"""

    module_name = "bk_plugins_ai_audit_report"
    base_url = AI_AUDIT_REPORT_API_URL
    platform_authorization = True
    tags = ["AIAuditReport"]
    TIMEOUT = 300  # 执行超时时间（秒）

    @property
    def app_code(self) -> str:
        """获取 APP_CODE，优先使用自定义配置"""
        return settings.AI_AUDIT_REPORT_APP_CODE or settings.APP_CODE

    @property
    def secret_key(self) -> str:
        """获取 SECRET_KEY，优先使用自定义配置"""
        return settings.AI_AUDIT_REPORT_SECRET_KEY or settings.SECRET_KEY

    def add_esb_info_before_request(self, params: dict) -> dict:
        """
        添加API鉴权信息，支持自定义 APP_CODE 和 SECRET_KEY
        完全重写父类方法，避免并发问题
        """
        # 使用自定义的 APP_CODE 和 SECRET_KEY
        params["bk_app_code"] = self.app_code
        params["bk_app_secret"] = self.secret_key

        # 后台程序或非request请求直接返回
        if params.pop("_is_backend", False) or is_backend():
            params.pop("_request", None)
            params = self.add_platform_auth_params(params, force_platform_auth=True)
            return params

        # 前端应用, _request，用于并发请求的场景
        from blueapps.utils.request_provider import get_local_request

        # 获取请求
        _request = params.pop("_request", None)
        req: WSGIRequest = _request or get_local_request()

        # 添加鉴权信息
        auth_info = self.build_auth_args(req)
        params.update(auth_info)
        if req is not None:
            user = getattr(req, "user", None)
            if user:
                params["bk_username"] = getattr(user, "bk_username", None) or getattr(user, "username", None) or ""

        # 平台鉴权兼容
        params = self.add_platform_auth_params(params)

        return params


class ChatCompletion(AIAuditReport):
    """智能体对话接口（应用态）

    接口协议：
    请求头：
    - X-BKAIDEV-USER: 会话用户名（必须）

    请求体：
    {
      "input": "用户内容",
      "chat_history": [
        {"role": "user", "content": "用户内容"},
        {"role": "assistant", "content": "AI内容"}
      ],
      "execute_kwargs": {
        "stream": true/false
      }
    }
    """

    name = gettext_lazy("智能体对话")
    method = "POST"
    action = "/bk_plugin/openapi/agent/chat_completion/"

    def build_header(self, validated_request_data):
        """构建请求头，添加 X-BKAIDEV-USER"""
        headers = super().build_header(validated_request_data)
        # 从请求参数中取出 user 并设置到请求头
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
        done_cover_content = None
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
                if cover:
                    done_cover_content = content
                else:
                    text_content += content
            elif event_type == "text":
                text_content = content if cover else text_content + content
        if done_cover_content is not None:
            return done_cover_content
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
        if isinstance(data, dict) and "content" in data:
            return data.get("content")
        return data

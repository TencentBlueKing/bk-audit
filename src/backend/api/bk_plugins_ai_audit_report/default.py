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

from bk_resource import BkApiResource
from django.utils.translation import gettext_lazy

from api.domains import AI_AUDIT_REPORT_API_URL


class AIAuditReport(BkApiResource, abc.ABC):
    """AI审计报告智能体API基类"""

    module_name = "bk_plugins_ai_audit_report"
    base_url = AI_AUDIT_REPORT_API_URL
    platform_authorization = True
    tags = ["AIAuditReport"]


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

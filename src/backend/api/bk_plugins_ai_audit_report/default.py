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

from django.utils.translation import gettext_lazy

from api.bk_plugins_ai_agent.default import AIAgentBase
from api.bk_plugins_ai_agent.default import ChatCompletion as BaseChatCompletion
from api.domains import AI_AUDIT_REPORT_API_URL


class AIAuditReport(AIAgentBase, abc.ABC):
    """AI审计报告智能体API基类（向后兼容别名）"""

    module_name = "bk_plugins_ai_audit_report"
    base_url = AI_AUDIT_REPORT_API_URL
    tags = ["AIAuditReport"]


class ChatCompletion(BaseChatCompletion):
    """审计报告智能体对话接口（固定路由到 AUDIT_REPORT agent）

    保持 api.bk_plugins_ai_audit_report.chat_completion 的调用方式不变，
    调用方无需传 agent_code 参数。
    """

    module_name = "bk_plugins_ai_audit_report"
    name = gettext_lazy("智能体对话")

    def build_url(self, validated_request_data):
        return AI_AUDIT_REPORT_API_URL.rstrip("/") + "/" + self.action.lstrip("/")

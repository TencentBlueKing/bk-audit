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

from enum import Enum

from django.conf import settings
from django.db.models import TextChoices
from django.utils.translation import gettext_lazy

ESB_PREFIX = "/api/c/compapi/v2/"
ESB_URL_FORMAT = "{}{}{{}}".format(settings.BK_COMPONENT_API_URL, ESB_PREFIX)

APIGW_URL_FORMAT = "{}/{{stage}}".format(settings.BK_API_URL_TMPL)


class APIProvider(Enum):
    APIGW = "apigw"
    ESB = "esb"


# AI Agent 环境变量模板
# 完整 URL 覆盖：BKAPP_AI_{AGENT_CODE}_API_URL
AI_AGENT_API_URL_TMPL = "BKAPP_AI_{}_API_URL"
# APIGW 网关名覆盖：BKAPP_AI_{AGENT_CODE}_APIGW_NAME
AI_AGENT_APIGW_NAME_TMPL = "BKAPP_AI_{}_APIGW_NAME"


class AIAgentCode(TextChoices):
    """AI 智能体标识枚举

    value 为默认 APIGW 网关名，新增 agent 只需加一行。
    环境变量按模板自动生效：
      - BKAPP_AI_{name}_API_URL      完整 URL（优先级最高）
      - BKAPP_AI_{name}_APIGW_NAME   覆盖网关名
    """

    AUDIT_REPORT = "bp-ai-audit-report", gettext_lazy("风险报告智能体")
    RISK_SEARCH = "bp-ai-aud-rsk-srch", gettext_lazy("风险检索助手")

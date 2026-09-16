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

import datetime
import uuid

from bk_resource.settings import bk_resource_settings
from django.utils import timezone
from django.utils.translation import gettext
from rest_framework.settings import api_settings

from apps.itsm.constants import TicketStatus
from apps.sops.constants import SOPSTaskStatus
from services.web.risk.constants import RiskStatus

RISK_INFO = {
    "event_content": gettext("Admin 风险"),
    "raw_event_id": uuid.uuid1().hex,
    "strategy_id": 1,
    "event_evidence": "[]",
    "event_type": ["SuperPermission"],
    "event_data": {"username": "admin"},
    "event_time": timezone.now(),
    "event_end_time": timezone.now(),
    "event_source": "bkm",
    "operator": ["admin"],
    "status": RiskStatus.NEW,
}

PA_INFO = {
    "name": gettext("自动处理套餐"),
    "sops_template_id": 1,
    "need_approve": True,
    "approve_service_id": 1,
    "approve_config": {"risk_level": {"value": "high"}},
    "description": "",
}

RULE_INFO = {
    "name": gettext("自动处理规则"),
    "scope": [{"field": "operator", "value": ["admin"], "operator": "="}],
    "pa_params": {"${operator}": {"field": "operator"}},
    "auto_close_risk": False,
}

# V4 Workflows 接口返回的完整响应（取自真实网关响应，bk_resource 已解包信封）：
# workflows() 直接返回 {"items":[workflow, ...]}，workflow 的表单字段定义位于
# form_canvas_data.jsonschema.properties，key 带 ticket__ 命名空间前缀
APPROVE_SERVICE_INFO = {
    "items": [
        {
            "form_canvas_data": {
                "jsonschema": {
                    "type": "object",
                    "properties": {
                        "ticket__title": {"type": "string", "title": "标题"},
                        "ticket__process_application_name": {"type": "string", "title": "处理套餐名称"},
                        "ticket__tags": {"type": "string", "title": "标签"},
                        "ticket__operator": {"type": "string", "title": "责任人"},
                        "ticket__risk_url": {"type": "string", "title": "审计关联单据"},
                        "ticket__raw_event_id": {"type": "string", "title": "原始事件ID"},
                    },
                }
            }
        }
    ]
}

APPROVE_TICKET_DETAIL = {"id": uuid.uuid1().hex, "sn": uuid.uuid1().hex}

APPROVE_TICKET_STATUS = {
    "id": uuid.uuid1().hex,
    "title": gettext("【审计中心】执行自动处理套餐审批"),
    "update_at": datetime.datetime.now().strftime(api_settings.DATETIME_FORMAT),
    "ticket_url": "https://bk.tencnet.com",
    "updated_by": bk_resource_settings.PLATFORM_AUTH_ACCESS_USERNAME,
    "approve_result": True,
    "current_status": TicketStatus.RUNNING.value,
}

CUSTOM_AUTO_PROCESS_PARAMS = {"pa_params": {"${operator}": {"field": "operator"}}, "auto_close_risk": False}

SOPS_TEMPLATE_INFO = {"pipeline_tree": {"constants": {"${operator}": {"key": "${operator}"}}}}

SOPS_FLOW_STATUS = {
    "state": SOPSTaskStatus.RUNNING.value,
}
SOPS_FLOW_INFO = {"task_id": 1}

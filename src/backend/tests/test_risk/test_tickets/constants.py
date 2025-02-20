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
from services.web.risk.constants import (
    ApproveTicketFields,
    EventMappingFields,
    RiskStatus,
)

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

APPROVE_SERVICE_INFO = {
    "fields": [
        {"key": ApproveTicketFields.TITLE.key},
        {"key": ApproveTicketFields.PROCESS_APPLICATION_NAME_FIELD.key},
        {"key": ApproveTicketFields.TAGS.key},
        {"key": ApproveTicketFields.OPERATOR.key},
        {"key": ApproveTicketFields.RISK_URL.key},
        {"key": EventMappingFields.RAW_EVENT_ID.field_name},
    ]
}

APPROVE_TICKET_DETAIL = {"sn": uuid.uuid1().hex}

APPROVE_TICKET_STATUS = {
    "sn": uuid.uuid1().hex,
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

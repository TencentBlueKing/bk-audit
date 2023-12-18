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

from bk_audit.client import BkAudit
from bk_audit.constants.log import DEFAULT_EMPTY_VALUE, DEFAULT_RESULT_CODE
from bk_audit.contrib.opentelemetry.exporters import OTLogExporter
from bk_audit.contrib.opentelemetry.utils import ServiceNameHandler
from django.conf import settings

from apps.audit.formatters import AuditFormatter


class BkAuditClient(BkAudit):
    def add_event(
        self,
        action,
        resource_type=None,
        instance=None,
        audit_context=None,
        event_id=None,
        event_content=DEFAULT_EMPTY_VALUE,
        start_time=None,
        end_time=None,
        result_code=DEFAULT_RESULT_CODE,
        result_content=DEFAULT_EMPTY_VALUE,
        extend_data=DEFAULT_EMPTY_VALUE,
    ):
        from blueapps.utils.request_provider import get_request_username

        username = get_request_username()
        if not username:
            return
        super().add_event(
            action=action,
            resource_type=resource_type,
            instance=instance,
            audit_context=audit_context,
            event_id=event_id,
            event_content=event_content,
            start_time=start_time,
            end_time=end_time,
            result_code=result_code,
            result_content=result_content,
            extend_data=extend_data,
        )


bk_audit_client = BkAuditClient(
    settings.APP_CODE,
    settings.SECRET_KEY,
    {"formatter": AuditFormatter(), "exporters": [OTLogExporter()], "service_name_handler": ServiceNameHandler},
)

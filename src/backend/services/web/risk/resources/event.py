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

import uuid
from typing import List

from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy

from apps.audit.resources import AuditMixinResource
from apps.meta.models import GlobalMetaConfig
from core.utils.tools import get_app_info
from services.web.risk.constants import ENABLE_EVENTS_MOCK_KEY, EVENTS_MOCK_DATA_KEY
from services.web.risk.handlers import EventHandler
from services.web.risk.handlers.risk import RiskHandler
from services.web.risk.models import Risk
from services.web.risk.serializers import (
    CreateEventAPIResponseSerializer,
    CreateEventAPISerializer,
    ListEventRequestSerializer,
    ListEventResponseSerializer,
)
from services.web.risk.tasks import add_event


class EventMeta(AuditMixinResource):
    tags = ["Event"]


class CreateEvent(EventMeta):
    name = gettext_lazy("创建事件")
    RequestSerializer = CreateEventAPISerializer
    ResponseSerializer = CreateEventAPIResponseSerializer
    bind_request = True

    ADMIN_SOURCE = "ADMIN"  # 常量定义超级管理员来源标识

    def _create_events(self, events: List[dict], source: str):
        event_ids = []
        for event in events:
            event["event_id"] = "{}{}".format(
                event.get("strategy_id") or source, event["raw_event_id"] or uuid.uuid1().hex
            )
            event["event_source"] = source
            event_ids.append(event["event_id"])
        return event_ids

    def perform_request(self, validated_request_data: dict):
        gen_risk = validated_request_data.get("gen_risk", False)
        events = validated_request_data["events"]
        # 检查超级管理员权限
        req = validated_request_data.get("_request")
        if req and req.user.is_superuser:
            source = self.ADMIN_SOURCE
        # 校验调用身份
        else:
            app = get_app_info()
            source = app.bk_app_code
        event_ids = self._create_events(events, source)
        if gen_risk:
            for event in events:
                RiskHandler().generate_risk(event)
        add_event(events)
        return {"event_ids": event_ids}


class ListEvent(EventMeta):
    name = gettext_lazy("获取事件列表")
    RequestSerializer = ListEventRequestSerializer
    ResponseSerializer = ListEventResponseSerializer

    def perform_request(self, validated_request_data):
        risk = get_object_or_404(Risk, risk_id=validated_request_data.pop("risk_id"))
        validated_request_data.update({"raw_event_id": risk.raw_event_id, "strategy_id": str(risk.strategy_id)})
        if GlobalMetaConfig.get(ENABLE_EVENTS_MOCK_KEY, default=False) and GlobalMetaConfig.get(
            EVENTS_MOCK_DATA_KEY, default=[]
        ):
            return {
                "page": 1,
                "num_pages": 50,
                "total": 1,
                "results": GlobalMetaConfig.get(EVENTS_MOCK_DATA_KEY),
            }
        return EventHandler.search_event(**validated_request_data)

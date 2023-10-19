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

from bk_resource import Resource
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy

from core.utils.tools import get_app_info
from services.web.risk.handlers import EventHandler
from services.web.risk.models import Risk
from services.web.risk.serializers import (
    CreateEventAPIResponseSerializer,
    CreateEventAPISerializer,
    ListEventRequestSerializer,
    ListEventResponseSerializer,
)
from services.web.risk.tasks import add_event


class EventMeta:
    tags = ["Event"]


class CreateEvent(EventMeta, Resource):
    name = gettext_lazy("创建事件")
    RequestSerializer = CreateEventAPISerializer
    ResponseSerializer = CreateEventAPIResponseSerializer

    def perform_request(self, validated_request_data):
        # 校验调用身份
        app = get_app_info()
        # 创建事件
        event_ids = []
        for event in validated_request_data["events"]:
            event["event_id"] = "{}{}".format(
                event.get("strategy_id") or app.bk_app_code, event["raw_event_id"] or uuid.uuid1().hex
            )
            event["event_source"] = app.bk_app_code
            event_ids.append(event["event_id"])
        add_event(validated_request_data)
        return {"event_ids": event_ids}


class ListEvent(EventMeta, Resource):
    name = gettext_lazy("获取事件列表")
    RequestSerializer = ListEventRequestSerializer
    ResponseSerializer = ListEventResponseSerializer

    def perform_request(self, validated_request_data):
        risk = get_object_or_404(Risk, risk_id=validated_request_data.pop("risk_id"))
        validated_request_data.update({"raw_event_id": risk.raw_event_id, "strategy_id": str(risk.strategy_id)})
        return EventHandler.search_event(**validated_request_data)

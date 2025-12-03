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
from typing import List

from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.translation import gettext, gettext_lazy
from rest_framework import serializers

from apps.audit.resources import AuditMixinResource
from core.utils.tools import get_app_info
from services.web.risk.constants import RiskStatus
from services.web.risk.handlers import EventHandler
from services.web.risk.handlers.risk import RiskHandler
from services.web.risk.models import Risk
from services.web.risk.permissions import GenerateStrategyRiskPermission
from services.web.risk.serializers import (
    CreateEventAPIResponseSerializer,
    CreateEventAPISerializer,
    ListEventRequestSerializer,
    ListEventResponseSerializer,
)
from services.web.risk.tasks import manual_add_event
from services.web.strategy_v2.constants import StrategyType
from services.web.strategy_v2.models import Strategy


class EventMeta(AuditMixinResource):
    tags = ["Event"]


class CreateEvent(EventMeta):
    name = gettext_lazy("创建事件")
    RequestSerializer = CreateEventAPISerializer
    ResponseSerializer = CreateEventAPIResponseSerializer
    bind_request = True

    def _create_events(self, events: List[dict], source: str):
        event_ids = []
        for event in events:
            event["event_id"] = "{}{}".format(event.get("strategy_id"), event["raw_event_id"] or uuid.uuid1().hex)
            event["event_source"] = source
            event_ids.append(event["event_id"])
        return event_ids

    def perform_request(self, validated_request_data: dict):
        gen_risk = validated_request_data.get("gen_risk", False)
        events = validated_request_data["events"]
        if not gen_risk:
            bound_risk = self._validate_existing_risk(validated_request_data.get("risk_id"), events)
            self._sync_raw_event_id_with_risk(events, bound_risk)
            self._ensure_model_strategy(bound_risk.strategy_id)
        else:
            for event in events:
                self._ensure_model_strategy(event["strategy_id"])
        req = validated_request_data.get("_request")
        if req and getattr(req, "user", None) and getattr(req.user, "is_authenticated", False):
            GenerateStrategyRiskPermission(req).ensure_allowed(events)
            source = req.user.username
        else:
            app = get_app_info()
            source = app.bk_app_code
        event_ids = self._create_events(events, source)
        manual_add_event(events)
        risk_ids = []
        eligible_strategy_ids = RiskHandler.fetch_eligible_strategy_ids()  # 更新 eligible_strategy_ids
        for event in events:
            risk_id = RiskHandler().generate_risk(event, eligible_strategy_ids, manual=True)
            if risk_id:
                risk_ids.append(risk_id)
        return {"event_ids": event_ids, "risk_ids": risk_ids}

    def _validate_existing_risk(self, risk_id: str, events: List[dict]) -> Risk:
        if not risk_id:
            raise serializers.ValidationError(gettext("风险ID不能为空"))

        risk = (
            Risk.objects.filter(risk_id=str(risk_id))
            .only("status", "event_time", "event_end_time", "strategy_id")
            .first()
        )
        if not risk:
            raise serializers.ValidationError(gettext("风险不存在或不可用"))

        tz = timezone.get_current_timezone()
        for event in events:
            strategy_id = event["strategy_id"]
            if strategy_id and int(strategy_id) != risk.strategy_id:
                raise serializers.ValidationError(gettext("事件所属策略与风险不一致"))

            if risk.status == RiskStatus.CLOSED:
                raise serializers.ValidationError(gettext("风险单已关闭，无法添加事件"))

            event_dt = datetime.datetime.fromtimestamp(event["event_time"] / 1000, tz=tz)
            if not risk.event_time <= event_dt:
                raise serializers.ValidationError(gettext("事件时间不在风险有效区间内"))
        return risk

    def _sync_raw_event_id_with_risk(self, events: List[dict], risk: Risk):
        for event in events:
            event["raw_event_id"] = risk.raw_event_id

    def _ensure_model_strategy(self, strategy_id: int):
        strategy = Strategy.objects.filter(strategy_id=strategy_id).only("strategy_type").first()
        if not strategy:
            raise serializers.ValidationError(gettext("策略不存在"))
        if strategy.strategy_type != StrategyType.RULE:
            raise serializers.ValidationError(gettext("仅支持规则审计策略创建事件"))


class ListEvent(EventMeta):
    name = gettext_lazy("获取事件列表")
    RequestSerializer = ListEventRequestSerializer
    ResponseSerializer = ListEventResponseSerializer

    def perform_request(self, validated_request_data):
        risk = get_object_or_404(Risk, risk_id=validated_request_data.pop("risk_id"))
        _ = validated_request_data.pop("_request", None)
        validated_request_data.update({"raw_event_id": risk.raw_event_id, "strategy_id": str(risk.strategy_id)})
        return EventHandler.search_event(**validated_request_data)

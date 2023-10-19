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
import json
import math
import re
from typing import List, Union

from blueapps.utils.logger import logger
from django.conf import settings
from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone
from django.utils.translation import gettext
from rest_framework.settings import api_settings

from apps.meta.models import GlobalMetaConfig
from apps.meta.utils.saas import get_saas_url
from apps.notice.handlers import ErrorMsgHandler
from apps.notice.models import (
    NoticeButton,
    NoticeContent,
    NoticeContentConfig,
    NoticeGroup,
)
from apps.notice.tasks import send_notice
from services.web.risk.constants import (
    EVENT_DATA_SORT_FIELD,
    EVENT_DATA_TIME_DURATION_HOURS,
    EVENT_OPERATOR_SPLIT_REGEX,
    EVENT_TYPE_SPLIT_REGEX,
    RISK_ESQUERY_DELAY_TIME,
    RISK_SYNC_BATCH_SIZE,
    RISK_SYNC_START_TIME_KEY,
    EventMappingFields,
    RiskStatus,
)
from services.web.risk.handlers import EventHandler
from services.web.risk.models import Risk
from services.web.risk.serializers import CreateRiskSerializer
from services.web.strategy_v2.models import Strategy, StrategyTag


class RiskHandler:
    """
    Deal with Risk
    """

    @transaction.atomic()
    def generate_risk_from_event(self) -> None:
        """
        从事件生成风险
        """

        events = self.load_events()
        for event in events:
            try:
                is_create, risk = self.create_risk(event)
                if is_create:
                    self.send_risk_notice(risk)

                    from services.web.risk.tasks import process_risk_ticket

                    process_risk_ticket(risk_id=risk.risk_id)
            except Exception as err:  # NOCC:broad-except(需要处理所有错误)
                logger.exception("[CreateRiskFailed] Event: %s; Error: %s", json.dumps(event), err)
                ErrorMsgHandler(
                    title=gettext("Create Risk Failed"),
                    content=gettext("Strategy ID: %s; Raw Event ID:\t%s")
                    % (
                        event.get("strategy_id"),
                        event.get("raw_event_id"),
                    ),
                ).send()

    def load_events(self) -> List[dict]:
        """
        加载事件
        """

        # 获取起始时间
        start_time_ts = GlobalMetaConfig.get(
            config_key=RISK_SYNC_START_TIME_KEY,
            default=math.floor(
                (datetime.datetime.now() - datetime.timedelta(hours=EVENT_DATA_TIME_DURATION_HOURS)).timestamp()
            ),
        )
        start_time = datetime.datetime.fromtimestamp(start_time_ts)
        end_time = datetime.datetime.now() - datetime.timedelta(seconds=RISK_ESQUERY_DELAY_TIME)

        # 加载数据
        data = EventHandler.search_all_event(
            namespace=settings.DEFAULT_NAMESPACE,
            start_time=start_time.strftime(api_settings.DATETIME_FORMAT),
            end_time=end_time.strftime(api_settings.DATETIME_FORMAT),
            page=1,
            page_size=RISK_SYNC_BATCH_SIZE,
            sort_list=EVENT_DATA_SORT_FIELD,
        )
        logger.info("[LoadEventSuccess] Total %d", len(data))

        # 存储起始时间
        GlobalMetaConfig.set(config_key=RISK_SYNC_START_TIME_KEY, config_value=math.floor(end_time.timestamp()))

        return data

    def create_risk(self, event: dict) -> (bool, Risk):
        """
        创建或更新风险
        """

        # 校验数据
        serializer = CreateRiskSerializer(data=event)
        if not serializer.is_valid():
            logger.error("[CreateRiskFailed] Event Invalid: %s", json.dumps(event))
            return False, None
        event = serializer.validated_data

        # 检查是否有已存在的
        risk = (
            Risk.objects.filter(strategy_id=event["strategy_id"], raw_event_id=event["raw_event_id"])
            .exclude(status=RiskStatus.CLOSED)
            .order_by("-event_time")
            .first()
        )

        # 存在则更新结束事件
        if risk:
            risk.event_end_time = datetime.datetime.fromtimestamp(event["event_time"] / 1000)
            risk.save(update_fields=["event_end_time"])
            return False, None

        # 不存在则创建
        return True, Risk.objects.create(
            event_content=event.get("event_content"),
            raw_event_id=event["raw_event_id"],
            strategy_id=event["strategy_id"],
            event_evidence=event.get("event_evidence"),
            event_type=self.parse_event_type(event.get("event_type")),
            event_data=event.get("event_data"),
            event_time=datetime.datetime.fromtimestamp(event["event_time"] / 1000),
            event_end_time=datetime.datetime.fromtimestamp(event["event_time"] / 1000),
            event_source=event.get("event_source"),
            operator=self.parse_operator(event.get("operator")),
            tags=list(StrategyTag.objects.filter(strategy_id=event["strategy_id"]).values_list("tag_id", flat=True)),
        )

    def parse_operator(self, operator: str) -> List[str]:
        operators = [str(o) for o in re.split(EVENT_OPERATOR_SPLIT_REGEX, (operator or "")) if o]
        return operators

    def parse_event_type(self, event_type: str) -> List[str]:
        event_types = [t for t in re.split(EVENT_TYPE_SPLIT_REGEX, (event_type or "")) if t]
        return event_types

    def send_risk_notice(self, risk: Risk) -> None:
        """
        发送通知
        """

        # 获取策略
        strategy = Strategy.objects.filter(strategy_id=risk.strategy_id).first()
        if not strategy:
            return

        # 获取通知组
        notice_groups = NoticeGroup.objects.filter(group_id__in=(strategy.notice_groups or []))
        if not notice_groups:
            return

        # 构造标题
        title = "【{}】{} - {}".format(
            gettext("BkAudit"),
            gettext("新增风险提醒"),
            strategy.strategy_name,
        )

        # 发送通知
        self.send_notice(risk=risk, notice_groups=notice_groups, title=title, strategy=strategy)

        # 更新风险的通知人员名单
        notice_users = []
        for notice_group in notice_groups:
            notice_users.extend(notice_group.group_member if isinstance(notice_group.group_member, list) else [])
        risk.notice_users = notice_users
        risk.save(update_fields=["notice_users"])

    @classmethod
    def send_notice(
        cls,
        risk: Risk,
        notice_groups: Union[QuerySet, List[NoticeGroup]],
        title: str,
        strategy: Strategy = None,
        show_handle: bool = False,
        skip_recent_check: bool = True,
    ) -> None:
        """
        发送通知
        """

        # 构造内容
        risk_time = risk.event_time.astimezone(timezone.get_current_timezone())
        risk_url = "{}/risk-manage/detail/{}{}".format(
            get_saas_url(settings.APP_CODE), risk.risk_id, "?tab=handleRisk" if show_handle else ""
        )
        notice_contents = [
            NoticeContentConfig(
                key="risk_id", name=gettext("Risk ID"), value=f'<a href="{risk_url}">{risk.risk_id}</a>'
            ),
            NoticeContentConfig(
                key=EventMappingFields.EVENT_CONTENT.field_name,
                name=gettext("风险描述"),
                value=risk.event_content or "- -",
            ),
        ]
        if strategy:
            notice_contents.append(
                NoticeContentConfig(
                    key="strategy", name=gettext("命中策略"), value=f"{strategy.strategy_name}({strategy.strategy_id})"
                )
            )
        notice_contents.extend(
            [
                NoticeContentConfig(
                    key=EventMappingFields.OPERATOR.field_name,
                    name=gettext("责任人"),
                    value="; ".join(risk.operator if isinstance(risk.operator, list) else []) or "- -",
                ),
                NoticeContentConfig(
                    key=EventMappingFields.EVENT_TIME.field_name,
                    name=gettext("风险发现时间"),
                    value=risk_time.strftime(api_settings.DATETIME_FORMAT),
                ),
            ]
        )
        content = NoticeContent(*notice_contents)
        button = NoticeButton(
            text=gettext("Show Detail"),
            url=risk_url,
        )

        # 发送通知
        for notice_group in notice_groups:
            send_notice.delay(
                notice_group=notice_group,
                title=title,
                content=content,
                button=button,
                skip_recent_check=skip_recent_check,
            )

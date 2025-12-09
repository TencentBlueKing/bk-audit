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
from typing import List, Optional, Set, Tuple, Union

from bk_resource import resource
from blueapps.utils.logger import logger
from django.conf import settings
from django.db.models import Q, QuerySet
from django.utils import timezone
from django.utils.translation import gettext
from rest_framework.settings import api_settings

from apps.meta.models import GlobalMetaConfig
from apps.meta.utils.format import preprocess_data
from apps.notice.constants import RelateType
from apps.notice.handlers import ErrorMsgHandler
from apps.notice.models import NoticeGroup
from core.exceptions import ValidationError
from core.render import Jinja2Renderer, VariableUndefined
from services.web.risk.constants import (
    EVENT_DATA_SORT_FIELD,
    EVENT_TYPE_SPLIT_REGEX,
    RISK_SYNC_BATCH_SIZE,
    RISK_SYNC_START_TIME_KEY,
    EventMappingFields,
    RiskStatus,
)
from services.web.risk.handlers import EventHandler
from services.web.risk.models import Risk
from services.web.risk.parser import RiskNoticeParser
from services.web.risk.serializers import CreateRiskSerializer
from services.web.strategy_v2.constants import StrategyStatusChoices
from services.web.strategy_v2.models import Strategy


class RiskHandler:
    """
    Deal with Risk
    """

    @classmethod
    def fetch_eligible_strategy_ids(cls) -> Set[str]:
        """
        获取可用策略ID集合
        """
        return set(
            Strategy.objects.exclude(status=StrategyStatusChoices.DISABLED.value).values_list("strategy_id", flat=True)
        )

    def generate_risk(self, event: dict, eligible_strategy_ids: Set[str], manual: bool = False):
        """
        生成风险
        :param event: 事件
        :param eligible_strategy_ids: 可用策略ID集合
        :param manual: 是否手动创建
        """
        try:
            is_create, risk = self.create_risk(event, eligible_strategy_ids, manual=manual)
            if is_create:
                self.send_risk_notice(risk)

                from services.web.risk.tasks import process_risk_ticket

                process_risk_ticket(risk_id=risk.risk_id)
            return risk.risk_id
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

    def generate_risk_from_event(self, start_time: datetime.datetime, end_time: datetime.datetime) -> None:
        """
        从事件生成风险
        """
        eligible_strategy_ids = self.fetch_eligible_strategy_ids()
        events = self.load_events(start_time, end_time)
        for event in events:
            self.generate_risk(event, eligible_strategy_ids)

    def load_events(self, start_time: datetime.datetime, end_time: datetime.datetime) -> List[dict]:
        """
        加载事件
        """

        # 加载数据
        data = EventHandler.search_all_event(
            namespace=settings.DEFAULT_NAMESPACE,
            start_time=start_time.strftime(api_settings.DATETIME_FORMAT),
            end_time=end_time.strftime(api_settings.DATETIME_FORMAT),
            page=1,
            page_size=RISK_SYNC_BATCH_SIZE,
            sort_list=EVENT_DATA_SORT_FIELD,
            include_end_time=False,
        )
        logger.info("[LoadEventSuccess] Total %d", len(data))

        # 存储起始时间
        GlobalMetaConfig.set(config_key=RISK_SYNC_START_TIME_KEY, config_value=math.floor(end_time.timestamp()))

        return data

    @classmethod
    def render_risk_title(cls, create_params: dict) -> Optional[str]:
        """
        生成风险标题
        自动处理变量中的 list 类型，渲染为逗号拼接的字符串
        """
        create_params = create_params.copy()
        strategy: Strategy = Strategy.objects.filter(strategy_id=create_params["strategy_id"]).first()
        if not strategy or not strategy.risk_title:
            return None

        # 事件证据为字符串需要转换成列表，并取第一条字典数据
        try:
            event_evidence = json.loads(create_params["event_evidence"])[0]
        except (json.JSONDecodeError, IndexError, KeyError):
            event_evidence = {}
        create_params["event_evidence"] = event_evidence

        processed_params = preprocess_data(create_params)

        try:
            risk_title = Jinja2Renderer(undefined=VariableUndefined, autoescape=True).jinja_render(
                strategy.risk_title,
                processed_params,  # 使用预处理后的参数
            )
            return risk_title
        except Exception as err:  # NOCC:broad-except(需要处理所有错误)
            logger.exception(
                "[RenderRiskTitleFailed] risk_title: %s; risk_content: %s; err: %s",
                strategy.risk_title,
                create_params,
                err,
            )
            return strategy.risk_title

    def gen_risk_create_params(self, event: dict, manual: bool = False) -> dict:
        create_params = {
            "event_content": event.get("event_content"),
            "raw_event_id": event["raw_event_id"],
            "strategy_id": event["strategy_id"],
            "event_evidence": event.get("event_evidence"),
            "event_type": self.parse_event_type(event.get("event_type")),
            "event_data": event.get("event_data"),
            "event_time": datetime.datetime.fromtimestamp(event["event_time"] / 1000),
            "event_end_time": datetime.datetime.fromtimestamp(event["event_time"] / 1000),
            "event_source": event.get("event_source"),
            "operator": self.parse_operator(event.get("operator")),
        }
        if manual:
            self._apply_basic_field_mapping(create_params=create_params, event=event)
        create_params["title"] = self.render_risk_title(create_params)
        return create_params

    def _apply_basic_field_mapping(self, create_params: dict, event: dict) -> None:
        """
        根据策略基础字段配置，将事件数据中的字段映射到风险创建参数中
        """

        strategy = (
            Strategy.objects.filter(strategy_id=create_params["strategy_id"]).only("event_basic_field_configs").first()
        )
        if not strategy:
            return

        basic_configs = strategy.event_basic_field_configs or []
        if not basic_configs:
            return

        event_data = event.get("event_data")
        if not isinstance(event_data, dict):
            return

        for field in basic_configs:
            field_name = field.get("field_name")
            map_config = field.get("map_config") or {}
            if not field_name or not map_config:
                continue

            target_value = map_config.get("target_value")
            source_field = map_config.get("source_field")
            if target_value:
                mapped_value = target_value
            elif source_field:
                mapped_value = event_data.get(source_field)
            else:
                continue

            if mapped_value is None:
                continue

            if field_name == EventMappingFields.EVENT_TYPE.field_name:
                create_params[field_name] = self.parse_event_type(
                    mapped_value
                    if isinstance(mapped_value, str)
                    else ",".join(map(str, mapped_value))
                    if isinstance(mapped_value, (list, tuple, set))
                    else str(mapped_value)
                )
                continue

            if field_name == EventMappingFields.OPERATOR.field_name:
                operators = (
                    mapped_value
                    if isinstance(mapped_value, str)
                    else ",".join(map(str, mapped_value))
                    if isinstance(mapped_value, (list, tuple, set))
                    else str(mapped_value)
                )
                create_params[field_name] = self.parse_operator(operators)
                continue
            if field_name == EventMappingFields.RAW_EVENT_ID.field_name and not mapped_value:
                raise ValidationError(
                    message=gettext("raw_event_id（映射自{source_field}）不能为空。").format(source_field=source_field)
                )
            create_params[field_name] = mapped_value

    def create_risk(
        self, event: dict, eligible_strategy_ids: Set[str], manual: bool = False
    ) -> Tuple[bool, Optional[Risk]]:
        """
        创建或更新风险
        """

        # 校验数据
        serializer = CreateRiskSerializer(data=event)
        if not serializer.is_valid():
            logger.error("[CreateRiskFailed] Event Invalid: %s", json.dumps(event))
            return False, None
        event = serializer.validated_data

        # 若关联策略已停用，则不生成风险
        event_strategy_id = event["strategy_id"]
        if event_strategy_id not in eligible_strategy_ids:
            logger.info(
                "[SkipCreateRisk] Strategy not found. strategy_id=%s, raw_event_id=%s",
                event["strategy_id"],
                event.get("raw_event_id"),
            )
            return False, None

        # 检查是否有已存在的
        # 策略ID相同，原始事件ID相同，不为关单状态或事件时间小于最后发现时间
        # 若未关单，则不创建新风险
        # 若事件时间小于最后发现时间，则应当收敛风险
        risk = (
            Risk.objects.filter(
                Q(
                    Q(strategy_id=event["strategy_id"], raw_event_id=event["raw_event_id"])
                    & Q(
                        ~Q(status=RiskStatus.CLOSED)
                        | Q(
                            event_end_time__gte=datetime.datetime.fromtimestamp(
                                event["event_time"] / 1000, tz=timezone.get_default_timezone()
                            )
                        )
                    )
                )
            )
            .order_by("-event_time")
            .first()
        )

        # 存在则更新结束时间, 风险事件描述
        if risk:
            last_end_time = event["event_time"] / 1000
            logger.info("[UpdateRisk] Risk exists. risk_id=%s; last_end_time=%s", risk.risk_id, last_end_time)
            # 只在事件的时间更新的时候存储
            if risk.event_end_time.timestamp() < last_end_time:
                risk.event_end_time = datetime.datetime.fromtimestamp(last_end_time)
                risk.save(update_fields=["event_end_time"])
            if event.get("event_content") and risk.event_content != event["event_content"]:
                risk.event_content = event["event_content"]
                risk.save(update_fields=["event_content"])
            return False, risk

        # 不存在则创建
        create_params = self.gen_risk_create_params(event, manual=manual)
        if manual:
            create_params["manual_synced"] = False
        risk: Risk = Risk.objects.create(**create_params)
        logger.info("[CreateRisk] Risk created. risk_id=%s", risk.risk_id)
        return True, risk

    def parse_operator(self, operator: str) -> List[str]:
        operator = operator or ""
        return [j.strip() for i in operator.split(",") for j in i.split(";") if j]

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

        # 发送通知
        self.send_notice(risk=risk, notice_groups=notice_groups, is_todo=False)

        # 更新风险的通知人员名单
        risk.notice_users = RiskNoticeParser(risk=risk).parse_groups(notice_groups)
        risk.save(update_fields=["notice_users"])

    @classmethod
    def send_notice(cls, risk: Risk, notice_groups: Union[QuerySet, List[NoticeGroup]], is_todo: bool) -> None:
        """
        发送通知
        """

        # 发送通知
        for notice_group in notice_groups:
            resource.notice.send_notice(
                relate_type=RelateType.RISK,
                relate_id=risk.pk,
                agg_key=f"notice_group:{notice_group.group_id}::strategy:{risk.strategy_id}::is_todo:{is_todo}",
                msg_type=[c.get("msg_type") for c in notice_group.notice_config if "msg_type" in c],
                receivers=RiskNoticeParser(risk=risk).parse_group(notice_group),
            )

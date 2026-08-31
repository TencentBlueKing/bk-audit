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
import uuid
from typing import List, Optional, Set, Tuple, Union

from bk_resource import resource
from blueapps.utils.logger import logger
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils import timezone
from django.utils.translation import gettext
from rest_framework.settings import api_settings

from apps.meta.models import GlobalMetaConfig
from apps.meta.utils.format import preprocess_data
from apps.notice.constants import RelateType
from apps.notice.handlers import ErrorMsgHandler
from apps.notice.models import NoticeGroup
from core.render import Jinja2Renderer, VariableUndefined
from services.web.risk.constants import (
    EVENT_DATA_SORT_FIELD,
    EVENT_TYPE_SPLIT_REGEX,
    RISK_EVENT_LATEST_TIME_KEY,
    RISK_RENDER_LOCK_KEY,
    RISK_SYNC_BATCH_SIZE,
    RISK_SYNC_START_TIME_KEY,
    RiskDisplayStatus,
    RiskStatus,
)
from services.web.risk.handlers import EventHandler
from services.web.risk.models import Risk
from services.web.risk.parser import RiskNoticeParser
from services.web.risk.serializers import CreateRiskSerializer
from services.web.scene.constants import BindingType, ResourceVisibilityType
from services.web.scene.filters import BindingMetadataHelper
from services.web.scene.models import ResourceBinding, ResourceBindingScene
from services.web.strategy_v2.constants import DispatchMode, StrategyStatusChoices
from services.web.strategy_v2.models import Strategy, StrategyRule


class RiskHandler:
    """
    Deal with Risk
    """

    @classmethod
    def fetch_eligible_strategy_ids(cls, extra_filter: Optional[Q] = None) -> Set[str]:
        """
        获取可用策略ID集合（排除停用与草稿：草稿未部署不产生事件）
        """
        queryset = Strategy.objects.exclude(
            status__in=[StrategyStatusChoices.DISABLED.value, StrategyStatusChoices.DRAFT.value]
        )
        if extra_filter:
            queryset = queryset.filter(extra_filter)
        return set(queryset.values_list("strategy_id", flat=True))

    def generate_risk(self, event: dict, eligible_strategy_ids: Set[str], manual: bool = False):
        """
        生成风险
        :param event: 事件
        :param eligible_strategy_ids: 可用策略ID集合
        :param manual: 是否手动创建
        """
        try:
            is_create, risk = self.create_risk(event, eligible_strategy_ids, manual=manual)
            if risk:
                # 触发渲染任务
                self.trigger_render_task(risk)
            if is_create:
                self.send_risk_notice(risk)

                from services.web.risk.tasks import process_risk_ticket

                process_risk_ticket(risk_id=risk.risk_id, manual=manual)
            return risk.risk_id if risk else None
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
            if manual:
                raise err

    def generate_risk_from_event(
        self, start_time: datetime.datetime, end_time: datetime.datetime, extra_filter: Optional[Q] = None
    ) -> None:
        """
        从事件生成风险
        """
        eligible_strategy_ids = self.fetch_eligible_strategy_ids(extra_filter=extra_filter)
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
        生成风险标题: 获取发现规则中的risk_title
        自动处理变量中的 list 类型，渲染为逗号拼接的字符串
        """
        create_params = create_params.copy()
        title_template = create_params.pop("_title_template", None)
        if not title_template:
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
                title_template,
                processed_params,  # 使用预处理后的参数
            )
            return risk_title
        except Exception as err:  # NOCC:broad-except(需要处理所有错误)
            logger.exception(
                "[RenderRiskTitleFailed] risk_title: %s; risk_content: %s; err: %s",
                title_template,
                create_params,
                err,
            )
            return title_template

    def gen_risk_create_params(self, event: dict) -> dict:
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
        strategy_rule_id = event.get("strategy_rule_id")
        rule: Optional[StrategyRule] = None
        if strategy_rule_id:
            # _base_manager避免规则已经被软删除
            rule = StrategyRule._base_manager.filter(rule_id=strategy_rule_id).first()
            if rule is not None and rule.strategy_id != event["strategy_id"]:
                # 事件的规则归属与策略不一致
                logger.warning(
                    "[CreateRisk] rule %s not belong to strategy %s, fallback to strategy meta",
                    strategy_rule_id,
                    event["strategy_id"],
                )
                rule = None
        # 存量事件strategy_rule_id为空，需要从本地DB去查rule
        if rule is None:
            rule_order = (
                Strategy.objects.filter(strategy_id=event["strategy_id"]).values_list("rule_order", flat=True).first()
            )
            if rule_order:
                rule = StrategyRule._base_manager.filter(rule_id=rule_order[0]).first()
        # 规则级元信息（优先级：规则 > 策略；策略级回退覆盖模型策略与窗口期事件）
        strategy = Strategy.objects.filter(strategy_id=event["strategy_id"]).first()
        create_params["strategy_rule_id"] = rule.rule_id if rule else None
        create_params["risk_level"] = (rule.risk_level if rule else None) or (strategy.risk_level if strategy else None)
        create_params["risk_hazard"] = (rule.risk_hazard if rule else None) or (
            strategy.risk_hazard if strategy else None
        )
        create_params["risk_guidance"] = (rule.risk_guidance if rule else None) or (
            strategy.risk_guidance if strategy else None
        )
        create_params["_title_template"] = (rule.risk_title if rule else None) or (
            strategy.risk_title if strategy else None
        )
        create_params["title"] = self.render_risk_title(create_params)
        create_params.pop("_title_template", None)
        return create_params

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

        # 构建建单参数（含发现规则归因），查重键与建单参数共用同一 strategy_rule_id，
        # 避免旧 SQL 未重建窗口期事件因规则 ID 为空导致去重错位、重复建单
        create_params = self.gen_risk_create_params(event)

        # 检查是否有已存在的
        # 策略ID相同，原始事件ID相同，命中发现规则相同，不为关单状态或事件时间小于最后发现时间
        # 若未关单，则不创建新风险
        # 若事件时间小于最后发现时间，则应当收敛风险
        risk = (
            Risk.objects.filter(
                Q(
                    Q(
                        strategy_id=event["strategy_id"],
                        raw_event_id=event["raw_event_id"],
                        strategy_rule_id=create_params["strategy_rule_id"],
                    )
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
                risk.event_data = event.get("event_data")
                risk.save(update_fields=["event_end_time", "event_data"])
            if event.get("event_content") and risk.event_content != event["event_content"]:
                risk.event_content = event["event_content"]
                risk.save(update_fields=["event_content"])
            if event.get("event_type") and risk.event_type != event["event_type"]:
                risk.event_type = self.parse_event_type(event.get("event_type"))
                risk.save(update_fields=["event_type"])
            if event.get("operator") and risk.operator != event["operator"]:
                risk.operator = self.parse_operator(event.get("operator"))
                risk.save(update_fields=["operator"])
            return False, risk

        # 不存在则创建
        if manual:
            create_params["manual_synced"] = False
            create_params["display_status"] = RiskDisplayStatus.STAND_BY
        # 获取分派条件命中结果
        dispatch_result = self._match_dispatch(event, create_params)
        # 建单 + 分派信息固化 + 场景绑定需保持原子：中途失败整体回滚
        with transaction.atomic():
            risk: Risk = Risk.objects.create(**create_params)
            if dispatch_result is not None:
                # 将分派结果（dispatch_rule/confirmer）固化到风险单，后续分派规则编辑不影响已产生单据
                self._apply_dispatch(risk, dispatch_result)
                if dispatch_result.dispatch_mode == DispatchMode.DIRECT:
                    # direct：建单时即建 RISK 场景绑定（after_confirm 延迟到确认时建，仅绑定时机不同）
                    BindingMetadataHelper.create_risk_scene_binding(risk.risk_id, dispatch_result.target_scene_id)
            else:
                # 场景策略
                scene_id = self._get_strategy_scene_id(event["strategy_id"])
                BindingMetadataHelper.create_risk_scene_binding(risk.risk_id, scene_id)
        logger.info("[CreateRisk] Risk created. risk_id=%s", risk.risk_id)

        if dispatch_result is not None and dispatch_result.dispatch_mode == DispatchMode.AFTER_CONFIRM:
            # 待确认阶段不渲染报告、不通知关注人/处理人、不自动流转（确认后触发），
            # 仅通知确认人；事务提交后发送，保证接收人收到通知时数据已落库
            self._send_confirm_notice(risk, risk.confirmer)
            return False, risk
        # 直接分派（direct）与场景策略一致：进入 NewRisk 流转
        return True, risk

    def _match_dispatch(self, event: dict, create_params: dict):
        """
        全局策略分派匹配：按 dispatch_rule_order 首匹配分派规则

        :return:
            - None: 场景策略
            - DispatchResult: 分派结果，全局策略：
                - matched (bool): 是否命中
                - rule (DispatchRule): 命中的分派规则
                - dispatch_mode (str): 分派方式（direct/after_confirm）
                - target_scene_id (int): 目标场景 ID
                - processor (List[int]): 处理人通知组 ID 列表
                - follower (List[int]): 关注人通知组 ID 列表
                - confirmer (List[int]): 确认人通知组 ID 列表
        """
        from services.web.strategy_v2.handlers.dispatch import match_dispatch_rule

        # 策略绑定类型：platform_binding 才走分派
        binding_type = (
            ResourceBinding.objects.filter(
                resource_type=ResourceVisibilityType.STRATEGY,
                resource_id=str(event["strategy_id"]),
            )
            .values_list("binding_type", flat=True)
            .first()
        )
        if binding_type != BindingType.PLATFORM_BINDING:
            return None
        strategy = Strategy.objects.filter(strategy_id=event["strategy_id"]).first()
        if strategy is None:
            return None
        # ctx：事件字段 + 已实例化的规则元信息
        ctx = {
            **event,
            "risk_level": create_params.get("risk_level"),
            "risk_hazard": create_params.get("risk_hazard"),
            "risk_guidance": create_params.get("risk_guidance"),
        }
        dispatch_result = match_dispatch_rule(ctx, strategy=strategy)
        if not dispatch_result.matched:
            logger.error(
                "[DispatchRisk] no dispatch rule matched. strategy_id=%s, raw_event_id=%s",
                event["strategy_id"],
                event.get("raw_event_id"),
            )
            raise ValueError(gettext("全局策略[%s]分派规则未命中且无默认兜底规则，请检查策略分派规则配置") % event["strategy_id"])
        return dispatch_result

    def _apply_dispatch(self, risk: Risk, dispatch_result) -> None:
        """
        将分派结果固化到风险单（dispatch_rule 快照）
        - after_confirm：额外固化确认人并进入待确认状态
        - direct：无需确认人，直接分派，由调用方进入 NewRisk 流转
        """
        risk.dispatch_rule_id = dispatch_result.rule.rule_id
        update_fields = ["dispatch_rule"]
        if dispatch_result.dispatch_mode == DispatchMode.AFTER_CONFIRM:
            confirmers = list(NoticeGroup.objects.filter(group_id__in=dispatch_result.confirmer))
            risk.confirmer = RiskNoticeParser(risk=risk).parse_groups(confirmers)
            # display_status 同步，否则列表页展示为空；周期任务 process_one_risk 的 match 无该分支会跳过，
            risk.status = RiskStatus.PENDING_CONFIRM
            risk.display_status = RiskDisplayStatus.PENDING_CONFIRM
            update_fields += ["confirmer", "status", "display_status"]
        risk.save(update_fields=update_fields)

    def _get_strategy_scene_id(self, strategy_id) -> Optional[int]:
        """策略绑定的场景 ID（场景策略）"""
        return (
            ResourceBindingScene.objects.filter(
                scene__is_deleted=False,
                binding__resource_type=ResourceVisibilityType.STRATEGY,
                binding__resource_id=str(strategy_id),
            )
            .values_list("scene_id", flat=True)
            .first()
        )

    def _send_confirm_notice(self, risk: Risk, confirmer: List[str]) -> None:
        """
        PENDING_CONFIRM 阶段通知确认人，确认人接收后经确认接口流转。
        """
        if not confirmer:
            return
        try:
            resource.notice.send_notice(
                relate_type=RelateType.RISK,
                relate_id=risk.pk,
                agg_key=f"risk_confirm:{risk.risk_id}",
                msg_type=["mail"],
                receivers=confirmer,
                title=gettext("风险单待确认"),
                content=gettext("风险单[%s]等待您的确认") % risk.risk_id,
            )
        except Exception as err:  # NOCC:broad-except(通知失败不阻断主流程)
            logger.exception("[SendConfirmNoticeFailed] risk_id=%s, err=%s", risk.risk_id, err)

    def trigger_render_task(self, risk: Risk):
        """
        触发渲染任务
        """
        from services.web.risk.tasks import render_risk_report

        # 待确认（after_confirm 分派）不渲染报告：确认流转后再触发
        if risk.status == RiskStatus.PENDING_CONFIRM:
            logger.info("[TriggerRender] Skip render for pending confirm risk. risk_id=%s", risk.risk_id)
            return

        # 检查触发条件：策略开启报告 + 风险开启自动生成
        if not risk.can_auto_generate_report():
            logger.info("[TriggerRender] Render disabled. risk_id=%s", risk.risk_id)
            return

        risk_id = risk.risk_id
        current_time = datetime.datetime.now().timestamp()

        # 1. 更新最新事件时间
        latest_time_key = RISK_EVENT_LATEST_TIME_KEY.format(risk_id=risk_id)
        cache.set(latest_time_key, current_time, timeout=settings.RENDER_TASK_TIMEOUT)

        # 2. 尝试获取锁 (Value = UUID)
        lock_key = RISK_RENDER_LOCK_KEY.format(risk_id=risk_id)
        task_id = str(uuid.uuid4())

        # NX=True (set if not exists), EX=timeout
        # 如果获取成功，说明当前没有任务在运行，立即触发
        if cache.set(lock_key, task_id, nx=True, timeout=settings.RENDER_TASK_TIMEOUT):
            logger.info(
                "[TriggerRender] Acquired lock, triggering task with %ds delay. risk_id=%s, task_id=%s",
                settings.RENDER_TASK_DELAY,
                risk_id,
                task_id,
            )
            render_risk_report.apply_async(
                kwargs={"risk_id": risk_id, "task_id": task_id},
                countdown=settings.RENDER_TASK_DELAY,
            )
        else:
            # 如果获取失败，说明已有任务在运行
            # 只需更新 latest_event_time (步骤1已做)，运行中的任务会在结束前检查该时间并决定是否递归触发
            logger.info("[TriggerRender] Lock exists, updated latest time. risk_id=%s", risk_id)

    def parse_operator(self, operator: str) -> List[str]:
        operator = operator or ""
        return [j.strip() for i in operator.split(",") for j in i.split(";") if j]

    def parse_event_type(self, event_type: str) -> List[str]:
        event_types = [t for t in re.split(EVENT_TYPE_SPLIT_REGEX, (event_type or "")) if t]
        return event_types

    def send_risk_notice(self, risk: Risk) -> None:
        """
        发送通知给关注人

        关注人来源：
        1. 全局策略风险：分派规则的follower DispatchRule.follower
        2. 场景策略风险：发现规则的follower  StrategyRule.follower
        """

        # 获取策略
        strategy = Strategy.objects.filter(strategy_id=risk.strategy_id).first()
        if not strategy:
            return

        # 1. 全局策略风险：获取分派规则的关注组
        if getattr(risk, "dispatch_rule_id", None):
            from services.web.strategy_v2.models import DispatchRule

            dispatch_rule = DispatchRule._base_manager.filter(rule_id=risk.dispatch_rule_id).first()
            follower_group_ids = (dispatch_rule.follower if dispatch_rule else None) or []
        else:
            # 2. 场景策略风险：获取发现规则的关注组
            follower_group_ids = strategy.notice_groups or []
            if getattr(risk, "strategy_rule_id", None):
                from services.web.strategy_v2.models import StrategyRule

                rule = StrategyRule._base_manager.filter(rule_id=risk.strategy_rule_id).first()
                if rule and rule.follower:
                    follower_group_ids = rule.follower

        # 获取通知组
        notice_groups = NoticeGroup.objects.filter(group_id__in=follower_group_ids)
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

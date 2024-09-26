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
import os

from billiard.exceptions import SoftTimeLimitExceeded
from bk_resource import api
from bk_resource.settings import bk_resource_settings
from blueapps.contrib.celery_tools.periodic import periodic_task
from blueapps.core.celery import celery_app
from blueapps.utils.logger import logger_celery
from celery.schedules import crontab
from django.conf import settings
from django.core.cache import cache as _cache
from django.db import transaction
from django.utils.translation import gettext
from django_redis.client import DefaultClient

from apps.itsm.constants import TicketStatus
from apps.notice.handlers import ErrorMsgHandler
from apps.sops.constants import SOPSTaskStatus
from core.lock import lock
from services.web.risk.constants import (
    RISK_ESQUERY_DELAY_TIME,
    RISK_ESQUERY_SLICE_DURATION,
    RISK_EVENTS_SYNC_TIME,
    RiskStatus,
    TicketNodeStatus,
)
from services.web.risk.handlers import BKMAlertSyncHandler, EventHandler
from services.web.risk.handlers.risk import RiskHandler
from services.web.risk.handlers.ticket import (
    AutoProcess,
    ForApprove,
    NewRisk,
    TransOperator,
)
from services.web.risk.models import Risk, TicketNode

cache: DefaultClient = _cache


@periodic_task(run_every=crontab(minute="*/10"), queue="risk", soft_time_limit=settings.DEFAULT_CACHE_LOCK_TIMEOUT)
@lock(lock_name="celery:sync_bkm_alert")
def sync_bkm_alert():
    """同步监控告警为审计事件"""

    try:
        BKMAlertSyncHandler().sync()
    except Exception as err:  # NOCC:broad-except(需要处理所有错误)
        logger_celery.exception("[SyncBKMAlertFailed] %s", err)
        ErrorMsgHandler(gettext("Sync BKM Alert Failed"), str(err)).send()


@celery_app.task(queue="risk", soft_time_limit=settings.DEFAULT_CACHE_LOCK_TIMEOUT)
@lock(lock_name="celery:add_event")
def add_event(data: list):
    """创建审计事件"""

    EventHandler().add_event(data)


@periodic_task(
    run_every=crontab(minute="0", hour=os.getenv("BKAPP_GENERATE_RISK_FROM_EVENT_SCHEDULE", "*")),
    queue="risk",
    soft_time_limit=int(os.getenv("BKAPP_GENERATE_RISK_FROM_EVENT_TIMEOUT", settings.DEFAULT_CACHE_LOCK_TIMEOUT)),
)
@lock(
    lock_name="celery:generate_risk_from_event",
    timeout=int(os.getenv("BKAPP_GENERATE_RISK_FROM_EVENT_TIMEOUT", settings.DEFAULT_CACHE_LOCK_TIMEOUT)),
)
def generate_risk_from_event():
    """从审计事件创建风险"""

    # 初始化时间
    start_time = datetime.datetime.now() - datetime.timedelta(days=RISK_EVENTS_SYNC_TIME)
    end_time = start_time + datetime.timedelta(seconds=RISK_ESQUERY_SLICE_DURATION)
    task_end_time = datetime.datetime.now() - datetime.timedelta(seconds=RISK_ESQUERY_DELAY_TIME)

    try:
        while end_time <= task_end_time:
            # 生成风险
            RiskHandler().generate_risk_from_event(start_time=start_time, end_time=end_time)
            logger_celery.info("[GenerateRiskFinished] %s ~ %s", start_time, end_time)
            # 滚动时间
            start_time = end_time
            end_time = start_time + datetime.timedelta(seconds=RISK_ESQUERY_SLICE_DURATION)
    except Exception as err:  # NOCC:broad-except(需要处理所有错误)
        # 异常通知
        logger_celery.exception("[GenerateRiskFailed] %s", err)
        ErrorMsgHandler(gettext("Generate Risk Failed"), str(err)).send()


@periodic_task(run_every=crontab(minute="0"), queue="risk", soft_time_limit=settings.DEFAULT_CACHE_LOCK_TIMEOUT)
@lock(
    lock_name="celery:process_risk_ticket",
    load_lock_name=lambda **kwargs: f"celery:process_risk_ticket:{kwargs['risk_id'] if kwargs else None}",
)
def process_risk_ticket(*, risk_id: str = None):
    """自动处理风险单"""

    # 检测是否开启自动流转
    if not settings.ENABLE_PROCESS_RISK_TASK:
        return

    # 获取风险
    risks = Risk.objects.filter(status__in=[RiskStatus.NEW, RiskStatus.FOR_APPROVE, RiskStatus.AUTO_PROCESS])
    if risk_id:
        risks = risks.filter(risk_id=risk_id)

    # 风险白名单
    if settings.ENABLE_PROCESS_RISK_WHITELIST:
        risks = risks.filter(strategy_id__in=settings.PROCESS_RISK_WHITELIST)

    logger_celery.info("[ProcessRiskTicket] Total %s", len(risks))
    # 逐个处理
    for risk in risks:
        if settings.ENABLE_MULTI_PROCESS_RISK:
            process_one_risk.delay(risk_id=risk.risk_id)
            logger_celery.info("[ProcessRiskTicket] Scheduled %s", risk.risk_id)
        else:
            logger_celery.info("[ProcessRiskTicket] Sync-Running %s", risk.risk_id)
            process_one_risk(risk_id=risk.risk_id)


@celery_app.task(queue="risk", soft_time_limit=settings.DEFAULT_CACHE_LOCK_TIMEOUT)
@lock(
    lock_name="celery:process_one_risk",
    load_lock_name=lambda **kwargs: f"celery:process_one_risk:{kwargs['risk_id']}",
)
def process_one_risk(*, risk_id: str):
    """
    处理单个风险
    """

    # 获取风险
    risk = Risk.objects.get(risk_id=risk_id)

    # 重试
    cache_key = f"process_one_risk:fail:{risk.risk_id}"
    # 判断操作
    match risk.status:
        case RiskStatus.NEW:
            process_class = NewRisk
        case RiskStatus.FOR_APPROVE:
            process_class = ForApprove
        case RiskStatus.AUTO_PROCESS:
            process_class = AutoProcess
        case _:
            return
    # 处理
    try:
        logger_celery.info("[ProcessRiskTicket] %s Start %s", process_class.__name__, risk.risk_id)
        # 处理
        process_class(risk_id=risk.risk_id, operator=bk_resource_settings.PLATFORM_AUTH_ACCESS_USERNAME).run()
        # 成功后移除缓存
        cache.delete(key=cache_key)
    except Exception as err:  # NOCC:broad-except(需要处理所有错误)
        # 获取失败次数
        retry_times = cache.get(key=cache_key, default=1)
        # 异常通知
        logger_celery.exception("[ProcessRiskTicket] %s Error %s %s", process_class.__name__, risk.risk_id, err)
        title = gettext("Process Risk Ticket Failed")
        content = gettext("ProcessClass: %s\nRiskID: %s(%d/%d)\nError: %s") % (
            process_class.__name__,
            risk.risk_id,
            retry_times,
            settings.PROCESS_RISK_MAX_RETRY,
            err,
        )
        ErrorMsgHandler(title, content).send()
        # 不捕获超时的异常
        if isinstance(err, SoftTimeLimitExceeded):
            raise err
        # 失败达到最大次数转人工
        if retry_times >= settings.PROCESS_RISK_MAX_RETRY:
            cache.delete(key=cache_key)
            TransOperator(risk_id=risk.risk_id, operator=bk_resource_settings.PLATFORM_AUTH_ACCESS_USERNAME).run(
                new_operators=TransOperator.load_security_person(), description=gettext("风险自动流转失败，转为安全接口人处理")
            )
        else:
            cache.set(
                key=cache_key,
                value=retry_times + 1,
                timeout=(settings.PROCESS_RISK_MAX_RETRY + 1) * settings.DEFAULT_CACHE_LOCK_TIMEOUT,
            )
    finally:
        logger_celery.info("[ProcessRiskTicket] %s End %s", process_class.__name__, risk.risk_id)


@periodic_task(run_every=crontab(minute="0"), queue="risk", soft_time_limit=settings.DEFAULT_CACHE_LOCK_TIMEOUT)
@lock(lock_name="celery:sync_auto_result")
def sync_auto_result(node_id: str = None):
    """同步处理节点状态"""

    # 筛选所有需要更新的节点
    if node_id:
        nodes = TicketNode.objects.filter(id=node_id)
    else:
        nodes = TicketNode.objects.filter(status=TicketNodeStatus.RUNNING)

    # 逐个更新
    for node in nodes:
        with transaction.atomic():
            node = TicketNode.objects.select_for_update().get(id=node.id)
            # 审批节点
            if node.action == ForApprove.__name__:
                sn = node.process_result.get("ticket", {}).get("sn")
                if sn:
                    status = api.bk_itsm.ticket_approve_result(sn=[sn])[0]
                    node.process_result["status"] = status
                    node.status = (
                        TicketNodeStatus.FINISHED
                        if node.process_result["status"]["current_status"]
                        in [TicketStatus.TERMINATED, TicketStatus.FINISHED, TicketStatus.FAILED, TicketStatus.REVOKED]
                        else TicketNodeStatus.RUNNING
                    )
                else:
                    node.status = TicketNodeStatus.FINISHED
            # 自动处理套餐节点
            elif node.action == AutoProcess.__name__:
                task_id = node.process_result.get("task", {}).get("task_id", "")
                if task_id:
                    status = api.bk_sops.get_task_status(task_id=task_id, bk_biz_id=settings.DEFAULT_BK_BIZ_ID)
                    node.process_result["status"] = status
                    node.status = (
                        TicketNodeStatus.FINISHED
                        if node.process_result["status"]["state"]
                        in [
                            SOPSTaskStatus.EXPIRED,
                            SOPSTaskStatus.FINISHED,
                            SOPSTaskStatus.FAILED,
                            SOPSTaskStatus.REVOKED,
                        ]
                        else TicketNodeStatus.RUNNING
                    )
                else:
                    node.status = TicketNodeStatus.FINISHED
            # 其他节点只需要判断不为最后一个，则关闭
            # 或 该风险单已关闭，则关闭
            else:
                last_node = TicketNode.objects.filter(risk_id=node.risk_id).order_by("-timestamp").first()
                risk = Risk.objects.filter(risk_id=node.risk_id).first()
                if (last_node and last_node.timestamp > node.timestamp) or (risk and risk.status == RiskStatus.CLOSED):
                    node.status = TicketNodeStatus.FINISHED
            node.save(update_fields=["process_result", "status"])

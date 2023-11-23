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

from bk_resource import api
from bk_resource.settings import bk_resource_settings
from blueapps.utils.logger import logger_celery
from celery.schedules import crontab
from celery.task import periodic_task, task
from django.conf import settings
from django.core.cache import cache as _cache
from django.db import transaction
from django.utils.translation import gettext
from django_redis.client import DefaultClient

from apps.itsm.constants import TicketStatus
from apps.notice.handlers import ErrorMsgHandler
from apps.sops.constants import SOPSTaskStatus
from core.utils.tools import single_task_decorator
from services.web.risk.constants import RiskStatus, TicketNodeStatus
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


@periodic_task(run_every=crontab(minute="*/10"), queue="risk")
@single_task_decorator
def sync_bkm_alert():
    """同步监控告警为审计事件"""

    BKMAlertSyncHandler().sync()


@task(queue="risk")
def add_event(data: list):
    """创建审计事件"""

    EventHandler().add_event(data)


@periodic_task(run_every=crontab(minute="0"), queue="risk")
@single_task_decorator
def generate_risk_from_event():
    """从审计事件创建风险"""

    RiskHandler().generate_risk_from_event()


@periodic_task(run_every=crontab(minute="*/5"), queue="risk")
@single_task_decorator
def process_risk_ticket(risk_id: str = None):
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

    # 流转风险
    for risk in risks:
        # 重试
        cache_key = f"process_risk_ticket-{risk.risk_id}"
        # 判断操作
        match risk.status:
            case RiskStatus.NEW:
                process_class = NewRisk
            case RiskStatus.FOR_APPROVE:
                process_class = ForApprove
            case RiskStatus.AUTO_PROCESS:
                process_class = AutoProcess
            case _:
                continue
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
            # 失败达到最大次数转人工
            if retry_times >= settings.PROCESS_RISK_MAX_RETRY:
                cache.delete(key=cache_key)
                TransOperator(risk_id=risk.risk_id, operator=bk_resource_settings.PLATFORM_AUTH_ACCESS_USERNAME).run(
                    new_operators=TransOperator.load_security_person(), description=gettext("风险自动流转失败，转为安全接口人处理")
                )
            else:
                cache.set(key=cache_key, value=retry_times + 1, timeout=settings.PROCESS_RISK_RETRY_KEY_TIMEOUT)
        finally:
            logger_celery.info("[ProcessRiskTicket] %s End %s", process_class.__name__, risk.risk_id)


@periodic_task(run_every=crontab(minute="0"), queue="risk")
@single_task_decorator
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

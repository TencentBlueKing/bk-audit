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
import os
from typing import Any

from bk_resource import api
from bk_resource.settings import bk_resource_settings
from blueapps.contrib.celery_tools.periodic import periodic_task
from blueapps.core.celery import celery_app
from blueapps.utils.logger import logger_celery
from celery.exceptions import MaxRetriesExceededError
from celery.schedules import crontab
from django.conf import settings
from django.core.cache import cache as _cache
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext
from django_redis.client import DefaultClient
from rest_framework.settings import api_settings

from apps.exceptions import MetaConfigNotExistException
from apps.itsm.constants import TicketStatus
from apps.meta.constants import ConfigLevelChoices
from apps.meta.models import GlobalMetaConfig
from apps.notice.handlers import ErrorMsgHandler
from apps.sops.constants import SOPSTaskStatus
from core.lock import lock
from core.utils.data import data_chunks
from services.web.databus.constants import ASSET_RISK_BKBASE_RT_ID_KEY
from services.web.risk.constants import (
    BULK_ADD_EVENT_SIZE,
    RISK_ESQUERY_DELAY_TIME,
    RISK_ESQUERY_SLICE_DURATION,
    RISK_EVENTS_SYNC_TIME,
    RiskStatus,
    TicketNodeStatus,
)
from services.web.risk.handlers import (
    BKMAlertSyncHandler,
    EventHandler,
    RiskReportHandler,
)
from services.web.risk.handlers.risk import RiskHandler
from services.web.risk.handlers.ticket import (
    AutoProcess,
    ForApprove,
    NewRisk,
    TransOperator,
)
from services.web.risk.models import ManualEvent, Risk, TicketNode
from services.web.risk.report import AIProvider
from services.web.risk.report.markdown import render_ai_markdown
from services.web.risk.serializers import CreateEventSerializer
from services.web.strategy_v2.constants import StrategyType

cache: DefaultClient = _cache


@celery_app.task(
    bind=True,
    queue="risk_report",
    time_limit=settings.RENDER_TASK_TIMEOUT + 60,  # 宽限 60s
    max_retries=settings.RENDER_MAX_RETRY,
    acks_late=True,  # 任务级别的延迟确认
    rate_limit=settings.RENDER_TASK_RATE_LIMIT,  # 限流：防止下游服务被打爆
)
def render_risk_report(self, risk_id: str, task_id: str):
    """
    渲染风险报告任务（尾部触发机制）

    工作流：
    1. 获取 Redis 锁
    2. 执行渲染
    3. 检查任务期间是否有新事件
    4. 有新事件 -> 递归触发新任务
    5. 无新事件 -> 释放锁
    """
    handler = RiskReportHandler(risk_id=risk_id, task_id=task_id)
    try:
        handler.run()
    except Exception as exc:
        logger_celery.info("[RenderRiskReportFailed] risk_id=%s, task_id=%s, error=%s", risk_id, task_id, exc)
        # 注意：handler.run() 的 finally 块已经释放了锁，这里不需要再释放
        try:
            # 失败重试（不传 exc 参数，确保达到上限时 raise MaxRetriesExceededError）
            self.retry(countdown=settings.RENDER_RETRY_DELAY)
        except MaxRetriesExceededError:
            # 达到最大重试次数
            handler.handle_max_retries_exceeded(exc)
            raise


@periodic_task(run_every=crontab(minute="*/10"), queue="risk", time_limit=settings.DEFAULT_CACHE_LOCK_TIMEOUT)
@lock(lock_name="celery:sync_bkm_alert")
def sync_bkm_alert():
    """同步监控告警为审计事件"""

    try:
        BKMAlertSyncHandler().sync()
    except Exception as err:  # NOCC:broad-except(需要处理所有错误)
        logger_celery.exception("[SyncBKMAlertFailed] %s", err)
        ErrorMsgHandler(gettext("Sync BKM Alert Failed"), str(err)).send()


@celery_app.task(queue="risk", time_limit=settings.DEFAULT_CACHE_LOCK_TIMEOUT)
@lock(lock_name="celery:add_event")
def add_event(data: list):
    """创建审计事件"""

    EventHandler().add_event(data)


def manual_add_event(data: list):
    """将事件写入 ManualEvent 表"""

    if not data:
        logger_celery.warning("[ManualAddEvent] Empty payload")
        return

    manual_events = []
    for event in data:
        serializer = CreateEventSerializer(data=event)
        if not serializer.is_valid():
            logger_celery.warning("[ManualAddEvent] invalid event: %s", serializer.errors)
            continue
        payload = serializer.validated_data
        payload["event_data"] = json.loads(payload["event_data"])
        event_time = datetime.datetime.fromtimestamp(payload["event_time"] / 1000, tz=timezone.get_default_timezone())
        manual_events.append(
            ManualEvent(
                event_content=payload.get("event_content"),
                raw_event_id=payload["raw_event_id"],
                strategy_id=payload["strategy_id"],
                event_evidence=payload.get("event_evidence"),
                event_type=payload.get("event_type"),
                event_data=payload.get("event_data"),
                event_time=event_time,
                event_source=payload.get("event_source"),
                operator=payload.get("operator"),
            )
        )
    if not manual_events:
        logger_celery.info("[ManualAddEvent] No valid events to persist")
        return
    ManualEvent.objects.bulk_create(manual_events, batch_size=BULK_ADD_EVENT_SIZE)
    logger_celery.info("[ManualAddEvent] Saved %s manual events", len(manual_events))


def _build_manual_event_time_range(event_time: datetime.datetime, window: datetime.timedelta) -> tuple[str, str]:
    aware_time = event_time
    if timezone.is_naive(aware_time):
        aware_time = timezone.make_aware(aware_time, timezone.get_default_timezone())
    local_time = timezone.localtime(aware_time)
    start_time = (local_time - window).strftime(api_settings.DATETIME_FORMAT)
    end_time = (local_time + window).strftime(api_settings.DATETIME_FORMAT)
    return start_time, end_time


def _sync_manual_event_status(batch_size: int = 100, window: datetime.timedelta = datetime.timedelta(hours=1)) -> None:
    events = list(ManualEvent.objects.filter(manual_synced=False).order_by("manual_event_id")[:batch_size])
    if not events:
        return

    start_times: list[str] = []
    end_times: list[str] = []
    manual_event_ids: list[str] = []
    for event in events:
        start_time, end_time = _build_manual_event_time_range(event.event_time, window)
        start_times.append(start_time)
        end_times.append(end_time)
        manual_event_ids.append(str(event.manual_event_id))

    search_start = min(start_times)
    search_end = max(end_times)
    manual_event_id_param = ",".join(manual_event_ids)
    page_size = max(len(events), 10)

    try:
        resp = (
            EventHandler.search_event(
                namespace=settings.DEFAULT_NAMESPACE,
                start_time=search_start,
                end_time=search_end,
                page=1,
                page_size=page_size,
                manual_event_id=manual_event_id_param,
            )
            or {}
        )
    except Exception as err:  # NOCC:broad-except(需要处理所有错误)
        logger_celery.warning(
            "[SyncManualEventStatus] search failed for manual_event_ids=%s: %s",
            manual_event_id_param,
            err,
        )
        return

    results = resp.get("results") or []
    synced_ids = {
        int(item["manual_event_id"])
        for item in results
        if isinstance(item, dict) and item.get("manual_event_id") is not None
    }

    if synced_ids:
        ManualEvent.objects.filter(manual_event_id__in=synced_ids, manual_synced=False).update(manual_synced=True)
        logger_celery.info("[SyncManualEventStatus] Updated %s manual events", len(synced_ids))


@periodic_task(
    run_every=datetime.timedelta(seconds=10),
    queue="risk",
    time_limit=30,
)
@lock(lock_name="celery:sync_manual_event_status", timeout=30)
def sync_manual_event_status():
    """同步已入 ES 的手工事件状态"""

    _sync_manual_event_status()


def _sync_manual_risk_status(batch_size: int = 500) -> None:
    try:
        table_id = GlobalMetaConfig.get(
            config_key=ASSET_RISK_BKBASE_RT_ID_KEY,
            config_level=ConfigLevelChoices.NAMESPACE.value,
            instance_key=settings.DEFAULT_NAMESPACE,
        )
    except MetaConfigNotExistException as err:  # NOCC:broad-except(配置缺失时只记录)
        logger_celery.warning("[SyncManualRiskStatus] skip because config missing: %s", err)
        return
    table_ref = table_id
    if not table_ref:
        logger_celery.warning("[SyncManualRiskStatus] skip because table id is empty")
        return

    unsynced_ids = list(Risk.objects.filter(manual_synced=False).values_list("risk_id", flat=True))
    if not unsynced_ids:
        return

    for chunk in data_chunks(unsynced_ids, batch_size):
        id_clause = f"""({','.join(f"'{item}'" for item in chunk)})"""
        sql = f"SELECT risk_id FROM {table_ref}.doris WHERE risk_id IN {id_clause}"
        logger_celery.info("[SyncManualRiskStatus] Executing SQL: %s", sql)
        resp = api.bk_base.query_sync(sql=sql) or {}
        found_ids = {row.get("risk_id") for row in resp.get("list") or [] if row.get("risk_id")}
        if found_ids:
            _ = Risk.objects.filter(risk_id__in=found_ids, manual_synced=False).update(manual_synced=True)
            logger_celery.info("[SyncManualRiskStatus] Updated %s risks in chunk", found_ids)


@periodic_task(
    run_every=datetime.timedelta(seconds=10),
    queue="risk",
    time_limit=30,
)
@lock(lock_name="celery:sync_manual_risk_status", timeout=30)
def sync_manual_risk_status():
    """同步已入 BKBase 的手工风险状态"""

    _sync_manual_risk_status()


@periodic_task(
    run_every=crontab(minute="0", hour=os.getenv("BKAPP_GENERATE_RISK_FROM_EVENT_SCHEDULE", "*")),
    queue="risk",
    time_limit=int(os.getenv("BKAPP_GENERATE_RISK_FROM_EVENT_TIMEOUT", settings.DEFAULT_CACHE_LOCK_TIMEOUT)),
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
            RiskHandler().generate_risk_from_event(
                start_time=start_time,
                end_time=end_time,
                extra_filter=Q(strategy_type=StrategyType.MODEL.value),
            )
            logger_celery.info("[GenerateRiskFinished] %s ~ %s", start_time, end_time)
            # 滚动时间
            start_time = end_time
            end_time = start_time + datetime.timedelta(seconds=RISK_ESQUERY_SLICE_DURATION)
    except Exception as err:  # NOCC:broad-except(需要处理所有错误)
        # 异常通知
        logger_celery.exception("[GenerateRiskFailed] %s", err)
        ErrorMsgHandler(gettext("Generate Risk Failed"), str(err)).send()


@periodic_task(
    run_every=crontab(minute=settings.PROCESS_ONE_RISK_PERIODIC_TASK_MINUTE),
    queue="risk",
    time_limit=settings.DEFAULT_CACHE_LOCK_TIMEOUT,
)
@lock(
    lock_name="celery:process_risk_ticket",
    load_lock_name=lambda **kwargs: f"celery:process_risk_ticket:{kwargs['risk_id'] if kwargs else None}",
)
def process_risk_ticket(*, risk_id: str = None, manual: bool = False):
    """自动处理风险单"""

    # 检测是否开启自动流转
    if not settings.ENABLE_PROCESS_RISK_TASK:
        return

    # 获取风险
    risks = Risk.objects.filter(status__in=[RiskStatus.NEW, RiskStatus.FOR_APPROVE, RiskStatus.AUTO_PROCESS]).only(
        "risk_id", "strategy"
    )
    if risk_id:
        risks = risks.filter(risk_id=risk_id)

    # 仅处理正式发单的策略对应的风险
    risks = risks.filter(strategy__is_formal=True)

    # 逐个处理
    for risk in risks:
        if settings.ENABLE_MULTI_PROCESS_RISK and not manual:
            process_one_risk.delay(risk_id=risk.risk_id)
            logger_celery.info("[ProcessRiskTicket] Scheduled %s", risk.risk_id)
        else:
            logger_celery.info("[ProcessRiskTicket] Sync-Running %s", risk.risk_id)
            process_one_risk(risk_id=risk.risk_id)


@celery_app.task(queue="risk", time_limit=settings.DEFAULT_CACHE_LOCK_TIMEOUT)
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
        # 失败达到最大次数转人工
        if retry_times >= settings.PROCESS_RISK_MAX_RETRY:
            cache.delete(key=cache_key)
            TransOperator(risk_id=risk.risk_id, operator=bk_resource_settings.PLATFORM_AUTH_ACCESS_USERNAME).run(
                new_operators=TransOperator.load_security_person(),
                description=gettext("风险自动流转失败，转为安全接口人处理"),
            )
        else:
            cache.set(
                key=cache_key,
                value=retry_times + 1,
                timeout=(settings.PROCESS_RISK_MAX_RETRY + 1) * settings.DEFAULT_CACHE_LOCK_TIMEOUT,
            )
    except BaseException as err:
        logger_celery.exception("[ProcessRiskTicket] %s Error %s %s", process_class.__name__, risk.risk_id, err)
        raise err
    finally:
        logger_celery.info("[ProcessRiskTicket] %s End %s", process_class.__name__, risk.risk_id)


@periodic_task(
    run_every=crontab(minute=settings.SYNC_AUTO_RESULT_PERIODIC_TASK_MINUTE),
    queue="risk",
    time_limit=settings.DEFAULT_CACHE_LOCK_TIMEOUT,
)
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
        try:
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
                            in [
                                TicketStatus.TERMINATED,
                                TicketStatus.FINISHED,
                                TicketStatus.FAILED,
                                TicketStatus.REVOKED,
                            ]
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
                    if (last_node and last_node.timestamp > node.timestamp) or (
                        risk and risk.status == RiskStatus.CLOSED
                    ):
                        node.status = TicketNodeStatus.FINISHED
                node.save(update_fields=["process_result", "status"])
        except Exception as err:  # NOCC:broad-except(需要处理所有错误)
            logger_celery.exception("[SyncAutoResult] Error %s %s", node.id, err)


def _build_risk_query_from_prompt_params(prompt_params: dict) -> Q:
    """
    根据报告的 prompt_params（前端传入的风险过滤条件）构建 Risk ORM 查询条件。

    prompt_params 的键与 ListRiskRequestSerializer 的字段一致，
    此处仅处理常用的过滤字段，不涉及分页、排序等非查询参数。
    """
    q = Q()
    if not prompt_params:
        return q

    # risk_id 精确匹配
    if prompt_params.get("risk_id"):
        risk_ids = [i.strip() for i in str(prompt_params["risk_id"]).split(",") if i.strip()]
        if risk_ids:
            q &= Q(risk_id__in=risk_ids)

    # 时间范围
    if prompt_params.get("start_time"):
        q &= Q(event_time__gte=prompt_params["start_time"])
    if prompt_params.get("end_time"):
        q &= Q(event_time__lt=prompt_params["end_time"])

    # operator 模糊匹配
    if prompt_params.get("operator"):
        q &= Q(operator__contains=prompt_params["operator"])

    # strategy_id
    if prompt_params.get("strategy_id"):
        strategy_ids = [i.strip() for i in str(prompt_params["strategy_id"]).split(",") if i.strip()]
        if strategy_ids:
            q &= Q(strategy_id__in=strategy_ids)

    # status -> display_status
    if prompt_params.get("status"):
        statuses = [i.strip() for i in str(prompt_params["status"]).split(",") if i.strip()]
        if statuses:
            q &= Q(display_status__in=statuses)

    # current_operator 模糊匹配
    if prompt_params.get("current_operator"):
        q &= Q(current_operator__contains=prompt_params["current_operator"])

    # event_type 模糊匹配
    if prompt_params.get("event_type"):
        q &= Q(event_type__contains=prompt_params["event_type"])

    # risk_level
    if prompt_params.get("risk_level"):
        levels = [i.strip() for i in str(prompt_params["risk_level"]).split(",") if i.strip()]
        if levels:
            q &= Q(strategy__risk_level__in=levels)

    return q


def _link_risks_to_report(report) -> int:
    """
    根据报告的 prompt_params 查询关联风险，批量创建 AnalyseReportRisk 关联记录。

    Returns:
        关联的风险数量
    """
    from services.web.risk.models import AnalyseReportRisk

    prompt_params = report.prompt_params or {}
    q = _build_risk_query_from_prompt_params(prompt_params)

    # 查询符合条件的风险 ID 列表
    risk_ids = list(Risk.objects.filter(q).values_list("risk_id", flat=True))
    if not risk_ids:
        logger_celery.info(
            "[LinkRisksToReport] No risks found for report_id=%s, prompt_params=%s", report.report_id, prompt_params
        )
        return 0

    # 批量创建关联记录（忽略已存在的重复记录）
    report_risks = [AnalyseReportRisk(report=report, risk_id=rid) for rid in risk_ids]
    AnalyseReportRisk.objects.bulk_create(report_risks, ignore_conflicts=True)

    # 更新报告的 risk_count
    report.risk_count = len(risk_ids)
    report.save(update_fields=["risk_count"])

    logger_celery.info(
        "[LinkRisksToReport] Linked %d risks to report_id=%s",
        len(risk_ids),
        report.report_id,
    )
    return len(risk_ids)


@celery_app.task(
    bind=True,
    queue="risk_report",
    time_limit=900,
    max_retries=2,
    acks_late=True,
)
def generate_analyse_report(self, report_id: int):
    """
    异步生成AI分析报告

    直接将分析要求作为 prompt 传递给 Analyse Agent，
    sub_agent 配置已在 agent 服务中预配置，无需从调用端传入。
    """
    from services.web.risk.constants import AnalyseReportStatus
    from services.web.risk.models import AnalyseReport

    report = AnalyseReport.objects.get(report_id=report_id)

    try:
        # 1. 构造分析要求 prompt
        scenario = report.scenario
        if scenario:
            # 内置场景：使用场景配置的 system_prompt 作为分析要求前缀
            analysis_request = scenario.system_prompt
        else:
            # 自定义分析：使用用户自定义描述
            analysis_request = report.custom_prompt or "请使用风险查询条件查询风险详细数据生成分析报告。"

        # 将 prompt_params 拼接到分析要求中，构造完整的文本字符串
        prompt_params = report.prompt_params or {}
        prompt_params_text = json.dumps(prompt_params, ensure_ascii=False) if prompt_params else ""
        prompt = f"{analysis_request}\n{prompt_params_text}" if prompt_params_text else analysis_request

        # 2. 调用 Analyse Agent API（sub_agent 配置在 agent 服务中已预配置）
        result = api.bk_plugins_ai_audit_analyse.chat_completion(
            user=report.created_by or "admin",
            input=prompt,
            execute_kwargs={"stream": True},
        )

        # 3. 更新报告
        report.content = result
        report.status = AnalyseReportStatus.SUCCESS
        report.save(update_fields=["content", "status", "updated_at"])

        # 4. 根据 prompt_params 关联风险记录
        try:
            _link_risks_to_report(report)
        except Exception as link_exc:
            logger_celery.warning(
                "[GenerateAnalyseReport] Failed to link risks for report_id=%s: %s",
                report_id,
                link_exc,
            )

        return {"report_id": report.report_id}

    except Exception as exc:
        logger_celery.exception("[GenerateAnalyseReport] Failed report_id=%s: %s", report_id, exc)
        error_msg = f"[错误] {type(exc).__name__}: {exc}"
        report.status = AnalyseReportStatus.FAILED
        report.content = error_msg
        report.save(update_fields=["status", "content", "updated_at"])
        try:
            self.retry(exc=exc, countdown=60)
        except MaxRetriesExceededError:
            logger_celery.error("[GenerateAnalyseReport] Max retries reached for report_id=%s", report_id)
            raise exc


@celery_app.task(queue="risk_render")
def render_ai_variable(risk_id: str, ai_variables: list[dict]) -> dict[str, Any]:
    """Celery任务：渲染 AI 变量

    用于「AI 智能体预览」接口，单独预览 AI 变量的输出

    Args:
        risk_id: 风险ID
        ai_variables: AI 变量配置列表，格式：
            [
                {"name": "ai.risk_summary", "prompt_template": "..."},
                {"name": "ai.suggestion", "prompt_template": "..."}
            ]

    Returns:
        {
            "ai": {
                "risk_summary": "AI 生成的风险摘要...",
                "suggestion": "AI 生成的建议..."
            }
        }
    """
    try:
        # 获取风险实例
        _ = Risk.objects.get(risk_id=risk_id)

        # 构建 AI Provider
        ai_provider = AIProvider(context={"risk_id": risk_id}, ai_variables_config=ai_variables, enable_cache=True)

        # 执行 AI 调用，收集结果
        ai_results = {}
        for var_config in ai_variables:
            var_name = var_config["name"]
            # 提取变量名（去掉 ai. 前缀）
            field_name = var_name.replace("ai.", "") if var_name.startswith("ai.") else var_name

            try:
                result = ai_provider.get(name=var_name)
                if result:
                    result = render_ai_markdown(result)
                ai_results[field_name] = result
            except Exception as e:
                logger_celery.exception("[RenderAIVariable] Failed to get AI variable %s: %s", var_name, e)
                ai_results[field_name] = f"[Error: {e}]"

        return {"ai": ai_results}

    except Risk.DoesNotExist:
        logger_celery.error("[RenderAIVariable] Risk not found: %s", risk_id)
        raise ValueError(f"风险单不存在: {risk_id}")
    except Exception as e:
        logger_celery.exception("[RenderAIVariable] Failed to render AI variables: %s", e)
        raise

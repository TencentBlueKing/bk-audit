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

import time
from functools import reduce
from operator import or_
from typing import List

from bk_resource import api
from bk_resource.exceptions import APIRequestError
from blueapps.contrib.celery_tools.periodic import periodic_task
from blueapps.core.celery import celery_app
from blueapps.utils.logger import logger_celery
from celery.schedules import crontab
from django.conf import settings
from django.db.models import Q
from django.utils.translation import gettext

from apps.notice.constants import MsgType
from apps.notice.handlers import ErrorMsgHandler
from apps.notice.models import NoticeGroup
from apps.notice.parser import IgnoreMemberVariableParser
from core.lock import lock
from services.web.analyze.constants import (
    BKBASE_ERROR_LOG_LEVEL,
    CHECK_FLOW_STATUS_SLEEP_SECONDS,
    BaseControlTypeChoices,
    FlowStatusChoices,
)
from services.web.analyze.controls.auth import (
    AssetAuthHandler,
    CollectorPluginAuthHandler,
)
from services.web.analyze.models import ControlVersion
from services.web.bkbase import flow as bkbase_flow
from services.web.bkbase import permissions as bkbase_permissions
from services.web.bkbase.common import get_bkbase_version
from services.web.bkbase.constants import BKBaseVersion
from services.web.common.monitor import LostSceneDetectedEvent
from services.web.databus.models import CollectorPlugin, Snapshot
from services.web.strategy_v2.constants import StrategyStatusChoices
from services.web.strategy_v2.models import Strategy


@celery_app.task(time_limit=settings.DEFAULT_CACHE_LOCK_TIMEOUT)
def call_controller(
    func_name: str,
    strategy_id: int,
    base_control_type: BaseControlTypeChoices = None,
    *args,
    bkbase_version=BKBaseVersion.V3,
    **kwargs,
):
    """按生产任务时的 BKBase 版本执行，旧队列未标记消息保持 V3 归属。"""
    if bkbase_version != get_bkbase_version():
        logger_celery.warning("[CallControllerSkipped] Strategy %s queued for BKBase %s", strategy_id, bkbase_version)
        return
    if base_control_type == BaseControlTypeChoices.RULE_AUDIT:
        from services.web.analyze.controls.rule_audit import RuleAuditController

        controller = RuleAuditController(strategy_id=strategy_id)
    else:
        from services.web.analyze.controls.base import Controller

        controller = Controller.get_typed_controller(strategy_id=strategy_id)
    controller_func = getattr(controller, func_name, None)
    controller_func(*args, **kwargs)


BKSEC_RULE_SYNC_MAX_RETRIES = 3
BKSEC_RULE_SYNC_RETRY_INTERVAL = 1


def _report_bksec_rule_activation_failed(strategy: Strategy, error: Exception) -> None:
    """策略状态已收敛，但发单规则同步失败：上报监控，避免静默不派单。"""
    try:
        from services.web.common.monitor import BkSecConfigSyncFailedEvent
        from services.web.risk.bksec.constants import (
            BkSecConfigSyncFailReason,
            BkSecConfigSyncStage,
        )

        BkSecConfigSyncFailedEvent(
            context={
                "strategy_id": str(strategy.strategy_id),
                "stage": BkSecConfigSyncStage.RULE_SYNC.value,
                "fail_reason": BkSecConfigSyncFailReason.RULE_ACTIVATION_FAILED.value,
            },
            extra={"status": strategy.status, "error": str(error)},
        ).report()
    except Exception:  # NOCC:broad-except(告警失败不得影响策略状态收敛)
        logger_celery.exception(
            "[ReportBkSecRuleActivationFailed] strategy_id=%s status=%s",
            strategy.strategy_id,
            strategy.status,
        )


def _sync_bksec_rule_after_status_change(strategy: Strategy) -> None:
    """策略状态确认后同步 BKSEC 自动规则，保证规则只在启动成功后可见。"""
    if strategy.status == StrategyStatusChoices.RUNNING.value:
        strategy_alive = True
    elif strategy.status in (
        StrategyStatusChoices.START_FAILED.value,
        StrategyStatusChoices.UPDATE_FAILED.value,
    ):
        # 启动/更新异步失败：停用发单规则，避免失败态下规则仍对风险生效
        strategy_alive = False
    else:
        return

    from services.web.risk.bksec.rules import (
        BkSecPluginSyncError,
        BkSecPresetNotReady,
        sync_bksec_rule,
    )

    last_error = None
    for attempt in range(BKSEC_RULE_SYNC_MAX_RETRIES):
        try:
            sync_bksec_rule(strategy, strategy_alive=strategy_alive)
            return
        except (BkSecPluginSyncError, BkSecPresetNotReady) as err:
            # 插件同步内部已有重试；套餐缺失需人工配置，重试无意义，直接告警
            last_error = err
            break
        except Exception as err:  # NOCC:broad-except(规则同步失败需重试并告警)
            last_error = err
            if attempt < BKSEC_RULE_SYNC_MAX_RETRIES - 1:
                time.sleep(BKSEC_RULE_SYNC_RETRY_INTERVAL)

    if last_error is not None:
        logger_celery.error(
            "[SyncBkSecRuleAfterStatusChangeFailed] strategy_id=%s status=%s error=%s",
            strategy.strategy_id,
            strategy.status,
            last_error,
        )
        _report_bksec_rule_activation_failed(strategy, last_error)


@periodic_task(run_every=crontab(minute="*/10"), time_limit=settings.DEFAULT_CACHE_LOCK_TIMEOUT)
@lock(lock_name="celery:reconcile_bksec_auto_rule")
def reconcile_bksec_auto_rule():
    """补偿策略 RUNNING 且启用 BKSEC 配置，但自动发单规则缺失/未启用的情况。"""
    from services.web.risk.bksec.rules import sync_bksec_rule
    from services.web.risk.models import RiskRule

    strategies = Strategy.objects.filter(
        status=StrategyStatusChoices.RUNNING.value,
        bksec_config__enabled=True,
    )
    for strategy in strategies.iterator():
        try:
            latest_rule = RiskRule.objects.filter(auto_strategy_id=strategy.strategy_id).order_by("-version").first()
            if latest_rule and latest_rule.is_enabled:
                continue
            logger_celery.warning(
                "[ReconcileBkSecRule] Auto rule missing or disabled, strategy_id=%s", strategy.strategy_id
            )
            sync_bksec_rule(strategy, strategy_alive=True)
        except Exception:  # NOCC:broad-except(单个策略补偿失败不影响其他策略)
            logger_celery.exception("[ReconcileBkSecRuleFailed] strategy_id=%s", strategy.strategy_id)


@celery_app.task(time_limit=settings.DEFAULT_CACHE_LOCK_TIMEOUT)
def check_flow_status(strategy_id: int, success_status: str, failed_status: str, other_status: str, operation_id=None):
    """观测Flow并更新策略；过期V4操作回调不推进资源、不回写状态。"""

    # load strategy
    strategy: Strategy = Strategy.objects.filter(strategy_id=strategy_id).first()
    if strategy is None:
        logger_celery.error("[CheckFlowStatusFailed] Strategy Not Found => %s", strategy_id)
        return
    if not bkbase_flow.is_current_operation(strategy, operation_id):
        return
    if bkbase_flow.check_pure_operation(strategy, operation_id):
        return

    # check flow status
    message = None
    try:
        deploy_data = bkbase_flow.strategy_deploy_data(strategy)
        status = deploy_data["status"]
        if status == FlowStatusChoices.SUCCESS.value:
            next_status = success_status
        elif status == FlowStatusChoices.FAILURE.value:
            next_status = failed_status
            message = ";".join(
                [
                    str(log.get("message", ""))
                    for log in deploy_data.get("logs", [])
                    if log.get("level") == BKBASE_ERROR_LOG_LEVEL
                ]
            )
        else:
            next_status = other_status
    except (APIRequestError, TypeError, KeyError):
        next_status = other_status

    # update status
    if not bkbase_flow.persist_operation_status(strategy, operation_id, next_status, message):
        return

    # 状态确认后再同步自动规则：启动成功才启用，启动失败则保持关闭
    _sync_bksec_rule_after_status_change(strategy)

    # check re-run
    if strategy.status == other_status:
        retry_params = {"success_status": success_status, "failed_status": failed_status, "other_status": other_status}
        if operation_id is not None:
            retry_params["operation_id"] = operation_id
        check_flow_status.apply_async(
            args=[strategy_id],
            kwargs=retry_params,
            countdown=CHECK_FLOW_STATUS_SLEEP_SECONDS,
        )

    # check failed
    if strategy.status == failed_status:
        ErrorMsgHandler(title=gettext("Flow Status Abnormal"), content=gettext("Strategy ID:\t%s") % strategy_id).send()


@periodic_task(run_every=crontab(minute="*/10"), time_limit=settings.DEFAULT_CACHE_LOCK_TIMEOUT)
@lock(lock_name="celery:sync_plan_from_bkbase")
def sync_plan_from_bkbase():
    """
    从 BKBASE 同步方案
    """

    from services.web.analyze.controls.aiops import AiopsFeature, AiopsPlanSyncHandler

    if not AiopsFeature(help_text="check_flow_status").available:
        return

    try:
        AiopsPlanSyncHandler().sync()
    except Exception as e:
        logger_celery.exception("[AIOPS_SYNC] 执行 AiopsPlanSyncHandler.sync() 时发生异常: %s", str(e))
        raise


@periodic_task(run_every=crontab(minute="*/1"), time_limit=settings.DEFAULT_CACHE_LOCK_TIMEOUT)
@lock(lock_name="celery:auth_rt")
def auth_rt():
    """Auth Result Table For BkBase"""

    if not bkbase_permissions.project_auth_available():
        return

    # auth collector plugins
    plugins = list(CollectorPlugin.objects.filter(auth_rt=False, bkbase_table_id__isnull=False))
    for plugin in plugins:
        CollectorPluginAuthHandler(plugin).auth()

    # auth asset
    assets = list(Snapshot.objects.filter(auth_rt=False, bkbase_table_id__isnull=False))
    for asset in assets:
        AssetAuthHandler(asset).auth()


@celery_app.task(time_limit=settings.DEFAULT_CACHE_LOCK_TIMEOUT)
def toggle_monitor(strategy_id: int, is_active: bool, operation_id=None):
    """
    切换BKBASE数据监控开关状态；V4生产者携带operation_id，过期消息在平台读写前退出。
    """

    # 获取策略并判定关键参数存在
    strategy: Strategy = Strategy.objects.filter(strategy_id=strategy_id).first()
    if strategy and (
        (get_bkbase_version() == BKBaseVersion.V4 and not bkbase_flow.is_current_operation(strategy, operation_id))
        or (get_bkbase_version() != BKBaseVersion.V4 and operation_id is not None)
    ):
        logger_celery.info("[ToggleMonitorSuperseded] %s %s", strategy_id, operation_id)
        return
    if not strategy or not bkbase_flow.has_flow(strategy):
        logger_celery.error("[ToggleMonitorFailed] Strategy Status Invalid => %s", strategy_id)
        return

    # 获取通知组并判定关键参数存在
    notice_groups: List[NoticeGroup] = list(NoticeGroup.objects.filter(group_id__in=strategy.notice_groups))
    receivers = [
        {"receiver_type": "user", "username": member}
        for member in IgnoreMemberVariableParser().parse_groups(notice_groups)
    ]
    notify_config = list(
        {
            config["msg_type"]
            for notice_group in notice_groups
            for config in notice_group.notice_config
            if config.get("msg_type") != MsgType.VOICE
        }
    )
    if (not receivers or not notify_config) and not (get_bkbase_version() == BKBaseVersion.V4 and not is_active):
        logger_celery.error("[ToggleMonitorFailed] %s Notice Group Invalid => %s", strategy_id, strategy.notice_groups)
        return

    result = bkbase_flow.configure_monitor(
        strategy, active=is_active, receivers=receivers, notify_config=notify_config, operation_id=operation_id
    )
    if get_bkbase_version() == BKBaseVersion.V4 and result is None:
        logger_celery.info("[ToggleMonitorSuperseded] %s %s", strategy_id, operation_id)
        return
    logger_celery.info("[ToggleMonitorSuccess] %s %s", strategy_id, is_active)


@periodic_task(
    run_every=crontab(minute=settings.CHECK_LOST_SCENE_INTERVAL), soft_time_limit=settings.DEFAULT_CACHE_LOCK_TIMEOUT
)
@lock(lock_name="celery:check_lost_scene")
def check_lost_scene():
    """
    丢失场景检查任务：扫描策略中引用的控件版本是否已被删除
    """
    strategies = list(
        Strategy.objects.filter(control_id__isnull=False, control_version__isnull=False).only(
            "strategy_id", "control_id", "control_version", "strategy_name"
        )
    )

    control_pairs = {(s.control_id, s.control_version) for s in strategies}

    if not control_pairs:
        logger_celery.info("没有策略引用控件版本，跳过丢失场景检查任务")
        return
    q = reduce(or_, [Q(control_id=cid, control_version=cv) for cid, cv in control_pairs], Q())
    existing_pairs = set(ControlVersion.objects.filter(q).values_list("control_id", "control_version"))

    for strategy in strategies:
        if (strategy.control_id, strategy.control_version) not in existing_pairs:
            event = LostSceneDetectedEvent(
                target=f"strategy_{strategy.strategy_id}",
                context={
                    "strategy_id": str(strategy.strategy_id),
                    "control_id": strategy.control_id,
                    "control_version": str(strategy.control_version),
                    "strategy_name": strategy.strategy_name,
                },
                extra={"control_id": strategy.control_id, "control_version": strategy.control_version},
            )
            try:
                api.bk_monitor.report_event(event.to_json())
                logger_celery.info(f"丢失控件版本事件上报成功，策略ID={strategy.strategy_id}")
            except APIRequestError as e:
                logger_celery.error(f"丢失控件版本事件上报失败，策略ID={strategy.strategy_id}，错误信息：{e}")

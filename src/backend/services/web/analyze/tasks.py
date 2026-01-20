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
    ObjectType,
)
from services.web.analyze.controls.auth import (
    AssetAuthHandler,
    CollectorPluginAuthHandler,
)
from services.web.analyze.models import ControlVersion
from services.web.common.monitor import LostSceneDetectedEvent
from services.web.databus.models import CollectorPlugin, Snapshot
from services.web.strategy_v2.models import Strategy


@celery_app.task(time_limit=settings.DEFAULT_CACHE_LOCK_TIMEOUT)
def call_controller(
    func_name: str, strategy_id: int, base_control_type: BaseControlTypeChoices = None, *args, **kwargs
):
    """
    call controller async
    """
    if base_control_type == BaseControlTypeChoices.RULE_AUDIT:
        from services.web.analyze.controls.rule_audit import RuleAuditController

        controller = RuleAuditController(strategy_id=strategy_id)
    else:
        from services.web.analyze.controls.base import Controller

        controller = Controller.get_typed_controller(strategy_id=strategy_id)
    controller_func = getattr(controller, func_name, None)
    controller_func(*args, **kwargs)


@celery_app.task(time_limit=settings.DEFAULT_CACHE_LOCK_TIMEOUT)
def check_flow_status(strategy_id: int, success_status: str, failed_status: str, other_status: str):
    """
    check flow status
    """

    # load strategy
    strategy: Strategy = Strategy.objects.filter(strategy_id=strategy_id).first()
    if strategy is None:
        logger_celery.error("[CheckFlowStatusFailed] Strategy Not Found => %s", strategy_id)
        return

    # check flow status
    flow_id = strategy.backend_data["flow_id"]
    try:
        deploy_data = api.bk_base.get_flow_deploy_data(flow_id=flow_id)
        status = deploy_data["status"]
        if status == FlowStatusChoices.SUCCESS.value:
            strategy.status = success_status
        elif status == FlowStatusChoices.FAILURE.value:
            strategy.status = failed_status
            strategy.status_msg = ";".join(
                [
                    str(log.get("message", ""))
                    for log in deploy_data.get("logs", [])
                    if log.get("level") == BKBASE_ERROR_LOG_LEVEL
                ]
            )
            strategy.save(update_record=False, update_fields=["status_msg"])
        else:
            strategy.status = other_status
    except (APIRequestError, TypeError, KeyError):
        strategy.status = other_status

    # update status
    strategy.save(update_record=False, update_fields=["status"])

    # check re-run
    if strategy.status == other_status:
        time.sleep(CHECK_FLOW_STATUS_SLEEP_SECONDS)
        check_flow_status.delay(
            strategy_id, success_status=success_status, failed_status=failed_status, other_status=other_status
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

    from services.web.analyze.controls.aiops import AiopsFeature

    if not AiopsFeature(help_text="auth_rt").available:
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
def toggle_monitor(strategy_id: int, is_active: bool):
    """
    切换BKBASE数据监控开关状态
    """

    # 获取策略并判定关键参数存在
    strategy: Strategy = Strategy.objects.filter(strategy_id=strategy_id).first()
    if not strategy or not strategy.backend_data or not strategy.backend_data.get("flow_id"):
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
    if not receivers or not notify_config:
        logger_celery.error("[ToggleMonitorFailed] %s Notice Group Invalid => %s", strategy_id, strategy.notice_groups)
        return

    # 获取告警配置
    alert_config = api.bk_base.get_alert_configs(
        object_type=ObjectType.DATAFLOW, object_id=strategy.backend_data["flow_id"]
    )
    alert_config["active"] = is_active
    alert_config["alert_config_id"] = alert_config["id"]
    alert_config["receivers"] = receivers
    alert_config["notify_config"] = notify_config
    api.bk_base.edit_alert_configs(**alert_config)
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

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

from bk_resource import api
from bk_resource.exceptions import APIRequestError
from blueapps.utils.logger import logger_celery
from celery.schedules import crontab
from celery.task import periodic_task, task
from django.utils.translation import gettext

from apps.notice.handlers import ErrorMsgHandler
from core.utils.tools import single_task_decorator
from services.web.analyze.constants import (
    BKBASE_ERROR_LOG_LEVEL,
    CHECK_FLOW_STATUS_SLEEP_SECONDS,
    FlowStatusChoices,
)
from services.web.analyze.controls.auth import (
    AssetAuthHandler,
    CollectorPluginAuthHandler,
)
from services.web.analyze.controls.base import Controller
from services.web.databus.models import CollectorPlugin, Snapshot
from services.web.strategy_v2.models import Strategy


@task()
def call_controller(func_name: str, strategy_id: int, *args, **kwargs):
    """
    call controller async
    """

    # init controller
    controller = Controller(strategy_id=strategy_id)
    controller_func = getattr(controller, func_name, None)
    controller_func(*args, **kwargs)


@task()
def check_flow_status(strategy_id: int, success_status: str, failed_status: str, other_status: str):
    """
    check flow status
    """

    from services.web.analyze.controls.aiops import AiopsFeature

    if not AiopsFeature(help_text="check_flow_status").available:
        return

    # load strategy
    strategy = Strategy.objects.filter(strategy_id=strategy_id).first()
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
            strategy.save(update_fields=["status_msg"])
        else:
            strategy.status = other_status
    except (APIRequestError, TypeError, KeyError):
        strategy.status = other_status

    # update status
    strategy.save(update_fields=["status"])

    # check re-run
    if strategy.status == other_status:
        time.sleep(CHECK_FLOW_STATUS_SLEEP_SECONDS)
        check_flow_status.delay(
            strategy_id, success_status=success_status, failed_status=failed_status, other_status=other_status
        )

    # check failed
    if strategy.status == failed_status:
        ErrorMsgHandler(title=gettext("Flow Status Abnormal"), content=gettext("Strategy ID:\t%s") % strategy_id).send()


@periodic_task(run_every=crontab(minute="*/1"))
@single_task_decorator
def sync_plan_from_bkbase():
    """
    从 BKBASE 同步方案
    """

    from services.web.analyze.controls.aiops import AiopsFeature, AiopsPlanSyncHandler

    if not AiopsFeature(help_text="check_flow_status").available:
        return

    AiopsPlanSyncHandler().sync()


@periodic_task(run_every=crontab(minute="*/1"))
@single_task_decorator
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
    assets = list(Snapshot.objects.filter(auth_rt=False, bkbase_hdfs_table_id__isnull=False))
    for asset in assets:
        AssetAuthHandler(asset).auth()

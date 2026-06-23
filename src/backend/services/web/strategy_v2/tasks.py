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

from datetime import datetime, timedelta
from typing import Dict, List, Optional

from bk_resource import api
from blueapps.contrib.celery_tools.periodic import periodic_task
from blueapps.utils.logger import logger_celery
from celery.schedules import crontab
from django.conf import settings

from core.lock import lock
from services.web.analyze.constants import FlowNodeStatusChoices
from services.web.strategy_v2.constants import (
    RuleAuditSourceType,
    StrategyStatusChoices,
)
from services.web.strategy_v2.handlers.strategy_running_status import (
    StrategyRunningStatusHandler,
)
from services.web.strategy_v2.models import Strategy

# 策略状态与Flow状态的期望关系
EXPECTED_FLOW_STATUS = {
    StrategyStatusChoices.RUNNING.value: FlowNodeStatusChoices.RUNNING.value,
    StrategyStatusChoices.STARTING.value: FlowNodeStatusChoices.RUNNING.value,
    StrategyStatusChoices.UPDATING.value: FlowNodeStatusChoices.RUNNING.value,
    StrategyStatusChoices.DISABLED.value: FlowNodeStatusChoices.NO_START.value,
    StrategyStatusChoices.STOPPING.value: FlowNodeStatusChoices.NO_START.value,
    StrategyStatusChoices.START_FAILED.value: FlowNodeStatusChoices.FAILED.value,
    StrategyStatusChoices.UPDATE_FAILED.value: FlowNodeStatusChoices.FAILED.value,
    StrategyStatusChoices.STOP_FAILED.value: FlowNodeStatusChoices.FAILED.value,
    StrategyStatusChoices.FAILED.value: FlowNodeStatusChoices.FAILED.value,
    StrategyStatusChoices.DELETE_FAILED.value: FlowNodeStatusChoices.FAILED.value,
}


class StrategyStatusChecker:
    """策略状态检查器"""

    def fetch_flow_status(self, flow_id: Optional[int]) -> str:
        """
        获取Flow状态
        """
        if not flow_id:
            return FlowNodeStatusChoices.NO_START.value
        try:
            data = api.bk_base.get_flow_deploy_data(flow_id=flow_id)
        except Exception as error:  # pylint: disable=broad-except
            return f"error:{error}"
        if not data:
            return FlowNodeStatusChoices.NO_START.value
        return data.get("flow_status") or FlowNodeStatusChoices.NO_START.value

    def judge(self, strategy: Strategy, flow_status: str) -> Optional[str]:
        if flow_status.startswith("error:"):
            return flow_status
        expected = EXPECTED_FLOW_STATUS.get(strategy.status)
        if expected and flow_status != expected:
            return f"expect_flow={expected}, actual={flow_status}"
        # strategy 暂无 flow_id 却处于需要运行的状态
        if not (strategy.backend_data or {}).get("flow_id") and strategy.status not in (
            StrategyStatusChoices.DISABLED.value,
            StrategyStatusChoices.DELETE_FAILED.value,
        ):
            return "missing flow_id"

        failed_statuses = [
            StrategyStatusChoices.START_FAILED.value,
            StrategyStatusChoices.UPDATE_FAILED.value,
            StrategyStatusChoices.STOP_FAILED.value,
            StrategyStatusChoices.DELETE_FAILED.value,
        ]
        if strategy.status in failed_statuses:
            return f"{strategy.status} operation failed"

        if not flow_status:
            return None

        # 检查启动中的策略是否有错误消息
        if strategy.status == StrategyStatusChoices.RUNNING.value and strategy.status_msg:
            return f"starting strategy has error messages: {strategy.status_msg}"

        return None

    def is_realtime_strategy(self, strategy: Strategy) -> bool:
        """判断是否为实时策略"""
        source_type = strategy.configs.get("data_source", {}).get("source_type")
        return source_type == RuleAuditSourceType.REALTIME

    def get_strategy_running_data(self, strategy: Strategy, days: int = 1, limit: int = 100) -> List[Dict]:
        """获取策略运行数据"""
        try:
            end_time = datetime.now()
            start_time = end_time - timedelta(days=days)

            handler = StrategyRunningStatusHandler.get_typed_handler(
                strategy=strategy, start_time=start_time, end_time=end_time, limit=limit, offset=0
            )

            if not handler:
                return []

            running_status = handler.get_strategy_running_status()

            result = []
            for status in running_status:
                result.append(
                    {
                        "schedule_time": status.get("schedule_time", ""),
                        "data_time": status.get("data_time", ""),
                        "err_msg": status.get("err_msg", ""),
                        "status": status.get("status", ""),
                        "status_str": status.get("status_str", ""),
                        "risk_count": status.get("risk_count", 0),
                    }
                )

            return result

        except Exception as e:
            logger_celery.error("[GetRunningDataError] strategy=%s error=%s", strategy.strategy_id, str(e))
            return []

    def check_no_schedule_records(
        self, strategy: Strategy, flow_status: Optional[str], running_data: List[Dict] = None
    ) -> Optional[str]:
        """检查离线策略的调度记录情况
        - 运行中策略但无调度记录
        - 运行失败情况
        """
        if not flow_status:
            return None

        # 检查RUNNING状态的策略（运行中但无调度记录）
        if (
            strategy.status == StrategyStatusChoices.RUNNING.value
            and flow_status == FlowNodeStatusChoices.RUNNING.value
        ):

            if not running_data:
                return "running flow has no schedule records in last 1 day"

            # 检查是否有失败的调度记录
            failed_records = [record for record in running_data if record.get("status") == "failed"]
            if failed_records:
                latest_failed = failed_records[0]
                return f"schedule failed: {latest_failed.get('err_msg', 'unknown error')}"

        return None

    def report_anomaly(self, strategy: Strategy, anomaly):
        """上报异常事件"""
        try:
            # 统一处理异常信息（支持字符串、字典和其他类型）
            if isinstance(anomaly, dict):
                reason = anomaly.get("reason", str(anomaly))
            elif hasattr(anomaly, 'reason'):
                reason = getattr(anomaly, 'reason', str(anomaly))
            else:
                reason = str(anomaly)

            # 构造监控事件数据
            event_data = {
                "data_id": settings.ALERT_DATA_ID,
                "access_token": settings.ALERT_ACCESS_TOKEN,
                "data": [
                    {
                        "target": strategy.strategy_id,
                        "event_name": f"strategy_exception_{strategy.strategy_id}",
                        "event": {"content": reason},
                        "timestamp": int(datetime.now().timestamp() * 1000),
                    }
                ],
            }

            api.bk_monitor.report_event(**event_data)

            if "missing flow_id" in reason or "expect_flow=" in reason:
                logger_celery.warning(
                    "[StrategyStatusMismatch] strategy=%s namespace=%s type=%s status=%s flow_status=%s reason=%s",
                    strategy.strategy_id,
                    strategy.namespace,
                    strategy.strategy_type,
                    strategy.status,
                    (strategy.backend_data or {}).get("flow_id", "no_flow"),
                    reason,
                )
            else:
                logger_celery.error(
                    "[StrategyStatusAnomaly] strategy=%s namespace=%s type=%s status=%s reason=%s",
                    strategy.strategy_id,
                    strategy.namespace,
                    strategy.strategy_type,
                    strategy.status,
                    reason,
                )

        except Exception as e:
            logger_celery.error("[StrategyStatusReportFailed] strategy=%s error=%s", strategy.strategy_id, str(e))


@periodic_task(run_every=crontab(minute="*/10"), time_limit=settings.DEFAULT_CACHE_LOCK_TIMEOUT)
@lock(lock_name="celery:check_strategy_status_anomalies")
def check_strategy_status_anomalies():
    """
    检查策略状态异常定时任务
    """
    checker = StrategyStatusChecker()

    # 获取所有策略
    strategies = Strategy.objects.all()

    for strategy in strategies:
        try:
            # 获取策略对应的flow_id
            flow_id = (strategy.backend_data or {}).get("flow_id")

            # 获取flow状态
            flow_status = checker.fetch_flow_status(flow_id)

            # 获取策略运行数据（最近1天的数据）
            running_data = checker.get_strategy_running_data(strategy, days=1, limit=100)

            # 判断策略类型：离线策略还是实时策略
            if checker.is_realtime_strategy(strategy):
                # 实时策略：使用judge方法检查状态一致性
                anomaly_reason = checker.judge(strategy, flow_status)
            else:
                # 离线策略：检查调度记录情况
                anomaly_reason = checker.check_no_schedule_records(strategy, flow_status, running_data)

            # 如果有异常，上报监控事件
            if anomaly_reason:
                checker.report_anomaly(strategy, anomaly_reason)

                logger_celery.warning(
                    "[StrategyStatusAnomalyDetected] strategy=%s namespace=%s "
                    "type=%s status=%s flow_status=%s reason=%s",
                    strategy.strategy_id,
                    strategy.namespace,
                    strategy.strategy_type,
                    strategy.status,
                    flow_status,
                    anomaly_reason,
                )
            else:
                logger_celery.debug(
                    "[StrategyStatusNormal] strategy=%s namespace=%s " "type=%s status=%s flow_status=%s",
                    strategy.strategy_id,
                    strategy.namespace,
                    strategy.strategy_type,
                    strategy.status,
                    flow_status,
                )

        except Exception as e:
            logger_celery.error("[StrategyStatusCheckError] strategy=%s error=%s", strategy.strategy_id, str(e))

    logger_celery.info("[StrategyStatusCheckCompleted] total_strategies=%s", len(strategies))

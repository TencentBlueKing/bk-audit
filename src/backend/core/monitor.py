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
import logging
import time
from typing import Any, Dict, List, Optional

from bk_resource import api
from blueapps.core.celery import celery_app
from django.conf import settings

from core.utils.service import get_service_name

__all__ = ["Event", "Metric", "report_event_to_bk_monitor", "report_metric_to_bk_monitor"]

logger = logging.getLogger(__name__)


class Event:
    name: str = ""  # 事件名称
    labelnames: List[str] = []  # 维度字段列表
    documentation: str = ""  # 事件说明

    # 监控平台鉴权信息
    data_id: int = settings.ALERT_DATA_ID
    access_token: str = settings.ALERT_ACCESS_TOKEN

    def __init__(
        self,
        target: str = "",
        context: Optional[Dict] = None,
        extra: Optional[Dict] = None,
        records: Optional[List[Dict[str, Any]]] = None,
    ):
        self.timestamp = int(time.time() * 1000)
        event_records = (
            records if records is not None else [{"target": target, "context": context or {}, "extra": extra}]
        )
        self.records = [self._build_record(record) for record in event_records]

        # 保留单条场景的常用属性，兼容既有测试和临时调试代码。
        first_record = self.records[0] if self.records else {}
        self.target = first_record.get("target", target)
        self.dimension = first_record.get("dimension", {})
        self.content = first_record.get("event", {}).get("content", self.documentation or self.name)

    def _build_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        target = record.get("target", "")
        context = record.get("context") or {}
        extra = record.get("extra")
        timestamp = record.get("timestamp") or self.timestamp

        # 事件维度只取子类声明的 labelnames，避免把任意 context 全量打进 BKM。
        dimension = {field: str(context.get(field, "")) for field in self.labelnames}
        dimension["job"] = get_service_name()

        if extra:
            detail = ", ".join(f"{k}={v}" for k, v in extra.items())
            content = f"{self.documentation or self.name}: {detail}"
        else:
            content = self.documentation or self.name

        return {
            "event_name": str(self.name),
            "event": {"content": content},
            "target": target,
            "dimension": dimension,
            "timestamp": timestamp,
        }

    def to_json(self) -> Dict:
        return {
            "data_id": self.data_id,
            "access_token": self.access_token,
            "data": self.records,
        }

    def report(self):
        """同步上报监控事件。"""

        try:
            return api.bk_monitor.report_event(self.to_json())
        except Exception:  # NOCC:broad-except(监控上报失败不能影响业务流程)
            logger.exception("[MonitorEvent] report failed event=%s", self.name)
            return None

    def async_report(self):
        """异步上报监控事件，避免业务流程阻塞在监控 API 调用上。"""

        try:
            return report_event_to_bk_monitor.delay(self.to_json())
        except Exception:  # NOCC:broad-except(监控任务投递失败不能影响业务流程)
            logger.exception("[MonitorEvent] async report failed event=%s", self.name)
            return None


@celery_app.task(time_limit=settings.MONITOR_EVENT_TASK_TIMEOUT)
def report_event_to_bk_monitor(payload: Dict):
    """统一的监控事件异步上报任务。"""

    return api.bk_monitor.report_event(payload)


class Metric:
    """BKM 自定义指标记录封装。

    调用方只需要关心 metrics 和低基数 dimension；data_id、access_token、target、
    timestamp、job 这些 BKM 协议字段统一在这里补齐。单条记录直接传 metrics /
    dimension；多条记录传 records，不需要调用方拼 BKM payload。
    """

    target: str = "bk_audit"

    def __init__(
        self,
        metrics: Optional[Dict[str, int | float]] = None,
        dimension: Optional[Dict[str, Any]] = None,
        target: Optional[str] = None,
        timestamp: Optional[int] = None,
        records: Optional[List[Dict[str, Any]]] = None,
    ):
        self.data_id = settings.LOG_EXPORT_STATUS_DATA_ID
        self.access_token = settings.LOG_EXPORT_STATUS_ACCESS_TOKEN
        self.timestamp = timestamp or int(time.time() * 1000)
        metric_records = (
            records
            if records is not None
            else [
                {
                    "metrics": metrics or {},
                    "dimension": dimension or {},
                    "target": target,
                    "timestamp": self.timestamp,
                }
            ]
        )
        self.records = [self._build_record(record) for record in metric_records]

        # 保留单条场景的常用属性，兼容既有测试和临时调试代码。
        first_record = self.records[0] if self.records else {}
        self.metrics = first_record.get("metrics", {})
        self.target = first_record.get("target", target or self.target)
        self.dimension = first_record.get("dimension", {})

    def _build_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        dimension = {key: str(value) for key, value in (record.get("dimension") or {}).items() if value is not None}
        dimension["job"] = get_service_name()
        return {
            "target": record.get("target") or self.target,
            "metrics": record.get("metrics") or {},
            "dimension": dimension,
            "timestamp": record.get("timestamp") or self.timestamp,
        }

    @property
    def metric_names(self) -> List[str]:
        return sorted({name for record in self.records for name in record.get("metrics", {})})

    @property
    def is_configured(self) -> bool:
        return bool(self.data_id and self.access_token)

    def to_json(self) -> Dict:
        return {
            "data_id": self.data_id,
            "access_token": self.access_token,
            "data": self.records,
        }

    def report(self):
        """同步上报监控指标。"""

        if not self.is_configured:
            return None
        try:
            return api.bk_monitor.report_metric(self.to_json())
        except Exception:  # NOCC:broad-except(监控上报失败不能影响业务流程)
            logger.exception("[MonitorMetric] report failed metrics=%s", self.metric_names)
            return None

    def async_report(self):
        """异步上报监控指标，避免业务流程阻塞在监控 API 调用上。"""

        if not self.is_configured:
            return None
        try:
            return report_metric_to_bk_monitor.delay(self.to_json())
        except Exception:  # NOCC:broad-except(监控任务投递失败不能影响业务流程)
            logger.exception("[MonitorMetric] async report failed metrics=%s", self.metric_names)
            return None


@celery_app.task(time_limit=settings.MONITOR_METRIC_TASK_TIMEOUT)
def report_metric_to_bk_monitor(payload: Dict):
    """统一的监控指标异步上报任务。"""

    return api.bk_monitor.report_metric(payload)

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
from typing import List

from bk_resource import api, resource
from bk_resource.exceptions import APIRequestError
from blueapps.utils.logger import logger
from django.conf import settings
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.settings import api_settings

from apps.meta.models import GlobalMetaConfig
from apps.meta.utils.fields import REPORT_TIME
from services.web.databus.constants import (
    COLLECTOR_CHECK_AGG_SIZE,
    COLLECTOR_CHECK_DECIMALS,
    COLLECTOR_CHECK_EXTRA_CONFIG_KEY,
    COLLECTOR_CHECK_TIME_PERIOD,
    COLLECTOR_CHECK_TIME_RANGE,
)
from services.web.databus.models import CollectorConfig


class ReportCheckHandler:
    """
    检测是否有不连续的数据
    """

    def __init__(
        self, namespace: str = None, end_time: datetime.datetime = None, time_period: int = None, time_range: int = None
    ):
        """
        初始化，注册采集项
        """
        self.namespace = namespace or settings.DEFAULT_NAMESPACE
        self.time_period: int = time_period or COLLECTOR_CHECK_TIME_PERIOD
        self.time_range: int = time_range or COLLECTOR_CHECK_TIME_RANGE
        self.data_id: int = int(os.getenv("BKAPP_COLLECTOR_CHECK_REPORT_DATA_ID", -1))
        self.access_token: str = os.getenv("BKAPP_COLLECTOR_CHECK_REPORT_ACCESS_TOKEN", "")
        self.end_time = end_time or datetime.datetime.now()
        self.custom_end_time = end_time is not None
        self.start_time = self.end_time
        self.get_timerange()

    def check(self):
        """
        检查入口
        """
        # 获取数据
        collector_data = self.search_es()
        # 遍历采集项数据
        for collector_item in collector_data:
            collector_config_id = collector_item["key"]
            server_data = collector_item["hosts"]["buckets"]
            # 遍历服务器数据
            for server_item in server_data:
                ip = server_item["key"]
                time_data = server_item["count"]["buckets"]
                # 遍历时序数据
                for time_item in time_data:
                    self.report_event(collector_config_id, ip, time_item)
        logger.info("[ReportCheckFinished]")

    def check_count(self, data: dict) -> int:
        """
        判断GseIndex是否连续
        大于0则丢失，小于0则异常
        """
        # 获取判断数据
        _, _, min_gse_index, max_gse_index, event_count = self.load_data(data)
        result = max_gse_index - min_gse_index + 1 - event_count
        return result

    def load_data(self, data: dict) -> (str, int, int, int, int):
        """
        解析数据
        """
        # timestamp, doc_count, min_gse_index, max_gse_index, event_count
        return (
            data["key"],
            data["doc_count"],
            data["min_gse_index"]["value"],
            data["max_gse_index"]["value"],
            len(data["gseIndex"]["buckets"]),
        )

    def search_es(self) -> List[dict]:
        """
        检索ES获取聚合信息
        """
        data = resource.query.es_query(**self.query_config)
        return data.get("aggregations", {}).get("collectors", {}).get("buckets", [])

    @property
    def query_config(self):
        extra_filter = GlobalMetaConfig.get(COLLECTOR_CHECK_EXTRA_CONFIG_KEY, default=[])
        return {
            "namespace": self.namespace,
            "start_time": self.start_time.strftime(api_settings.DATETIME_FORMAT),
            "end_time": self.end_time.strftime(api_settings.DATETIME_FORMAT),
            "time_field": REPORT_TIME.field_name,
            "query_string": "*",
            "filter": [*extra_filter],
            "size": 0,
            "aggs": {
                "collectors": {
                    "terms": {"field": "collector_config_id", "size": COLLECTOR_CHECK_AGG_SIZE},
                    "aggs": {
                        "hosts": {
                            "terms": {"field": "serverIp", "size": COLLECTOR_CHECK_AGG_SIZE},
                            "aggs": {
                                "count": {
                                    "histogram": {"field": "bk_receive_time", "interval": self.time_range},
                                    "aggs": {
                                        "gseIndex": {"terms": {"field": "gseIndex", "size": COLLECTOR_CHECK_AGG_SIZE}},
                                        "min_gse_index": {"min": {"field": "gseIndex"}},
                                        "max_gse_index": {"max": {"field": "gseIndex"}},
                                    },
                                }
                            },
                        }
                    },
                }
            },
        }

    def get_timerange(self) -> None:
        """
        获取时间配置
        """
        self.end_time = self.end_time.replace(microsecond=0)
        if not self.custom_end_time:
            self.end_time = self.end_time.replace(second=0)
        self.start_time = self.end_time - datetime.timedelta(seconds=self.time_range * self.time_period)

    def report_event(self, collector_id: int, ip: str, data: dict) -> None:
        """
        上报事件
        """
        # 检查数据有效
        if data["doc_count"] == 0:
            loss_event_count = 0
            timestamp = data["key"]
            doc_count, min_gse_index, max_gse_index, event_count = 0, 0, 0, 0
        # 计算数据
        else:
            loss_event_count = self.check_count(data)
            timestamp, doc_count, min_gse_index, max_gse_index, event_count = self.load_data(data)
        start_time = datetime.datetime.fromtimestamp(timestamp, tz=timezone.get_default_timezone())
        end_time = start_time + datetime.timedelta(seconds=self.time_range)
        # 打印日志
        logger.info(
            "[GseIndexCheckResult] "
            "CollectorID => %s; "
            "StartTime => %s; "
            "EndTime => %s; "
            "TimeStamp => %d "
            "ServerIp => %s; "
            "LossCount => %d "
            "DocCount => %d; "
            "MinGseIndex => %d; "
            "MaxGseIndex => %d; "
            "EventCount => %d",
            collector_id,
            start_time,
            end_time,
            timestamp,
            ip,
            loss_event_count,
            doc_count,
            min_gse_index,
            max_gse_index,
            event_count,
        )
        # 判断是否上报
        if not self.access_token:
            return
            # 计算指标
        event_total = loss_event_count + event_count
        if event_total > 0:
            loss_rate = loss_event_count / event_total
        elif loss_event_count > 0:
            loss_rate = 1
        else:
            loss_rate = 0
        # 上报到监控自定义指标
        params = {
            "data_id": self.data_id,
            "access_token": self.access_token,
            "data": [
                {
                    "target": str(collector_id),
                    "metrics": {
                        "DocCount": doc_count,
                        "GseIndexCount": event_count,
                        "LossCount": loss_event_count,
                        "LossRate": round(loss_rate, COLLECTOR_CHECK_DECIMALS),
                        "AvailableRate": round(1 - loss_rate, COLLECTOR_CHECK_DECIMALS),
                        "MaxGseIndex": max_gse_index,
                        "MinGseIndex": min_gse_index,
                    },
                    "dimension": {
                        "ServerIP": ip,
                        "CollectorConfigID": str(collector_id),
                        **CollectorConfig.load_dimensions(collector_id),
                    },
                    "timestamp": int(end_time.timestamp() * 1000),
                }
            ],
        }
        try:
            api.bk_monitor.report_metric(params)
        except (APIRequestError, ValidationError):
            pass

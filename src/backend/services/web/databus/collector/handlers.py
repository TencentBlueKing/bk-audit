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

from bk_resource import api
from bk_resource.exceptions import APIRequestError
from blueapps.utils.logger import logger
from django.utils import timezone
from django.utils.timezone import get_default_timezone
from rest_framework.settings import api_settings

from services.web.databus.constants import SourcePlatformChoices
from services.web.databus.models import CollectorConfig


class TailLogHandler:
    """
    最近日志处理
    """

    @classmethod
    def get_instance(cls, collector: CollectorConfig) -> "TailLogHandler":
        if collector.source_platform == SourcePlatformChoices.BKLOG.value:
            return BkLogTailLogHandler(collector)
        if collector.source_platform == SourcePlatformChoices.BKBASE.value:
            return BkBaseTailLogHandler(collector)
        raise NotImplementedError(
            "[TailLogHandlerNotImplemented] Collector => {}; SourcePlatform => {}".format(
                collector.collector_config_id, collector.source_platform
            )
        )

    def __init__(self, collector: CollectorConfig):
        self.collector = collector
        self.tail_logs = []
        self.tail_log_time: datetime = None

    def load_tail_log(self):
        raise NotImplementedError

    def parse_log_time(self):
        raise NotImplementedError

    def sync(self):
        try:
            self.load_tail_log()
        except APIRequestError as err:
            logger.warning(
                "[GetCollectorTailLogError] CollectorConfigID => %s; Err => %s", self.collector.collector_config_id, err
            )
        if self.tail_logs:
            try:
                self.parse_log_time()
            except Exception as err:
                logger.warning(
                    "[ParseLogFailed] Collector => %s; Log => %s; Err => %s",
                    self.collector.collector_config_id,
                    self.tail_logs,
                    err,
                )
        self.collector.tail_log_time = self.tail_log_time
        self.collector.save(update_fields=["tail_log_time"])


class BkLogTailLogHandler(TailLogHandler):
    """
    日志平台最近日志获取
    """

    def load_tail_log(self):
        self.tail_logs = api.bk_log.get_collector_tail_log(collector_config_id=self.collector.collector_config_id)

    def parse_log_time(self):
        self.tail_log_time = datetime.datetime.strptime(
            self.tail_logs[0].get("origin", {}).get("datetime"), api_settings.DATETIME_FORMAT
        ).replace(tzinfo=get_default_timezone())


class BkBaseTailLogHandler(TailLogHandler):
    """
    计算平台最近日志获取
    """

    def load_tail_log(self):
        self.tail_logs = api.bk_base.get_rawdata_tail(bk_data_id=self.collector.bk_data_id)

    def parse_log_time(self):
        start_time = int(json.loads(self.tail_logs[0].get("value", "{}")).get("start_time"))
        self.tail_log_time = datetime.datetime.fromtimestamp(start_time / 1000).astimezone(
            timezone.get_default_timezone()
        )

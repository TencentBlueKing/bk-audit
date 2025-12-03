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

import json
from time import sleep

from blueapps.utils.logger import logger
from django.conf import settings
from django.core.management.base import BaseCommand
from kafka import KafkaConsumer

from core.kafka import KafkaRecordConsumer
from services.web.analyze.constants import AUDIT_EVENT_QUEUE_TOPIC_PATTERN
from services.web.risk.handlers.risk import RiskHandler
from services.web.risk.models import ManualEvent


class AuditEventKafkaRecordConsumer(KafkaRecordConsumer):
    def __init__(self, consumer: KafkaConsumer, timeout_ms: int, max_records: int, sleep_time: float, sleep_wait=True):
        super().__init__(consumer, timeout_ms, max_records, sleep_time, sleep_wait)
        self.eligible_strategy_ids = RiskHandler.fetch_eligible_strategy_ids()

    def process_records(self, records: list):
        if records:
            first_record = records[0]
            logger.info(
                "[%s] processing batch topic=%s partition=%s count=%s offset_range=[%s,%s]",
                self.__class__.__name__,
                first_record.topic,
                first_record.partition,
                len(records),
                records[0].offset,
                records[-1].offset,
            )
        self.eligible_strategy_ids = RiskHandler.fetch_eligible_strategy_ids()  # 更新 eligible_strategy_ids
        super().process_records(records)

    def process_record(self, record):
        key_present = record.key is not None
        value = record.value
        value_type = type(value).__name__
        if isinstance(value, (str, bytes)):
            value_size = len(value)
        elif isinstance(value, dict):
            value_size = len(value.keys())
        elif isinstance(value, list):
            value_size = len(value)
        else:
            value_size = None
        logger.info(
            "[%s] record topic=%s partition=%s offset=%s key_present=%s value_type=%s value_size=%s",
            self.__class__.__name__,
            record.topic,
            record.partition,
            record.offset,
            key_present,
            value_type,
            value_size,
        )
        if isinstance(value, dict) and 'manual_event_id' in value:
            value = value['manual_event_id']
            ManualEvent.objects.filter(manual_event_id=int(value)).update(manual_synced=True)
            logger.info("manual_event_id %s synced." % value)
        else:
            logger.info("manual_event_id not found in value.The value is %s." % value)
        RiskHandler().generate_risk(value, self.eligible_strategy_ids)


class Command(BaseCommand):
    """从 kafka 中读取并生成事件"""

    def handle(self, *args, **kwargs) -> None:
        config: dict = settings.KAFKA_CONFIG
        while True:
            logger.info("Waiting for kafka config...")
            if config:
                break
            sleep(5)
        consumer = KafkaConsumer(
            **config,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            enable_auto_commit=False,
        )
        consumer.subscribe(pattern=AUDIT_EVENT_QUEUE_TOPIC_PATTERN)
        timeout_ms = settings.EVENT_KAFKA_TIMEOUT_MS
        max_records = settings.EVENT_KAFKA_MAX_RECORDS
        sleep_time = settings.EVENT_KAFKA_SLEEP_TIME
        AuditEventKafkaRecordConsumer(
            consumer=consumer, timeout_ms=timeout_ms, max_records=max_records, sleep_time=sleep_time
        ).process()

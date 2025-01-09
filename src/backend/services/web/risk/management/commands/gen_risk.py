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

from django.conf import settings
from django.core.management.base import BaseCommand
from kafka import KafkaConsumer

from core.kafka import KafkaRecordConsumer
from services.web.analyze.constants import AUDIT_EVENT_QUEUE_TOPIC_PATTERN
from services.web.risk.handlers.risk import RiskHandler


class AuditEventKafkaRecordConsumer(KafkaRecordConsumer):
    def process_record(self, record):
        RiskHandler().generate_risk(record.value)


class Command(BaseCommand):
    """从 kafka 中读取并生成事件"""

    def handle(self, *args, **kwargs) -> None:
        config: dict = settings.KAFKA_CONFIG
        if not config:
            return
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

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

import abc
import time

from blueapps.utils.logger import logger
from kafka import KafkaConsumer

from core.connection import ping_db


class KafkaRecordConsumer:
    """kafka 消息消费者基类"""

    def __init__(self, consumer: KafkaConsumer, timeout_ms: int, max_records: int, sleep_time: float, sleep_wait=True):
        self.consumer = consumer
        self.timeout_ms = timeout_ms
        self.max_records = max_records
        self.sleep_time = sleep_time
        self.sleep_wait = sleep_wait

    def process(self):
        while True:
            data = self.consumer.poll(timeout_ms=self.timeout_ms, max_records=self.max_records)
            if not data:
                logger.info(f"[{self.__class__.__name__}] no message received, wait {self.sleep_time}s ...")
                if not self.sleep_wait:
                    return
                time.sleep(self.sleep_time)
                continue
            records_summary = {f"{tp.topic}:{tp.partition}": len(records) for tp, records in data.items()}
            total_records = sum(records_summary.values())
            logger.info(
                f"[{self.__class__.__name__}] polled {total_records} records from {len(data)} "
                f"partitions: {records_summary}"
            )
            # 重连 db，防止消费者长时间没有消费数据的情况下， db 连接因为空闲被释放
            ping_db()
            for records in data.values():
                self.process_records(records)
            self.consumer.commit()

    def process_records(self, records: list):
        for record in records:
            try:
                self.process_record(record)
            except Exception as e:  # pylint: disable=broad-except
                logger.exception(f"[{self.__class__.__name__}] process_record error: {e}; record={record}")

    @abc.abstractmethod
    def process_record(self, record):
        raise NotImplementedError()

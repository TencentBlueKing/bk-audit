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
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import TestCase

from services.web.risk.management.commands.gen_risk import AuditEventKafkaRecordConsumer
from services.web.risk.models import Risk
from services.web.strategy_v2.constants import StrategyStatusChoices
from services.web.strategy_v2.models import Strategy


class TestAuditEventKafkaRecordConsumer(TestCase):
    def _build_consumer(self):
        # Minimal dummy Kafka consumer placeholder; not used by these unit tests
        return object()

    @patch("services.web.risk.management.commands.gen_risk.RiskHandler.fetch_eligible_strategy_ids")
    def test_init_fetches_eligible_ids(self, mock_fetch):
        mock_fetch.return_value = {1, 2, 3}
        consumer = AuditEventKafkaRecordConsumer(
            consumer=self._build_consumer(), timeout_ms=1000, max_records=100, sleep_time=0.1
        )
        self.assertEqual(consumer.eligible_strategy_ids, {1, 2, 3})

    @patch("services.web.risk.management.commands.gen_risk.RiskHandler.generate_risk")
    @patch("services.web.risk.management.commands.gen_risk.RiskHandler.fetch_eligible_strategy_ids")
    def test_process_records_refreshes_and_processes(self, mock_fetch, mock_generate):
        # First call (during __init__) returns set A, second call (refresh) returns set B
        mock_fetch.side_effect = [{10}, {20}]
        consumer = AuditEventKafkaRecordConsumer(
            consumer=self._build_consumer(), timeout_ms=1000, max_records=100, sleep_time=0.1
        )
        # Prepare two fake records
        records = [SimpleNamespace(value={"event": 1}), SimpleNamespace(value={"event": 2})]
        consumer.process_records(records)

        # After refresh, eligible ids should be updated to second value
        self.assertEqual(consumer.eligible_strategy_ids, {20})
        # And generate_risk called with each record value and refreshed eligible set
        mock_generate.assert_any_call({"event": 1}, {20})
        mock_generate.assert_any_call({"event": 2}, {20})
        self.assertEqual(mock_generate.call_count, 2)

    @patch("services.web.risk.management.commands.gen_risk.RiskHandler.generate_risk")
    def test_process_record_forwards_to_handler(self, mock_generate):
        consumer = AuditEventKafkaRecordConsumer(
            consumer=self._build_consumer(), timeout_ms=1000, max_records=100, sleep_time=0.1
        )
        consumer.eligible_strategy_ids = {99}
        record = SimpleNamespace(value={"hello": "world"})
        consumer.process_record(record)
        mock_generate.assert_called_once_with({"hello": "world"}, {99})

    @patch("services.web.risk.tasks.process_risk_ticket")
    @patch("services.web.risk.handlers.risk.RiskHandler.send_risk_notice")
    @patch("core.connection.ping_db")
    def test_process_creates_risk(self, mock_ping_db, mock_send_notice, mock_process_ticket):
        # Prepare strategies: one running, one disabled
        Strategy.objects.create(strategy_id=201, status=StrategyStatusChoices.RUNNING.value)
        Strategy.objects.create(strategy_id=202, status=StrategyStatusChoices.DISABLED.value)

        now_ms = int(datetime.datetime.now().timestamp() * 1000)

        event_ok = {
            "strategy_id": 201,
            "raw_event_id": "k-001",
            "event_time": now_ms,
            "event_data": {},
            "event_evidence": "[]",
        }
        event_skip = {
            "strategy_id": 202,
            "raw_event_id": "k-002",
            "event_time": now_ms,
            "event_data": {},
            "event_evidence": "[]",
        }

        # Mock KafkaConsumer.poll to return our records then empty to exit
        records_batch = [SimpleNamespace(value=event_ok), SimpleNamespace(value=event_skip)]
        mock_consumer = MagicMock()
        mock_consumer.poll.side_effect = [{"tp": records_batch}, {}]

        consumer = AuditEventKafkaRecordConsumer(
            consumer=mock_consumer, timeout_ms=1000, max_records=100, sleep_time=0.01, sleep_wait=False
        )

        self.assertEqual(Risk.objects.count(), 0)
        consumer.process()  # should process our two records and then exit

        # Only the running strategy event should create a risk
        self.assertEqual(Risk.objects.filter(strategy_id=201, raw_event_id="k-001").count(), 1)
        self.assertEqual(Risk.objects.filter(strategy_id=202, raw_event_id="k-002").count(), 0)

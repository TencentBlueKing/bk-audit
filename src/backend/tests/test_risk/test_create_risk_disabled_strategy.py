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
import threading
from unittest import mock

from django.db import connections
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature

from services.web.risk.handlers.risk import RiskHandler
from services.web.risk.models import Risk, RiskPersonIndex
from services.web.scene.constants import ResourceVisibilityType
from services.web.scene.models import ResourceBinding
from services.web.strategy_v2.constants import RiskLevel, StrategyStatusChoices
from services.web.strategy_v2.models import Strategy


class TestCreateRiskWithStrategyStatus(TestCase):
    def setUp(self):
        # Common timestamps
        self.now_ms = int(datetime.datetime.now().timestamp() * 1000)

    def test_skip_when_strategy_disabled(self):
        # Prepare a disabled strategy
        Strategy.objects.create(strategy_id=101, status=StrategyStatusChoices.DISABLED.value)

        event = {
            "strategy_id": 101,
            "raw_event_id": "raw-001",
            "event_time": self.now_ms,
            "event_data": {},
            "event_evidence": "[]",
        }

        eligible = RiskHandler.fetch_eligible_strategy_ids()
        created, risk = RiskHandler().create_risk(event, eligible)

        self.assertFalse(created)
        self.assertIsNone(risk)
        self.assertEqual(Risk.objects.count(), 0)

    def test_create_when_strategy_running(self):
        # Prepare a running strategy
        Strategy.objects.create(
            strategy_id=102,
            status=StrategyStatusChoices.RUNNING.value,
            risk_level=RiskLevel.HIGH.value,
        )

        event = {
            "strategy_id": 102,
            "raw_event_id": "raw-002",
            "event_time": self.now_ms,
            "event_data": {},
            "event_evidence": "[]",
        }

        eligible = RiskHandler.fetch_eligible_strategy_ids()
        created, risk = RiskHandler().create_risk(event, eligible)

        self.assertTrue(created)
        self.assertIsNotNone(risk)
        self.assertEqual(Risk.objects.filter(strategy_id=102, raw_event_id="raw-002").count(), 1)
        self.assertEqual(risk.risk_level, RiskLevel.HIGH.value)
        self.assertEqual(risk.risk_level_order, RiskLevel.order_value(RiskLevel.HIGH.value))
        self.assertFalse(
            ResourceBinding.objects.filter(
                resource_type=ResourceVisibilityType.RISK,
                resource_id=risk.risk_id,
            ).exists()
        )

    def test_gen_risk_create_params_includes_risk_level_snapshot(self):
        Strategy.objects.create(
            strategy_id=105,
            status=StrategyStatusChoices.RUNNING.value,
            risk_level=RiskLevel.HIGH.value,
        )
        event = {
            "strategy_id": 105,
            "raw_event_id": "raw-005",
            "event_time": self.now_ms,
            "event_data": {},
            "event_evidence": "[]",
        }
        create_params = RiskHandler().gen_risk_create_params(event)
        self.assertEqual(create_params["risk_level"], RiskLevel.HIGH.value)
        self.assertEqual(create_params["risk_level_order"], RiskLevel.order_value(RiskLevel.HIGH.value))

    def test_create_risk_syncs_operator_index(self):
        Strategy.objects.create(strategy_id=106, status=StrategyStatusChoices.RUNNING.value)
        event = {
            "strategy_id": 106,
            "raw_event_id": "raw-006",
            "event_time": self.now_ms,
            "event_data": {},
            "event_evidence": "[]",
            "operator": "operator-a,operator-b",
        }
        created, risk = RiskHandler().create_risk(event, RiskHandler.fetch_eligible_strategy_ids())
        self.assertTrue(created)

        users = set(
            RiskPersonIndex.objects.filter(
                risk_id=risk.risk_id,
                relation_type=RiskPersonIndex.RelationType.OPERATOR,
            ).values_list("user", flat=True)
        )
        self.assertEqual(users, {"operator-a", "operator-b"})

    def test_existing_risk_operator_change_syncs_operator_index(self):
        strategy = Strategy.objects.create(strategy_id=107, status=StrategyStatusChoices.RUNNING.value)
        existing = Risk.objects.create(
            strategy=strategy,
            raw_event_id="raw-007",
            event_time=datetime.datetime.fromtimestamp(self.now_ms / 1000),
            event_end_time=datetime.datetime.fromtimestamp(self.now_ms / 1000),
            event_data={},
            event_type=[],
            operator=["old-operator"],
        )
        RiskPersonIndex.sync_risk(existing)

        event = {
            "strategy_id": 107,
            "raw_event_id": "raw-007",
            "event_time": self.now_ms + 60_000,
            "event_data": {},
            "event_evidence": "[]",
            "operator": "new-operator",
        }
        created, risk = RiskHandler().create_risk(event, RiskHandler.fetch_eligible_strategy_ids())
        self.assertFalse(created)
        self.assertEqual(risk.risk_id, existing.risk_id)

        self.assertTrue(
            RiskPersonIndex.objects.filter(
                risk_id=risk.risk_id,
                relation_type=RiskPersonIndex.RelationType.OPERATOR,
                user="new-operator",
            ).exists()
        )
        self.assertTrue(
            RiskPersonIndex._objects.filter(
                risk_id=risk.risk_id,
                relation_type=RiskPersonIndex.RelationType.OPERATOR,
                user="old-operator",
                is_deleted=True,
            ).exists()
        )

    def test_existing_risk_operator_change_locks_exact_risk_before_sync(self):
        strategy = Strategy.objects.create(strategy_id=110, status=StrategyStatusChoices.RUNNING.value)
        existing = Risk.objects.create(
            strategy=strategy,
            raw_event_id="raw-110",
            event_time=datetime.datetime.fromtimestamp(self.now_ms / 1000),
            event_end_time=datetime.datetime.fromtimestamp(self.now_ms / 1000),
            event_data={},
            event_type=[],
            operator=["old-operator"],
        )
        event = {
            "strategy_id": 110,
            "raw_event_id": "raw-110",
            "event_time": self.now_ms + 60_000,
            "event_data": {},
            "event_evidence": "[]",
            "operator": "new-operator",
        }

        with (
            mock.patch.object(Risk.objects, "select_for_update", wraps=Risk.objects.select_for_update) as lock_risk,
            mock.patch.object(RiskPersonIndex, "sync_risk", return_value=None) as sync_risk,
        ):
            created, risk = RiskHandler().create_risk(event, RiskHandler.fetch_eligible_strategy_ids())

        self.assertFalse(created)
        self.assertEqual(risk.risk_id, existing.risk_id)
        lock_risk.assert_called_once()
        sync_risk.assert_called_once_with(
            risk,
            relation_types=[RiskPersonIndex.RelationType.OPERATOR],
        )

    def test_sync_risk_accepts_single_relation_type(self):
        strategy = Strategy.objects.create(strategy_id=108, status=StrategyStatusChoices.RUNNING.value)
        risk = Risk.objects.create(
            strategy=strategy,
            raw_event_id="raw-008",
            event_time=datetime.datetime.fromtimestamp(self.now_ms / 1000),
            event_end_time=datetime.datetime.fromtimestamp(self.now_ms / 1000),
            event_data={},
            event_type=[],
            operator=["old-operator"],
        )
        RiskPersonIndex.sync_risk(risk)

        risk.operator = ["new-operator"]
        risk.save(update_fields=["operator"])
        RiskPersonIndex.sync_risk(risk, RiskPersonIndex.RelationType.OPERATOR)

        self.assertTrue(
            RiskPersonIndex.objects.filter(
                risk_id=risk.risk_id,
                relation_type=RiskPersonIndex.RelationType.OPERATOR,
                user="new-operator",
            ).exists()
        )
        self.assertTrue(
            RiskPersonIndex._objects.filter(
                risk_id=risk.risk_id,
                relation_type=RiskPersonIndex.RelationType.OPERATOR,
                user="old-operator",
                is_deleted=True,
            ).exists()
        )

    def test_create_risk_does_not_lock_convergence_range_query(self):
        Strategy.objects.create(strategy_id=109, status=StrategyStatusChoices.RUNNING.value)
        event = {
            "strategy_id": 109,
            "raw_event_id": "raw-109",
            "event_time": self.now_ms,
            "event_data": {},
            "event_evidence": "[]",
        }

        with (
            mock.patch.object(RiskPersonIndex, "sync_risk", return_value=None),
            mock.patch.object(
                Risk.objects,
                "select_for_update",
                side_effect=AssertionError("create_risk should not use broad select_for_update"),
            ),
        ):
            created, risk = RiskHandler().create_risk(event, RiskHandler.fetch_eligible_strategy_ids())

        self.assertTrue(created)
        self.assertIsNotNone(risk)

    def test_existing_risk_not_updated_when_disabled(self):
        # Strategy disabled
        strategy = Strategy.objects.create(strategy_id=103, status=StrategyStatusChoices.DISABLED.value)

        # Create an existing risk for the same strategy/raw_event_id
        existing = Risk.objects.create(
            strategy=strategy,
            raw_event_id="raw-003",
            event_time=datetime.datetime.fromtimestamp(self.now_ms / 1000),
            event_end_time=datetime.datetime.fromtimestamp(self.now_ms / 1000),
            event_data={},
            event_type=[],
        )

        later_ms = self.now_ms + 60_000
        event = {
            "strategy_id": 103,
            "raw_event_id": "raw-003",
            "event_time": later_ms,
            "event_data": {},
            "event_evidence": "[]",
        }

        eligible = RiskHandler.fetch_eligible_strategy_ids()
        created, risk = RiskHandler().create_risk(event, eligible)

        # Should skip and not touch the existing risk
        self.assertFalse(created)
        self.assertIsNone(risk)

        existing.refresh_from_db()
        self.assertEqual(int(existing.event_end_time.timestamp()), int(self.now_ms / 1000))

    def test_existing_risk_event_data_updated_when_event_time_is_later(self):
        strategy = Strategy.objects.create(strategy_id=104, status=StrategyStatusChoices.RUNNING.value)
        existing = Risk.objects.create(
            strategy=strategy,
            raw_event_id="raw-004",
            event_time=datetime.datetime.fromtimestamp(self.now_ms / 1000),
            event_end_time=datetime.datetime.fromtimestamp(self.now_ms / 1000),
            event_data={"result": "old"},
            event_type=[],
        )

        later_ms = self.now_ms + 60_000
        event = {
            "strategy_id": 104,
            "raw_event_id": "raw-004",
            "event_time": later_ms,
            "event_data": {"result": "new"},
            "event_evidence": "[]",
        }

        eligible = RiskHandler.fetch_eligible_strategy_ids()
        created, risk = RiskHandler().create_risk(event, eligible)

        self.assertFalse(created)
        self.assertEqual(risk.risk_id, existing.risk_id)

        existing.refresh_from_db()
        self.assertEqual(int(existing.event_end_time.timestamp()), int(later_ms / 1000))
        self.assertEqual(existing.event_data, {"result": "new"})


@skipUnlessDBFeature("has_select_for_update")
class RiskOperatorConvergenceConcurrencyTest(TransactionTestCase):
    reset_sequences = True

    def test_concurrent_existing_risk_operator_updates_keep_index_consistent(self):
        now_ms = int(datetime.datetime.now().timestamp() * 1000)
        strategy = Strategy.objects.create(strategy_id=111, status=StrategyStatusChoices.RUNNING.value)
        risk = Risk.objects.create(
            strategy=strategy,
            raw_event_id="raw-111",
            event_time=datetime.datetime.fromtimestamp(now_ms / 1000),
            event_end_time=datetime.datetime.fromtimestamp(now_ms / 1000),
            event_data={},
            event_type=[],
            operator=["origin-operator"],
        )
        RiskPersonIndex.sync_risk(risk)
        eligible_strategy_ids = RiskHandler.fetch_eligible_strategy_ids()
        barrier = threading.Barrier(2)
        errors = []

        def update_operator(user: str, offset: int):
            connections.close_all()
            try:
                barrier.wait(timeout=5)
                event = {
                    "strategy_id": 111,
                    "raw_event_id": "raw-111",
                    "event_time": now_ms + offset,
                    "event_data": {},
                    "event_evidence": "[]",
                    "operator": user,
                }
                RiskHandler().create_risk(event, eligible_strategy_ids)
            except Exception as error:  # pragma: no cover - asserted below
                errors.append(error)
            finally:
                connections.close_all()

        threads = [
            threading.Thread(target=update_operator, args=("operator-a", 60_000)),
            threading.Thread(target=update_operator, args=("operator-b", 120_000)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(errors, [])
        risk.refresh_from_db()
        active_users = set(
            RiskPersonIndex.objects.filter(
                risk_id=risk.risk_id,
                relation_type=RiskPersonIndex.RelationType.OPERATOR,
            ).values_list("user", flat=True)
        )
        self.assertEqual(active_users, set(risk.operator))

# -*- coding: utf-8 -*-
"""
tests for manual risk event creation
"""
import datetime
from types import SimpleNamespace
from unittest import mock

from bk_resource import resource
from blueapps.core.celery import celery_app
from django.conf import settings
from django.core.cache.backends.locmem import LocMemCache
from django.test import TestCase
from django.utils import timezone
from rest_framework import serializers

import core.lock as lock_module
from services.web.risk.constants import RiskStatus
from services.web.risk.models import ManualEvent, Risk
from services.web.risk.tasks import manual_add_event
from services.web.strategy_v2.constants import StrategyType
from services.web.strategy_v2.models import Strategy


class CreateEventResourceTest(TestCase):
    def setUp(self):
        super().setUp()
        self.strategy = Strategy.objects.create(
            namespace=settings.DEFAULT_NAMESPACE, strategy_name="manual", strategy_type=StrategyType.RULE
        )
        now = timezone.now()
        self.risk = Risk.objects.create(
            risk_id="risk-manual",
            strategy=self.strategy,
            raw_event_id="risk-base",
            event_time=now - datetime.timedelta(hours=1),
            event_end_time=now + datetime.timedelta(hours=1),
            event_content="risk",
        )
        self.perm_patcher = mock.patch(
            "services.web.risk.permissions.GenerateStrategyRiskPermission.ensure_allowed", return_value=None
        )
        self.perm_patcher.start()
        self._orig_eager = celery_app.conf.task_always_eager
        self._orig_propagates = celery_app.conf.task_eager_propagates
        celery_app.conf.task_always_eager = True
        celery_app.conf.task_eager_propagates = True
        self._orig_lock_cache = lock_module.cache
        lock_module.cache = LocMemCache("risk-event-tests", {})

    def tearDown(self):
        lock_module.cache = self._orig_lock_cache
        celery_app.conf.task_always_eager = self._orig_eager
        celery_app.conf.task_eager_propagates = self._orig_propagates
        self.perm_patcher.stop()
        super().tearDown()

    def _build_request(self, username, is_superuser=False):
        return SimpleNamespace(
            user=SimpleNamespace(username=username, is_authenticated=True, is_superuser=is_superuser),
            COOKIES={},
        )

    def test_create_event_uses_manual_task(self):
        event_payload = {
            "event_content": "content",
            "raw_event_id": "raw-1",
            "strategy_id": self.strategy.strategy_id,
            "event_data": {"foo": "bar"},
            "event_time": int(datetime.datetime.now().timestamp() * 1000),
            "event_evidence": "[]",
            "event_type": "login",
            "event_source": "api",
            "operator": "user1",
        }
        request = self._build_request(username="super", is_superuser=True)
        with mock.patch("services.web.risk.tasks.process_risk_ticket"):
            response = resource.risk.create_event(events=[event_payload], gen_risk=True, _request=request)
        self.assertEqual(len(response["event_ids"]), 1)
        self.assertTrue(
            ManualEvent.objects.filter(raw_event_id="raw-1", strategy_id=self.strategy.strategy_id).exists()
        )
        self.assertTrue(Risk.objects.filter(raw_event_id="raw-1", strategy_id=self.strategy.strategy_id).exists())

    def test_create_event_without_gen_risk(self):
        event_payload = {
            "event_content": "content",
            "raw_event_id": "raw-no-risk",
            "strategy_id": self.strategy.strategy_id,
            "event_data": {"foo": "bar"},
            "event_time": int(timezone.now().timestamp() * 1000),
            "event_evidence": "[]",
            "event_type": "login",
            "event_source": "api",
            "operator": "user1",
        }
        request = self._build_request(username="super", is_superuser=True)
        with mock.patch("services.web.risk.tasks.process_risk_ticket"):
            response = resource.risk.create_event(
                events=[event_payload], gen_risk=False, risk_id=self.risk.risk_id, _request=request
            )
        self.assertEqual(len(response["event_ids"]), 1)
        self.assertTrue(
            ManualEvent.objects.filter(
                raw_event_id=self.risk.raw_event_id, strategy_id=self.strategy.strategy_id
            ).exists()
        )
        self.assertFalse(
            ManualEvent.objects.filter(raw_event_id="raw-no-risk", strategy_id=self.strategy.strategy_id).exists()
        )
        self.assertFalse(Risk.objects.filter(raw_event_id="raw-no-risk").exists())

    def test_create_event_without_gen_risk_invalid_time(self):
        self.risk.status = RiskStatus.CLOSED
        self.risk.event_end_time = self.risk.event_time + datetime.timedelta(minutes=5)
        self.risk.save(update_fields=["status", "event_end_time"])
        request = self._build_request(username="super", is_superuser=True)
        event_payload = {
            "event_content": "content",
            "raw_event_id": "raw-invalid",
            "strategy_id": self.strategy.strategy_id,
            "event_data": {"foo": "bar"},
            "event_time": int((self.risk.event_end_time + datetime.timedelta(hours=1)).timestamp() * 1000),
            "event_evidence": "[]",
            "event_type": "login",
            "event_source": "api",
            "operator": "user1",
        }
        with mock.patch("services.web.risk.tasks.process_risk_ticket"):
            with self.assertRaises(serializers.ValidationError):
                resource.risk.create_event(
                    events=[event_payload], gen_risk=False, risk_id=self.risk.risk_id, _request=request
                )

    def test_create_event_without_gen_risk_requires_risk_id(self):
        request = self._build_request(username="super", is_superuser=True)
        event_payload = {
            "event_content": "content",
            "raw_event_id": "raw-missing-risk",
            "strategy_id": self.strategy.strategy_id,
            "event_data": {"foo": "bar"},
            "event_time": int(timezone.now().timestamp() * 1000),
            "event_evidence": "[]",
            "event_type": "login",
            "event_source": "api",
            "operator": "user1",
        }
        with mock.patch("services.web.risk.tasks.process_risk_ticket"):
            with self.assertRaises(serializers.ValidationError):
                resource.risk.create_event(events=[event_payload], gen_risk=False, _request=request)

    def test_create_event_with_owner_request(self):
        self.strategy.created_by = "owner"
        self.strategy.updated_by = "owner"
        self.strategy.save(update_fields=["created_by", "updated_by"])
        request = self._build_request(username="owner", is_superuser=False)
        event_payload = {
            "event_content": "content",
            "raw_event_id": "raw-owner",
            "strategy_id": self.strategy.strategy_id,
            "event_data": {"foo": "bar"},
            "event_time": int(datetime.datetime.now().timestamp() * 1000),
            "event_evidence": "[]",
            "event_type": "login",
            "event_source": "api",
            "operator": "user1",
        }
        with mock.patch("services.web.risk.tasks.process_risk_ticket"):
            response = resource.risk.create_event(events=[event_payload], gen_risk=True, _request=request)
        self.assertEqual(len(response["event_ids"]), 1)
        self.assertTrue(
            ManualEvent.objects.filter(raw_event_id="raw-owner", strategy_id=self.strategy.strategy_id).exists()
        )
        self.assertTrue(Risk.objects.filter(raw_event_id="raw-owner").exists())

    def test_manual_event_maps_basic_config(self):
        strategy = Strategy.objects.create(
            namespace=settings.DEFAULT_NAMESPACE,
            strategy_name="manual-map",
            strategy_type=StrategyType.RULE,
            event_basic_field_configs=[
                {"field_name": "raw_event_id", "display_name": "raw", "map_config": {"source_field": "原始事件ID"}},
                {"field_name": "event_content", "display_name": "content", "map_config": {"source_field": "事件描述"}},
                {"field_name": "event_type", "display_name": "type", "map_config": {"source_field": "事件类型"}},
                {
                    "field_name": "event_source",
                    "display_name": "source",
                    "map_config": {"target_value": "manual-source"},
                },
                {"field_name": "operator", "display_name": "operator", "map_config": {"source_field": "责任人"}},
            ],
        )
        event_payload = {
            "strategy_id": strategy.strategy_id,
            "event_data": {
                "原始事件ID": "mapped-raw",
                "事件描述": "mapped content",
                "事件类型": "a;b",
                "责任人": "alice,bob",
            },
            "event_time": int(datetime.datetime.now().timestamp() * 1000),
        }
        request = self._build_request(username="super", is_superuser=True)
        with mock.patch("services.web.risk.tasks.process_risk_ticket"):
            response = resource.risk.create_event(events=[event_payload], gen_risk=True, _request=request)

        self.assertEqual(len(response.get("risk_ids", [])), 1)
        risk = Risk.objects.get(risk_id=response["risk_ids"][0])
        self.assertEqual(risk.event_content, "mapped content")
        self.assertEqual(risk.event_source, "manual-source")
        self.assertEqual(risk.event_type, ["a", "b"])
        self.assertEqual(risk.operator, ["alice", "bob"])


class ManualAddEventTaskTest(TestCase):
    def setUp(self):
        super().setUp()
        self.strategy = Strategy.objects.create(namespace=settings.DEFAULT_NAMESPACE, strategy_name="manual-task")

    def _build_event(self):
        return {
            "event_content": "manual event",
            "raw_event_id": "raw-manual",
            "strategy_id": self.strategy.strategy_id,
            "event_data": {"field": "value"},
            "event_time": int(datetime.datetime.now().timestamp() * 1000),
            "event_evidence": "[]",
            "event_type": "manual",
            "event_source": "manual",
            "operator": "ops",
        }

    def test_manual_add_event_persists_rows(self):
        manual_add_event([self._build_event()])
        manual_event = ManualEvent.objects.get()
        self.assertEqual(manual_event.raw_event_id, "raw-manual")
        self.assertEqual(manual_event.strategy_id, self.strategy.strategy_id)
        self.assertEqual(manual_event.event_type, "manual")
        self.assertEqual(manual_event.event_data.get("field"), "value")
        self.assertIsNotNone(manual_event.event_time.tzinfo)

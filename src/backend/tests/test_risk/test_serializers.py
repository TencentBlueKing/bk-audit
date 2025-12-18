# -*- coding: utf-8 -*-
"""
risk serializers 单测
"""
from datetime import datetime
from types import SimpleNamespace

from django.utils import timezone

from services.web.risk.serializers import (
    CreateRiskSerializer,
    ListEventResponseSerializer,
)
from tests.base import TestCase


class RiskSerializersTest(TestCase):
    def test_create_risk_serializer_parses_event_data(self):
        data = {
            "strategy_id": 1,
            "event_data": '{"foo": "bar"}',
            "dtEventTimeStamp": 1700000000000,
        }
        serializer = CreateRiskSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["event_data"], {"foo": "bar"})
        self.assertEqual(serializer.validated_data["event_time"], data["dtEventTimeStamp"])

    def test_list_event_response_serializer_rounds_microseconds(self):
        serializer = ListEventResponseSerializer()
        dt = timezone.make_aware(datetime(2024, 1, 1, 12, 0, 0, 500000))
        value = serializer.get_event_end_time(SimpleNamespace(event_end_time=dt))
        self.assertEqual(value, "2024-01-01 12:00:01")

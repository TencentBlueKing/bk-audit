# -*- coding: utf-8 -*-
from bk_resource import resource
from django.conf import settings
from django.test import TestCase
from django.utils import timezone

from services.web.risk.models import Risk
from services.web.strategy_v2.constants import StrategyType
from services.web.strategy_v2.models import Strategy


class MergeSelectFieldTypeExposeTests(TestCase):
    def setUp(self):
        self.strategy = Strategy.objects.create(
            namespace=settings.DEFAULT_NAMESPACE,
            strategy_name="merge-select-type",
            strategy_type=StrategyType.MODEL,
            event_data_field_configs=[
                {
                    "field_name": "Foo Field",
                    "display_name": "Foo Field",
                    "is_priority": False,
                    "is_show": True,
                    "duplicate_field": False,
                },
                {
                    "field_name": "Bar Field",
                    "display_name": "Bar Field",
                    "is_priority": False,
                    "is_show": True,
                    "duplicate_field": False,
                },
            ],
            configs={
                "select": [
                    {"raw_name": "foo", "display_name": "Foo Field", "field_type": "string"},
                    {"raw_name": "bar", "display_name": "Bar Field", "field_type": "long"},
                ]
            },
        )
        self.risk = Risk.objects.create(
            risk_id="risk-merge",
            strategy=self.strategy,
            raw_event_id="raw-merge",
            event_time=timezone.now(),
            event_end_time=timezone.now(),
        )

    def test_list_strategy_exposes_field_type(self):
        resp = resource.strategy_v2.list_strategy(namespace=settings.DEFAULT_NAMESPACE)
        item = next(s for s in resp if s["strategy_id"] == self.strategy.strategy_id)
        field_dict = {f["field_name"]: f for f in item["event_data_field_configs"]}
        self.assertEqual(field_dict["Foo Field"]["field_type"], "string")
        self.assertEqual(field_dict["Bar Field"]["field_type"], "long")

    def test_risk_strategy_info_exposes_field_type(self):
        resp = resource.risk.retrieve_risk_strategy_info(risk_id=self.risk.risk_id)
        field_dict = {f["field_name"]: f for f in resp["event_data_field_configs"]}
        self.assertEqual(field_dict["Foo Field"]["field_type"], "string")
        self.assertEqual(field_dict["Bar Field"]["field_type"], "long")

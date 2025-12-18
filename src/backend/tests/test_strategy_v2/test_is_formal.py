# -*- coding: utf-8 -*-
"""
Unit tests for Strategy.is_formal field exposure and defaults.
"""

import copy
from unittest import mock

from bk_resource import resource
from django.conf import settings

from services.web.analyze.models import Control, ControlVersion
from services.web.strategy_v2.constants import RiskLevel
from services.web.strategy_v2.models import Strategy
from tests.base import TestCase
from tests.test_strategy_v2.constants import (
    BKM_CONTROL_DATA,
    BKM_CONTROL_VERSION_DATA,
    BKM_STRATEGY_DATA,
)


class TestStrategyIsFormal(TestCase):
    def setUp(self) -> None:  # NOCC:invalid-name(单元测试)
        # Prepare a control/version for creating strategy via resource
        self.control = Control.objects.create(**BKM_CONTROL_DATA)
        self.control_version = ControlVersion.objects.create(
            **{**BKM_CONTROL_VERSION_DATA, "control_id": self.control.control_id}
        )

    @mock.patch("services.web.analyze.controls.bkm.api.bk_monitor.save_alarm_strategy", mock.Mock(return_value={}))
    def test_list_strategy_contains_is_formal_default_true(self) -> None:
        # Create a strategy via resource (is_formal should be default True)
        params = copy.deepcopy(BKM_STRATEGY_DATA)
        params.update(
            {
                "control_id": self.control_version.control_id,
                "control_version": self.control_version.control_version,
                "risk_level": RiskLevel.HIGH.value,
                "risk_hazard": "",
                "risk_guidance": "",
                "risk_title": "risk title",
                "processor_groups": ["123"],
            }
        )
        created = resource.strategy_v2.create_strategy(**params)

        # List strategies and ensure is_formal in response and True
        result = resource.strategy_v2.list_strategy(namespace=settings.DEFAULT_NAMESPACE)
        found = next((s for s in result if s["strategy_id"] == created["strategy_id"]), None)
        assert found is not None
        assert "is_formal" in found
        assert found["is_formal"] is True

    def test_list_strategy_contains_is_formal_false(self) -> None:
        # Manually create a non-formal strategy
        s = Strategy.objects.create(
            namespace=settings.DEFAULT_NAMESPACE,
            strategy_name="non-formal",
            is_formal=False,
        )
        # List strategies and ensure is_formal shows False
        result = resource.strategy_v2.list_strategy(namespace=settings.DEFAULT_NAMESPACE)
        found = next((item for item in result if item["strategy_id"] == s.strategy_id), None)
        assert found is not None
        assert found["is_formal"] is False

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

from unittest import TestCase

import pytest
from bk_resource import resource

from services.web.risk.models import ProcessApplication, Risk, RiskRule
from tests.test_risk.test_tickets.constants import PA_INFO, RISK_INFO, RULE_INFO


@pytest.mark.django_db
class TicketTest(TestCase):
    ...


class RiskContext:
    def __init__(self, risk_info: dict = None):
        Risk.objects.all().delete()
        risk_info = risk_info or {}
        self.risk = Risk.objects.create(**{**RISK_INFO, **risk_info})

    def __enter__(self) -> Risk:
        return self.risk

    def __exit__(self, exc_type, exc_value, traceback):
        self.risk.delete()


class RuleContext:
    def __init__(self, pa_info: dict = None, rule_info: dict = None):
        ProcessApplication.objects.all().delete()
        RiskRule.objects.all().delete()
        pa_info = pa_info or {}
        self.pa = resource.risk.create_process_application.perform_request({**PA_INFO, **pa_info})
        rule_info = rule_info or {}
        self.rule = resource.risk.create_risk_rule.perform_request({**RULE_INFO, **rule_info, "pa_id": self.pa.id})
        self.rule.is_enabled = True
        self.rule.save()

    def __enter__(self) -> (ProcessApplication, RiskRule):
        return self.pa, self.rule

    def __exit__(self, exc_type, exc_value, traceback):
        self.pa.delete()
        self.rule.delete()

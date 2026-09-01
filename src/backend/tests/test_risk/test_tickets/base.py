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
from uuid import uuid4

import pytest
from bk_resource import resource

from services.web.risk.models import ProcessApplication, Risk, RiskRule
from services.web.scene.models import Scene
from tests.test_risk.test_tickets.constants import PA_INFO, RISK_INFO, RULE_INFO


@pytest.mark.django_db
class TicketTest(TestCase):
    databases = {"default"}

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # 修复测试数据库表结构，确保必填字段有默认值
        from django.db import OperationalError, connection

        try:
            cursor = connection.cursor()
            cursor.execute("ALTER TABLE strategy_v2_strategy MODIFY COLUMN report_enabled BOOLEAN DEFAULT FALSE")
            cursor.execute("ALTER TABLE strategy_v2_strategy MODIFY COLUMN report_auto_render BOOLEAN DEFAULT TRUE")
        except OperationalError:
            pass  # 可能已经修复过了


class RiskContext:
    def __init__(self, risk_info: dict = None):
        Risk.objects.all().delete()
        risk_info = risk_info or {}
        # 确保策略存在
        strategy_id = risk_info.get("strategy_id", RISK_INFO.get("strategy_id"))
        if strategy_id:
            from services.web.strategy_v2.models import Strategy

            # 使用 bulk_create with ignore_conflicts 避免主键冲突和字段默认值问题
            Strategy.objects.bulk_create(
                [
                    Strategy(
                        strategy_id=strategy_id,
                        namespace="test",
                        strategy_name=f"test_strategy_{strategy_id}",
                        report_auto_render=True,
                        report_enabled=False,
                        is_formal=True,
                        source="user",
                        status="starting",
                        strategy_type="model",
                    )
                ],
                ignore_conflicts=True,
            )
        self.risk = Risk.objects.create(**{**RISK_INFO, **risk_info})

    def __enter__(self) -> Risk:
        return self.risk

    def __exit__(self, exc_type, exc_value, traceback):
        self.risk.delete()


class RuleContext:
    def __init__(self, pa_info: dict = None, rule_info: dict = None):
        ProcessApplication.objects.all().delete()
        RiskRule.objects.all().delete()
        # 创建独立场景用于 ResourceBinding，避免测试间场景名冲突
        self.scene = Scene.objects.create(name=f"test_risk_scene_{uuid4().hex}", description="test")
        pa_info = pa_info or {}
        self.pa = resource.risk.create_process_application.perform_request(
            {**PA_INFO, "scene_id": self.scene.scene_id, **pa_info}
        )
        rule_info = rule_info or {}
        self.rule = resource.risk.create_risk_rule.perform_request(
            {**RULE_INFO, "scene_id": self.scene.scene_id, **rule_info, "pa_id": self.pa.id}
        )
        self.rule.is_enabled = True
        self.rule.save()

    def __enter__(self) -> (ProcessApplication, RiskRule):
        return self.pa, self.rule

    def __exit__(self, exc_type, exc_value, traceback):
        self.pa.delete()
        self.rule.delete()
        self.scene.delete()

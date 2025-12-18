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

from core.exceptions import RiskRuleNotMatch
from services.web.risk.constants import RiskRuleOperator
from services.web.risk.models import Risk, RiskRule


class RiskRuleHandler:
    """
    风险处理规则
    """

    def __init__(self, risk_id: str):
        self.risk = Risk.objects.get(risk_id=risk_id)
        # 仅使用启用的规则用于匹配
        self.rules = RiskRule.load_latest_rules().filter(is_enabled=True).order_by("-priority_index")

    def bind_rule(self) -> None:
        """
        为风险绑定处理规则
        """

        try:
            rule = self.match_rule()
            self.risk.rule_id, self.risk.rule_version = rule.rule_id, rule.version
            self.risk.save(update_fields=["rule_id", "rule_version"])
        except RiskRuleNotMatch:
            pass

    def match_rule(self) -> RiskRule:
        """
        获取风险处理规则
        """

        for r in self.rules:
            q = RiskRuleOperator.build_query_filter(r.scope)
            if Risk.objects.filter(risk_id=self.risk.risk_id).filter(q).exists():
                return r
        raise RiskRuleNotMatch(message=RiskRuleNotMatch.MESSAGE % self.risk.risk_id)

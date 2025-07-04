# -*- coding: utf-8 -*-

from iam.contrib.converter.queryset import PathEqDjangoQuerySetConverter
from iam.eval.constants import KEYWORD_BK_IAM_PATH


def risk_path_value_hook(value):
    # get id in "/strategy,1/"
    return value[1:-1].split(",")[1]


class RiskPathEqDjangoQuerySetConverter(PathEqDjangoQuerySetConverter):
    def __init__(self):
        key_mapping = {
            "risk.id": "risk_id",
            "risk.risk_id": "risk_id",
            f"risk.{KEYWORD_BK_IAM_PATH}": "strategy_id",
        }
        super().__init__(key_mapping, {"strategy_id": risk_path_value_hook})

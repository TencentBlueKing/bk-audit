# -*- coding: utf-8 -*-

from iam.contrib.converter.queryset import PathEqDjangoQuerySetConverter


def risk_path_value_hook(value):
    # get id in "/strategy,1/"
    return value[1:-1].split(",")[1]


class RiskPathEqDjangoQuerySetConverter(PathEqDjangoQuerySetConverter):
    def __init__(self):
        key_mapping = {
            "risk.id": "risk_id",
            "risk.risk_id": "risk_id",
            "risk._bk_iam_path_": "strategy_id",
        }
        super().__init__(key_mapping, {"strategy_id": risk_path_value_hook})

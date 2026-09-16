# -*- coding: utf-8 -*-

import operator
from functools import reduce

from django.db.models import Q
from iam.contrib.converter.queryset import PathEqDjangoQuerySetConverter
from iam.eval.constants import KEYWORD_BK_IAM_PATH, OP

# IAM 路径中场景前缀标识
_SCENE_PATH_PREFIX = "/scene,"


def _parse_resource_id(value: str) -> str:
    """从 IAM path 值中提取 resource_id

    支持格式：'/scene,100001/' → '100001', '/strategy,123/' → '123'
    """
    return value[1:-1].split(",")[1]


class RiskPathEqDjangoQuerySetConverter(PathEqDjangoQuerySetConverter):
    """Risk 的 IAM 策略 → Django Q 转换器

    支持两种 IAM 路径：
    - /scene,{scene_id}/  → 通过策略绑定反查 strategy_id__in
    - /strategy,{strategy_id}/  → 直接匹配 strategy_id（兼容旧路径）
    """

    def __init__(self):
        key_mapping = {
            "risk.id": "risk_id",
            "risk.risk_id": "risk_id",
        }
        super().__init__(key_mapping)

    def convert(self, data):
        """重写 convert，拦截 _bk_iam_path_ 路径做场景/策略分发处理"""
        op = data.get("op")

        # 非叶子节点（AND/OR），走默认递归
        if op in (OP.AND, OP.OR):
            return super().convert(data)

        field = data.get("field", "")
        value = data.get("value", "")

        # 仅对 _bk_iam_path_ 字段做特殊处理
        if field == f"risk.{KEYWORD_BK_IAM_PATH}":
            return self._convert_path(value)

        # 其他字段走默认流程
        return super().convert(data)

    def _convert_path(self, value) -> Q:
        """根据路径值判断是场景路径还是策略路径，返回对应的 Q 对象"""
        if isinstance(value, (list, tuple)):
            if not value:
                return Q(pk__in=[])
            return reduce(operator.or_, [self._convert_path(v) for v in value])

        if value.startswith(_SCENE_PATH_PREFIX):
            # /scene,{scene_id}/ → 风险场景归属已固化到 Risk.scene_id，直接按模型字段过滤
            scene_id = _parse_resource_id(value)
            try:
                scene_id_int = int(scene_id)
            except (TypeError, ValueError):
                return Q(pk__in=[])
            return Q(scene_id=scene_id_int)

        # 兼容旧路径：/strategy,{strategy_id}/
        strategy_id = _parse_resource_id(value)
        try:
            return Q(strategy_id=int(strategy_id))
        except (TypeError, ValueError):
            return Q(strategy_id=strategy_id)

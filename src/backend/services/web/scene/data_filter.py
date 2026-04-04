# -*- coding: utf-8 -*-
"""
数据过滤规则引擎

根据场景配置生成对应的 Django ORM 查询条件。
本阶段仅实现规则引擎本身，暂不集成到检索、策略等业务功能中。
"""
from typing import Any, Dict, List, Optional

from django.db.models import Q

from services.web.scene.models import SceneDataTable, SceneSystem


class SceneDataFilter:
    """
    场景数据过滤规则引擎

    根据场景关联的系统/数据表及其过滤规则，生成 Django ORM Q 对象。
    """

    OPERATORS = {
        "=": lambda field, value: Q(**{field: value}),
        "!=": lambda field, value: ~Q(**{field: value}),
        "in": lambda field, value: Q(**{f"{field}__in": _parse_list_value(value)}),
        "not_in": lambda field, value: ~Q(**{f"{field}__in": _parse_list_value(value)}),
        "contains": lambda field, value: Q(**{f"{field}__contains": value}),
        "gt": lambda field, value: Q(**{f"{field}__gt": value}),
        "gte": lambda field, value: Q(**{f"{field}__gte": value}),
        "lt": lambda field, value: Q(**{f"{field}__lt": value}),
        "lte": lambda field, value: Q(**{f"{field}__lte": value}),
    }

    @classmethod
    def build_filter(cls, scene_id: int) -> Q:
        """
        根据场景构建数据过滤条件（Django ORM Q 对象）

        :param scene_id: 场景 ID
        :return: Q 对象，可直接用于 queryset.filter()
        """
        q = Q()

        # 处理系统级过滤规则
        scene_systems = SceneSystem.objects.filter(scene_id=scene_id)
        for scene_system in scene_systems:
            if scene_system.is_all_systems:
                continue
            system_q = cls._build_rules_q(scene_system.filter_rules)
            if system_q:
                q &= system_q

        # 处理数据表级过滤规则
        scene_tables = SceneDataTable.objects.filter(scene_id=scene_id)
        for scene_table in scene_tables:
            table_q = cls._build_rules_q(scene_table.filter_rules)
            if table_q:
                q &= table_q

        return q

    @classmethod
    def _build_rules_q(cls, rules: List[Dict[str, Any]]) -> Optional[Q]:
        """
        将过滤规则列表转换为 Q 对象

        :param rules: 过滤规则列表，格式:
            [{"field": "xxx", "operator": "=", "value": "yyy"}, ...]
        :return: Q 对象或 None
        """
        if not rules:
            return None

        q = Q()
        for rule in rules:
            field = rule.get("field", "")
            operator = rule.get("operator", "=")
            value = rule.get("value", "")

            builder = cls.OPERATORS.get(operator)
            if builder and field:
                q &= builder(field, value)

        return q if q else None

    @classmethod
    def get_system_ids(cls, scene_id: int) -> List[str]:
        """
        获取场景关联的系统 ID 列表

        :param scene_id: 场景 ID
        :return: 系统 ID 列表
        """
        scene_systems = SceneSystem.objects.filter(scene_id=scene_id)

        # 如果有 is_all_systems=True 的记录，返回空列表表示不限制
        if scene_systems.filter(is_all_systems=True).exists():
            return []

        return list(scene_systems.values_list("system_id", flat=True))

    @classmethod
    def get_table_ids(cls, scene_id: int) -> List[str]:
        """
        获取场景关联的数据表 ID 列表

        :param scene_id: 场景 ID
        :return: 数据表 ID 列表
        """
        return list(SceneDataTable.objects.filter(scene_id=scene_id).values_list("table_id", flat=True))


def _parse_list_value(value: Any) -> List[str]:
    """
    将值解析为列表

    支持逗号分隔的字符串或已经是列表的情况。
    """
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    return [str(value)]

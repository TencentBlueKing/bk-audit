# -*- coding: utf-8 -*-
"""
调用方资源权限判定的统一入口。

当前支持：
- risk：当携带 caller_resource_type=risk 与 caller_resource_id 时，校验用户是否有风险查看权限；
  通过则允许跳过原有工具/报表权限校验。

后续如有新增类型，请按策略注册方式扩展。
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping as _Mapping
from contextlib import suppress
from enum import Enum
from functools import singledispatch
from typing import Any, Dict, List, Optional, Tuple, Type

from bk_resource import resource
from blueapps.utils.logger import logger

from apps.permission.handlers.actions import ActionEnum
from apps.permission.handlers.resource_types import ResourceEnum
from core.exceptions import PermissionException
from services.web.common.constants import CallerResourceType


class BaseCallerPermission:
    """调用方资源权限判定策略抽象类"""

    def has_permission(self, instance_id: str, username: str, **kwargs) -> bool:  # pragma: no cover - 简单封装
        raise NotImplementedError


class RiskCallerPermission(BaseCallerPermission):
    def has_permission(self, instance_id: str, username: str, **kwargs) -> bool:
        from services.web.risk.permissions import RiskViewPermission

        current_type = kwargs.get("current_type")
        current_object_id = kwargs.get("current_object_id")
        caller_validated = kwargs.get("caller_validated")
        # 1) 先校验风险查看权限（失败会抛出权限异常，成功继续）
        if not caller_validated:
            perm = RiskViewPermission(actions=[ActionEnum.LIST_RISK], resource_meta=ResourceEnum.RISK)
            perm.has_risk_permission(instance_id, username)
        # 2) 基于 current_type+current_object_id/extra_context 做关系校验
        if current_type and current_object_id:
            return self.extra_context_validate(current_type, current_object_id, instance_id, kwargs)
        return True

    def extra_context_validate(self, current_type, current_object_id, instance_id, kwargs):
        # 如果存在current_type但current_type异常则检验不通过
        try:
            ct = CurrentType(current_type)
        except ValueError:
            return False
        if ct == CurrentType.STRATEGY:
            return is_risk_related_to_strategy(instance_id, current_object_id)
        if ct == CurrentType.TOOL:
            # 先校验工具与风险所属策略是否建立关联
            if not is_tool_related_to_risk(instance_id, current_object_id):
                return False
            # 如调用方传入了工具变量值，则基于策略字段 drill_config 与风险事件进行值校验
            tool_variable_items = kwargs.get("tool_variables") or []
            variable_values = {item["raw_name"]: item["value"] for item in tool_variable_items}
            drill_field = kwargs.get("drill_field")
            event_start_time = kwargs.get("event_start_time")
            event_end_time = kwargs.get("event_end_time")
            if variable_values:
                return validate_tool_variables_with_risk(
                    risk_id=instance_id,
                    tool_uid=current_object_id,
                    variable_values=variable_values,
                    drill_field=drill_field,
                    start_time=event_start_time,
                    end_time=event_end_time,
                )
            return True


# 权限处理器注册表：resource_type -> 权限处理器
# 受支持的调用者资源类型


CALLER_RESOURCE_TYPE_CHOICES = tuple((i.value, i.value) for i in CallerResourceType)

_CALLER_PERMISSIONS: Dict[str, Type[BaseCallerPermission]] = {
    CallerResourceType.RISK.value: RiskCallerPermission,
}


class CurrentType(str, Enum):
    """当前对象类型（用于调用方上下文关联判断）"""

    STRATEGY = "strategy"
    TOOL = "tool"


CURRENT_TYPE_CHOICES = tuple((i.value, i.value) for i in CurrentType)


def should_skip_permission(
    caller_resource_type: Optional[str],
    caller_resource_id: Optional[str],
    username: str,
    raise_exception: bool = True,
    **kwargs,
) -> bool:
    """
    依据调用方资源上下文判断是否跳过原有权限校验。

    返回：
      - True：已验证调用方资源权限，通过，允许跳过后续原有权限校验；
      - False：未命中或不支持该类型，走原有权限校验。
    """

    if not caller_resource_type or not caller_resource_id:
        return False

    rtype = str(caller_resource_type).lower()
    permission_handler = _CALLER_PERMISSIONS.get(rtype)
    if permission_handler and permission_handler().has_permission(caller_resource_id, username, **kwargs):
        return True
    elif raise_exception:
        raise PermissionException(f'使用{caller_resource_type}:{caller_resource_id}', '?')
    else:
        return False


def extract_caller_context(source: Any) -> Tuple[Optional[str], Optional[str]]:
    """从 dict 或 request 中提取 caller_resource_type 与 caller_resource_id"""
    crt = None
    cri = None

    if isinstance(source, _Mapping):
        crt = source.get("caller_resource_type")
        cri = source.get("caller_resource_id")
        return crt, cri
    for attr in ("data", "query_params"):
        if hasattr(source, attr):
            with suppress(Exception):
                crt = crt or getattr(source, attr).get("caller_resource_type")
                cri = cri or getattr(source, attr).get("caller_resource_id")
    return crt, cri


def extract_extra_variables(source: Any) -> Dict[str, Any]:
    """
    从 dict 或 request 中提取额外上下文参数，形成动态 kwargs。
    当前支持：
      - current_type：如 "strategy" / "tool"
      - current_object_id：如策略ID/工具UID
      - tool_variable：当 current_type=tool 且调用方传入了执行变量时，提取变量名->值映射
      - event_start_time：当 current_type=tool 且调用方传入了执行变量时，提取事件开始时间
      - event_end_time：当 current_type=tool 且调用方传入了执行变量时，提取事件结束时间
      - drill_field：当 current_type=tool 时，指定应使用的字段 drill_config
    """
    extra: Dict[str, Any] = {}

    def _collect(mapping: _Mapping):
        for variable in (
                "current_type",
                "current_object_id",
                "event_start_time",
                "event_end_time",
                "drill_field",
                "tool_variables",
                "caller_validated",
        ):
            extra[variable] = mapping.get(variable)

    if isinstance(source, _Mapping):
        _collect(source)
    else:
        for attr in ("data", "query_params"):
            if hasattr(source, attr):
                _collect(getattr(source, attr))
    return extra


def is_tool_related_to_risk(risk_id: str, tool_uid: str) -> bool:
    """
    校验指定风险的策略是否关联给定工具。
    返回 True 表示存在关联，False 表示不存在或无法定位。
    """
    from services.web.risk.models import Risk
    from services.web.strategy_v2.models import StrategyTool

    strategy_id = Risk.objects.filter(risk_id=risk_id).values_list("strategy_id", flat=True).first()
    if not strategy_id:
        return False
    return StrategyTool.objects.filter(strategy_id=strategy_id, tool_uid=tool_uid).exists()


@singledispatch
def collection_to_tuple(collection: Any) -> Tuple[Any, ...]:
    return collection


@collection_to_tuple.register
def _dict_to_tuple(iterable: dict) -> Tuple[tuple, ...]:
    return tuple(iterable.items())


@collection_to_tuple.register
def _list_to_tuple(iterable: list) -> Tuple[str, ...]:
    return tuple(iterable)


def validate_tool_variables_with_risk(
        risk_id: str,
        tool_uid: str,
        variable_values: Dict[str, Any],
        drill_field: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
) -> bool:
    """
    基于策略字段 drill_config(DrillConfig) 与风险 event_data，对工具执行变量进行值校验：
      - FIXED_VALUE：变量值必须等于配置的 target_value
      - FIELD：变量值必须等于 event_data 中的 target_value (basic和非basic处理逻辑不同，详见具体逻辑)
    仅对在 mapping（由 drill_config 针对该 tool 建立的映射）中声明的变量进行校验；
    未在 mapping 中声明的变量不参与校验。
    若风险/策略不可用、字段值校验失败，返回 False。
    """
    from services.web.risk.models import Risk
    from services.web.strategy_v2.constants import StrategyFieldSourceEnum
    from services.web.tool.constants import TargetValueTypeEnum

    if not start_time or not end_time or not drill_field:
        return False

    risk = Risk.objects.filter(risk_id=risk_id).only("strategy_id", "event_data").first()
    if not risk or not risk.strategy_id:
        return False

    event_record = _get_risk_event_record(risk, start_time, end_time)
    uncheck_field, mapping = _collect_check_rules(risk, tool_uid, drill_field)

    for name, value in variable_values.items():
        if name in uncheck_field:
            continue
        rules = mapping.get(name)
        # 若变量未在 mapping 中声明，则跳过校验
        if not rules:
            continue
        # 逐个规则进行校验
        match_result = []
        for rule in rules:
            if rule["type"] == TargetValueTypeEnum.FIXED_VALUE.value:
                if rule["target"] in (None, ""):
                    match_result.append(True)
                    continue
                if value != rule["target"]:
                    match_result.append(False)
                    continue
            elif rule["type"] == TargetValueTypeEnum.FIELD.value:
                # 根据 target_field_type 决定取顶层事件字段还是嵌套的 event_data 字段
                tft = (rule.get("target_field_type") or "").lower()
                if tft == StrategyFieldSourceEnum.BASIC.value:
                    expected = event_record.get(rule["target"])
                else:
                    expected = event_record.get("event_data", {}).get(rule["target"])
                value_to_match = collection_to_tuple(value)
                single_value = (
                    value_to_match[0] if (isinstance(value_to_match, tuple) and len(value_to_match) == 1) else None
                )
                combined_expected = {','.join(str(per) for per in item) for item in expected if isinstance(item, tuple)}
                if not expected or (
                    (value_to_match not in expected)
                    and (value_to_match not in combined_expected)
                    and (single_value not in expected if single_value else True)
                ):
                    match_result.append(False)
                    continue
            match_result.append(True)
        if not any(match_result):
            return False
    return True


def _collect_check_rules(risk, tool_uid: str, drill_field: Optional[str] = None):
    """生成检查规则"""
    from services.web.strategy_v2.models import Strategy
    from services.web.tool.constants import FieldCategory
    from services.web.tool.models import Tool

    strategy = (
        Strategy.objects.filter(strategy_id=risk.strategy_id)
        .only("event_basic_field_configs", "event_data_field_configs", "event_evidence_field_configs")
        .first()
    )
    if not strategy:
        return set(), {}

    # 某些字段类型不检查值，比如时间范围选择器常会有NOW等非具体值
    uncheck_field = set()

    tool = Tool.last_version_tool(tool_uid)
    cfg = (tool.config if tool else {}) or {}
    for item in cfg.get("input_variable") or []:
        name = (item or {}).get("raw_name")
        ftype = (item or {}).get("field_category")
        if ftype in [FieldCategory.TIME_RANGE_SELECT, FieldCategory.TIME_SELECT]:
            uncheck_field.add(name)

    # 收集所有字段的 drill_config 中与 tool_uid 匹配的映射（source_field -> (type, target, source_field_type)）
    def iter_field_configs() -> list[dict]:
        cfgs = []
        for key in ("event_basic_field_configs", "event_data_field_configs", "event_evidence_field_configs"):
            fields = getattr(strategy, key) or []
            if drill_field:
                fields = [f for f in fields if (f or {}).get("field_name") == drill_field]
            cfgs.extend(fields)
        return cfgs

    mapping: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for field_cfg in iter_field_configs():
        drill_list = (field_cfg or {}).get("drill_config") or []
        for drill in drill_list:
            tool = (drill or {}).get("tool") or {}
            if not tool or tool.get("uid") != tool_uid:
                continue
            for item in drill.get("config") or []:
                src = item.get("source_field")
                tv_type = item.get("target_value_type")
                target_value = item.get("target_value")
                target_field_type = item.get("target_field_type")
                if not src or not tv_type:
                    continue
                mapping[src].append({"type": tv_type, "target": target_value, "target_field_type": target_field_type})
    # 返回顺序需与调用方保持一致：(uncheck_field, mapping)
    return uncheck_field, mapping


def _get_risk_event_record(risk, start_time, end_time) -> Dict[str, Any]:
    """获取风险事件记录"""
    risk_id = risk.risk_id
    # 获取事件数据：通过接口按时间范围获取
    event_record: Dict[str, Any] = defaultdict(set, **{"event_data": defaultdict(set)})
    events = []
    try:
        events = resource.risk.list_event(
            start_time=start_time, end_time=end_time, risk_id=risk_id, page=1, page_size=100
        ).get("results", [])
    except Exception as e:
        logger.exception("Failed to get event data", exc_info=e)
    if not events:
        events = [risk.event_data]
    for event in events:
        for k, v in event.pop("event_data", {}).items():
            event_record["event_data"][k].add(collection_to_tuple(v))
        for k, v in event.items():
            event_record[k].add(collection_to_tuple(v))
    return event_record


def is_risk_related_to_strategy(risk_id: str, strategy_id: Any) -> bool:
    """
    校验指定风险是否归属于给定策略。
    - True：归属；False：不归属或无法定位
    """
    from services.web.risk.models import Risk

    try:
        sid = int(strategy_id)
    except ValueError:
        return False
    return Risk.objects.filter(risk_id=risk_id, strategy_id=sid).exists()


def should_skip_permission_from(source: Any, username: str) -> bool:
    """
    根据调用方上下文判断是否跳过原始权限校验，使用上下文权限进行判断。
    """
    crt, cri = extract_caller_context(source)
    extras = extract_extra_variables(source)
    return should_skip_permission(crt, cri, username, **extras)

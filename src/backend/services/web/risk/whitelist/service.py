# -*- coding: utf-8 -*-
"""白名单创建、ITSM 审批回写、到期和命中拦截。"""

import datetime
import json
import logging
import re
import uuid
from concurrent.futures import ThreadPoolExecutor

from bk_resource import api
from dateutil.relativedelta import relativedelta
from django.db import transaction
from django.db.models import Case, IntegerField, Q, Value, When
from django.utils import timezone
from django.utils.translation import gettext
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.settings import api_settings

from apps.permission.handlers.actions import ActionEnum
from apps.permission.handlers.permission import Permission
from core.models import get_request_username
from core.serializers import FriendlyDateTimeField
from core.utils.time import mstimestamp_to_date_string
from services.web.common.constants import ScopeType
from services.web.common.scope_permission import ScopeContext, ScopePermission
from services.web.risk.constants import RiskStatus, TicketNodeStatus
from services.web.risk.whitelist.constants import (
    FLOW_STATUS,
    RISK_WHITELIST_CALLBACK_URL,
    RISK_WHITELIST_WORKFLOW_KEY,
    WHITELIST_NODE_ACTION,
    HitAction,
    WhitelistStatus,
    WhitelistType,
)
from services.web.risk.whitelist.match import (
    append_risk_match_fields,
    format_scope_readable,
    match_scope,
    scope_field_names,
    validate_match_scope,
)
from services.web.risk.whitelist.models import RiskWhitelist, RiskWhitelistHit
from services.web.scene.constants import ITSMV4TicketStatus
from services.web.scene.models import Scene
from services.web.scene.permission import (
    _extract_reject_reason_from_logs,
    parse_itsm_ticket,
)

logger = logging.getLogger(__name__)

# 冒险加白未传天数时的默认值，对应原来的一个月。
DEFAULT_ACCEPTANCE_DAYS = 30


def is_platform_admin(username: str) -> bool:
    """平台管理员看 IAM 的平台管理权限。这个权限不能通过、驳回，可以编辑、启停和删除。"""

    if not username:
        return False
    return Permission(username=username).has_action_any_permission(ActionEnum.MANAGE_PLATFORM)


def is_scene_admin(username: str, scene_id: int) -> bool:
    """场景管理员是该场景 managers 里的人。平台管理员不在名单里不能立即通过，也不能通过、驳回。"""

    if not username or not scene_id:
        return False
    return username in _scene_admin_usernames(scene_id)


def managed_scene_ids(username: str):
    """返回 IAM 里有管理场景权限的场景。"""

    return ScopePermission(username).get_scene_ids(ScopeContext(ScopeType.CROSS_SCENE), ActionEnum.MANAGE_SCENE)


_PERIOD_PATTERN = re.compile(r"^(\d+)([dDmM])$")


def _period_value(text: str):
    """7d 为天数，1m 为整月。对不上返回 None。"""

    matched = _PERIOD_PATTERN.fullmatch(text)
    if not matched:
        return None
    count = int(matched.group(1))
    if count < 1:
        raise ValidationError(gettext("有效期必须大于 0"))
    if matched.group(2).lower() == "d":
        return count
    return ("month", count)


def coerce_duration_days(value):
    """整数或 Nd 是有效天数，Nm 是整月，permanent 永久，custom 另传到期时间。空值返回 None。"""

    if value in (None, ""):
        return None
    if isinstance(value, bool):
        raise ValidationError(gettext("有效天数必须是大于 0 的整数、整月或到期时间"))
    if isinstance(value, datetime.datetime):
        return value
    if isinstance(value, tuple) and value[:1] == ("month",):
        return value
    if isinstance(value, int):
        if value < 1:
            raise ValidationError(gettext("有效天数必须是大于 0 的整数"))
        return value
    text = str(value).strip()
    if text.lower() == "permanent":
        return "permanent"
    if text.lower() == "custom":
        return "custom"
    period = _period_value(text)
    if period is not None:
        return period
    if text.isdigit():
        days = int(text)
        if days < 1:
            raise ValidationError(gettext("有效天数必须是大于 0 的整数"))
        return days
    parsed = None
    if _looks_like_local_dt(text):
        try:
            parsed = datetime.datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            parsed = None
    if parsed is None:
        from django.utils.dateparse import parse_datetime

        parsed = parse_datetime(text)
    if parsed is None:
        raise ValidationError(gettext("有效天数必须是大于 0 的整数或到期时间"))
    return parsed


def _looks_like_local_dt(text: str) -> bool:
    return len(text) == 19 and text[10] == " "


def resolve_duration(whitelist_type: str, duration_days=None) -> tuple:
    """返回 (是否永久, 天数)。未传时误报加白默认永久，冒险加白默认 30 天。"""

    has_days = duration_days not in (None, "")
    if not has_days:
        if whitelist_type == WhitelistType.FALSE_POSITIVE:
            return True, None
        return False, DEFAULT_ACCEPTANCE_DAYS
    try:
        days = int(duration_days)
    except (TypeError, ValueError):
        raise ValidationError(gettext("有效天数必须是大于 0 的整数"))
    if days < 1:
        raise ValidationError(gettext("有效天数必须是大于 0 的整数"))
    return False, days


def resolve_expire_at(whitelist_type: str, duration_days=None, expire_at=None, base=None):
    """返回 (是否永久, 到期时间)。permanent 为永久，custom 直接存 expire_at，整数加天数，Nm 加整月。"""

    duration_days = coerce_duration_days(duration_days)
    if duration_days == "permanent":
        if whitelist_type == WhitelistType.RISK_ACCEPTANCE:
            raise ValidationError(gettext("冒险加白需要填写有效天数"))
        return True, None
    if duration_days == "custom":
        if expire_at in (None, ""):
            raise ValidationError(gettext("自定义有效期需要填写到期时间"))
        if not isinstance(expire_at, datetime.datetime):
            expire_at = serializers.DateTimeField().to_internal_value(expire_at)
        if expire_at <= timezone.now():
            raise ValidationError(gettext("到期时间必须晚于当前时间"))
        return False, expire_at.replace(microsecond=0)
    if isinstance(duration_days, datetime.datetime):
        if duration_days <= timezone.now():
            raise ValidationError(gettext("到期时间必须晚于当前时间"))
        return False, duration_days.replace(microsecond=0)
    if isinstance(duration_days, tuple) and duration_days[:1] == ("month",):
        return False, expire_at_from_months(duration_days[1], base)
    permanent, days = resolve_duration(whitelist_type, duration_days)
    return permanent, expire_at_from(permanent, days, base)


def expire_at_from_months(months: int, base=None):
    base = base or timezone.now()
    return (base + relativedelta(months=int(months))).replace(microsecond=0)


def expire_at_from(is_permanent: bool, duration_days, base=None):
    base = base or timezone.now()
    if is_permanent:
        return None
    return (base + datetime.timedelta(days=int(duration_days or 0))).replace(microsecond=0)


def _format_dt(value) -> str:
    """和风险列表一样：转到默认时区后按 DATETIME_FORMAT 输出。"""

    if not value:
        return ""
    return FriendlyDateTimeField().to_representation(value) or ""


def format_snapshot_value(key: str, value):
    """命中事件里的 event_time 是毫秒时间戳，展示时转成日期时间。"""

    if key not in {"event_time", "dtEventTimeStamp"} or isinstance(value, bool) or not isinstance(value, (int, float)):
        return value
    try:
        return mstimestamp_to_date_string(int(value))
    except (OverflowError, OSError, ValueError):
        return value


def build_hit_event_fields(snapshot: dict) -> list:
    """field 保留原字段名，field_name 用策略事件字段配置里的中文名。"""

    from services.web.strategy_v2.models import Strategy
    from services.web.strategy_v2.resources import GetEventFieldsConfig

    snapshot = snapshot or {}
    strategy_id = snapshot.get("strategy_id")
    lookup = int(strategy_id) if isinstance(strategy_id, str) and strategy_id.isdigit() else strategy_id
    strategy = Strategy.objects.filter(strategy_id=lookup).first() if lookup not in (None, "") else None
    reader = GetEventFieldsConfig()
    configured = [
        *reader.get_event_basic_field_configs(None, False),
        *reader.get_event_data_field_configs(strategy, None, False),
        *reader.get_event_evidence_field_configs(strategy, None, False),
    ]
    names = {item["field_name"]: item["display_name"] for item in configured if item.get("display_name")}
    fields = []
    for key, value in snapshot.items():
        shown = format_snapshot_value(key, value)
        fields.append(
            {
                "field": key,
                "field_name": names.get(key) or key,
                "field_type": type(shown).__name__,
                "field_value": ""
                if shown is None
                else shown
                if isinstance(shown, str)
                else json.dumps(shown, ensure_ascii=False),
            }
        )
    return fields


def _format_expire(value) -> str:
    return _format_dt(value)


def validity_text(rule: RiskWhitelist) -> str:
    if not rule.expire_at:
        return "永久"
    return _format_expire(rule.expire_at)


def _kept(ticket: dict, previous: dict, key: str):
    """工单这次没带回的字段，沿用节点上一次的值。"""

    if key in (ticket or {}):
        return (ticket or {}).get(key) or []
    return (previous or {}).get(key) or []


def _node_status(ticket: dict) -> tuple:
    """节点和白名单用同一套工单结果。回调带回结果时一起改成待审批、生效中或已驳回。"""

    mapped, display = map_whitelist_status(ticket)
    return mapped, display, ticket.get("approve_result")


def _node_payload(rule: RiskWhitelist, ticket: dict = None, previous: dict = None) -> dict:
    """节点上保留申请内容和 ITSM 单。申请状态取本次工单结果，处理人、当前步骤取工单返回。"""

    ticket = ticket or {}
    previous = previous or {}
    status, status_display, approved = _node_status(ticket)
    return {
        "rule_id": str(rule.id or ""),
        "match_scope": rule.match_scope,
        "applicant": rule.created_by or "",
        "whitelist_type": rule.whitelist_type,
        "validity_text": validity_text(rule),
        "reason": rule.reason,
        "submitted_at": submitted_at_of(rule),
        "itsm_ticket_id": str(ticket.get("id") or rule.itsm_ticket_id or ""),
        "itsm_sn": ticket.get("sn") or rule.itsm_sn or "",
        "itsm_url": ticket.get("frontend_url") or rule.itsm_ticket_url or "",
        "itsm_status": status,
        "itsm_status_display": status_display,
        "approve_result": approved,
        "current_processors": _kept(ticket, previous, "current_processors"),
        "current_steps": _kept(ticket, previous, "current_steps"),
    }


def _raw_ticket_status(ticket: dict) -> str:
    """工单状态统一成小写。回调里可能是 FINISHED，或包在对象里。"""

    raw = (ticket or {}).get("status")
    if raw in (None, ""):
        raw = (ticket or {}).get("current_status")
    if isinstance(raw, dict):
        raw = raw.get("key") or raw.get("id") or raw.get("value") or raw.get("status") or ""
    return str(raw or "").strip().lower()


def _is_approved(ticket: dict) -> bool:
    """和场景权限一样，直接用工单里的 approve_result，缺省当未通过。"""

    return bool((ticket or {}).get("approve_result", False))


def map_whitelist_status(ticket: dict) -> tuple:
    """ITSMV4TicketStatus 映射到白名单状态。和场景申请的 ApplicationStatus 同一层。

    finished 且通过 → 生效中；finished 未通过或 termination → 已驳回；running 或没有结果 → 待审批。
    """

    status = _raw_ticket_status(ticket)
    if status == ITSMV4TicketStatus.FINISHED and _is_approved(ticket):
        mapped = WhitelistStatus.ACTIVE
    elif status in {ITSMV4TicketStatus.FINISHED, ITSMV4TicketStatus.TERMINATION}:
        mapped = WhitelistStatus.REJECTED
    else:
        mapped = WhitelistStatus.PENDING
    return mapped, str(WhitelistStatus(mapped).label)


def _ticket_process_result(rule: RiskWhitelist, ticket: dict) -> dict:
    """处理记录只留工单入口。审批状态只放在 whitelist 上，避免和 extra 各写一份。"""

    ticket = ticket or {}
    return {
        "ticket": {
            "id": str(ticket.get("id") or rule.itsm_ticket_id or ""),
            "sn": ticket.get("sn") or rule.itsm_sn or "",
            "frontend_url": ticket.get("frontend_url") or rule.itsm_ticket_url or "",
            "rule_id": str(rule.id or ""),
        }
    }


def _ticket_on_rule(rule: RiskWhitelist) -> dict:
    """节点上的工单。"""

    ticket = {
        "id": rule.itsm_ticket_id or "",
        "sn": rule.itsm_sn or "",
        "frontend_url": rule.itsm_ticket_url or "",
    }
    if rule.status == WhitelistStatus.ACTIVE:
        ticket["status"] = ITSMV4TicketStatus.FINISHED
        ticket["approve_result"] = True
    elif rule.status == WhitelistStatus.REJECTED:
        ticket["status"] = ITSMV4TicketStatus.FINISHED
        ticket["approve_result"] = False
    return ticket


def _node_ticket(rule: RiskWhitelist, ticket: dict = None) -> dict:
    """和创建白名单写节点一样，申请状态以白名单当前状态为准。回调只补处理人、步骤和意见。"""

    stored = _ticket_on_rule(rule)
    incoming = ticket or {}
    for key in ("sn", "frontend_url"):
        if not stored.get(key) and incoming.get(key):
            stored[key] = incoming[key]
    for key in ("current_processors", "current_steps", "comment"):
        if key in incoming:
            stored[key] = incoming[key]
    return stored


def write_whitelist_nodes(rule: RiskWhitelist, risks) -> None:
    """工单创建完成后再写风险节点。申请状态直接用白名单上已经写下的状态。"""

    now = datetime.datetime.now()
    with transaction.atomic():
        current = RiskWhitelist.objects.select_for_update().get(pk=rule.pk)
        ticket = _node_ticket(current)
        payload = {"whitelist": _node_payload(current, ticket)}
        process_result = _ticket_process_result(current, ticket)
        _insert_whitelist_nodes(current, risks, now, payload, process_result)


def _insert_whitelist_nodes(rule: RiskWhitelist, risks, now, payload: dict, process_result: dict) -> None:
    for risk in risks:
        from services.web.risk.models import TicketNode

        TicketNode.objects.create(
            risk_id=risk.risk_id,
            operator=rule.created_by or "",
            current_operator=risk.current_operator or [],
            action=WHITELIST_NODE_ACTION,
            timestamp=now.timestamp(),
            time=now.strftime(api_settings.DATETIME_FORMAT),
            process_result=process_result,
            extra=payload,
            status=TicketNodeStatus.FINISHED,
        )


def refresh_whitelist_nodes(rule: RiskWhitelist, ticket: dict = None) -> None:
    from services.web.risk.models import TicketNode

    # 回调用内存里的旧对象时，以库里的白名单状态为准，避免把已经生效中的节点写回待审批。
    if isinstance(rule, RiskWhitelist):
        current = RiskWhitelist.objects.filter(pk=rule.pk).first()
        if current is not None:
            rule = current
    if not rule.risk_id:
        return
    ticket = _node_ticket(rule, ticket)
    nodes = TicketNode.objects.filter(risk_id=rule.risk_id, action=WHITELIST_NODE_ACTION)
    for node in nodes:
        if not _node_belongs_to_rule(node, rule):
            continue
        previous = (node.process_result or {}).get("ticket") or {}
        process_result = _ticket_process_result(rule, ticket)
        node.extra = {"whitelist": _node_payload(rule, ticket, previous)}
        node.process_result = process_result
        node.save(update_fields=["extra", "process_result"])


def _node_belongs_to_rule(node, rule: RiskWhitelist) -> bool:
    """同一条白名单的节点才回写。旧节点没写 rule_id 时，用工单号为空或相同来认。"""

    whitelist = (node.extra or {}).get("whitelist") or {}
    current = whitelist.get("rule_id")
    if current not in (None, ""):
        return str(current) == str(rule.id)
    stored_ticket = str(whitelist.get("itsm_ticket_id") or "")
    if stored_ticket and rule.itsm_ticket_id and stored_ticket != str(rule.itsm_ticket_id):
        return False
    return True


def ensure_same_strategy_scene(risks) -> None:
    """批量加白必须同一策略、同一场景。"""

    if len(risks) <= 1:
        return
    if len({risk.strategy_id for risk in risks}) != 1:
        raise ValidationError(gettext("批量加白仅适用于同一审计策略"))
    if len({risk.scene_id for risk in risks}) != 1:
        raise ValidationError(gettext("批量加白仅适用于同一场景"))


def submit_whitelist(
    *,
    scene_id: int,
    match_scope: dict,
    whitelist_type: str,
    reason: str,
    duration_days=None,
    expire_at=None,
    risks,
    username: str,
):
    """创建白名单。单条和批量都补策略、原始事件。批量逐条创建，并要求同一策略、同一场景。"""

    risks = list(risks or [])
    if len(risks) > 1:
        ensure_same_strategy_scene(risks)
        return [
            _create_whitelist(
                scene_id=risk.scene_id,
                match_scope=append_risk_match_fields(
                    match_scope,
                    strategy_id=risk.strategy_id,
                    raw_event_id=risk.raw_event_id,
                ),
                whitelist_type=whitelist_type,
                reason=reason,
                duration_days=duration_days,
                expire_at=expire_at,
                risks=[risk],
                username=username,
            )
            for risk in risks
        ]
    if risks:
        risk = risks[0]
        match_scope = append_risk_match_fields(
            match_scope,
            strategy_id=risk.strategy_id,
            raw_event_id=risk.raw_event_id,
        )
        scene_id = risk.scene_id
    return _create_whitelist(
        scene_id=scene_id,
        match_scope=match_scope,
        whitelist_type=whitelist_type,
        reason=reason,
        duration_days=duration_days,
        expire_at=expire_at,
        risks=risks,
        username=username,
    )


def _create_whitelist(
    *,
    scene_id: int,
    match_scope: dict,
    whitelist_type: str,
    reason: str,
    duration_days=None,
    expire_at=None,
    risks,
    username: str,
):
    error = validate_match_scope(match_scope, whitelist_type)
    if error:
        raise ValidationError(gettext(error))
    if whitelist_type not in WhitelistType.values:
        raise ValidationError(gettext("不支持的加白类型"))
    if not reason:
        raise ValidationError(gettext("加白原因不能为空"))
    is_permanent, expire_at = resolve_expire_at(whitelist_type, duration_days, expire_at)
    if not Scene.objects.filter(pk=scene_id, is_deleted=False).exists():
        raise ValidationError(gettext("场景不存在"))

    rule = RiskWhitelist.objects.create(
        scene_id=scene_id,
        risk_id=risks[0].risk_id if len(risks) == 1 else "",
        whitelist_type=whitelist_type,
        match_scope=match_scope,
        reason=reason[:500],
        is_permanent=is_permanent,
        expire_at=expire_at,
        status=WhitelistStatus.PENDING,
        callback_token=uuid.uuid4().hex,
        created_by=username,
        updated_by=username,
    )
    create_itsm_ticket(rule.id)
    rule.refresh_from_db()
    # 白名单状态这里已经会是生效中。节点只读这个状态，不再另算一遍。
    if rule.status == WhitelistStatus.PENDING:
        _pass_if_admin(rule, username)
        rule.refresh_from_db()
    if risks and rule.itsm_ticket_id:
        write_whitelist_nodes(rule, risks)
    return rule


def operate_itsm(rule: RiskWhitelist, method: str, operator: str):
    if not rule.itsm_ticket_id:
        raise ValidationError(gettext("ITSM 工单尚未创建"))
    return api.bk_itsm_v4.ticket_handle(
        ticket_id=rule.itsm_ticket_id,
        action={"method": method, "params": {}},
        operator=operator,
        portal_id="DEFAULT",
        form_data={},
        options={},
    )


def review_whitelist(rule: RiskWhitelist, method: str, operator: str, reject_reason: str = "") -> RiskWhitelist:
    """场景管理员点击通过或驳回。ITSM 返回 success 为 true 才改状态，为 false 不改。"""

    ensure_admin(operator, rule.scene_id)
    payload = operate_itsm(rule, method, operator)
    if not (isinstance(payload, dict) and payload.get("success") is True):
        return rule
    approved = method == "approve"
    return apply_whitelist_result(
        rule,
        {
            "id": rule.itsm_ticket_id,
            "status": ITSMV4TicketStatus.FINISHED,
            "approve_result": approved,
            "comment": "" if approved else reject_reason,
        },
    )


def apply_whitelist_result(rule: RiskWhitelist, ticket: dict) -> RiskWhitelist:
    """终态才改状态。已经不是待审批时仍把当前状态回写到风险节点。"""

    status, _display = map_whitelist_status(ticket)
    comment = (ticket or {}).get("comment") or ""
    with transaction.atomic():
        current = RiskWhitelist.objects.select_for_update().get(pk=rule.pk)
        if current.status != WhitelistStatus.PENDING:
            refresh_whitelist_nodes(current, ticket)
            return current
        if status == WhitelistStatus.ACTIVE:
            current.status = WhitelistStatus.ACTIVE
            current.reject_reason = ""
        elif status == WhitelistStatus.REJECTED:
            current.status = WhitelistStatus.REJECTED
            current.reject_reason = comment or current.reject_reason
        else:
            current.refresh_from_db()
            refresh_whitelist_nodes(current, ticket)
            return current
        _save_rule(current, ["status", "reject_reason", "updated_at", "updated_by"])
    current.refresh_from_db()
    refresh_whitelist_nodes(current, ticket)
    if current.status == WhitelistStatus.ACTIVE:
        _close_source_risk(current)
    return current


def _close_source_risk(rule: RiskWhitelist) -> None:
    """审批通过后关闭来源风险单。已关单跳过，驳回不关。"""

    if not rule.risk_id:
        return
    from services.web.risk.constants import RiskStatus
    from services.web.risk.handlers.ticket import CloseRisk
    from services.web.risk.models import Risk

    risk = Risk.objects.filter(risk_id=rule.risk_id).first()
    if risk is None or risk.status == RiskStatus.CLOSED:
        return
    if risk.status == RiskStatus.PENDING_CONFIRM:
        risk.status = RiskStatus.AWAIT_PROCESS
        risk.save(update_fields=["status"])
    try:
        CloseRisk(risk_id=risk.risk_id, operator=rule.updated_by or rule.created_by or "").run(
            description=gettext("白名单审批通过，关闭风险单")
        )
    except Exception:
        logger.exception("[RiskWhitelist] close risk failed, rule=%s risk=%s", rule.id, rule.risk_id)


def _abort_whitelist(rule: RiskWhitelist) -> None:
    from services.web.risk.models import TicketNode

    if rule.risk_id:
        nodes = TicketNode.objects.filter(risk_id=rule.risk_id, action=WHITELIST_NODE_ACTION)
        for node in nodes:
            current = ((node.extra or {}).get("whitelist") or {}).get("rule_id")
            if str(current) == str(rule.id):
                node.delete()
    rule.delete()


def _usernames(values) -> list:
    if not isinstance(values, (list, tuple)):
        return []
    names = []
    for item in values:
        username = str(item or "").strip()
        if username and username not in names:
            names.append(username)
    return names


def _scene_admin_usernames(scene_id) -> list:
    """审批人里的场景管理员直接取该场景的 managers。"""

    try:
        scene = Scene.objects.filter(pk=scene_id, is_deleted=False).first()
    except Exception:
        logger.exception("[RiskWhitelist] load scene admins failed, scene_id=%s", scene_id)
        return []
    if scene is None:
        return []
    return _usernames(getattr(scene, "managers", None))


def _whitelist_approvers(scene_id) -> list:
    """审批人只取该场景的场景管理员。"""

    return _scene_admin_usernames(scene_id)


def _submit_itsm_ticket(rule: RiskWhitelist, *, operator: str, callback_token: str, reason=None, match_scope=None):
    """提交 ITSM 工单。"""

    workflow_key = RISK_WHITELIST_WORKFLOW_KEY
    if not workflow_key:
        logger.error("[RiskWhitelist] 未配置itsm, id=%s", rule.id)
        raise ValidationError(gettext("ITSM 审批流程未配置"))
    scope = rule.match_scope if match_scope is None else match_scope
    form_data = {
        "ticket__title": "【审计中心】风险白名单",
        "scene_id": str(rule.scene_id),
        "whitelist_type": rule.whitelist_type,
        "reason": rule.reason if reason is None else reason,
        # 审批单里给人看的匹配范围，条件树太长放不下，压成一行可读文本
        "match_scope": format_scope_readable(scope),
        "risk_id": rule.risk_id,
        "applicant": operator or rule.created_by or "",
        "approver": _whitelist_approvers(rule.scene_id),
    }
    try:
        ticket = api.bk_itsm_v4.ticket_create(
            operator=operator or rule.created_by or "",
            workflow_key=workflow_key,
            form_data=form_data,
            is_submit=True,
            callback_url=RISK_WHITELIST_CALLBACK_URL,
            callback_token=callback_token,
            portal="DEFAULT",
        )
    except Exception as exc:
        logger.exception("[RiskWhitelist] ticket_create failed, id=%s", rule.id)
        raise ValidationError(gettext("ITSM 工单创建失败")) from exc
    if not str((ticket or {}).get("id") or ""):
        raise ValidationError(gettext("ITSM 工单创建失败"))
    return ticket or {}


def _bind_ticket(rule: RiskWhitelist, ticket: dict) -> None:
    rule.itsm_ticket_id = str(ticket.get("id") or "")
    rule.itsm_sn = ticket.get("sn") or ""
    rule.itsm_ticket_url = ticket.get("frontend_url") or ""


def submitted_at_of(rule: RiskWhitelist) -> str:

    # 续期重建单据会把 updated_at 推到创建时间之后；纯创建（含建单失败）两者一致
    created_at = getattr(rule, "created_at", None)
    updated_at = getattr(rule, "updated_at", None)
    if updated_at and created_at and updated_at > created_at:
        return _format_dt(updated_at)
    return _format_dt(created_at)


def _pass_if_admin(rule: RiskWhitelist, username: str) -> None:
    """场景管理员创建后直接写成生效中。先尝试审批工单；回调若已写入终态则保持。"""

    if not username or not is_scene_admin(username, rule.scene_id):
        return
    try:
        operate_itsm(rule, "approve", username)
    except Exception:
        logger.exception("[RiskWhitelist] admin approve failed, id=%s", rule.id)
    if hasattr(rule, "refresh_from_db"):
        rule.refresh_from_db()
    if getattr(rule, "status", WhitelistStatus.PENDING) != WhitelistStatus.PENDING:
        return
    apply_whitelist_result(
        rule,
        {
            "id": rule.itsm_ticket_id,
            "status": ITSMV4TicketStatus.FINISHED,
            "approve_result": True,
        },
    )
    if hasattr(rule, "refresh_from_db"):
        rule.refresh_from_db()


def _renew_snapshot(rule: RiskWhitelist) -> dict:
    return {
        "status": rule.status,
        "whitelist_type": rule.whitelist_type,
        "callback_token": rule.callback_token,
        "reject_reason": rule.reject_reason,
        "itsm_ticket_id": rule.itsm_ticket_id,
        "itsm_sn": rule.itsm_sn,
        "itsm_ticket_url": rule.itsm_ticket_url,
        "updated_by": getattr(rule, "updated_by", "") or "",
    }


def _restore_renew_snapshot(rule: RiskWhitelist, previous: dict) -> None:
    for key, value in previous.items():
        setattr(rule, key, value)
    _save_rule(rule, [*previous.keys(), "updated_at"])


def _save_rule(rule: RiskWhitelist, fields) -> None:
    """按字段保存白名单。回调、Celery 等入口没有登录用户时，把 updated_by 排除出 update_fields，
    UPDATE 不含该列，从而保住实例加载时携带的原更新人，避免基类把它写成空。"""

    fields = set(fields)
    if not get_request_username():
        fields.add("updated_by")
    rule.save(update_fields=list(fields))


def renew_whitelist(
    rule: RiskWhitelist,
    *,
    match_scope,
    reason,
    duration_days,
    expire_at,
    username: str,
    whitelist_type: str = None,
) -> RiskWhitelist:
    """续期或更换加白方式都不新建白名单。先改成待审批再提工单，和创建一样让回调或管理员审批立刻生效。创建失败恢复原状态和原类型。"""

    if rule.status not in {WhitelistStatus.ACTIVE, WhitelistStatus.EXPIRED, WhitelistStatus.DISABLED}:
        raise ValidationError(gettext("只有生效中或已到期的规则可以续期"))
    target_type = whitelist_type or rule.whitelist_type
    if target_type not in WhitelistType.values:
        raise ValidationError(gettext("不支持的加白类型"))
    error = validate_match_scope(match_scope, target_type)
    if error:
        raise ValidationError(gettext(error))
    is_permanent, resolved_expire = resolve_expire_at(target_type, duration_days, expire_at)
    previous = _renew_snapshot(rule)
    callback_token = uuid.uuid4().hex
    # 创建是先落待审批和 token 再提工单，回调才能在返回前写成生效中。续期同样先腾出待审批，并清掉旧单号，避免轮询把旧工单当成这次结果。
    rule.status = WhitelistStatus.PENDING
    rule.whitelist_type = target_type
    rule.reject_reason = ""
    rule.callback_token = callback_token
    rule.itsm_ticket_id = ""
    rule.itsm_sn = ""
    rule.itsm_ticket_url = ""
    rule.updated_by = username
    _save_rule(
        rule,
        [
            "status",
            "whitelist_type",
            "reject_reason",
            "callback_token",
            "itsm_ticket_id",
            "itsm_sn",
            "itsm_ticket_url",
            "updated_at",
            "updated_by",
        ],
    )
    try:
        ticket = _submit_itsm_ticket(
            rule,
            operator=username,
            callback_token=callback_token,
            reason=reason,
            match_scope=match_scope,
        )
    except ValidationError:
        _restore_renew_snapshot(rule, previous)
        raise
    rule.refresh_from_db()
    rule.whitelist_type = target_type
    rule.match_scope = match_scope
    rule.reason = (reason or "")[:500]
    rule.is_permanent = is_permanent
    rule.expire_at = resolved_expire
    _bind_ticket(rule, ticket)
    rule.updated_by = username
    # 不回写 status。回调若已写成生效中，这里再写待审批会把它盖掉。
    _save_rule(
        rule,
        [
            "whitelist_type",
            "match_scope",
            "reason",
            "is_permanent",
            "expire_at",
            "callback_token",
            "itsm_ticket_id",
            "itsm_sn",
            "itsm_ticket_url",
            "updated_at",
            "updated_by",
        ],
    )
    refresh_whitelist_nodes(rule, ticket)
    if rule.status == WhitelistStatus.PENDING:
        _pass_if_admin(rule, username)
    rule.refresh_from_db()
    return rule


def create_itsm_ticket(rule_id: int) -> None:
    rule = RiskWhitelist.objects.filter(pk=rule_id).first()
    if rule is None or rule.itsm_ticket_id:
        return
    try:
        ticket = _submit_itsm_ticket(rule, operator=rule.created_by or "", callback_token=rule.callback_token)
    except ValidationError:
        _abort_whitelist(rule)
        raise
    _bind_ticket(rule, ticket)
    _save_rule(rule, ["itsm_ticket_id", "itsm_sn", "itsm_ticket_url", "updated_at", "updated_by"])
    rule.refresh_from_db()
    # 节点要等调用方按这里的状态插入。这时刷节点还找不到记录。


def sync_pending_whitelists(limit: int = 50) -> None:
    """回调没有写成终态时，查待审批记录的工单日志，按日志结果更新状态。"""

    rules = list(
        RiskWhitelist.objects.filter(status=WhitelistStatus.PENDING)
        .exclude(itsm_ticket_id="")
        .order_by("-updated_at", "-id")[:limit]
    )
    for rule in rules:
        try:
            refresh_pending_whitelist(rule)
        except Exception:
            logger.exception("[RiskWhitelist] poll failed, id=%s", rule.id)


def refresh_pending_whitelist(rule: RiskWhitelist) -> dict:
    """待审批记录查工单日志。已通过写成生效中，驳回或终止写成已驳回。"""

    if rule.status != WhitelistStatus.PENDING or not rule.itsm_ticket_id:
        return {}
    ticket = _ticket_from_logs(rule)
    if not ticket:
        return {}
    mapped, _display = map_whitelist_status(ticket)
    logger.info(
        "[RiskWhitelist] logs id=%s itsm=%s raw_status=%s mapped=%s",
        rule.id,
        rule.itsm_ticket_id,
        _raw_ticket_status(ticket),
        mapped,
    )
    if mapped != WhitelistStatus.PENDING:
        _write_terminal_status(rule, ticket)
    return ticket


def prepare_callback_ticket(ticket: dict) -> dict:
    """和场景权限回调一样，只看回调体里的 status、approve_result。

    approve_result 缺省当未通过。finished 且通过才是生效中；finished 未通过是已驳回；
    termination 也记为已驳回。日志只补驳回或终止理由，不改通过还是驳回。
    """

    ticket = dict(ticket or {})
    ticket["status"] = _raw_ticket_status(ticket)
    parsed = parse_itsm_ticket(ticket)
    ticket["status"] = parsed["status"]
    ticket["approve_result"] = parsed["approve_result"]
    terminal = parsed["status"] in {ITSMV4TicketStatus.FINISHED, ITSMV4TicketStatus.TERMINATION}
    if terminal and not parsed["approve_result"]:
        ticket["comment"] = _callback_reject_reason(ticket) or ticket.get("comment") or ""
    return ticket


def _callback_reject_reason(ticket: dict) -> str:
    ticket_id = str((ticket or {}).get("id") or "")
    if not ticket_id:
        return ""
    try:
        logs = api.bk_itsm_v4.ticket_logs(ticket_id=ticket_id) or {}
    except Exception:
        logger.exception("[RiskWhitelist] callback ticket_logs failed, ticket_id=%s", ticket_id)
        return ""
    return _extract_reject_reason_from_logs(logs if isinstance(logs, dict) else {})


def _ticket_from_logs(rule: RiskWhitelist):
    """用工单日志判断审批是否已经结束。和场景权限轮询同一套日志解析。"""

    try:
        logs = api.bk_itsm_v4.ticket_logs(ticket_id=rule.itsm_ticket_id) or {}
    except Exception:
        logger.exception("[RiskWhitelist] ticket_logs failed, id=%s", rule.id)
        return None
    from services.web.scene.permission import parse_itsm_ticket_from_logs

    parsed = parse_itsm_ticket_from_logs(logs if isinstance(logs, dict) else {})
    if parsed.get("status") not in {ITSMV4TicketStatus.FINISHED, ITSMV4TicketStatus.TERMINATION}:
        return None
    return {
        "id": rule.itsm_ticket_id,
        "status": parsed["status"],
        "approve_result": parsed.get("approve_result"),
    }


def _poll_whitelist_ticket(rule: RiskWhitelist) -> None:
    refresh_pending_whitelist(rule)


def _load_ticket_detail(rule: RiskWhitelist) -> dict:
    try:
        detail = api.bk_itsm_v4.ticket_detail(id=rule.itsm_ticket_id) or {}
    except Exception:
        logger.exception("[RiskWhitelist] ticket_detail failed, id=%s", rule.id)
        return {}
    return detail if isinstance(detail, dict) else {}


def expire_whitelists() -> int:
    """到期只改白名单状态。节点申请状态仍是已通过。"""

    updated = RiskWhitelist.objects.filter(
        status=WhitelistStatus.ACTIVE, expire_at__isnull=False, expire_at__lte=timezone.now()
    ).update(status=WhitelistStatus.EXPIRED, skip_update_user=True)
    return updated


def _json_safe(value):
    return json.loads(json.dumps(value, default=str))


def _find_converged_risk(event: dict, create_params: dict, scene_id):
    from services.web.risk.models import Risk

    return (
        Risk.objects.filter(
            Q(
                Q(
                    strategy_id=event["strategy_id"],
                    raw_event_id=event["raw_event_id"],
                    strategy_rule_id=create_params["strategy_rule_id"],
                    scene_id=scene_id,
                )
                & Q(
                    ~Q(status=RiskStatus.CLOSED)
                    | Q(
                        event_end_time__gte=datetime.datetime.fromtimestamp(
                            event["event_time"] / 1000, tz=timezone.get_default_timezone()
                        )
                    )
                )
            )
        )
        .order_by("-event_time")
        .first()
    )


def intercept_whitelist(event: dict, create_params: dict, scene_id) -> bool:
    """命中生效规则时写命中记录并返回 True。调用方不再建单或追加。"""

    if not scene_id:
        return False
    now = timezone.now()
    rules = list(
        RiskWhitelist.objects.filter(scene_id=scene_id, status=WhitelistStatus.ACTIVE).only(
            "id", "expire_at", "match_scope", "status", "scene_id"
        )
    )
    matched = [
        rule
        for rule in rules
        if (rule.expire_at is None or rule.expire_at > now) and match_scope(rule.match_scope, event)
    ]
    if not matched:
        return False
    converged = _find_converged_risk(event, create_params, scene_id)
    action = HitAction.SUPPRESS_APPEND if converged else HitAction.SUPPRESS_NEW
    risk_id = converged.risk_id if converged else ""
    snapshot = _json_safe(event)
    RiskWhitelistHit.objects.bulk_create(
        [
            RiskWhitelistHit(
                whitelist_id=rule.id,
                hit_at=now,
                action=action,
                risk_id=risk_id,
                match_snapshot=rule.match_scope,
                event_snapshot=snapshot,
            )
            for rule in matched
        ]
    )
    logger.info(
        "[RiskWhitelist] intercepted event strategy=%s scene=%s action=%s rules=%s",
        event.get("strategy_id"),
        scene_id,
        action,
        [rule.id for rule in matched],
    )
    return True


def _can_apply_renew(rule: RiskWhitelist) -> bool:
    """续期是申请。有到期时间、且不是待审批或已驳回时都可以发起。"""

    return bool(getattr(rule, "expire_at", None)) and rule.status in {
        WhitelistStatus.ACTIVE,
        WhitelistStatus.EXPIRED,
        WhitelistStatus.DISABLED,
    }


def _with_renew(actions: list, rule: RiskWhitelist) -> list:
    if not _can_apply_renew(rule) or "renew" in actions:
        return actions
    if "edit" in actions:
        actions.insert(actions.index("edit") + 1, "renew")
    else:
        actions.insert(0, "renew")
    return actions


def _maintenance_actions(rule: RiskWhitelist) -> list:
    """编辑、启停和删除。续期另算，谁都可以申请。"""

    if rule.status == WhitelistStatus.ACTIVE:
        return ["edit", "disable", "hits"]
    if rule.status == WhitelistStatus.DISABLED:
        return ["edit", "enable", "hits", "delete"]
    if rule.status == WhitelistStatus.EXPIRED:
        return ["edit", "hits", "delete"]
    if rule.status == WhitelistStatus.REJECTED:
        return ["delete"]
    return []


def order_whitelist_queryset(queryset, order_fields):
    """到期时间排序：永久白名单没有到期时间（expire_at 为空）。

    沿用 NULL 的排序语义：倒序时空值置顶（永久在最上面），正序时空值垫底。
    """

    ordering = []
    for field in order_fields:
        descending = str(field).startswith("-")
        name = field[1:] if descending else field
        if name != "expire_at":
            ordering.append(field)
            continue
        queryset = queryset.annotate(
            expire_is_permanent=Case(
                When(expire_at__isnull=True, then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            )
        )
        ordering.append("-expire_is_permanent" if descending else "expire_is_permanent")
        ordering.append("-expire_at" if descending else "expire_at")
    return queryset.order_by(*ordering)


def list_actions(rule: RiskWhitelist, username: str = "", is_admin=None) -> list:
    """通过和驳回只给该场景的场景管理员。续期是申请，看到这条白名单的人都可以发起。"""

    if is_admin is None:
        is_admin = bool(username and is_scene_admin(username, rule.scene_id))
    if not is_admin:
        actions = _maintenance_actions(rule) if username and is_platform_admin(username) else []
        return _with_renew(actions, rule)
    if rule.status == WhitelistStatus.PENDING:
        return ["approve", "reject"]
    if rule.status == WhitelistStatus.ACTIVE:
        actions = ["edit", "disable", "hits"]
    elif rule.status == WhitelistStatus.DISABLED:
        actions = ["edit", "enable", "hits", "delete"]
    elif rule.status == WhitelistStatus.EXPIRED:
        actions = ["edit", "hits", "delete"]
    elif rule.status == WhitelistStatus.REJECTED:
        return ["delete"]
    else:
        return []
    return _with_renew(actions, rule)


def flow_of(rule: RiskWhitelist, ticket: dict = None):
    if rule.status not in FLOW_STATUS:
        return None
    ticket = ticket or {}
    rejected = rule.status == WhitelistStatus.REJECTED
    if ticket.get("status"):
        status, status_display = map_whitelist_status(ticket)
    else:
        status, status_display = rule.status, str(WhitelistStatus(rule.status).label)
    return {
        "itsm_ticket_id": str(ticket.get("id") or rule.itsm_ticket_id or ""),
        "itsm_sn": ticket.get("sn") or rule.itsm_sn or "",
        "itsm_url": ticket.get("frontend_url") or rule.itsm_ticket_url or "",
        "status": status,
        "status_display": status_display,
        "approve_result": ticket.get("approve_result"),
        "comment": ticket.get("comment") or "",
        "current_processors": ticket.get("current_processors") or [],
        "current_steps": ticket.get("current_steps") or [],
        "rejector": rule.updated_by if rejected else "",
        "reject_reason": rule.reject_reason if rejected else "",
        "rejected_at": _format_dt(rule.updated_at) if rejected else "",
    }


def _load_ticket_details(rules) -> dict:
    if not rules:
        return {}
    if len(rules) == 1:
        return {str(rules[0].id): _load_ticket_detail(rules[0])}

    def _load(rule):
        from django.db import close_old_connections

        close_old_connections()
        try:
            return _load_ticket_detail(rule)
        finally:
            close_old_connections()

    found = {}
    with ThreadPoolExecutor(max_workers=len(rules)) as pool:
        futures = {pool.submit(_load, rule): rule for rule in rules}
        for future, rule in futures.items():
            try:
                found[str(rule.id)] = future.result()
            except Exception:
                logger.exception("[RiskWhitelist] list ticket_detail failed, id=%s", rule.id)
                found[str(rule.id)] = {}
    return found


def _write_terminal_status(rule: RiskWhitelist, ticket: dict) -> None:
    """flow 映射成生效中或已驳回时，把同一个结果写到白名单 status。"""

    if rule.status != WhitelistStatus.PENDING or not ticket:
        return
    mapped, _display = map_whitelist_status(ticket)
    if mapped == WhitelistStatus.PENDING:
        return
    try:
        updated = apply_whitelist_result(rule, ticket)
        rule.status = updated.status
        rule.reject_reason = updated.reject_reason
    except Exception:
        logger.exception("[RiskWhitelist] write ticket status failed, id=%s", getattr(rule, "id", None))
    if rule.status != WhitelistStatus.PENDING:
        refresh_whitelist_nodes(rule, ticket)
        return
    stored = RiskWhitelist.objects.filter(pk=rule.pk).values_list("status", "reject_reason").first()
    if stored and stored[0] != WhitelistStatus.PENDING:
        rule.status, rule.reject_reason = stored
        refresh_whitelist_nodes(rule, ticket)
        return
    comment = (ticket or {}).get("comment") or ""
    reject_reason = "" if mapped == WhitelistStatus.ACTIVE else (comment or getattr(rule, "reject_reason", "") or "")
    changed = RiskWhitelist.objects.filter(pk=rule.pk, status=WhitelistStatus.PENDING).update(
        status=mapped,
        reject_reason=reject_reason,
        updated_at=timezone.now(),
    )
    if not changed:
        return
    rule.status = mapped
    rule.reject_reason = reject_reason
    refresh_whitelist_nodes(rule, ticket)
    if mapped == WhitelistStatus.ACTIVE:
        _close_source_risk(rule)


def sync_whitelist_nodes_for_risk(risk_id: str) -> None:
    """审批已经通过或驳回、节点仍停在待审批时，补写成已通过或被驳回。"""

    from services.web.risk.models import TicketNode

    if not risk_id:
        return
    nodes = list(TicketNode.objects.filter(risk_id=risk_id, action=WHITELIST_NODE_ACTION))
    if not nodes:
        return
    rule_ids = []
    for node in nodes:
        rule_id = ((node.extra or {}).get("whitelist") or {}).get("rule_id")
        if rule_id not in (None, ""):
            rule_ids.append(rule_id)
    if rule_ids:
        rules = list(RiskWhitelist.objects.filter(pk__in=rule_ids))
    else:
        rules = list(RiskWhitelist.objects.filter(risk_id=risk_id))
    for rule in rules:
        if rule.status == WhitelistStatus.ACTIVE:
            expected = WhitelistStatus.ACTIVE
        elif rule.status == WhitelistStatus.REJECTED:
            expected = WhitelistStatus.REJECTED
        else:
            continue
        stale = False
        for node in nodes:
            if not _node_belongs_to_rule(node, rule):
                continue
            current = ((node.extra or {}).get("whitelist") or {}).get("itsm_status")
            if current != expected:
                stale = True
                break
        if stale:
            refresh_whitelist_nodes(rule)


def serialize_rule(
    rule: RiskWhitelist,
    hit_count: int = 0,
    progress: dict = None,
    username: str = "",
    is_admin=None,
) -> dict:
    if progress is None:
        progress = getattr(rule, "_itsm_progress", None)
    return {
        "id": str(rule.id),
        "rule_code": str(rule.id),
        "scene_id": rule.scene_id,
        "risk_id": rule.risk_id,
        "match_scope": rule.match_scope,
        # 匹配范围里实际带值的条件字段名，列表“包含条件”筛选和展示共用
        "contains_fields": sorted(scope_field_names(rule.match_scope)),
        "whitelist_type": rule.whitelist_type,
        "expire_at": _format_expire(rule.expire_at) or None,
        "is_permanent": rule.is_permanent,
        "status": rule.status,
        "reason": rule.reason,
        "hit_count": hit_count,
        "updated_by": rule.updated_by or "",
        "updated_at": _format_dt(rule.updated_at),
        # 单据提交时间：创建取创建时间，续期重建单据后取更新时间，其余不变
        "submitted_at": submitted_at_of(rule),
        "applicant": rule.created_by or "",
        "itsm_ticket_id": rule.itsm_ticket_id or "",
        "itsm_sn": rule.itsm_sn or "",
        "itsm_url": rule.itsm_ticket_url or "",
        "flow": flow_of(rule, progress),
        "actions": list_actions(rule, username, is_admin=is_admin),
    }


def ensure_admin(username: str, scene_id: int) -> None:
    if not is_scene_admin(username, scene_id):
        raise ValidationError(gettext("没有该场景的白名单管理权限"))


def get_rule_for_admin(rule_id: int, username: str, *, maintain: bool = False) -> RiskWhitelist:
    """maintain 为真时，平台管理员也可以编辑、启停和删除。通过和驳回仍只认场景管理员。"""

    rule = RiskWhitelist.objects.filter(pk=rule_id).first()
    if rule is None:
        raise ValidationError(gettext("白名单不存在"))
    if is_scene_admin(username, rule.scene_id):
        return rule
    if maintain and is_platform_admin(username) and rule.scene_id in set(managed_scene_ids(username)):
        return rule
    raise ValidationError(gettext("没有该场景的白名单管理权限"))

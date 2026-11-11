# -*- coding: utf-8 -*-
"""白名单创建、ITSM 审批回写、到期和命中拦截。"""

import datetime
import json
import logging
import uuid

from bk_resource import api
from bk_resource.settings import bk_resource_settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext
from rest_framework.exceptions import ValidationError
from rest_framework.settings import api_settings

from apps.permission.handlers.actions import ActionEnum
from apps.permission.handlers.permission import Permission
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
    match_scope,
    validate_match_scope,
)
from services.web.risk.whitelist.models import RiskWhitelist, RiskWhitelistHit
from services.web.scene.constants import ITSMV4TicketStatus
from services.web.scene.models import Scene

logger = logging.getLogger(__name__)

# 冒险加白未传天数时的默认值，对应原来的一个月。
DEFAULT_ACCEPTANCE_DAYS = 30


def is_platform_admin(username: str) -> bool:
    if username == bk_resource_settings.PLATFORM_AUTH_ACCESS_USERNAME:
        return True
    return Permission(username=username).has_action_any_permission(ActionEnum.MANAGE_PLATFORM)


def is_scene_admin(username: str, scene_id: int) -> bool:
    if is_platform_admin(username):
        return True
    scene = Scene.objects.filter(pk=scene_id, is_deleted=False).only("managers").first()
    return bool(scene and username in (scene.managers or []))


def managed_scene_ids(username: str):
    """平台管理员返回 None，表示不限场景。"""

    if is_platform_admin(username):
        return None
    return list(
        Scene.objects.filter(is_deleted=False, managers__contains=[username]).values_list("scene_id", flat=True)
    )


def coerce_duration_days(value):
    """整数是有效天数，时间字符串是到期时间。空值返回 None。"""

    if value in (None, ""):
        return None
    if isinstance(value, bool):
        raise ValidationError(gettext("有效天数必须是大于 0 的整数或到期时间"))
    if isinstance(value, datetime.datetime):
        return value
    if isinstance(value, int):
        if value < 1:
            raise ValidationError(gettext("有效天数必须是大于 0 的整数"))
        return value
    text = str(value).strip()
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


def resolve_duration(whitelist_type: str, is_permanent=None, duration_days=None) -> tuple:
    """返回 (是否永久, 天数)。天数由调用方传入，不限 7 天或整月。"""

    has_days = duration_days not in (None, "")
    if is_permanent is not True and not has_days:
        if whitelist_type == WhitelistType.FALSE_POSITIVE:
            return True, None
        return False, DEFAULT_ACCEPTANCE_DAYS
    if is_permanent is True:
        if whitelist_type == WhitelistType.RISK_ACCEPTANCE:
            raise ValidationError(gettext("冒险加白需要填写有效天数"))
        return True, None
    try:
        days = int(duration_days)
    except (TypeError, ValueError):
        raise ValidationError(gettext("有效天数必须是大于 0 的整数"))
    if days < 1:
        raise ValidationError(gettext("有效天数必须是大于 0 的整数"))
    return False, days


def resolve_expire_at(whitelist_type: str, is_permanent=None, duration_days=None):
    """返回 (是否永久, 到期时间)。duration_days 为时间时原样保存，为整数时从当前时间加天数。"""

    duration_days = coerce_duration_days(duration_days)
    if isinstance(duration_days, datetime.datetime):
        if is_permanent is True:
            raise ValidationError(gettext("永久规则不能填写到期时间"))
        expire_at = duration_days
        if timezone.is_naive(expire_at):
            expire_at = timezone.make_aware(expire_at, timezone.get_current_timezone())
        expire_at = expire_at.replace(microsecond=0)
        if expire_at <= timezone.now():
            raise ValidationError(gettext("到期时间必须晚于当前时间"))
        return False, expire_at
    permanent, days = resolve_duration(whitelist_type, is_permanent, duration_days)
    return permanent, expire_at_from(permanent, days)


def expire_at_from(is_permanent: bool, duration_days, base=None):
    base = base or timezone.now()
    if is_permanent:
        return None
    return (base + datetime.timedelta(days=int(duration_days or 0))).replace(microsecond=0)


def _format_dt(value) -> str:
    if not value:
        return ""
    return value.strftime(api_settings.DATETIME_FORMAT)


def _format_expire(value) -> str:
    if not value:
        return ""
    if timezone.is_aware(value):
        value = timezone.localtime(value)
    return value.strftime(api_settings.DATETIME_FORMAT)


def validity_text(rule: RiskWhitelist) -> str:
    if rule.is_permanent:
        return "永久"
    return _format_expire(rule.expire_at)


def _kept(ticket: dict, previous: dict, key: str):
    """工单这次没带回的字段，沿用节点上一次的值。"""

    if key in (ticket or {}):
        return (ticket or {}).get(key) or []
    return (previous or {}).get(key) or []


def _node_payload(rule: RiskWhitelist, ticket: dict = None, previous: dict = None) -> dict:
    """节点上保留申请内容和 ITSM 单。状态、处理人、当前步骤取工单返回。"""

    ticket = ticket or {}
    previous = previous or {}
    status, status_display = map_whitelist_status(ticket)
    approved = ticket.get("approve_result")
    return {
        "match_scope": rule.match_scope,
        "applicant": rule.created_by or "",
        "whitelist_type": rule.whitelist_type,
        "validity_text": validity_text(rule),
        "reason": rule.reason,
        "submitted_at": _format_dt(rule.created_at),
        "itsm_ticket_id": str(ticket.get("id") or rule.itsm_ticket_id or ""),
        "itsm_sn": ticket.get("sn") or rule.itsm_sn or "",
        "itsm_url": ticket.get("frontend_url") or rule.itsm_ticket_url or "",
        "itsm_status": status,
        "itsm_status_display": status_display,
        "approve_result": approved,
        "current_processors": _kept(ticket, previous, "current_processors"),
        "current_steps": _kept(ticket, previous, "current_steps"),
    }


def map_whitelist_status(ticket: dict) -> tuple:
    """ITSM 工单状态对应到白名单状态。未结束仍是待审批。"""

    status = (ticket or {}).get("status") or ""
    approved = bool((ticket or {}).get("approve_result"))
    if status == ITSMV4TicketStatus.FINISHED and approved:
        mapped = WhitelistStatus.ACTIVE
    elif status in {ITSMV4TicketStatus.FINISHED, ITSMV4TicketStatus.TERMINATION}:
        mapped = WhitelistStatus.REJECTED
    else:
        mapped = WhitelistStatus.PENDING
    return mapped, str(WhitelistStatus(mapped).label)


def _ticket_process_result(rule: RiskWhitelist, ticket: dict, previous: dict = None) -> dict:
    ticket = ticket or {}
    previous = previous or {}
    status, status_display = map_whitelist_status(ticket)
    approved = ticket.get("approve_result")
    stored = {
        "id": str(ticket.get("id") or rule.itsm_ticket_id or ""),
        "sn": ticket.get("sn") or rule.itsm_sn or "",
        "frontend_url": ticket.get("frontend_url") or rule.itsm_ticket_url or "",
        "status": status,
        "status_display": status_display,
        "approve_result": approved,
        "comment": ticket.get("comment") or "",
        "current_processors": _kept(ticket, previous, "current_processors"),
        "current_steps": _kept(ticket, previous, "current_steps"),
    }
    return {"ticket": stored}


def write_whitelist_nodes(rule: RiskWhitelist, risks) -> None:
    now = datetime.datetime.now()
    payload = {"whitelist": _node_payload(rule)}
    for risk in risks:
        from services.web.risk.models import TicketNode

        TicketNode.objects.create(
            risk_id=risk.risk_id,
            operator=rule.created_by or "",
            current_operator=risk.current_operator or [],
            action=WHITELIST_NODE_ACTION,
            timestamp=now.timestamp(),
            time=now.strftime(api_settings.DATETIME_FORMAT),
            process_result=_ticket_process_result(rule, {}),
            extra=payload,
            status=TicketNodeStatus.FINISHED,
        )


def refresh_whitelist_nodes(rule: RiskWhitelist, ticket: dict = None) -> None:
    from services.web.risk.models import TicketNode

    if not rule.risk_id:
        return
    ticket = ticket or {}
    nodes = TicketNode.objects.filter(risk_id=rule.risk_id, action=WHITELIST_NODE_ACTION)
    for node in nodes:
        current = ((node.extra or {}).get("whitelist") or {}).get("rule_id")
        if str(current) != str(rule.id):
            continue
        previous = (node.process_result or {}).get("ticket") or {}
        process_result = _ticket_process_result(rule, ticket, previous)
        node.extra = {"whitelist": _node_payload(rule, ticket, previous)}
        node.process_result = process_result
        node.save(update_fields=["extra", "process_result"])


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
    is_permanent=None,
    duration_days=None,
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
                is_permanent=is_permanent,
                duration_days=duration_days,
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
        is_permanent=is_permanent,
        duration_days=duration_days,
        risks=risks,
        username=username,
    )


def _create_whitelist(
    *,
    scene_id: int,
    match_scope: dict,
    whitelist_type: str,
    reason: str,
    is_permanent=None,
    duration_days=None,
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
    is_permanent, expire_at = resolve_expire_at(whitelist_type, is_permanent, duration_days)
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
    if risks:
        write_whitelist_nodes(rule, risks)
    create_itsm_ticket(rule.id)
    rule.refresh_from_db()
    return rule


def operate_itsm(rule: RiskWhitelist, method: str, operator: str) -> None:
    if not rule.itsm_ticket_id:
        raise ValidationError(gettext("ITSM 工单尚未创建"))
    api.bk_itsm_v4.ticket_handle(
        ticket_id=rule.itsm_ticket_id,
        action={"method": method, "params": {}},
        operator=operator,
        portal_id="DEFAULT",
        form_data={},
        options={},
    )


def apply_whitelist_result(rule: RiskWhitelist, ticket: dict) -> RiskWhitelist:
    """终态才改状态。已经不是待审批时直接返回。"""

    status, _display = map_whitelist_status(ticket)
    comment = (ticket or {}).get("comment") or ""
    with transaction.atomic():
        current = RiskWhitelist.objects.select_for_update().get(pk=rule.pk)
        if current.status != WhitelistStatus.PENDING:
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
        current.save(update_fields=["status", "reject_reason", "updated_at", "updated_by"])
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


def create_itsm_ticket(rule_id: int) -> None:
    rule = RiskWhitelist.objects.filter(pk=rule_id).first()
    if rule is None or rule.itsm_ticket_id:
        return
    workflow_key = RISK_WHITELIST_WORKFLOW_KEY
    if not workflow_key:
        logger.error("[RiskWhitelist] RISK_WHITELIST_WORKFLOW_KEY 未配置, id=%s", rule.id)
        _abort_whitelist(rule)
        raise ValidationError(gettext("ITSM 审批流程未配置"))
    callback_url = RISK_WHITELIST_CALLBACK_URL
    form_data = {
        "ticket__title": f"【审计中心】风险白名单 {rule.id}",
        "scene_id": str(rule.scene_id),
        "whitelist_id": str(rule.id),
        "whitelist_type": rule.whitelist_type,
        "reason": rule.reason,
        "match_scope": json.dumps(rule.match_scope, ensure_ascii=False),
        "risk_id": rule.risk_id,
        "applicant": rule.created_by or "",
    }
    try:
        ticket = api.bk_itsm_v4.ticket_create(
            operator=rule.created_by or "",
            workflow_key=workflow_key,
            form_data=form_data,
            is_submit=True,
            callback_url=callback_url,
            callback_token=rule.callback_token,
            portal="DEFAULT",
        )
    except Exception as exc:
        logger.exception("[RiskWhitelist] ticket_create failed, id=%s", rule.id)
        _abort_whitelist(rule)
        raise ValidationError(gettext("ITSM 工单创建失败")) from exc
    rule.itsm_ticket_id = str(ticket.get("id") or "")
    rule.itsm_sn = ticket.get("sn") or ""
    rule.itsm_ticket_url = ticket.get("frontend_url") or ""
    if not rule.itsm_ticket_id:
        _abort_whitelist(rule)
        raise ValidationError(gettext("ITSM 工单创建失败"))
    rule.save(update_fields=["itsm_ticket_id", "itsm_sn", "itsm_ticket_url", "updated_at", "updated_by"])
    refresh_whitelist_nodes(rule, ticket)
    if rule.created_by and is_scene_admin(rule.created_by, rule.scene_id):
        try:
            operate_itsm(rule, "approve", rule.created_by)
        except Exception:
            logger.exception("[RiskWhitelist] admin approve failed, id=%s", rule.id)
            return
        apply_whitelist_result(
            rule,
            {
                "id": rule.itsm_ticket_id,
                "sn": rule.itsm_sn,
                "frontend_url": rule.itsm_ticket_url,
                "status": ITSMV4TicketStatus.FINISHED,
                "approve_result": True,
                "comment": "",
                "current_processors": ticket.get("current_processors") or [],
                "current_steps": ticket.get("current_steps") or [],
            },
        )


def sync_pending_whitelists(limit: int = 50) -> None:
    rules = list(
        RiskWhitelist.objects.filter(status=WhitelistStatus.PENDING).exclude(itsm_ticket_id="").order_by("id")[:limit]
    )
    for rule in rules:
        try:
            detail = api.bk_itsm_v4.ticket_detail(id=rule.itsm_ticket_id)
        except Exception:
            logger.exception("[RiskWhitelist] ticket_detail failed, id=%s", rule.id)
            continue
        apply_whitelist_result(rule, detail)


def expire_whitelists() -> int:
    return RiskWhitelist.objects.filter(
        status=WhitelistStatus.ACTIVE, expire_at__isnull=False, expire_at__lte=timezone.now()
    ).update(status=WhitelistStatus.EXPIRED)


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


def list_actions(rule: RiskWhitelist) -> list:
    if rule.status == WhitelistStatus.PENDING:
        return ["approve", "reject"]
    if rule.status == WhitelistStatus.ACTIVE:
        actions = ["edit", "disable", "hits"]
        if not rule.is_permanent:
            actions.insert(2, "renew")
        return actions
    if rule.status == WhitelistStatus.DISABLED:
        return ["edit", "enable", "hits", "delete"]
    if rule.status == WhitelistStatus.EXPIRED:
        return ["edit", "renew", "hits", "delete"]
    if rule.status == WhitelistStatus.REJECTED:
        return ["delete"]
    return []


def flow_of(rule: RiskWhitelist, ticket: dict = None):
    if rule.status not in FLOW_STATUS:
        return None
    ticket = ticket or {}
    rejected = rule.status == WhitelistStatus.REJECTED
    status, status_display = map_whitelist_status(ticket) if ticket.get("status") else ("", "")
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
        "rejected_at": rule.updated_at.strftime(api_settings.DATETIME_FORMAT) if rejected and rule.updated_at else "",
    }


def progress_map(rules) -> dict:
    """待审批、驳回直接读 ITSM 工单回显，不读风险节点，也不另存。"""

    found = {}
    for rule in rules:
        if rule.status not in FLOW_STATUS or not rule.itsm_ticket_id:
            continue
        try:
            detail = api.bk_itsm_v4.ticket_detail(id=rule.itsm_ticket_id) or {}
        except Exception:
            logger.exception("[RiskWhitelist] list ticket_detail failed, id=%s", rule.id)
            found[str(rule.id)] = {}
            continue
        found[str(rule.id)] = detail
    return found


def serialize_rule(rule: RiskWhitelist, hit_count: int = 0, progress: dict = None) -> dict:
    if progress is None:
        progress = getattr(rule, "_itsm_progress", None)
    if progress is None and rule.status in FLOW_STATUS:
        progress = progress_map([rule]).get(str(rule.id))
    return {
        "id": str(rule.id),
        "rule_code": str(rule.id),
        "scene_id": rule.scene_id,
        "risk_id": rule.risk_id,
        "match_scope": rule.match_scope,
        "whitelist_type": rule.whitelist_type,
        "expire_at": _format_expire(rule.expire_at) or None,
        "is_permanent": rule.is_permanent,
        "status": rule.status,
        "reason": rule.reason,
        "hit_count": hit_count,
        "updated_by": rule.updated_by or "",
        "updated_at": rule.updated_at.strftime(api_settings.DATETIME_FORMAT) if rule.updated_at else "",
        "applicant": rule.created_by or "",
        "itsm_ticket_id": rule.itsm_ticket_id or "",
        "itsm_sn": rule.itsm_sn or "",
        "itsm_url": rule.itsm_ticket_url or "",
        "flow": flow_of(rule, progress),
        "actions": list_actions(rule),
    }


def ensure_admin(username: str, scene_id: int) -> None:
    if not is_scene_admin(username, scene_id):
        raise ValidationError(gettext("没有该场景的白名单管理权限"))


def get_rule_for_admin(rule_id: int, username: str) -> RiskWhitelist:
    rule = RiskWhitelist.objects.filter(pk=rule_id).first()
    if rule is None:
        raise ValidationError(gettext("白名单不存在"))
    ensure_admin(username, rule.scene_id)
    return rule

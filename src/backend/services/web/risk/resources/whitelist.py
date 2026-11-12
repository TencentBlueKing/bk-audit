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
software distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import abc
import json

from django.db.models import Count, Q
from django.utils import timezone
from django.utils.translation import gettext, gettext_lazy

from apps.audit.resources import AuditMixinResource
from core.exceptions import ValidationError
from core.models import get_request_username
from services.web.risk.constants import RiskLabel
from services.web.risk.models import Risk
from services.web.risk.whitelist.constants import (
    DELETABLE_STATUS,
    WhitelistStatus,
    WhitelistType,
)
from services.web.risk.whitelist.match import validate_match_scope
from services.web.risk.whitelist.models import RiskWhitelist, RiskWhitelistHit
from services.web.risk.whitelist.serializers import (
    BatchCreateRiskWhitelistReqSerializer,
    CreateRiskWhitelistReqSerializer,
    FetchWhitelistHitEventReqSerializer,
    ListRiskWhitelistReqSerializer,
    ListWhitelistHitRecordReqSerializer,
    RejectRiskWhitelistReqSerializer,
    RenewRiskWhitelistReqSerializer,
    RiskWhitelistCallbackReqSerializer,
    RiskWhitelistIdReqSerializer,
    UpdateRiskWhitelistReqSerializer,
)
from services.web.risk.whitelist.service import (
    _format_dt,
    apply_whitelist_result,
    ensure_admin,
    ensure_same_strategy_scene,
    get_rule_for_admin,
    managed_scene_ids,
    operate_itsm,
    progress_map,
    renew_whitelist,
    serialize_rule,
    submit_whitelist,
)


def _filter_any_icontains(queryset, field_name, values):
    """多个关键字任一包含即命中，和场景列表的名称、更新人筛选一样。"""

    if not values:
        return queryset
    matched = Q()
    for value in values:
        if value:
            matched |= Q(**{f"{field_name}__icontains": value})
    return queryset.filter(matched) if matched else queryset


class RiskWhitelistMeta(AuditMixinResource, abc.ABC):
    tags = ["RiskWhitelist"]
    audit_action = None
    audit_resource_type = None


class ListRiskWhitelists(RiskWhitelistMeta):
    name = gettext_lazy("风险白名单列表")
    RequestSerializer = ListRiskWhitelistReqSerializer

    def perform_request(self, validated_request_data):
        username = get_request_username()
        scene_ids = managed_scene_ids(username)
        if scene_ids is not None and not scene_ids:
            raise ValidationError(gettext("没有白名单权限"))
        queryset = RiskWhitelist.objects.all()
        if scene_ids is not None:
            queryset = queryset.filter(scene_id__in=scene_ids)
        scene_id = validated_request_data.get("scene_id")
        if scene_id:
            ensure_admin(username, scene_id)
            queryset = queryset.filter(scene_id=scene_id)
        rule_id = validated_request_data.get("id")
        if rule_id:
            queryset = queryset.filter(pk__in=rule_id)
        if validated_request_data.get("status"):
            queryset = queryset.filter(status__in=validated_request_data["status"])
        if validated_request_data.get("whitelist_type"):
            queryset = queryset.filter(whitelist_type__in=validated_request_data["whitelist_type"])
        queryset = _filter_any_icontains(queryset, "reason", validated_request_data.get("reason"))
        queryset = _filter_any_icontains(queryset, "updated_by", validated_request_data.get("updated_by"))
        if validated_request_data.get("keyword"):
            queryset = queryset.filter(match_scope__icontains=validated_request_data["keyword"])
        total = queryset.count()
        page = validated_request_data["page"]
        page_size = validated_request_data["page_size"]
        rows = list(
            queryset.annotate(hit_count=Count("hits", filter=Q(hits__is_deleted=False))).order_by(
                *validated_request_data["order_fields"]
            )[(page - 1) * page_size : page * page_size]
        )
        snapshots = progress_map(rows)
        return {
            "page": page,
            "page_size": page_size,
            "total": total,
            "results": [serialize_rule(row, getattr(row, "hit_count", 0), snapshots.get(str(row.id))) for row in rows],
        }


class CreateRiskWhitelist(RiskWhitelistMeta):
    """新建白名单。"""

    name = gettext_lazy("新建风险白名单")
    RequestSerializer = CreateRiskWhitelistReqSerializer

    def perform_request(self, validated_request_data):
        username = get_request_username()
        risk_id = validated_request_data.get("risk_id") or ""
        risks = []
        scene_id = validated_request_data.get("scene_id")
        if risk_id:
            risks = list(Risk.objects.filter(risk_id=risk_id))
            if not risks:
                raise ValidationError(gettext("风险单不存在"))
            _misreport_for_whitelist(risks, validated_request_data)
            risks = list(Risk.objects.filter(risk_id=risk_id))
            scene_id = risks[0].scene_id
        elif not scene_id:
            raise ValidationError(gettext("需要 scene_id"))
        return serialize_rule(
            _submit_created(
                validated_request_data,
                scene_id=scene_id,
                risks=risks,
                username=username,
            )
        )


class BatchCreateRiskWhitelist(RiskWhitelistMeta):
    """批量新建白名单。选单方式和批量确认风险一样，每张风险各建一条。"""

    name = gettext_lazy("批量新建风险白名单")
    RequestSerializer = BatchCreateRiskWhitelistReqSerializer

    def perform_request(self, validated_request_data):
        from services.web.risk.resources.risk import (
            BULK_ACTION_MAX_RISK_IDS,
            _prepare_bulk_risks,
        )

        username = get_request_username()
        risk_ids, risks, _risk_map = _prepare_bulk_risks(validated_request_data, BULK_ACTION_MAX_RISK_IDS)
        if len(risks) != len(risk_ids):
            raise ValidationError(gettext("部分风险单不存在"))
        ensure_same_strategy_scene(risks)
        _misreport_for_whitelist(risks, validated_request_data)
        risks = list(Risk.objects.filter(risk_id__in=risk_ids))
        created = _submit_created(
            validated_request_data,
            scene_id=risks[0].scene_id,
            risks=risks,
            username=username,
        )
        if not isinstance(created, list):
            created = [created]
        return [serialize_rule(item) for item in created]


def _misreport_for_whitelist(risks, validated_request_data) -> None:
    if validated_request_data.get("whitelist_type") != WhitelistType.FALSE_POSITIVE:
        return
    from services.web.risk.resources.risk import UpdateRiskLabel

    for risk in risks:
        UpdateRiskLabel().request(
            {
                "risk_id": risk.risk_id,
                "risk_label": RiskLabel.MISREPORT,
                "description": validated_request_data.get("reason") or "",
            }
        )


def _submit_created(validated_request_data, *, scene_id, risks, username):
    return submit_whitelist(
        scene_id=scene_id,
        match_scope=validated_request_data["match_scope"],
        whitelist_type=validated_request_data["whitelist_type"],
        reason=validated_request_data["reason"],
        duration_days=validated_request_data.get("duration_days"),
        expire_at=validated_request_data.get("expire_at"),
        risks=risks,
        username=username,
    )


class UpdateRiskWhitelist(RiskWhitelistMeta):
    name = gettext_lazy("编辑风险白名单")
    RequestSerializer = UpdateRiskWhitelistReqSerializer

    def perform_request(self, validated_request_data):
        rule = get_rule_for_admin(validated_request_data["id"], get_request_username())
        error = validate_match_scope(validated_request_data["match_scope"], rule.whitelist_type)
        if error:
            raise ValidationError(gettext(error))
        # 带了新有效期就是续期：原白名单不新建，重新提工单后把状态和工单绑回去。
        if validated_request_data.get("duration_days") not in (None, ""):
            renewed = renew_whitelist(
                rule,
                match_scope=validated_request_data["match_scope"],
                reason=validated_request_data["reason"],
                duration_days=validated_request_data["duration_days"],
                expire_at=validated_request_data.get("expire_at"),
                username=get_request_username(),
            )
            return serialize_rule(renewed)
        rule.match_scope = validated_request_data["match_scope"]
        rule.reason = validated_request_data["reason"]
        rule.save(update_fields=["match_scope", "reason", "updated_at", "updated_by"])
        return serialize_rule(rule)


class ApproveRiskWhitelist(RiskWhitelistMeta):
    name = gettext_lazy("通过风险白名单")
    RequestSerializer = RiskWhitelistIdReqSerializer

    def perform_request(self, validated_request_data):
        rule = get_rule_for_admin(validated_request_data["id"], get_request_username())
        if rule.status != WhitelistStatus.PENDING:
            return serialize_rule(rule)
        operate_itsm(rule, "approve", get_request_username())
        return serialize_rule(rule)


class RejectRiskWhitelist(RiskWhitelistMeta):
    name = gettext_lazy("驳回风险白名单")
    RequestSerializer = RejectRiskWhitelistReqSerializer

    def perform_request(self, validated_request_data):
        rule = get_rule_for_admin(validated_request_data["id"], get_request_username())
        if rule.status != WhitelistStatus.PENDING:
            return serialize_rule(rule)
        rule.reject_reason = validated_request_data["reason"]
        rule.save(update_fields=["reject_reason", "updated_at", "updated_by"])
        operate_itsm(rule, "refuse", get_request_username())
        return serialize_rule(rule)


class EnableRiskWhitelist(RiskWhitelistMeta):
    name = gettext_lazy("启用风险白名单")
    RequestSerializer = RiskWhitelistIdReqSerializer

    def perform_request(self, validated_request_data):
        rule = get_rule_for_admin(validated_request_data["id"], get_request_username())
        if rule.status != WhitelistStatus.DISABLED:
            raise ValidationError(gettext("只有已停用的规则可以启用"))
        if rule.expire_at and rule.expire_at <= timezone.now():
            rule.status = WhitelistStatus.EXPIRED
        else:
            rule.status = WhitelistStatus.ACTIVE
        rule.save(update_fields=["status", "updated_at", "updated_by"])
        return serialize_rule(rule)


class DisableRiskWhitelist(RiskWhitelistMeta):
    name = gettext_lazy("停用风险白名单")
    RequestSerializer = RiskWhitelistIdReqSerializer

    def perform_request(self, validated_request_data):
        rule = get_rule_for_admin(validated_request_data["id"], get_request_username())
        if rule.status != WhitelistStatus.ACTIVE:
            raise ValidationError(gettext("只有生效中的规则可以停用"))
        rule.status = WhitelistStatus.DISABLED
        rule.save(update_fields=["status", "updated_at", "updated_by"])
        return serialize_rule(rule)


class RenewRiskWhitelist(RiskWhitelistMeta):
    name = gettext_lazy("续期风险白名单")
    RequestSerializer = RenewRiskWhitelistReqSerializer

    def perform_request(self, validated_request_data):
        rule = get_rule_for_admin(validated_request_data["id"], get_request_username())
        renewed = renew_whitelist(
            rule,
            match_scope=rule.match_scope,
            reason=validated_request_data.get("remark") or rule.reason,
            duration_days=validated_request_data["duration_days"],
            expire_at=validated_request_data.get("expire_at"),
            username=get_request_username(),
        )
        return serialize_rule(renewed)


class DeleteRiskWhitelist(RiskWhitelistMeta):
    name = gettext_lazy("删除风险白名单")
    RequestSerializer = RiskWhitelistIdReqSerializer

    def perform_request(self, validated_request_data):
        rule = get_rule_for_admin(validated_request_data["id"], get_request_username())
        if rule.status not in DELETABLE_STATUS:
            raise ValidationError(gettext("只有已停用、已到期、已驳回的规则可以删除"))
        RiskWhitelistHit.objects.filter(whitelist=rule).update(is_deleted=True)
        rule.delete()
        return {"id": str(rule.id)}


class ListWhitelistHitRecords(RiskWhitelistMeta):
    name = gettext_lazy("白名单命中记录")
    RequestSerializer = ListWhitelistHitRecordReqSerializer

    def perform_request(self, validated_request_data):
        rule = get_rule_for_admin(validated_request_data["id"], get_request_username())
        queryset = RiskWhitelistHit.objects.filter(whitelist=rule)
        if validated_request_data.get("action"):
            queryset = queryset.filter(action=validated_request_data["action"])
        if validated_request_data.get("risk_id"):
            queryset = queryset.filter(risk_id=validated_request_data["risk_id"])
        total = queryset.count()
        page = validated_request_data["page"]
        page_size = validated_request_data["page_size"]
        rows = list(queryset.order_by("-hit_at", "-id")[(page - 1) * page_size : page * page_size])
        return {
            "page": page,
            "total": total,
            "results": [
                {
                    "id": str(row.id),
                    "hit_time": _format_dt(row.hit_at),
                    "action": row.action,
                    "match_scope": row.match_snapshot,
                    "risk_id": row.risk_id,
                    "risk_url": "",
                }
                for row in rows
            ],
        }


class FetchWhitelistHitEvent(RiskWhitelistMeta):
    """白名单下某次命中的事件字段。"""

    name = gettext_lazy("白名单命中事件")
    RequestSerializer = FetchWhitelistHitEventReqSerializer

    def perform_request(self, validated_request_data):
        rule = get_rule_for_admin(validated_request_data["id"], get_request_username())
        hit = RiskWhitelistHit.objects.filter(pk=validated_request_data["hit_id"], whitelist=rule).first()
        if hit is None:
            raise ValidationError(gettext("命中记录不存在"))
        fields = []
        for key, value in (hit.event_snapshot or {}).items():
            fields.append(
                {
                    "field": key,
                    "field_name": key,
                    "field_type": type(value).__name__,
                    "field_value": ""
                    if value is None
                    else value
                    if isinstance(value, str)
                    else json.dumps(value, ensure_ascii=False),
                }
            )
        return {"fields": fields}


class RiskWhitelistCallback(RiskWhitelistMeta):
    """ITSM 审批完成后回调。工单详情在请求体 ticket 里"""

    name = gettext_lazy("风险白名单 ITSM 回调")
    RequestSerializer = RiskWhitelistCallbackReqSerializer

    def perform_request(self, validated_request_data):
        callback_token = validated_request_data.get("callback_token") or ""
        ticket = validated_request_data.get("ticket") or {}
        ticket_id = str(ticket.get("id") or "")
        if not ticket_id:
            return {"result": False, "message": "missing ticket id"}
        rule = RiskWhitelist.objects.filter(itsm_ticket_id=ticket_id).first()
        if rule is None or not callback_token or rule.callback_token != callback_token:
            return {"result": False, "message": "invalid callback"}
        if rule.status == WhitelistStatus.PENDING:
            apply_whitelist_result(rule, ticket)
        return {"result": True, "message": "success"}

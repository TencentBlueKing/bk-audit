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
from concurrent.futures import ThreadPoolExecutor

from django.db.models import Count, Q
from django.utils import timezone
from django.utils.translation import gettext, gettext_lazy

from apps.audit.resources import AuditMixinResource
from core.exceptions import ValidationError
from core.models import get_request_username
from services.web.risk.models import Risk
from services.web.risk.whitelist.constants import DELETABLE_STATUS, WhitelistStatus
from services.web.risk.whitelist.match import (
    scope_field_names,
    scope_field_options,
    validate_match_scope,
)
from services.web.risk.whitelist.models import RiskWhitelist, RiskWhitelistHit
from services.web.risk.whitelist.serializers import (
    BatchCreateRiskWhitelistReqSerializer,
    BatchRiskWhitelistDetailReqSerializer,
    CreateRiskWhitelistReqSerializer,
    FetchWhitelistHitEventReqSerializer,
    ListRiskWhitelistReqSerializer,
    ListWhitelistContainsFieldsReqSerializer,
    ListWhitelistHitRecordReqSerializer,
    RejectRiskWhitelistReqSerializer,
    RenewRiskWhitelistReqSerializer,
    RiskWhitelistCallbackReqSerializer,
    RiskWhitelistIdReqSerializer,
    UpdateRiskWhitelistReqSerializer,
)
from services.web.risk.whitelist.service import (
    _bind_ticket,
    _format_dt,
    _load_ticket_detail,
    _save_rule,
    apply_whitelist_result,
    assert_can_manage_scene,
    build_hit_event_fields,
    can_access_whitelist,
    ensure_same_strategy_scene,
    get_rule_for_admin,
    order_whitelist_queryset,
    prepare_callback_ticket,
    refresh_whitelist_nodes,
    renew_whitelist,
    review_whitelist,
    serialize_rule,
    submit_whitelist,
    submitted_at_of,
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


def _filter_contains_fields(queryset, fields):
    """按匹配范围包含的条件字段筛选，多个字段任一命中即可。

    icontains 只能粗筛 JSON 文本，字段名互为子串或命中字段值都会误伤，
    所以再对候选行用 scope_field_names 精确判定（白名单表规模小）。
    """

    fields = [field for field in fields or [] if field]
    if not fields:
        return queryset
    pruned = Q()
    for field in fields:
        pruned |= Q(match_scope__icontains=f'"{field}"')
    if not pruned:
        return queryset
    candidates = list(queryset.filter(pruned).values_list("pk", "match_scope"))
    wanted = set(fields)
    pks = [pk for pk, scope in candidates if wanted & scope_field_names(scope)]
    return queryset.filter(pk__in=pks)


class RiskWhitelistMeta(AuditMixinResource, abc.ABC):
    tags = ["RiskWhitelist"]
    audit_action = None
    audit_resource_type = None


class ListRiskWhitelists(RiskWhitelistMeta):
    name = gettext_lazy("风险白名单列表")
    RequestSerializer = ListRiskWhitelistReqSerializer

    def perform_request(self, validated_request_data):
        username = get_request_username()
        # 场景管理权限由 viewset InstanceActionPermission(MANAGE_SCENE) 校验，这里只按场景过滤
        scene_id = validated_request_data["scene_id"]
        queryset = RiskWhitelist.objects.filter(scene_id=scene_id)
        rule_id = validated_request_data.get("id")
        if rule_id:
            queryset = queryset.filter(pk__in=rule_id)
        if validated_request_data.get("status"):
            queryset = queryset.filter(status__in=validated_request_data["status"])
        if validated_request_data.get("whitelist_type"):
            queryset = queryset.filter(whitelist_type__in=validated_request_data["whitelist_type"])
        queryset = _filter_any_icontains(queryset, "reason", validated_request_data.get("reason"))
        queryset = _filter_any_icontains(queryset, "updated_by", validated_request_data.get("updated_by"))
        queryset = _filter_any_icontains(queryset, "match_scope", validated_request_data.get("match_scope"))
        queryset = _filter_contains_fields(queryset, validated_request_data.get("contains_fields"))
        if validated_request_data.get("keyword"):
            queryset = queryset.filter(match_scope__icontains=validated_request_data["keyword"])
        total = queryset.count()
        page = validated_request_data["page"]
        page_size = validated_request_data["page_size"]
        rows = list(
            order_whitelist_queryset(
                queryset.annotate(hit_count=Count("hits", filter=Q(hits__is_deleted=False))),
                validated_request_data["order_fields"],
            )[(page - 1) * page_size : page * page_size]
        )
        # 列表只读库里的状态，不回显工单流转（flow 在详情接口按需实时拉，避免逐条外呼拖慢列表）。
        # actions 的管理按钮口径与写操作一致：整个列表同属一个场景，按 scene_id 判一次白名单管理权限，
        # 传入每行 list_actions（不再逐行判，也不硬编码 True 让普通申请人误见管理按钮）。
        is_admin = can_access_whitelist(username, scene_id)
        return {
            "page": page,
            "page_size": page_size,
            "total": total,
            "results": [
                serialize_rule(
                    row,
                    getattr(row, "hit_count", 0),
                    username=username,
                    is_admin=is_admin,
                    include_flow=False,
                )
                for row in rows
            ],
        }


class ListWhitelistContainsFields(RiskWhitelistMeta):
    """枚举某场景下所有白名单匹配范围里去重后的条件字段，供列表“包含条件”下拉。

    match_scope 是 JSON，字段名要在 Python 侧遍历每行求并集去重（白名单表规模小）。
    """

    name = gettext_lazy("白名单包含条件字段")
    RequestSerializer = ListWhitelistContainsFieldsReqSerializer

    def perform_request(self, validated_request_data):
        # 场景管理权限由 viewset InstanceActionPermission(MANAGE_SCENE) 校验，scene_id 已由序列化器必传
        # 跨行按 field 去重，field_name 取首次出现的非空展示名，全空回退 field
        scene_id = validated_request_data["scene_id"]
        picked: dict = {}
        scopes = RiskWhitelist.objects.filter(scene_id=scene_id).values_list("match_scope", flat=True)
        for scope in scopes:
            for field, field_name in scope_field_options(scope):
                if field not in picked:
                    picked[field] = field_name
                elif not picked[field] and field_name:
                    picked[field] = field_name
        return {"results": [{"field": field, "field_name": picked[field]} for field in sorted(picked)]}


class RetrieveRiskWhitelist(RiskWhitelistMeta):
    """批量查询白名单工单详情：入参一批白名单 ID，「待审批 / 已驳回」的单返回。"""

    name = gettext_lazy("风险白名单详情")
    RequestSerializer = BatchRiskWhitelistDetailReqSerializer

    def perform_request(self, validated_request_data):
        scene_id = validated_request_data["scene_id"]
        rule_ids = validated_request_data["id"]
        # 状态硬编码只取待审批 / 已驳回；scene_id 再过滤一次，杜绝跨场景 ID 越权查询
        rules = list(
            RiskWhitelist.objects.filter(
                pk__in=rule_ids,
                scene_id=scene_id,
                status__in=[WhitelistStatus.PENDING, WhitelistStatus.REJECTED],
            ).order_by("-created_at")
        )
        with ThreadPoolExecutor(max_workers=10) as executor:
            return list(executor.map(self._detail, rules))

    @staticmethod
    def _detail(rule: RiskWhitelist) -> dict:
        """组装单条详情：工单字段优先，外呼失败 / 无工单号时回落本地值。"""

        detail = _load_ticket_detail(rule) or {}
        # 状态：工单返回优先；外呼失败回落白名单本地状态（列表态，和 flow 终态一致）
        status = detail.get("status") or rule.status
        status_display = detail.get("status_display") or str(WhitelistStatus(rule.status).label)
        rejected = rule.status == WhitelistStatus.REJECTED
        return {
            "id": str(rule.id),
            "current_steps": detail.get("current_steps") or [],
            "current_processors": detail.get("current_processors") or [],
            "status": status,
            "status_display": status_display,
            # creator 是工单申请人，与建单提交的 applicant 同源，外呼失败回落白名单创建人
            "creator": detail.get("creator") or rule.created_by or "",
            "created_at": detail.get("created_at") or submitted_at_of(rule),
            "title": detail.get("title") or "",
            "sn": detail.get("sn") or rule.itsm_sn or "",
            "rejector": rule.updated_by if rejected else "",
            "reject_reason": rule.reject_reason if rejected else "",
        }


class CreateRiskWhitelist(RiskWhitelistMeta):
    """新建白名单。

    菜单直接新建（只带 scene_id，不关联风险）：建的是场景级规则，限场景管理员。
    风险详情「申请加白」（带 risk_id，不标误报）：风险处理人即可发起，口径同「确认误报」，
    提交后仍走 ITSM / 场景管理员审批，故放开到风险处理权限；批量入口仍限场景管理员。
    """

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
            scene_id = risks[0].scene_id
            # 风险处理人申请加白：创建白名单只是发起审批申请，不做确认人 / 平台管理员鉴权，
            # 能否生效由场景管理员在工单审批环节把关。
        else:
            if not scene_id:
                raise ValidationError(gettext("需要 scene_id"))
            # 菜单直接新建：场景级规则，保留场景管理权限限制
            assert_can_manage_scene(username, scene_id)
        return serialize_rule(
            _submit_created(
                validated_request_data,
                scene_id=scene_id,
                risks=risks,
                username=username,
            ),
            progress={},
            username=username,
            include_flow=False,
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
        assert_can_manage_scene(username, risks[0].scene_id)
        created = _submit_created(
            validated_request_data,
            scene_id=risks[0].scene_id,
            risks=risks,
            username=username,
        )
        # 全成功：submit_whitelist 返回规则列表；部分失败：返回 {succeeded, failed} 供逐项展示
        if isinstance(created, dict):
            return {
                "succeeded": [
                    serialize_rule(item, progress={}, username=username, include_flow=False)
                    for item in created.get("succeeded", [])
                ],
                "failed": created.get("failed", []),
            }
        if not isinstance(created, list):
            created = [created]
        return [serialize_rule(item, progress={}, username=username, include_flow=False) for item in created]


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
        target_type = validated_request_data.get("whitelist_type") or rule.whitelist_type
        error = validate_match_scope(validated_request_data["match_scope"], target_type)
        if error:
            raise ValidationError(gettext(error))
        # 换加白方式或带了新有效期，都在原单上重新提工单。不换类型、也不改有效期时，只改匹配范围和原因。
        type_changed = target_type != rule.whitelist_type
        if type_changed or validated_request_data.get("duration_days") not in (None, ""):
            renewed = renew_whitelist(
                rule,
                match_scope=validated_request_data["match_scope"],
                reason=validated_request_data["reason"],
                duration_days=validated_request_data.get("duration_days"),
                expire_at=validated_request_data.get("expire_at"),
                username=get_request_username(),
                whitelist_type=target_type,
            )
            return serialize_rule(renewed, username=get_request_username())
        rule.match_scope = validated_request_data["match_scope"]
        rule.reason = validated_request_data["reason"]
        _save_rule(rule, ["match_scope", "reason", "updated_at", "updated_by"])
        return serialize_rule(rule, username=get_request_username())


class ApproveRiskWhitelist(RiskWhitelistMeta):
    name = gettext_lazy("通过风险白名单")
    RequestSerializer = RiskWhitelistIdReqSerializer

    def perform_request(self, validated_request_data):
        rule = get_rule_for_admin(validated_request_data["id"], get_request_username())
        if rule.status != WhitelistStatus.PENDING:
            return serialize_rule(rule, username=get_request_username())
        rule = review_whitelist(rule, "approve", get_request_username())
        return serialize_rule(rule, username=get_request_username())


class RejectRiskWhitelist(RiskWhitelistMeta):
    name = gettext_lazy("驳回风险白名单")
    RequestSerializer = RejectRiskWhitelistReqSerializer

    def perform_request(self, validated_request_data):
        rule = get_rule_for_admin(validated_request_data["id"], get_request_username())
        if rule.status != WhitelistStatus.PENDING:
            return serialize_rule(rule, username=get_request_username())
        rule = review_whitelist(
            rule,
            "refuse",
            get_request_username(),
            reject_reason=validated_request_data["reason"],
        )
        return serialize_rule(rule, username=get_request_username())


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
        _save_rule(rule, ["status", "updated_at", "updated_by"])
        return serialize_rule(rule, username=get_request_username())


class DisableRiskWhitelist(RiskWhitelistMeta):
    name = gettext_lazy("停用风险白名单")
    RequestSerializer = RiskWhitelistIdReqSerializer

    def perform_request(self, validated_request_data):
        rule = get_rule_for_admin(validated_request_data["id"], get_request_username())
        if rule.status != WhitelistStatus.ACTIVE:
            raise ValidationError(gettext("只有生效中的规则可以停用"))
        rule.status = WhitelistStatus.DISABLED
        _save_rule(rule, ["status", "updated_at", "updated_by"])
        return serialize_rule(rule, username=get_request_username())


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
        return serialize_rule(renewed, username=get_request_username())


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
        return {"fields": build_hit_event_fields(hit.event_snapshot)}


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
        if rule is None and callback_token:
            # 回调可能在单据号落库前到达，这时用工单创建时带的 token 找到同一条白名单。
            rule = RiskWhitelist.objects.filter(callback_token=callback_token).first()
        if rule is None or not callback_token or rule.callback_token != callback_token:
            return {"result": False, "message": "invalid callback"}
        if not rule.itsm_ticket_id:
            _bind_ticket(rule, ticket)
            _save_rule(rule, ["itsm_ticket_id", "itsm_sn", "itsm_ticket_url", "updated_at", "updated_by"])
        ticket = prepare_callback_ticket(ticket)
        if rule.status == WhitelistStatus.PENDING:
            rule = apply_whitelist_result(rule, ticket)
        elif rule.status in {WhitelistStatus.ACTIVE, WhitelistStatus.REJECTED}:
            refresh_whitelist_nodes(rule, ticket)
        return {"result": True, "message": "success", "status": rule.status}

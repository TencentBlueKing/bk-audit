# -*- coding: utf-8 -*-
"""风险白名单接口入参。"""

from django.utils.translation import gettext_lazy
from rest_framework import serializers

from core.serializers import FlexibleListField, SortListField, SortSerializerMixin
from services.web.risk.serializers import (
    BULK_ACTION_MAX_RISK_IDS,
    BulkRiskSelectionSerializer,
)
from services.web.risk.whitelist.constants import WhitelistStatus, WhitelistType

WHITELIST_LIST_SORT_FIELDS = ("id", "updated_at", "expire_at", "status", "whitelist_type", "hit_count", "updated_by")
WHITELIST_LIST_SORT_FIELD_DESCRIPTIONS = {
    "id": "规则标识",
    "updated_at": "更新时间",
    "expire_at": "到期时间",
    "status": "状态",
    "whitelist_type": "加白类型",
    "hit_count": "命中次数",
    "updated_by": "更新人",
}
DEFAULT_WHITELIST_LIST_SORT = ["-id"]


class DurationDaysField(serializers.Field):
    """天数或到期时间，请求里都叫 duration_days。"""

    def to_internal_value(self, data):
        from services.web.risk.whitelist.service import coerce_duration_days

        try:
            value = coerce_duration_days(data)
        except Exception as exc:
            detail = getattr(exc, "detail", None)
            if isinstance(detail, list):
                detail = detail[0]
            raise serializers.ValidationError(detail or str(exc))
        if value is None:
            raise serializers.ValidationError(gettext_lazy("有效天数必须是大于 0 的整数或到期时间"))
        return value


class RiskWhitelistScopeSerializer(serializers.Serializer):
    scene_id = serializers.IntegerField(label=gettext_lazy("场景ID"), required=False)
    match_scope = serializers.JSONField(label=gettext_lazy("匹配范围"))
    whitelist_type = serializers.CharField(label=gettext_lazy("加白类型"))
    reason = serializers.CharField(label=gettext_lazy("加白原因"), max_length=500)
    duration_days = DurationDaysField(label=gettext_lazy("有效天数"), required=False, allow_null=True)
    expire_at = serializers.DateTimeField(label=gettext_lazy("到期时间"), required=False, allow_null=True)


class CreateRiskWhitelistReqSerializer(RiskWhitelistScopeSerializer):
    risk_id = serializers.CharField(label=gettext_lazy("风险ID"), required=False, allow_blank=True)


class BatchCreateRiskWhitelistReqSerializer(BulkRiskSelectionSerializer, RiskWhitelistScopeSerializer):
    """批量新建。risk_ids 与列表筛选 filters 二选一，和批量确认风险一样。"""

    risk_id_limit = BULK_ACTION_MAX_RISK_IDS


class ListRiskWhitelistReqSerializer(SortSerializerMixin, serializers.Serializer):
    scene_id = serializers.IntegerField(label=gettext_lazy("场景ID"), required=False)
    id = FlexibleListField(child=serializers.IntegerField(), required=False, label=gettext_lazy("白名单ID"))
    status = FlexibleListField(
        child=serializers.ChoiceField(choices=WhitelistStatus.choices),
        required=False,
        label=gettext_lazy("状态"),
    )
    whitelist_type = FlexibleListField(
        child=serializers.ChoiceField(choices=WhitelistType.choices),
        required=False,
        label=gettext_lazy("加白类型"),
    )
    reason = FlexibleListField(
        child=serializers.CharField(allow_blank=False), required=False, label=gettext_lazy("加白原因")
    )
    updated_by = FlexibleListField(
        child=serializers.CharField(allow_blank=False), required=False, label=gettext_lazy("更新人")
    )
    keyword = serializers.CharField(label=gettext_lazy("关键字"), required=False, allow_blank=True)
    sort = SortListField(
        allowed_fields=WHITELIST_LIST_SORT_FIELDS,
        default_sort=DEFAULT_WHITELIST_LIST_SORT,
        field_descriptions=WHITELIST_LIST_SORT_FIELD_DESCRIPTIONS,
    )
    page = serializers.IntegerField(label=gettext_lazy("页码"), required=False, min_value=1, default=1)
    page_size = serializers.IntegerField(
        label=gettext_lazy("每页数量"), required=False, min_value=1, max_value=100, default=10
    )


class UpdateRiskWhitelistReqSerializer(serializers.Serializer):
    id = serializers.IntegerField(label=gettext_lazy("白名单ID"))
    match_scope = serializers.JSONField(label=gettext_lazy("匹配范围"))
    reason = serializers.CharField(label=gettext_lazy("加白原因"), max_length=500)
    duration_days = DurationDaysField(label=gettext_lazy("有效天数"), required=False, allow_null=True)
    expire_at = serializers.DateTimeField(label=gettext_lazy("到期时间"), required=False, allow_null=True)


class RiskWhitelistIdReqSerializer(serializers.Serializer):
    id = serializers.IntegerField(label=gettext_lazy("白名单ID"))


class RejectRiskWhitelistReqSerializer(RiskWhitelistIdReqSerializer):
    reason = serializers.CharField(label=gettext_lazy("驳回理由"), allow_blank=False)


class RenewRiskWhitelistReqSerializer(RiskWhitelistIdReqSerializer):
    duration_days = DurationDaysField(label=gettext_lazy("有效天数"), required=True, allow_null=False)
    expire_at = serializers.DateTimeField(label=gettext_lazy("到期时间"), required=False, allow_null=True)
    remark = serializers.CharField(
        label=gettext_lazy("备注"), required=False, allow_blank=True, default="", max_length=500
    )


class ListWhitelistHitRecordReqSerializer(RiskWhitelistIdReqSerializer):
    page = serializers.IntegerField(label=gettext_lazy("页码"), required=False, min_value=1, default=1)
    page_size = serializers.IntegerField(
        label=gettext_lazy("每页数量"), required=False, min_value=1, max_value=100, default=10
    )
    action = serializers.CharField(label=gettext_lazy("命中动作"), required=False, allow_blank=True)
    risk_id = serializers.CharField(label=gettext_lazy("风险ID"), required=False, allow_blank=True)


class FetchWhitelistHitEventReqSerializer(RiskWhitelistIdReqSerializer):
    hit_id = serializers.IntegerField(label=gettext_lazy("命中记录ID"))


class RiskWhitelistCallbackReqSerializer(serializers.Serializer):
    callback_token = serializers.CharField(label=gettext_lazy("回调鉴权Token"))
    ticket = serializers.DictField(label=gettext_lazy("工单详情"))

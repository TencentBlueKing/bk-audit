# -*- coding: utf-8 -*-
"""风险白名单接口入参。"""

from django.utils.translation import gettext_lazy
from rest_framework import serializers

from services.web.risk.serializers import (
    BULK_ACTION_MAX_RISK_IDS,
    BulkRiskSelectionSerializer,
)


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


class ListRiskWhitelistReqSerializer(serializers.Serializer):
    scene_id = serializers.IntegerField(label=gettext_lazy("场景ID"), required=False)
    id = serializers.CharField(label=gettext_lazy("白名单ID"), required=False, allow_blank=True)
    status = serializers.CharField(label=gettext_lazy("状态"), required=False, allow_blank=True)
    whitelist_type = serializers.CharField(label=gettext_lazy("加白类型"), required=False, allow_blank=True)
    reason = serializers.CharField(label=gettext_lazy("加白原因"), required=False, allow_blank=True)
    updated_by = serializers.CharField(label=gettext_lazy("更新人"), required=False, allow_blank=True)
    keyword = serializers.CharField(label=gettext_lazy("关键字"), required=False, allow_blank=True)
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

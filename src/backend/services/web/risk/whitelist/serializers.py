# -*- coding: utf-8 -*-
"""风险白名单接口入参。"""

from django.utils.translation import gettext_lazy
from rest_framework import serializers


class RiskWhitelistScopeSerializer(serializers.Serializer):
    scene_id = serializers.IntegerField(label=gettext_lazy("场景ID"), required=False)
    match_scope = serializers.JSONField(label=gettext_lazy("匹配范围"))
    whitelist_type = serializers.CharField(label=gettext_lazy("加白类型"))
    reason = serializers.CharField(label=gettext_lazy("加白原因"), max_length=500)
    is_permanent = serializers.BooleanField(label=gettext_lazy("是否永久"), required=False)
    duration_days = serializers.IntegerField(label=gettext_lazy("有效天数"), required=False, allow_null=True, min_value=1)


class CreateRiskWhitelistReqSerializer(RiskWhitelistScopeSerializer):
    risk_id = serializers.CharField(label=gettext_lazy("风险ID"), required=False, allow_blank=True)
    risk_ids = serializers.ListField(label=gettext_lazy("风险ID列表"), child=serializers.CharField(), required=False)


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


class RiskWhitelistIdReqSerializer(serializers.Serializer):
    id = serializers.IntegerField(label=gettext_lazy("白名单ID"))


class RejectRiskWhitelistReqSerializer(RiskWhitelistIdReqSerializer):
    reason = serializers.CharField(label=gettext_lazy("驳回理由"), allow_blank=False)


class RenewRiskWhitelistReqSerializer(RiskWhitelistIdReqSerializer):
    duration_days = serializers.IntegerField(label=gettext_lazy("有效天数"), min_value=1)


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

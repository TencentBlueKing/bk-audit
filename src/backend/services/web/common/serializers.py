# -*- coding: utf-8 -*-

from rest_framework import serializers

from services.web.common.constants import ScopeQueryField, ScopeType


class ScopeQuerySerializer(serializers.Serializer):
    """通用 scope 查询参数。"""

    scope_type = serializers.ChoiceField(choices=ScopeType.choices, required=True)
    scope_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate(self, attrs: dict) -> dict:
        attrs = super().validate(attrs)
        scope_type = attrs[ScopeQueryField.SCOPE_TYPE]

        if scope_type in {ScopeType.SCENE, ScopeType.SYSTEM} and not attrs.get(ScopeQueryField.SCOPE_ID):
            raise serializers.ValidationError({ScopeQueryField.SCOPE_ID: "该字段是必填项。"})

        if scope_type in {ScopeType.CROSS_SCENE, ScopeType.CROSS_SYSTEM}:
            attrs[ScopeQueryField.SCOPE_ID] = None

        return attrs


class OptionalScopeQuerySerializer(ScopeQuerySerializer):
    """可选 scope 查询参数。

    - 不传 scope_type/scope_id：表示不按 scope 过滤
    - 仅传 scope_id：校验失败
    - 传 scope_type：沿用 ScopeQuerySerializer 的校验规则
    """

    scope_type = serializers.ChoiceField(choices=ScopeType.choices, required=False, allow_null=True)
    scope_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate(self, attrs: dict) -> dict:
        scope_type = attrs.get(ScopeQueryField.SCOPE_TYPE)
        scope_id = attrs.get(ScopeQueryField.SCOPE_ID)

        if not scope_type:
            if scope_id:
                raise serializers.ValidationError({ScopeQueryField.SCOPE_TYPE: "传入 scope_id 时必须同时传入 scope_type。"})
            attrs.pop(ScopeQueryField.SCOPE_TYPE, None)
            attrs.pop(ScopeQueryField.SCOPE_ID, None)
            return attrs

        return super().validate(attrs)

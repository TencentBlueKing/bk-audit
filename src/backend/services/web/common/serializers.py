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

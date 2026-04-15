# -*- coding: utf-8 -*-
from typing import List, Optional

from rest_framework import serializers

from services.web.common.constants import ScopeQueryField, ScopeType


class ScopeQuerySerializer(serializers.Serializer):
    """通用 scope 查询参数。"""

    scope_type = serializers.ChoiceField(choices=ScopeType.choices, required=True)
    scope_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    # 子类可覆盖：限制允许的 scope_type
    allowed_scope_types: Optional[List[ScopeType]] = None

    def validate(self, attrs: dict) -> dict:
        attrs = super().validate(attrs)
        scope_type = attrs[ScopeQueryField.SCOPE_TYPE]

        if self.allowed_scope_types and scope_type not in self.allowed_scope_types:
            raise serializers.ValidationError(
                {ScopeQueryField.SCOPE_TYPE: f"不支持的 scope_type，可选值：{', '.join(self.allowed_scope_types)}"}
            )

        if scope_type in {ScopeType.SCENE, ScopeType.SYSTEM} and not attrs.get(ScopeQueryField.SCOPE_ID):
            raise serializers.ValidationError({ScopeQueryField.SCOPE_ID: "该字段是必填项。"})

        if scope_type in {ScopeType.CROSS_SCENE, ScopeType.CROSS_SYSTEM}:
            attrs[ScopeQueryField.SCOPE_ID] = None

        return attrs

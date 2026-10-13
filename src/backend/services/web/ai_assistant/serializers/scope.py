"""资源集合查询的 Scope 参数：有业务 UID 时由资源派生，否则显式选范围。"""

from rest_framework import serializers

from services.web.common.constants import ScopeType
from services.web.common.serializers import OptionalScopeQuerySerializer


class ResourceScopeQuerySerializer(OptionalScopeQuerySerializer):
    """限定资源的 UID 替代重复的查询 Scope，不允许无边界集合查询。"""

    resource_uid_fields = ()
    scope_type = serializers.ChoiceField(
        choices=ScopeType.choices,
        required=False,
        help_text="无资源 UID 时必填；有资源 UID 时按资源真实归属鉴权，忽略重复 Scope",
    )
    scope_id = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text="无资源 UID 的 scene/system 查询必填；cross 查询省略",
    )

    def validate(self, attrs):
        """资源查询移除重复 Scope，普通集合查询沿用 concrete/cross 校验。"""
        if any(attrs.get(name) for name in self.resource_uid_fields):
            attrs.pop("scope_type", None)
            attrs.pop("scope_id", None)
        elif not attrs.get("scope_type"):
            raise serializers.ValidationError({"scope_type": "未指定资源 UID 时必须传入查询范围。"})
        return super().validate(attrs)

# -*- coding: utf-8 -*-
from django.utils.translation import gettext_lazy
from rest_framework import serializers

from core.constants import OrderTypeChoices
from core.utils.params import parse_nested_params


class ChoiceListSerializer(serializers.Serializer):
    """
    Choice List
    """

    label = serializers.CharField(label=gettext_lazy("Label"), allow_blank=True, allow_null=True)
    value = serializers.CharField(label=gettext_lazy("Value"))
    config = serializers.JSONField(label=gettext_lazy("Config"), required=False)


class OrderBaseSerializer(serializers.Serializer):
    order_field = serializers.CharField(label=gettext_lazy("排序字段"), required=False, allow_null=True, allow_blank=True)
    order_type = serializers.ChoiceField(
        label=gettext_lazy("排序方式"), default=OrderTypeChoices.DESC.value, choices=OrderTypeChoices.choices
    )


class OrderSerializer(OrderBaseSerializer):
    def validate(self, attrs: dict) -> dict:
        order_field = attrs.pop("order_field", "")
        order_type = attrs.pop("order_type", OrderTypeChoices.ASC.value)
        if not order_field:
            return attrs
        attrs["sort"] = [order_field] if order_type == OrderTypeChoices.ASC.value else [f"-{order_field}"]
        return attrs


class ExtraDataSerializerMixin(serializers.Serializer):
    """支持额外字段的序列化器"""

    parse_nested_data = True

    def to_internal_value(self, data):
        """
        重写此方法，以便在接收额外字段时，能将它们也包含在 validated_data 中
        """
        # 获取原有的字段
        validated_data = super().to_internal_value(data)

        # 获取额外的字段（不在预定义字段中的字段）
        extra_fields = {key: value for key, value in data.items() if key not in validated_data}

        # 将额外的字段添加到 validated_data 中
        validated_data.update(extra_fields)

        # 解析嵌套数据
        if self.parse_nested_data:
            validated_data = parse_nested_params(validated_data)
        return validated_data

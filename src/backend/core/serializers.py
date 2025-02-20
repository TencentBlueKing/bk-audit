# -*- coding: utf-8 -*-
from django.utils.translation import gettext_lazy
from rest_framework import serializers

from core.constants import OrderTypeChoices


class ChoiceListSerializer(serializers.Serializer):
    """
    Choice List
    """

    label = serializers.CharField(label=gettext_lazy("Label"), allow_blank=True, allow_null=True)
    value = serializers.CharField(label=gettext_lazy("Value"))
    config = serializers.JSONField(label=gettext_lazy("Config"), required=False)


class OrderSerializer(serializers.Serializer):
    order_field = serializers.CharField(label=gettext_lazy("排序字段"), required=False, allow_null=True, allow_blank=True)
    order_type = serializers.ChoiceField(
        label=gettext_lazy("排序方式"), default=OrderTypeChoices.DESC.value, choices=OrderTypeChoices.choices
    )

    def validate(self, attrs: dict) -> dict:
        order_field = attrs.pop("order_field", "")
        order_type = attrs.pop("order_type", OrderTypeChoices.ASC.value)
        if not order_field:
            return attrs
        attrs["sort"] = [order_field] if order_type == OrderTypeChoices.ASC.value else [f"-{order_field}"]
        return attrs

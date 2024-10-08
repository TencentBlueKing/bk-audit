# -*- coding: utf-8 -*-
from django.utils.translation import gettext_lazy
from rest_framework import serializers


class ChoiceListSerializer(serializers.Serializer):
    """
    Choice List
    """

    label = serializers.CharField(label=gettext_lazy("Label"), allow_blank=True, allow_null=True)
    value = serializers.CharField(label=gettext_lazy("Value"))
    config = serializers.JSONField(label=gettext_lazy("Config"), required=False)

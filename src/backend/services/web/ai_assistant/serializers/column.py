from django.utils.translation import gettext_lazy
from rest_framework import serializers


class ColumnConfigFieldSerializer(serializers.Serializer):
    """可选字段元数据（raw_name / 展示名 / 是否锁死列）。"""

    raw_name = serializers.CharField(label=gettext_lazy("字段名"))
    display_name = serializers.CharField(label=gettext_lazy("展示名"))
    is_locked = serializers.BooleanField(label=gettext_lazy("是否固定列"))


class ColumnConfigResponseSerializer(serializers.Serializer):
    """展示字段配置：可选字段 + 当前用户已选字段。"""

    available_fields = ColumnConfigFieldSerializer(many=True, label=gettext_lazy("可选字段"))
    selected_fields = serializers.ListField(
        child=serializers.CharField(), label=gettext_lazy("已选字段")
    )


class ColumnConfigApplyRequestSerializer(serializers.Serializer):
    """应用展示字段选择：提交字段名列表（固定列可缺省，后端自动补齐）。"""

    fields = serializers.ListField(
        child=serializers.CharField(min_length=1),
        label=gettext_lazy("选择的字段"),
        allow_empty=True,
    )


class ColumnConfigApplyResponseSerializer(serializers.Serializer):
    """应用后返回规范化结果（固定列在前 + 自选列按提交顺序）。"""

    selected_fields = serializers.ListField(
        child=serializers.CharField(), label=gettext_lazy("已选字段")
    )

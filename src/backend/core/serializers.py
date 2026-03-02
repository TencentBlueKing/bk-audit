# -*- coding: utf-8 -*-
import datetime
from collections import OrderedDict

from django.utils import timezone
from django.utils.encoding import force_str
from django.utils.translation import gettext_lazy
from rest_framework import serializers
from rest_framework.settings import api_settings

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


class AnyValueField(serializers.Field):
    """无损传递任意 JSON 值，不做转换或格式化"""

    def to_internal_value(self, data):
        return data

    def to_representation(self, value):
        return value


class ChoiceDisplayField(serializers.Field):
    """
    枚举字段，自动将值翻译为 label 显示

    Usage:
        risk_label = ChoiceDisplayField(choices=RiskLabel, label="风险标签")
    """

    def __init__(self, choices, **kwargs):
        """
        Args:
            choices: Django TextChoices 或 IntegerChoices 枚举类
        """
        self.choices = choices
        super().__init__(**kwargs)

    def to_representation(self, value):
        if value is None:
            return None
        # 使用标准 Django Choices 获取 label
        choices_dict = dict(self.choices.choices)
        return str(choices_dict.get(value, value))

    def to_internal_value(self, data):
        raise NotImplementedError("ChoiceDisplayField is read-only and does not support input")


class FriendlyDateTimeField(serializers.DateTimeField):
    """
    友好时间字段，输出本地时区的标准格式时间

    默认格式: "2025-01-19 21:00:00"

    Usage:
        event_time = FriendlyDateTimeField(label="首次发现时间")
        # 或自定义格式
        event_time = FriendlyDateTimeField(format="%Y年%m月%d日 %H:%M", label="首次发现时间")
    """

    def __init__(self, **kwargs):
        # 默认格式: 标准可读格式
        kwargs.setdefault("format", api_settings.DATETIME_FORMAT)
        super().__init__(**kwargs)

    def to_representation(self, value):
        if value is None:
            return None
        # 转换为本地时区
        if hasattr(value, "astimezone"):
            value = value.astimezone(timezone.get_default_timezone())
        return super().to_representation(value)


class CommaSeparatedListField(serializers.Field):
    """
    列表字段，将列表转换为英文逗号分隔的字符串

    Usage:
        operator = CommaSeparatedListField(label="责任人")

    示例：
        输入: ["user1", "user2"] -> 输出: "user1,user2"
        输入: None -> 输出: ""
        输入: [] -> 输出: ""
    """

    def to_representation(self, value):
        if value is None or value == []:
            return ""
        if isinstance(value, list):
            return ",".join(str(item) for item in value if item)
        return str(value) if value else ""

    def to_internal_value(self, data):
        raise NotImplementedError("CommaSeparatedListField is read-only and does not support input")


class TimestampIntegerField(serializers.IntegerField):
    """用于将日期时间字段序列化为毫秒级整型时间戳的 IntegerField。"""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("required", False)
        kwargs.setdefault("allow_null", True)
        super().__init__(*args, **kwargs)

    @staticmethod
    def _to_ms_timestamp(value: datetime.datetime) -> int:
        if timezone.is_naive(value):
            value = timezone.make_aware(value, timezone.get_current_timezone())
        return int(value.timestamp() * 1000)

    def to_representation(self, value):
        if value in (None, ""):
            return None
        if isinstance(value, datetime.datetime):
            return self._to_ms_timestamp(value)
        if isinstance(value, float):
            value = int(value)
        return super().to_representation(value)


class FieldType(object):
    BOOLEAN = "Boolean"
    NUMBER = "Number"
    STRING = "String"
    INTEGER = "Integer"
    OBJECT = "Object"
    ARRAY = "Array"
    ENUM = "Enum"
    JSON = "Json"


def get_serializer_fields(serializer_class):
    """
    遍历serializer所有field，生成关于该serializer的schema列表
    """

    if not serializer_class:
        return []

    serializer = serializer_class()

    if isinstance(serializer, serializers.ListSerializer):
        return []

    if not isinstance(serializer, serializers.Serializer):
        return []

    fields = []
    for field in list(serializer.fields.values()):
        if field.read_only or isinstance(field, serializers.HiddenField):
            continue

        fields.append(field_to_schema(field))

    return fields


def field_to_schema(field):
    """
    根据serializer field生成关于该field数据结构的schema
    """
    description = force_str(field.label) if field.label else ""

    type_params = {
        "type": FieldType.STRING,
    }

    if isinstance(field, (serializers.ListSerializer, serializers.ListField)):
        child_schema = field_to_schema(field.child)
        type_params = {"type": FieldType.ARRAY, "items": child_schema}
    elif isinstance(field, serializers.Serializer):
        type_params = {
            "type": FieldType.OBJECT,
            "properties": OrderedDict([(key, field_to_schema(value)) for key, value in list(field.fields.items())]),
        }
    elif isinstance(field, serializers.JSONField):
        type_params = {
            "type": FieldType.JSON,
        }
    elif isinstance(field, serializers.RelatedField):
        type_params = {
            "type": FieldType.STRING,
        }
    elif isinstance(field, (serializers.MultipleChoiceField, serializers.ChoiceField)):
        type_params = {
            "type": FieldType.ENUM,
            "choices": list(field.choices.keys()),
        }
    elif isinstance(field, serializers.BooleanField):
        type_params = {
            "type": FieldType.BOOLEAN,
        }
    elif isinstance(field, (serializers.DecimalField, serializers.FloatField)):
        type_params = {
            "type": FieldType.NUMBER,
        }
    elif isinstance(field, serializers.IntegerField):
        type_params = {
            "type": FieldType.INTEGER,
        }

    type_params.update(
        {
            "required": field.required,
            "name": field.field_name,
            "source_name": field.source,
            "description": description,
            "default": field.default,
        }
    )
    return type_params

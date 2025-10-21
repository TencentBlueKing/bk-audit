# -*- coding: utf-8 -*-
from collections import OrderedDict

from django.utils.encoding import force_str
from django.utils.translation import gettext_lazy
from rest_framework import serializers
from rest_framework.fields import empty

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
    # elif isinstance(field, serializers.ManyRelatedField):
    #     type_params = {
    #         "type": FieldType.ARRAY,
    #         "items": FieldType.STRING,
    #     }
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


def render_schema(fields, parent="", using_source=False):
    """
    将field schema渲染成apidoc的格式
    :param fields: schema list
    :param parent: field name of parent
    :param using_source: using source name of the field
    :return: list
    """
    print_list = []
    for field in fields:
        real_type = field["type"]
        field_name = field["source_name"] if using_source else field["name"]
        origin_name = "{}.{}".format(parent, field_name) if parent else field_name
        real_name = origin_name
        if field["type"] == FieldType.ARRAY:
            real_type = "%s[]" % field["items"]["type"]
        elif field["type"] == FieldType.ENUM:
            choices = ",".join(['"%s"' % c for c in field["choices"]])
            real_type = "{}={}".format(FieldType.STRING, choices)
        if field["default"] is not empty:
            real_name = "{}={}".format(real_name, field["default"])
        if not field["required"]:
            real_name = "[%s]" % real_name
        print_list.append("{{{}}} {} {}".format(real_type, real_name, field["description"]))

        if field["type"] == FieldType.ARRAY and field["items"]["type"] == FieldType.OBJECT:
            print_list += render_schema(
                fields=list(field["items"]["properties"].values()),
                parent=origin_name,
                using_source=using_source,
            )
        elif field["type"] == FieldType.OBJECT:
            print_list += render_schema(
                fields=list(field["properties"].values()),
                parent=origin_name,
                using_source=using_source,
            )
    return print_list

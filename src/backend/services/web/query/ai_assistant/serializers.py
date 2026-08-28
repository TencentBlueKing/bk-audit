"""日志 MCP 的 Pydantic/DRF 协议适配。

领域模型仍是 Task 3-5 的唯一协议事实。这里仅使用 drf-pydantic 生成
Serializer，并为 URL path 的 ``namespace`` 增加最薄封装；不维护平行字段定义。
"""

from collections.abc import Mapping
from copy import copy

from drf_pydantic.config import DrfConfigDict
from drf_pydantic.parse import create_serializer_from_model
from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError
from rest_framework import serializers

from services.web.query.ai_assistant.log_tools.schemas import (
    AggregateLogsRequest,
    AggregateLogsResponse,
    GetLogFieldMetadataRequest,
    GetLogFieldMetadataResponse,
    SearchLogsRequest,
    SearchLogsResponse,
)

_DRF_CONFIG = DrfConfigDict(validate_pydantic=True, validation_error="drf", backpopulate_after_validation=True)
_RESPONSE_DRF_CONFIG = DrfConfigDict(
    validate_pydantic=True, validation_error="drf", backpopulate_after_validation=False
)


class NamespacePathRequestSerializerMixin(serializers.Serializer):
    """在 DRF 丢弃未知键前校验原始 body，并只承接 Router 注入的 namespace。"""

    PydanticRequestModel: type[BaseModel]
    namespace = serializers.CharField(
        write_only=True,
        help_text="命名空间，仅由 URL path 注入；请求体不应提供该字段。",
    )

    def run_validation(self, data=serializers.empty):
        if data is not serializers.empty and not isinstance(data, Mapping):
            raise serializers.ValidationError({"body": ["请求体必须为 JSON 对象。"]})
        return super().run_validation(data)

    def to_internal_value(self, data):
        payload = copy(data)
        payload.pop("namespace", None)
        try:
            self.PydanticRequestModel.model_validate(payload)
        except PydanticValidationError as err:
            errors = {}
            for item in err.errors():
                path = ".".join(str(part) for part in item["loc"]) or "body"
                message = "不允许未知字段" if item["type"] == "extra_forbidden" else item["msg"]
                errors.setdefault(path, []).append(message)
            raise serializers.ValidationError(errors) from err
        return super().to_internal_value(data)

    def is_valid(self, *, raise_exception=False):
        """让 Resource SDK 不把本接口的请求校验错误包装为 500。"""

        is_valid = super().is_valid(raise_exception=False)
        if not is_valid:
            raise serializers.ValidationError(self.errors)
        return is_valid

    def validate(self, attrs):
        namespace = attrs.pop("namespace")
        attrs = super().validate(attrs)
        attrs["namespace"] = namespace
        return attrs


class GetLogFieldMetadataRequestSerializer(
    NamespacePathRequestSerializerMixin,
    create_serializer_from_model(GetLogFieldMetadataRequest, _DRF_CONFIG),
):
    """字段探索请求的生成 Serializer，加上 URL path namespace。"""

    PydanticRequestModel = GetLogFieldMetadataRequest


class GetLogFieldMetadataResponseSerializer(
    create_serializer_from_model(GetLogFieldMetadataResponse, _RESPONSE_DRF_CONFIG)
):
    """字段探索响应的生成 Serializer。"""


class SearchLogsRequestSerializer(
    NamespacePathRequestSerializerMixin,
    create_serializer_from_model(SearchLogsRequest, _DRF_CONFIG),
):
    """明细检索请求的生成 Serializer，加上 URL path namespace。"""

    PydanticRequestModel = SearchLogsRequest


class SearchLogsResponseSerializer(create_serializer_from_model(SearchLogsResponse, _RESPONSE_DRF_CONFIG)):
    """明细检索响应的生成 Serializer。"""


class AggregateLogsRequestSerializer(
    NamespacePathRequestSerializerMixin,
    create_serializer_from_model(AggregateLogsRequest, _DRF_CONFIG),
):
    """聚合请求的生成 Serializer，加上 URL path namespace。"""

    PydanticRequestModel = AggregateLogsRequest


class AggregateLogsResponseSerializer(create_serializer_from_model(AggregateLogsResponse, _RESPONSE_DRF_CONFIG)):
    """聚合响应的生成 Serializer。"""

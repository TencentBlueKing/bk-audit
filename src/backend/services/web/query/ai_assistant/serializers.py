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

from services.web.query.ai_assistant.exceptions import (
    InvalidLogCondition,
    LogToolException,
    UnsupportedAggregation,
    UnsupportedLogField,
)
from services.web.query.ai_assistant.log_tools.schemas import (
    AggregateLogsRequest,
    AggregateLogsResponse,
    GetLogFieldMetadataRequest,
    GetLogFieldMetadataResponse,
    SearchLogsRequest,
    SearchLogsResponse,
)

_DRF_CONFIG = DrfConfigDict(validate_pydantic=False, backpopulate_after_validation=False)
_RESPONSE_DRF_CONFIG = DrfConfigDict(
    validate_pydantic=True, validation_error="drf", backpopulate_after_validation=False
)


class NamespacePathRequestSerializerMixin(serializers.Serializer):
    """在 DRF 丢弃未知键前校验原始 body，并只承接 Router 注入的 namespace。"""

    PydanticRequestModel: type[BaseModel]
    field_error_roots: frozenset[str] = frozenset()
    condition_error_roots: frozenset[str] = frozenset()
    aggregation_error_roots: frozenset[str] = frozenset()
    nested_field_error_roots: frozenset[str] = frozenset()
    model_error: type[LogToolException] | None = None
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
            domain_error = self.get_domain_validation_error(err)
            if domain_error is not None:
                # 公开 MCP 只返回稳定领域码；Pydantic input_value 不进入异常链和响应。
                raise domain_error() from None
            errors = {}
            for item in err.errors():
                path = ".".join(str(part) for part in item["loc"]) or "body"
                message = "不允许未知字段" if item["type"] == "extra_forbidden" else item["msg"]
                errors.setdefault(path, []).append(message)
            raise serializers.ValidationError(errors) from err
        return super().to_internal_value(data)

    def get_domain_validation_error(self, error: PydanticValidationError) -> type[LogToolException] | None:
        """将已知业务字段的校验失败映射为稳定领域异常，未知请求键仍由 DRF 展示。"""

        locations = self._error_locations(error)
        roots = {location[0] for location in locations if location}
        condition_field_error = any(
            item["type"] == "value_error"
            and item["loc"]
            and item["loc"][0] == "condition"
            and ("field" in item["loc"][1:] or "operator" in item["loc"][1:])
            for item in error.errors()
        )
        if (
            condition_field_error
            or roots & self.field_error_roots
            or any(
                location and location[0] in self.nested_field_error_roots and "field" in location
                for location in locations
            )
        ):
            return UnsupportedLogField
        if "condition" in roots or roots & self.condition_error_roots:
            return InvalidLogCondition
        if roots & self.aggregation_error_roots:
            return UnsupportedAggregation
        if not roots:
            return self.model_error
        return None

    @staticmethod
    def _error_locations(error: PydanticValidationError) -> tuple[tuple[str, ...], ...]:
        return tuple(tuple(str(part) for part in item["loc"]) for item in error.errors())

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
    field_error_roots = frozenset(("parent_field",))
    model_error = UnsupportedLogField


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
    condition_error_roots = frozenset(("page", "page_size"))
    field_error_roots = frozenset(("fields", "sort"))
    model_error = UnsupportedLogField


class SearchLogsResponseSerializer(create_serializer_from_model(SearchLogsResponse, _RESPONSE_DRF_CONFIG)):
    """明细检索响应的生成 Serializer。"""


class AggregateLogsRequestSerializer(
    NamespacePathRequestSerializerMixin,
    create_serializer_from_model(AggregateLogsRequest, _DRF_CONFIG),
):
    """聚合请求的生成 Serializer，加上 URL path namespace。"""

    PydanticRequestModel = AggregateLogsRequest
    aggregation_error_roots = frozenset(("dimensions", "metrics", "order_by", "limit"))
    nested_field_error_roots = frozenset(("dimensions", "metrics"))
    model_error = UnsupportedAggregation


class AggregateLogsResponseSerializer(create_serializer_from_model(AggregateLogsResponse, _RESPONSE_DRF_CONFIG)):
    """聚合响应的生成 Serializer。"""

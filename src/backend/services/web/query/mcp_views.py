"""日志分析 Agent 的用户态 APIGW ViewSet。"""

from collections.abc import Mapping
from functools import wraps
from typing import Any, Dict

from bk_resource import resource
from bk_resource.viewsets import ResourceRoute
from drf_spectacular.types import OpenApiTypes
from rest_framework.exceptions import ValidationError

from core.utils.spectacular import BKResourceAutoSchema
from core.view_sets import UserAPIGWViewSet
from services.web.query.ai_assistant.log_tools.schemas import (
    AggregateLogsRequest,
    AggregateLogsResponse,
    GetLogFieldMetadataRequest,
    GetLogFieldMetadataResponse,
    SearchLogsRequest,
    SearchLogsResponse,
)


def reject_body_namespace(view_func):
    """在 ResourceViewSet 合并 path 参数前拒绝 body 中的 namespace。"""

    @wraps(view_func)
    def wrapper(view, request, *args, **kwargs):
        if not isinstance(request.data, Mapping):
            raise ValidationError({"body": ["请求体必须为 JSON 对象。"]})
        if "namespace" in request.data:
            raise ValidationError({"namespace": ["只能通过 URL path 提供。"]})
        return view_func(view, request, *args, **kwargs)

    return wrapper


class MCPLogAutoSchema(BKResourceAutoSchema):
    """为三个对 Agent 稳定暴露的日志工具固定 OpenAPI operationId。"""

    _OPERATION_IDS = {
        "field_metadata": "mcp_get_log_field_metadata",
        "search": "mcp_search_logs",
        "aggregate": "mcp_aggregate_logs",
    }
    _PYDANTIC_MODELS = {
        "field_metadata": (GetLogFieldMetadataRequest, GetLogFieldMetadataResponse),
        "search": (SearchLogsRequest, SearchLogsResponse),
        "aggregate": (AggregateLogsRequest, AggregateLogsResponse),
    }
    _ERROR_STATUS_CODES = (400, 403, 413, 502, 504)

    def get_operation_id(self):
        return self._OPERATION_IDS.get(self.view.action, super().get_operation_id())

    def get_response_serializers(self):
        if self.view.action in self._PYDANTIC_MODELS:
            return {200: OpenApiTypes.OBJECT}
        return super().get_response_serializers()

    def get_operation(self, *args, **kwargs):
        """用领域 Pydantic schema 覆盖三个固定工具的 OpenAPI body 与 data。"""

        operation = super().get_operation(*args, **kwargs)
        models = self._PYDANTIC_MODELS.get(self.view.action)
        if not models:
            return operation

        request_model, response_model = models
        request_schema = self._inline_pydantic_schema(request_model.model_json_schema(mode="validation"))
        response_schema = self._inline_pydantic_schema(response_model.model_json_schema(mode="serialization"))
        self._mark_model_dump_fields_required(response_schema)
        operation["requestBody"]["content"]["application/json"]["schema"] = request_schema
        operation["responses"]["200"]["content"]["application/json"]["schema"] = self._envelope_schema(response_schema)
        for status_code in self._ERROR_STATUS_CODES:
            operation["responses"][str(status_code)] = {
                "description": "平台标准错误响应",
                "content": {"application/json": {"schema": self._error_envelope_schema()}},
            }
        return operation

    @classmethod
    def _inline_pydantic_schema(
        cls, schema: Dict[str, Any], definitions: Dict[str, Any] | None = None
    ) -> Dict[str, Any]:
        """将三个工具的 Pydantic JSON Schema 转成 OpenAPI 3.0 Schema。"""

        definitions = definitions or schema.get("$defs", {})
        if "$ref" in schema:
            result = cls._inline_pydantic_schema(definitions[schema["$ref"].rsplit("/", 1)[-1]], definitions)
            siblings = {key: value for key, value in schema.items() if key != "$ref"}
            result.update(cls._inline_pydantic_schema(siblings, definitions))
            return result

        result: Dict[str, Any] = {}
        for key, value in schema.items():
            if key == "$defs":
                continue
            if key == "const":
                result["enum"] = [value]
                continue
            if (
                key in {"exclusiveMinimum", "exclusiveMaximum"}
                and isinstance(value, (int, float))
                and not isinstance(value, bool)
            ):
                result["minimum" if key == "exclusiveMinimum" else "maximum"] = value
                result[key] = True
                continue
            if key == "anyOf":
                non_null = [item for item in value if item.get("type") != "null"]
                if len(non_null) == 1 and len(non_null) != len(value):
                    result.update(cls._inline_pydantic_schema(non_null[0], definitions))
                    result["nullable"] = True
                else:
                    # anyOf 的分支可能重叠，例如整数同时属于 JSON Schema 的 integer
                    # 和 number；改成 oneOf 会让 OpenAPI 拒绝 Pydantic 接受的合法值。
                    result["anyOf"] = [cls._inline_pydantic_schema(item, definitions) for item in value]
                continue
            if isinstance(value, dict):
                result[key] = cls._inline_pydantic_schema(value, definitions)
            elif isinstance(value, list):
                result[key] = [
                    cls._inline_pydantic_schema(item, definitions) if isinstance(item, dict) else item for item in value
                ]
            else:
                result[key] = value
        return result

    @staticmethod
    def _envelope_schema(data_schema: Dict[str, Any]) -> Dict[str, Any]:
        """声明 UserAPIGWViewSet 实际渲染的标准成功响应。"""

        return {
            "type": "object",
            "required": ["result", "code", "message", "request_id", "trace_id", "data"],
            "properties": {
                "result": {"type": "boolean"},
                "code": {"type": "integer"},
                "message": {"type": "string", "nullable": True},
                "request_id": {"type": "string", "nullable": True},
                "trace_id": {"type": "string", "nullable": True},
                "data": data_schema,
            },
        }

    @staticmethod
    def _error_envelope_schema() -> Dict[str, Any]:
        """声明 APIRenderer 的标准错误响应；errors 为兼容诊断字段，不作为必填契约。"""

        return {
            "type": "object",
            "required": ["result", "code", "message", "request_id", "trace_id", "data"],
            "properties": {
                "result": {"type": "boolean"},
                "code": {
                    "oneOf": [{"type": "integer"}, {"type": "string"}],
                    "description": (
                        "日志工具稳定领域错误码：2926001 日志查询条件不合法、2926002 不支持的日志字段、"
                        "2926003 不支持的日志聚合方式、2926004 无敏感字段查询权限、"
                        "2926005 日志查询超时，请稍后重试、2926006 日志查询失败，请稍后重试、"
                        "2926007 日志查询结果过大，请缩小字段或 page_size 后重试；"
                        "也可能返回 IAM 或平台通用错误码。"
                    ),
                },
                "message": {"type": "string", "nullable": True},
                "request_id": {"type": "string", "nullable": True},
                "trace_id": {"type": "string", "nullable": True},
                "data": {"nullable": True},
                "errors": {"nullable": True},
            },
        }

    @classmethod
    def _mark_model_dump_fields_required(cls, schema: Dict[str, Any]) -> None:
        """Pydantic 的 model_dump 不省略默认值，响应 schema 也必须声明这些键。"""

        properties = schema.get("properties")
        if properties:
            schema["required"] = list(properties)
            for value in properties.values():
                cls._mark_model_dump_fields_required(value)
        if isinstance(schema.get("items"), dict):
            cls._mark_model_dump_fields_required(schema["items"])


class MCPUserLogViewSet(UserAPIGWViewSet):
    """Agent 日志分析的用户态工具入口，仅暴露字段、明细和聚合三个 POST 操作。"""

    schema = MCPLogAutoSchema()
    resource_routes = [
        ResourceRoute(
            "POST",
            resource.query.mcp_get_log_field_metadata,
            endpoint="field_metadata",
            decorators=[reject_body_namespace],
        ),
        ResourceRoute("POST", resource.query.mcp_search_logs, endpoint="search", decorators=[reject_body_namespace]),
        ResourceRoute(
            "POST", resource.query.mcp_aggregate_logs, endpoint="aggregate", decorators=[reject_body_namespace]
        ),
    ]

"""日志分析 Agent 的用户态 APIGW ViewSet。"""

from collections.abc import Mapping
from functools import wraps

from bk_resource import resource
from bk_resource.viewsets import ResourceRoute
from rest_framework.exceptions import ValidationError

from core.utils.spectacular import MCPToolAutoSchema
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


class MCPLogAutoSchema(MCPToolAutoSchema):
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

    _ERROR_CODE_DESCRIPTION = (
        "日志工具稳定领域错误码：2926001 日志查询条件不合法、2926002 不支持的日志字段、"
        "2926003 不支持的日志聚合方式、2926004 无敏感字段查询权限、"
        "2926005 日志查询超时，请稍后重试、2926006 日志查询失败，请稍后重试、"
        "2926007 日志查询结果过大，请缩小字段或 page_size 后重试、"
        "2926008 字段类型不支持当前统计操作、"
        "2926009 统计结果超出预算，请调整查询范围、类别数量或指标、"
        "2926010 统计结果过大，请缩短查询范围或减少返回规模；"
        "也可能返回 IAM 或平台通用错误码。"
    )
    _ERRORS_FIELD_DESCRIPTION = (
        "可选诊断信息。统计预算错误包含 suggested_interval（MINUTE/HOUR/DAY/MONTH 或 null）"
        "及受控 adjustments 调整建议；不回显 SQL 或字段值，工具分支仍按 code 判断。"
    )


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

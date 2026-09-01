"""日志分析 Agent 的用户态 MCP Resource。"""

from django.utils.translation import gettext_lazy

from core.models import get_request_username
from services.web.query.ai_assistant.log_tools.aggregation import LogAggregationService
from services.web.query.ai_assistant.log_tools.field_metadata import (
    LogFieldMetadataService,
)
from services.web.query.ai_assistant.log_tools.schemas import (
    AggregateLogsRequest,
    GetLogFieldMetadataRequest,
    SearchLogsRequest,
)
from services.web.query.ai_assistant.log_tools.search import LogDetailSearchService
from services.web.query.ai_assistant.serializers import (
    AggregateLogsRequestSerializer,
    AggregateLogsResponseSerializer,
    GetLogFieldMetadataRequestSerializer,
    GetLogFieldMetadataResponseSerializer,
    SearchLogsRequestSerializer,
    SearchLogsResponseSerializer,
)
from services.web.query.resources.base import QueryBaseResource


class MCPGetLogFieldMetadata(QueryBaseResource):
    """探索当前用户可查询日志字段的脱敏样例和下一层 JSON 路径。

    仅采样至多 50 条已脱敏日志，不递归展开对象字段；字段引用可用于明细查询，
    聚合使用时还需满足聚合工具的字段和类型限制。业务 data 载荷不超过 1 MiB。
    可恢复的参数、字段和权限错误维持平台标准错误响应。
    """

    name = gettext_lazy("MCP 获取日志字段元信息")
    RequestSerializer = GetLogFieldMetadataRequestSerializer
    ResponseSerializer = GetLogFieldMetadataResponseSerializer
    support_data_collect = False

    def perform_request(self, validated_request_data):
        data = dict(validated_request_data)
        namespace = data.pop("namespace")
        request = GetLogFieldMetadataRequest.model_validate(data)
        return LogFieldMetadataService.get_metadata(
            username=get_request_username(), namespace=namespace, request=request
        ).model_dump(mode="json")


class MCPSearchLogs(QueryBaseResource):
    """按受控字段分页返回当前用户可见、已脱敏的日志明细。

    省略 fields 时使用紧凑默认列；显式投影最多 20 列、页码和每页数量最多 100，运行
    配置只能收紧这些边界。业务 data 载荷不超过 1 MiB，且不含 SQL、表名或原始敏感行；
    超时可缩小时间范围后重试。
    """

    name = gettext_lazy("MCP 查询日志明细")
    RequestSerializer = SearchLogsRequestSerializer
    ResponseSerializer = SearchLogsResponseSerializer
    support_data_collect = False

    def perform_request(self, validated_request_data):
        data = dict(validated_request_data)
        namespace = data.pop("namespace")
        request = SearchLogsRequest.model_validate(data)
        return LogDetailSearchService.search(
            username=get_request_username(), namespace=namespace, request=request
        ).model_dump(mode="json")


class MCPAggregateLogs(QueryBaseResource):
    """对当前用户可访问日志执行类型化、受控的分组聚合。

    最多声明 2 个维度和 5 个指标，AUTO 时间桶由已验证时间范围决定实际粒度；文本或
    拓展数值转换质量在 data_quality 中返回，业务 data 载荷不超过 1 MiB。敏感字段无权限时不执行查询。
    """

    name = gettext_lazy("MCP 聚合日志")
    RequestSerializer = AggregateLogsRequestSerializer
    ResponseSerializer = AggregateLogsResponseSerializer
    support_data_collect = False

    def perform_request(self, validated_request_data):
        data = dict(validated_request_data)
        namespace = data.pop("namespace")
        request = AggregateLogsRequest.model_validate(data)
        return LogAggregationService.aggregate(
            username=get_request_username(), namespace=namespace, request=request
        ).model_dump(mode="json")

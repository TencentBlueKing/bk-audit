"""Agent/MCP 日志工具的公共协议、查询上下文和受控 SQL 构建器。"""

from .aggregation import LogAggregationService
from .context import LogQueryContext, LogQueryContextService
from .errors import map_log_query_error
from .field_metadata import LogFieldMetadataService
from .schemas import (
    FieldSampleSummary,
    GetLogFieldMetadataRequest,
    GetLogFieldMetadataResponse,
    LogDetailColumn,
    LogFieldMetadataItem,
    LogFieldMetadataTypeSource,
    LogFieldRef,
    LogFieldScope,
    LogSearchPagination,
    LogSortItem,
    SearchLogsRequest,
    SearchLogsResponse,
)
from .search import LogDetailSearchService
from .sql import ProjectedLogSQLBuilder

__all__ = [
    "FieldSampleSummary",
    "GetLogFieldMetadataRequest",
    "GetLogFieldMetadataResponse",
    "LogFieldMetadataItem",
    "LogAggregationService",
    "LogFieldMetadataService",
    "LogFieldMetadataTypeSource",
    "LogFieldRef",
    "LogFieldScope",
    "LogDetailColumn",
    "LogDetailSearchService",
    "LogSearchPagination",
    "LogSortItem",
    "LogQueryContext",
    "LogQueryContextService",
    "ProjectedLogSQLBuilder",
    "SearchLogsRequest",
    "SearchLogsResponse",
    "map_log_query_error",
]

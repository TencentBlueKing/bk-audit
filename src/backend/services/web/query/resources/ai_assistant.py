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
    """探索当前用户可查询的日志根字段或下一层 JSON 字段，返回脱敏元信息。

    Web 字段选择器与 MCP 共用该 Resource。Web 使用
    `POST /api/v1/query/namespaces/{namespace}/collector_query/field_metadata/`；
    namespace 从路径传入，身份来自当前请求，不在 body 提交 namespace 或 username。

    ### Case 1：打开程序统计字段选择器

    ```json
    {
      "condition": {
        "scope_type": "system",
        "scope_id": "your-system-id",
        "start_time": "2026-09-17 00:00:00",
        "end_time": "2026-09-17 23:59:59",
        "conditions": []
      }
    }
    ```

    将 condition 替换为来源 LOG_SEARCH 消息 input_data.condition 的完整内容，保留过滤条件。
    省略 parent_field 时返回声明的根字段，不查询 Doris 样本；sampling_performed=false，sampled_count=0 不代表无日志。
    日志总量应调用 COUNT，已取得的字段目录可复用，不要为了确认总量重复探索或扩大时间范围。

    ### Case 2：展开拓展字段

    ```json
    {
      "condition": {
        "scope_type": "system",
        "scope_id": "your-system-id",
        "start_time": "2026-09-17 00:00:00",
        "end_time": "2026-09-17 23:59:59",
        "conditions": []
      },
      "parent_field": {
        "raw_name": "extend_data",
        "keys": []
      }
    }
    ```

    下一次展开时用上一层返回的 field 替换 parent_field，保留完整 keys。
    每次仅探索下一层，至多采样 50 条脱敏日志，不递归展开全部路径。

    ### 如何使用返回值

    fields[].field 可传给后续工具或程序统计附件；is_expandable 控制展开入口，
    statistics_supported 控制统计选择提示，unsupported_reason 说明不可统计原因。
    对象可展开不等于本身可统计。类型和覆盖率可能来自样本，不保证全范围一致；
    执行统计时仍重新校验权限和真实类型。sample_summary.truncated 表示探索有截断，
    不代表目录中不存在其他 key。业务 data 载荷不超过 1 MiB；配置可收紧采样与大小限制。
    Web 使用登录用户身份，MCP 使用网关用户身份，均重验权限。

    | HTTP / code | 含义 | 调用方动作 |
    | --- | --- | --- |
    | 400 / 2926001、2926002 | 条件、字段或操作符非法 | 修正输入，操作符以 allow_operators 为准 |
    | 403 / 2926004 | 敏感字段权限不足 | 停止该字段查询，重新选择或申请权限 |
    | 504 / 2926005、502 / 2926006 | 查询超时或失败 | 稍后重试；持续失败保留请求标识排查 |
    | 413 / 2926007 | 探索响应过大 | 缩小探索范围 |

    认证、系统查询权限等其他错误遵循平台公共协议，以上不是完整错误清单。

    """

    name = gettext_lazy("获取日志字段元信息")
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

    省略 fields 时返回含 event_id 的紧凑证据列，JSON/完整日志按需显式投影；
    显式投影最多 20 列、页码为正整数且每页最多 100 条，运行
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

    维度和指标 id 必须全局唯一，不能使用 group_id/group_kind/log_count/log_ratio/bucket_start；COUNT 示例为 {"id":"cnt","type":"COUNT"}。
    DISTINCT_COUNT 只需 id/type/field，不传 value_type/percentile；order_by 仅控制类别TopN，不能引用时间维度，时间桶自动升序。
    最多声明 2 个维度和 5 个指标，AUTO 时间桶由已验证时间范围决定实际粒度；文本或
    拓展数值转换质量按全范围 present_count 返回；有类别默认 top_n=10、最大 500，无类别省略。
    时序 rows 仅返回有日志的桶，query_summary.sparse_time_buckets=true；缺省桶计数为0、数值指标为null。
    完整结果统一限制 1440 时间桶、100000 数值单元格及 4 MiB，不静默截断；敏感字段无权限时不执行查询。
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

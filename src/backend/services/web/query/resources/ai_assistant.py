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
    GetLogFieldMetadataTreeResponseSerializer,
    GetLogFieldMetadataWebRequestSerializer,
    SearchLogsRequestSerializer,
    SearchLogsResponseSerializer,
)
from services.web.query.resources.base import QueryBaseResource


class MCPGetLogFieldMetadata(QueryBaseResource):
    """字段、路径或操作符不明确时，探索当前用户可查询的字段及脱敏元信息。

    省略 parent_field 返回声明的根目录，不采样；sampled_count=0 不代表没有日志。
    指定 parent_field 时默认最多采样 100 条、返回 50 个直接子字段；继续展开应复用 field 的完整路径。
    JSON 根列先筛有效父对象，VARIANT 根列使用兼容采样；已取得的目录可复用，总量用 COUNT。

    子字段仅代表样本发现：空目录、is_expandable=false 均不证明全范围没有子键。
    目录类型、统计能力与 coverage 仅供参考，最终以全范围统计为准；对象可展开不等于可直接统计。
    truncated=true 表示采样或字段/解析预算等导致发现不完整；业务 data 最大 1 MiB。
    筛选使用返回的 allow_operators；权限拒绝时停止对应查询，查询失败不能当作零。
    """

    name = gettext_lazy("获取日志字段元信息")
    RequestSerializer = GetLogFieldMetadataRequestSerializer
    ResponseSerializer = GetLogFieldMetadataResponseSerializer

    def perform_request(self, validated_request_data):
        data = dict(validated_request_data)
        namespace = data.pop("namespace")
        include_descendants = data.pop("include_descendants", False)
        request = GetLogFieldMetadataRequest.model_validate(data)
        return LogFieldMetadataService.get_metadata(
            username=get_request_username(),
            namespace=namespace,
            request=request,
            include_descendants=include_descendants,
        ).model_dump(mode="json")


class GetLogFieldMetadata(MCPGetLogFieldMetadata):
    """前端日志检索、统计与分析的字段选择目录，不要求先创建附件。

    首次仅传 condition：返回基础字段，JSON 根字段 is_expandable=true，不采样。
    再传 parent_field 和 include_descendants=true：在该检索条件内一次采样最多100条日志，
    返回父路径自身及采样发现的全部对象后代，字段数量不截断；数组作为叶子。
    例如 parent_field={"raw_name":"extend_data","keys":["a"]} 返回 a、a.b、a.b.c、a.b.d。
    使用 field.raw_name+keys 分组、搜索及提交统计，is_expandable 仅用于层级展示，
    statistics_supported 决定统计能力提示；本响应已包含发现的后代，无需逐层重查。
    省略 include_descendants 时仅返回直接子字段（最多50个）。目录先脱敏再解析，
    sample_summary.truncated 表示采样/路径预算导致发现可能不全；业务data超过1 MiB返回413。
    namespace 来自 URL，body 不传；样本目录不是全范围字段全集，统计可直接提交合法自定义路径。
    """

    RequestSerializer = GetLogFieldMetadataWebRequestSerializer
    ResponseSerializer = GetLogFieldMetadataTreeResponseSerializer


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

    def perform_request(self, validated_request_data):
        data = dict(validated_request_data)
        namespace = data.pop("namespace")
        request = SearchLogsRequest.model_validate(data)
        return LogDetailSearchService.search(
            username=get_request_username(), namespace=namespace, request=request
        ).model_dump(mode="json")


class MCPAggregateLogs(QueryBaseResource):
    """对当前用户可访问日志执行类型化、受控的分组聚合，用于总量、分布和趋势。

    TopN 按全范围排名；OTHER 汇总剩余非缺失类别，MISSING 独立，比例分母为全范围总量。
    核对 query_summary 的范围、粒度及 complete，不从样例或 TopN 部分组推断总体。
    查询失败不能当作零，应按错误提示调整请求；权限拒绝时停止对应查询。

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

    def perform_request(self, validated_request_data):
        data = dict(validated_request_data)
        namespace = data.pop("namespace")
        request = AggregateLogsRequest.model_validate(data)
        return LogAggregationService.aggregate(
            username=get_request_username(), namespace=namespace, request=request
        ).model_dump(mode="json")

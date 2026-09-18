"""解析有界统计帧并验证完整性。

META/GROUP/ROW/QUALITY 必须来自同一最终 SQL；先核对数量和键，再组织公开 DTO。
不在 Python 排名或归并类别，不把无效/截断远端响应标记为完整。
"""
import re
from dataclasses import dataclass

from django.utils.translation import gettext_lazy

from services.web.query.ai_assistant.exceptions import (
    StatisticsBudgetExceeded,
    UnsupportedFieldType,
)
from services.web.query.ai_assistant.log_tools.schemas import (
    AggregateLogsRequest,
    AggregationDataQuality,
    AggregationDimensionType,
    AggregationGroup,
    AggregationGroupValue,
    AggregationMetricType,
)
from services.web.query.ai_assistant.log_tools.statistics_budget import (
    budget_limits,
    build_time_axis,
)
from services.web.query.ai_assistant.log_tools.statistics_summary import (
    StatisticsFieldSummary,
    parse_field_summary,
)
from services.web.query.ai_assistant.log_tools.statistics_types import (
    parse_statistics_scalar,
)


class UnsupportedStatisticsNumber(UnsupportedFieldType):
    """复用字段类型错误码，仅暴露固定的数值保真失败原因。"""

    MESSAGE = gettext_lazy("字段数值超出安全整数范围，或引擎数值文本转换无法无损往返")


def statistics_count(value) -> int:
    """接受 STRING 通道的非负整数；拒绝 bool/float、符号和非规范前导零。"""
    if not isinstance(value, str) or re.fullmatch(r"0|[1-9][0-9]*", value) is None or len(value) > 20:
        raise ValueError("invalid statistics count")
    return int(value)


@dataclass(frozen=True)
class StatisticsResult:
    """已验证且补齐时间轴的聚合结果，供可信后端消费者组织响应。"""

    groups: tuple[AggregationGroup, ...]
    rows: tuple[dict, ...]
    quality: tuple[AggregationDataQuality, ...]
    total_count: int
    field_summary: StatisticsFieldSummary | None = None


class StatisticsResultParser:
    """只接受最终语句的完整帧集合，不信任远端行序或请求外的字段。"""

    def __init__(self, request: AggregateLogsRequest, time_axis=None, numeric_columns=None, summary_field=None):
        """摘要字段由可信 builder 显式提供，普通 MCP 不能接收 SUMMARY。"""
        self.summary_field = summary_field
        self.request = request
        self.dimensions = tuple(d for d in request.dimensions if d.type == AggregationDimensionType.FIELD)
        self.time_dimension = next(
            (d for d in request.dimensions if d.type == AggregationDimensionType.TIME_BUCKET), None
        )
        self.time_axis = time_axis
        self.numeric_columns = numeric_columns if numeric_columns is not None else len(request.metrics) + 2
        self.quality_indices = {i for i, m in enumerate(request.metrics) if m.needs_conversion}

    def parse(self, response: dict) -> StatisticsResult:
        """校验协议/计数/键后返回业务结果；任何不一致抛 ValueError。"""
        if not isinstance(response, dict) or not isinstance(response.get("list"), list):
            raise ValueError("missing statistics frames")
        frames = response["list"]
        max_groups = self.request.top_n + 2 if self.dimensions else 1
        if len(frames) > 1 + int(self.summary_field is not None) + max_groups * (
            1 + (len(self.time_axis.bucket_starts) if self.time_axis else 1)
        ) + len(self.quality_indices):
            raise ValueError("unbounded statistics frames")
        by_type = {kind: [] for kind in ("META", "GROUP", "ROW", "QUALITY")}
        if self.summary_field is not None:
            by_type["SUMMARY"] = []
        for frame in frames:
            if not isinstance(frame, dict) or frame.get("frame") not in by_type:
                raise ValueError("invalid statistics frame")
            by_type[frame["frame"]].append(frame)
        if len(by_type["META"]) != 1:
            raise ValueError("missing or duplicate statistics meta")
        meta = by_type["META"][0]
        total, group_count, row_count, quality_count, invalid_type, invalid_number = (
            statistics_count(meta.get(key)) for key in ("n", "a", "b", "c", "d", "e")
        )
        if invalid_type:
            raise UnsupportedFieldType()
        if invalid_number:
            raise UnsupportedStatisticsNumber()
        if group_count > max_groups:
            raise ValueError("unbounded statistics groups")
        buckets = len(self.time_axis.bucket_starts) if self.time_axis else 1
        if group_count * buckets * self.numeric_columns > budget_limits()[1]:
            try:
                build_time_axis(
                    start_time=self.request.condition.start_time,
                    end_time=self.request.condition.end_time,
                    interval=self.time_axis.effective_interval if self.time_axis else None,
                    group_count=group_count,
                    numeric_columns=self.numeric_columns,
                )
            except StatisticsBudgetExceeded as err:
                err.actual_group_count = group_count
                raise
        if (len(by_type["GROUP"]), len(by_type["ROW"]), len(by_type["QUALITY"])) != (
            group_count,
            row_count,
            quality_count,
        ):
            raise ValueError("truncated statistics frames")
        if quality_count != len(self.quality_indices) or (not self.time_axis and row_count != group_count):
            raise ValueError("invalid statistics frame counts")
        groups = self._groups(by_type["GROUP"], total)
        rows = self._rows(by_type["ROW"], groups, total)
        quality = self._quality(by_type["QUALITY"], total)
        summary = None
        if self.summary_field is not None:
            summary = parse_field_summary(
                by_type["SUMMARY"], self.summary_field, groups.values(), total, statistics_count
            )
        return StatisticsResult(
            groups=tuple(groups.values()), rows=rows, quality=quality, total_count=total, field_summary=summary
        )

    def _groups(self, frames, total):
        """验证真实类别/合成组身份、稳定序号及全范围计数闭合。"""
        groups = {}
        seen_values = set()
        number_keys = {}
        for frame in frames:
            key = statistics_count(frame.get("frame_key"))
            count = statistics_count(frame.get("n"))
            kind = frame.get("kind")
            values = []
            if not self.dimensions:
                valid_kind = key == 1 and kind == "ALL"
            else:
                valid_kind = (
                    (kind == "VALUE" and 1 <= key <= self.request.top_n)
                    or (kind == "OTHER" and key == self.request.top_n + 1)
                    or (kind == "MISSING" and key == self.request.top_n + 2)
                ) and count > 0
            if key in groups or not valid_kind:
                raise ValueError("invalid or duplicate statistics group")
            for i, dimension in enumerate(self.dimensions):
                value_type, text = frame.get(f"d{i}_type"), frame.get(f"d{i}_json")
                if kind != "VALUE":
                    if value_type is not None or text is not None:
                        raise ValueError("synthetic statistics group has business value")
                    continue
                if value_type not in {"number", "string", "boolean"}:
                    raise ValueError("invalid statistics group scalar type")
                value = parse_statistics_scalar(value_type, text)
                if value_type == "number":
                    identity = (i, value)
                    if identity in number_keys and number_keys[identity] != text:
                        raise ValueError("different number keys collapse in output")
                    number_keys[identity] = text
                values.append(AggregationGroupValue(dimension_id=dimension.id, value_type=value_type, value=value))
            if kind == "VALUE":
                identity = tuple((v.value_type, v.value) for v in values)
                if identity in seen_values:
                    raise ValueError("duplicate statistics category")
                seen_values.add(identity)
            groups[key] = AggregationGroup(
                group_id=f"g{key}", kind=kind, values=tuple(values), count=count, ratio=count / total if total else None
            )
        value_keys = sorted(key for key, group in groups.items() if group.kind == "VALUE")
        if value_keys != list(range(1, len(value_keys) + 1)):
            raise ValueError("statistics category ranks are incomplete")
        if any(g.kind == "OTHER" for g in groups.values()) and len(value_keys) != self.request.top_n:
            raise ValueError("statistics OTHER misses selected categories")
        if sum(group.count for group in groups.values()) != total:
            raise ValueError("statistics group counts do not close")
        if (not self.dimensions and len(groups) != 1) or (self.dimensions and not total and groups):
            raise ValueError("invalid empty statistics groups")
        return dict(sorted(groups.items()))

    def _rows(self, frames, groups, total):
        """验证组/桶唯一及计数闭合，再补轴；非可加指标只保留原桶值。"""
        rows = {}
        counts = {key: 0 for key in groups}
        bucket_starts = self.time_axis.bucket_starts if self.time_axis else (None,)
        for frame in frames:
            key = statistics_count(frame.get("frame_key"))
            count = statistics_count(frame.get("n"))
            bucket = statistics_count(frame.get("bucket")) if self.time_axis else 0
            identity = (key, bucket)
            if key not in groups or identity in rows or bucket >= len(bucket_starts):
                raise ValueError("statistics row group/bucket mismatch")
            if self.time_axis and count == 0:
                raise ValueError("sparse statistics row must contain events")
            if not self.time_axis and count != groups[key].count:
                raise ValueError("statistics row group/count mismatch")
            counts[key] += count
            row = self._empty_row(groups[key], bucket_starts[bucket], total)
            row.update(log_count=count, log_ratio=count / total if total else None)
            for i, metric in enumerate(self.request.metrics):
                if f"m{i}" not in frame:
                    raise ValueError("statistics row misses metric")
                text = frame[f"m{i}"]
                if metric.type in {AggregationMetricType.COUNT, AggregationMetricType.DISTINCT_COUNT}:
                    value = statistics_count(text)
                    if value > count or (metric.type == AggregationMetricType.COUNT and value != count):
                        raise ValueError("statistics count metric mismatch")
                else:
                    value = None if text is None else parse_statistics_scalar("number", text)
                    if count == 0 and value is not None:
                        raise ValueError("statistics empty metric is not null")
                row[metric.id] = value
            rows[identity] = row
        if any(counts[key] != group.count for key, group in groups.items()):
            raise ValueError("statistics bucket counts do not close")
        if not self.time_axis and {key for key, _ in rows} != groups.keys():
            raise ValueError("statistics row groups are incomplete")
        return tuple(
            rows.get((key, index), self._empty_row(group, start, total))
            for key, group in groups.items()
            for index, start in enumerate(bucket_starts)
        )

    def _empty_row(self, group, bucket_start, total):
        """建立可公开的行身份；空桶计数为零，没有有效值的数值指标保持 null。"""
        row = dict(group_id=group.group_id, group_kind=group.kind.value, log_count=0, log_ratio=0.0 if total else None)
        row.update({d.id: None for d in self.dimensions})
        row.update({v.dimension_id: v.value for v in group.values})
        row.update(
            {
                m.id: 0 if m.type in {AggregationMetricType.COUNT, AggregationMetricType.DISTINCT_COUNT} else None
                for m in self.request.metrics
            }
        )
        if self.time_dimension:
            row[self.time_dimension.id] = bucket_start
        return row

    def _quality(self, frames, total):
        """质量计数覆盖完整原集合，空串计 present，失败转换不作为零。"""
        quality = {}
        for frame in frames:
            key = statistics_count(frame.get("frame_key"))
            if key not in self.quality_indices or key in quality:
                raise ValueError("invalid or duplicate statistics quality")
            present, converted, failed = (statistics_count(frame.get(k)) for k in ("n", "a", "b"))
            if present > total or present != converted + failed:
                raise ValueError("statistics quality counts do not close")
            quality[key] = AggregationDataQuality(
                metric_id=self.request.metrics[key].id,
                present_count=present,
                converted_count=converted,
                conversion_failed_count=failed,
            )
        if quality.keys() != self.quality_indices:
            raise ValueError("missing statistics quality")
        return tuple(quality[key] for key in sorted(quality))

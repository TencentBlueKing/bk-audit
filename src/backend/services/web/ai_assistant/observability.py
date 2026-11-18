"""AI 助手平台异步执行的指标、事件与 Trace 入口。

Message、Attachment、流式 Runtime 和失活巡检在各自生命周期节点构造类型化快照，
本模块只负责把脱敏、低基数快照转换为 Metric/Event/Trace。Metric/Event 复用
``core.monitor`` 最佳努力投递，Trace 复用 ``core.observability``。分层架构、生命周期和
接入约束见 ``services/web/ai_assistant/docs/observability.md``，具体指标与事件协议以
本模块的声明式类型为准。
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Collection

from django.conf import settings
from opentelemetry import trace

from core.monitor import Event, Metric, MetricDimension, MetricField
from core.observability import set_span_attributes, start_observation_span
from services.web.ai_assistant.constants import ExecutionObjectType


class AIAssistantExecutionMetric(Metric):
    """Message/Attachment 进入终态时上报执行量、阶段耗时和 SLO 结果。"""

    documentation = "AI 助手异步执行终态、阶段耗时与 SLO 达标情况"
    metric_fields = {
        "ai_assistant_execution_count": MetricField(
            documentation="赢得终态 CAS 并进入 SUCCESS 或 FAILED 的执行对象数",
            unit="count",
        ),
        "ai_assistant_execution_queue_duration_ms": MetricField(
            documentation="从任务投递到 Worker 首次开始的耗时；Worker 未启动时计算到执行终态",
            unit="ms",
        ),
        "ai_assistant_execution_duration_ms": MetricField(
            documentation="从 Worker 首次开始执行到对象进入终态的耗时，缺少开始时间时为 0",
            unit="ms",
        ),
        "ai_assistant_execution_total_duration_ms": MetricField(
            documentation="从对象首次创建到进入终态的用户总等待时间",
            unit="ms",
        ),
        "ai_assistant_execution_slo_met_count": MetricField(
            documentation="总收敛耗时满足对应 Message/Attachment SLO 时为 1，否则为 0",
            unit="count",
        ),
    }
    dimension_fields = {
        "object_type": MetricDimension(documentation="执行对象类型，固定为 MESSAGE 或 ATTACHMENT"),
        "business_type": MetricDimension(documentation="Handler 注册的消息或附件类型，必须是稳定低基数值"),
        "execution_mode": MetricDimension(documentation="执行模式，固定为 SYNC 或 ASYNC"),
        "is_stream": MetricDimension(documentation="是否使用流式执行，固定为 true 或 false"),
        "stage": MetricDimension(documentation="上报所在平台阶段，本指标组固定为 terminal"),
        "status": MetricDimension(documentation="执行终态，通常为 SUCCESS 或 FAILED"),
        "error_code": MetricDimension(documentation="平台或 Handler 返回的稳定错误码，成功时为空字符串"),
    }


class AIAssistantProcessingMetric(Metric):
    """巡检按对象、业务类型和存活年龄分桶上报扫描时的 PROCESSING 存量。"""

    documentation = "AI 助手 PROCESSING 存量、警告阈值和硬失效阈值聚合"
    metric_fields = {
        "ai_assistant_processing_count": MetricField(
            documentation="本轮巡检扫描时年龄分桶中的 PROCESSING 对象数",
            unit="count",
        ),
        "ai_assistant_processing_warning_count": MetricField(
            documentation="本轮巡检扫描时达到无活动告警阈值的对象数",
            unit="count",
        ),
        "ai_assistant_processing_expired_count": MetricField(
            documentation="本轮巡检扫描时达到硬失效阈值的对象数",
            unit="count",
        ),
    }
    dimension_fields = {
        "object_type": MetricDimension(documentation="被巡检的对象类型，固定为 MESSAGE 或 ATTACHMENT"),
        "business_type": MetricDimension(documentation="Handler 注册的消息或附件类型，必须是稳定低基数值"),
        "age_bucket": MetricDimension(documentation="按 last_activity_at 分类的 HEALTHY、WARNING、EXPIRED 或 UNKNOWN 固定年龄分桶"),
    }


class AIAssistantReconcileMetric(Metric):
    """每轮巡检结束时上报心跳、耗时和自动收敛结果。"""

    documentation = "AI 助手失活执行巡检的心跳、耗时和收敛结果"
    metric_fields = {
        "ai_assistant_reconcile_heartbeat": MetricField(
            documentation="一轮巡检完成时上报的心跳样本，固定为 1",
            unit="count",
        ),
        "ai_assistant_reconcile_duration_ms": MetricField(documentation="当前一轮巡检的总耗时", unit="ms"),
        "ai_assistant_reconcile_scanned_count": MetricField(
            documentation="当前一轮进入有界候选集的 Message 和 Attachment 总数",
            unit="count",
        ),
        "ai_assistant_reconcile_expired_count": MetricField(
            documentation="当前一轮聚合发现达到硬失效阈值的对象数",
            unit="count",
        ),
        "ai_assistant_reconcile_failed_count": MetricField(
            documentation="当前一轮通过 CAS 成功收敛为 FAILED 的对象数",
            unit="count",
        ),
    }
    dimension_fields = {
        "stage": MetricDimension(documentation="平台执行阶段，本指标组固定为 reconcile"),
        "status": MetricDimension(documentation="本轮巡检状态，正常完成为 SUCCESS，样例上报为 SAMPLE"),
    }


class AIAssistantStreamExecutionMetric(Metric):
    """每次流式 Attachment execution 收敛时上报容量、降级和截断汇总。"""

    documentation = "AI 助手流式 Attachment 执行的事件容量、降级和截断情况"
    metric_fields = {
        "ai_assistant_stream_execution_count": MetricField(documentation="收敛的流式 execution 数", unit="count"),
        "ai_assistant_stream_degraded_count": MetricField(
            documentation="本次 execution 发生 Redis 实时通道或 MySQL checkpoint 降级时为 1",
            unit="count",
        ),
        "ai_assistant_stream_truncated_count": MetricField(
            documentation="本次 execution 达到事件或归档容量上限时为 1",
            unit="count",
        ),
        "ai_assistant_stream_event_count": MetricField(documentation="本次 execution 接收的业务流事件总数", unit="count"),
        "ai_assistant_stream_event_bytes": MetricField(
            documentation="本次 execution 接收的业务流事件编码后总字节数",
            unit="byte",
        ),
    }
    dimension_fields = {
        "object_type": MetricDimension(documentation="流式对象类型，本期固定为 ATTACHMENT"),
        "business_type": MetricDimension(documentation="Handler 注册的附件类型，必须是稳定低基数值"),
        "is_stream": MetricDimension(documentation="是否使用流式执行，本指标组固定为 true"),
        "stage": MetricDimension(documentation="平台执行阶段，本指标组固定为 stream"),
        "status": MetricDimension(documentation="本次 execution 的收敛状态，例如 SUCCESS、FAILED 或 RETRY"),
        "error_code": MetricDimension(documentation="平台或 Handler 返回的稳定错误码，成功时为空字符串"),
    }


class AIAssistantExecutionTimeoutEvent(Event):
    """巡检赢得硬超时 CAS 并将对象收敛为 FAILED 时上报。

    ``target`` 是 Message/Attachment UID，只用于单对象排查；``object_type``、
    ``business_type`` 和 ``error_code`` 是低基数聚合维度。``task_id`` 放在
    ``extra`` 中用于 Worker/Trace 追踪，不进入 BKM 维度。CAS 未命中不上报；
    唯一例外是运维样例命令使用 ``OBSERVABILITY_SAMPLE`` 显式验证 BKM 数据源。
    """

    name = "ai_assistant_execution_timeout"
    documentation = "AI 助手异步执行超时"
    labelnames = ["object_type", "business_type", "error_code"]


class AIAssistantReconcileFailedEvent(Event):
    """巡检任务自身异常时上报，要求优先恢复兜底任务心跳。

    ``target`` 固定为巡检任务名；``error_code`` 是可配置告警的稳定错误维度。
    异常类名仅放入 ``extra`` 协助排查，避免把非稳定类名引入聚合维度。
    运维样例命令可使用 ``OBSERVABILITY_SAMPLE`` 显式验证 BKM 数据源。
    """

    name = "ai_assistant_reconcile_failed"
    documentation = "AI 助手异步执行巡检失败"
    labelnames = ["error_code"]


class AIAssistantInvariantViolationEvent(Event):
    """Handler 输出或平台终态硬约束被破坏时上报。

    ``target`` 是受影响的 Message/Attachment UID；``object_type``、``business_type``
    和 ``error_code`` 用于按平台契约类型聚合。``task_id`` 只放入 ``extra`` 追踪
    当次 Worker，不作为高基数维度。普通 Handler 业务失败不触发此事件。
    运维样例命令可使用 ``OBSERVABILITY_SAMPLE`` 显式验证 BKM 数据源。
    """

    name = "ai_assistant_invariant_violation"
    documentation = "AI 助手平台执行约束异常"
    labelnames = ["object_type", "business_type", "error_code"]


@dataclass(frozen=True, slots=True)
class ExecutionMetricSnapshot:
    """一次 Message 或 Attachment 进入终态时的低基数快照。

    ``created_at`` 衡量用户总等待时间；``queued_at`` 和 ``started_at`` 只衡量
    当前平台执行的排队和 Worker 阶段，同步执行或时间缺失时允许为空。
    """

    object_type: ExecutionObjectType
    business_type: str
    execution_mode: str
    is_stream: bool
    status: str
    error_code: str
    created_at: datetime
    queued_at: datetime | None
    started_at: datetime | None
    finished_at: datetime


@dataclass(frozen=True, slots=True)
class ProcessingMetricRecord:
    """巡检将 MySQL PROCESSING 存量聚合为一条分桶上报记录。"""

    object_type: ExecutionObjectType
    business_type: str
    age_bucket: str
    processing_count: int
    warning_count: int
    expired_count: int


@dataclass(frozen=True, slots=True)
class ReconcileMetricSnapshot:
    """一轮 Message/Attachment 失活巡检完成后的心跳与收敛快照。"""

    duration_ms: int
    scanned_count: int
    expired_count: int
    failed_count: int
    status: str


@dataclass(frozen=True, slots=True)
class StreamMetricSnapshot:
    """一次流式 Attachment 收敛后的容量与降级快照，不包含事件正文。"""

    business_type: str
    status: str
    error_code: str
    degraded: bool
    truncated: bool
    event_count: int
    event_bytes: int


@dataclass(frozen=True, slots=True)
class TimeoutEventRecord:
    """巡检成功收敛的对象信息；高基数标识只进入事件 target/extra。"""

    object_type: ExecutionObjectType
    business_type: str
    object_uid: str
    task_id: str
    error_code: str


def _duration_ms(started_at: datetime | None, finished_at: datetime | None) -> int:
    """将可选时间区间转换为非负毫秒；缺失阶段不虚构耗时。"""

    if started_at is None or finished_at is None:
        return 0
    return max(0, int((finished_at - started_at).total_seconds() * 1000))


def _execution_slo_met(snapshot: ExecutionMetricSnapshot) -> int:
    """按对象类型使用平台 SLO，生成可在 BKM 直接求达标率的样本。"""

    slo_seconds = {
        ExecutionObjectType.MESSAGE: settings.AI_ASSISTANT_MESSAGE_SLO_SECONDS,
        ExecutionObjectType.ATTACHMENT: settings.AI_ASSISTANT_ATTACHMENT_SLO_SECONDS,
    }.get(snapshot.object_type)
    if slo_seconds is None:
        return 0
    return int(_duration_ms(snapshot.created_at, snapshot.finished_at) <= slo_seconds * 1000)


def _build_execution_metric_record(snapshot: ExecutionMetricSnapshot) -> dict:
    """把一个终态快照转换为声明式 Execution Metric 记录。"""

    return {
        "metrics": {
            "ai_assistant_execution_count": 1,
            "ai_assistant_execution_queue_duration_ms": _duration_ms(
                snapshot.queued_at,
                snapshot.started_at or snapshot.finished_at,
            ),
            "ai_assistant_execution_duration_ms": _duration_ms(snapshot.started_at, snapshot.finished_at),
            "ai_assistant_execution_total_duration_ms": _duration_ms(snapshot.created_at, snapshot.finished_at),
            "ai_assistant_execution_slo_met_count": _execution_slo_met(snapshot),
        },
        "dimension": {
            "object_type": snapshot.object_type,
            "business_type": snapshot.business_type,
            "execution_mode": snapshot.execution_mode,
            "is_stream": str(snapshot.is_stream).lower(),
            "stage": "terminal",
            "status": snapshot.status,
            "error_code": snapshot.error_code,
        },
    }


def report_execution_finished(snapshot: ExecutionMetricSnapshot) -> None:
    """上报一个终态对象的执行次数及阶段耗时。"""

    AIAssistantExecutionMetric(**_build_execution_metric_record(snapshot)).async_report()


def report_execution_finished_batch(snapshots: Collection[ExecutionMetricSnapshot]) -> None:
    """批量上报同一巡检中收敛的终态，避免按对象创建监控任务。"""

    records = [_build_execution_metric_record(snapshot) for snapshot in snapshots]
    if records:
        AIAssistantExecutionMetric(records=records).async_report()


def report_processing_metrics(records: Collection[ProcessingMetricRecord]) -> None:
    """批量上报巡检聚合结果，避免逐对象产生指标任务。"""

    if not records:
        return

    AIAssistantProcessingMetric(
        records=[
            {
                "metrics": {
                    "ai_assistant_processing_count": record.processing_count,
                    "ai_assistant_processing_warning_count": record.warning_count,
                    "ai_assistant_processing_expired_count": record.expired_count,
                },
                "dimension": {
                    "object_type": record.object_type,
                    "business_type": record.business_type,
                    "age_bucket": record.age_bucket,
                },
            }
            for record in records
        ]
    ).async_report()


def report_reconcile_metric(snapshot: ReconcileMetricSnapshot) -> None:
    """上报巡检心跳；BKM 通过心跳缺失识别兜底任务失效。"""

    AIAssistantReconcileMetric(
        metrics={
            "ai_assistant_reconcile_heartbeat": 1,
            "ai_assistant_reconcile_duration_ms": max(0, snapshot.duration_ms),
            "ai_assistant_reconcile_scanned_count": max(0, snapshot.scanned_count),
            "ai_assistant_reconcile_expired_count": max(0, snapshot.expired_count),
            "ai_assistant_reconcile_failed_count": max(0, snapshot.failed_count),
        },
        dimension={"stage": "reconcile", "status": snapshot.status},
    ).async_report()


def report_stream_execution(snapshot: StreamMetricSnapshot) -> None:
    """一次流执行结束后上报汇总，不按事件或 checkpoint 高频投递。"""

    AIAssistantStreamExecutionMetric(
        metrics={
            "ai_assistant_stream_execution_count": 1,
            "ai_assistant_stream_degraded_count": int(snapshot.degraded),
            "ai_assistant_stream_truncated_count": int(snapshot.truncated),
            "ai_assistant_stream_event_count": max(0, snapshot.event_count),
            "ai_assistant_stream_event_bytes": max(0, snapshot.event_bytes),
        },
        dimension={
            "object_type": ExecutionObjectType.ATTACHMENT,
            "business_type": snapshot.business_type,
            "is_stream": "true",
            "stage": "stream",
            "status": snapshot.status,
            "error_code": snapshot.error_code,
        },
    ).async_report()


def report_execution_timeout_events(records: Collection[TimeoutEventRecord]) -> None:
    """批量上报本轮真正赢得超时 CAS 的对象，未命中对象不产生事件。"""

    if not records:
        return

    AIAssistantExecutionTimeoutEvent(
        records=[
            {
                "target": record.object_uid,
                "context": {
                    "object_type": record.object_type,
                    "business_type": record.business_type,
                    "error_code": record.error_code,
                },
                "extra": {"task_id": record.task_id},
            }
            for record in records
        ]
    ).async_report()


def report_reconcile_failed_event(error: Exception) -> None:
    """上报巡检自身失败；异常类型仅进入事件正文，不作为聚合维度。"""

    AIAssistantReconcileFailedEvent(
        target="ai_assistant_reconcile",
        context={"error_code": "RECONCILE_FAILED"},
        extra={"error_type": error.__class__.__name__},
    ).async_report()


def report_invariant_violation(
    object_type: ExecutionObjectType,
    business_type: str,
    object_uid: str,
    task_id: str,
    error_code: str,
) -> None:
    """上报输出协议等硬约束异常，高基数标识只用于单对象排查。"""

    AIAssistantInvariantViolationEvent(
        target=object_uid,
        context={
            "object_type": object_type,
            "business_type": business_type,
            "error_code": error_code,
        },
        extra={"task_id": task_id},
    ).async_report()


def start_execution_span(
    object_type: ExecutionObjectType,
    object_id: int,
    task_id: str,
    task_name: str,
    retries: int,
    redelivered: bool,
):
    """创建 Message/Attachment 公共任务 Span，具体业务信息在加载后补充。"""

    span_name = f"ai_assistant.{object_type.lower()}.execute"
    return start_observation_span(
        span_name,
        {
            "bk_audit.ai_assistant.object_type": object_type,
            "bk_audit.ai_assistant.object_id": object_id,
            "bk_audit.ai_assistant.task_id": task_id,
            "bk_audit.ai_assistant.task_name": task_name,
            "bk_audit.ai_assistant.retries": retries,
            "bk_audit.ai_assistant.redelivered": redelivered,
        },
    )


def start_stream_span(
    attachment_uid: str,
    business_type: str,
    execution_id: str,
    status: str,
):
    """记录一次流执行的收敛阶段，不跨线程长期持有 OTel Context。

    Attachment 的任务 Span 已覆盖完整业务执行；这里单独观测最终归档事务、
    Retry 刷盘和终止事件发布，便于区分业务执行慢与流收敛慢。
    """

    return start_observation_span(
        "ai_assistant.attachment.stream",
        {
            "bk_audit.ai_assistant.object_type": ExecutionObjectType.ATTACHMENT,
            "bk_audit.ai_assistant.object_uid": attachment_uid,
            "bk_audit.ai_assistant.business_type": business_type,
            "bk_audit.ai_assistant.execution_id": execution_id,
            "bk_audit.ai_assistant.status": status,
        },
    )


def set_execution_span_context(object_uid: str, business_type: str, is_stream: bool) -> None:
    """在领域对象加载完成后，为当前任务 Span 补充可检索上下文。"""

    set_span_attributes(
        trace.get_current_span(),
        {
            "bk_audit.ai_assistant.object_uid": object_uid,
            "bk_audit.ai_assistant.business_type": business_type,
            "bk_audit.ai_assistant.is_stream": is_stream,
        },
    )

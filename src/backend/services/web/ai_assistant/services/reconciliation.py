"""AI 助手异步执行巡检。

MySQL 是状态事实源。巡检只按状态与活动时间索引扫描候选，通过 task_id 和活动
截止时间 CAS 收敛，不查询 Celery Worker、Result Backend 或 RabbitMQ 状态。
"""

import time
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from core.observability import set_span_attributes, start_observation_span
from services.web.ai_assistant.constants import (
    AttachmentErrorCode,
    ExecutionMode,
    ExecutionObjectType,
    ExecutionStatus,
    MessageErrorCode,
)
from services.web.ai_assistant.models import Attachment, Message
from services.web.ai_assistant.observability import (
    ExecutionMetricSnapshot,
    ProcessingMetricRecord,
    ReconcileMetricSnapshot,
    TimeoutEventRecord,
    report_execution_finished_batch,
    report_execution_timeout_events,
    report_processing_metrics,
    report_reconcile_metric,
)

_TIMEOUT_MESSAGE = "任务执行超时，请重试"


@dataclass(frozen=True, slots=True)
class ReconcileSummary:
    """一次巡检的稳定返回值；周期任务只返回可序列化计数。"""

    duration_ms: int
    scanned_count: int
    expired_count: int
    failed_count: int

    def as_dict(self) -> dict[str, int]:
        return {
            "duration_ms": self.duration_ms,
            "scanned_count": self.scanned_count,
            "expired_count": self.expired_count,
            "failed_count": self.failed_count,
        }


@dataclass(frozen=True, slots=True)
class _ModelReconcileConfig:
    """Message/Attachment 巡检的最小差异，避免复制同一套状态算法。"""

    model: type[Message] | type[Attachment]
    object_type: ExecutionObjectType
    business_field: str
    warning_seconds: int
    failure_seconds: int
    timeout_error_code: str


@dataclass(frozen=True, slots=True)
class _ModelReconcileResult:
    records: tuple[ProcessingMetricRecord, ...]
    scanned_count: int
    expired_count: int
    failed_count: int


def reconcile_processing_executions(*, now: datetime | None = None) -> ReconcileSummary:
    """聚合 PROCESSING 存量，并按平台阈值自动失败失活对象。"""

    now = now or timezone.now()
    started_at = time.perf_counter()
    configs = (
        _ModelReconcileConfig(
            model=Message,
            object_type=ExecutionObjectType.MESSAGE,
            business_field="message_type",
            warning_seconds=settings.AI_ASSISTANT_MESSAGE_WARNING_SECONDS,
            failure_seconds=settings.AI_ASSISTANT_MESSAGE_FAILURE_SECONDS,
            timeout_error_code=MessageErrorCode.TASK_EXECUTION_TIMEOUT,
        ),
        _ModelReconcileConfig(
            model=Attachment,
            object_type=ExecutionObjectType.ATTACHMENT,
            business_field="attachment_type",
            warning_seconds=settings.AI_ASSISTANT_ATTACHMENT_WARNING_SECONDS,
            failure_seconds=settings.AI_ASSISTANT_ATTACHMENT_FAILURE_SECONDS,
            timeout_error_code=AttachmentErrorCode.TASK_EXECUTION_TIMEOUT,
        ),
    )

    with start_observation_span("ai_assistant.execution.reconcile", {}) as span:
        results = tuple(_reconcile_model(config=config, now=now) for config in configs)
        duration_ms = max(0, int((time.perf_counter() - started_at) * 1000))
        summary = ReconcileSummary(
            duration_ms=duration_ms,
            scanned_count=sum(result.scanned_count for result in results),
            expired_count=sum(result.expired_count for result in results),
            failed_count=sum(result.failed_count for result in results),
        )
        set_span_attributes(
            span,
            {
                "bk_audit.ai_assistant.scanned_count": summary.scanned_count,
                "bk_audit.ai_assistant.expired_count": summary.expired_count,
                "bk_audit.ai_assistant.failed_count": summary.failed_count,
            },
        )

    processing_records = tuple(record for result in results for record in result.records)
    report_processing_metrics(processing_records)
    report_reconcile_metric(
        ReconcileMetricSnapshot(
            duration_ms=summary.duration_ms,
            scanned_count=summary.scanned_count,
            expired_count=summary.expired_count,
            failed_count=summary.failed_count,
            status="SUCCESS",
        )
    )
    return summary


def _reconcile_model(*, config: _ModelReconcileConfig, now: datetime) -> _ModelReconcileResult:
    """对一个模型执行聚合和有界候选收敛；候选竞争失败属于正常并发。"""

    warning_cutoff = now - timedelta(seconds=config.warning_seconds)
    failure_cutoff = now - timedelta(seconds=config.failure_seconds)
    processing = config.model.objects.filter(status=ExecutionStatus.PROCESSING)
    records = _aggregate_processing(
        queryset=processing,
        config=config,
        warning_cutoff=warning_cutoff,
        failure_cutoff=failure_cutoff,
    )
    expired_count = sum(record.expired_count for record in records)
    candidates = _load_timeout_candidates(
        queryset=processing,
        business_field=config.business_field,
        failure_cutoff=failure_cutoff,
        batch_size=settings.AI_ASSISTANT_RECONCILE_BATCH_SIZE,
    )

    timeout_records: list[TimeoutEventRecord] = []
    execution_snapshots: list[ExecutionMetricSnapshot] = []
    try:
        if settings.AI_ASSISTANT_RECONCILE_AUTO_FAIL_ENABLED:
            for candidate in candidates:
                task_id = candidate["task_id"]
                # 迁移后正常行一定有 task_id/activity；异常空值只进入观测，不做不安全推断。
                if not task_id or candidate["last_activity_at"] is None:
                    continue
                updated = config.model.timeout_processing(
                    instance_id=candidate["id"],
                    task_id=task_id,
                    cutoff=failure_cutoff,
                    error_code=config.timeout_error_code,
                    error_message=_TIMEOUT_MESSAGE,
                    now=now,
                    extra_updates={"updated_at": now},
                )
                if not updated:
                    continue
                timeout_records.append(
                    TimeoutEventRecord(
                        object_type=config.object_type,
                        business_type=str(candidate[config.business_field]),
                        object_uid=str(candidate["uid"]),
                        task_id=task_id,
                        error_code=str(config.timeout_error_code),
                    )
                )
                execution_snapshots.append(
                    ExecutionMetricSnapshot(
                        object_type=config.object_type,
                        business_type=str(candidate[config.business_field]),
                        execution_mode=ExecutionMode.ASYNC,
                        is_stream=bool(candidate.get("is_stream", False)),
                        status=ExecutionStatus.FAILED,
                        error_code=str(config.timeout_error_code),
                        created_at=candidate["created_at"],
                        queued_at=candidate["queued_at"],
                        started_at=candidate["started_at"],
                        finished_at=now,
                    )
                )
    finally:
        # 每个模型完成或中途失败时批量上报已提交的 CAS，避免监控任务按对象放大。
        report_execution_finished_batch(execution_snapshots)
        if timeout_records:
            report_execution_timeout_events(timeout_records)

    return _ModelReconcileResult(
        records=records,
        scanned_count=len(candidates),
        expired_count=expired_count,
        failed_count=len(timeout_records),
    )


def _aggregate_processing(
    *,
    queryset,
    config: _ModelReconcileConfig,
    warning_cutoff: datetime,
    failure_cutoff: datetime,
) -> tuple[ProcessingMetricRecord, ...]:
    """在数据库按业务类型和年龄分桶，Python 只转换小规模聚合结果。"""

    rows = (
        queryset.annotate(
            age_bucket=models.Case(
                models.When(last_activity_at__isnull=True, then=models.Value("UNKNOWN")),
                models.When(last_activity_at__lte=failure_cutoff, then=models.Value("EXPIRED")),
                models.When(last_activity_at__lte=warning_cutoff, then=models.Value("WARNING")),
                default=models.Value("HEALTHY"),
                output_field=models.CharField(),
            )
        )
        .values(config.business_field, "age_bucket")
        .annotate(processing_count=models.Count("id"))
        .order_by()
    )
    return tuple(
        ProcessingMetricRecord(
            object_type=config.object_type,
            business_type=str(row[config.business_field]),
            age_bucket=row["age_bucket"],
            processing_count=row["processing_count"],
            warning_count=row["processing_count"] if row["age_bucket"] in {"WARNING", "EXPIRED"} else 0,
            expired_count=row["processing_count"] if row["age_bucket"] == "EXPIRED" else 0,
        )
        for row in rows
    )


def _load_timeout_candidates(*, queryset, business_field: str, failure_cutoff: datetime, batch_size: int):
    """先走状态活动索引，再用剩余额度读取异常空活动行，避免主查询 OR。"""

    fields = [
        "id",
        "uid",
        "task_id",
        "created_at",
        "queued_at",
        "started_at",
        "last_activity_at",
        business_field,
    ]
    if queryset.model is Attachment:
        fields.append("is_stream")
    candidates = list(
        queryset.filter(last_activity_at__lte=failure_cutoff)
        .order_by("last_activity_at", "id")
        .values(*fields)[:batch_size]
    )
    remaining = batch_size - len(candidates)
    if remaining > 0:
        candidates.extend(queryset.filter(last_activity_at__isnull=True).order_by("id").values(*fields)[:remaining])
    return candidates

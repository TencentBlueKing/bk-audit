"""显式上报 AI 助手可观测性样例，供 BKM 首次发现指标和事件协议。"""

from django.conf import settings
from django.core.management import BaseCommand, CommandError
from django.utils import timezone

from services.web.ai_assistant.constants import ExecutionMode, ExecutionObjectType
from services.web.ai_assistant.observability import (
    AIAssistantExecutionTimeoutEvent,
    AIAssistantInvariantViolationEvent,
    AIAssistantReconcileFailedEvent,
    ExecutionMetricSnapshot,
    ProcessingMetricRecord,
    ReconcileMetricSnapshot,
    StreamMetricSnapshot,
    report_execution_finished,
    report_processing_metrics,
    report_reconcile_metric,
    report_stream_execution,
)

_SAMPLE_BUSINESS_TYPE = "OBSERVABILITY_SAMPLE"
_SAMPLE_ERROR_CODE = "OBSERVABILITY_SAMPLE"
_SAMPLE_STATUS = "SAMPLE"
_SAMPLE_TARGET = "ai_assistant_observability_sample"


class Command(BaseCommand):
    """向已配置的 BKM 数据源提交一组可识别为样例的观测数据。"""

    help = "上报 AI 助手 Metric/Event 样例，供 BKM 创建指标、事件和告警策略"

    def handle(self, *args, **options):
        self._validate_monitor_configuration()
        now = timezone.now()

        report_execution_finished(
            ExecutionMetricSnapshot(
                object_type=ExecutionObjectType.MESSAGE,
                business_type=_SAMPLE_BUSINESS_TYPE,
                execution_mode=ExecutionMode.ASYNC,
                is_stream=False,
                status=_SAMPLE_STATUS,
                error_code="",
                created_at=now,
                queued_at=now,
                started_at=now,
                finished_at=now,
            )
        )
        report_processing_metrics(
            [
                ProcessingMetricRecord(
                    object_type=ExecutionObjectType.MESSAGE,
                    business_type=_SAMPLE_BUSINESS_TYPE,
                    age_bucket="HEALTHY",
                    processing_count=1,
                    warning_count=0,
                    expired_count=0,
                )
            ]
        )
        report_reconcile_metric(
            ReconcileMetricSnapshot(
                duration_ms=0,
                scanned_count=0,
                expired_count=0,
                failed_count=0,
                status=_SAMPLE_STATUS,
            )
        )
        report_stream_execution(
            StreamMetricSnapshot(
                business_type=_SAMPLE_BUSINESS_TYPE,
                status=_SAMPLE_STATUS,
                error_code="",
                degraded=False,
                truncated=False,
                event_count=1,
                event_bytes=0,
            )
        )
        self._report_event_samples()
        self.stdout.write(self.style.SUCCESS("已提交 4 组 Metric 和 3 类 Event 样例上报任务"))

    @staticmethod
    def _validate_monitor_configuration() -> None:
        """缺少数据源配置时直接失败，避免命令看似成功但没有实际投递。"""

        required_settings = (
            "LOG_EXPORT_STATUS_DATA_ID",
            "LOG_EXPORT_STATUS_ACCESS_TOKEN",
            "ALERT_DATA_ID",
            "ALERT_ACCESS_TOKEN",
        )
        if any(not getattr(settings, setting_name, None) for setting_name in required_settings):
            raise CommandError("监控上报配置不完整，请先配置 Metric 和 Event 数据源")

    @staticmethod
    def _report_event_samples() -> None:
        """事件 target 和正文显式标记 sample，避免被误判为真实故障。"""

        common_extra = {"sample": True}
        AIAssistantExecutionTimeoutEvent(
            target=_SAMPLE_TARGET,
            context={
                "object_type": ExecutionObjectType.MESSAGE,
                "business_type": _SAMPLE_BUSINESS_TYPE,
                "error_code": _SAMPLE_ERROR_CODE,
            },
            extra=common_extra,
        ).async_report()
        AIAssistantReconcileFailedEvent(
            target=_SAMPLE_TARGET,
            context={"error_code": _SAMPLE_ERROR_CODE},
            extra=common_extra,
        ).async_report()
        AIAssistantInvariantViolationEvent(
            target=_SAMPLE_TARGET,
            context={
                "object_type": ExecutionObjectType.MESSAGE,
                "business_type": _SAMPLE_BUSINESS_TYPE,
                "error_code": _SAMPLE_ERROR_CODE,
            },
            extra=common_extra,
        ).async_report()

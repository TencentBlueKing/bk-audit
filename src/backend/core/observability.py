"""
审计中心业务观测性补充入口。

项目的 OTel 初始化由 `blueapps.opentelemetry.instrument_app` 完成，Django、
Celery、requests、Redis 等框架级 span 会自动生成。本文件只补自动埋点
覆盖不到、但排障时必须稳定可查的业务语义。

职责边界：
1. Trace / Span
   - `BKResourceAPIInstrumentor`：把 bk_resource 的三方 API 调用包成
     `api.<module>.<Resource>` 形式的 client span。
   - `start_observation_span`：给关键业务入口或阶段手动创建 business span。
   - span 只描述调用链，不负责推断业务成功率。

2. Metric
   - `report_observation_metric`：基于 `core.monitor.Metric` 显式上报低基数业务指标。
   - 调用方必须传入真实业务 status，例如 NL2Risk 的 parse_failed 虽然不抛异常，
     也应由业务代码显式计入错误率。
   - 当前按接入约定复用 `LOG_EXPORT_STATUS_DATA_ID/ACCESS_TOKEN`；虽然配置名带
     log export，但这里把它作为通用 BKM 自定义指标数据源使用。

3. Event
   - 失败事件仍放在 `core.monitor.Event` 及其业务子类中。
   - Event 面向“少量、可读、需要人处理”的异常事实；Metric 面向聚合告警。
"""

import time
from contextlib import contextmanager
from functools import wraps
from typing import Any, Collection, Generator

from opentelemetry import trace
from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from opentelemetry.trace import Span, SpanKind, Status, StatusCode

API_SPAN_INSTRUMENTATION_NAME = "bk_audit.bk_resource"
BUSINESS_SPAN_INSTRUMENTATION_NAME = "bk_audit.business"

API_SPAN_STATUS_SUCCESS = "success"
API_SPAN_STATUS_ERROR = "error"

OBSERVATION_METRIC_STATUS_SUCCESS = "success"
OBSERVATION_METRIC_STATUS_ERROR = "error"


def _to_span_attribute_value(value: Any) -> Any:
    """把项目内常见值收敛成 OTel attribute 支持的稳定标量。"""

    if isinstance(value, (bool, int, float, str)):
        return value
    return str(value) if value is not None else ""


def _set_span_attribute(span: Span, key: str, value: Any):
    """安全设置单个 span attribute；None 表示没有该维度，直接跳过。"""

    if value is None:
        return
    span.set_attribute(key, _to_span_attribute_value(value))


def set_span_attributes(span: Span, attributes: dict[str, Any] | None):
    """批量补充 span attribute，供业务代码在拿到中间结果后继续补信息。"""

    if not attributes or not span.is_recording():
        return

    for key, value in attributes.items():
        _set_span_attribute(span, key, value)


def _get_api_resource_span_name(resource: Any) -> str:
    """生成低基数 client span 名称，避免 URL、参数进入 span name。"""

    module_name = getattr(resource, "module_name", "") or resource.__class__.__module__
    return f"api.{module_name}.{resource.__class__.__name__}"


def _set_api_resource_attributes(span: Span, resource: Any, status: str):
    """写入 bk_resource client span 的稳定业务维度。"""

    if not span.is_recording():
        return

    _set_span_attribute(span, "bk_audit.api.module", getattr(resource, "module_name", ""))
    _set_span_attribute(span, "bk_audit.api.resource", resource.__class__.__name__)
    _set_span_attribute(span, "bk_audit.api.method", getattr(resource, "method", ""))
    _set_span_attribute(span, "bk_audit.api.action", getattr(resource, "action", ""))
    _set_span_attribute(span, "bk_audit.api.status", status)


def _set_api_resource_error_attributes(span: Span, err: Exception):
    """把三方 API 异常类型和状态码写到 client span 上。"""

    if not span.is_recording():
        return

    _set_span_attribute(span, "bk_audit.api.error_type", err.__class__.__name__)
    status_code = getattr(err, "status_code", None)
    if status_code:
        _set_span_attribute(span, "bk_audit.api.status_code", status_code)
    span.set_status(Status(StatusCode.ERROR, str(err)[:1024]))


def report_observation_metric(
    name: str,
    started_at: float,
    status: str,
    dimensions: dict[str, Any] | None = None,
    error_type: str = "",
):
    """
    显式上报一次业务调用的聚合指标。

    这里不从 span status 推断成功失败，因为 span 只能说明代码是否抛异常；
    业务失败可能以返回值表达，例如 NL2Risk 解析失败。
    """

    duration_ms = max(0, int((time.perf_counter() - started_at) * 1000))
    metric_dimensions = {
        **(dimensions or {}),
        "span_name": name,
        "status": status,
        "error_type": error_type,
    }

    # 延迟导入：config.default 会在 settings 初始化期间导入本模块，不能提前加载 bk_resource。
    from core.monitor import Metric

    return Metric(
        metrics={
            "call_count": 1,
            "duration_ms": duration_ms,
        },
        dimension=metric_dimensions,
    ).async_report()


@contextmanager
def start_observation_span(
    name: str,
    attributes: dict[str, Any] | None = None,
    kind: SpanKind = SpanKind.INTERNAL,
) -> Generator[Span, None, None]:
    """创建一个手动业务 span；metric 请由业务代码显式调用。"""

    tracer = trace.get_tracer(BUSINESS_SPAN_INSTRUMENTATION_NAME)
    with tracer.start_as_current_span(
        name,
        kind=kind,
        record_exception=True,
        set_status_on_exception=True,
    ) as span:
        set_span_attributes(span, attributes)
        try:
            yield span
        except Exception as err:
            # OTel 会记录异常栈；这里补一个低基数 error_type，便于 APM 侧聚合过滤。
            _set_span_attribute(span, "bk_audit.error_type", err.__class__.__name__)
            span.set_status(Status(StatusCode.ERROR, str(err)[:1024]))
            raise
        span.set_status(Status(StatusCode.OK))


class BKResourceAPIInstrumentor(BaseInstrumentor):
    """为 bk_resource 的 APIResource.perform_request 补 client span。"""

    _original_perform_request = None
    _is_patched = False

    def instrumentation_dependencies(self) -> Collection[str]:
        return []

    def _instrument(self, **kwargs):
        if self.__class__._is_patched:
            return

        # config.default 会在 Django settings 初始化期间导入本模块；bk_resource 顶层导入会读取
        # settings.APP_CODE，因此只能在真正执行 instrument 时延迟导入。
        from bk_resource.contrib.api import APIResource

        original_perform_request = APIResource.perform_request

        @wraps(original_perform_request)
        def traced_perform_request(resource, validated_request_data):
            tracer = trace.get_tracer(API_SPAN_INSTRUMENTATION_NAME)
            span_name = _get_api_resource_span_name(resource)
            with tracer.start_as_current_span(
                span_name,
                kind=SpanKind.CLIENT,
                record_exception=True,
                set_status_on_exception=True,
            ) as span:
                _set_api_resource_attributes(span, resource, API_SPAN_STATUS_SUCCESS)
                try:
                    result = original_perform_request(resource, validated_request_data)
                except Exception as err:
                    _set_api_resource_attributes(span, resource, API_SPAN_STATUS_ERROR)
                    _set_api_resource_error_attributes(span, err)
                    raise
                span.set_status(Status(StatusCode.OK))
                return result

        self.__class__._original_perform_request = original_perform_request
        APIResource.perform_request = traced_perform_request
        self.__class__._is_patched = True

    def _uninstrument(self, **kwargs):
        if not self.__class__._is_patched:
            return

        from bk_resource.contrib.api import APIResource

        APIResource.perform_request = self.__class__._original_perform_request
        self.__class__._original_perform_request = None
        self.__class__._is_patched = False


__all__ = [
    "OBSERVATION_METRIC_STATUS_ERROR",
    "OBSERVATION_METRIC_STATUS_SUCCESS",
    "BKResourceAPIInstrumentor",
    "report_observation_metric",
    "set_span_attributes",
    "start_observation_span",
]

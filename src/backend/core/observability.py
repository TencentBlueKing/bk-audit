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

   `BKResourceAPIInstrumentor` 的设计点：
   - 包 `APIResource.__call__`：`ResourceRequestLog` 在 `Resource.__call__`
     的 finally 中打印，span 必须覆盖到 finally，日志才有 trace_id。
   - 包 `APIResource.request`：直接 `.request()` 不经过 `__call__`，仍要有
     client span。
   - 包 `bk_resource` 的 `ThreadPool`：`bulk_request` 在线程池里调用 request，
     OTel context 默认不跨线程传播，因此在 SDK 线程池任务入口统一恢复 context。
   - `__call__` 内部本来会调用一次 `.request()`；这次 request span 会被跳过，
     避免同一个 API 调用生成两个同名 client span。

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
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import contextmanager
from contextvars import ContextVar
from functools import partial, wraps
from typing import Any, Callable, Collection, Generator

from opentelemetry import context as otel_context
from opentelemetry import trace
from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from opentelemetry.trace import Span, SpanKind, Status, StatusCode

API_SPAN_INSTRUMENTATION_NAME = "bk_audit.bk_resource"
BUSINESS_SPAN_INSTRUMENTATION_NAME = "bk_audit.business"

API_SPAN_STATUS_SUCCESS = "success"
API_SPAN_STATUS_ERROR = "error"

# 对外使用的指标状态值。值必须保持低基数且稳定，便于 BKM 过滤和聚合。
OBSERVATION_METRIC_STATUS_SUCCESS = "success"
OBSERVATION_METRIC_STATUS_ERROR = "error"

_SKIP_NEXT_REQUEST_SPAN_NAMES_FOR_CALL_LOG: ContextVar[tuple[str, ...]] = ContextVar(
    "bk_audit_skip_next_api_resource_request_span_for_call_log",
    default=(),
)


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


def set_span_attributes(span: Span, attributes: dict[str, Any] | None) -> None:
    """给已有 span 批量补充业务属性。

    适用于 span 已经创建，但关键维度要等中间结果返回后才能确定的场景，
    例如 DB 查询完成后补数量，或 AI API 返回后补内容大小。

    参数：
        span: `start_observation_span()` 返回的 span，或
            `trace.get_current_span()` 获取到的当前 span。
        attributes: 需要写入 span 的属性字典。值为 None 的属性会被忽略；
            非标量值会先转成字符串，再交给 OTel。

    返回：
        None。

    示例：
        ```python
        with start_observation_span("risk.export") as span:
            export_file = build_export_file()
            set_span_attributes(span, {"bk_audit.export.total": export_file.total})
        ```
    """

    if not attributes or not span.is_recording():
        return

    for key, value in attributes.items():
        _set_span_attribute(span, key, value)


def _get_current_observation_context():
    """截取当前 OTel context，供线程池任务提交时携带。"""

    return otel_context.get_current()


def _run_with_observation_context(parent_context: Any, callback: Callable[[], Any]):
    """在线程池子线程中恢复提交任务时的 OTel context，再执行回调。"""

    context_token = otel_context.attach(parent_context)
    try:
        return callback()
    finally:
        otel_context.detach(context_token)


def submit_with_observation_context(
    executor: ThreadPoolExecutor,
    callback: Callable[..., Any],
    *args: Any,
    **kwargs: Any,
) -> Future:
    """提交线程池任务，并让子线程继承当前 OTel context。

    OTel 使用的 `contextvars` 默认不会自动传播到新线程。如果子线程里会打日志、
    创建 span，或调用 `bk_resource.api`，需要用这个 helper 替代
    `executor.submit(...)`。

    参数：
        executor: 执行任务的 `concurrent.futures.ThreadPoolExecutor`。
        callback: 在线程池 worker 中执行的回调函数。
        *args: 传给 `callback` 的位置参数。
        **kwargs: 传给 `callback` 的关键字参数。

    返回：
        `executor.submit` 返回的 `Future` 对象。

    示例：
        ```python
        with ThreadPoolExecutor(max_workers=3) as executor:
            future = submit_with_observation_context(executor, api_call, payload)
            result = future.result()
        ```
    """

    task = partial(callback, *args, **kwargs)
    return executor.submit(_run_with_observation_context, _get_current_observation_context(), task)


def _get_api_resource_span_name(resource: Any) -> str:
    """生成低基数 client span 名称，避免 URL、参数进入 span name。"""

    module_name = getattr(resource, "module_name", "") or resource.__class__.__module__
    return f"api.{module_name}.{resource.__class__.__name__}"


def _run_with_next_request_span_skipped(span_name: str, callback: Callable[[], Any]):
    """标记 `__call__` 即将触发的下一次同名 `.request()` 不再重复建 span。"""

    skip_span_names = _SKIP_NEXT_REQUEST_SPAN_NAMES_FOR_CALL_LOG.get()
    token = _SKIP_NEXT_REQUEST_SPAN_NAMES_FOR_CALL_LOG.set((*skip_span_names, span_name))
    try:
        return callback()
    finally:
        _SKIP_NEXT_REQUEST_SPAN_NAMES_FOR_CALL_LOG.reset(token)


def _run_api_resource_request_with_span(resource: Any, callback: Callable[[], Any]):
    """直接 `.request()` 建 span；若来自 `__call__`，只跳过被标记的那一次。"""

    span_name = _get_api_resource_span_name(resource)
    skip_span_names = list(_SKIP_NEXT_REQUEST_SPAN_NAMES_FOR_CALL_LOG.get())
    if span_name not in skip_span_names:
        return _run_with_api_resource_span(resource, callback)

    skip_span_names.remove(span_name)
    token = _SKIP_NEXT_REQUEST_SPAN_NAMES_FOR_CALL_LOG.set(tuple(skip_span_names))
    try:
        return callback()
    finally:
        _SKIP_NEXT_REQUEST_SPAN_NAMES_FOR_CALL_LOG.reset(token)


def _run_with_api_resource_span(resource: Any, callback: Callable[[], Any]):
    """在稳定的 APIResource client span 中执行回调。"""

    span_name = _get_api_resource_span_name(resource)

    tracer = trace.get_tracer(API_SPAN_INSTRUMENTATION_NAME)
    with tracer.start_as_current_span(
        span_name,
        kind=SpanKind.CLIENT,
        record_exception=True,
        set_status_on_exception=True,
    ) as span:
        _set_api_resource_attributes(span, resource, API_SPAN_STATUS_SUCCESS)
        try:
            result = callback()
        except Exception as err:
            _set_api_resource_attributes(span, resource, API_SPAN_STATUS_ERROR)
            _set_api_resource_error_attributes(span, err)
            raise
        span.set_status(Status(StatusCode.OK))
        return result


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
    """把一次业务调用上报为 BKM 自定义指标。

    这里不会从 span status 推断业务成功或失败。部分业务失败不会抛异常，
    而是通过返回值表达，例如 NL2Risk 解析失败。

    参数：
        name: 稳定、低基数的操作名。会写入 `span_name` 维度，便于仪表盘过滤，
            例如
            `risk.nl2risk_filter.generate`.
        started_at: 操作开始前记录的 `time.perf_counter()` 值。本函数会转换成
            `duration_ms`。
        status: 业务状态。优先使用 `OBSERVATION_METRIC_STATUS_SUCCESS` 或
            `OBSERVATION_METRIC_STATUS_ERROR`.
        dimensions: 额外低基数维度，例如 `service`、`operation`、`scenario` 或
            `queue`。
        error_type: 低基数错误类型。成功时保持为空字符串。

    返回：
        `Metric.async_report()` 返回的 Celery async result；如果未配置指标上报，
        或任务投递失败，则返回 None。

    示例：
        ```python
        started_at = time.perf_counter()
        try:
            result = parse_query(query)
        except ValueError:
            report_observation_metric(
                name="risk.nl2risk_filter.generate",
                started_at=started_at,
                status=OBSERVATION_METRIC_STATUS_ERROR,
                dimensions={"service": "risk", "operation": "nl2risk_filter"},
                error_type="ValueError",
            )
            raise
        ```
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
    """创建一个手动业务 span。

    适用于 Django、Celery、requests、Redis、`bk_resource` 自动埋点覆盖不到的
    关键业务阶段。本函数只负责 trace，不会自动上报 metric；业务成功或失败状态
    明确后，需要显式调用 `report_observation_metric()`。

    参数：
        name: 稳定、低基数的 span 名称，例如
            `risk.generate_analyse_report.render`.
        attributes: 初始 span 属性。值应保持低基数，并适合在 APM 中过滤。
        kind: OTel span kind。业务阶段默认使用 `SpanKind.INTERNAL`；
            只有在表达真实边界时才使用其他类型。

    产出：
        创建好的 `Span`。调用方可以在拿到中间结果后继续补充属性。

    示例：
        ```python
        with start_observation_span(
            "risk.generate_analyse_report.render",
            {"bk_audit.report.id": report_id},
        ) as span:
            content = render_report(report_id)
            set_span_attributes(span, {"bk_audit.report.content_size": len(content)})
        ```
    """

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
    """为 `bk_resource` API 调用补充稳定的 client span。

    该 instrumentor 通过 Django settings 中的
    `BK_APP_OTEL_ADDTIONAL_INSTRUMENTORS` 注册，业务代码不应直接调用。
    它会 patch `APIResource.__call__`、`APIResource.request` 和 SDK
    `ThreadPool` 包装函数，用于覆盖：

    - `Resource.__call__` 内部的 `ResourceRequestLog.record()`。
    - 绕过 `__call__` 的直接 `.request()` 调用。
    - 可能丢失 OTel context 的 `bulk_request()` worker 子线程。

    参数：
        不需要构造参数。

    返回：
        遵循 OpenTelemetry `BaseInstrumentor` 约定。`instrument()`、
        `uninstrument()` 等生命周期方法由父类提供。

    示例：
        ```python
        BK_APP_OTEL_ADDTIONAL_INSTRUMENTORS = [BKResourceAPIInstrumentor()]
        ```
    """

    _original_call = None
    _original_request = None
    _original_thread_pool_get_func_with_local = None
    _had_own_call = False
    _is_patched = False

    def instrumentation_dependencies(self) -> Collection[str]:
        return []

    def _instrument(self, **kwargs):
        if self.__class__._is_patched:
            return

        # config.default 会在 Django settings 初始化期间导入本模块；bk_resource 顶层导入会读取
        # settings.APP_CODE，因此只能在真正执行 instrument 时延迟导入。
        from bk_resource.contrib.api import APIResource
        from bk_resource.utils.thread_backend import ThreadPool

        original_call = APIResource.__call__
        original_request = APIResource.request
        original_thread_pool_get_func_with_local = ThreadPool.get_func_with_local

        @wraps(original_call)
        def traced_call(resource, *args, **kwargs):
            # `Resource.__call__` 的 finally 会打印 ResourceRequestLog；
            # span 放在这里才能让日志带 trace_id。
            span_name = _get_api_resource_span_name(resource)

            def call_original():
                return _run_with_next_request_span_skipped(
                    span_name,
                    lambda: original_call(resource, *args, **kwargs),
                )

            return _run_with_api_resource_span(resource, call_original)

        @wraps(original_request)
        def traced_request(resource, request_data=None, **kwargs):
            # 直接 `.request()` 和 `bulk_request()` 子请求不会经过 `__call__`，这里单独兜住。
            return _run_api_resource_request_with_span(
                resource,
                lambda: original_request(resource, request_data=request_data, **kwargs),
            )

        @wraps(original_thread_pool_get_func_with_local)
        def traced_get_func_with_local(func):
            # bk_resource 的 bulk_request 统一走 ThreadPool；
            # 在任务封装点继承 context，比复制每个 bulk_request 实现更稳。
            parent_context = _get_current_observation_context()
            local_func = original_thread_pool_get_func_with_local(func)

            @wraps(func)
            def func_with_context(*args, **kwargs):
                return _run_with_observation_context(
                    parent_context,
                    lambda: local_func(*args, **kwargs),
                )

            return func_with_context

        self.__class__._original_call = original_call
        self.__class__._original_request = original_request
        self.__class__._original_thread_pool_get_func_with_local = original_thread_pool_get_func_with_local
        self.__class__._had_own_call = "__call__" in APIResource.__dict__
        APIResource.__call__ = traced_call
        APIResource.request = traced_request
        ThreadPool.get_func_with_local = staticmethod(traced_get_func_with_local)
        self.__class__._is_patched = True

    def _uninstrument(self, **kwargs):
        if not self.__class__._is_patched:
            return

        from bk_resource.contrib.api import APIResource
        from bk_resource.utils.thread_backend import ThreadPool

        if self.__class__._had_own_call:
            APIResource.__call__ = self.__class__._original_call
        else:
            delattr(APIResource, "__call__")
        APIResource.request = self.__class__._original_request
        ThreadPool.get_func_with_local = staticmethod(self.__class__._original_thread_pool_get_func_with_local)
        self.__class__._original_call = None
        self.__class__._original_request = None
        self.__class__._original_thread_pool_get_func_with_local = None
        self.__class__._had_own_call = False
        self.__class__._is_patched = False


__all__ = [
    "OBSERVATION_METRIC_STATUS_ERROR",
    "OBSERVATION_METRIC_STATUS_SUCCESS",
    "BKResourceAPIInstrumentor",
    "report_observation_metric",
    "set_span_attributes",
    "start_observation_span",
    "submit_with_observation_context",
]

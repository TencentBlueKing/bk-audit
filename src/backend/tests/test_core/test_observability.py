from unittest import mock

from bk_resource import APIResource, Resource
from django.test import SimpleTestCase, override_settings
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind, StatusCode

from core.monitor import Event, Metric
from core.observability import (
    OBSERVATION_METRIC_STATUS_SUCCESS,
    BKResourceAPIInstrumentor,
    report_observation_metric,
    start_observation_span,
)


class DummyAPIResource(APIResource):
    module_name = "bk_dummy"
    method = "POST"
    base_url = "https://example.com/api"
    action = "/v1/do_something/"


class LocalDummyAPIResource(DummyAPIResource):
    def perform_request(self, validated_request_data):
        return {"value": validated_request_data.get("foo", "")}


class LocalOuterBulkResource(Resource):
    def perform_request(self, validated_request_data):
        return LocalDummyAPIResource().request({"foo": validated_request_data.get("foo", "")})


class DummyEvent(Event):
    name = "dummy_event"
    documentation = "dummy event"
    labelnames = ["status", "error_type"]
    data_id = 321
    access_token = "event-token"


class TestMonitorPayloads(SimpleTestCase):
    def test_event_builds_single_record_payload(self):
        event = DummyEvent(
            target="nl2risk_filter",
            context={"status": "error", "error_type": "ValueError"},
            extra={"error": "failed"},
        )

        with mock.patch("core.monitor.report_event_to_bk_monitor.delay") as mock_delay:
            event.async_report()

        mock_delay.assert_called_once()
        payload = mock_delay.call_args[0][0]
        self.assertEqual(payload["data_id"], 321)
        self.assertEqual(payload["access_token"], "event-token")
        self.assertEqual(len(payload["data"]), 1)
        self.assertEqual(payload["data"][0]["event_name"], "dummy_event")
        self.assertEqual(payload["data"][0]["target"], "nl2risk_filter")
        self.assertEqual(payload["data"][0]["dimension"]["status"], "error")
        self.assertIn("error=failed", payload["data"][0]["event"]["content"])

    def test_event_builds_multi_record_payload(self):
        event = DummyEvent(
            records=[
                {
                    "target": "nl2risk_filter",
                    "context": {"status": "api_error", "error_type": "ValueError"},
                    "extra": {"error": "api failed"},
                },
                {
                    "target": "analyse_report",
                    "context": {"status": "failed", "error_type": "RuntimeError"},
                    "extra": {"error": "generate failed"},
                },
            ]
        )

        payload = event.to_json()

        self.assertEqual(len(payload["data"]), 2)
        self.assertEqual(payload["data"][0]["target"], "nl2risk_filter")
        self.assertEqual(payload["data"][0]["dimension"]["status"], "api_error")
        self.assertIn("error=api failed", payload["data"][0]["event"]["content"])
        self.assertEqual(payload["data"][1]["target"], "analyse_report")
        self.assertEqual(payload["data"][1]["dimension"]["status"], "failed")
        self.assertIn("error=generate failed", payload["data"][1]["event"]["content"])

    @mock.patch("core.monitor.api.bk_monitor.report_event", side_effect=RuntimeError("bkm failed"))
    def test_event_report_swallows_monitor_error(self, mock_report_event):
        event = DummyEvent(target="nl2risk_filter", context={"status": "error"})

        self.assertIsNone(event.report())
        mock_report_event.assert_called_once()

    @mock.patch("core.monitor.report_event_to_bk_monitor.delay", side_effect=RuntimeError("celery failed"))
    def test_event_async_report_swallows_enqueue_error(self, mock_delay):
        event = DummyEvent(target="nl2risk_filter", context={"status": "error"})

        self.assertIsNone(event.async_report())
        mock_delay.assert_called_once()


class TestObservationMetric(SimpleTestCase):
    @override_settings(LOG_EXPORT_STATUS_DATA_ID=456, LOG_EXPORT_STATUS_ACCESS_TOKEN="log-token")
    @mock.patch("core.monitor.report_metric_to_bk_monitor.delay")
    def test_metric_builds_single_record_payload(self, mock_delay):
        metric = Metric(
            metrics={"call_count": 1, "duration_ms": 100},
            dimension={
                "span_name": "risk.nl2risk_filter.generate",
                "status": "success",
                "operation": "nl2risk_filter",
            },
        )

        metric.async_report()

        mock_delay.assert_called_once()
        payload = mock_delay.call_args[0][0]
        self.assertEqual(payload["data_id"], 456)
        self.assertEqual(payload["access_token"], "log-token")
        data = payload["data"][0]
        self.assertEqual(data["target"], "bk_audit")
        self.assertEqual(data["metrics"], {"call_count": 1, "duration_ms": 100})
        self.assertEqual(data["dimension"]["operation"], "nl2risk_filter")
        self.assertEqual(data["dimension"]["status"], "success")
        self.assertIn("job", data["dimension"])

    @override_settings(LOG_EXPORT_STATUS_DATA_ID=456, LOG_EXPORT_STATUS_ACCESS_TOKEN="log-token")
    @mock.patch("core.monitor.report_metric_to_bk_monitor.delay")
    def test_metric_builds_multi_record_payload(self, mock_delay):
        metric = Metric(
            records=[
                {
                    "metrics": {"call_count": 1, "duration_ms": 100},
                    "dimension": {"operation": "nl2risk_filter", "status": "success"},
                },
                {
                    "metrics": {"call_count": 1, "duration_ms": 200},
                    "dimension": {"operation": "generate_analyse_report", "status": "error"},
                    "target": "bk_audit_worker",
                },
            ]
        )

        metric.async_report()

        mock_delay.assert_called_once()
        payload = mock_delay.call_args[0][0]
        self.assertEqual(len(payload["data"]), 2)
        self.assertEqual(payload["data"][0]["target"], "bk_audit")
        self.assertEqual(payload["data"][0]["dimension"]["operation"], "nl2risk_filter")
        self.assertEqual(payload["data"][1]["target"], "bk_audit_worker")
        self.assertEqual(payload["data"][1]["dimension"]["operation"], "generate_analyse_report")
        self.assertIn("job", payload["data"][0]["dimension"])
        self.assertIn("job", payload["data"][1]["dimension"])

    @override_settings(LOG_EXPORT_STATUS_DATA_ID=456, LOG_EXPORT_STATUS_ACCESS_TOKEN="log-token")
    @mock.patch("core.monitor.report_metric_to_bk_monitor.delay", side_effect=RuntimeError("celery failed"))
    def test_metric_async_report_swallows_enqueue_error(self, mock_delay):
        metric = Metric(metrics={"call_count": 1}, dimension={"operation": "nl2risk_filter"})

        self.assertIsNone(metric.async_report())
        mock_delay.assert_called_once()

    @override_settings(LOG_EXPORT_STATUS_DATA_ID=456, LOG_EXPORT_STATUS_ACCESS_TOKEN="log-token")
    @mock.patch("core.monitor.report_metric_to_bk_monitor.delay")
    def test_report_observation_metric_reuses_log_export_status_config(self, mock_delay):
        report_observation_metric(
            name="risk.nl2risk_filter.generate",
            started_at=0,
            status=OBSERVATION_METRIC_STATUS_SUCCESS,
            dimensions={
                "service": "risk",
                "operation": "nl2risk_filter",
                "status": "caller_status",
            },
        )

        mock_delay.assert_called_once()
        payload = mock_delay.call_args[0][0]
        self.assertEqual(payload["data_id"], 456)
        self.assertEqual(payload["access_token"], "log-token")
        self.assertEqual(len(payload["data"]), 1)
        data = payload["data"][0]
        self.assertEqual(data["target"], "bk_audit")
        self.assertEqual(data["metrics"]["call_count"], 1)
        self.assertGreaterEqual(data["metrics"]["duration_ms"], 0)
        self.assertEqual(data["dimension"]["span_name"], "risk.nl2risk_filter.generate")
        self.assertEqual(data["dimension"]["service"], "risk")
        self.assertEqual(data["dimension"]["operation"], "nl2risk_filter")
        self.assertEqual(data["dimension"]["status"], "success")
        self.assertEqual(data["dimension"]["error_type"], "")
        self.assertIn("job", data["dimension"])

    @override_settings(LOG_EXPORT_STATUS_DATA_ID=0, LOG_EXPORT_STATUS_ACCESS_TOKEN="")
    @mock.patch("core.monitor.report_metric_to_bk_monitor.delay")
    def test_report_observation_metric_skips_without_config(self, mock_delay):
        report_observation_metric(
            name="risk.nl2risk_filter.generate",
            started_at=0,
            status=OBSERVATION_METRIC_STATUS_SUCCESS,
            dimensions={"service": "risk"},
        )

        mock_delay.assert_not_called()


class TestBKResourceAPIInstrumentor(SimpleTestCase):
    def setUp(self):
        self.exporter = InMemorySpanExporter()
        self.provider = TracerProvider()
        self.provider.add_span_processor(SimpleSpanProcessor(self.exporter))
        self.provider_patch = mock.patch("core.observability.trace.get_tracer_provider", return_value=self.provider)
        self.provider_patch.start()
        self.instrumentor = BKResourceAPIInstrumentor()
        self.instrumentor.instrument()

    def tearDown(self):
        self.instrumentor.uninstrument()
        self.provider_patch.stop()
        self.exporter.clear()

    def test_api_resource_request_creates_client_span(self):
        response = mock.Mock()
        response.json.return_value = {"result": True, "code": 0, "data": {"ok": True}}
        response.raise_for_status.return_value = None
        response.headers = {}
        response.request.url = "https://example.com/api/v1/do_something/"
        resource = DummyAPIResource()
        resource.session = mock.Mock()
        resource.session.request.return_value = response

        result = resource.request({"foo": "bar"})

        self.assertEqual(result, {"ok": True})
        spans = self.exporter.get_finished_spans()
        self.assertEqual(len(spans), 1)
        span = spans[0]
        self.assertEqual(span.name, "api.bk_dummy.DummyAPIResource")
        self.assertEqual(span.kind, SpanKind.CLIENT)
        self.assertEqual(span.status.status_code, StatusCode.OK)
        self.assertEqual(span.attributes["bk_audit.api.module"], "bk_dummy")
        self.assertEqual(span.attributes["bk_audit.api.resource"], "DummyAPIResource")
        self.assertEqual(span.attributes["bk_audit.api.method"], "POST")
        self.assertEqual(span.attributes["bk_audit.api.action"], "/v1/do_something/")
        self.assertEqual(span.attributes["bk_audit.api.status"], "success")

    def test_api_resource_request_marks_error_span(self):
        class FailedAPIResource(DummyAPIResource):
            def build_url(self, validated_request_data):
                raise ValueError("failed")

        with self.assertRaises(ValueError):
            FailedAPIResource().request({})

        spans = self.exporter.get_finished_spans()
        self.assertEqual(len(spans), 1)
        span = spans[0]
        self.assertEqual(span.name, "api.bk_dummy.FailedAPIResource")
        self.assertEqual(span.status.status_code, StatusCode.ERROR)
        self.assertEqual(span.attributes["bk_audit.api.status"], "error")
        self.assertEqual(span.attributes["bk_audit.api.error_type"], "ValueError")

    def test_api_resource_call_keeps_request_log_inside_client_span(self):
        class TraceCapturingLogHandler:
            trace_id = 0

            def __init__(self, *args, **kwargs):
                pass

            def record(self):
                self.__class__.trace_id = trace.get_current_span().get_span_context().trace_id

        with mock.patch("bk_resource.base.bk_resource_settings.REQUEST_LOG_HANDLER", TraceCapturingLogHandler):
            result = LocalDummyAPIResource()({"foo": "bar"})

        self.assertEqual(result, {"value": "bar"})
        spans = self.exporter.get_finished_spans()
        self.assertEqual(len(spans), 1)
        self.assertEqual(spans[0].name, "api.bk_dummy.LocalDummyAPIResource")
        self.assertEqual(TraceCapturingLogHandler.trace_id, spans[0].context.trace_id)

    def test_api_resource_call_does_not_create_duplicate_request_span(self):
        result = LocalDummyAPIResource()({"foo": "bar"})

        self.assertEqual(result, {"value": "bar"})
        spans = self.exporter.get_finished_spans()
        self.assertEqual([span.name for span in spans], ["api.bk_dummy.LocalDummyAPIResource"])

    def test_api_resource_bulk_request_propagates_parent_context_to_child_threads(self):
        with start_observation_span("risk.bulk.parent"):
            result = LocalDummyAPIResource().bulk_request([{"foo": "one"}, {"foo": "two"}])

        self.assertEqual(result, [{"value": "one"}, {"value": "two"}])
        spans = self.exporter.get_finished_spans()
        parent_span = next(span for span in spans if span.name == "risk.bulk.parent")
        api_spans = [span for span in spans if span.name == "api.bk_dummy.LocalDummyAPIResource"]
        self.assertEqual(len(api_spans), 2)
        self.assertTrue(all(span.parent.span_id == parent_span.context.span_id for span in api_spans))

    def test_local_resource_bulk_request_propagates_parent_context_to_inner_api(self):
        with start_observation_span("risk.local_bulk.parent"):
            result = LocalOuterBulkResource().bulk_request([{"foo": "one"}, {"foo": "two"}])

        self.assertEqual(result, [{"value": "one"}, {"value": "two"}])
        spans = self.exporter.get_finished_spans()
        parent_span = next(span for span in spans if span.name == "risk.local_bulk.parent")
        api_spans = [span for span in spans if span.name == "api.bk_dummy.LocalDummyAPIResource"]
        self.assertEqual(len(api_spans), 2)
        self.assertTrue(all(span.parent.span_id == parent_span.context.span_id for span in api_spans))


class TestStartObservationSpan(SimpleTestCase):
    def setUp(self):
        self.exporter = InMemorySpanExporter()
        self.provider = TracerProvider()
        self.provider.add_span_processor(SimpleSpanProcessor(self.exporter))
        self.provider_patch = mock.patch("core.observability.trace.get_tracer_provider", return_value=self.provider)
        self.provider_patch.start()

    def tearDown(self):
        self.provider_patch.stop()
        self.exporter.clear()

    def test_start_observation_span_records_attributes(self):
        with start_observation_span(
            "risk.nl2risk_filter.generate",
            attributes={
                "bk_audit.service": "risk",
                "bk_audit.operation": "nl2risk_filter",
            },
        ):
            pass

        spans = self.exporter.get_finished_spans()
        self.assertEqual(len(spans), 1)
        span = spans[0]
        self.assertEqual(span.name, "risk.nl2risk_filter.generate")
        self.assertEqual(span.kind, SpanKind.INTERNAL)
        self.assertEqual(span.status.status_code, StatusCode.OK)
        self.assertEqual(span.attributes["bk_audit.service"], "risk")
        self.assertEqual(span.attributes["bk_audit.operation"], "nl2risk_filter")

    def test_start_observation_span_marks_error(self):
        with self.assertRaises(ValueError):
            with start_observation_span("risk.nl2risk_filter.generate"):
                raise ValueError("failed")

        spans = self.exporter.get_finished_spans()
        self.assertEqual(len(spans), 1)
        span = spans[0]
        self.assertEqual(span.status.status_code, StatusCode.ERROR)
        self.assertEqual(span.attributes["bk_audit.error_type"], "ValueError")

    @mock.patch("core.monitor.report_metric_to_bk_monitor.delay")
    def test_start_observation_span_does_not_report_metric(self, mock_delay):
        with start_observation_span(
            "risk.nl2risk_filter.generate",
            attributes={
                "bk_audit.service": "risk",
                "bk_audit.operation": "nl2risk_filter",
            },
        ):
            pass

        mock_delay.assert_not_called()

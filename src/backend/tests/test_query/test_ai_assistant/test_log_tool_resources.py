# -*- coding: utf-8 -*-
"""用户态日志 MCP Resource 与路由契约。"""

import json
from copy import deepcopy
from unittest import mock

import jsonschema
import yaml
from django.test import SimpleTestCase, override_settings
from django.urls import resolve
from drf_spectacular.views import SpectacularAPIView
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory, force_authenticate

from core.permissions import UserAPIGWPermission
from services.web.query.ai_assistant.log_tools.schemas import (
    AggregateLogsRequest,
    AggregateLogsResponse,
    AggregationQuerySummary,
    FieldSampleSummary,
    GetLogFieldMetadataResponse,
    LogSearchPagination,
    SearchLogsResponse,
)
from services.web.query.ai_assistant.serializers import (
    AggregateLogsRequestSerializer,
    GetLogFieldMetadataRequestSerializer,
    SearchLogsRequestSerializer,
)
from tests.test_query.test_ai_assistant.base import AIAssistantTestCase


class TestMCPUserLogRouting(SimpleTestCase):
    """三个日志工具只通过用户态 MCP ViewSet 暴露 POST 路由。"""

    @override_settings(ROOT_URLCONF="services.web.urls")
    def test_log_tools_resolve_to_one_user_apigw_viewset(self):
        from services.web.query.mcp_views import MCPUserLogViewSet

        for endpoint in ("field_metadata", "search", "aggregate"):
            with self.subTest(endpoint=endpoint):
                match = resolve(f"/api/v1/query/namespaces/default/mcp_user/logs/{endpoint}/")
                self.assertIs(match.func.cls, MCPUserLogViewSet)

    def test_viewset_exposes_only_three_post_resources(self):
        from services.web.query.mcp_views import MCPUserLogViewSet

        self.assertEqual(
            [(route.method, route.endpoint) for route in MCPUserLogViewSet.resource_routes],
            [("POST", "field_metadata"), ("POST", "search"), ("POST", "aggregate")],
        )
        self.assertIsInstance(MCPUserLogViewSet().get_permissions()[0], UserAPIGWPermission)


@override_settings(ROOT_URLCONF="services.web.urls")
class TestMCPUserLogResources(AIAssistantTestCase):
    """Resource 仅转换可信用户、路径 namespace 与类型化 Service 协议。"""

    def setUp(self):
        super().setUp()
        self.condition = self.make_condition()

    def test_field_metadata_uses_request_user_and_path_namespace(self):
        from services.web.query.resources.ai_assistant import MCPGetLogFieldMetadata

        response_model = GetLogFieldMetadataResponse(sample_summary=FieldSampleSummary())
        with (
            mock.patch("services.web.query.resources.ai_assistant.get_request_username", return_value="alice"),
            mock.patch(
                "services.web.query.ai_assistant.log_tools.field_metadata.LogFieldMetadataService.get_metadata"
            ) as service,
        ):
            service.return_value = response_model
            response = MCPGetLogFieldMetadata().request(
                namespace="default", condition=self.condition.model_dump(mode="json")
            )

        service.assert_called_once()
        self.assertEqual(service.call_args.kwargs["username"], "alice")
        self.assertEqual(service.call_args.kwargs["namespace"], "default")
        self.assertEqual(response, response_model.model_dump(mode="json"))

    def test_search_uses_request_user_and_path_namespace(self):
        from services.web.query.resources.ai_assistant import MCPSearchLogs

        response_model = SearchLogsResponse(
            total=0,
            pagination=LogSearchPagination(page=1, page_size=20, total=0, returned_count=0, has_more=False),
            query_summary=self.make_query_summary(),
        )
        with (
            mock.patch("services.web.query.resources.ai_assistant.get_request_username", return_value="alice"),
            mock.patch("services.web.query.ai_assistant.log_tools.search.LogDetailSearchService.search") as service,
        ):
            service.return_value = response_model
            response = MCPSearchLogs().request(namespace="default", condition=self.condition.model_dump(mode="json"))

        service.assert_called_once()
        self.assertEqual(service.call_args.kwargs["username"], "alice")
        self.assertEqual(service.call_args.kwargs["namespace"], "default")
        self.assertEqual(response, response_model.model_dump(mode="json"))

    def test_aggregate_uses_request_user_and_path_namespace(self):
        from services.web.query.resources.ai_assistant import MCPAggregateLogs

        response_model = AggregateLogsResponse(
            columns=(),
            rows=(),
            query_summary=AggregationQuerySummary(
                returned_count=0, has_more=False, took_ms=1, executed_at=self.end_time
            ),
        )
        with (
            mock.patch("services.web.query.resources.ai_assistant.get_request_username", return_value="alice"),
            mock.patch(
                "services.web.query.ai_assistant.log_tools.aggregation.LogAggregationService.aggregate"
            ) as service,
        ):
            service.return_value = response_model
            response = MCPAggregateLogs().request(
                namespace="default",
                condition=self.condition.model_dump(mode="json"),
                metrics=[{"id": "total", "type": "COUNT"}],
            )

        service.assert_called_once()
        self.assertEqual(service.call_args.kwargs["username"], "alice")
        self.assertEqual(service.call_args.kwargs["namespace"], "default")
        self.assertEqual(response, response_model.model_dump(mode="json"))

    def test_aggregate_http_accepts_model_dump_with_explicit_nulls(self):
        request_model = AggregateLogsRequest.model_validate(
            {
                "condition": self.condition.model_dump(mode="json"),
                "metrics": [{"id": "count", "type": "COUNT"}],
            }
        )
        request = APIRequestFactory().post(
            "/api/v1/query/namespaces/path-ns/mcp_user/logs/aggregate/",
            request_model.model_dump(mode="json"),
            format="json",
        )
        force_authenticate(request, user=type("User", (), {"username": "gateway-user", "is_authenticated": True})())
        response_model = AggregateLogsResponse(
            columns=(),
            rows=(),
            query_summary=AggregationQuerySummary(
                returned_count=0, has_more=False, took_ms=1, executed_at=self.end_time
            ),
        )
        with (
            mock.patch("core.permissions.get_app_info"),
            mock.patch("query.resources.ai_assistant.get_request_username", return_value="gateway-user"),
            mock.patch(
                "services.web.query.ai_assistant.log_tools.aggregation.LogAggregationService.aggregate",
                return_value=response_model,
            ) as service,
        ):
            response = self._view("aggregate")(request, namespace="path-ns")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(service.call_args.kwargs["request"], request_model)
        self.assertEqual(service.call_args.kwargs["namespace"], "path-ns")

    def test_http_response_uses_standard_envelope_after_render(self):
        request = APIRequestFactory().post(
            "/api/v1/query/namespaces/path-ns/mcp_user/logs/field_metadata/",
            {
                "condition": self.condition.model_dump(mode="json"),
            },
            format="json",
        )
        force_authenticate(request, user=type("User", (), {"username": "gateway-user", "is_authenticated": True})())
        view = self._view("field_metadata")

        with (
            mock.patch("core.permissions.get_app_info"),
            mock.patch("query.resources.ai_assistant.get_request_username", return_value="gateway-user"),
            mock.patch(
                "services.web.query.ai_assistant.log_tools.field_metadata.LogFieldMetadataService.get_metadata",
                return_value=GetLogFieldMetadataResponse(sample_summary=FieldSampleSummary()),
            ) as service,
        ):
            response = view(request, namespace="path-ns")

        self.assertEqual(response.status_code, 200, response.data)
        response.render()
        body = json.loads(response.content)
        self.assertTrue(body["result"])
        self.assertEqual(body["code"], 0)
        self.assertIn("data", body)
        self.assertEqual(body["data"]["sample_summary"]["sampled_count"], 0)
        self.assertEqual(
            service.call_args.kwargs, {"username": "gateway-user", "namespace": "path-ns", "request": mock.ANY}
        )

    def test_rendered_http_json_validates_against_openapi_response_schema(self):
        request = APIRequestFactory().post(
            "/api/v1/query/namespaces/path-ns/mcp_user/logs/field_metadata/",
            {"condition": self.condition.model_dump(mode="json")},
            format="json",
        )
        force_authenticate(request, user=type("User", (), {"username": "gateway-user", "is_authenticated": True})())
        with (
            mock.patch("core.permissions.get_app_info"),
            mock.patch("query.resources.ai_assistant.get_request_username", return_value="gateway-user"),
            mock.patch(
                "services.web.query.ai_assistant.log_tools.field_metadata.LogFieldMetadataService.get_metadata",
                return_value=GetLogFieldMetadataResponse(sample_summary=FieldSampleSummary()),
            ),
        ):
            response = self._view("field_metadata")(request, namespace="path-ns")

        response.render()
        schema_response = SpectacularAPIView.as_view()(APIRequestFactory().get("/api/schema/"))
        schema_response.render()
        schema = yaml.safe_load(schema_response.content)
        response_schema = schema["paths"]["/api/v1/query/namespaces/{namespace}/mcp_user/logs/field_metadata/"]["post"][
            "responses"
        ]["200"]["content"]["application/json"]["schema"]
        validator = jsonschema.Draft7Validator(self._openapi_json_schema(response_schema))
        errors = list(validator.iter_errors(json.loads(response.content)))
        self.assertEqual(errors, [], "\n".join(f"{list(error.path)}: {error.message}" for error in errors))

    def test_raw_body_rejects_unknown_identity_fields(self):
        view = self._view("field_metadata")

        for forged_field in ("username", "app_code", "sql"):
            with self.subTest(forged_field=forged_field):
                request = APIRequestFactory().post(
                    "/api/v1/query/namespaces/path-ns/mcp_user/logs/field_metadata/",
                    {"condition": self.condition.model_dump(mode="json"), forged_field: "forged"},
                    format="json",
                )
                force_authenticate(
                    request, user=type("User", (), {"username": "gateway-user", "is_authenticated": True})()
                )
                with (
                    mock.patch("core.permissions.get_app_info"),
                    mock.patch(
                        "services.web.query.ai_assistant.log_tools.field_metadata.LogFieldMetadataService.get_metadata"
                    ) as service,
                ):
                    response = view(request, namespace="path-ns")

                self.assertEqual(response.status_code, 400)
                self.assertIn(forged_field, str(response.data))
                service.assert_not_called()

    def test_field_metadata_http_rejects_unsafe_parent_key(self):
        request = APIRequestFactory().post(
            "/api/v1/query/namespaces/path-ns/mcp_user/logs/field_metadata/",
            {"condition": self.condition.model_dump(mode="json"), "parent_keys": ["unsafe-key"]},
            format="json",
        )
        force_authenticate(request, user=type("User", (), {"username": "gateway-user", "is_authenticated": True})())
        with (
            mock.patch("core.permissions.get_app_info"),
            mock.patch(
                "services.web.query.ai_assistant.log_tools.field_metadata.LogFieldMetadataService.get_metadata"
            ) as service,
        ):
            response = self._view("field_metadata")(request, namespace="path-ns")

        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("parent_keys", str(response.data))
        service.assert_not_called()

    def test_body_namespace_is_rejected_before_resource_execution(self):
        cases = (
            (
                "field_metadata",
                {"condition": self.condition.model_dump(mode="json")},
                "services.web.query.ai_assistant.log_tools.field_metadata.LogFieldMetadataService.get_metadata",
            ),
            (
                "search",
                {"condition": self.condition.model_dump(mode="json")},
                "services.web.query.ai_assistant.log_tools.search.LogDetailSearchService.search",
            ),
            (
                "aggregate",
                {
                    "condition": self.condition.model_dump(mode="json"),
                    "metrics": [{"id": "count", "type": "COUNT"}],
                },
                "services.web.query.ai_assistant.log_tools.aggregation.LogAggregationService.aggregate",
            ),
        )
        for endpoint, payload, service_path in cases:
            with self.subTest(endpoint=endpoint):
                request = APIRequestFactory().post(
                    f"/api/v1/query/namespaces/path-ns/mcp_user/logs/{endpoint}/",
                    {**payload, "namespace": "forged-ns"},
                    format="json",
                )
                force_authenticate(
                    request, user=type("User", (), {"username": "gateway-user", "is_authenticated": True})()
                )
                with mock.patch("core.permissions.get_app_info"), mock.patch(service_path) as service:
                    response = self._view(endpoint)(request, namespace="path-ns")

                self.assertEqual(response.status_code, 400, response.data)
                self.assertIn("namespace", str(response.data))
                service.assert_not_called()

    def test_non_object_json_body_is_rejected_before_resource_execution(self):
        cases = (
            (
                "field_metadata",
                "services.web.query.ai_assistant.log_tools.field_metadata.LogFieldMetadataService.get_metadata",
            ),
            ("search", "services.web.query.ai_assistant.log_tools.search.LogDetailSearchService.search"),
            ("aggregate", "services.web.query.ai_assistant.log_tools.aggregation.LogAggregationService.aggregate"),
        )
        for endpoint, service_path in cases:
            for payload in ([], None, "not-an-object"):
                with self.subTest(endpoint=endpoint, payload=payload):
                    request = APIRequestFactory().generic(
                        "POST",
                        f"/api/v1/query/namespaces/path-ns/mcp_user/logs/{endpoint}/",
                        data=json.dumps(payload),
                        content_type="application/json",
                    )
                    force_authenticate(
                        request, user=type("User", (), {"username": "gateway-user", "is_authenticated": True})()
                    )
                    with mock.patch("core.permissions.get_app_info"), mock.patch(service_path) as service:
                        response = self._view(endpoint)(request, namespace="path-ns")

                    self.assertEqual(response.status_code, 400, response.data)
                    self.assertIn("JSON 对象", str(response.data))
                    service.assert_not_called()

    def test_request_serializers_reject_non_mapping_data_cleanly(self):
        for serializer_class in (
            GetLogFieldMetadataRequestSerializer,
            SearchLogsRequestSerializer,
            AggregateLogsRequestSerializer,
        ):
            for payload in ([], None, "not-an-object"):
                with self.subTest(serializer=serializer_class.__name__, payload=payload):
                    with self.assertRaisesRegex(ValidationError, "JSON 对象"):
                        serializer_class(data=payload).is_valid()

    def test_raw_body_rejects_unknown_nested_request_fields(self):
        cases = (
            ("field_metadata", {"condition": {**self.condition.model_dump(mode="json"), "sql": "select 1"}}),
            (
                "field_metadata",
                {
                    "condition": {
                        **self.condition.model_dump(mode="json"),
                        "conditions": [
                            {
                                "field": {"raw_name": "action_id", "sql": "select 1"},
                                "operator": "eq",
                                "filters": ["read"],
                            }
                        ],
                    }
                },
            ),
            (
                "search",
                {
                    "condition": self.condition.model_dump(mode="json"),
                    "fields": [{"raw_name": "start_time", "sql": "select 1"}],
                },
            ),
            (
                "aggregate",
                {
                    "condition": self.condition.model_dump(mode="json"),
                    "dimensions": [{"id": "d", "type": "FIELD", "field": {"raw_name": "action_id"}, "sql": "x"}],
                    "metrics": [{"id": "count", "type": "COUNT", "sql": "x"}],
                    "order_by": [{"target_id": "count", "direction": "DESC", "sql": "x"}],
                },
            ),
        )
        for endpoint, payload in cases:
            with self.subTest(endpoint=endpoint):
                request = APIRequestFactory().post(
                    f"/api/v1/query/namespaces/path-ns/mcp_user/logs/{endpoint}/", payload, format="json"
                )
                force_authenticate(
                    request, user=type("User", (), {"username": "gateway-user", "is_authenticated": True})()
                )
                view = self._view(endpoint)
                with mock.patch("core.permissions.get_app_info"):
                    response = view(request, namespace="path-ns")

                self.assertEqual(response.status_code, 400)
                self.assertIn("sql", str(response.data))

    @staticmethod
    def _view(endpoint):
        return resolve(f"/api/v1/query/namespaces/path-ns/mcp_user/logs/{endpoint}/").func

    @classmethod
    def _openapi_json_schema(cls, value):
        if isinstance(value, list):
            return [cls._openapi_json_schema(item) for item in value]
        if not isinstance(value, dict):
            return value
        result = {key: cls._openapi_json_schema(item) for key, item in deepcopy(value).items() if key != "nullable"}
        if value.get("nullable") and isinstance(result.get("type"), str):
            result["type"] = [result["type"], "null"]
        if value.get("nullable") and isinstance(result.get("enum"), list):
            result["enum"] = [*result["enum"], None]
        return result

    def make_query_summary(self):
        from services.web.query.ai_assistant.schemas import QuerySummary

        return QuerySummary(
            scope_type=self.condition.scope_type,
            scope_id=self.condition.scope_id,
            time_range={"start_time": self.condition.start_time, "end_time": self.condition.end_time},
            executed_at=self.end_time,
        )

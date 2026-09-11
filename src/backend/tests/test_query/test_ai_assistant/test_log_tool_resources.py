# -*- coding: utf-8 -*-
"""用户态日志 MCP Resource 与路由契约。"""

import json
from copy import deepcopy
from pathlib import Path
from unittest import mock

import jsonschema
import yaml
from django.test import SimpleTestCase, override_settings
from django.urls import resolve
from drf_spectacular.views import SpectacularAPIView
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory, force_authenticate

from api.bk_base.default import SafeQuerySyncResource
from apps.meta.constants import SENSITIVE_REPLACE_VALUE, SensitiveResourceTypeEnum
from apps.meta.models import SensitiveObject
from core.exceptions import PermissionException
from core.permissions import UserAPIGWPermission
from services.web.query.ai_assistant.exceptions import (
    InvalidLogCondition,
    LogQueryFailed,
    LogQueryResponseTooLarge,
    LogQueryTimeout,
    SensitiveFieldPermissionDenied,
    UnsupportedAggregation,
    UnsupportedLogField,
)
from services.web.query.ai_assistant.log_tools.schemas import (
    AggregateLogsRequest,
    AggregateLogsResponse,
    AggregationQuerySummary,
    FieldSampleSummary,
    GetLogFieldMetadataResponse,
    LogDetailColumn,
    LogFieldMetadataItem,
    LogQueryExecutionSummary,
    LogSearchPagination,
    SearchLogsResponse,
)
from services.web.query.ai_assistant.serializers import (
    AggregateLogsRequestSerializer,
    GetLogFieldMetadataRequestSerializer,
    SearchLogsRequestSerializer,
)
from services.web.query.resources.ai_assistant import MCPSearchLogs
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

    def test_search_request_matches_sensitive_rules_before_masking_action(self):
        """公开入口保留真实脱敏链路，校验私密、授权和不匹配规则。"""
        first = SensitiveObject(
            id=1,
            system_id=self.target_system_id,
            resource_type=SensitiveResourceTypeEnum.RESOURCE.value,
            resource_id="host",
            fields=[{"field_name": "action_id"}],
        )
        secret_rule = SensitiveObject(
            id=2,
            system_id=self.target_system_id,
            resource_type=SensitiveResourceTypeEnum.ACTION.value,
            resource_id="view",
            fields=[{"field_name": "extend_data.secret"}],
        )
        with (
            mock.patch("services.web.query.resources.ai_assistant.get_request_username", return_value="alice"),
            mock.patch(
                "services.web.query.ai_assistant.log_tools.context.SearchLogPermission.has_system_search_permission",
                return_value=True,
            ),
            mock.patch("services.web.query.ai_assistant.log_tools.context.System.objects") as systems,
            mock.patch(
                "services.web.query.ai_assistant.log_tools.context.CollectorPlugin.build_collector_rt",
                return_value="test_table",
            ),
            mock.patch("services.web.query.search_data.SensitiveObject._objects") as private_objects,
            mock.patch("services.web.query.search_data.SensitiveObject.objects") as public_objects,
            mock.patch("services.web.query.search_data.PermissionService") as permissions,
            mock.patch.object(SafeQuerySyncResource, "bulk_request") as query,
        ):
            systems.filter.return_value.exists.return_value = True
            for private, authorized, matched in (
                (True, False, True),
                (True, True, True),
                (False, False, True),
                (False, True, True),
                (True, False, False),
            ):
                for reverse in (False, True):
                    with self.subTest(private=private, authorized=authorized, matched=matched, reverse=reverse):
                        secret = deepcopy(secret_rule)
                        secret.is_private = private
                        secret.resource_id = "view" if matched else "other-action"
                        private_objects.filter.return_value.filter.return_value = [secret] if private else []
                        rules = [first] if private else ([secret, first] if reverse else [first, secret])
                        public_objects.all.return_value.filter.return_value = rules
                        permissions.return_value.get_sensitive_object_permissions.return_value = {
                            "1": authorized,
                            "2": authorized,
                        }
                        query.return_value = (
                            {
                                "list": [
                                    {
                                        "system_id": self.target_system_id,
                                        "resource_type_id": "host",
                                        "action_id": "view",
                                        "extend_data": {"secret": "raw-secret", "public": "visible"},
                                        "log": "payload raw-secret",
                                    }
                                ]
                            },
                            {"list": [{"count": 1}]},
                        )

                        result = MCPSearchLogs().request(
                            namespace=self.namespace,
                            condition=self.condition.model_dump(mode="json"),
                            fields=[{"raw_name": name} for name in ("action_id", "extend_data", "log")],
                        )

                        expected_data = {"public": "visible"}
                        if not matched or (authorized and not private):
                            expected_data["secret"] = "raw-secret"
                        elif not private:
                            expected_data["secret"] = SENSITIVE_REPLACE_VALUE
                        self.assertEqual(
                            result["items"],
                            [
                                {
                                    "action_id": "view" if authorized else SENSITIVE_REPLACE_VALUE,
                                    "extend_data": expected_data,
                                    "log": (
                                        "payload raw-secret"
                                        if authorized and not (private and matched)
                                        else SENSITIVE_REPLACE_VALUE
                                    ),
                                }
                            ],
                        )
                        self.assertEqual(result["total"], 1)
                        self.assertEqual(
                            result["pagination"],
                            {"page": 1, "page_size": 20, "returned_count": 1, "has_more": False},
                        )

    def test_sensitive_precheck_uses_sql_normalized_condition_paths(self):
        from services.web.query.resources.ai_assistant import (
            MCPAggregateLogs,
            MCPGetLogFieldMetadata,
            MCPSearchLogs,
        )

        # 不 mock Context/序列化器/权限判定本身，只替换基础设施；验证公开入口到 SQL 前的路径。
        sensitive_rule = mock.Mock(id=1, fields=[{"field_name": "extend_data. secret "}], is_private=True)
        cases = (
            ("extend_data", [" secret "], "eq"),
            ("log", ["bypass"], "match_any"),
        )
        resources = (
            (MCPSearchLogs, {}),
            (MCPGetLogFieldMetadata, {"parent_field": {"raw_name": "extend_data", "keys": ["public"]}}),
            (MCPAggregateLogs, {"metrics": [{"id": "total", "type": "COUNT"}]}),
        )
        with (
            mock.patch("services.web.query.resources.ai_assistant.get_request_username", return_value="alice"),
            mock.patch(
                "services.web.query.ai_assistant.log_tools.context.SearchLogPermission.has_system_search_permission",
                return_value=True,
            ),
            mock.patch("services.web.query.ai_assistant.log_tools.context.System.objects") as systems,
            mock.patch(
                "services.web.query.ai_assistant.log_tools.context.CollectorPlugin.build_collector_rt",
                return_value="test_table",
            ),
            mock.patch(
                "services.web.query.ai_assistant.log_tools.sensitive.SensitiveObject._objects"
            ) as sensitive_objects,
            mock.patch.object(SafeQuerySyncResource, "bulk_request") as query,
            mock.patch.object(SafeQuerySyncResource, "request") as single_query,
        ):
            systems.filter.return_value.exists.return_value = True
            sensitive_objects.filter.return_value = [sensitive_rule]
            for resource_class, extra in resources:
                for raw_name, keys, operator in cases:
                    condition = self.make_condition(
                        conditions=[self.make_field_condition(raw_name=raw_name, keys=keys, operator=operator)]
                    )
                    with self.subTest(resource=resource_class.__name__, field=raw_name):
                        with self.assertRaises(SensitiveFieldPermissionDenied):
                            resource_class().request(
                                namespace="default", condition=condition.model_dump(mode="json"), **extra
                            )
            query.assert_not_called()
            single_query.assert_not_called()

    def test_http_serializers_honor_optional_empty_list_defaults(self):
        condition = self.condition.model_dump(mode="json")
        condition["conditions"] = [{"field": {"raw_name": "extend_data"}, "operator": "isnull"}]
        cases = (
            (SearchLogsRequestSerializer, {"fields": [{"raw_name": "username"}]}),
            (GetLogFieldMetadataRequestSerializer, {"parent_field": {"raw_name": "extend_data"}}),
            (
                AggregateLogsRequestSerializer,
                {
                    "dimensions": [{"id": "action", "type": "FIELD", "field": {"raw_name": "action_id"}}],
                    "metrics": [{"id": "total", "type": "COUNT"}],
                },
            ),
        )
        for serializer_class, extra in cases:
            with self.subTest(serializer=serializer_class.__name__):
                serializer = serializer_class(data={"namespace": "default", "condition": condition, **extra})
                self.assertTrue(serializer.is_valid(), serializer.errors)
                normalized = serializer.validated_data["condition"]["conditions"][0]
                self.assertEqual(normalized["field"]["keys"], [])
                self.assertEqual(normalized["filters"], [])

    def test_request_serializers_keep_validated_data_json_shaped(self):
        """DRF 层只完成 HTTP 适配，领域对象统一在 Resource 边界构造。"""

        serializer = SearchLogsRequestSerializer(
            data={
                "namespace": "default",
                "condition": self.condition.model_dump(mode="json"),
                "fields": [{"raw_name": "username"}],
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertIsInstance(serializer.validated_data["condition"], dict)
        self.assertIsInstance(serializer.validated_data["fields"][0], dict)

    def test_field_metadata_uses_request_user_and_path_namespace(self):
        from services.web.query.resources.ai_assistant import MCPGetLogFieldMetadata

        response_model = GetLogFieldMetadataResponse(
            fields=[
                LogFieldMetadataItem(
                    field={"raw_name": "extend_data", "keys": ["request_data"]},
                    category="EXTENDED",
                    type_source="INFERRED",
                    description="",
                )
            ],
            sample_summary=FieldSampleSummary(),
        )
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
            columns=[
                LogDetailColumn(
                    field={"raw_name": "extend_data", "keys": ["request_data"]},
                    key="extend_data.request_data",
                    description="",
                )
            ],
            total=0,
            pagination=LogSearchPagination(page=1, page_size=20, returned_count=0, has_more=False),
            query_summary=LogQueryExecutionSummary(took_ms=1, executed_at=self.end_time),
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

    def test_aggregate_resource_request_preserves_system_permission_exception_and_skips_doris(self):
        from services.web.query.resources.ai_assistant import MCPAggregateLogs

        permission_error = PermissionException(
            action_name="view_system",
            permission={"system_id": self.condition.scope_id},
            apply_url="https://iam.example/apply",
        )
        with (
            mock.patch("services.web.query.resources.ai_assistant.get_request_username", return_value="alice"),
            mock.patch(
                "services.web.query.ai_assistant.log_tools.aggregation.LogQueryContextService.build",
                side_effect=permission_error,
            ),
            mock.patch.object(SafeQuerySyncResource, "bulk_request") as query,
        ):
            try:
                MCPAggregateLogs().request(
                    namespace="default",
                    condition=self.condition.model_dump(mode="json"),
                    metrics=[{"id": "count", "type": "COUNT"}],
                )
            except Exception as error:  # noqa: BLE001 - 断言 Resource 保留同一平台权限异常。
                raised = error
            else:
                self.fail("system permission failure must be raised")

        self.assertIs(raised, permission_error)
        self.assertEqual(raised.STATUS_CODE, 403)
        self.assertEqual(raised.code, "9900403")
        self.assertEqual(
            json.loads(raised.data),
            {
                "permission": {"system_id": self.condition.scope_id},
                "apply_url": "https://iam.example/apply",
            },
        )
        query.assert_not_called()

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

    def test_field_metadata_http_rejects_oversized_parent_key(self):
        request = APIRequestFactory().post(
            "/api/v1/query/namespaces/path-ns/mcp_user/logs/field_metadata/",
            {
                "condition": self.condition.model_dump(mode="json"),
                "parent_field": {"raw_name": "extend_data", "keys": ["x" * 129]},
            },
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
        self.assertEqual(str(response.data["code"]), UnsupportedLogField().code)
        service.assert_not_called()

    def test_public_http_maps_schema_errors_to_stable_domain_codes(self):
        cases = (
            (
                "field_metadata",
                {
                    "condition": self.condition.model_dump(mode="json"),
                    "parent_field": {"raw_name": "unknown", "keys": []},
                },
                UnsupportedLogField,
            ),
            (
                "aggregate",
                {
                    "condition": self.condition.model_dump(mode="json"),
                    "metrics": [{"id": "count", "type": "COUNT", "field": {"raw_name": "username"}}],
                },
                UnsupportedAggregation,
            ),
            (
                "search",
                {
                    "condition": {
                        **self.condition.model_dump(mode="json"),
                        "conditions": [
                            {
                                "field": {"raw_name": "unknown", "keys": []},
                                "operator": "eq",
                                "filters": ["alice"],
                            }
                        ],
                    }
                },
                UnsupportedLogField,
            ),
            (
                "search",
                {
                    "condition": {
                        **self.condition.model_dump(mode="json"),
                        "conditions": [
                            {
                                "field": {"raw_name": "username", "keys": []},
                                "operator": "unknown",
                                "filters": ["alice"],
                            }
                        ],
                    }
                },
                UnsupportedLogField,
            ),
            (
                "search",
                {
                    "condition": {
                        **self.condition.model_dump(mode="json"),
                        "conditions": [
                            {
                                "field": {"raw_name": "username", "keys": []},
                                "operator": "like",
                                "filters": ["alice"],
                            }
                        ],
                    }
                },
                UnsupportedLogField,
            ),
            (
                "search",
                {
                    "condition": {
                        **self.condition.model_dump(mode="json"),
                        "conditions": [
                            {
                                "field": {"raw_name": "username", "keys": []},
                                "operator": "eq",
                                "filters": ["alice"],
                            }
                        ]
                        * 101,
                    }
                },
                InvalidLogCondition,
            ),
        )
        for endpoint, payload, exception_type in cases:
            with self.subTest(endpoint=endpoint):
                request = APIRequestFactory().post(
                    f"/api/v1/query/namespaces/path-ns/mcp_user/logs/{endpoint}/", payload, format="json"
                )
                force_authenticate(
                    request, user=type("User", (), {"username": "gateway-user", "is_authenticated": True})()
                )
                with mock.patch("core.permissions.get_app_info"):
                    response = self._view(endpoint)(request, namespace="path-ns")

                self.assertEqual(response.status_code, exception_type.STATUS_CODE, response.data)
                response.render()
                body = json.loads(response.content)
                self.assertEqual(str(body["code"]), exception_type().code)
                self.assertEqual(body["message"], str(exception_type.MESSAGE))

    def test_public_http_rejects_complex_filter_values_before_service(self):
        """对象和数组过滤值必须在协议层失败，不能流入 SQL 构建。"""

        for value in ({"nested": "value"}, ["nested"], True, None):
            with self.subTest(value=value):
                condition = self.condition.model_dump(mode="json")
                condition["conditions"] = [
                    {
                        "field": {"raw_name": "username", "keys": []},
                        "operator": "eq",
                        "filters": [value],
                    }
                ]
                request = APIRequestFactory().post(
                    "/api/v1/query/namespaces/path-ns/mcp_user/logs/search/",
                    {"condition": condition},
                    format="json",
                )
                force_authenticate(
                    request,
                    user=type("User", (), {"username": "gateway-user", "is_authenticated": True})(),
                )
                with (
                    mock.patch("core.permissions.get_app_info"),
                    mock.patch(
                        "services.web.query.ai_assistant.log_tools.search.LogDetailSearchService.search"
                    ) as service,
                ):
                    response = self._view("search")(request, namespace="path-ns")

                self.assertEqual(response.status_code, InvalidLogCondition.STATUS_CODE, response.data)
                response.render()
                body = json.loads(response.content)
                self.assertEqual(str(body["code"]), InvalidLogCondition().code)
                service.assert_not_called()

    def test_real_error_envelopes_match_dynamic_and_apigw_schemas(self):
        """真实 APIRenderer 响应必须同时满足代码与网关公开契约。"""

        schema_response = SpectacularAPIView.as_view()(APIRequestFactory().get("/api/schema/"))
        schema_response.render()
        openapi = yaml.safe_load(schema_response.content)
        operation = openapi["paths"]["/api/v1/query/namespaces/{namespace}/mcp_user/logs/search/"]["post"]

        backend_root = Path(__file__).resolve().parents[3]
        apigw = yaml.safe_load((backend_root / "support-files/apigw/resources.yaml").read_text(encoding="utf-8"))
        apigw_error_schema = self._openapi_json_schema(
            {
                "$ref": "#/definitions/log_tool_error_response",
                "definitions": apigw["definitions"],
            }
        )
        apigw_validator = jsonschema.Draft4Validator(apigw_error_schema)

        def validate_response_body(status_code, body):
            dynamic_schema = self._openapi_json_schema(
                operation["responses"][str(status_code)]["content"]["application/json"]["schema"]
            )
            dynamic_errors = list(jsonschema.Draft7Validator(dynamic_schema).iter_errors(body))
            static_errors = list(apigw_validator.iter_errors(body))
            self.assertEqual(dynamic_errors, [], "\n".join(item.message for item in dynamic_errors))
            self.assertEqual(static_errors, [], "\n".join(item.message for item in static_errors))

        permission_error = PermissionException(
            action_name="view_system",
            permission={"system_id": self.condition.scope_id},
            apply_url="https://iam.example/apply",
        )
        cases = (
            InvalidLogCondition(),
            SensitiveFieldPermissionDenied(),
            permission_error,
            LogQueryResponseTooLarge(),
            LogQueryFailed(),
            LogQueryTimeout(),
        )
        for error in cases:
            with self.subTest(error=type(error).__name__):
                request = APIRequestFactory().post(
                    "/api/v1/query/namespaces/path-ns/mcp_user/logs/search/",
                    {"condition": self.condition.model_dump(mode="json")},
                    format="json",
                )
                force_authenticate(
                    request,
                    user=type("User", (), {"username": "gateway-user", "is_authenticated": True})(),
                )
                with (
                    mock.patch("core.permissions.get_app_info"),
                    mock.patch("query.resources.ai_assistant.get_request_username", return_value="gateway-user"),
                    mock.patch(
                        "services.web.query.ai_assistant.log_tools.search.LogDetailSearchService.search",
                        side_effect=error,
                    ),
                ):
                    response = self._view("search")(request, namespace="path-ns")

                self.assertEqual(response.status_code, error.STATUS_CODE, response.data)
                response.render()
                body = json.loads(response.content)
                self.assertEqual(str(body["code"]), error.code)
                self.assertEqual(body["message"], str(error.message))
                validate_response_body(error.STATUS_CODE, body)

        request = APIRequestFactory().post(
            "/api/v1/query/namespaces/path-ns/mcp_user/logs/search/",
            {"condition": self.condition.model_dump(mode="json"), "unknown_field": True},
            format="json",
        )
        force_authenticate(
            request,
            user=type("User", (), {"username": "gateway-user", "is_authenticated": True})(),
        )
        with mock.patch("core.permissions.get_app_info"):
            response = self._view("search")(request, namespace="path-ns")

        self.assertEqual(response.status_code, 400, response.data)
        response.render()
        validate_response_body(400, json.loads(response.content))

    @override_settings(AI_LOG_SEARCH_MAX_PAGE_SIZE=20)
    def test_public_http_maps_runtime_pagination_limits_to_invalid_condition(self):
        for field_name, invalid_value in (("page", 0), ("page_size", 21)):
            with self.subTest(field_name=field_name):
                payload = {
                    "condition": self.condition.model_dump(mode="json"),
                    field_name: invalid_value,
                }
                request = APIRequestFactory().post(
                    "/api/v1/query/namespaces/path-ns/mcp_user/logs/search/",
                    payload,
                    format="json",
                )
                force_authenticate(
                    request,
                    user=type("User", (), {"username": "gateway-user", "is_authenticated": True})(),
                )
                with mock.patch("core.permissions.get_app_info"):
                    response = self._view("search")(request, namespace="path-ns")

                self.assertEqual(response.status_code, InvalidLogCondition.STATUS_CODE, response.data)
                response.render()
                body = json.loads(response.content)
                self.assertEqual(str(body["code"]), InvalidLogCondition().code)
                self.assertEqual(body["message"], str(InvalidLogCondition.MESSAGE))

    def test_resource_request_rejects_oversized_shared_condition_before_service(self):
        from services.web.query.resources.ai_assistant import MCPAggregateLogs

        condition = self.condition.model_dump(mode="json")
        condition["conditions"] = [
            {
                "field": {"raw_name": "username", "keys": []},
                "operator": "eq",
                "filters": ["alice"],
            }
        ] * 101
        with mock.patch(
            "services.web.query.ai_assistant.log_tools.aggregation.LogAggregationService.aggregate"
        ) as service:
            with self.assertRaises(InvalidLogCondition):
                MCPAggregateLogs().request(
                    namespace="default",
                    condition=condition,
                    metrics=[{"id": "count", "type": "COUNT"}],
                )

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
            (
                "field_metadata",
                {"condition": {**self.condition.model_dump(mode="json"), "sql": "select 1"}},
                InvalidLogCondition,
            ),
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
                InvalidLogCondition,
            ),
            (
                "search",
                {
                    "condition": self.condition.model_dump(mode="json"),
                    "fields": [{"raw_name": "start_time", "sql": "select 1"}],
                },
                UnsupportedLogField,
            ),
            (
                "aggregate",
                {
                    "condition": self.condition.model_dump(mode="json"),
                    "dimensions": [{"id": "d", "type": "FIELD", "field": {"raw_name": "action_id"}, "sql": "x"}],
                    "metrics": [{"id": "count", "type": "COUNT", "sql": "x"}],
                    "order_by": [{"target_id": "count", "direction": "DESC", "sql": "x"}],
                },
                UnsupportedAggregation,
            ),
        )
        for endpoint, payload, exception_type in cases:
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
                self.assertEqual(str(response.data["code"]), exception_type().code)
                self.assertNotIn("sql", str(response.data))

    @staticmethod
    def _view(endpoint):
        return resolve(f"/api/v1/query/namespaces/path-ns/mcp_user/logs/{endpoint}/").func

    @classmethod
    def _openapi_json_schema(cls, value):
        if isinstance(value, list):
            return [cls._openapi_json_schema(item) for item in value]
        if not isinstance(value, dict):
            return value
        nullable = value.get("nullable") or value.get("x-nullable")
        result = {
            key: cls._openapi_json_schema(item)
            for key, item in deepcopy(value).items()
            if key not in {"nullable", "x-nullable"}
        }
        if nullable and isinstance(result.get("type"), str):
            result["type"] = [result["type"], "null"]
        if nullable and isinstance(result.get("enum"), list):
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

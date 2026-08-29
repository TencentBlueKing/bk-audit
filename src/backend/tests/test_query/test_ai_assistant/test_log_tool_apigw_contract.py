# -*- coding: utf-8 -*-
"""日志 MCP 的 APIGW YAML 契约。"""

from copy import deepcopy
from pathlib import Path
from unittest import mock

import jsonschema
import yaml
from django.test import SimpleTestCase, override_settings
from drf_spectacular.views import SpectacularAPIView
from rest_framework.test import APIRequestFactory

from services.web.query.ai_assistant.log_tools.schemas import (
    AggregateLogsRequest,
    AggregateLogsResponse,
    AggregationColumn,
    AggregationQuerySummary,
    FieldSampleSummary,
    GetLogFieldMetadataRequest,
    GetLogFieldMetadataResponse,
    LogDetailColumn,
    LogFieldMetadataItem,
    LogFieldRef,
    LogSearchPagination,
    SearchLogsRequest,
    SearchLogsResponse,
)
from services.web.query.ai_assistant.schemas import QuerySummary

BACKEND_ROOT = Path(__file__).resolve().parents[3]
MCP_LOG_RESOURCES = {
    "mcp_get_log_field_metadata": (
        "/mcp/{namespace}/logs/field_metadata/",
        "/api/v1/query/namespaces/{namespace}/mcp_user/logs/field_metadata/",
    ),
    "mcp_search_logs": (
        "/mcp/{namespace}/logs/search/",
        "/api/v1/query/namespaces/{namespace}/mcp_user/logs/search/",
    ),
    "mcp_aggregate_logs": (
        "/mcp/{namespace}/logs/aggregate/",
        "/api/v1/query/namespaces/{namespace}/mcp_user/logs/aggregate/",
    ),
}
REQUEST_MODELS = {
    "mcp_get_log_field_metadata": GetLogFieldMetadataRequest,
    "mcp_search_logs": SearchLogsRequest,
    "mcp_aggregate_logs": AggregateLogsRequest,
}


class TestMCPUserLogAPIGWContract(SimpleTestCase):
    """网关只公开三个固定用户态工具，并与后端和 Schema 同步。"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.resources = yaml.safe_load(
            (BACKEND_ROOT / "support-files/apigw/resources.yaml").read_text(encoding="utf-8")
        )
        cls.json_schema = cls._to_json_schema(cls.resources)

    def test_log_resources_have_complete_user_apigw_contracts(self):
        for operation_id, (path, backend_path) in MCP_LOG_RESOURCES.items():
            with self.subTest(operation_id=operation_id):
                operation = self.resources["paths"][path]["post"]
                self.assertEqual(operation["operationId"], operation_id)
                self.assertEqual(
                    operation["parameters"][0],
                    {
                        "in": "path",
                        "name": "namespace",
                        "type": "string",
                        "required": True,
                        "description": "命名空间，仅由 URL path 提供，不能在请求体伪造。",
                    },
                )
                request_schema = next(item["schema"] for item in operation["parameters"] if item["in"] == "body")
                self.assertNotIn("namespace", request_schema["properties"])
                self.assertTrue(operation["responses"]["200"]["schema"]["properties"])
                config = operation["x-bk-apigateway-resource"]
                self.assertTrue(config["isPublic"])
                self.assertTrue(config["allowApplyPermission"])
                self.assertEqual(config["backend"]["method"], "post")
                self.assertEqual(config["backend"]["path"], backend_path)
                self.assertEqual(
                    config["authConfig"],
                    {
                        "appVerifiedRequired": True,
                        "userVerifiedRequired": True,
                        "resourcePermissionRequired": True,
                    },
                )

    def test_operation_ids_are_unique_across_the_resource_file(self):
        operation_ids = [
            operation["operationId"]
            for methods in self.resources["paths"].values()
            for operation in methods.values()
            if isinstance(operation, dict) and "operationId" in operation
        ]
        self.assertEqual(len(operation_ids), len(set(operation_ids)))

    def test_minimal_runtime_requests_validate_against_yaml(self):
        condition = {
            "scope_id": "bk_log",
            "start_time": "2026-08-13T00:00:00+08:00",
            "end_time": "2026-08-14T00:00:00+08:00",
        }
        requests = {
            "mcp_get_log_field_metadata": {"condition": condition},
            "mcp_search_logs": {"condition": condition},
            "mcp_aggregate_logs": {"condition": condition, "metrics": [{"id": "count", "type": "COUNT"}]},
        }
        for operation_id, payload in requests.items():
            with self.subTest(operation_id=operation_id):
                self._validate(self._body_schema(operation_id), payload)

    def test_model_dump_envelopes_validate_against_yaml(self):
        field_ref = LogFieldRef(raw_name="start_time")
        query_summary = QuerySummary(
            scope_type="system",
            scope_id="bk_log",
            time_range={"start_time": "2026-08-13T00:00:00+08:00", "end_time": "2026-08-14T00:00:00+08:00"},
            executed_at="2026-08-14T00:00:00+08:00",
        )
        responses = {
            "mcp_get_log_field_metadata": GetLogFieldMetadataResponse(
                fields=[LogFieldMetadataItem(field=field_ref, category="BASIC", type_source="DECLARED", options=None)],
                sample_summary=FieldSampleSummary(),
            ),
            "mcp_search_logs": SearchLogsResponse(
                total=0,
                columns=[LogDetailColumn(field=field_ref, key="start_time", options=None)],
                pagination=LogSearchPagination(page=1, page_size=20, total=0, returned_count=0, has_more=False),
                query_summary=query_summary,
            ),
            "mcp_aggregate_logs": AggregateLogsResponse(
                columns=[
                    AggregationColumn(
                        id="count", name="count", role="METRIC", data_type="BIGINT", effective_time_interval=None
                    )
                ],
                rows=(),
                query_summary=AggregationQuerySummary(
                    returned_count=0, has_more=False, took_ms=1, executed_at="2026-08-14T00:00:00+08:00"
                ),
            ),
        }
        for operation_id, response in responses.items():
            with self.subTest(operation_id=operation_id):
                self._validate(self._response_schema(operation_id), self._envelope(response.model_dump(mode="json")))

    def test_defaults_nullable_and_required_match_runtime_contract(self):
        search = self._body_schema("mcp_search_logs")
        self.assertIsNone(search["properties"]["fields"]["default"])
        self.assertIn("null", search["properties"]["fields"]["type"])
        self.assertEqual(search["properties"]["sort"]["default"], [])
        aggregate = self._body_schema("mcp_aggregate_logs")
        self.assertEqual(aggregate["properties"]["dimensions"]["default"], [])
        self.assertEqual(aggregate["properties"]["order_by"]["default"], [])
        for operation_id in MCP_LOG_RESOURCES:
            response = self._response_schema(operation_id)
            self.assertEqual(response["required"], ["result", "code", "message", "request_id", "trace_id", "data"])

    def test_request_required_defaults_and_nullable_match_pydantic_recursively(self):
        for operation_id, model in REQUEST_MODELS.items():
            with self.subTest(operation_id=operation_id):
                pydantic_schema = model.model_json_schema(mode="validation")
                self._assert_request_shape(
                    pydantic_schema,
                    self._raw_body_schema(operation_id),
                    pydantic_schema.get("$defs", {}),
                    operation_id,
                )

    def test_aggregate_schema_explains_agent_visible_dsl_semantics(self):
        properties = self._raw_body_schema("mcp_aggregate_logs")["properties"]
        condition = self._resolve_ref(properties["condition"], self.resources["definitions"])
        self.assertIn("当前用户重新鉴权", condition["description"])

        dimension = properties["dimensions"]["items"]["properties"]
        self.assertIn("字母开头", dimension["id"]["description"])
        self.assertIn("TIME_BUCKET", dimension["type"]["description"])
        self.assertIn("start_time", dimension["type"]["description"])
        self.assertIn("start_time", dimension["field"]["description"])
        self.assertIn("AUTO", dimension["interval"]["description"])

        metric = properties["metrics"]["items"]["properties"]
        self.assertIn("字母开头", metric["id"]["description"])
        self.assertIn("COUNT", metric["type"]["description"])
        self.assertIn("value_type", metric["type"]["description"])
        self.assertIn("COUNT", metric["field"]["description"])
        self.assertIn("LONG", metric["value_type"]["description"])
        self.assertIn("DOUBLE", metric["value_type"]["description"])
        self.assertIn("0 < percentile < 1", metric["percentile"]["description"])

        order_by = properties["order_by"]
        order = order_by["items"]["properties"]
        self.assertIn("已声明", order_by["description"])
        self.assertIn("已声明", order["target_id"]["description"])
        self.assertIn("ASC", order["direction"]["description"])
        self.assertIn("DESC", order["direction"]["description"])

    def test_parent_keys_unsafe_key_is_rejected_by_apigw_schema(self):
        payload = {
            "condition": {
                "scope_id": "bk_log",
                "start_time": "2026-08-13T00:00:00+08:00",
                "end_time": "2026-08-14T00:00:00+08:00",
            },
            "parent_keys": ["unsafe-key"],
        }
        schema = self._body_schema("mcp_get_log_field_metadata")
        validator = jsonschema.Draft4Validator(schema, resolver=jsonschema.RefResolver.from_schema(self.json_schema))
        self.assertTrue(list(validator.iter_errors(payload)))

    def test_shared_request_cost_limits_are_expressed_in_apigw_schema(self):
        condition = self.resources["definitions"]["log_tool_condition"]
        self.assertEqual(condition["properties"]["scope_id"]["maxLength"], 255)
        self.assertEqual(condition["properties"]["conditions"]["maxItems"], 100)
        item = condition["properties"]["conditions"]["items"]
        self.assertEqual(item["properties"]["filters"]["maxItems"], 1000)
        field = self.resources["definitions"]["log_tool_condition_field"]
        self.assertEqual(field["properties"]["keys"]["maxItems"], 16)
        self.assertEqual(field["properties"]["keys"]["items"]["maxLength"], 128)
        self.assertIn("1024 bytes", field["properties"]["keys"]["description"])
        self.assertIn("256 KiB", condition["description"])
        self.assertIn("16 KiB", item["properties"]["filters"]["description"])

        request = self._raw_body_schema("mcp_get_log_field_metadata")
        self.assertEqual(request["properties"]["parent_keys"]["maxItems"], 16)
        self.assertEqual(request["properties"]["parent_keys"]["items"]["maxLength"], 128)
        self.assertIn("1024 bytes", request["properties"]["parent_keys"]["description"])

    def test_response_capacity_and_expandable_semantics_are_documented(self):
        field_operation = self.resources["paths"][MCP_LOG_RESOURCES["mcp_get_log_field_metadata"][0]]["post"]
        field_response = field_operation["responses"]["200"]["schema"]["properties"]["data"]
        self.assertEqual(field_response["properties"]["fields"]["maxItems"], 100)
        field_item = field_response["properties"]["fields"]["items"]
        self.assertEqual(field_item["properties"]["sample_values"]["maxItems"], 3)
        self.assertIn(
            "extend_data 根字段及其对象子字段",
            field_item["properties"]["is_expandable"]["description"],
        )
        self.assertIn("1 MiB", field_operation["description"])

        aggregate_operation = self.resources["paths"][MCP_LOG_RESOURCES["mcp_aggregate_logs"][0]]["post"]
        aggregate_response = aggregate_operation["responses"]["200"]["schema"]["properties"]["data"]
        self.assertEqual(aggregate_response["properties"]["rows"]["maxItems"], 100)
        self.assertIn("1 MiB", aggregate_operation["description"])

    @override_settings(ROOT_URLCONF="urls")
    def test_response_field_ref_limits_match_dynamic_openapi(self):
        request = APIRequestFactory().get("/api/schema/")
        request.user = mock.Mock(is_staff=True, is_authenticated=True)
        response = SpectacularAPIView.as_view()(request)
        response.render()
        openapi = yaml.safe_load(response.content)
        operation = openapi["paths"][MCP_LOG_RESOURCES["mcp_get_log_field_metadata"][1]]["post"]
        envelope = operation["responses"]["200"]["content"]["application/json"]["schema"]
        dynamic_keys = envelope["properties"]["data"]["properties"]["fields"]["items"]["properties"]["field"][
            "properties"
        ]["keys"]
        static_keys = self.resources["definitions"]["log_tool_field_ref_response"]["properties"]["keys"]

        for keyword in ("maxItems", "description"):
            self.assertEqual(static_keys.get(keyword), dynamic_keys[keyword])
        for keyword in ("maxLength", "pattern"):
            self.assertEqual(static_keys["items"].get(keyword), dynamic_keys["items"][keyword])

    def test_aggregate_descriptions_match_pydantic_and_explain_runtime_combinations(self):
        properties = self._raw_body_schema("mcp_aggregate_logs")["properties"]
        dimension = properties["dimensions"]["items"]["properties"]
        metric = properties["metrics"]["items"]["properties"]
        pydantic_schema = AggregateLogsRequest.model_json_schema(mode="validation")
        pydantic_dimension = pydantic_schema["$defs"]["AggregationDimension"]["properties"]
        pydantic_metric = pydantic_schema["$defs"]["AggregationMetric"]["properties"]

        for name in ("type", "field", "interval"):
            self.assertEqual(dimension[name]["description"], pydantic_dimension[name]["description"])
        for name in ("type", "field", "value_type", "percentile"):
            self.assertEqual(metric[name]["description"], pydantic_metric[name]["description"])

        allowed_fields = (
            "action_id",
            "resource_type_id",
            "username",
            "result_code",
            "access_type",
            "start_time",
            "extend_data",
        )
        for description in (dimension["field"]["description"], metric["field"]["description"]):
            for field_name in allowed_fields:
                self.assertIn(field_name, description)
            self.assertIn("keys", description)

        self.assertIn("FIELD 必须省略", dimension["interval"]["description"])
        self.assertIn("TIME_BUCKET 必填", dimension["interval"]["description"])
        metric_type_description = metric["type"]["description"]
        for metric_type in ("COUNT", "DISTINCT_COUNT", "MIN", "MAX", "AVG", "SUM", "PERCENTILE_APPROX"):
            self.assertIn(metric_type, metric_type_description)
        self.assertIn("field/value_type/percentile", metric_type_description)
        self.assertIn("0 < percentile < 1", metric_type_description)

    def test_aggregate_model_dump_with_explicit_nulls_validates_against_yaml(self):
        request = AggregateLogsRequest.model_validate(
            {
                "condition": {
                    "scope_id": "bk_log",
                    "start_time": "2026-08-13T00:00:00+08:00",
                    "end_time": "2026-08-14T00:00:00+08:00",
                },
                "metrics": [{"id": "count", "type": "COUNT"}],
            }
        )
        payload = request.model_dump(mode="json")
        self.assertEqual(
            {key: payload["metrics"][0][key] for key in ("field", "value_type", "percentile")},
            {"field": None, "value_type": None, "percentile": None},
        )
        AggregateLogsRequest.model_validate(payload)
        self._validate(self._body_schema("mcp_aggregate_logs"), payload)

    def _body_schema(self, operation_id):
        operation = self.json_schema["paths"][MCP_LOG_RESOURCES[operation_id][0]]["post"]
        return next(parameter["schema"] for parameter in operation["parameters"] if parameter["in"] == "body")

    def _raw_body_schema(self, operation_id):
        operation = self.resources["paths"][MCP_LOG_RESOURCES[operation_id][0]]["post"]
        return next(parameter["schema"] for parameter in operation["parameters"] if parameter["in"] == "body")

    def _response_schema(self, operation_id):
        return self.json_schema["paths"][MCP_LOG_RESOURCES[operation_id][0]]["post"]["responses"]["200"]["schema"]

    def _validate(self, schema, instance):
        validator = jsonschema.Draft4Validator(schema, resolver=jsonschema.RefResolver.from_schema(self.json_schema))
        errors = sorted(validator.iter_errors(instance), key=lambda error: list(error.path))
        self.assertEqual(errors, [], "\n".join(error.message for error in errors))

    def _assert_request_shape(self, pydantic_schema, yaml_schema, pydantic_definitions, path):
        pydantic_schema = self._resolve_ref(pydantic_schema, pydantic_definitions)
        yaml_schema = self._resolve_ref(yaml_schema, self.resources["definitions"])

        any_of = pydantic_schema.get("anyOf", [])
        non_null = [item for item in any_of if item.get("type") != "null"]
        pydantic_nullable = bool(any_of) and len(non_null) == 1 and len(non_null) != len(any_of)
        if pydantic_nullable:
            siblings = {key: value for key, value in pydantic_schema.items() if key != "anyOf"}
            pydantic_schema = self._resolve_ref(non_null[0], pydantic_definitions)
            pydantic_schema.update(siblings)

        self.assertEqual(pydantic_nullable, bool(yaml_schema.get("x-nullable")), path)
        if "default" in pydantic_schema:
            self.assertIn("default", yaml_schema, path)
            self.assertEqual(pydantic_schema["default"], yaml_schema["default"], path)

        for keyword in ("minLength", "maxLength", "minItems", "maxItems", "pattern"):
            if keyword in pydantic_schema:
                self.assertEqual(pydantic_schema[keyword], yaml_schema.get(keyword), path)

        pydantic_properties = pydantic_schema.get("properties", {})
        yaml_properties = yaml_schema.get("properties", {})
        if pydantic_properties:
            self.assertEqual(set(pydantic_properties), set(yaml_properties), path)
            self.assertEqual(set(pydantic_schema.get("required", [])), set(yaml_schema.get("required", [])), path)
            for name, child_schema in pydantic_properties.items():
                self._assert_request_shape(
                    child_schema,
                    yaml_properties[name],
                    pydantic_definitions,
                    f"{path}.{name}",
                )

        if "items" in pydantic_schema:
            self._assert_request_shape(
                pydantic_schema["items"], yaml_schema["items"], pydantic_definitions, f"{path}[]"
            )

    @staticmethod
    def _resolve_ref(schema, definitions):
        schema = deepcopy(schema)
        if len(schema.get("allOf", [])) == 1 and "$ref" in schema["allOf"][0]:
            resolved = TestMCPUserLogAPIGWContract._resolve_ref(schema.pop("allOf")[0], definitions)
            resolved.update(schema)
            return resolved
        if "$ref" not in schema:
            return schema
        resolved = deepcopy(definitions[schema.pop("$ref").rsplit("/", 1)[-1]])
        resolved.update(schema)
        return resolved

    @staticmethod
    def _envelope(data):
        return {
            "result": True,
            "code": 0,
            "message": None,
            "request_id": "request-id",
            "trace_id": "trace-id",
            "data": data,
        }

    @classmethod
    def _to_json_schema(cls, value):
        if isinstance(value, list):
            return [cls._to_json_schema(item) for item in value]
        if not isinstance(value, dict):
            return value
        result = {key: cls._to_json_schema(item) for key, item in deepcopy(value).items() if key != "x-nullable"}
        if value.get("x-nullable") and isinstance(result.get("type"), str):
            result["type"] = [result["type"], "null"]
        if value.get("x-nullable") and isinstance(result.get("enum"), list):
            result["enum"] = [*result["enum"], None]
        return result

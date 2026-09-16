# -*- coding: utf-8 -*-
"""用户态日志 MCP OpenAPI 契约。"""

from copy import deepcopy
from unittest import mock

import jsonschema
import yaml
from django.test import SimpleTestCase, override_settings
from drf_spectacular.views import SpectacularAPIView
from pydantic import ValidationError as PydanticValidationError
from rest_framework.test import APIRequestFactory

from services.web.query.ai_assistant.exceptions import (
    InvalidLogCondition,
    LogQueryFailed,
    LogQueryResponseTooLarge,
    LogQueryTimeout,
    SensitiveFieldPermissionDenied,
    StatisticsBudgetExceeded,
    StatisticsResponseTooLarge,
    UnsupportedAggregation,
    UnsupportedFieldType,
    UnsupportedLogField,
)
from services.web.query.ai_assistant.log_tools.schemas import (
    AggregateLogsRequest,
    AggregationGroupValue,
)

LOG_TOOL_ERROR_TYPES = (
    InvalidLogCondition,
    UnsupportedLogField,
    UnsupportedAggregation,
    SensitiveFieldPermissionDenied,
    LogQueryTimeout,
    LogQueryFailed,
    LogQueryResponseTooLarge,
    UnsupportedFieldType,
    StatisticsBudgetExceeded,
    StatisticsResponseTooLarge,
)


@override_settings(ROOT_URLCONF="urls")
class TestMCPUserLogOpenAPI(SimpleTestCase):
    """OpenAPI 必须反映路径 namespace、Pydantic 限制和真实 JSON 响应。"""

    def setUp(self):
        self.request = APIRequestFactory().get("/api/schema/")
        self.request.user = mock.Mock(is_staff=True, is_authenticated=True)
        response = SpectacularAPIView.as_view()(self.request)
        response.render()
        self.schema = yaml.safe_load(response.content)

    def test_three_post_operations_have_stable_unique_operation_ids(self):
        expected = {
            "/api/v1/query/namespaces/{namespace}/mcp_user/logs/field_metadata/": "mcp_get_log_field_metadata",
            "/api/v1/query/namespaces/{namespace}/mcp_user/logs/search/": "mcp_search_logs",
            "/api/v1/query/namespaces/{namespace}/mcp_user/logs/aggregate/": "mcp_aggregate_logs",
        }
        operation_ids = []
        for path, operation_id in expected.items():
            with self.subTest(path=path):
                operation = self.schema["paths"][path]["post"]
                self.assertEqual(operation["operationId"], operation_id)
                self.assertIn("200", operation["responses"])
                self.assertIn("requestBody", operation)
                parameters = {(item["in"], item["name"]) for item in operation["parameters"]}
                self.assertIn(("path", "namespace"), parameters)
                request_schema = operation["requestBody"]["content"]["application/json"]["schema"]
                self.assertNotIn("namespace", request_schema.get("properties", {}))
            operation_ids.append(operation_id)

        all_operation_ids = [
            operation["operationId"]
            for methods in self.schema["paths"].values()
            for operation in methods.values()
            if isinstance(operation, dict) and "operationId" in operation
        ]
        self.assertEqual(len(all_operation_ids), len(set(all_operation_ids)))

    def test_aggregate_request_documents_frozen_cost_and_enum_boundaries(self):
        operation = self.schema["paths"]["/api/v1/query/namespaces/{namespace}/mcp_user/logs/aggregate/"]["post"]
        component = operation["requestBody"]["content"]["application/json"]["schema"]

        self.assertEqual(component["properties"]["dimensions"]["maxItems"], 2)
        self.assertEqual(component["properties"]["metrics"]["maxItems"], 5)
        self.assertEqual(component["properties"]["top_n"]["maximum"], 500)
        self.assertIn("COUNT", self._enum(component, "metrics", "type"))
        self.assertIn("PERCENTILE_APPROX", self._enum(component, "metrics", "type"))
        self.assertEqual(self._enum(component, "dimensions", "type"), {"FIELD", "TIME_BUCKET"})

    def test_openapi_preserves_nested_pydantic_constraints_and_standard_response_envelope(self):
        search = self.schema["paths"]["/api/v1/query/namespaces/{namespace}/mcp_user/logs/search/"]["post"]
        search_request = self._component(search["requestBody"]["content"]["application/json"]["schema"])
        fields = search_request["properties"]["fields"]
        self.assertEqual(fields["minItems"], 1)
        self.assertEqual(fields["maxItems"], 20)
        self.assertEqual(search_request["properties"]["sort"]["maxItems"], 3)
        self.assertNotIn("maximum", search_request["properties"]["page"])

        aggregate = self.schema["paths"]["/api/v1/query/namespaces/{namespace}/mcp_user/logs/aggregate/"]["post"]
        aggregate_request = self._component(aggregate["requestBody"]["content"]["application/json"]["schema"])
        metric = self._component(aggregate_request["properties"]["metrics"]["items"])
        self.assertEqual(metric["properties"]["id"]["pattern"], "^[A-Za-z][A-Za-z0-9_]{0,63}$")
        self.assertEqual(metric["properties"]["percentile"]["minimum"], 0)
        self.assertIs(metric["properties"]["percentile"]["exclusiveMinimum"], True)
        self.assertEqual(metric["properties"]["percentile"]["maximum"], 1)
        self.assertIs(metric["properties"]["percentile"]["exclusiveMaximum"], True)
        self.assertIn("COUNT", metric["properties"]["type"]["enum"])
        self.assertIn("必须", metric["properties"]["field"]["description"])

        field_metadata = self.schema["paths"]["/api/v1/query/namespaces/{namespace}/mcp_user/logs/field_metadata/"][
            "post"
        ]
        response = field_metadata["responses"]["200"]["content"]["application/json"]["schema"]
        envelope = self._component(response)
        self.assertEqual(set(envelope["required"]), {"result", "code", "message", "request_id", "trace_id", "data"})
        payload = self._component(envelope["properties"]["data"])
        self.assertEqual(set(payload["required"]), {"fields", "sample_summary"})
        truncated_description = payload["properties"]["sample_summary"]["properties"]["truncated"]["description"]
        self.assertIn("协议无法表达", truncated_description)
        self.assertIn("业务 data 载荷超限返回 413", truncated_description)

    def test_openapi_documents_standard_error_envelope(self):
        paths = (
            "/api/v1/query/namespaces/{namespace}/mcp_user/logs/field_metadata/",
            "/api/v1/query/namespaces/{namespace}/mcp_user/logs/search/",
            "/api/v1/query/namespaces/{namespace}/mcp_user/logs/aggregate/",
        )
        for path in paths:
            with self.subTest(path=path):
                responses = self.schema["paths"][path]["post"]["responses"]
                self.assertTrue({"400", "403", "413", "502", "504"}.issubset(responses))
                for status_code in ("400", "403", "413", "502", "504"):
                    envelope = responses[status_code]["content"]["application/json"]["schema"]
                    self.assertEqual(
                        set(envelope["required"]),
                        {"result", "code", "message", "request_id", "trace_id", "data"},
                    )
                    self.assertIn("errors", envelope["properties"])
                    code_description = envelope["properties"]["code"]["description"]
                    for error_type in LOG_TOOL_ERROR_TYPES:
                        error = error_type()
                        self.assertIn(f"{error.code} {error_type.MESSAGE}", code_description)

    def test_parent_field_openapi_allows_business_key_and_rejects_empty_key(self):
        operation = self.schema["paths"]["/api/v1/query/namespaces/{namespace}/mcp_user/logs/field_metadata/"]["post"]
        schema = operation["requestBody"]["content"]["application/json"]["schema"]
        parent_field = schema["properties"]["parent_field"]
        parent_key = parent_field["properties"]["keys"]["items"]
        self.assertEqual(parent_key["minLength"], 1)
        self.assertEqual(parent_key["maxLength"], 128)
        self.assertEqual(parent_key["pattern"], "^[^.]+$")

        payload = {
            "condition": {
                "scope_id": "bk_log",
                "start_time": "2026-08-13T00:00:00+08:00",
                "end_time": "2026-08-14T00:00:00+08:00",
            },
            "parent_field": {"raw_name": "extend_data", "keys": ["业务-字段"]},
        }
        errors = list(jsonschema.Draft7Validator(self._openapi_json_schema(schema)).iter_errors(payload))
        self.assertEqual(errors, [])

        payload["parent_field"]["keys"] = [""]
        errors = list(jsonschema.Draft7Validator(self._openapi_json_schema(schema)).iter_errors(payload))
        self.assertTrue(errors)

        payload["parent_field"]["keys"] = ["literal.dot"]
        errors = list(jsonschema.Draft7Validator(self._openapi_json_schema(schema)).iter_errors(payload))
        self.assertTrue(errors)

    def test_shared_condition_and_field_path_cost_limits_are_documented(self):
        operation = self.schema["paths"]["/api/v1/query/namespaces/{namespace}/mcp_user/logs/field_metadata/"]["post"]
        request = operation["requestBody"]["content"]["application/json"]["schema"]
        condition = self._component(request["properties"]["condition"])
        self.assertEqual(condition["properties"]["scope_id"]["maxLength"], 255)
        self.assertEqual(condition["properties"]["conditions"]["maxItems"], 100)
        condition_item = self._component(condition["properties"]["conditions"]["items"])
        self.assertEqual(condition_item["properties"]["filters"]["maxItems"], 1000)
        condition_field = self._component(condition_item["properties"]["field"])
        self.assertEqual(condition_field["properties"]["keys"]["maxItems"], 16)
        self.assertEqual(condition_field["properties"]["keys"]["items"]["maxLength"], 128)
        self.assertIn("1024 bytes", condition_field["properties"]["keys"]["description"])
        self.assertIn("256 KiB", condition["description"])
        filters = condition_item["properties"]["filters"]
        self.assertIn("16 KiB", filters["description"])
        self.assertEqual(
            {item["type"] for item in filters["items"]["anyOf"]},
            {"string", "integer", "number"},
        )

        payload = {
            "condition": {
                "scope_id": "bk_log",
                "start_time": "2026-08-13T00:00:00+08:00",
                "end_time": "2026-08-14T00:00:00+08:00",
                "conditions": [
                    {
                        "field": {"raw_name": "result_code"},
                        "operator": "eq",
                        "filters": [1],
                    }
                ],
            }
        }
        validator = jsonschema.Draft7Validator(self._openapi_json_schema(request))
        self.assertEqual(list(validator.iter_errors(payload)), [])
        payload["condition"]["conditions"][0]["filters"] = [{"invalid": "object"}]
        self.assertTrue(list(validator.iter_errors(payload)))

        parent_keys = request["properties"]["parent_field"]["properties"]["keys"]
        self.assertEqual(parent_keys["maxItems"], 16)
        self.assertEqual(parent_keys["items"]["maxLength"], 128)
        self.assertIn("1024 bytes", parent_keys["description"])

    def test_response_capacity_and_expandable_semantics_are_documented(self):
        field_operation = self.schema["paths"]["/api/v1/query/namespaces/{namespace}/mcp_user/logs/field_metadata/"][
            "post"
        ]
        field_response = self._response_payload(field_operation)
        self.assertEqual(field_response["properties"]["fields"]["maxItems"], 100)
        field_item = self._component(field_response["properties"]["fields"]["items"])
        self.assertEqual(field_item["properties"]["sample_values"]["maxItems"], 3)
        self.assertIn(
            "可见 JSON 根字段及其对象子字段",
            field_item["properties"]["is_expandable"]["description"],
        )
        self.assertIn("1 MiB", field_operation["description"])

        aggregate_operation = self.schema["paths"]["/api/v1/query/namespaces/{namespace}/mcp_user/logs/aggregate/"][
            "post"
        ]
        aggregate_response = self._response_payload(aggregate_operation)
        self.assertNotIn("maxItems", aggregate_response["properties"]["rows"])
        self.assertIn("4 MiB", aggregate_operation["description"])

    def test_aggregate_descriptions_explain_all_runtime_combinations(self):
        operation = self.schema["paths"]["/api/v1/query/namespaces/{namespace}/mcp_user/logs/aggregate/"]["post"]
        properties = operation["requestBody"]["content"]["application/json"]["schema"]["properties"]
        dimension = properties["dimensions"]["items"]["properties"]
        metric = properties["metrics"]["items"]["properties"]

        for description in (dimension["field"]["description"], metric["field"]["description"]):
            self.assertIn("日志检索可见", description)
            self.assertIn("keys", description)

        self.assertIn("FIELD", dimension["type"]["description"])
        self.assertIn("不得传 interval", dimension["type"]["description"])
        self.assertIn("TIME_BUCKET", dimension["type"]["description"])
        self.assertIn("默认 AUTO", dimension["type"]["description"])
        self.assertIn("FIELD 必须省略", dimension["interval"]["description"])
        self.assertIn("AUTO", dimension["interval"]["description"])

        metric_type_description = metric["type"]["description"]
        for metric_type in ("COUNT", "DISTINCT_COUNT", "MIN", "MAX", "AVG", "SUM", "PERCENTILE_APPROX"):
            self.assertIn(metric_type, metric_type_description)
        self.assertIn("field/value_type/percentile", metric_type_description)
        self.assertIn("0 < percentile < 1", metric_type_description)
        self.assertIn("COUNT/DISTINCT_COUNT 必须省略", metric["value_type"]["description"])
        self.assertIn("标准数值字段必须省略", metric["value_type"]["description"])
        self.assertIn("其余指标必须省略", metric["percentile"]["description"])

    def test_three_operations_only_use_openapi_30_numeric_exclusive_keywords(self):
        self.assertEqual(self.schema["openapi"], "3.0.3")
        paths = (
            "/api/v1/query/namespaces/{namespace}/mcp_user/logs/field_metadata/",
            "/api/v1/query/namespaces/{namespace}/mcp_user/logs/search/",
            "/api/v1/query/namespaces/{namespace}/mcp_user/logs/aggregate/",
        )
        for path in paths:
            with self.subTest(path=path):
                operation = self.schema["paths"][path]["post"]
                self._assert_oas_30_schema(operation["requestBody"]["content"]["application/json"]["schema"])
                self._assert_oas_30_schema(operation["responses"]["200"]["content"]["application/json"]["schema"])

    def test_ref_expansion_preserves_field_level_descriptions(self):
        field_metadata = self.schema["paths"]["/api/v1/query/namespaces/{namespace}/mcp_user/logs/field_metadata/"][
            "post"
        ]
        condition = field_metadata["requestBody"]["content"]["application/json"]["schema"]["properties"]["condition"]
        self.assertIn("当前用户重新鉴权", condition["description"])

        aggregate = self.schema["paths"]["/api/v1/query/namespaces/{namespace}/mcp_user/logs/aggregate/"]["post"]
        dimension_field = aggregate["requestBody"]["content"]["application/json"]["schema"]["properties"]["dimensions"][
            "items"
        ]["properties"]["field"]
        self.assertIn("TIME_BUCKET 只能使用无 keys 的 start_time", dimension_field["description"])

    def test_aggregate_model_dump_with_explicit_nulls_validates_against_openapi(self):
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
        operation = self.schema["paths"]["/api/v1/query/namespaces/{namespace}/mcp_user/logs/aggregate/"]["post"]
        schema = self._openapi_json_schema(operation["requestBody"]["content"]["application/json"]["schema"])
        errors = list(jsonschema.Draft7Validator(schema).iter_errors(payload))
        self.assertEqual(errors, [], "\n".join(error.message for error in errors))

    def test_response_enums_are_narrow_and_required_fields_match_model_dump(self):
        field_metadata = self.schema["paths"]["/api/v1/query/namespaces/{namespace}/mcp_user/logs/field_metadata/"][
            "post"
        ]
        field_payload = self._response_payload(field_metadata)
        item = self._component(field_payload["properties"]["fields"]["items"])
        self.assertEqual(self._resolve_enum(item["properties"]["category"]), {"BASIC", "EXTENDED"})

        aggregate = self.schema["paths"]["/api/v1/query/namespaces/{namespace}/mcp_user/logs/aggregate/"]["post"]
        aggregate_payload = self._response_payload(aggregate)
        column = self._component(aggregate_payload["properties"]["columns"]["items"])
        self.assertEqual(self._resolve_enum(column["properties"]["effective_time_interval"]), {"MINUTE", "HOUR", "DAY"})
        self.assertTrue({"boolean", "number", "scalar"}.issubset(self._resolve_enum(column["properties"]["data_type"])))
        self.assertEqual(
            set(aggregate_payload["required"]), {"columns", "rows", "groups", "query_summary", "data_quality"}
        )

    def test_aggregate_groups_schema_preserves_scalar_values_and_complete_summary(self):
        """公开 schema 不能允许 DTO 会拒绝的容器、缺失值或旧分页摘要。"""
        operation = self.schema["paths"]["/api/v1/query/namespaces/{namespace}/mcp_user/logs/aggregate/"]["post"]
        payload = self._response_payload(operation)
        group = self._component(payload["properties"]["groups"]["items"])
        self.assertEqual(self._resolve_enum(group["properties"]["kind"]), {"VALUE", "OTHER", "MISSING", "ALL"})
        typed_value = self._component(group["properties"]["values"]["items"])
        self.assertEqual(
            self._resolve_enum(typed_value["properties"]["value_type"]), {"boolean", "integer", "number", "string"}
        )
        validator = jsonschema.Draft7Validator(self._openapi_json_schema(typed_value))
        for value_type, value in (("boolean", True), ("integer", 1), ("number", 1.5), ("string", "")):
            self.assertEqual(
                list(validator.iter_errors({"dimension_id": "category", "value_type": value_type, "value": value})), []
            )
        for value in (None, [], {}):
            self.assertTrue(
                list(validator.iter_errors({"dimension_id": "category", "value_type": "string", "value": value}))
            )
        summary = self._component(payload["properties"]["query_summary"])
        self.assertEqual(
            set(summary["required"]),
            {
                "returned_count",
                "total_count",
                "top_n",
                "has_other",
                "scope_id",
                "start_time",
                "end_time",
                "requested_interval",
                "effective_interval",
                "timezone",
                "complete",
                "took_ms",
                "executed_at",
            },
        )
        quality = self._component(payload["properties"]["data_quality"]["items"])
        self.assertEqual(
            set(quality["required"]), {"metric_id", "present_count", "converted_count", "conversion_failed_count"}
        )

    def test_optional_request_fields_reject_null_in_public_schema_and_runtime(self):
        """请求可省略参数不可声明 nullable；响应实际粒度和无类别 top_n 仍允许 null。"""
        operation = self.schema["paths"]["/api/v1/query/namespaces/{namespace}/mcp_user/logs/aggregate/"]["post"]
        request_schema = self._openapi_json_schema(operation["requestBody"]["content"]["application/json"]["schema"])
        validator = jsonschema.Draft7Validator(request_schema)
        condition = {
            "scope_id": "bk_log",
            "start_time": "2026-08-13T00:00:00+08:00",
            "end_time": "2026-08-14T00:00:00+08:00",
        }
        for dimension in (
            {"id": "actor", "type": "FIELD", "field": {"raw_name": "username"}},
            {"id": "time", "type": "TIME_BUCKET", "field": {"raw_name": "start_time"}},
        ):
            payload = {
                "condition": condition,
                "dimensions": [dimension],
                "metrics": [{"id": "events", "type": "COUNT"}],
            }
            self.assertEqual(list(validator.iter_errors(payload)), [])
            request = AggregateLogsRequest.model_validate(payload)
            self.assertEqual(AggregateLogsRequest.model_validate(request.model_dump()), request)
            for invalid in ({**payload, "top_n": None}, {**payload, "dimensions": [{**dimension, "interval": None}]}):
                with self.subTest(invalid=invalid):
                    with self.assertRaises(PydanticValidationError):
                        AggregateLogsRequest.model_validate(invalid)
                    self.assertTrue(list(validator.iter_errors(invalid)))
        summary = self._response_payload(operation)["properties"]["query_summary"]["properties"]
        for field in ("top_n", "requested_interval", "effective_interval"):
            self.assertEqual(
                list(jsonschema.Draft7Validator(self._openapi_json_schema(summary[field])).iter_errors(None)), []
            )

    def test_typed_group_public_schema_and_runtime_agree_on_type_pairs(self):
        """typed value 的公开契约必须将 discriminator 与真实标量类型配对。"""
        operation = self.schema["paths"]["/api/v1/query/namespaces/{namespace}/mcp_user/logs/aggregate/"]["post"]
        group = self._response_payload(operation)["properties"]["groups"]["items"]
        typed_value = group["properties"]["values"]["items"]
        validator = jsonschema.Draft7Validator(self._openapi_json_schema(typed_value))
        valid_pairs = (
            ("boolean", True),
            ("boolean", False),
            ("integer", 1),
            ("number", 1),
            ("number", 1.5),
            ("string", ""),
            ("string", "true"),
        )
        invalid_pairs = (
            ("string", 1),
            ("boolean", "true"),
            ("integer", True),
            ("number", False),
            ("integer", 1.5),
            ("string", None),
            ("string", []),
            ("string", {}),
        )
        for value_type, value in valid_pairs:
            payload = {"dimension_id": "category", "value_type": value_type, "value": value}
            with self.subTest(payload=payload):
                self.assertEqual(AggregationGroupValue.model_validate(payload).model_dump(mode="json"), payload)
                self.assertEqual(list(validator.iter_errors(payload)), [])
        for value_type, value in invalid_pairs:
            payload = {"dimension_id": "category", "value_type": value_type, "value": value}
            with self.subTest(payload=payload):
                with self.assertRaises(PydanticValidationError):
                    AggregationGroupValue.model_validate(payload)
                self.assertTrue(list(validator.iter_errors(payload)))

    def test_descriptions_explain_sampling_pagination_and_auto_conversion_boundaries(self):
        operations = self.schema["paths"]
        self.assertIn(
            "采样",
            operations["/api/v1/query/namespaces/{namespace}/mcp_user/logs/field_metadata/"]["post"]["description"],
        )
        self.assertIn(
            "分页", operations["/api/v1/query/namespaces/{namespace}/mcp_user/logs/search/"]["post"]["description"]
        )
        self.assertIn(
            "AUTO", operations["/api/v1/query/namespaces/{namespace}/mcp_user/logs/aggregate/"]["post"]["description"]
        )

    def _enum(self, component, list_field, nested_field):
        nested = self._component(component["properties"][list_field]["items"])
        field_schema = nested["properties"][nested_field]
        if "$ref" in field_schema:
            field_schema = self.schema["components"]["schemas"][field_schema["$ref"].rsplit("/", 1)[-1]]
        return set(field_schema["enum"])

    def _component(self, schema):
        if "$ref" not in schema:
            return schema
        return self.schema["components"]["schemas"][schema["$ref"].rsplit("/", 1)[-1]]

    def _resolve_enum(self, schema):
        return set(self._component(schema)["enum"] if "$ref" in schema else schema["enum"])

    def _response_payload(self, operation):
        envelope = self._component(operation["responses"]["200"]["content"]["application/json"]["schema"])
        return self._component(envelope["properties"]["data"])

    def _assert_oas_30_schema(self, schema):
        if isinstance(schema, list):
            for item in schema:
                self._assert_oas_30_schema(item)
            return
        if not isinstance(schema, dict):
            return
        for keyword, boundary in (("exclusiveMinimum", "minimum"), ("exclusiveMaximum", "maximum")):
            if keyword in schema:
                self.assertIsInstance(schema[keyword], bool, schema)
                if schema[keyword]:
                    self.assertIn(boundary, schema)
        for value in schema.values():
            self._assert_oas_30_schema(value)

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
        if result.get("exclusiveMinimum") is True:
            result["exclusiveMinimum"] = result.pop("minimum")
        elif result.get("exclusiveMinimum") is False:
            result.pop("exclusiveMinimum")
        if result.get("exclusiveMaximum") is True:
            result["exclusiveMaximum"] = result.pop("maximum")
        elif result.get("exclusiveMaximum") is False:
            result.pop("exclusiveMaximum")
        return result

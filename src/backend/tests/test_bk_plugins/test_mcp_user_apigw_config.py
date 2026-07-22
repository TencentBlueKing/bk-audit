# -*- coding: utf-8 -*-
import re
from pathlib import Path

import yaml
from django.test import SimpleTestCase

BACKEND_DIR = Path(__file__).resolve().parents[2]
EXPECTED_MCP_RESOURCES = {
    "mcp_retrieve_risk": ("/mcp/risks/{risk_id}/", "get", "/api/v1/mcp_user/risk/{risk_id}/"),
    "mcp_retrieve_risk_strategy_info": (
        "/mcp/risks/{risk_id}/strategy_info/",
        "get",
        "/api/v1/mcp_user/risk/{risk_id}/strategy_info/",
    ),
    "mcp_list_risk_event": ("/mcp/risks/events/", "get", "/api/v1/mcp_user/event/"),
    "mcp_list_analyse_report_risk": (
        "/mcp/analyse_reports/{report_id}/risks/",
        "post",
        "/api/v1/mcp_user/analyse_report/{report_id}/risks/",
    ),
    "mcp_execute_tool": (
        "/mcp/{namespace}/tools/{uid}/execute/",
        "post",
        "/api/v1/namespaces/{namespace}/mcp_user/tool/{uid}/execute/",
    ),
    "mcp_get_tool_detail_by_name": (
        "/mcp/{namespace}/tools/detail_by_name/",
        "get",
        "/api/v1/namespaces/{namespace}/mcp_user/tool/detail_by_name/",
    ),
}

MCP_SCHEMA_SOURCES = {
    "mcp_retrieve_risk": "retrieve_risk",
    "mcp_retrieve_risk_strategy_info": "retrieve_risk_strategy_info",
    "mcp_list_risk_event": "list_risk_event_apigw",
    "mcp_list_analyse_report_risk": "list_analyse_report_risk_apigw",
    "mcp_execute_tool": "execute_tool",
    "mcp_get_tool_detail_by_name": "get_tool_detail_by_name",
}

MCP_PATH_PARAMETER_ALIASES = {
    "mcp_retrieve_risk": {"id": "risk_id"},
    "mcp_retrieve_risk_strategy_info": {"id": "risk_id"},
}


class TestMCPUserAPIGWConfig(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.resources = yaml.safe_load((BACKEND_DIR / "support-files/apigw/resources.yaml").read_text(encoding="utf-8"))

    def test_all_mcp_resources_require_app_user_and_resource_permission(self):
        for operation_id, (path, method, backend_path) in EXPECTED_MCP_RESOURCES.items():
            operation = self.resources["paths"][path][method]

            self.assertEqual(operation["operationId"], operation_id)
            config = operation["x-bk-apigateway-resource"]
            self.assertFalse(config["isPublic"])
            self.assertEqual(config["backend"]["path"], backend_path)
            self.assertTrue(config["authConfig"]["appVerifiedRequired"])
            self.assertTrue(config["authConfig"]["userVerifiedRequired"])
            self.assertTrue(config["authConfig"]["resourcePermissionRequired"])

    def test_operation_ids_are_unique(self):
        operation_ids = [
            operation["operationId"]
            for methods in self.resources["paths"].values()
            for operation in methods.values()
            if isinstance(operation, dict) and "operationId" in operation
        ]

        self.assertEqual(len(operation_ids), len(set(operation_ids)))

    def test_mcp_schema_keeps_legacy_resource_contract(self):
        """用户态 MCP 仅变更鉴权和路由，不得缩减既有 Agent 可见契约。"""
        operations = self._get_operations()

        for mcp_operation_id, legacy_operation_id in MCP_SCHEMA_SOURCES.items():
            legacy_operation = operations[legacy_operation_id]
            mcp_operation = operations[mcp_operation_id]

            self.assertEqual(mcp_operation["responses"], legacy_operation["responses"])

            legacy_parameters = {
                (parameter["in"], parameter["name"]): parameter for parameter in legacy_operation["parameters"]
            }
            mcp_parameters = {
                (parameter["in"], parameter["name"]): parameter for parameter in mcp_operation["parameters"]
            }
            for parameter_key, legacy_parameter in legacy_parameters.items():
                parameter_key = (
                    parameter_key[0],
                    MCP_PATH_PARAMETER_ALIASES.get(mcp_operation_id, {}).get(parameter_key[1], parameter_key[1]),
                )
                if parameter_key[1] != legacy_parameter["name"]:
                    legacy_parameter = {**legacy_parameter, "name": parameter_key[1]}
                self.assertEqual(mcp_parameters[parameter_key], legacy_parameter)

        detail_parameters = {
            (parameter["in"], parameter["name"]): parameter
            for parameter in operations["mcp_get_tool_detail_by_name"]["parameters"]
        }
        self.assertIn(("path", "namespace"), detail_parameters)
        self.assertIn(("query", "lite_mode"), detail_parameters)

    def test_all_audit_report_servers_use_new_mcp_resources(self):
        definition = self._load_definition()

        for stage in definition["stages"]:
            server = next(server for server in stage["mcp_servers"] if server["name"] == "audit-report")
            self.assertEqual(set(server["resource_names"]), set(EXPECTED_MCP_RESOURCES))

    def test_resource_change_advances_release_version(self):
        definition = self._load_definition()

        self.assertNotEqual(definition["release"]["version"], "0.0.9")
        self.assertEqual(definition["release"]["title"], definition["release"]["version"])

    def _get_operations(self):
        return {
            operation["operationId"]: operation
            for methods in self.resources["paths"].values()
            for operation in methods.values()
            if isinstance(operation, dict) and "operationId" in operation
        }

    @staticmethod
    def _load_definition():
        content = (BACKEND_DIR / "support-files/apigw/definition.yaml").read_text(encoding="utf-8")
        content = re.sub(
            r"\{% for admin in settings\.SYSTEM_ADMIN %\}.*?\{% endfor %\}",
            '      - "admin"',
            content,
            flags=re.DOTALL,
        )
        return yaml.safe_load(content)

"""验证 Flow 引擎或部署失败时业务状态的错误提示。"""
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase, override_settings

from services.web.bkbase import flow


@override_settings(BKBASE_API_VERSION="v4")
class FlowFailureMessageTests(SimpleTestCase):
    def setUp(self):
        self.context = {"tenant": "tenant_a", "namespace": "audit", "mcp_project_id": 1}
        ref = {"kind": "Flow", "tenant": "tenant_a", "namespace": "audit", "name": "flow_a"}
        self.strategy = SimpleNamespace(
            backend_data={"bkbase_v4": {"flow": ref, "operation_id": "op_a", "requested_action": "start"}}
        )
        self.cr = {"spec": {}, "status": {"phase": "Ok", "message": ""}}
        self.engine = {"flow_status": "running"}
        self.deployment = {"status": "failure"}
        self.enterContext(mock.patch("services.web.bkbase.flow.get_bkbase_context", return_value=self.context))
        self.enterContext(mock.patch("services.web.bkbase.flow._save_operation_binding"))
        self.enterContext(mock.patch("services.web.bkbase.flow.resolve_engine_flow_id", return_value=5))
        self.enterContext(mock.patch("services.web.bkbase.flow.api.bk_base_v4.flow_get", return_value=self.cr))
        self.enterContext(mock.patch("services.web.bkbase.flow.api.bk_base_v4.flow_status", return_value=self.engine))
        self.enterContext(
            mock.patch("services.web.bkbase.flow.api.bk_base_v4.flow_latest_deploy", return_value=self.deployment)
        )

    def test_deployment_failure_without_cr_message_has_generic_message(self):
        result = flow.strategy_deploy_data(self.strategy)
        self.assertEqual(result["status"], "failure")
        self.assertEqual(result["logs"], [{"level": "ERROR", "message": "Flow deployment reported failure."}])

    def test_engine_failure_without_cr_message_has_generic_message(self):
        self.engine["flow_status"] = "failure"
        self.deployment["status"] = "success"
        result = flow.strategy_deploy_data(self.strategy)
        self.assertEqual(result["status"], "failure")
        self.assertEqual(result["logs"], [{"level": "ERROR", "message": "Flow engine reported failure."}])

    def test_deployment_message_takes_priority_when_both_fail(self):
        self.engine["flow_status"] = "failure"
        result = flow.strategy_deploy_data(self.strategy)
        self.assertEqual(result["status"], "failure")
        self.assertEqual(result["logs"], [{"level": "ERROR", "message": "Flow deployment reported failure."}])

    def test_failures_preserve_existing_cr_message(self):
        self.cr["status"]["message"] = "existing diagnostic"
        for engine_state, deployment_state in (("running", "failure"), ("failure", "success"), ("failure", "failure")):
            with self.subTest(engine=engine_state, deployment=deployment_state):
                self.engine["flow_status"] = engine_state
                self.deployment["status"] = deployment_state
                result = flow.strategy_deploy_data(self.strategy)
                self.assertEqual(result["status"], "failure")
                self.assertEqual(result["logs"], [{"level": "ERROR", "message": "existing diagnostic"}])

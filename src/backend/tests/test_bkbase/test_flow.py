"""验证Flow整图转换、稳定身份和真实运行状态边界。"""
import json
from copy import deepcopy
from types import SimpleNamespace
from unittest import mock

import requests
from django.test import SimpleTestCase, TransactionTestCase, override_settings

from services.web.analyze import tasks as analyze_tasks
from services.web.bkbase import flow
from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.strategy_v2.constants import StrategyStatusChoices
from tests.test_bkbase.test_flow_pure_operation import FlowFixture


class FlowTests(SimpleTestCase):
    def setUp(self):
        self.context = {"version": "v4", "tenant": "tenant_a", "namespace": "audit", "mcp_project_id": 7}
        self.ref = {"kind": "Flow", "tenant": "tenant_a", "namespace": "audit", "name": "flow_a"}

    def test_compile_realtime_graph(self):
        strategy = SimpleNamespace(
            strategy_id=7, strategy_name="test rule", namespace="audit", sql="SELECT * FROM rt_a", backend_data={}
        )
        rt = {"result_table_id": "rt_a", "bk_biz_id": 1, "fields": [], "storages": {}}
        bindings = {
            "sources": {
                "rt_a": {
                    "kind": "StreamSourceNode",
                    "data": {"kind": "ResultTable", "tenant": "tenant_a", "namespace": "inputs", "name": "rt_a"},
                }
            },
            "output": "1_audit_rule_7",
            "biz_id": 1,
            "sql_node": {
                "kind": "StreamNode",
                "config": {"sql": "SELECT * FROM rt_a", "window_config": {"type": None}},
            },
            "storages": [],
        }
        result = flow.build_rule_flow(strategy, rt_metadata=[rt], binding_map=bindings)
        source_node, sql_node = result["nodes"]
        self.assertEqual(source_node["data"]["namespace"], "inputs")
        self.assertEqual(sql_node["inputs"], [source_node["name"]])
        self.assertEqual(sql_node["output"], "1_audit_rule_7")
        self.assertEqual(result, flow.build_rule_flow(strategy, rt_metadata=[rt], binding_map=bindings))

    def test_phase_ok_projects_applied_configuration(self):
        strategy = SimpleNamespace(backend_data={"bkbase_v4": {"flow": self.ref}})
        with mock.patch(
            "services.web.bkbase.flow.api.bk_base_v4.flow_get",
            return_value={"metadata": self.ref, "spec": {"nodes": []}, "status": {"phase": "Ok"}},
        ):
            result = flow.get_rule_flow_status(self.context, strategy)
            self.assertEqual(result["task_state"], "running")
            self.assertNotIn("engine", result)

    def test_response_identity_must_match_the_explicit_ref(self):
        strategy = SimpleNamespace(backend_data={"bkbase_v4": {"flow": self.ref}})
        with mock.patch(
            "services.web.bkbase.flow.api.bk_base_v4.flow_get",
            return_value={"metadata": {**self.ref, "name": "other"}, "spec": {"nodes": []}, "status": {"phase": "Ok"}},
        ):
            with self.assertRaises(BKBaseResourceMappingError):
                flow.get_rule_flow_status(self.context, strategy)


@override_settings(
    BKBASE_API_VERSION="v4",
    BKBASE_V4_TENANT="tenant_a",
    BKBASE_V4_NAMESPACE="audit",
    APP_CODE="synthetic_app",
    SECRET_KEY="synthetic_secret",
    BK_RESOURCE={
        "PLATFORM_AUTH_ENABLED": True,
        "PLATFORM_AUTH_ACCESS_USERNAME": "synthetic_platform",
        "PLATFORM_AUTH_ACCESS_TOKEN": "synthetic_token",
    },
)
class FlowNotificationTests(SimpleTestCase):
    """从真实Celery业务入口穿过Service和Resource.request验证通知协议。"""

    def setUp(self):
        self.ref = {"kind": "Flow", "tenant": "tenant_a", "namespace": "flow_project", "name": "actual_flow"}
        self.strategy = SimpleNamespace(
            strategy_id=17,
            backend_data={"bkbase_v4": {"flow": self.ref, "operation_id": "current_operation"}},
            notice_groups=[1],
        )
        self.channels = ["rtx", "mail"]
        self.config = {
            "active": False,
            "alert_config": {
                "notify_group_configs": [
                    {
                        "active": True,
                        "group": "data_exception_group",
                        "group_alias": "异常",
                        "notify_configs": [{"type": "task_status", "task_status": "failed", "future": 1}],
                        "receiver_config": {
                            "receivers": ["old_user"],
                            "notify_channels": ["sms"],
                            "receive_groups": ["retained_group"],
                            "future": "keep",
                        },
                    }
                ],
                "converge_rules": [{"type": "TimeWindow", "threshold": 8, "times": 2, "duration": 20}],
                "future": {"retain": True},
            },
        }
        self.calls = []
        self.enterContext(
            mock.patch.object(
                analyze_tasks.Strategy.objects, "filter", return_value=SimpleNamespace(first=lambda: self.strategy)
            )
        )
        self.enterContext(
            mock.patch.object(
                analyze_tasks.NoticeGroup.objects,
                "filter",
                side_effect=lambda **kw: [SimpleNamespace(notice_config=[{"msg_type": c} for c in self.channels])],
            )
        )
        self.enterContext(
            mock.patch.object(analyze_tasks.IgnoreMemberVariableParser, "parse_groups", return_value=["synthetic_user"])
        )
        self.enterContext(mock.patch("requests.sessions.Session.request", side_effect=self.transport))

    def transport(self, method, url, **kwargs):
        self.calls.append((method, url, deepcopy(kwargs)))
        self.assertTrue(url.endswith("/v4/databus/data_source/notifies/"))
        self.assertEqual(kwargs["headers"]["X-Bk-Tenant-Id"], "tenant_a")
        auth = json.loads(kwargs["headers"]["x-bkapi-authorization"])
        self.assertEqual(auth["bk_username"], "synthetic_platform")
        self.assertNotIn("tenant", kwargs.get("params", {}))
        self.assertNotIn("tenant", kwargs.get("json", {}))
        response = requests.Response()
        response.status_code = 200
        response._content = json.dumps({"result": True, "code": "00", "data": self.config}).encode()
        return response

    def test_task_accepts_only_v4_ref_and_preserves_complete_detection_config(self):
        old = deepcopy(self.config)
        analyze_tasks.toggle_monitor.run(17, True, operation_id="current_operation")
        self.assertEqual([c[0] for c in self.calls], ["GET", "PUT"])
        self.assertEqual(
            self.calls[0][2]["params"], {"kind": "Flow", "namespace": "flow_project", "name": "actual_flow"}
        )
        payload = self.calls[1][2]["json"]
        self.assertEqual(payload["target"], {"kind": "Flow", "namespace": "flow_project", "name": "actual_flow"})
        expected = deepcopy(old["alert_config"])
        expected["notify_group_configs"][0]["receiver_config"].update(
            receivers=["synthetic_user"], notify_channels=["mail", "rtx"]
        )
        self.assertIs(payload["active"], True)
        self.assertEqual(payload["alert_config"], expected)
        self.assertEqual(self.config, old)

    def test_v4_message_without_operation_id_has_no_platform_calls(self):
        analyze_tasks.toggle_monitor.run(17, False)
        self.assertEqual(self.calls, [])

    def test_mixed_legacy_weixin_keeps_mail_without_remapping_it_to_rtx(self):
        self.channels = ["weixin", "mail"]
        with mock.patch("services.web.bkbase.flow.logger", create=True) as flow_logger:
            analyze_tasks.toggle_monitor.run(17, True, operation_id="current_operation")
        self.assertEqual([call[0] for call in self.calls], ["GET", "PUT"])
        receiver = self.calls[1][2]["json"]["alert_config"]["notify_group_configs"][0]["receiver_config"]
        self.assertEqual(receiver["notify_channels"], ["mail"])
        self.assertEqual(self.channels, ["weixin", "mail"])
        flow_logger.warning.assert_called_once()

    def test_only_weixin_activation_is_rejected_before_platform_requests(self):
        self.channels = ["weixin"]
        with self.assertRaises(BKBaseResourceMappingError) as caught:
            analyze_tasks.toggle_monitor.run(17, True, operation_id="current_operation")
        self.assertIn("移除微信", str(caught.exception))
        self.assertEqual(self.calls, [])

    def test_disabling_legacy_weixin_preserves_the_complete_remote_configuration(self):
        self.channels = ["weixin"]
        old = deepcopy(self.config["alert_config"])
        analyze_tasks.toggle_monitor.run(17, False, operation_id="current_operation")
        self.assertEqual([call[0] for call in self.calls], ["GET", "PUT"])
        payload = self.calls[1][2]["json"]
        self.assertFalse(payload["active"])
        self.assertEqual(payload["alert_config"], old)

    def test_disabling_without_current_local_channels_or_members_still_closes_monitor(self):
        self.channels = []
        old = deepcopy(self.config["alert_config"])
        with mock.patch.object(analyze_tasks.IgnoreMemberVariableParser, "parse_groups", return_value=[]):
            analyze_tasks.toggle_monitor.run(17, False, operation_id="current_operation")
        self.assertEqual([call[0] for call in self.calls], ["GET", "PUT"])
        self.assertFalse(self.calls[1][2]["json"]["active"])
        self.assertEqual(self.calls[1][2]["json"]["alert_config"], old)

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_monitor_keeps_legacy_weixin_configuration(self):
        self.strategy.backend_data["flow_id"] = 901
        original = {"id": 3, "future": "keep"}
        with mock.patch.object(flow, "get_alert_configs", return_value=deepcopy(original)), mock.patch.object(
            flow, "edit_alert_configs", return_value={"ok": True}
        ) as edit:
            result = flow.configure_monitor(
                self.strategy,
                active=True,
                receivers=[{"receiver_type": "user", "username": "synthetic_user"}],
                notify_config=["weixin"],
            )
        self.assertEqual(result, {"ok": True})
        self.assertEqual(edit.call_args.kwargs["notify_config"], ["weixin"])
        self.assertEqual(edit.call_args.kwargs["future"], "keep")

    def test_generation_change_before_first_get_has_no_platform_calls(self):
        def change_before_configure(*args, **kwargs):
            self.strategy.backend_data["bkbase_v4"]["operation_id"] = "new_operation"
            return [SimpleNamespace(notice_config=[{"msg_type": "mail"}])]

        with mock.patch.object(analyze_tasks.NoticeGroup.objects, "filter", side_effect=change_before_configure):
            analyze_tasks.toggle_monitor.run(17, False, operation_id="current_operation")
        self.assertEqual(self.calls, [])

    def test_monitor_put_is_skipped_if_get_supersedes_operation(self):
        original = self.transport

        def get_then_supersede(method, url, **kwargs):
            response = original(method, url, **kwargs)
            if method.upper() == "GET":
                self.strategy.backend_data["bkbase_v4"]["operation_id"] = "new_operation"
            return response

        with mock.patch("requests.sessions.Session.request", side_effect=get_then_supersede):
            analyze_tasks.toggle_monitor.run(17, False, operation_id="current_operation")
        self.assertEqual([call[0] for call in self.calls], ["GET"])

    def test_monitor_put_is_skipped_if_get_changes_flow_reference(self):
        original = self.transport

        def get_then_change_ref(method, url, **kwargs):
            response = original(method, url, **kwargs)
            if method.upper() == "GET":
                self.strategy.backend_data["bkbase_v4"]["flow"] = {**self.ref, "name": "new_flow"}
            return response

        with mock.patch("requests.sessions.Session.request", side_effect=get_then_change_ref):
            analyze_tasks.toggle_monitor.run(17, False, operation_id="current_operation")
        self.assertEqual([call[0] for call in self.calls], ["GET"])

    def test_task_skips_superseded_monitor_operation_before_any_http(self):
        self.strategy.backend_data["bkbase_v4"]["operation_id"] = "current_operation"
        analyze_tasks.toggle_monitor.run(17, True, operation_id="old_operation")
        self.assertEqual(self.calls, [])

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v4_monitor_message_is_not_replayed_through_v3_after_version_switch(self):
        self.strategy.backend_data.update(flow_id=901)
        self.strategy.backend_data["bkbase_v4"]["operation_id"] = "current_operation"
        analyze_tasks.toggle_monitor.run(17, True, operation_id="current_operation")
        self.assertEqual(self.calls, [])

    def test_missing_legacy_flow_mapping_fails_before_any_notify_request(self):
        self.strategy.backend_data = {"flow_id": 901, "bkbase_v4": {"operation_id": "current_operation"}}
        with self.assertRaises(BKBaseResourceMappingError):
            analyze_tasks.toggle_monitor.run(17, True, operation_id="current_operation")
        self.assertEqual(self.calls, [])

    def test_wrong_tenant_ref_fails_without_default_notify_creation(self):
        self.ref["tenant"] = "tenant_b"
        with self.assertRaises(BKBaseResourceMappingError):
            analyze_tasks.toggle_monitor.run(17, True, operation_id="current_operation")
        self.assertEqual(self.calls, [])

    def test_unsupported_channel_fails_instead_of_silently_dropping_it(self):
        self.channels = ["unsupported_synthetic_channel"]
        with self.assertRaises(BKBaseResourceMappingError):
            analyze_tasks.toggle_monitor.run(17, True, operation_id="current_operation")
        self.assertEqual(self.calls, [])

    def test_incomplete_native_config_is_not_replaced_by_a_partial_put(self):
        del self.config["alert_config"]["converge_rules"]
        with self.assertRaises(BKBaseResourceMappingError):
            analyze_tasks.toggle_monitor.run(17, False, operation_id="current_operation")
        self.assertEqual([c[0] for c in self.calls], ["GET"])

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_task_keeps_existing_payload_and_receiver_shape(self):
        self.strategy.backend_data = {"flow_id": 901}
        with mock.patch.object(
            flow.api.bk_base, "get_alert_configs", return_value={"id": 8, "retained": 1}
        ), mock.patch.object(flow.api.bk_base, "edit_alert_configs", return_value=True) as write:
            analyze_tasks.toggle_monitor.run(17, False)
        channels = write.call_args.kwargs.pop("notify_config")
        self.assertCountEqual(channels, ["rtx", "mail"])
        self.assertEqual(
            write.call_args.kwargs,
            {
                "id": 8,
                "retained": 1,
                "alert_config_id": 8,
                "active": False,
                "receivers": [{"receiver_type": "user", "username": "synthetic_user"}],
            },
        )
        self.assertEqual(self.calls, [])


@override_settings(
    BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="tenant_a", BKBASE_V4_NAMESPACE="audit", BKBASE_V4_MCP_PROJECT_ID=11
)
class FlowStopDeclarationTests(FlowFixture, TransactionTestCase):
    def test_stop_preserves_spec_and_uses_string_annotation(self):
        original = deepcopy(self.remote)
        self.stop()
        self.assertEqual(len(self.writes()), 1)
        _, url, request = self.writes()[0]
        self.assertIn("/v4/tenants/tenant_a/namespaces/audit/flows/flow_a/", url)
        original["metadata"]["annotations"]["task_stopped"] = "true"
        self.assertEqual(request["json"]["metadata"], original["metadata"])
        self.assertEqual(request["json"]["spec"], original["spec"])
        self.assertIsNone(request["json"]["status"])
        self.assertEqual(self.binding()["pure_operation"]["accepted"], True)
        self.assertEqual(self.strategy.status, StrategyStatusChoices.STOPPING)
        self.assertFalse(any("/mcp/" in url for _, url, _ in self.calls))

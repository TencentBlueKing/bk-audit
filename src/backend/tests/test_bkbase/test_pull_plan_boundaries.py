"""PULL旧入口保留V3行为，V4未闭合路径不再归因于已答复B04。"""
from types import SimpleNamespace
from unittest import mock

from bk_resource.exceptions import APIRequestError
from django.test import SimpleTestCase, override_settings

from api.bk_base_v4 import default as v4_api
from services.web.bkbase import source
from services.web.bkbase.exceptions import BKBaseResourceMappingError


class PullPlanBoundaryTests(SimpleTestCase):
    @override_settings(BKBASE_API_VERSION="v4")
    def test_explicit_sensitivity_change_passes_to_maintenance(self):
        snapshot = SimpleNamespace(status="running", bkbase_data_id=11, pull_config={"sensitivity": "private"})
        with mock.patch.object(source, "prepare_snapshot_replay", return_value=True) as prepare:
            self.assertTrue(
                source.update_deploy_plan(
                    {"bkbase_data_id": 11, "reset_to_head": True, "access_raw_data": {"sensitivity": "public"}},
                    snapshot=snapshot,
                )
            )
        prepare.assert_called_once_with(
            snapshot, {"reset_to_head": True, "access_raw_data": {"sensitivity": "public"}}, configure=True
        )

    def test_v4_create_resources_send_full_body_without_redirects(self):
        for cls, path in ((v4_api.DataConnCreate, "dataconns"), (v4_api.DataSourceCreate, "datasources")):
            with self.subTest(path=path):
                resource = cls()
                response = mock.Mock(status_code=200)
                response.json.return_value = {"result": True, "code": "00", "data": {"metadata": {}, "spec": {}}}
                resource.session.request = mock.Mock(return_value=response)
                resource.build_header = mock.Mock(return_value={})
                resource.request(tenant="tenant_a", namespace="project_a", metadata={"name": "source_a"}, spec={})
                request = resource.session.request.call_args.kwargs
                self.assertTrue(request["url"].endswith(f"/namespaces/project_a/{path}/"))
                self.assertEqual(request["json"], {"metadata": {"name": "source_a"}, "spec": {}, "status": None})
                self.assertIs(request["allow_redirects"], False)

    def test_v4_create_rejects_redirect_even_with_success_body(self):
        for cls in (v4_api.DataConnCreate, v4_api.DataSourceCreate):
            with self.subTest(resource=cls.__name__):
                resource = cls()
                response = mock.Mock(status_code=307)
                response.json.return_value = {"result": True, "code": "00", "data": {}}
                resource.session.request = mock.Mock(return_value=response)
                resource.build_header = mock.Mock(return_value={})
                with self.assertRaises(APIRequestError):
                    resource.request(tenant="tenant_a", namespace="project_a", metadata={"name": "source_a"}, spec={})
                resource.session.request.assert_called_once()

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_plan_requests_keep_reset_and_delay(self):
        params = {"reset_to_head": True, "access_conf_info": {"delay": 1}, "bkbase_data_id": 11}
        for operation in ("create_deploy_plan", "update_deploy_plan"):
            with self.subTest(operation=operation), mock.patch.object(
                source.api.bk_base, operation, return_value={"raw_data_id": 11}
            ) as endpoint:
                self.assertEqual(getattr(source, operation)(params), {"raw_data_id": 11})
                endpoint.assert_called_once_with(reset_to_head=True, access_conf_info={"delay": 1}, bkbase_data_id=11)

    @override_settings(BKBASE_API_VERSION="v4")
    def test_new_pull_requires_snapshot_owner_before_network(self):
        with mock.patch("requests.sessions.Session.request", side_effect=AssertionError("Unexpected HTTP")):
            with self.assertRaises(BKBaseResourceMappingError):
                source.create_deploy_plan({"reset_to_head": True})

    @override_settings(BKBASE_API_VERSION="v4")
    def test_existing_pull_legacy_parameters_require_audit_workflow_binding(self):
        with mock.patch("requests.sessions.Session.request", side_effect=AssertionError("Unexpected HTTP")):
            with self.assertRaises(BKBaseResourceMappingError):
                source.update_deploy_plan({"bkbase_data_id": 11, "reset_to_head": True})

"""规则离线历史通过正式 Flow、Batch Resource 和业务消费者读取。"""
import datetime
import json
from types import SimpleNamespace
from unittest import mock
from urllib.parse import parse_qs, urlparse

import requests
from bk_resource.exceptions import APIRequestError
from django.test import SimpleTestCase, override_settings

from api.bk_base_v4.default import BatchStatusList, FlowGet
from services.web.bkbase import flow
from services.web.bkbase.exceptions import (
    BKBaseCapabilityNotReady,
    BKBaseResourceMappingError,
)
from services.web.strategy_v2.handlers.strategy_running_status import (
    ModelAuditBatchV2StrategyRunningStatusHandler,
    RuleAuditBatchV2StrategyRunningStatusHandler,
)


@override_settings(BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="tenant_a", BKBASE_V4_NAMESPACE="project_a")
class BatchHistoryConsumerTests(SimpleTestCase):
    def setUp(self):
        self.ref = {"kind": "Flow", "tenant": "tenant_a", "namespace": "project_a", "name": "flow_a"}
        self.strategy = SimpleNamespace(backend_data={"bkbase_v4": {"flow": self.ref}})
        self.handler = RuleAuditBatchV2StrategyRunningStatusHandler(
            self.strategy,
            datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc),
            datetime.datetime(2024, 1, 2, tzinfo=datetime.timezone.utc),
            2,
            3,
        )
        self.resource = BatchStatusList()
        self.resource.build_header = mock.Mock(return_value={})
        self.pages = []
        self.calls = []

        def transport(method, url, **kwargs):
            self.calls.append((method, url, kwargs))
            response = requests.Response()
            response.status_code = 200
            response._content = json.dumps({"result": True, "code": "00", "data": self.pages.pop(0)}).encode()
            return response

        self.resource.session.request = mock.Mock(side_effect=transport)
        self.enterContext(mock.patch.object(flow.api.bk_base_v4, "batch_status_list", self.resource.request))
        self.flow_resource = FlowGet()
        self.flow_resource.build_header = mock.Mock(return_value={})
        self.flow_value = {
            "kind": "Flow",
            "metadata": {k: self.ref[k] for k in ("tenant", "namespace", "name")},
            "spec": {"nodes": [{"kind": "BatchSqlNode", "name": "node_a", "output": "actual_job"}]},
            "status": {"phase": "Ok"},
        }

        def flow_transport(method, url, **kwargs):
            response = requests.Response()
            response.status_code = 200
            response._content = json.dumps({"result": True, "code": "00", "data": self.flow_value}).encode()
            return response

        self.flow_resource.session.request = mock.Mock(side_effect=flow_transport)
        self.enterContext(mock.patch.object(flow.api.bk_base_v4, "flow_get", self.flow_resource.request))

    @mock.patch.object(flow, "batch_processing_id", return_value="actual_job")
    def test_empty_page_with_simulated_job_association(self, _job):
        self.pages = [{"history": []}]
        self.assertEqual(self.handler.get_strategy_running_status(), [])
        _, url, kwargs = self.calls[0]
        self.assertTrue(url.endswith("/v4/dataflow/batch/jobs/actual_job/status_list/"))
        self.assertEqual(
            kwargs["params"],
            {
                "start_time": "2024-01-01 00:00:00",
                "end_time": "2024-01-02 00:00:00",
                "page_num": 2,
                "page_size": 2,
                "is_data_time": "true",
            },
        )

    def test_unaligned_offset_is_sliced_once_and_nonempty_is_projected(self):
        self.pages = [{"history": [{"id": 2}, {"id": 3}]}, {"history": [{"id": 4}, {"id": 5}]}]
        self.assertEqual(self.handler.get_running_status_list(), [{"id": 3}, {"id": 4}])
        self.assertEqual([x[2]["params"]["page_num"] for x in self.calls], [2, 3])
        self.calls.clear()
        row = {
            "schedule_time": 1704067200000,
            "data_time": None,
            "err_msg": "synthetic",
            "status": "failed",
            "status_str": "Execution failed",
        }
        self.pages = [{"history": [{"id": 2}, row]}, {"history": []}]
        with mock.patch.object(self.handler, "get_risk_count_map", return_value={}):
            result = self.handler.get_strategy_running_status()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["data_time"], "")
        self.assertEqual(result[0]["status"], "failed")

    def test_bound_flow_reads_native_node_then_queries_job(self):
        self.pages = [{"history": []}]
        self.assertEqual(self.handler.get_strategy_running_status(), [])
        self.assertTrue(
            self.flow_resource.session.request.call_args.args[1].endswith("/namespaces/project_a/flows/flow_a/")
        )
        self.assertTrue(self.calls[0][1].endswith("/jobs/actual_job/status_list/"))

    def test_native_flow_identity_and_structure_are_verified(self):
        context = flow.get_bkbase_context()
        self.assertEqual(
            flow.read_flow_nodes(context, self.ref),
            [{"kind": "BatchSqlNode", "name": "node_a", "output": "actual_job"}],
        )
        self.flow_value["metadata"]["name"] = "other"
        with self.assertRaises(BKBaseResourceMappingError):
            self.handler.get_strategy_running_status()
        self.flow_value["metadata"]["name"] = "flow_a"
        self.flow_value["spec"]["nodes"] = None
        with self.assertRaises(BKBaseResourceMappingError):
            self.handler.get_strategy_running_status()
        self.flow_value["spec"]["nodes"] = []
        self.assertEqual(flow.read_flow_nodes(context, self.ref), [])
        self.flow_value["metadata"]["tenant"] = "other"
        with self.assertRaises(BKBaseResourceMappingError):
            flow.read_flow_nodes(context, self.ref)

    def test_batch_resource_encodes_query_boolean_in_lowercase(self):
        for value, expected in ((True, "true"), (False, "false")):
            with self.subTest(value=value):
                self.pages = [{"history": []}]
                self.resource.request(
                    job_id="synthetic_job",
                    start_time="2024-01-01 00:00:00",
                    end_time="2024-01-02 00:00:00",
                    page_num=1,
                    page_size=10,
                    is_data_time=value,
                )
                method, url, kwargs = self.calls[-1]
                prepared = requests.Request(method, url, params=kwargs["params"]).prepare()
                self.assertEqual(parse_qs(urlparse(prepared.url).query)["is_data_time"], [expected])

    def test_wrong_tenant_cannot_use_job_binding(self):
        self.ref["tenant"] = "other"
        with self.assertRaises(BKBaseResourceMappingError):
            self.handler.get_strategy_running_status()
        self.assertEqual(self.calls, [])

    def test_model_audit_stays_deprecated_path(self):
        handler = ModelAuditBatchV2StrategyRunningStatusHandler(
            self.strategy, self.handler.start_time, self.handler.end_time, 2, 0
        )
        with self.assertRaises(BKBaseCapabilityNotReady) as caught:
            handler.get_strategy_running_status()
        self.assertEqual(caught.exception.blocker_id, "B09")
        self.assertEqual(self.calls, [])
        self.flow_resource.session.request.assert_not_called()

    def test_missing_old_flow_mapping_is_c19(self):
        self.strategy.backend_data = {"flow_id": 23}
        with self.assertRaises(BKBaseResourceMappingError) as caught:
            self.handler.get_strategy_running_status()
        self.assertIn("C19", str(caught.exception))
        self.assertEqual(self.calls, [])

    @mock.patch.object(flow, "batch_processing_id", return_value="actual_job")
    def test_missing_job_is_error_not_empty_history(self, _job):
        response = requests.Response()
        response.status_code = 200
        response._content = json.dumps(
            {"result": False, "code": "1558014", "message": "job missing", "data": None}
        ).encode()
        self.resource.session.request = mock.Mock(return_value=response)
        with self.assertRaises(APIRequestError):
            self.handler.get_strategy_running_status()

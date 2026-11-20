"""验证离线作业历史的 V4 契约和分页，不推断业务数据时间。"""
from unittest import mock

from bk_resource.exceptions import APIRequestError
from django.test import SimpleTestCase, override_settings

from api.bk_base_v4 import default as v4_api
from services.web.bkbase import flow
from services.web.bkbase.exceptions import BKBaseResourceMappingError


@override_settings(BKBASE_API_VERSION="v4")
class BatchHistoryContractTests(SimpleTestCase):
    def resource(self, pages):
        resource = v4_api.BatchStatusList()
        responses = []
        for data in pages:
            response = mock.Mock()
            response.json.return_value = {"result": True, "code": "00", "data": data}
            response.raise_for_status.return_value = None
            responses.append(response)
        resource.session.request = mock.Mock(side_effect=responses)
        resource.build_header = mock.Mock(return_value={})
        return resource

    def test_non_aligned_offset_fetches_two_pages_and_slices_once(self):
        self.assertTrue(hasattr(v4_api, "BatchStatusList"))
        resource = self.resource([{"history": [{"id": 2}, {"id": 3}]}, {"history": [{"id": 4}, {"id": 5}]}])
        with mock.patch.object(flow.api.bk_base_v4, "batch_status_list", resource.request):
            result = flow.dataflow_batch_status_list(
                processing_id="1_job",
                data_start=1704067200000,
                data_end=1704070800000,
                offset=3,
                limit=2,
            )
        self.assertEqual(result, [{"id": 3}, {"id": 4}])
        first, second = resource.session.request.call_args_list
        self.assertEqual(first.args[0], "GET")
        self.assertTrue(first.args[1].endswith("/v4/dataflow/batch/jobs/1_job/status_list/"))
        self.assertEqual(
            first.kwargs["params"],
            {
                "start_time": "2024-01-01 00:00:00",
                "end_time": "2024-01-01 01:00:00",
                "is_data_time": "true",
                "page_num": 2,
                "page_size": 2,
            },
        )
        self.assertEqual(second.kwargs["params"]["page_num"], 3)

    def test_invalid_history_shape_is_not_empty_success(self):
        resource = self.resource([{"history": "invalid"}])
        with mock.patch.object(flow.api.bk_base_v4, "batch_status_list", resource.request):
            with self.assertRaises(BKBaseResourceMappingError):
                flow.dataflow_batch_status_list(
                    processing_id="1_job",
                    data_start=0,
                    data_end=1000,
                    offset=0,
                    limit=2,
                )

    def test_missing_job_error_is_not_empty_history(self):
        resource = self.resource([])
        response = mock.Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"result": False, "code": "1558014", "data": None, "message": "job not found"}
        resource.session.request = mock.Mock(return_value=response)
        with mock.patch.object(flow.api.bk_base_v4, "batch_status_list", resource.request):
            with self.assertRaises(APIRequestError):
                flow.dataflow_batch_status_list(
                    processing_id="1_job",
                    data_start=0,
                    data_end=1000,
                    offset=0,
                    limit=2,
                )

"""以V4实测字符串数组验证审计原始数据与最近日志消费者。

样本为合成输入；不借HTTP源推断BKLog包装或时间字段。
V3返回及JSON解码错误行为保持现有契约。
"""
import json
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase, override_settings

from api.bk_base_v4.default import DataIdTail
from services.web.bkbase import source
from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.databus.collector.handlers import BkBaseTailLogHandler
from services.web.databus.collector.resources import GetDataIdTail


@override_settings(BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="tenant_a", BKBASE_V4_NAMESPACE="audit")
class TailConsumerTests(SimpleTestCase):
    def setUp(self):
        transport = mock.patch("requests.sessions.Session.request", side_effect=AssertionError("Unexpected HTTP"))
        transport.start()
        self.addCleanup(transport.stop)
        self.context = {"version": "v4", "tenant": "tenant_a", "namespace": "audit"}
        self.ref = {"kind": "DataId", "tenant": "tenant_a", "namespace": "raw_project", "name": "data_a"}
        synced = {
            "kind": "DataSource",
            "metadata": {"name": "source_a", "namespace": "audit", "labels": {"raw_data_id": "11"}},
            "spec": {"data_id": {"namespace": "raw_project", "name": "data_a"}},
        }
        sources = mock.patch.object(source.api.bk_base_v4, "data_source_list", return_value=[synced])
        sources.start()
        self.addCleanup(sources.stop)

    def test_raw_tail_keeps_text_without_inventing_topic_or_time(self):
        payload = ['{"event_id":"sample"}', "invalid json", ""]
        with mock.patch.object(source.api.bk_base_v4, "data_id_tail", return_value=payload) as tail:
            result = GetDataIdTail().request({"bk_data_id": 11})
        self.assertEqual(result, [{"value": '{"event_id":"sample"}'}, {"value": "invalid json"}, {"value": ""}])
        self.assertEqual(payload, ['{"event_id":"sample"}', "invalid json", ""])
        tail.assert_called_once_with(namespace="raw_project", name="data_a")

    def test_parsed_tail_keeps_existing_business_response_without_mutating_upstream(self):
        payload = ['{"event_id":"sample"}', '[1,2]', 'null']
        with mock.patch.object(source.api.bk_base_v4, "data_id_tail", return_value=payload):
            result = GetDataIdTail().request({"bk_data_id": 11, "parse_json": True})
        self.assertEqual(
            result, [{"parsed_value": {"event_id": "sample"}}, {"parsed_value": [1, 2]}, {"parsed_value": None}]
        )
        self.assertEqual(payload, ['{"event_id":"sample"}', '[1,2]', 'null'])

    def test_empty_tail_is_empty_for_both_modes(self):
        for parse_json in (False, True):
            with self.subTest(parse_json=parse_json), mock.patch.object(
                source.api.bk_base_v4, "data_id_tail", return_value=[]
            ):
                self.assertEqual(GetDataIdTail().request({"bk_data_id": 11, "parse_json": parse_json}), [])

    def test_invalid_json_is_rejected_when_parsing_is_requested(self):
        with mock.patch.object(source.api.bk_base_v4, "data_id_tail", return_value=["not json"]):
            with self.assertRaises(json.JSONDecodeError):
                GetDataIdTail().request({"bk_data_id": 11, "parse_json": True})

    def test_unknown_tail_shape_is_not_silently_coerced(self):
        for payload in ({"list": []}, [1], [None], ["sample", {"value": "other"}]):
            with self.subTest(payload=payload), mock.patch.object(
                source.api.bk_base_v4, "data_id_tail", return_value=payload
            ):
                with self.assertRaises(BKBaseResourceMappingError):
                    source.tail_source(self.context, self.ref)

    def test_log_handler_can_load_value_but_does_not_guess_missing_time(self):
        collector = SimpleNamespace(bk_data_id=11, collector_config_id=1, tail_log_time=None, save=mock.Mock())
        handler = BkBaseTailLogHandler(collector)
        with mock.patch.object(source.api.bk_base_v4, "data_id_tail", return_value=['{"event_id":"sample"}']):
            handler.sync()
        self.assertEqual(handler.tail_logs, [{"value": '{"event_id":"sample"}'}])
        self.assertIsNone(collector.tail_log_time)

    def test_real_api_request_accepts_string_array_and_normalizes_only_in_service(self):
        resource = DataIdTail()
        response = mock.Mock()
        response.status_code = 200
        response.raise_for_status.return_value = None
        response.json.return_value = {"result": True, "code": "00", "data": ['{"event_id":"sample"}']}
        resource.session.get = mock.Mock(return_value=response)
        with mock.patch.object(resource, "build_header", return_value={}), mock.patch.object(
            source.api.bk_base_v4, "data_id_tail", resource.request
        ):
            self.assertEqual(source.tail_source(self.context, self.ref), [{"value": '{"event_id":"sample"}'}])
        self.assertTrue(resource.session.get.call_args.args[0].endswith('/raw_project/dataids/data_a/tail_kafka/'))

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_raw_and_parsed_tail_keep_existing_shape(self):
        for parse_json, expected in (
            (False, [{"topic": "legacy_topic", "value": '{"event_id":"sample"}'}]),
            (True, [{"topic": "legacy_topic", "parsed_value": {"event_id": "sample"}}]),
        ):
            with self.subTest(parse_json=parse_json), mock.patch.object(
                source.api.bk_base,
                "get_rawdata_tail",
                return_value=[{"topic": "legacy_topic", "value": '{"event_id":"sample"}'}],
            ) as tail:
                self.assertEqual(GetDataIdTail().request({"bk_data_id": 11, "parse_json": parse_json}), expected)
            tail.assert_called_once_with(bk_data_id=11, parse_json=parse_json)

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_invalid_json_keeps_existing_rejection(self):
        with mock.patch.object(source.api.bk_base, "get_rawdata_tail", return_value=[{"value": "not json"}]):
            with self.assertRaises(json.JSONDecodeError):
                GetDataIdTail().request({"bk_data_id": 11, "parse_json": True})

"""用合成网关响应验证正则预览消费者及发布规则的一致性。

真实平台取证已覆盖匹配、无匹配与失败；非业务使用的配置在本地拒绝。
仅替换HTTP传输，不触达真实平台或读取本地联调数据。
"""
import json
import re
from unittest import mock

import requests
from bk_resource.exceptions import APIRequestError
from django.test import SimpleTestCase, override_settings
from rest_framework.exceptions import ValidationError

from api.bk_base_v4 import default as v4_api
from apps.exceptions import RegexpExpressionError
from services.web.bkbase import clean
from services.web.databus.collector.etl.bk_log_regexp import BkLogRegexpEtlClean
from services.web.entry.handler.healthz import MockData


@override_settings(BKBASE_API_VERSION="v4")
class CleanPreviewTests(SimpleTestCase):
    def setUp(self):
        transport = mock.patch("requests.sessions.Session.request", side_effect=AssertionError("Unexpected HTTP"))
        transport.start()
        self.addCleanup(transport.stop)
        self.conf = {
            "type": "fun",
            "method": "regex_extract",
            "label": "label00001",
            "args": [{"result": "data", "keys": ["content"], "regexp": r"start_(?<content>\w+)_end"}],
            "next": None,
        }

    def response(self, value, *, status="succeed", rule_status="succeed", output_id="data"):
        return {
            "rules_output": [
                {
                    "status": rule_status,
                    "input_id": "__raw_data",
                    "output_id": output_id,
                    "type": "dict",
                    "value": value,
                }
            ],
            "output_selector": [],
            "final_output": {"fields": [], "values": [{}]},
            "status": status,
            "failed_message": "" if status == "succeed" else "ext_error",
        }

    def gateway(self, payload, *, status_code=200):
        response = requests.Response()
        response.status_code = status_code
        response.url = "https://gateway.test/v4/databus/clean/debug/"
        response.request = requests.Request("POST", response.url).prepare()
        response._content = (
            json.dumps({"result": True, "code": "00", "data": payload})
            if status_code == 200
            else "Failed to deserialize the JSON body: invalid regex"
        ).encode()
        resource = v4_api.CleanDebug()
        resource.session.request = mock.Mock(return_value=response)
        resource.build_header = mock.Mock(return_value={})
        return resource

    def test_regexp_consumer_preserves_values_and_sends_v4_protocol(self):
        resource = self.gateway(self.response({"content": '{"name":"value"}'}))
        with mock.patch.object(clean.api.bk_base_v4, "clean_debug", resource.request):
            result = BkLogRegexpEtlClean().etl_preview("  synthetic line  ", {"regexp": r"start_(?P<content>\w+)_end"})
        self.assertEqual(
            result,
            [
                {"key": "content", "val": {"name": "value"}, "path": "content"},
                {"key": "content/name", "val": "value", "path": "content/name"},
            ],
        )
        call = resource.session.request.call_args.kwargs
        self.assertTrue(call["url"].endswith("/v4/databus/clean/debug/"))
        self.assertEqual(
            call["json"],
            {
                "input": "  synthetic line  ",
                "rules": [
                    {
                        "input_id": "__raw_data",
                        "output_id": "data",
                        "operator": {"type": "regex", "regex": r"start_(?P<content>\w+)_end"},
                    }
                ],
                "filter_rules": [],
            },
        )

    def test_no_match_is_successful_empty_preview(self):
        resource = self.gateway(self.response({}))
        with mock.patch.object(clean.api.bk_base_v4, "clean_debug", resource.request):
            self.assertEqual(BkLogRegexpEtlClean().etl_preview("no match", {"regexp": "(?P<content>x)"}), [])

    def test_health_sample_reads_rule_output_instead_of_empty_final_output(self):
        resource = self.gateway(self.response({"content": "abcdefg"}))
        with mock.patch.object(clean.api.bk_base_v4, "clean_debug", resource.request):
            result = clean.clean_preview(
                msg=MockData.BkBaseCleanPreview.msg,
                conf=MockData.BkBaseCleanPreview.conf,
                debug_by_step=True,
                _is_backend=True,
            )
        self.assertEqual(result["nodes"], {"label00001": {"content": "abcdefg"}})

    def test_failed_or_malformed_output_never_becomes_empty_success(self):
        for payload in (
            self.response({}, status="failed", rule_status="failed"),
            self.response({}, rule_status="failed"),
            self.response({}, output_id="other"),
            self.response(None),
            {},
        ):
            with self.subTest(payload=payload):
                resource = self.gateway(payload)
                with mock.patch.object(clean.api.bk_base_v4, "clean_debug", resource.request):
                    with self.assertRaises(RegexpExpressionError):
                        BkLogRegexpEtlClean().etl_preview("line", {"regexp": "(?P<content>x)"})

    def test_invalid_regex_http_error_preserves_business_error(self):
        resource = self.gateway({"message": "invalid regex"}, status_code=422)
        with mock.patch.object(clean.api.bk_base_v4, "clean_debug", resource.request):
            with self.assertRaises(RegexpExpressionError):
                BkLogRegexpEtlClean().etl_preview("line", {"regexp": "(?P<content>"})

    def test_health_inner_failure_is_api_error(self):
        resource = self.gateway(self.response({}, status="failed", rule_status="failed"))
        with mock.patch.object(clean.api.bk_base_v4, "clean_debug", resource.request):
            with self.assertRaises(APIRequestError):
                clean.clean_preview(msg="line", conf=json.dumps(self.conf), debug_by_step=True)

    def test_unsupported_preview_config_is_local_validation_error_before_network(self):
        for conf in (
            {"type": "fun", "method": "from_json"},
            {**self.conf, "next": {"type": "assign"}},
            {**self.conf, "args": []},
            None,
        ):
            with self.subTest(conf=conf):
                with self.assertRaises(ValidationError) as caught:
                    clean.clean_preview(msg="line", conf=json.dumps(conf), debug_by_step=True)
                self.assertEqual(caught.exception.status_code, 400)
                self.assertIn("conf", caught.exception.detail)

    def test_publication_regex_reads_actual_producer_argument_and_keeps_lookbehind(self):
        config = {
            "extract": {
                **self.conf,
                "args": [{"result": "regexp_result", "keys": ["content"], "regexp": r"(?<=start_)(?<content>\w+)"}],
                "next": {
                    "type": "assign",
                    "assign": [{"key": "content", "assign_to": "event_content", "type": "string"}],
                },
            }
        }
        rules = clean.convert_rules(config)
        self.assertEqual(rules[0]["output_id"], "regexp_result")
        self.assertEqual(rules[0]["operator"], {"type": "regex", "regex": r"(?<=start_)(?P<content>\w+)"})
        self.assertEqual(rules[1]["input_id"], "regexp_result")

    def test_regex_group_conversion_keeps_character_classes_and_escaped_literals(self):
        patterns = [
            (r"[(?<name>]+(?P<content>[0-9]+)", r"[(?<name>]+(?P<content>[0-9]+)"),
            (r"\(\?<literal>(?<content>\d+)", r"\(\?<literal>(?P<content>\d+)"),
            (r"[[a](?<name>)](?<content>\d+)", r"[[a](?<name>)](?P<content>\d+)"),
            (r"[](?<name>]+(?<content>\d+)", r"[](?<name>]+(?P<content>\d+)"),
        ]
        for pattern, expected in patterns:
            with self.subTest(pattern=pattern):
                conf = {**self.conf, "args": [{"result": "data", "regexp": pattern}]}
                actual = clean.convert_rules({"extract": conf})[0]["operator"]["regex"]
                self.assertEqual(actual, expected)
        conf = {**self.conf, "args": [{"result": "data", "regexp": patterns[0][0]}]}
        actual = clean.convert_rules({"extract": conf})[0]["operator"]["regex"]
        self.assertIsNone(re.fullmatch(actual, "P123"))
        self.assertIsNotNone(re.fullmatch(actual, "?123"))

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_preview_keeps_original_request_and_response(self):
        params = {"msg": "line", "conf": json.dumps(self.conf), "debug_by_step": True}
        expected = {"nodes": {"label00001": {"content": "value"}}}
        with mock.patch.object(clean.api.bk_base, "clean_preview", return_value=expected) as preview:
            self.assertEqual(clean.clean_preview(params), expected)
        preview.assert_called_once_with(**params)

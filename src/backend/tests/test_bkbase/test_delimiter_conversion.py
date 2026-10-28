"""验证分隔符字段路径转换为 V4 数组下标。"""
from unittest import mock

from django.test import SimpleTestCase

from services.web.bkbase import clean
from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.databus.collector.etl.etl_config_handler.bk_log_delimiter import (
    DelimiterConfig,
)


class DelimiterConversionTests(SimpleTestCase):
    def test_business_delimiter_paths_become_integer_array_indices(self):
        producer = DelimiterConfig.__new__(DelimiterConfig)
        producer.fields = [
            {"field_name": "name", "field_type": "string", "option": {"path": "0/name"}},
            {"field_name": "payload", "field_type": "object", "option": {"path": "2"}},
        ]
        producer.etl_params = {"delimiter": "|"}
        producer.label_ids = set()
        with mock.patch.object(producer, "trans_config", side_effect=lambda config: {"extract": config}):
            config = producer.json_config

        rules = clean.convert_rules(config)
        indices = [rule["operator"]["key_index"][0] for rule in rules if rule["operator"]["type"] == "get"]
        self.assertEqual(indices, [{"type": "index", "value": 2}, {"type": "index", "value": 0}])

    def test_invalid_array_index_does_not_become_a_resource_request(self):
        for index in ("bad", "-1", True, None):
            config = {"extract": {"type": "access", "subtype": "access_pos", "index": index, "result": "item"}}
            with self.subTest(index=index), self.assertRaises(BKBaseResourceMappingError):
                clean.convert_rules(config)

    def test_numeric_object_keys_remain_strings(self):
        config = {"extract": {"type": "access", "subtype": "access_obj", "key": "2", "result": "item"}}
        rules = clean.convert_rules(config)
        self.assertEqual(rules[0]["operator"]["key_index"], [{"type": "key", "value": "2"}])

# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
"""
from unittest import mock

from bk_resource.exceptions import APIRequestError
from iam import OP

from services.web.vision.exceptions import VisionPermissionInvalid
from services.web.vision.handlers.convertor import DeptConvertor
from tests.base import TestCase


class TestDeptConvertor(TestCase):
    @mock.patch("services.web.vision.handlers.convertor.api.user_manage.retrieve_department")
    def test_convert_with_or_condition(self, mock_retrieve_department):
        mock_retrieve_department.side_effect = [
            {"full_name": "Finance"},
            {"full_name": "Dept200"},
        ]
        convertor = DeptConvertor({"tag.id": "tag_id"})
        data = {
            "op": OP.OR,
            "content": [
                {"op": OP.IN, "field": "tag.id", "value": ["1"]},
                {"op": OP.STARTS_WITH, "field": "tag.id", "value": "root/bk/1/,200"},
            ],
        }

        result = convertor.convert(data)

        self.assertListEqual(sorted(result.value), ["Dept200", "Finance"])
        self.assertEqual(mock_retrieve_department.call_count, 2)

    @mock.patch("services.web.vision.handlers.convertor.api.user_manage.retrieve_department", return_value={})
    def test_convert_with_and_condition(self, _):
        convertor = DeptConvertor()
        data = {
            "op": OP.AND,
            "content": [
                {"op": OP.STARTS_WITH, "field": "tag.id", "value": "123"},
                {"op": OP.IN, "field": "tag.id", "value": ["abc", "def"]},
            ],
        }

        result = convertor.convert(data)
        self.assertEqual(result.value, ["abc", "def"])

    @mock.patch("services.web.vision.handlers.convertor.api.user_manage.retrieve_department", return_value={})
    def test_convert_numeric_starts_with(self, _):
        convertor = DeptConvertor()
        data = {"op": OP.STARTS_WITH, "field": "tag.id", "value": "456"}
        result = convertor.convert(data)
        self.assertEqual(result.value, ["456"])

    @mock.patch(
        "services.web.vision.handlers.convertor.api.user_manage.retrieve_department", side_effect=APIRequestError
    )
    def test_convert_fallback_when_department_api_failed(self, _):
        convertor = DeptConvertor()
        data = {"op": OP.IN, "field": "tag.id", "value": ["20"]}
        result = convertor.convert(data)
        self.assertEqual(result.value, ["20"])

    def test_convert_raise_on_unsupported_operator(self):
        convertor = DeptConvertor()
        with self.assertRaises(VisionPermissionInvalid):
            convertor.convert({"op": OP.NOT_IN, "field": "tag.id", "value": ["1"]})

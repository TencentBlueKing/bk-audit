# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
"""
from types import SimpleNamespace

from bk_resource.base import Empty
from django.db import models

from apps.meta.models import Tag
from core.utils.data import (
    choices_to_dict,
    choices_to_items,
    choices_to_select_list,
    compare_dict_specific_keys,
    data2string,
    data_chunks,
    distinct,
    drop_dict_item_by_path,
    expand_json,
    extract_nested_value,
    generate_random_string,
    get_value_by_request,
    group_by,
    ignore_wrapper,
    modify_dict_by_path,
    ordered_dict_to_json,
    preserved_order_sort,
    replenish_params,
    trans_object_local,
    unique_id,
    value_to_label,
)
from tests.base import TestCase


class DummyChoices(models.TextChoices):
    ALPHA = "a", "Alpha"
    BETA = "b", "Beta"


class TestDataUtils(TestCase):
    def test_choices_helpers(self):
        self.assertEqual(
            choices_to_dict(DummyChoices, val="value", name="label"),
            [{"value": "a", "label": "Alpha"}, {"value": "b", "label": "Beta"}],
        )
        self.assertEqual(
            choices_to_select_list(DummyChoices),
            [{"id": "a", "name": "Alpha"}, {"id": "b", "name": "Beta"}],
        )
        self.assertEqual(choices_to_items(DummyChoices), {"a": "Alpha", "b": "Beta"})
        self.assertEqual(value_to_label(DummyChoices, "a"), "Alpha")
        self.assertEqual(value_to_label(DummyChoices, "x", default="Unknown"), "Unknown")

    def test_group_and_distinct(self):
        sample = [
            {"id": 1, "category": "risk"},
            {"id": 2, "category": "risk"},
            {"id": 3, "category": "tool"},
        ]
        grouped = group_by(sample, key=lambda row: row["category"])
        self.assertEqual(len(grouped["risk"]), 2)
        self.assertListEqual(distinct([1, 1, 2]), [1, 2])
        self.assertListEqual(distinct([{"id": 1}, {"id": 1}, {"id": 2}]), [{"id": 1}, {"id": 2}])

    def test_replenish_expand_and_chunks(self):
        data = {"key": "value"}
        replenish_params(data, {"key": "value", "extra": "data"})
        self.assertEqual(data["extra"], "data")
        expanded = expand_json({"root": {"child": 1}}, level=2)
        self.assertEqual(expanded["root/child"], 1)
        chunks = list(data_chunks([1, 2, 3, 4, 5], 2))
        self.assertEqual(chunks, [[1, 2], [3, 4], [5]])

    def test_ignore_wrapper_and_ordered_dict_to_json(self):
        @ignore_wrapper
        def raise_error():
            raise ValueError("boom")

        self.assertIsNone(raise_error())
        nested = ordered_dict_to_json({"a": [{"b": 1}]})
        self.assertEqual(nested["a"][0]["b"], 1)

    def test_trans_and_modify_drop_path(self):
        obj = {"id": 1, "token": 123}
        trans_object_local(obj, ["id", "token"])
        self.assertEqual(obj["token"], "123")

        target = {"level": {"child": 1}}
        modify_dict_by_path(target, ["level", "child"], 2)
        self.assertEqual(target["level"]["child"], 2)
        modify_dict_by_path(target, ["new", "child"], 3, auto_create=True)
        self.assertIn("new", target)
        target["new"]["placeholder"] = 0
        target = modify_dict_by_path(target, ["new", "child"], 4)
        self.assertEqual(target["new"]["child"], 4)
        drop_dict_item_by_path(target, ["new", "child"], None)
        self.assertNotIn("child", target["new"])

    def test_extract_nested_value(self):
        data = {"a": {"b": 1}}
        self.assertEqual(extract_nested_value(data, ["a", "b"]), 1)
        self.assertEqual(extract_nested_value('{"a": {"b": 2}}', ["a", "b"]), 2)
        self.assertIsInstance(extract_nested_value({}, ["a"]), Empty)

    def test_random_and_request_helpers(self):
        self.assertEqual(len(unique_id()), 32)
        token = generate_random_string(4, alphabet="ab")
        self.assertIn(token[0], "ab")

        request = SimpleNamespace(
            query_params={"key": "value"},
            data={"fallback": "data", "missing": "data"},
        )
        self.assertEqual(get_value_by_request(request, "key"), "value")
        self.assertEqual(get_value_by_request(request, "missing"), "data")
        self.assertTrue(compare_dict_specific_keys({"a": 1, "b": 2}, {"a": 1, "b": 3}, ["a"]))
        self.assertEqual(data2string(["a", "b"]), "a,b")

    def test_preserved_order_sort(self):
        Tag.objects.create(tag_name="Beta")
        Tag.objects.create(tag_name="Alpha")
        Tag.objects.create(tag_name="Gamma")
        queryset = Tag.objects.all()

        ordered = preserved_order_sort(queryset, "-tag_name", ["Gamma", "Alpha"]).values_list("tag_name", flat=True)

        self.assertEqual(list(ordered), ["Alpha", "Gamma", "Beta"])

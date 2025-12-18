# -*- coding: utf-8 -*-

import json


def format_serializer_data(serializer_data):
    return json.loads(json.dumps(serializer_data))


def assert_equal(actual, expect):
    """比较两个对象的值 ."""
    actual = format_serializer_data(actual)
    assert actual == expect


def assert_dict_contains(data: dict, expect: dict, key: str = None):
    """测试字典是否包含指定数据 ."""
    if not expect:
        try:
            assert data == expect
        except (AssertionError, AttributeError):
            print("-" * 100)
            print("key =", key, "actual =", data, "expect =", expect)
            print("-" * 100)
            raise
    for key, value in expect.items():
        if isinstance(value, dict):
            assert_dict_contains(data.get(key), value, key)
        elif isinstance(value, list):
            assert_list_contains(data.get(key), value, key)
        else:
            try:
                assert data.get(key) == value
            except (AssertionError, AttributeError):
                print("-" * 100)
                if data is None:
                    print("data = ", data, "key =", key, "expect =", value)
                else:
                    print("key =", key, "actual =", data.get(key), "expect =", value)
                print("-" * 100)
                raise


def assert_list_contains(data: list, expect: list, index: str = None):
    """测试数组是否包含指定数据 ."""
    if not expect:
        try:
            assert data == expect
        except (AssertionError, AttributeError):
            print("-" * 100)
            print("index =", index, "actual =", data, "expect =", expect)
            print("-" * 100)
            raise
    assert len(data) == len(expect)
    for index, value in enumerate(expect):
        if isinstance(value, dict):
            assert_dict_contains(data[index], value)
        elif isinstance(value, list):
            assert_list_contains(data[index], value, index)
        else:
            try:
                assert data[index] == value
            except AssertionError:
                print("-" * 100)
                print("index =", index, "actual =", data[index], "expect =", value)

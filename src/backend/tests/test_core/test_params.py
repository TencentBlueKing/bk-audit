# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
Copyright (C) 2023 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

import unittest

from core.utils.params import parse_nested_params


class TestParseNestedParams(unittest.TestCase):
    def test_simple_key(self):
        query = {"k1": "value1"}
        expected = {"k1": "value1"}
        self.assertEqual(parse_nested_params(query), expected)

    def test_single_nested_key(self):
        query = {"constants[a]": "1"}
        expected = {"constants": {"a": "1"}}
        self.assertEqual(parse_nested_params(query), expected)

    def test_multiple_nested_keys(self):
        query = {"constants[a]": "1", "constants[c][d]": "3"}
        expected = {"constants": {"a": "1", "c": {"d": "3"}}}
        self.assertEqual(parse_nested_params(query), expected)

    def test_non_dict_to_dict_conversion(self):
        # 测试场景：先存在普通键值，再传入同一键的嵌套参数
        query = {"key": "value1", "key[a]": "value2"}
        expected = {"key": {"__value__": "value1", "a": "value2"}}
        self.assertEqual(parse_nested_params(query), expected)

    def test_deeply_nested_keys(self):
        query = {"a[b][c][d]": "value"}
        expected = {"a": {"b": {"c": {"d": "value"}}}}
        self.assertEqual(parse_nested_params(query), expected)

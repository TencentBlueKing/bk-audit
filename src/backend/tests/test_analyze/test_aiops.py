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
from services.web.analyze.controls.aiops import AIOpsController
from tests.base import TestCase


class TestAiopsBuildSqlFilter(TestCase):
    def setUp(self):
        self.controller = AIOpsController

    def test_empty_filter(self):
        """测试空过滤器"""
        self.assertEqual(self.controller._build_sql_filter([]), "")

    def test_basic_equals_filter(self):
        """测试等于条件"""
        filters = [{"key": "name", "method": "=", "value": ["Alice"], "connector": "AND"}]
        expected = "where  (name = 'Alice') "
        self.assertEqual(self.controller._build_sql_filter(filters), expected)

    def test_in_operator(self):
        """测试IN条件"""
        filters = [{"key": "id", "method": "IN", "value": ["1", "2", "O'Neil"], "connector": "AND"}]
        expected = 'where  (id IN ("1","2","O\'\'Neil")) '
        self.assertEqual(self.controller._build_sql_filter(filters), expected)

    def test_empty_in_values(self):
        """测试空IN值处理"""
        # IN空列表应返回1=0
        filters = [{"key": "id", "method": "IN", "value": [], "connector": "AND"}]
        self.assertIn("where  (id IN ()) ", self.controller._build_sql_filter(filters))

    def test_number_handling(self):
        """测试数字类型处理"""
        filters = [{"key": "age", "method": ">", "value": ["18", "20"], "connector": "OR"}]  # 故意测试混合类型
        # 预期数字不加引号
        self.assertIn("where  (age > '18' or age > '20') ", self.controller._build_sql_filter(filters))

    def test_null_handling(self):
        """测试NULL判断"""
        filters = [{"key": "email", "method": "IS NULL", "value": [], "connector": "AND"}]
        expected = "where  (email IS NULL) "
        self.assertEqual(self.controller._build_sql_filter(filters), expected)

    def test_multiple_conditions(self):
        """测试多条件组合"""
        filters = [
            {"key": "status", "method": "IN", "value": ["running", "pending"], "connector": "AND"},
            {"key": "created_at", "method": ">=", "value": ["2023-01-01"], "connector": "OR"},
        ]
        expected = 'where  (status IN ("running","pending")) OR (created_at >= \'2023-01-01\') '
        self.assertEqual(self.controller._build_sql_filter(filters), expected)

    def test_special_char_escaping(self):
        """测试特殊字符转义"""
        filters = [{"key": "comment", "method": "=", "value": ["It's awesome"], "connector": "AND"}]
        expected = "where  (comment = 'It''s awesome') "
        self.assertEqual(self.controller._build_sql_filter(filters), expected)

    def test_regexp_operator(self):
        """测试REGEXP操作符"""
        filters = [{"key": "price", "method": "REGEXP", "value": ["100", "200"], "connector": "AND"}]
        expected = "where  (price REGEXP '100' or price REGEXP '200') "
        self.assertEqual(self.controller._build_sql_filter(filters), expected)

    def test_like_operator(self):
        """测试LIKE操作符"""
        filters = [{"key": "price", "method": "LIKE", "value": ["100", "200"], "connector": "AND"}]
        expected = "where  (price LIKE '100' or price LIKE '200') "
        self.assertEqual(self.controller._build_sql_filter(filters), expected)

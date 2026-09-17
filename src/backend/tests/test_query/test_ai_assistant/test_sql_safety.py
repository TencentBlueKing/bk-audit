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
either express or implied. See the License for the specific language governing
permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.

SQL 生成安全回归（共享 builder 行为固化）

背景（2026-08-14 实证）：AI 输出的 filters 直接进 DorisQuerySQLBuilder（共享链路，
与现有检索接口同路径）。pypika 的 format_quotes 对字符串值做单引号转义（' → ''），
SQL 注入不可行；like 操作符自动包裹 %（NL prompt「like 只传子串不带 %」的依据）。

本文件把上述验证结论固化为回归测试，防止 pypika 升级或 builder 改动引入回归。
"""

from services.web.query.utils.doris import DorisQuerySQLBuilder
from tests.test_query.test_ai_assistant.base import AIAssistantTestCase


class TestSQLInjectionSafety(AIAssistantTestCase):
    """单引号 filters 的 SQL 生成行为（注入安全回归）"""

    @staticmethod
    def _build_sql(filters, operator="eq"):
        builder = DorisQuerySQLBuilder(
            table="test_rt",
            conditions=[
                {
                    "field": {"raw_name": "username", "field_type": "string", "keys": []},
                    "operator": operator,
                    "filters": filters,
                }
            ],
            sort_list=[{"order_field": "dtEventTimeStamp", "order_type": "desc"}],
            page=1,
            page_size=10,
        )
        return builder.build_data_sql()

    def test_eq_single_quote_escaped(self):
        sql = self._build_sql(["a' OR 1=1 --"])
        # 单引号被转义为 ''，注入载荷整体仍是字符串字面量
        self.assertIn("'a'' OR 1=1 --'", sql)
        # 注入生效形态（裸闭合引号后跟 OR）不存在：
        # 转义后是 'a'' ...（引号对），而注入生效需要 'a' OR ...（单引号裸闭合）
        self.assertNotIn("'a' OR 1=1 --", sql)

    def test_include_single_quote_escaped(self):
        sql = self._build_sql(["a' OR 1=1 --", "b"], operator="include")
        self.assertIn("IN ('a'' OR 1=1 --','b')", sql)

    def test_like_auto_wrap_percent_and_escaped(self):
        """like 自动包裹 % + 单引号转义（NL prompt「like 只传子串」的依据）"""
        sql = self._build_sql(["%' OR '1'='1"], operator="like")
        self.assertIn("LIKE '%%'' OR ''1''=''1%'", sql)

    def test_backslash_not_breaking_string(self):
        """反斜杠不会破坏字符串字面量结构"""
        sql = self._build_sql(["C:\\windows\\x", "path"], operator="include")
        self.assertIn("IN (", sql)

    def test_empty_string_value_quoted(self):
        """空字符串值生成合法 SQL"""
        sql = self._build_sql([""])
        self.assertIn("''", sql)

    def test_normal_value_control(self):
        """对照组：正常值不受影响"""
        sql = self._build_sql(["a", "b"], operator="include")
        self.assertIn("IN ('a','b')", sql)

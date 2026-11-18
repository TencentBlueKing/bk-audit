"""验证 JSONPath 原始键语义及 BKBase 转译边界的字符串约束。"""

import sqlite3

from django.test import SimpleTestCase
from sqlglot import exp, parse_one

from core.sql.builder.terms import DorisField, DorisJsonTypeExtractFunction


class DorisJsonPathTest(SimpleTestCase):
    """路径含单引号时不能让平台重写字符串字面量破坏 SQL。"""

    def test_quote_keys_preserve_path_without_quotes_in_sql_literals(self):
        cases = [
            (["a'b"], '$."a\'b"'),
            (["中文'key-(1)"], '$."中文\'key-(1)"'),
            (["'a''b'", "child'key"], '$."\'a\'\'b\'"."child\'key"'),
            (["x'];SELECT1;--"], '$."x\'];SELECT1;--"'),
        ]
        with sqlite3.connect(":memory:") as db:
            db.create_function("CONCAT", -1, lambda *parts: "".join(parts))
            for keys, expected in cases:
                with self.subTest(keys=keys):
                    term = DorisJsonTypeExtractFunction(DorisField("extend_data"), keys)
                    path_sql = term.args[1].get_sql()
                    expression = parse_one(f"SELECT {path_sql}", read="doris")
                    # 当前 BKBase 重写会丢失字符串内部的单引号转义；原键须在表达式中构造。
                    self.assertTrue(all("'" not in item.this for item in expression.find_all(exp.Literal)))
                    self.assertEqual(db.execute(f"SELECT {path_sql}").fetchone()[0], expected)

    def test_ordinary_paths_remain_literals(self):
        for keys, expected in [(["plain", "中文"], "'$.plain.中文'"), (["bracket[key]"], "'$.\"bracket[key]\"'")]:
            with self.subTest(keys=keys):
                term = DorisJsonTypeExtractFunction(DorisField("extend_data"), keys)
                self.assertEqual(term.args[1].get_sql(), expected)

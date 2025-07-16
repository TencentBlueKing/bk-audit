from django.test import TestCase

from core.sql.exceptions import SQLParseError
from core.sql.parser.model import ParsedSQLInfo, RangeVariableData
from core.sql.parser.praser import SqlQueryAnalysis


class TestSqlQueryAnalysis(TestCase):
    """测试 SQL 解析和分析功能（无 SELECT *）"""

    def test_parse_simple_select(self):
        sql = "SELECT id, name FROM users WHERE age > :min_age"
        analyzer = SqlQueryAnalysis(sql)
        analyzer.parse_sql()

        result = analyzer.get_parsed_def()
        assert isinstance(result, ParsedSQLInfo)
        assert result.original_sql == sql
        assert {t.table_name for t in result.referenced_tables} == {"users"}
        assert {v.raw_name for v in result.sql_variables} == {"min_age"}
        assert {f.display_name for f in result.result_fields} == {"id", "name"}

    def test_parse_complex_query(self):
        sql = """
              WITH sales AS (SELECT user_id, SUM(amount) AS total
                             FROM orders
                             WHERE date > :start_date
              GROUP BY user_id
                  )
              SELECT u.id, u.name, s.total
              FROM users u
                       JOIN sales s ON u.id = s.user_id
              WHERE u.status = @status
              """
        analyzer = SqlQueryAnalysis(sql)
        analyzer.parse_sql()

        result = analyzer.get_parsed_def()
        assert {t.table_name for t in result.referenced_tables} == {"orders", "users"}
        assert {v.raw_name for v in result.sql_variables} == {"start_date", "status"}
        assert {f.display_name for f in result.result_fields} == {"id", "name", "total"}

    def test_generate_sql_with_values(self):
        sql = "SELECT id, name, price " "FROM products " "WHERE category = :cat AND price > :min_price"
        analyzer = SqlQueryAnalysis(sql)

        params = {"cat": "electronics", "min_price": 1000}
        generated = analyzer.generate_sql_with_values(params)["data"]

        assert "category = 'electronics'" in generated
        assert "price > 1000" in generated

    def test_parse_empty_sql(self):
        analyzer = SqlQueryAnalysis("")
        analyzer.parse_sql()
        result = analyzer.get_parsed_def()
        assert not result.referenced_tables and not result.sql_variables and not result.result_fields

    def test_parse_invalid_sql(self):
        analyzer = SqlQueryAnalysis("SELECT FROM WHERE")
        with self.assertRaises(SQLParseError):
            analyzer.parse_sql()

    def test_anonymous_variables(self):
        sql = "SELECT id FROM users WHERE id = ?"
        analyzer = SqlQueryAnalysis(sql)
        with self.assertRaises(SQLParseError):
            analyzer.parse_sql()

    def test_regenerate_sql_from_ast(self):
        sql = "SELECT id, name FROM users"
        analyzer = SqlQueryAnalysis(sql)
        regenerated = analyzer.generate_sql_with_values({}, sql)["data"]
        assert "SELECT id, name FROM users" in regenerated

    def test_external_template_generation(self):
        analyzer = SqlQueryAnalysis("SELECT 1")  # 原始 SQL 无关紧要
        template = "SELECT id, total FROM orders WHERE id = :order_id"
        generated = analyzer.generate_sql_with_values({"order_id": 123}, sql_template=template)["data"]
        assert "SELECT id, total FROM orders WHERE id = 123" in generated

    def test_parse_select_with_aliases(self):
        sql = "SELECT u.id AS user_id, u.name AS user_name FROM users u"
        analyzer = SqlQueryAnalysis(sql)
        analyzer.parse_sql()
        names = {f.display_name for f in analyzer.get_parsed_def().result_fields}
        assert names == {"user_id", "user_name"}

    def test_parse_union_query(self):
        sql = "SELECT id FROM users UNION SELECT id FROM customers"
        analyzer = SqlQueryAnalysis(sql)
        with self.assertRaises(SQLParseError):
            analyzer.parse_sql()

    def test_generate_sql_with_pagination_and_count(self):
        sql = "SELECT id, price FROM products WHERE category = :cat"
        analyzer = SqlQueryAnalysis(sql)
        generated = analyzer.generate_sql_with_values({"cat": "electronics"}, limit=10, offset=5, with_count=True)
        assert generated["data"].endswith("LIMIT 10 OFFSET 5")
        assert "COUNT(*)" in generated["count"]

    def test_regenerate_sql_with_storage(self):
        sql = "SELECT id, name FROM users.hdfs"
        analyzer = SqlQueryAnalysis(sql)
        regenerated = analyzer.generate_sql_with_values({}, sql)["data"]
        assert "SELECT id, name FROM users.hdfs" in regenerated

    def test_parse_and_regenerate_with_storage(self):
        sql = "SELECT id, name FROM users.hdfs WHERE age > 18"
        analyzer = SqlQueryAnalysis(sql)
        analyzer.parse_sql()

        result = analyzer.get_parsed_def()
        assert result.referenced_tables[0].storage == "hdfs"

        regenerated = analyzer.generate_sql_with_values({}, sql)["data"]
        assert "users.hdfs WHERE age > 18" in regenerated

    def test_generate_sql_with_range_dict(self):
        sql = "SELECT id FROM sales WHERE amount = :a"
        analyzer = SqlQueryAnalysis(sql)

        params = {"a": RangeVariableData(start=1, end=100)}
        generated = analyzer.generate_sql_with_values(params)["data"]
        assert "amount BETWEEN 1 AND 100" in generated

    def test_generate_sql_with_range_dict_and_extra_conditions(self):
        sql = "SELECT id FROM sales WHERE amount = :a AND status = :s"
        analyzer = SqlQueryAnalysis(sql)

        params = {
            "a": RangeVariableData(start=10, end=20),
            "s": "PAID",
        }
        data_sql = analyzer.generate_sql_with_values(params)["data"]
        assert "BETWEEN 10 AND 20" in data_sql and "status = 'PAID'" in data_sql

    def test_generate_sql_tuple_not_converted(self):
        sql = "SELECT id FROM sales WHERE amount = :a"
        analyzer = SqlQueryAnalysis(sql)

        params = {"a": [1, 10]}  # 非 range
        data_sql = analyzer.generate_sql_with_values(params)["data"]
        assert "amount = (" in data_sql and "BETWEEN" not in data_sql

    def test_parse_select_and_where_with_functions(self):
        sql = "SELECT UPPER(u.name) AS name, COUNT(*) AS cnt " "FROM users u WHERE LOWER(u.status) = :status"
        analyzer = SqlQueryAnalysis(sql)
        analyzer.parse_sql()

        result = analyzer.get_parsed_def()
        assert {v.raw_name for v in result.sql_variables} == {"status"}
        assert {f.display_name for f in result.result_fields} == {"name", "cnt"}

        data_sql = analyzer.generate_sql_with_values({"status": "active"})["data"]
        assert "LOWER(u.status) = 'active'" in data_sql
        assert "UPPER(u.name)" in data_sql and "COUNT(*)" in data_sql

        # 缺少别名应触发解析异常
        with self.assertRaises(SQLParseError):
            SqlQueryAnalysis(
                "SELECT UPPER(u.name), COUNT(*) AS cnt FROM users u WHERE LOWER(u.status) = :status"
            ).parse_sql()

    def test_parse_bracket_field_access(self):
        sql = "SELECT e.data['field'] AS field_val " "FROM events e WHERE e.data['status'] = :st"
        analyzer = SqlQueryAnalysis(sql)
        analyzer.parse_sql()

        result = analyzer.get_parsed_def()
        assert {t.table_name for t in result.referenced_tables} == {"events"}
        assert {v.raw_name for v in result.sql_variables} == {"st"}
        assert [f.display_name for f in result.result_fields] == ["field_val"]

        data_sql = analyzer.generate_sql_with_values({"st": "OK"})["data"]
        assert "e.data['status'] = 'OK'" in data_sql
        assert "e.data['field'] AS field_val" in data_sql

    def test_parse_select_star_should_fail(self):
        """
        使用 SELECT * 时应抛出 SQLParseError（已在解析器中禁止通配符）
        """
        sql = "SELECT * FROM users WHERE age > 18"
        analyzer = SqlQueryAnalysis(sql)
        with self.assertRaises(SQLParseError):
            analyzer.parse_sql()

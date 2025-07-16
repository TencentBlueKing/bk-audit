from django.test import TestCase

from core.sql.exceptions import SQLParseError
from core.sql.parser.model import ParsedSQLInfo, RangeVariableData
from core.sql.parser.praser import SqlQueryAnalysis


class TestSqlQueryAnalysis(TestCase):
    """测试SQL解析和分析功能"""

    def test_parse_simple_select(self):
        """测试解析简单SELECT语句"""
        sql = "SELECT id, name FROM users WHERE age > :min_age"
        analyzer = SqlQueryAnalysis(sql)
        analyzer.parse_sql()

        # 验证解析结果
        result = analyzer.get_parsed_def()
        assert isinstance(result, ParsedSQLInfo)
        assert result.original_sql == sql
        assert len(result.referenced_tables) == 1
        assert result.referenced_tables[0].table_name == "users"
        assert len(result.sql_variables) == 1
        assert result.sql_variables[0].raw_name == "min_age"
        assert len(result.result_fields) == 2
        assert {f.display_name for f in result.result_fields} == {"id", "name"}

    def test_parse_complex_query(self):
        """测试解析复杂查询"""
        sql = """
              WITH sales AS (SELECT user_id, SUM(amount) as total \
                             FROM orders \
                             WHERE date > :start_date
              GROUP BY user_id
                  )
              SELECT u.id, u.name, s.total
              FROM users u
                       JOIN sales s ON u.id = s.user_id
              WHERE u.status = @status \
              """
        analyzer = SqlQueryAnalysis(sql)
        analyzer.parse_sql()

        result = analyzer.get_parsed_def()
        assert len(result.referenced_tables) == 2
        assert {t.table_name for t in result.referenced_tables} == {"orders", "users"}
        assert len(result.sql_variables) == 2
        assert {v.raw_name for v in result.sql_variables} == {"start_date", "status"}
        assert len(result.result_fields) == 3
        assert {f.display_name for f in result.result_fields} == {"id", "name", "total"}

    def test_generate_sql_with_values(self):
        """测试参数替换生成SQL"""
        sql = "SELECT * FROM products WHERE category = :cat AND price > :min_price"
        analyzer = SqlQueryAnalysis(sql)

        params = {"cat": "electronics", "min_price": 1000}
        generated_sql = analyzer.generate_sql_with_values(params)

        assert "category = 'electronics'" in generated_sql["data"]
        assert "price > 1000" in generated_sql["data"]

    def test_parse_empty_sql(self):
        """测试解析空SQL"""
        analyzer = SqlQueryAnalysis("")
        analyzer.parse_sql()

        result = analyzer.get_parsed_def()
        assert not result.referenced_tables
        assert not result.sql_variables
        assert not result.result_fields

    def test_parse_invalid_sql(self):
        """测试解析无效SQL"""
        analyzer = SqlQueryAnalysis("SELECT FROM WHERE")
        with self.assertRaises(SQLParseError):
            analyzer.parse_sql()

    def test_anonymous_variables(self):
        """测试匿名变量"""
        sql = "SELECT * FROM users WHERE id = ?"
        analyzer = SqlQueryAnalysis(sql)
        with self.assertRaises(SQLParseError):
            analyzer.parse_sql()

    def test_regenerate_sql_from_ast(self):
        """测试从AST重新生成SQL"""
        sql = "SELECT id, name FROM users"
        analyzer = SqlQueryAnalysis(sql)
        def_ = analyzer.get_parsed_def()

        regenerated = analyzer.generate_sql_with_values({}, def_.original_sql)
        assert "SELECT id, name FROM users" in regenerated["data"]

    def test_external_template_generation(self):
        """测试使用外部模板生成SQL"""
        analyzer = SqlQueryAnalysis("SELECT 1")
        template = "SELECT * FROM orders WHERE id = :order_id"
        params = {"order_id": 123}

        generated = analyzer.generate_sql_with_values(params, sql_template=template)["data"]
        assert "SELECT * FROM orders WHERE id = 123" in generated

    def test_parse_select_with_aliases(self):
        """测试解析带别名的SELECT"""
        sql = "SELECT u.id as user_id, u.name as user_name FROM users u"
        analyzer = SqlQueryAnalysis(sql)
        analyzer.parse_sql()

        result = analyzer.get_parsed_def()
        assert len(result.result_fields) == 2
        assert {f.display_name for f in result.result_fields} == {"user_id", "user_name"}
        assert all(f.raw_name == "id" or f.raw_name == "name" for f in result.result_fields)

    def test_parse_union_query(self):
        """测试解析UNION查询"""
        sql = "SELECT id FROM users UNION SELECT id FROM customers"
        analyzer = SqlQueryAnalysis(sql)
        with self.assertRaises(SQLParseError):
            analyzer.parse_sql()

    def test_generate_sql_with_pagination_and_count(self):
        """测试分页和统计SQL生成功能"""
        sql = "SELECT * FROM products WHERE category = :cat"
        analyzer = SqlQueryAnalysis(sql)

        params = {"cat": "electronics"}
        generated = analyzer.generate_sql_with_values(params, limit=10, offset=5, with_count=True)

        assert isinstance(generated, dict)
        assert generated["data"].endswith("LIMIT 10 OFFSET 5")
        assert "COUNT(*)" in generated["count"]

    def test_regenerate_sql_with_storage(self):
        """测试带存储标识的表名重新生成"""
        sql = "SELECT id, name FROM users.hdfs"
        analyzer = SqlQueryAnalysis(sql)
        def_ = analyzer.get_parsed_def()

        regenerated = analyzer.generate_sql_with_values({}, def_.original_sql)
        assert "SELECT id, name FROM users.hdfs" in regenerated["data"]

    def test_parse_and_regenerate_with_storage(self):
        """测试带存储标识的表名完整解析和重新生成流程"""
        sql = "SELECT id, name FROM users.hdfs WHERE age > 18"
        analyzer = SqlQueryAnalysis(sql)
        analyzer.parse_sql()

        # 验证解析结果
        result = analyzer.get_parsed_def()
        assert len(result.referenced_tables) == 1
        assert result.referenced_tables[0].table_name == "users"
        assert result.referenced_tables[0].storage == "hdfs"

        # 验证重新生成
        regenerated = analyzer.generate_sql_with_values({}, result.original_sql)
        assert "SELECT id, name FROM users.hdfs WHERE age > 18" in regenerated["data"]

    def test_generate_sql_with_range_dict(self):
        """
        `{"type": "range", "start": x, "end": y}` 应自动改写为 BETWEEN
        """
        sql = "SELECT * FROM sales WHERE amount = :a"
        analyzer = SqlQueryAnalysis(sql)

        params = {"a": RangeVariableData(start=1, end=100)}
        generated = analyzer.generate_sql_with_values(params)

        assert "amount BETWEEN 1 AND 100" in generated["data"]

    def test_generate_sql_with_range_dict_and_extra_conditions(self):
        """
        区间改写应与其他条件共存
        """
        sql = "SELECT * FROM sales WHERE amount = :a AND status = :s"
        analyzer = SqlQueryAnalysis(sql)

        params = {
            "a": RangeVariableData(start=10, end=20),
            "s": "PAID",
        }
        generated = analyzer.generate_sql_with_values(params)

        data_sql = generated["data"]
        assert "amount BETWEEN 10 AND 20" in data_sql
        assert "status = 'PAID'" in data_sql

    def test_generate_sql_tuple_not_converted(self):
        """
        普通 2 元 tuple/list 不应被误判为 BETWEEN
        """
        sql = "SELECT * FROM sales WHERE amount = :a"
        analyzer = SqlQueryAnalysis(sql)

        params = {"a": [1, 10]}  # 无 'type': 'range' 标签
        generated = analyzer.generate_sql_with_values(params)

        # sqlglot 默认会保留空格，“(1, 100)” 或 “(1,100)” 都算通过
        assert "amount = (" in generated["data"]
        assert "BETWEEN" not in generated["data"]

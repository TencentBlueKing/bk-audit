from tests.base import TestCase


class TestSqlAnalyseResource(TestCase):
    def test_basic_sql_parse(self):
        sql = "SELECT id, name FROM users WHERE id = :uid"
        resp = self.resource.tool.sql_analyse(sql=sql)
        assert resp["original_sql"] == sql
        assert resp["referenced_tables"][0]["table_name"] == "users"
        assert resp["sql_variables"][0]["raw_name"] == "uid"
        assert {f["display_name"] for f in resp["result_fields"]} == {"id", "name"}

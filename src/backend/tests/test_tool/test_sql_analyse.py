from unittest import mock

from api.bk_base.default import UserAuthBatchCheck
from tests.base import TestCase


class TestSqlAnalyseResource(TestCase):
    def setUp(self):
        self.patcher_auth = mock.patch.object(
            UserAuthBatchCheck,
            "perform_request",
            return_value=[
                {"result": True, "user_id": "test_user", "object_id": "users"},
            ],
        )
        self.mock_auth_api = self.patcher_auth.start()

    def tearDown(self):
        mock.patch.stopall()

    def test_basic_sql_parse(self):
        sql = "SELECT id, name FROM users WHERE id = :uid"
        resp = self.resource.tool.sql_analyse(sql=sql, with_permission=True)
        assert resp["original_sql"] == sql
        assert resp["referenced_tables"][0]["table_name"] == "users"
        assert resp["referenced_tables"][0]["permission"]
        assert resp["sql_variables"][0]["raw_name"] == "uid"
        assert {f["display_name"] for f in resp["result_fields"]} == {"id", "name"}

from unittest import mock

from api.bk_base.default import UserAuthBatchCheck
from services.web.scene.data_filter import SceneDataFilter
from services.web.tool.exceptions import DataSearchTablePermission
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

    def test_scene_table_permission_all_authorized(self):
        """传入 scene_id 时，表在场景授权范围内，校验通过"""
        sql = "SELECT id FROM users"
        with mock.patch.object(SceneDataFilter, 'get_table_ids', return_value=['users']):
            resp = self.resource.tool.sql_analyse(sql=sql, scene_id=1, with_permission=False)
        assert resp["referenced_tables"][0]["table_name"] == "users"

    def test_scene_table_permission_not_authorized_but_user_has_permission(self):
        """传入 scene_id 时，表不在场景授权范围内，但用户个人有权限，校验通过"""
        sql = "SELECT id FROM users"
        with mock.patch.object(SceneDataFilter, 'get_table_ids', return_value=[]):
            with mock.patch.object(
                UserAuthBatchCheck,
                "perform_request",
                return_value=[{"result": True, "user_id": "test_user", "object_id": "users"}],
            ):
                resp = self.resource.tool.sql_analyse(sql=sql, scene_id=1, with_permission=False)
        assert resp["referenced_tables"][0]["table_name"] == "users"

    def test_scene_table_permission_not_authorized_and_user_denied(self):
        """传入 scene_id 时，表不在场景授权范围内且用户个人无权限，抛出异常"""
        sql = "SELECT id FROM users"
        with mock.patch.object(SceneDataFilter, 'get_table_ids', return_value=[]):
            with mock.patch.object(
                UserAuthBatchCheck,
                "perform_request",
                return_value=[{"result": False, "user_id": "test_user", "object_id": "users"}],
            ):
                with self.assertRaises(DataSearchTablePermission):
                    self.resource.tool.sql_analyse(sql=sql, scene_id=1, with_permission=False)

    def test_no_scene_id_skips_scene_table_permission(self):
        """不传 scene_id 时，不触发场景表权限校验"""
        sql = "SELECT id FROM users"
        with mock.patch.object(SceneDataFilter, 'get_table_ids') as mock_get_table_ids:
            self.resource.tool.sql_analyse(sql=sql, with_permission=False)
            mock_get_table_ids.assert_not_called()

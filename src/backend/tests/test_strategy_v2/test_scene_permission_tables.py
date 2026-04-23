from unittest.mock import patch

from django.test import TestCase

from services.web.scene.data_filter import SceneDataFilter
from services.web.scene.resources import GetScenePermissionTables


class TestGetScenePermissionTables(TestCase):
    """测试 GetScenePermissionTables 资源类"""

    def setUp(self):
        self.resource = GetScenePermissionTables()

    @patch.object(SceneDataFilter, 'get_table_ids')
    def test_perform_request_with_tables(self, mock_get_table_ids):
        """测试场景配置了数据表的情况"""
        mock_get_table_ids.return_value = ['table1', 'table2']

        result = self.resource.perform_request({'scene_id': 1})

        self.assertEqual(
            result,
            [
                {'table_id': 'table1'},
                {'table_id': 'table2'},
            ],
        )
        mock_get_table_ids.assert_called_once_with(1)

    @patch.object(SceneDataFilter, 'get_table_ids')
    def test_perform_request_no_tables(self, mock_get_table_ids):
        """测试场景没有配置数据表的情况，应返回空列表"""
        mock_get_table_ids.return_value = []

        result = self.resource.perform_request({'scene_id': 1})

        self.assertEqual(result, [])
        mock_get_table_ids.assert_called_once_with(1)

    def test_request_serializer_validation(self):
        """测试请求序列化器验证"""
        # 正常参数
        serializer = self.resource.RequestSerializer(data={'scene_id': 1})
        self.assertTrue(serializer.is_valid())

        # 缺少必填字段
        serializer = self.resource.RequestSerializer(data={})
        self.assertFalse(serializer.is_valid())
        self.assertIn('scene_id', serializer.errors)

    def test_response_serializer_structure(self):
        """测试响应序列化器结构"""
        serializer = self.resource.ResponseSerializer(data={'table_id': 'test_table'})
        self.assertTrue(serializer.is_valid())

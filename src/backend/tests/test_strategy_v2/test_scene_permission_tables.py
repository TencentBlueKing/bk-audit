from unittest.mock import patch

from django.test import TestCase

from services.web.scene.data_filter import SceneDataFilter
from services.web.strategy_v2.resources import GetScenePermissionTables
from services.web.strategy_v2.utils.table import BizRtTableHandler, BuildInTableHandler


class TestGetScenePermissionTables(TestCase):
    """测试 GetScenePermissionTables 资源类"""

    def setUp(self):
        self.resource = GetScenePermissionTables()

    @patch.object(SceneDataFilter, 'get_table_ids')
    @patch.object(BuildInTableHandler, 'list_tables')
    @patch.object(BizRtTableHandler, 'list_tables')
    def test_perform_request_with_tables(self, mock_bizrt_list_tables, mock_buildin_list_tables, mock_get_table_ids):
        """测试场景配置了数据表的情况"""
        mock_get_table_ids.return_value = ['table1', 'table2']
        # Mock BuildInTableHandler.list_tables() 返回包含 table1 的表结构
        mock_buildin_list_tables.return_value = [
            {
                'label': '分组1',
                'value': 'group1',
                'children': [{'value': 'table1', 'label': '表1'}, {'value': 'table3', 'label': '表3'}],
            }
        ]
        # Mock BizRtTableHandler.list_tables() 返回包含 table2 的表结构
        mock_bizrt_list_tables.return_value = [
            {
                'label': '分组2',
                'value': 'group2',
                'children': [{'value': 'table2', 'label': '表2'}, {'value': 'table4', 'label': '表4'}],
            }
        ]

        result = self.resource.perform_request({'scene_id': 1})

        # 返回分组结构，每个分组包含children列表
        self.assertEqual(len(result), 2)
        # 提取所有子表中的table_id
        table_ids = set()
        for group in result:
            for child in group.get('children', []):
                table_ids.add(child.get('value'))
        self.assertEqual(table_ids, {'table1', 'table2'})
        mock_get_table_ids.assert_called_once_with(1)

    @patch.object(SceneDataFilter, 'get_table_ids')
    @patch.object(BuildInTableHandler, 'list_tables')
    @patch.object(BizRtTableHandler, 'list_tables')
    def test_perform_request_no_tables(self, mock_bizrt_list_tables, mock_buildin_list_tables, mock_get_table_ids):
        """测试场景没有配置数据表时，返回空列表"""
        mock_get_table_ids.return_value = []
        mock_buildin_list_tables.return_value = []
        mock_bizrt_list_tables.return_value = []

        result = self.resource.perform_request({'scene_id': 1})

        # 白名单为空，返回空列表
        self.assertEqual(result, [])
        mock_get_table_ids.assert_called_once_with(1)

    def test_request_serializer_validation(self):
        """测试请求序列化器验证"""
        # 正常参数
        serializer = self.resource.RequestSerializer(data={'scene_id': 1})
        self.assertTrue(serializer.is_valid())

        # 缺少必填字段 scene_id
        serializer = self.resource.RequestSerializer(data={})
        self.assertFalse(serializer.is_valid())
        self.assertIn('scene_id', serializer.errors)

    def test_response_serializer_structure(self):
        """测试响应序列化器结构：many_response_data=True 表示返回列表数据"""
        # 验证资源类的基本属性配置正确
        self.assertTrue(self.resource.many_response_data)

        # 验证 ResponseSerializer 能正确序列化数据
        response_serializer = self.resource.ResponseSerializer(
            data={'label': '测试分组', 'value': 'test_group', 'children': [{'table_id': 'test_table'}]}
        )
        self.assertTrue(response_serializer.is_valid())

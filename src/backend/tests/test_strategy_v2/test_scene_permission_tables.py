from unittest.mock import patch

from django.test import TestCase

from services.web.scene.data_filter import SceneDataFilter
from services.web.strategy_v2.constants import ListTableType
from services.web.strategy_v2.resources import GetScenePermissionTables
from services.web.strategy_v2.utils.table import (
    BizRtTableHandler,
    BuildInTableHandler,
    MineBizRtTableHandler,
)


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

        result = self.resource.perform_request({'scene_id': 1, 'table_type': ListTableType.BUILD_ID_ASSET})

        # 当前接口按单一 table_type 返回对应分组结构
        self.assertEqual(
            result,
            [
                {
                    'label': '分组1',
                    'value': 'group1',
                    'children': [{'value': 'table1', 'label': '表1'}],
                }
            ],
        )
        mock_get_table_ids.assert_called_once_with(1)
        mock_buildin_list_tables.assert_called_once()
        mock_bizrt_list_tables.assert_not_called()

    @patch.object(SceneDataFilter, 'get_table_ids')
    @patch.object(MineBizRtTableHandler, 'list_tables')
    def test_perform_request_mine_biz_rt_tables(self, mock_minebizrt_list_tables, mock_get_table_ids):
        """测试 MINE_BIZ_RT 类型的数据表"""
        mock_get_table_ids.return_value = ['table5', 'table6']
        # Mock MineBizRtTableHandler.list_tables() 返回包含业务和结果表的树形结构
        mock_minebizrt_list_tables.return_value = [
            {
                'label': '业务A(11)',
                'value': '11',
                'children': [{'value': 'table5', 'label': '表5'}, {'value': 'table7', 'label': '表7'}],
            },
            {
                'label': '业务B(47)',
                'value': '47',
                'children': [{'value': 'table6', 'label': '表6'}, {'value': 'table8', 'label': '表8'}],
            },
        ]

        result = self.resource.perform_request({'scene_id': 1, 'table_type': ListTableType.MINE_BIZ_RT})

        # 验证返回过滤后的业务和结果表结构
        self.assertEqual(
            result,
            [
                {
                    'label': '业务A(11)',
                    'value': '11',
                    'children': [{'value': 'table5', 'label': '表5'}],
                },
                {
                    'label': '业务B(47)',
                    'value': '47',
                    'children': [{'value': 'table6', 'label': '表6'}],
                },
            ],
        )
        mock_get_table_ids.assert_called_once_with(1)
        mock_minebizrt_list_tables.assert_called_once()

    @patch.object(SceneDataFilter, 'get_table_ids')
    @patch.object(BuildInTableHandler, 'list_tables')
    @patch.object(BizRtTableHandler, 'list_tables')
    def test_perform_request_no_tables(self, mock_bizrt_list_tables, mock_buildin_list_tables, mock_get_table_ids):
        """测试场景没有配置数据表时，返回空列表"""
        mock_get_table_ids.return_value = []
        mock_buildin_list_tables.return_value = []
        mock_bizrt_list_tables.return_value = []

        result = self.resource.perform_request({'scene_id': 1, 'table_type': ListTableType.BUILD_ID_ASSET})

        # 白名单为空，返回空列表
        self.assertEqual(result, [])
        mock_get_table_ids.assert_called_once_with(1)
        mock_buildin_list_tables.assert_not_called()
        mock_bizrt_list_tables.assert_not_called()

    def test_request_serializer_validation(self):
        """测试请求序列化器验证"""
        # 正常参数
        serializer = self.resource.RequestSerializer(data={'scene_id': 1, 'table_type': ListTableType.BUILD_ID_ASSET})
        self.assertTrue(serializer.is_valid())

        serializer = self.resource.RequestSerializer(data={'scene_id': 1, 'table_type': ListTableType.BIZ_RT})
        self.assertTrue(serializer.is_valid())

        serializer = self.resource.RequestSerializer(data={'scene_id': 1, 'table_type': ListTableType.MINE_BIZ_RT})
        self.assertTrue(serializer.is_valid())

        serializer = self.resource.RequestSerializer(data={'scene_id': 1, 'table_type': ListTableType.EVENT_LOG})
        self.assertFalse(serializer.is_valid())
        self.assertIn('table_type', serializer.errors)

        # 缺少必填字段 scene_id / table_type
        serializer = self.resource.RequestSerializer(data={})
        self.assertFalse(serializer.is_valid())
        self.assertIn('scene_id', serializer.errors)
        self.assertIn('table_type', serializer.errors)

    def test_response_serializer_structure(self):
        """测试响应序列化器结构：many_response_data=True 表示返回列表数据"""
        # 验证资源类的基本属性配置正确
        self.assertTrue(self.resource.many_response_data)

        # 验证 ResponseSerializer 能正确序列化数据
        response_serializer = self.resource.ResponseSerializer(
            data={'label': '测试分组', 'value': 'test_group', 'children': [{'table_id': 'test_table'}]}
        )
        self.assertTrue(response_serializer.is_valid())

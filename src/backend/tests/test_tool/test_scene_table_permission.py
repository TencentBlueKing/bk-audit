from unittest.mock import MagicMock, patch

from django.test import TestCase

from core.sql.parser.models import ParsedSqlDefinition, ReferencedTable
from services.web.scene.filters import SceneDataFilter
from services.web.tool.executor.tool import SqlDataSearchExecutor


class TestSceneTablePermissionValidation(TestCase):
    """测试场景表权限校验功能"""

    def setUp(self):
        # 创建模拟的配置和工具对象
        self.mock_config = MagicMock()
        self.mock_tool = MagicMock()
        self.mock_tool.get_permission_owner.return_value = 'test_user'

        # 创建执行器实例
        self.executor = SqlDataSearchExecutor(config=self.mock_config, tool=self.mock_tool)

        # 创建模拟的SQL分析器
        self.mock_analyzer = MagicMock()
        self.executor.analyzer = self.mock_analyzer

    @patch.object(SceneDataFilter, 'get_table_ids')
    @patch.object(SceneDataFilter, 'get_system_ids')
    def test_scene_table_permission_with_table_whitelist_valid(self, mock_get_system_ids, mock_get_table_ids):
        """测试场景表白名单校验通过的情况"""
        # 模拟场景配置了数据表白名单
        mock_get_table_ids.return_value = ['table1', 'table2']
        mock_get_system_ids.return_value = []

        # 模拟SQL解析结果
        mock_table1 = ReferencedTable(table_name='table1', system_id='system1')
        mock_table2 = ReferencedTable(table_name='table2', system_id='system2')
        mock_parsed_def = ParsedSqlDefinition(referenced_tables=[mock_table1, mock_table2])
        self.mock_analyzer.get_parsed_def.return_value = mock_parsed_def

        # 模拟BK-Base权限校验通过
        with patch('api.bk_base.user_auth_batch_check') as mock_auth_check:
            mock_auth_check.return_value = [
                {'user_id': 'test_user', 'object_id': 'table1', 'result': True},
                {'user_id': 'test_user', 'object_id': 'table2', 'result': True},
            ]

            # 执行权限校验（应不抛出异常）
            params = MagicMock()
            params.scene_id = 1
            params.tool_variables = []

            self.executor.validate_permission(params)

            # 验证场景权限校验被调用
            mock_get_table_ids.assert_called_once_with(1)
            mock_get_system_ids.assert_not_called()

    @patch.object(SceneDataFilter, 'get_table_ids')
    @patch.object(SceneDataFilter, 'get_system_ids')
    def test_scene_table_permission_with_table_whitelist_denied(self, mock_get_system_ids, mock_get_table_ids):
        """测试场景表白名单校验不通过的情况"""
        # 模拟场景配置了数据表白名单
        mock_get_table_ids.return_value = ['table1']  # 只授权了table1
        mock_get_system_ids.return_value = []

        # 模拟SQL解析结果（引用了未授权的表）
        mock_table1 = ReferencedTable(table_name='table1', system_id='system1')
        mock_table2 = ReferencedTable(table_name='table2', system_id='system2')  # 未授权的表
        mock_parsed_def = ParsedSqlDefinition(referenced_tables=[mock_table1, mock_table2])
        self.mock_analyzer.get_parsed_def.return_value = mock_parsed_def

        # 执行权限校验（应返回False）
        params = MagicMock()
        params.scene_id = 1
        params.tool_variables = []

        # 验证权限校验返回False
        result = self.executor.validate_permission(params)
        self.assertFalse(result)
        mock_get_table_ids.assert_called_once_with(1)
        mock_get_system_ids.assert_not_called()

    @patch.object(SceneDataFilter, 'get_table_ids')
    @patch.object(SceneDataFilter, 'get_system_ids')
    def test_scene_table_permission_with_system_whitelist_valid(self, mock_get_system_ids, mock_get_table_ids):
        """测试场景系统白名单校验通过的情况"""
        # 模拟场景配置了系统白名单
        mock_get_table_ids.return_value = []
        mock_get_system_ids.return_value = ['system1', 'system2']

        # 模拟SQL解析结果
        mock_table1 = ReferencedTable(table_name='table1', system_id='system1')
        mock_table2 = ReferencedTable(table_name='table2', system_id='system2')
        mock_parsed_def = ParsedSqlDefinition(referenced_tables=[mock_table1, mock_table2])
        self.mock_analyzer.get_parsed_def.return_value = mock_parsed_def

        # 模拟BK-Base权限校验通过
        with patch('api.bk_base.user_auth_batch_check') as mock_auth_check:
            mock_auth_check.return_value = [
                {'user_id': 'test_user', 'object_id': 'table1', 'result': True},
                {'user_id': 'test_user', 'object_id': 'table2', 'result': True},
            ]

            # 执行权限校验
            params = MagicMock()
            params.scene_id = 1
            params.tool_variables = []

            self.executor.validate_permission(params)

            # 验证系统权限校验被调用
            mock_get_table_ids.assert_called_once_with(1)
            mock_get_system_ids.assert_called_once_with(1)

    @patch.object(SceneDataFilter, 'get_table_ids')
    @patch.object(SceneDataFilter, 'get_system_ids')
    def test_scene_table_permission_with_system_whitelist_denied(self, mock_get_system_ids, mock_get_table_ids):
        """测试场景系统白名单校验不通过的情况"""
        # 模拟场景配置了系统白名单
        mock_get_table_ids.return_value = []
        mock_get_system_ids.return_value = ['system1']  # 只授权了system1

        # 模拟SQL解析结果（引用了未授权系统的表）
        mock_table1 = ReferencedTable(table_name='table1', system_id='system1')
        mock_table2 = ReferencedTable(table_name='table2', system_id='system2')  # 未授权系统的表
        mock_parsed_def = ParsedSqlDefinition(referenced_tables=[mock_table1, mock_table2])
        self.mock_analyzer.get_parsed_def.return_value = mock_parsed_def

        # 执行权限校验（应返回False）
        params = MagicMock()
        params.scene_id = 1
        params.tool_variables = []

        # 验证权限校验返回False
        result = self.executor.validate_permission(params)
        self.assertFalse(result)
        mock_get_table_ids.assert_called_once_with(1)
        mock_get_system_ids.assert_called_once_with(1)

    @patch.object(SceneDataFilter, 'get_table_ids')
    @patch.object(SceneDataFilter, 'get_system_ids')
    def test_scene_table_permission_without_scene_id(self, mock_get_system_ids, mock_get_table_ids):
        """测试没有场景ID时的正常BK-Base权限校验"""
        # 模拟SQL解析结果
        mock_table1 = ReferencedTable(table_name='table1', system_id='system1')
        mock_parsed_def = ParsedSqlDefinition(referenced_tables=[mock_table1])
        self.mock_analyzer.get_parsed_def.return_value = mock_parsed_def

        # 模拟BK-Base权限校验通过
        with patch('api.bk_base.user_auth_batch_check') as mock_auth_check:
            mock_auth_check.return_value = [{'user_id': 'test_user', 'object_id': 'table1', 'result': True}]

            # 执行权限校验（没有scene_id）
            params = MagicMock()
            params.scene_id = None
            params.tool_variables = []

            self.executor.validate_permission(params)

            # 验证场景权限校验没有被调用
            mock_get_table_ids.assert_not_called()
            mock_get_system_ids.assert_not_called()

    @patch.object(SceneDataFilter, 'get_table_ids')
    @patch.object(SceneDataFilter, 'get_system_ids')
    def test_scene_table_permission_with_all_systems(self, mock_get_system_ids, mock_get_table_ids):
        """测试场景配置了所有系统的情况"""
        # 模拟场景配置了所有系统（空列表）
        mock_get_table_ids.return_value = []
        mock_get_system_ids.return_value = []

        # 模拟SQL解析结果
        mock_table1 = ReferencedTable(table_name='table1', system_id='system1')
        mock_table2 = ReferencedTable(table_name='table2', system_id='system2')
        mock_parsed_def = ParsedSqlDefinition(referenced_tables=[mock_table1, mock_table2])
        self.mock_analyzer.get_parsed_def.return_value = mock_parsed_def

        # 模拟BK-Base权限校验通过
        with patch('api.bk_base.user_auth_batch_check') as mock_auth_check:
            mock_auth_check.return_value = [
                {'user_id': 'test_user', 'object_id': 'table1', 'result': True},
                {'user_id': 'test_user', 'object_id': 'table2', 'result': True},
            ]

            # 执行权限校验
            params = MagicMock()
            params.scene_id = 1
            params.tool_variables = []

            self.executor.validate_permission(params)

            # 验证场景权限校验被调用但返回空列表（表示所有系统）
            mock_get_table_ids.assert_called_once_with(1)
            mock_get_system_ids.assert_called_once_with(1)

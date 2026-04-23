from unittest.mock import MagicMock, patch

from django.test import TestCase

from core.sql.model import Table
from core.sql.parser.model import ParsedSQLInfo
from services.web.scene.data_filter import SceneDataFilter
from services.web.tool.exceptions import DataSearchTablePermission
from services.web.tool.executor.tool import SqlDataSearchExecutor


class TestSceneTablePermissionValidation(TestCase):
    """测试场景表权限校验功能"""

    def setUp(self):
        # 创建模拟的工具对象
        self.mock_tool = MagicMock()
        self.mock_tool.get_permission_owner.return_value = 'test_user'

        # mock 掉 __init__，避免触发真实的配置解析和分析器初始化
        with patch.object(SqlDataSearchExecutor, '__init__', return_value=None):
            self.executor = SqlDataSearchExecutor.__new__(SqlDataSearchExecutor)

        # 手动设置执行器所需的属性
        self.executor.tool = self.mock_tool
        self.executor.config = MagicMock()
        self.mock_analyzer = MagicMock()
        self.executor.analyzer = self.mock_analyzer

    @patch.object(SceneDataFilter, 'get_table_ids')
    def test_scene_table_permission_with_table_whitelist_valid(self, mock_get_table_ids):
        """测试场景表白名单校验通过的情况"""
        # 模拟场景配置了数据表白名单
        mock_get_table_ids.return_value = ['table1', 'table2']

        # 模拟SQL解析结果
        mock_table1 = Table(table_name='table1')
        mock_table2 = Table(table_name='table2')
        mock_parsed_def = ParsedSQLInfo(
            original_sql='SELECT * FROM table1, table2',
            referenced_tables=[mock_table1, mock_table2],
            sql_variables=[],
            result_fields=[],
        )
        self.mock_analyzer.get_parsed_def.return_value = mock_parsed_def

        # 模拟BK-Base权限校验通过
        with patch('services.web.tool.executor.tool.api.bk_base.user_auth_batch_check') as mock_auth_check:
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

    @patch.object(SceneDataFilter, 'get_table_ids')
    def test_scene_table_permission_with_table_whitelist_denied(self, mock_get_table_ids):
        """测试场景表白名单校验不通过时抛出 DataSearchTablePermission 异常"""
        # 模拟场景配置了数据表白名单
        mock_get_table_ids.return_value = ['table1']  # 只授权了table1

        # 模拟SQL解析结果（引用了未授权的表）
        mock_table1 = Table(table_name='table1')
        mock_table2 = Table(table_name='table2')  # 未授权的表
        mock_parsed_def = ParsedSQLInfo(
            original_sql='SELECT * FROM table1, table2',
            referenced_tables=[mock_table1, mock_table2],
            sql_variables=[],
            result_fields=[],
        )
        self.mock_analyzer.get_parsed_def.return_value = mock_parsed_def

        # 执行权限校验（应抛出 DataSearchTablePermission 异常）
        params = MagicMock()
        params.scene_id = 1
        params.tool_variables = []

        with self.assertRaises(DataSearchTablePermission):
            self.executor.validate_permission(params)
        mock_get_table_ids.assert_called_once_with(1)

    @patch.object(SceneDataFilter, 'get_table_ids')
    def test_scene_table_permission_without_table_whitelist(self, mock_get_table_ids):
        """测试场景没有配置数据表白名单时抛出 DataSearchTablePermission 异常"""
        # 模拟场景没有配置数据表白名单
        mock_get_table_ids.return_value = []

        # 模拟SQL解析结果
        mock_table1 = Table(table_name='table1')
        mock_table2 = Table(table_name='table2')
        mock_parsed_def = ParsedSQLInfo(
            original_sql='SELECT * FROM table1, table2',
            referenced_tables=[mock_table1, mock_table2],
            sql_variables=[],
            result_fields=[],
        )
        self.mock_analyzer.get_parsed_def.return_value = mock_parsed_def

        # 执行权限校验（应抛出 DataSearchTablePermission 异常，因为没有表白名单）
        params = MagicMock()
        params.scene_id = 1
        params.tool_variables = []

        with self.assertRaises(DataSearchTablePermission):
            self.executor.validate_permission(params)
        mock_get_table_ids.assert_called_once_with(1)

    @patch.object(SceneDataFilter, 'get_table_ids')
    def test_scene_table_permission_partial_whitelist_denied(self, mock_get_table_ids):
        """测试引用了白名单之外的表时抛出 DataSearchTablePermission 异常"""
        # 模拟场景只授权了部分表
        mock_get_table_ids.return_value = ['table1']  # 只授权了table1

        # 模拟SQL解析结果（引用了未授权的表）
        mock_table1 = Table(table_name='table1')
        mock_table3 = Table(table_name='table3')  # 未授权的表
        mock_parsed_def = ParsedSQLInfo(
            original_sql='SELECT * FROM table1, table3',
            referenced_tables=[mock_table1, mock_table3],
            sql_variables=[],
            result_fields=[],
        )
        self.mock_analyzer.get_parsed_def.return_value = mock_parsed_def

        # 执行权限校验（应抛出 DataSearchTablePermission 异常）
        params = MagicMock()
        params.scene_id = 1
        params.tool_variables = []

        with self.assertRaises(DataSearchTablePermission):
            self.executor.validate_permission(params)
        mock_get_table_ids.assert_called_once_with(1)

    @patch.object(SceneDataFilter, 'get_table_ids')
    def test_scene_table_permission_without_scene_id(self, mock_get_table_ids):
        """测试没有场景ID时的正常BK-Base权限校验"""
        # 模拟SQL解析结果
        mock_table1 = Table(table_name='table1')
        mock_parsed_def = ParsedSQLInfo(
            original_sql='SELECT * FROM table1',
            referenced_tables=[mock_table1],
            sql_variables=[],
            result_fields=[],
        )
        self.mock_analyzer.get_parsed_def.return_value = mock_parsed_def

        # 模拟BK-Base权限校验通过
        with patch('services.web.tool.executor.tool.api.bk_base.user_auth_batch_check') as mock_auth_check:
            mock_auth_check.return_value = [{'user_id': 'test_user', 'object_id': 'table1', 'result': True}]

            # 执行权限校验（没有scene_id）
            params = MagicMock()
            params.scene_id = None
            params.tool_variables = []

            self.executor.validate_permission(params)

            # 验证场景权限校验没有被调用
            mock_get_table_ids.assert_not_called()

    @patch.object(SceneDataFilter, 'get_table_ids')
    def test_scene_table_permission_empty_whitelist_denied(self, mock_get_table_ids):
        """测试场景没有配置任何表白名单时抛出 DataSearchTablePermission 异常"""
        # 模拟场景没有配置任何数据表白名单
        mock_get_table_ids.return_value = []

        # 模拟SQL解析结果
        mock_table1 = Table(table_name='table1')
        mock_table2 = Table(table_name='table2')
        mock_parsed_def = ParsedSQLInfo(
            original_sql='SELECT * FROM table1, table2',
            referenced_tables=[mock_table1, mock_table2],
            sql_variables=[],
            result_fields=[],
        )
        self.mock_analyzer.get_parsed_def.return_value = mock_parsed_def

        # 执行权限校验（应抛出 DataSearchTablePermission 异常，因为没有表白名单）
        params = MagicMock()
        params.scene_id = 1
        params.tool_variables = []

        with self.assertRaises(DataSearchTablePermission):
            self.executor.validate_permission(params)
        mock_get_table_ids.assert_called_once_with(1)

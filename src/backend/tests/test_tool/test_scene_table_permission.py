from unittest.mock import MagicMock, patch

from django.test import TestCase

from core.sql.model import Table
from core.sql.parser.model import ParsedSQLInfo
from services.web.tool.exceptions import DataSearchTablePermission
from services.web.tool.executor.tool import SqlDataSearchExecutor


class TestSceneTablePermissionValidation(TestCase):
    """测试数据查询工具权限校验功能"""

    def setUp(self):
        # 创建模拟的工具对象
        self.mock_tool = MagicMock()
        self.mock_tool.uid = 'test_tool_uid'
        self.mock_tool.get_permission_owner.return_value = 'test_user'

        # mock 掉 __init__，避免触发真实的配置解析和分析器初始化
        with patch.object(SqlDataSearchExecutor, '__init__', return_value=None):
            self.executor = SqlDataSearchExecutor.__new__(SqlDataSearchExecutor)

        # 手动设置执行器所需的属性
        self.executor.tool = self.mock_tool
        self.executor.config = MagicMock()
        self.mock_analyzer = MagicMock()
        self.executor.analyzer = self.mock_analyzer

    def _make_parsed_def(self, table_names, sql=None):
        """辅助方法：构造 ParsedSQLInfo"""
        tables = [Table(table_name=name) for name in table_names]
        return ParsedSQLInfo(
            original_sql=sql or f'SELECT * FROM {", ".join(table_names)}',
            referenced_tables=tables,
            sql_variables=[],
            result_fields=[],
        )

    def test_validate_permission_all_tables_authorized_by_user(self):
        """测试所有表都有用户个人权限时校验通过（无场景授权）"""
        self.mock_analyzer.get_parsed_def.return_value = self._make_parsed_def(['table1', 'table2'])

        with patch.object(SqlDataSearchExecutor, '_get_tool_scene_id', return_value=None), patch(
            'services.web.tool.executor.tool.api.bk_base.user_auth_batch_check'
        ) as mock_auth_check, patch('services.web.tool.executor.tool.get_request_username', return_value='test_user'):
            mock_auth_check.return_value = [
                {'user_id': 'test_user', 'object_id': 'table1', 'result': True},
                {'user_id': 'test_user', 'object_id': 'table2', 'result': True},
            ]

            params = MagicMock()
            params.tool_variables = []

            self.executor.validate_permission(params)
            mock_auth_check.assert_called_once()

    def test_validate_permission_table_denied(self):
        """测试某个表没有权限时抛出 DataSearchTablePermission 异常"""
        self.mock_analyzer.get_parsed_def.return_value = self._make_parsed_def(['table1', 'table2'])

        with patch.object(SqlDataSearchExecutor, '_get_tool_scene_id', return_value=None), patch(
            'services.web.tool.executor.tool.api.bk_base.user_auth_batch_check'
        ) as mock_auth_check, patch('services.web.tool.executor.tool.get_request_username', return_value='test_user'):
            mock_auth_check.return_value = [
                {'user_id': 'test_user', 'object_id': 'table1', 'result': True},
                {'user_id': 'test_user', 'object_id': 'table2', 'result': False},
            ]

            params = MagicMock()
            params.tool_variables = []

            with self.assertRaises(DataSearchTablePermission):
                self.executor.validate_permission(params)

    def test_validate_permission_single_table_authorized(self):
        """测试单表有权限时校验通过"""
        self.mock_analyzer.get_parsed_def.return_value = self._make_parsed_def(['table1'])

        with patch.object(SqlDataSearchExecutor, '_get_tool_scene_id', return_value=None), patch(
            'services.web.tool.executor.tool.api.bk_base.user_auth_batch_check'
        ) as mock_auth_check, patch('services.web.tool.executor.tool.get_request_username', return_value='test_user'):
            mock_auth_check.return_value = [
                {'user_id': 'test_user', 'object_id': 'table1', 'result': True},
            ]

            params = MagicMock()
            params.tool_variables = []

            self.executor.validate_permission(params)
            mock_auth_check.assert_called_once()

    def test_validate_permission_all_tables_denied(self):
        """测试所有表都没有权限时抛出 DataSearchTablePermission 异常"""
        self.mock_analyzer.get_parsed_def.return_value = self._make_parsed_def(['table1', 'table2'])

        with patch.object(SqlDataSearchExecutor, '_get_tool_scene_id', return_value=None), patch(
            'services.web.tool.executor.tool.api.bk_base.user_auth_batch_check'
        ) as mock_auth_check, patch('services.web.tool.executor.tool.get_request_username', return_value='test_user'):
            mock_auth_check.return_value = [
                {'user_id': 'test_user', 'object_id': 'table1', 'result': False},
                {'user_id': 'test_user', 'object_id': 'table2', 'result': False},
            ]

            params = MagicMock()
            params.tool_variables = []

            with self.assertRaises(DataSearchTablePermission):
                self.executor.validate_permission(params)

    def test_validate_permission_uses_request_username(self):
        """测试权限校验使用 get_request_username 返回的用户名"""
        self.mock_analyzer.get_parsed_def.return_value = self._make_parsed_def(['table1'])

        with patch.object(SqlDataSearchExecutor, '_get_tool_scene_id', return_value=None), patch(
            'services.web.tool.executor.tool.api.bk_base.user_auth_batch_check'
        ) as mock_auth_check, patch('services.web.tool.executor.tool.get_request_username', return_value='test_user'):
            mock_auth_check.return_value = [
                {'user_id': 'test_user', 'object_id': 'table1', 'result': True},
            ]

            params = MagicMock()
            params.tool_variables = []

            self.executor.validate_permission(params)

            # 验证传给 BK-Base 的 user_id 是 get_request_username() 返回的值
            call_args = mock_auth_check.call_args
            permissions = call_args[0][0]['permissions'] if call_args[0] else call_args[1]['permissions']
            self.assertEqual(permissions[0]['user_id'], 'test_user')

    def test_validate_permission_without_tool(self):
        """测试没有 tool 对象时不查询场景授权表，直接校验用户个人权限"""
        self.executor.tool = None
        self.mock_analyzer.get_parsed_def.return_value = self._make_parsed_def(['table1'])

        with patch('services.web.tool.executor.tool.api.bk_base.user_auth_batch_check') as mock_auth_check, patch(
            'services.web.tool.executor.tool.get_request_username', return_value='request_user'
        ):
            mock_auth_check.return_value = [
                {'user_id': 'request_user', 'object_id': 'table1', 'result': True},
            ]

            params = MagicMock()
            params.tool_variables = []

            self.executor.validate_permission(params)

            call_args = mock_auth_check.call_args
            permissions = call_args[0][0]['permissions'] if call_args[0] else call_args[1]['permissions']
            self.assertEqual(permissions[0]['user_id'], 'request_user')

    def test_validate_permission_no_referenced_tables(self):
        """测试没有引用表时直接通过"""
        self.mock_analyzer.get_parsed_def.return_value = ParsedSQLInfo(
            original_sql='SELECT 1',
            referenced_tables=[],
            sql_variables=[],
            result_fields=[],
        )

        params = MagicMock()
        params.tool_variables = []

        # 不应抛出异常
        self.executor.validate_permission(params)

    # ========== 场景授权表相关测试 ==========

    def test_validate_permission_all_tables_authorized_by_scene(self):
        """测试所有表都在场景授权范围内时，不调用用户个人权限校验"""
        self.mock_analyzer.get_parsed_def.return_value = self._make_parsed_def(['table1', 'table2'])

        with patch.object(SqlDataSearchExecutor, '_get_tool_scene_id', return_value=1), patch(
            'services.web.tool.executor.tool.SceneDataFilter.get_table_ids', return_value=['table1', 'table2']
        ), patch('services.web.tool.executor.tool.api.bk_base.user_auth_batch_check') as mock_auth_check, patch(
            'services.web.tool.executor.tool.get_request_username', return_value='test_user'
        ):

            params = MagicMock()
            params.tool_variables = []

            self.executor.validate_permission(params)

            # 所有表都在场景授权范围内，不应调用用户权限校验
            mock_auth_check.assert_not_called()

    def test_validate_permission_partial_scene_authorization(self):
        """测试部分表在场景授权范围内，未授权的表需要校验用户个人权限"""
        self.mock_analyzer.get_parsed_def.return_value = self._make_parsed_def(['table1', 'table2', 'table3'])

        with patch.object(SqlDataSearchExecutor, '_get_tool_scene_id', return_value=1), patch(
            'services.web.tool.executor.tool.SceneDataFilter.get_table_ids', return_value=['table1']
        ), patch('services.web.tool.executor.tool.api.bk_base.user_auth_batch_check') as mock_auth_check, patch(
            'services.web.tool.executor.tool.get_request_username', return_value='test_user'
        ):
            mock_auth_check.return_value = [
                {'user_id': 'test_user', 'object_id': 'table2', 'result': True},
                {'user_id': 'test_user', 'object_id': 'table3', 'result': True},
            ]

            params = MagicMock()
            params.tool_variables = []

            self.executor.validate_permission(params)

            # 只对未被场景授权的 table2、table3 校验用户权限
            mock_auth_check.assert_called_once()
            call_args = mock_auth_check.call_args
            permissions = call_args[0][0]['permissions'] if call_args[0] else call_args[1]['permissions']
            checked_tables = {p['object_id'] for p in permissions}
            self.assertEqual(checked_tables, {'table2', 'table3'})

    def test_validate_permission_partial_scene_auth_user_denied(self):
        """测试部分表在场景授权范围内，但未授权的表用户也没有权限时抛出异常"""
        self.mock_analyzer.get_parsed_def.return_value = self._make_parsed_def(['table1', 'table2'])

        with patch.object(SqlDataSearchExecutor, '_get_tool_scene_id', return_value=1), patch(
            'services.web.tool.executor.tool.SceneDataFilter.get_table_ids', return_value=['table1']
        ), patch('services.web.tool.executor.tool.api.bk_base.user_auth_batch_check') as mock_auth_check, patch(
            'services.web.tool.executor.tool.get_request_username', return_value='test_user'
        ):
            mock_auth_check.return_value = [
                {'user_id': 'test_user', 'object_id': 'table2', 'result': False},
            ]

            params = MagicMock()
            params.tool_variables = []

            with self.assertRaises(DataSearchTablePermission):
                self.executor.validate_permission(params)

    def test_validate_permission_scene_id_none(self):
        """测试工具未关联场景时，所有表都需要校验用户个人权限"""
        self.mock_analyzer.get_parsed_def.return_value = self._make_parsed_def(['table1'])

        with patch.object(SqlDataSearchExecutor, '_get_tool_scene_id', return_value=None), patch(
            'services.web.tool.executor.tool.api.bk_base.user_auth_batch_check'
        ) as mock_auth_check, patch('services.web.tool.executor.tool.get_request_username', return_value='test_user'):
            mock_auth_check.return_value = [
                {'user_id': 'test_user', 'object_id': 'table1', 'result': True},
            ]

            params = MagicMock()
            params.tool_variables = []

            self.executor.validate_permission(params)
            mock_auth_check.assert_called_once()


class TestCheckTablePermission(TestCase):
    """测试 check_table_permission 静态方法"""

    def test_empty_referenced_tables(self):
        """测试引用表为空时直接通过"""
        SqlDataSearchExecutor.check_table_permission([], tool=None)

    def test_all_tables_in_scene(self):
        """测试所有表都在场景授权范围内时直接通过，不调用 API"""
        tables = ['t1', 't2']
        mock_tool = MagicMock()
        mock_tool.uid = 'test_tool_uid'
        with patch.object(SqlDataSearchExecutor, '_get_tool_scene_id', return_value=1), patch(
            'services.web.tool.executor.tool.SceneDataFilter.get_table_ids', return_value=['t1', 't2']
        ), patch('services.web.tool.executor.tool.api.bk_base.user_auth_batch_check') as mock_auth:
            SqlDataSearchExecutor.check_table_permission(tables, tool=mock_tool)
            mock_auth.assert_not_called()

    def test_no_scene_tables_user_authorized(self):
        """测试无场景授权（tool=None）时，返回全部表供后续校验"""
        tables = ['t1']
        result = SqlDataSearchExecutor.check_table_permission(tables, tool=None)
        # tool=None 时 scene_id 为 None，所有表都需要校验
        self.assertEqual(result, ['t1'])

    def test_no_scene_tables_returns_all(self):
        """测试无场景授权（tool=None）时，返回全部表"""
        tables = ['t1', 't2']
        result = SqlDataSearchExecutor.check_table_permission(tables, tool=None)
        # tool=None 时所有表都需要后续校验
        self.assertEqual(result, ['t1', 't2'])

    def test_partial_scene_auth_remaining_user_authorized(self):
        """测试部分场景授权，返回未被场景授权的表"""
        tables = ['t1', 't2', 't3']
        mock_tool = MagicMock()
        mock_tool.uid = 'test_tool_uid'
        with patch.object(SqlDataSearchExecutor, '_get_tool_scene_id', return_value=1), patch(
            'services.web.tool.executor.tool.SceneDataFilter.get_table_ids', return_value=['t1']
        ):
            result = SqlDataSearchExecutor.check_table_permission(tables, tool=mock_tool)

            # t1 被场景授权，只返回 t2 和 t3 供后续校验
            self.assertEqual(set(result), {'t2', 't3'})

    def test_partial_scene_auth_remaining_returned(self):
        """测试部分场景授权，返回未被场景授权的表供后续校验"""
        tables = ['t1', 't2']
        mock_tool = MagicMock()
        mock_tool.uid = 'test_tool_uid'
        with patch.object(SqlDataSearchExecutor, '_get_tool_scene_id', return_value=1), patch(
            'services.web.tool.executor.tool.SceneDataFilter.get_table_ids', return_value=['t1']
        ):
            result = SqlDataSearchExecutor.check_table_permission(tables, tool=mock_tool)
            # t1 被场景授权，只返回 t2 供后续校验
            self.assertEqual(result, ['t2'])

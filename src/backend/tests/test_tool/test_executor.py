# -*- coding: utf-8 -*-
from unittest import mock

from django.test import TestCase

from api.bk_base.default import QuerySyncResource, UserAuthBatchCheck
from apps.permission.handlers.permission import Permission
from core.sql.model import Table
from core.sql.parser.model import ParsedSQLInfo
from core.sql.parser.praser import SqlQueryAnalysis
from services.web.tool.constants import (
    BkvisionConfig,
    SQLDataSearchConfig,
    ToolTypeEnum,
)
from services.web.tool.exceptions import DataSearchTablePermission
from services.web.tool.executor.model import (
    BkVisionExecuteResult,
    DataSearchToolExecuteParams,
)
from services.web.tool.executor.tool import (
    BkVisionExecutor,
    SqlDataSearchExecutor,
    ToolExecutorFactory,
)
from services.web.tool.models import BkvisionToolConfig, DataSearchToolConfig, Tool
from services.web.vision.models import VisionPanel


class TestSqlDataSearchExecutor(TestCase):
    def setUp(self):
        """设置SQL查询执行器的测试环境和mock对象"""
        # Mock SqlQueryAnalysis
        self.mock_analyzer_cls = mock.MagicMock(spec=SqlQueryAnalysis)
        self.mock_analyzer_instance = self.mock_analyzer_cls.return_value
        self.mock_analyzer_instance.generate_sql_with_values.return_value = {
            "data": "SELECT * FROM mocked_table",
            "count": "SELECT COUNT(*) FROM mocked_table",
        }
        self.mock_analyzer_instance.get_parsed_def.return_value = ParsedSQLInfo(
            referenced_tables=[Table(table_name="mocked_table")],
            original_sql="SELECT * FROM table",
            sql_variables=[],
            result_fields=[],
        )

        # 创建测试Tool对象
        self.sql_tool = Tool.objects.create(
            namespace="test",
            name="sql_tool",
            uid="sql_tool_123",
            version=1,
            tool_type=ToolTypeEnum.DATA_SEARCH.value,
            config={
                "sql": "SELECT * FROM table",
                "referenced_tables": [{"table_name": "table"}],
                "input_variable": [],
                "output_fields": [],
                "prefer_storage": "doris",
            },
            updated_by="test_user",
        )

        # 创建执行参数
        self.sql_params = DataSearchToolExecuteParams(
            tool_variables=[{"raw_name": "time_range", "value": "2023-01-01,2023-12-31"}], page=1, page_size=100
        )

        # Mock API
        self.mock_bkbase_api = mock.patch.object(
            QuerySyncResource,
            'bulk_request',
            return_value=[{"list": [{"field1": "value1"}, {"field2": "value2"}]}, {"list": [{"count": 2}]}],
        )
        self.mock_bkbase_api = self.mock_bkbase_api.start()
        self.patcher_auth = mock.patch.object(
            UserAuthBatchCheck,
            "perform_request",
            return_value=[{"result": True, "user_id": "test_user", "object_id": "mocked_table"}],
        )
        self.mock_auth_api = self.patcher_auth.start()

    def tearDown(self):
        mock.patch.stopall()

    def test_execute_with_tool_object(self):
        """测试通过Tool对象初始化执行SQL查询"""
        executor = SqlDataSearchExecutor(source=self.sql_tool, analyzer_cls=self.mock_analyzer_cls)
        result = executor.execute(self.sql_params).model_dump()
        self.assertDictEqual(
            result,
            {
                'count_sql': 'SELECT COUNT(*) FROM mocked_table',
                'num_pages': 100,
                'page': 1,
                'query_sql': 'SELECT * FROM mocked_table',
                'results': [{'field1': 'value1'}, {'field2': 'value2'}],
                'total': 2,
            },
        )

    def test_execute_with_config_object(self):
        """测试通过配置对象直接初始化执行SQL查询"""
        config = SQLDataSearchConfig(
            sql="SELECT * FROM config_table",
            referenced_tables=[{"table_name": "table"}],
            input_variable=[],
            output_fields=[],
            prefer_storage="doris",
        )
        executor = SqlDataSearchExecutor(source=config, analyzer_cls=self.mock_analyzer_cls)
        result = executor.execute(self.sql_params).model_dump()
        self.assertDictEqual(
            result,
            {
                'count_sql': 'SELECT COUNT(*) FROM mocked_table',
                'num_pages': 100,
                'page': 1,
                'query_sql': 'SELECT * FROM mocked_table',
                'results': [{'field1': 'value1'}, {'field2': 'value2'}],
                'total': 2,
            },
        )

    def test_execute_permission_denied(self):
        """测试无权限时抛出 DataSearchTablePermission 异常"""
        with mock.patch.object(
            UserAuthBatchCheck,
            "perform_request",
            return_value=[{"result": False, "user_id": "test_user", "object_id": "mocked_table"}],
        ):
            executor = SqlDataSearchExecutor(source=self.sql_tool, analyzer_cls=self.mock_analyzer_cls)
            with self.assertRaises(DataSearchTablePermission):
                executor.execute(self.sql_params)


class TestBkVisionExecutor(TestCase):
    def setUp(self):
        """设置BK Vision执行器的测试环境"""
        # 创建测试Tool对象
        self.vision_tool = Tool.objects.create(
            namespace="test",
            name="vision_tool",
            uid="vision_tool_123",
            version=1,
            tool_type=ToolTypeEnum.BK_VISION.value,
            config={"uid": "vision_panel_123"},
            updated_by="test_user",
        )

        # 创建关联的VisionPanel和BkvisionToolConfig
        self.mock_panel = VisionPanel.objects.create(
            id="panel_123", vision_id="vision_panel_123", scenario="tool", handler="VisionHandler"
        )
        BkvisionToolConfig.objects.create(tool=self.vision_tool, panel=self.mock_panel)

    def test_execute_with_tool_object(self):
        """测试通过Tool对象初始化执行BK Vision查询"""
        with mock.patch.object(Permission, "is_allowed", return_value=True) as mock_is_allowed:
            executor = BkVisionExecutor(self.vision_tool)
            result = executor.execute({})
            self.assertIsInstance(result, BkVisionExecuteResult)
            self.assertEqual(result.panel_id, "panel_123")
            mock_is_allowed.assert_called_once()

    def test_execute_with_config_object(self):
        """测试通过配置对象直接初始化执行BK Vision查询"""
        config = BkvisionConfig(uid="vision_panel_123")
        with mock.patch.object(Permission, "is_allowed", return_value=True) as mock_is_allowed:
            with mock.patch.object(Tool, 'fetch_tool_vision_panel', return_value=self.mock_panel):
                executor = BkVisionExecutor(config)
                result = executor.execute({})
                self.assertEqual(result.panel_id, "panel_123")
                mock_is_allowed.assert_called_once()

    def test_execute_permission_denied(self):
        """测试无权限时抛出异常"""
        with mock.patch.object(Permission, "is_allowed", side_effect=Exception("No permission")):
            executor = BkVisionExecutor(self.vision_tool)
            with self.assertRaises(Exception):
                executor.execute({})


class TestToolExecutorFactory(TestCase):
    def setUp(self):
        self.mock_analyzer_cls = mock.MagicMock(spec=SqlQueryAnalysis)

        # 创建测试Tool对象
        self.sql_tool = Tool.objects.create(
            tool_type=ToolTypeEnum.DATA_SEARCH.value,
            name="vision_tool",
            version=1,
            config=SQLDataSearchConfig(
                sql="SELECT * FROM table",
                referenced_tables=[{"table_name": "table"}],
                input_variable=[],
                output_fields=[],
                prefer_storage="doris",
            ).model_dump(),
        )
        DataSearchToolConfig.objects.create(
            tool=self.sql_tool, data_search_config_type="sql", sql="SELECT * FROM table"
        )

        self.vision_tool = Tool.objects.create(
            tool_type=ToolTypeEnum.BK_VISION.value, name="vision_tool", version=1, config={"uid": "vision_panel_123"}
        )

    def test_create_sql_executor(self):
        """测试工厂创建SQL执行器"""
        factory = ToolExecutorFactory(self.mock_analyzer_cls)
        executor = factory.create_from_tool(self.sql_tool)

        self.assertIsInstance(executor, SqlDataSearchExecutor)
        self.assertEqual(executor.config.sql, "SELECT * FROM table")

    def test_create_vision_executor(self):
        """测试工厂创建BK Vision执行器"""
        factory = ToolExecutorFactory(self.mock_analyzer_cls)
        executor = factory.create_from_tool(self.vision_tool)

        self.assertIsInstance(executor, BkVisionExecutor)
        self.assertEqual(executor.config.uid, "vision_panel_123")

    def test_create_with_unsupported_type(self):
        """测试工厂处理不支持的工具类型"""
        invalid_tool = Tool.objects.create(tool_type="invalid_type", name="invalid_tool", version=1, namespace="test")

        factory = ToolExecutorFactory(self.mock_analyzer_cls)
        with self.assertRaises(ValueError):
            factory.create_from_tool(invalid_tool)

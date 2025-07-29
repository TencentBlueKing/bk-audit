# -*- coding: utf-8 -*-
from unittest import mock

from django.test import TestCase

from api.bk_base.default import QuerySyncResource, UserAuthBatchCheck
from apps.permission.handlers.permission import Permission
from core.sql.parser.praser import SqlQueryAnalysis
from services.web.tool.constants import (
    BkvisionConfig,
    FieldCategory,
    SQLDataSearchConfig,
    SQLDataSearchInputVariable,
    ToolTypeEnum,
)
from services.web.tool.exceptions import (
    DataSearchTablePermission,
    InputVariableMissingError,
    InvalidVariableFormatError,
    InvalidVariableStructureError,
    ParseVariableError,
)
from services.web.tool.executor.model import (
    BkVisionExecuteResult,
    DataSearchToolExecuteParams,
)
from services.web.tool.executor.tool import (
    BkVisionExecutor,
    SqlDataSearchExecutor,
    ToolExecutorFactory,
    VariableValueParser,
)
from services.web.tool.models import BkVisionToolConfig, DataSearchToolConfig, Tool
from services.web.vision.models import VisionPanel


class TestSqlDataSearchExecutor(TestCase):
    def setUp(self):
        """设置SQL查询执行器的测试环境和mock对象"""
        self.analyzer_cls = SqlQueryAnalysis

        # 创建测试Tool对象
        self.sql_tool = Tool.objects.create(
            namespace="test",
            name="sql_tool",
            uid="sql_tool_123",
            version=1,
            tool_type=ToolTypeEnum.DATA_SEARCH.value,
            config={
                "sql": "SELECT a FROM table",
                "referenced_tables": [{"table_name": "table"}],
                "input_variable": [],
                "output_fields": [],
                "prefer_storage": "doris",
            },
            updated_by="test_user",
        )

        # 创建执行参数
        self.sql_params = DataSearchToolExecuteParams(
            tool_variables=[{"raw_name": "time_range", "value": "2023-01-01,2023-12-31"}],
            page=1,
            page_size=100,
        )

        # Mock BKBase 查询接口
        self.mock_bkbase_api = mock.patch.object(
            QuerySyncResource,
            "bulk_request",
            return_value=[{"list": [{"field1": "value1"}, {"field2": "value2"}]}, {"list": [{"count": 2}]}],
        )
        self.mock_bkbase_api = self.mock_bkbase_api.start()

        # Mock 权限校验
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
        executor = SqlDataSearchExecutor(source=self.sql_tool, analyzer_cls=self.analyzer_cls)
        result = executor.execute(self.sql_params).model_dump()
        self.assertDictEqual(
            result,
            {
                "count_sql": "SELECT COUNT(*) AS count FROM (SELECT a FROM table) AS _sub",
                "num_pages": 100,
                "page": 1,
                "query_sql": "SELECT a FROM table LIMIT 100",
                "results": [{"field1": "value1"}, {"field2": "value2"}],
                "total": 2,
            },
        )

    def test_execute_with_config_object(self):
        """测试通过配置对象直接初始化执行SQL查询"""
        config = SQLDataSearchConfig(
            sql="SELECT a FROM config_table",
            referenced_tables=[{"table_name": "table"}],
            input_variable=[],
            output_fields=[],
        )
        executor = SqlDataSearchExecutor(source=config, analyzer_cls=self.analyzer_cls)
        result = executor.execute(self.sql_params).model_dump()
        self.assertDictEqual(
            result,
            {
                "count_sql": "SELECT COUNT(*) AS count FROM (SELECT a FROM config_table) AS _sub",
                "num_pages": 100,
                "page": 1,
                "query_sql": "SELECT a FROM config_table LIMIT 100",
                "results": [{"field1": "value1"}, {"field2": "value2"}],
                "total": 2,
            },
        )

    def test_execute_permission_denied(self):
        """测试无权限时抛出 DataSearchTablePermission 异常"""
        with mock.patch.object(
            UserAuthBatchCheck,
            "perform_request",
            return_value=[{"result": False, "user_id": "test_user", "object_id": "mocked_table"}],
        ):
            executor = SqlDataSearchExecutor(source=self.sql_tool, analyzer_cls=self.analyzer_cls)
            with self.assertRaises(DataSearchTablePermission):
                executor.execute(self.sql_params)

    def test_variable_missing(self):
        """测试必填变量缺失时抛出 InputVariableMissingError"""
        config = SQLDataSearchConfig(
            sql="SELECT a FROM table WHERE a = :a",
            referenced_tables=[{"table_name": "table"}],
            input_variable=[
                SQLDataSearchInputVariable(
                    raw_name="a", display_name="变量A", required=True, field_category=FieldCategory.INPUT, choices=[]
                )
            ],
            output_fields=[],
        )
        executor = SqlDataSearchExecutor(source=config, analyzer_cls=self.analyzer_cls)
        params = DataSearchToolExecuteParams(tool_variables=[], page=1, page_size=10)
        with self.assertRaises(InputVariableMissingError) as cm:
            executor.execute(params)
        self.assertEqual("输入变量“变量A”必填", cm.exception.message)

    def test_variable_format_error(self):
        """测试变量格式错误时抛出 InvalidVariableFormatError"""
        # 数字输入
        config = SQLDataSearchConfig(
            sql="SELECT a FROM table WHERE a = {{a}}",
            referenced_tables=[{"table_name": "table"}],
            input_variable=[
                SQLDataSearchInputVariable(
                    raw_name="a",
                    display_name="变量A",
                    required=True,
                    field_category=FieldCategory.NUMBER_INPUT,
                    choices=[],
                )
            ],
            output_fields=[],
        )
        executor = SqlDataSearchExecutor(source=config, analyzer_cls=self.analyzer_cls)
        params = DataSearchToolExecuteParams(
            tool_variables=[{"raw_name": "a", "value": "not_a_number"}], page=1, page_size=10
        )
        with self.assertRaises(InvalidVariableFormatError) as cm:
            executor.execute(params)
        self.assertEqual("变量类型“数字输入框”的值“not_a_number”格式无效", cm.exception.message)

        # 时间选择器
        config = SQLDataSearchConfig(
            sql="SELECT a FROM table WHERE a = {{a}}",
            referenced_tables=[{"table_name": "table"}],
            input_variable=[
                SQLDataSearchInputVariable(
                    raw_name="a",
                    display_name="变量A",
                    required=True,
                    field_category=FieldCategory.TIME_SELECT,
                    choices=[],
                )
            ],
            output_fields=[],
        )
        executor = SqlDataSearchExecutor(source=config, analyzer_cls=self.analyzer_cls)
        params = DataSearchToolExecuteParams(
            tool_variables=[{"raw_name": "a", "value": "not_a_time"}], page=1, page_size=10
        )
        with self.assertRaises(InvalidVariableFormatError) as cm:
            executor.execute(params)
        self.assertIn("格式无效", str(cm.exception.message))

    def test_variable_structure_error(self):
        """测试变量结构错误时抛出 InvalidVariableStructureError"""
        config = SQLDataSearchConfig(
            sql="SELECT a FROM table WHERE a = {{a}}",
            referenced_tables=[{"table_name": "table"}],
            input_variable=[
                SQLDataSearchInputVariable(
                    raw_name="a",
                    display_name="变量A",
                    required=True,
                    field_category=FieldCategory.TIME_RANGE_SELECT,
                    choices=[],
                )
            ],
            output_fields=[],
        )
        executor = SqlDataSearchExecutor(source=config, analyzer_cls=self.analyzer_cls)
        params = DataSearchToolExecuteParams(tool_variables=[{"raw_name": "a", "value": [1]}], page=1, page_size=10)
        with self.assertRaises(InvalidVariableStructureError) as cm:
            executor.execute(params)
        self.assertIn("结构无效", str(cm.exception))

    @mock.patch.object(VariableValueParser, "_format_input", side_effect=RuntimeError("mock error"))
    def test_variable_parse_fallback_error(self, _):
        """测试变量解析兜底异常 ParseVariableError"""
        config = SQLDataSearchConfig(
            sql="SELECT a FROM table WHERE a = {{a}}",
            referenced_tables=[{"table_name": "table"}],
            input_variable=[
                SQLDataSearchInputVariable(
                    raw_name="a", display_name="变量A", required=True, field_category=FieldCategory.INPUT, choices=[]
                )
            ],
            output_fields=[],
        )
        executor = SqlDataSearchExecutor(source=config, analyzer_cls=self.analyzer_cls)
        params = DataSearchToolExecuteParams(tool_variables=[{"raw_name": "a", "value": "xxx"}], page=1, page_size=10)
        with self.assertRaises(ParseVariableError) as cm:
            executor.execute(params)
        self.assertEqual("解析变量类型“输入框”的值“xxx”异常,请联系系统管理员", cm.exception.message)

    def test_sql_execute_input_type(self):
        """测试 input 类型变量的 SQL 执行"""
        config = SQLDataSearchConfig(
            sql="SELECT a FROM table WHERE a = :a",
            referenced_tables=[{"table_name": "table"}],
            input_variable=[
                SQLDataSearchInputVariable(
                    raw_name="a", display_name="变量A", required=True, field_category=FieldCategory.INPUT, choices=[]
                )
            ],
            output_fields=[],
        )
        executor = SqlDataSearchExecutor(source=config, analyzer_cls=self.analyzer_cls)
        params = DataSearchToolExecuteParams(tool_variables=[{"raw_name": "a", "value": "test"}], page=1, page_size=10)
        result = executor.execute(params).model_dump()
        expected = {
            "count_sql": "SELECT COUNT(*) AS count FROM (SELECT a FROM table WHERE a = 'test') AS _sub",
            "num_pages": 10,
            "page": 1,
            "query_sql": "SELECT a FROM table WHERE a = 'test' LIMIT 10",
            "results": [{"field1": "value1"}, {"field2": "value2"}],
            "total": 2,
        }
        self.assertDictEqual(expected, result)

    def test_sql_execute_number_input_type(self):
        """测试 number_input 类型变量的 SQL 执行"""
        config = SQLDataSearchConfig(
            sql="SELECT a FROM table WHERE a = :a",
            referenced_tables=[{"table_name": "table"}],
            input_variable=[
                SQLDataSearchInputVariable(
                    raw_name="a",
                    display_name="变量A",
                    required=True,
                    field_category=FieldCategory.NUMBER_INPUT,
                    choices=[],
                )
            ],
            output_fields=[],
        )
        executor = SqlDataSearchExecutor(source=config, analyzer_cls=self.analyzer_cls)
        params = DataSearchToolExecuteParams(tool_variables=[{"raw_name": "a", "value": 123}], page=1, page_size=10)
        result = executor.execute(params).model_dump()
        expected = {
            "count_sql": "SELECT COUNT(*) AS count FROM (SELECT a FROM table WHERE a = 123) AS _sub",
            "num_pages": 10,
            "page": 1,
            "query_sql": "SELECT a FROM table WHERE a = 123 LIMIT 10",
            "results": [{"field1": "value1"}, {"field2": "value2"}],
            "total": 2,
        }
        self.assertDictEqual(expected, result)

    def test_sql_execute_time_select_type(self):
        """测试 time_select 类型变量的 SQL 执行"""
        import arrow

        now = arrow.get("2023-01-01 12:00:00+08:00")
        ts = int(now.timestamp()) * 1000
        config = SQLDataSearchConfig(
            sql="SELECT a FROM table WHERE a = :a",
            referenced_tables=[{"table_name": "table"}],
            input_variable=[
                SQLDataSearchInputVariable(
                    raw_name="a",
                    display_name="变量A",
                    required=True,
                    field_category=FieldCategory.TIME_SELECT,
                    choices=[],
                )
            ],
            output_fields=[],
        )
        executor = SqlDataSearchExecutor(source=config, analyzer_cls=self.analyzer_cls)
        params = DataSearchToolExecuteParams(
            tool_variables=[{"raw_name": "a", "value": now.format('YYYY-MM-DD HH:mm:ss')}],
            page=1,
            page_size=10,
        )
        result = executor.execute(params).model_dump()
        expected = {
            "count_sql": f"SELECT COUNT(*) AS count FROM (SELECT a FROM table WHERE a = {ts}) AS _sub",
            "num_pages": 10,
            "page": 1,
            "query_sql": f"SELECT a FROM table WHERE a = {ts} LIMIT 10",
            "results": [{"field1": "value1"}, {"field2": "value2"}],
            "total": 2,
        }
        self.assertDictEqual(expected, result)

    def test_sql_execute_time_range_select_type(self):
        """测试 time_range_select 类型变量的 SQL 执行"""
        import arrow

        start = arrow.get("2023-01-01 00:00:00+08:00")
        end = arrow.get("2023-01-02 00:00:00+08:00")
        ts_start = int(start.timestamp()) * 1000
        ts_end = int(end.timestamp()) * 1000
        config = SQLDataSearchConfig(
            sql="SELECT a FROM table WHERE time_range(x, :a,)",
            referenced_tables=[{"table_name": "table"}],
            input_variable=[
                SQLDataSearchInputVariable(
                    raw_name="a",
                    display_name="变量A",
                    required=True,
                    field_category=FieldCategory.TIME_RANGE_SELECT,
                    choices=[],
                )
            ],
            output_fields=[],
        )
        executor = SqlDataSearchExecutor(source=config, analyzer_cls=self.analyzer_cls)
        params = DataSearchToolExecuteParams(
            tool_variables=[{"raw_name": "a", "value": [ts_start, ts_end]}],
            page=1,
            page_size=10,
        )
        result = executor.execute(params).model_dump()
        expected = {
            "count_sql": (
                "SELECT COUNT(*) AS count FROM " f"(SELECT a FROM table WHERE x >= {ts_start} AND x < {ts_end}) AS _sub"
            ),
            "num_pages": 10,
            "page": 1,
            "query_sql": f"SELECT a FROM table WHERE x >= {ts_start} AND x < {ts_end} LIMIT 10",
            "results": [{"field1": "value1"}, {"field2": "value2"}],
            "total": 2,
        }
        self.assertDictEqual(expected, result)

    def test_sql_execute_person_select_type(self):
        """测试 person_select 类型变量的 SQL 执行"""
        config = SQLDataSearchConfig(
            sql="SELECT a FROM table WHERE a IN :a",
            referenced_tables=[{"table_name": "table"}],
            input_variable=[
                SQLDataSearchInputVariable(
                    raw_name="a",
                    display_name="变量A",
                    required=True,
                    field_category=FieldCategory.PERSON_SELECT,
                    choices=[],
                )
            ],
            output_fields=[],
        )
        executor = SqlDataSearchExecutor(source=config, analyzer_cls=self.analyzer_cls)
        params = DataSearchToolExecuteParams(
            tool_variables=[{"raw_name": "a", "value": ["user1", "user2"]}],
            page=1,
            page_size=10,
        )
        result = executor.execute(params).model_dump()
        in_str = "('user1', 'user2')"  # 渲染后 IN 列表
        expected = {
            "count_sql": f"SELECT COUNT(*) AS count FROM (SELECT a FROM table WHERE a IN {in_str}) AS _sub",
            "num_pages": 10,
            "page": 1,
            "query_sql": f"SELECT a FROM table WHERE a IN {in_str} LIMIT 10",
            "results": [{"field1": "value1"}, {"field2": "value2"}],
            "total": 2,
        }
        self.assertDictEqual(expected, result)


class TestBkVisionExecutor(TestCase):
    def setUp(self):
        """设置BK Vision执行器的测试环境"""
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
        BkVisionToolConfig.objects.create(tool=self.vision_tool, panel=self.mock_panel)

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
        self.analyzer_cls = SqlQueryAnalysis

        # SQL 工具（去掉 *）
        self.sql_tool = Tool.objects.create(
            tool_type=ToolTypeEnum.DATA_SEARCH.value,
            name="vision_tool",
            version=1,
            config=SQLDataSearchConfig(
                sql="SELECT a FROM table",
                referenced_tables=[{"table_name": "table"}],
                input_variable=[],
                output_fields=[],
            ).model_dump(),
        )
        DataSearchToolConfig.objects.create(
            tool=self.sql_tool,
            data_search_config_type="sql",
            sql="SELECT a FROM table",
        )

        # Vision 工具
        self.vision_tool = Tool.objects.create(
            tool_type=ToolTypeEnum.BK_VISION.value,
            name="vision_tool",
            version=1,
            config={"uid": "vision_panel_123"},
        )

    def test_create_sql_executor(self):
        """测试工厂创建SQL执行器"""
        factory = ToolExecutorFactory(self.analyzer_cls)
        executor = factory.create_from_tool(self.sql_tool)

        self.assertIsInstance(executor, SqlDataSearchExecutor)
        self.assertEqual(executor.config.sql, "SELECT a FROM table")

    def test_create_vision_executor(self):
        """测试工厂创建BK Vision执行器"""
        factory = ToolExecutorFactory(self.analyzer_cls)
        executor = factory.create_from_tool(self.vision_tool)

        self.assertIsInstance(executor, BkVisionExecutor)
        self.assertEqual(executor.config.uid, "vision_panel_123")

    def test_create_with_unsupported_type(self):
        """测试工厂处理不支持的工具类型"""
        invalid_tool = Tool.objects.create(tool_type="invalid_type", name="invalid_tool", version=1, namespace="test")

        factory = ToolExecutorFactory(self.analyzer_cls)
        with self.assertRaises(ValueError):
            factory.create_from_tool(invalid_tool)

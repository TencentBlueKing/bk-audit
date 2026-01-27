# -*- coding: utf-8 -*-
import json
import os
from unittest import mock
from unittest.mock import MagicMock, patch

import requests
from django.test import TestCase

from api.bk_base.default import QuerySyncResource, UserAuthBatchCheck
from core.sql.parser.praser import SqlQueryAnalysis
from services.web.tool.constants import (
    ApiAuthMethod,
    ApiToolConfig,
    ApiToolErrorType,
    ApiVariablePosition,
    BkVisionConfig,
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
    ToolTypeNotSupport,
)
from services.web.tool.executor.model import (
    APIToolExecuteParams,
    ApiToolExecuteResult,
    BkVisionExecuteResult,
    DataSearchToolExecuteParams,
)
from services.web.tool.executor.parser import ApiVariableParser, SqlVariableParser
from services.web.tool.executor.tool import (
    ApiToolExecutor,
    BkVisionExecutor,
    SqlDataSearchExecutor,
    ToolExecutorFactory,
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

    @mock.patch.object(SqlVariableParser, "_format_input", side_effect=RuntimeError("mock error"))
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
        example_var = {
            "raw_name": "test_field",
            "display_name": "测试字段",
            "description": "字段描述",
            "field_category": "button",
            "required": True,
            "default_value": "default_val",
        }
        example_var2 = {
            "raw_name": "list_field",
            "display_name": "列表字段",
            "description": "列表默认值",
            "field_category": "selector",
            "required": False,
            "default_value": [1, 2, 3],
        }
        self.vision_tool = Tool.objects.create(
            namespace="test",
            name="vision_tool",
            uid="vision_tool_123",
            version=1,
            tool_type=ToolTypeEnum.BK_VISION.value,
            config={"uid": "vision_panel_123", "input_variable": [example_var, example_var2]},
            updated_by="test_user",
        )

        # 创建关联的VisionPanel和BkvisionToolConfig
        self.mock_panel = VisionPanel.objects.create(
            id="panel_123", vision_id="vision_panel_123", scenario="tool", handler="VisionHandler"
        )
        BkVisionToolConfig.objects.create(tool=self.vision_tool, panel=self.mock_panel)

    def test_execute_with_tool_object(self):
        """测试通过Tool对象初始化执行BK Vision查询"""
        with mock.patch("services.web.tool.executor.tool.check_bkvision_share_permission", return_value=True):
            executor = BkVisionExecutor(self.vision_tool)
            result = executor.execute({})
            self.assertIsInstance(result, BkVisionExecuteResult)
            self.assertEqual(result.panel_id, "panel_123")

    def test_execute_with_config_object(self):
        """测试通过配置对象直接初始化执行BK Vision查询"""
        example_var = {
            "raw_name": "test_field",
            "display_name": "测试字段",
            "description": "字段描述",
            "field_category": "button",
            "required": True,
            "default_value": "default_val",
        }
        example_var2 = {
            "raw_name": "list_field",
            "display_name": "列表字段",
            "description": "列表默认值",
            "field_category": "selector",
            "required": False,
            "default_value": [1, 2, 3],
        }
        config = BkVisionConfig(uid="vision_panel_123", input_variable=[example_var, example_var2])
        with mock.patch("services.web.tool.executor.tool.check_bkvision_share_permission", return_value=True):
            with mock.patch.object(Tool, 'fetch_tool_vision_panel', return_value=self.mock_panel):
                executor = BkVisionExecutor(config)
                result = executor.execute({})
                self.assertEqual(result.panel_id, "panel_123")


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
            config={"uid": "vision_panel_123", "input_variable": []},
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
        with self.assertRaises(ToolTypeNotSupport):
            factory.create_from_tool(invalid_tool)


class TestVariableParserPersonSelect(TestCase):
    """测试 person_select 类型变量的解析"""

    def setUp(self):
        """设置测试环境和mock对象"""
        self.analyzer_cls = SqlQueryAnalysis

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

    def test_sql_parser_person_select_with_list(self):
        """测试 SQL 解析器 person_select 类型变量输入为列表"""
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
        in_str = "('user1', 'user2')"
        expected = {
            "count_sql": f"SELECT COUNT(*) AS count FROM (SELECT a FROM table WHERE a IN {in_str}) AS _sub",
            "num_pages": 10,
            "page": 1,
            "query_sql": f"SELECT a FROM table WHERE a IN {in_str} LIMIT 10",
            "results": [{"field1": "value1"}, {"field2": "value2"}],
            "total": 2,
        }
        self.assertDictEqual(expected, result)

    def test_sql_parser_person_select_with_string(self):
        """测试 SQL 解析器 person_select 类型变量输入为字符串（逗号分隔）"""
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
            tool_variables=[{"raw_name": "a", "value": "user1,user2,user3"}],
            page=1,
            page_size=10,
        )
        result = executor.execute(params).model_dump()
        in_str = "('user1', 'user2', 'user3')"
        expected = {
            "count_sql": f"SELECT COUNT(*) AS count FROM (SELECT a FROM table WHERE a IN {in_str}) AS _sub",
            "num_pages": 10,
            "page": 1,
            "query_sql": f"SELECT a FROM table WHERE a IN {in_str} LIMIT 10",
            "results": [{"field1": "value1"}, {"field2": "value2"}],
            "total": 2,
        }
        self.assertDictEqual(expected, result)

    def test_sql_parser_person_select_with_string_spaces(self):
        """测试 SQL 解析器 person_select 类型变量输入为字符串（带空格的逗号分隔）"""
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
            tool_variables=[{"raw_name": "a", "value": "user1 , user2 , user3"}],
            page=1,
            page_size=10,
        )
        result = executor.execute(params).model_dump()
        in_str = "('user1', 'user2', 'user3')"
        expected = {
            "count_sql": f"SELECT COUNT(*) AS count FROM (SELECT a FROM table WHERE a IN {in_str}) AS _sub",
            "num_pages": 10,
            "page": 1,
            "query_sql": f"SELECT a FROM table WHERE a IN {in_str} LIMIT 10",
            "results": [{"field1": "value1"}, {"field2": "value2"}],
            "total": 2,
        }
        self.assertDictEqual(expected, result)

    def test_sql_parser_person_select_single_value(self):
        """测试 SQL 解析器 person_select 类型变量输入为单个非列表值"""
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
            tool_variables=[{"raw_name": "a", "value": "single_user"}],
            page=1,
            page_size=10,
        )
        result = executor.execute(params).model_dump()
        in_str = "('single_user')"
        expected = {
            "count_sql": f"SELECT COUNT(*) AS count FROM (SELECT a FROM table WHERE a IN {in_str}) AS _sub",
            "num_pages": 10,
            "page": 1,
            "query_sql": f"SELECT a FROM table WHERE a IN {in_str} LIMIT 10",
            "results": [{"field1": "value1"}, {"field2": "value2"}],
            "total": 2,
        }
        self.assertDictEqual(expected, result)


class TestApiVariableParserPersonSelect(TestCase):
    """测试 API 工具 person_select 类型变量的解析"""

    def test_api_parser_person_select_with_list(self):
        """测试 API 解析器 person_select 类型变量输入为列表时返回逗号分隔字符串"""
        from services.web.tool.constants import (
            ApiStandardInputVariable,
            ApiVariablePosition,
        )

        variable = ApiStandardInputVariable(
            raw_name="users",
            display_name="用户",
            description="选择用户",
            var_name="users",
            required=True,
            field_category=FieldCategory.PERSON_SELECT,
            is_show=True,
            position=ApiVariablePosition.QUERY,
        )
        parser = ApiVariableParser(variable)
        result = parser.parse(["user1", "user2", "user3"])
        self.assertEqual(result, "user1,user2,user3")

    def test_api_parser_person_select_with_string(self):
        """测试 API 解析器 person_select 类型变量输入为字符串（逗号分隔）"""
        from services.web.tool.constants import (
            ApiStandardInputVariable,
            ApiVariablePosition,
        )

        variable = ApiStandardInputVariable(
            raw_name="users",
            display_name="用户",
            description="选择用户",
            var_name="users",
            required=True,
            field_category=FieldCategory.PERSON_SELECT,
            is_show=True,
            position=ApiVariablePosition.QUERY,
        )
        parser = ApiVariableParser(variable)
        result = parser.parse("user1,user2,user3")
        self.assertEqual(result, "user1,user2,user3")

    def test_api_parser_person_select_with_string_spaces(self):
        """测试 API 解析器 person_select 类型变量输入为字符串（带空格的逗号分隔）"""
        from services.web.tool.constants import (
            ApiStandardInputVariable,
            ApiVariablePosition,
        )

        variable = ApiStandardInputVariable(
            raw_name="users",
            display_name="用户",
            description="选择用户",
            var_name="users",
            required=True,
            field_category=FieldCategory.PERSON_SELECT,
            is_show=True,
            position=ApiVariablePosition.QUERY,
        )
        parser = ApiVariableParser(variable)
        result = parser.parse("user1 , user2 , user3")
        self.assertEqual(result, "user1,user2,user3")

    def test_api_parser_person_select_single_value(self):
        """测试 API 解析器 person_select 类型变量输入为单个非列表/非字符串值"""
        from services.web.tool.constants import (
            ApiStandardInputVariable,
            ApiVariablePosition,
        )

        variable = ApiStandardInputVariable(
            raw_name="users",
            display_name="用户",
            description="选择用户",
            var_name="users",
            required=True,
            field_category=FieldCategory.PERSON_SELECT,
            is_show=True,
            position=ApiVariablePosition.QUERY,
        )
        parser = ApiVariableParser(variable)
        result = parser.parse(12345)
        self.assertEqual(result, "12345")

    def test_api_parser_person_select_single_string_no_comma(self):
        """测试 API 解析器 person_select 类型变量输入为单个用户字符串（无逗号）"""
        from services.web.tool.constants import (
            ApiStandardInputVariable,
            ApiVariablePosition,
        )

        variable = ApiStandardInputVariable(
            raw_name="users",
            display_name="用户",
            description="选择用户",
            var_name="users",
            required=True,
            field_category=FieldCategory.PERSON_SELECT,
            is_show=True,
            position=ApiVariablePosition.QUERY,
        )
        parser = ApiVariableParser(variable)
        result = parser.parse("single_user")
        self.assertEqual(result, "single_user")


class ApiToolExecutorTestCase(TestCase):
    def setUp(self):
        self.tool_uid = "executor_test_uid"
        self.tool_name = "Executor Test API"
        self.test_api_url_template = "http://api.example.com/test/{path_id}"  # Unified name
        self.test_api_method = "POST"
        self.app_code = "test_app"
        self.app_secret = "test_secret"

        self.tool_config = {
            "api_config": {
                "url": self.test_api_url_template,  # Use unified name
                "method": self.test_api_method,
                "auth_config": {
                    "method": ApiAuthMethod.BK_APP_AUTH.value,
                    "config": {"bk_app_code": self.app_code, "bk_app_secret": self.app_secret},
                },
                "headers": [{"key": "Content-Type", "value": "application/json"}],
            },
            "input_variable": [
                {
                    "raw_name": "path_id",
                    "var_name": "path_id",
                    "display_name": "Path ID",
                    "required": True,
                    "field_category": FieldCategory.INPUT.value,
                    "is_show": True,
                    "position": ApiVariablePosition.PATH.value,
                },
                {
                    "raw_name": "query_param",
                    "var_name": "query_param",
                    "display_name": "Query Param",
                    "required": False,
                    "field_category": FieldCategory.INPUT.value,
                    "is_show": True,
                    "position": ApiVariablePosition.QUERY.value,
                },
                {
                    "raw_name": "body_param",
                    "var_name": "body_param",
                    "display_name": "Body Param",
                    "required": True,
                    "field_category": FieldCategory.INPUT.value,
                    "is_show": True,
                    "position": ApiVariablePosition.BODY.value,
                },
                {
                    "raw_name": "time_range_split",
                    "var_name": "time_range_split",
                    "display_name": "Time Range Split",
                    "required": True,
                    "field_category": FieldCategory.TIME_RANGE_SELECT.value,
                    "is_show": True,
                    "position": ApiVariablePosition.QUERY.value,
                    "split_config": {"start_field": "start_time", "end_field": "end_time"},
                },
                {
                    "raw_name": "multiselect_param",
                    "var_name": "multiselect_param",
                    "display_name": "Multiselect Param",
                    "required": False,
                    "field_category": FieldCategory.MULTISELECT.value,
                    "is_show": True,
                    "position": ApiVariablePosition.QUERY.value,
                },
                {
                    "raw_name": "person_select_param",
                    "var_name": "person_select_param",
                    "display_name": "Person Select Param",
                    "required": False,
                    "field_category": FieldCategory.PERSON_SELECT.value,
                    "is_show": True,
                    "position": ApiVariablePosition.QUERY.value,
                },
            ],
            "output_config": {"enable_grouping": False, "groups": []},
        }

        self.tool = Tool.objects.create(
            uid=self.tool_uid,
            version=1,
            name=self.tool_name,
            namespace="default",
            tool_type=ToolTypeEnum.API.value,
            config=ApiToolConfig.model_validate(self.tool_config).model_dump(),
            created_by="admin",
        )

        self.executor = ApiToolExecutor(self.tool)

    @patch('requests.request')
    def test_execute_success(self, mock_requests_request):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.ok = True
        mock_response.json.return_value = {"result": True, "data": "mocked_data"}
        mock_requests_request.return_value = mock_response

        params_data = {
            "tool_variables": [
                {"raw_name": "path_id", "value": "123", "position": ApiVariablePosition.PATH.value},
                {"raw_name": "query_param", "value": "test_query", "position": ApiVariablePosition.QUERY.value},
                {"raw_name": "body_param", "value": {"key": "value"}, "position": ApiVariablePosition.BODY.value},
                {
                    "raw_name": "time_range_split",
                    "value": ["2023-01-01 00:00:00", "2023-01-01 01:00:00"],
                    "position": ApiVariablePosition.QUERY.value,
                },
                {
                    "raw_name": "multiselect_param",
                    "value": ["opt1", "opt2"],
                    "position": ApiVariablePosition.QUERY.value,
                },
            ]
        }

        result = self.executor.execute(params_data)

        self.assertIsInstance(result, ApiToolExecuteResult)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.result, {"result": True, "data": "mocked_data"})
        self.assertEqual(result.err_type, ApiToolErrorType.NONE)
        self.assertEqual(result.message, "")

        # Verify requests.request call
        expected_url = self.test_api_url_template.format(path_id="123")
        expected_headers = {
            "Content-Type": "application/json",
            "X-Bkapi-Authorization": json.dumps(
                {
                    "bk_app_code": self.app_code,
                    "bk_app_secret": self.app_secret,
                }
            ),
        }
        mock_requests_request.assert_called_once_with(
            method=self.test_api_method.lower(),
            url=expected_url,
            headers=expected_headers,
            timeout=int(os.getenv("API_EXECUTE_DEFAULT_TIMEOUT", "120")),
            params={
                "query_param": "test_query",
                "start_time": 1672502400000,  # 2023-01-01 00:00:00 in ms
                "end_time": 1672506000000,  # 2023-01-01 01:00:00 in ms
                "multiselect_param": ["opt1", "opt2"],
            },
            json={"body_param": {"key": "value"}},
        )

    @patch('requests.request')
    def test_execute_failed(self, mock_requests_request):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.ok = False
        mock_json_content = {"code": 404, "message": "Not Found"}
        mock_response.json.return_value = mock_json_content
        mock_response.text = json.dumps(mock_json_content)  # 使用 json.dumps 生成双引号的 JSON 字符串
        mock_requests_request.return_value = mock_response

        params_data = {
            "tool_variables": [
                {"raw_name": "path_id", "value": "404", "position": ApiVariablePosition.PATH.value},
                {"raw_name": "body_param", "value": "some_value", "position": ApiVariablePosition.BODY.value},
                {
                    "raw_name": "time_range_split",
                    "value": ["2023-01-01 00:00:00", "2023-01-01 01:00:00"],
                    "position": ApiVariablePosition.QUERY.value,
                },
            ]
        }

        # 应返回结果，而非抛出异常
        result = self.executor.execute(params_data)
        self.assertEqual(result.status_code, 404)
        self.assertEqual(result.result, mock_json_content)
        self.assertEqual(result.err_type, ApiToolErrorType.NONE)
        self.assertEqual(result.message, "")

    @patch('requests.request')
    def test_execute_non_json_response(self, mock_requests_request):
        mock_response = MagicMock()
        mock_response.status_code = 502
        mock_response.json.side_effect = ValueError("not json")
        mock_response.text = "Bad Gateway"
        mock_requests_request.return_value = mock_response

        params_data = {
            "tool_variables": [
                {"raw_name": "path_id", "value": "non-json", "position": ApiVariablePosition.PATH.value},
                {"raw_name": "body_param", "value": {"k": "v"}, "position": ApiVariablePosition.BODY.value},
                {
                    "raw_name": "time_range_split",
                    "value": ["2023-01-01 00:00:00", "2023-01-01 01:00:00"],
                    "position": ApiVariablePosition.QUERY.value,
                },
            ]
        }

        result = self.executor.execute(params_data)
        self.assertEqual(result.status_code, 502)
        self.assertIsNone(result.result)
        self.assertEqual(result.err_type, ApiToolErrorType.NON_JSON_RESPONSE)
        self.assertEqual(result.message, "Bad Gateway")

    @patch('requests.request')
    def test_execute_request_exception(self, mock_requests_request):
        mock_requests_request.side_effect = requests.RequestException("boom")

        params_data = {
            "tool_variables": [
                {"raw_name": "path_id", "value": "error", "position": ApiVariablePosition.PATH.value},
                {"raw_name": "body_param", "value": {"key": "value"}, "position": ApiVariablePosition.BODY.value},
                {
                    "raw_name": "time_range_split",
                    "value": ["2023-01-01 00:00:00", "2023-01-01 01:00:00"],
                    "position": ApiVariablePosition.QUERY.value,
                },
            ]
        }

        result = self.executor.execute(params_data)
        self.assertEqual(result.status_code, 500)
        self.assertIsNone(result.result)
        self.assertEqual(result.err_type, ApiToolErrorType.REQUEST_ERROR)
        self.assertEqual(result.message, "boom")

    def test_render_request_params_missing_required(self):
        params_data = {
            "tool_variables": [
                {"raw_name": "query_param", "value": "test_query", "position": ApiVariablePosition.QUERY.value},
                # path_id is missing
                {"raw_name": "body_param", "value": "some_value", "position": ApiVariablePosition.BODY.value},
            ]
        }
        params = APIToolExecuteParams.model_validate(params_data)

        with self.assertRaises(InputVariableMissingError):
            self.executor._render_request_params(params)

    def test_render_request_params_time_range_split(self):
        params_data = {
            "tool_variables": [
                {"raw_name": "path_id", "value": "1", "position": ApiVariablePosition.PATH.value},
                {"raw_name": "body_param", "value": "value", "position": ApiVariablePosition.BODY.value},
                {
                    "raw_name": "time_range_split",
                    "value": ["2023-01-01 00:00:00", "2023-01-01 01:00:00"],
                    "position": ApiVariablePosition.QUERY.value,
                },
            ]
        }
        params = APIToolExecuteParams.model_validate(params_data)
        rendered_params = self.executor._render_request_params(params)

        # 转换为字典列表进行比较
        rendered_dicts = [{'name': p.name, 'value': p.value, 'position': p.position} for p in rendered_params]
        expected_params = [
            {'name': 'path_id', 'value': '1', 'position': ApiVariablePosition.PATH},
            {'name': 'body_param', 'value': 'value', 'position': ApiVariablePosition.BODY},
            {'name': 'start_time', 'value': 1672502400000, 'position': ApiVariablePosition.QUERY},
            {'name': 'end_time', 'value': 1672506000000, 'position': ApiVariablePosition.QUERY},
        ]

        # Convert to set of frozensets for order-insensitive comparison of dicts
        self.assertEqual(
            {frozenset(d.items()) for d in rendered_dicts},
            {frozenset(d.items()) for d in expected_params},
        )

        # 确认可选参数 query_param 和 multiselect_param 不存在
        self.assertFalse(any(p.name == 'query_param' for p in rendered_params))
        self.assertFalse(any(p.name == 'multiselect_param' for p in rendered_params))

    def test_render_request_params_multiselect(self):
        params_data = {
            "tool_variables": [
                {"raw_name": "path_id", "value": "1", "position": ApiVariablePosition.PATH.value},
                {"raw_name": "body_param", "value": "value", "position": ApiVariablePosition.BODY.value},
                {
                    "raw_name": "time_range_split",
                    "value": ["2023-01-01 00:00:00", "2023-01-01 01:00:00"],
                    "position": ApiVariablePosition.QUERY.value,
                },
                {
                    "raw_name": "multiselect_param",
                    "value": ["val1", "val2"],
                    "position": ApiVariablePosition.QUERY.value,
                },
            ]
        }
        params = APIToolExecuteParams.model_validate(params_data)
        rendered_params = self.executor._render_request_params(params)

        multiselect_param = next(p for p in rendered_params if p.name == 'multiselect_param')
        self.assertEqual(multiselect_param.value, ['val1', 'val2'])

    def test_render_request_params_optional_missing(self):
        # query_param and multiselect_param are optional and not provided
        params_data = {
            "tool_variables": [
                {"raw_name": "path_id", "value": "1", "position": ApiVariablePosition.PATH.value},
                {"raw_name": "body_param", "value": "some_value", "position": ApiVariablePosition.BODY.value},
                {
                    "raw_name": "time_range_split",
                    "value": ["2023-01-01 00:00:00", "2023-01-01 01:00:00"],
                    "position": ApiVariablePosition.QUERY.value,
                },
            ]
        }
        params = APIToolExecuteParams.model_validate(params_data)
        rendered_params = self.executor._render_request_params(params)

        # Optional params should NOT be present
        self.assertFalse(any(p.name == 'query_param' for p in rendered_params))
        self.assertFalse(any(p.name == 'multiselect_param' for p in rendered_params))

    def test_render_request_params_time_range_optional_missing(self):
        # time_range_optional is optional and not provided
        params_data = {
            "tool_variables": [
                {"raw_name": "path_id", "value": "1", "position": ApiVariablePosition.PATH.value},
                {"raw_name": "query_param", "value": "test_query", "position": ApiVariablePosition.QUERY.value},
                {"raw_name": "body_param", "value": "some_value", "position": ApiVariablePosition.BODY.value},
                {
                    "raw_name": "time_range_split",
                    "value": ["2023-01-01 00:00:00", "2023-01-01 01:00:00"],
                    "position": ApiVariablePosition.QUERY.value,
                },
            ]
        }
        params = APIToolExecuteParams.model_validate(params_data)
        rendered_params = self.executor._render_request_params(params)

        # Check for split_config fields of time_range_optional
        # These should NOT be present
        self.assertFalse(any(p.name == 'body_start' for p in rendered_params))
        self.assertFalse(any(p.name == 'body_end' for p in rendered_params))

    def test_render_request_params_person_select(self):
        """测试 API 工具中人员选择器转换为逗号拼接的字符串"""
        params_data = {
            "tool_variables": [
                {"raw_name": "path_id", "value": "1", "position": ApiVariablePosition.PATH.value},
                {"raw_name": "body_param", "value": "value", "position": ApiVariablePosition.BODY.value},
                {
                    "raw_name": "time_range_split",
                    "value": ["2023-01-01 00:00:00", "2023-01-01 01:00:00"],
                    "position": ApiVariablePosition.QUERY.value,
                },
                {
                    "raw_name": "person_select_param",
                    "value": ["user1", "user2", "user3"],
                    "position": ApiVariablePosition.QUERY.value,
                },
            ]
        }
        params = APIToolExecuteParams.model_validate(params_data)
        rendered_params = self.executor._render_request_params(params)

        person_select_param = next(p for p in rendered_params if p.name == 'person_select_param')
        # 验证人员选择器被转换为逗号拼接的字符串
        self.assertEqual(person_select_param.value, "user1,user2,user3")

    def test_render_request_params_person_select_single_value(self):
        """测试 API 工具中人员选择器单值情况"""
        params_data = {
            "tool_variables": [
                {"raw_name": "path_id", "value": "1", "position": ApiVariablePosition.PATH.value},
                {"raw_name": "body_param", "value": "value", "position": ApiVariablePosition.BODY.value},
                {
                    "raw_name": "time_range_split",
                    "value": ["2023-01-01 00:00:00", "2023-01-01 01:00:00"],
                    "position": ApiVariablePosition.QUERY.value,
                },
                {
                    "raw_name": "person_select_param",
                    "value": "user1",  # 单个值
                    "position": ApiVariablePosition.QUERY.value,
                },
            ]
        }
        params = APIToolExecuteParams.model_validate(params_data)
        rendered_params = self.executor._render_request_params(params)

        person_select_param = next(p for p in rendered_params if p.name == 'person_select_param')
        # 验证单个值被转换为字符串
        self.assertEqual(person_select_param.value, "user1")

    @patch('requests.request')
    def test_execute_with_person_select(self, mock_requests_request):
        """测试 API 工具执行时人员选择器参数传递"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.ok = True
        mock_response.json.return_value = {"result": True, "data": "mocked_data"}
        mock_requests_request.return_value = mock_response

        params_data = {
            "tool_variables": [
                {"raw_name": "path_id", "value": "123", "position": ApiVariablePosition.PATH.value},
                {"raw_name": "body_param", "value": {"key": "value"}, "position": ApiVariablePosition.BODY.value},
                {
                    "raw_name": "time_range_split",
                    "value": ["2023-01-01 00:00:00", "2023-01-01 01:00:00"],
                    "position": ApiVariablePosition.QUERY.value,
                },
                {
                    "raw_name": "person_select_param",
                    "value": ["user1", "user2"],
                    "position": ApiVariablePosition.QUERY.value,
                },
            ]
        }

        result = self.executor.execute(params_data)

        self.assertIsInstance(result, ApiToolExecuteResult)
        self.assertEqual(result.status_code, 200)

        # 验证请求参数中人员选择器被转换为逗号拼接的字符串
        self.test_api_url_template.format(path_id="123")
        mock_requests_request.assert_called_once()
        call_kwargs = mock_requests_request.call_args[1]
        self.assertEqual(call_kwargs['params']['person_select_param'], "user1,user2")


class TestApiToolExecutor(TestCase):
    """测试 API 工具执行器"""

    def setUp(self):
        """设置 API 工具执行器的测试环境"""
        from services.web.tool.constants import (
            ApiAuthMethod,
            ApiConfig,
            ApiOutputConfiguration,
            ApiRequestMethod,
            ApiStandardInputVariable,
            ApiToolConfig,
            ApiVariablePosition,
            BkAppAuthConfig,
            BkAuthItem,
            HmacSignatureAuthConfig,
            HmacSignatureAuthItem,
            NoAuthItem,
            ParamField,
        )

        # 创建基础配置
        self.base_input_variable = ApiStandardInputVariable(
            raw_name="user_id",
            display_name="用户ID",
            description="用户唯一标识",
            var_name="user_id",
            required=True,
            field_category=FieldCategory.INPUT,
            is_show=True,
            position=ApiVariablePosition.QUERY,
        )

        self.output_config = ApiOutputConfiguration(
            enable_grouping=False,
            groups=[],
            result_schema={},
        )

        # 无认证配置
        self.no_auth_config = ApiToolConfig(
            api_config=ApiConfig(
                url="https://api.example.com/v1/users",
                method=ApiRequestMethod.GET,
                auth_config=NoAuthItem(method=ApiAuthMethod.NONE),
                headers=[ParamField(key="Content-Type", value="application/json")],
            ),
            input_variable=[self.base_input_variable],
            output_config=self.output_config,
        )

        # 蓝鲸应用认证配置
        self.bk_auth_config = ApiToolConfig(
            api_config=ApiConfig(
                url="https://api.example.com/v1/users",
                method=ApiRequestMethod.POST,
                auth_config=BkAuthItem(
                    method=ApiAuthMethod.BK_APP_AUTH,
                    config=BkAppAuthConfig(
                        bk_app_code="test_app",
                        bk_app_secret="test_secret_12345",
                    ),
                ),
                headers=[ParamField(key="Content-Type", value="application/json")],
            ),
            input_variable=[self.base_input_variable],
            output_config=self.output_config,
        )

        # HMAC签名认证配置
        self.hmac_auth_config = ApiToolConfig(
            api_config=ApiConfig(
                url="https://api.example.com/v1/users",
                method=ApiRequestMethod.POST,
                auth_config=HmacSignatureAuthItem(
                    method=ApiAuthMethod.HMAC_SIGNATURE,
                    config=HmacSignatureAuthConfig(
                        secret_id="test_secret_id",
                        secret_key="test_secret_key",
                        app_code="test_app_code",
                    ),
                ),
                headers=[ParamField(key="Content-Type", value="application/json")],
            ),
            input_variable=[self.base_input_variable],
            output_config=self.output_config,
        )

    def tearDown(self):
        mock.patch.stopall()

    @mock.patch('services.web.tool.executor.tool.requests.request')
    def test_execute_with_no_auth(self, mock_request):
        """测试无认证方式执行API工具"""
        from services.web.tool.executor.tool import ApiToolExecutor

        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"code": 0, "data": {"user": "test_user"}}
        mock_request.return_value = mock_response

        executor = ApiToolExecutor(self.no_auth_config.model_dump())
        params = {"tool_variables": [{"raw_name": "user_id", "value": "12345"}]}
        result = executor.execute(params)

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.result, {"code": 0, "data": {"user": "test_user"}})

        # 验证请求调用
        mock_request.assert_called_once()
        call_kwargs = mock_request.call_args
        self.assertEqual(call_kwargs[1]["method"], "get")
        self.assertEqual(call_kwargs[1]["url"], "https://api.example.com/v1/users")
        self.assertIn("Content-Type", call_kwargs[1]["headers"])
        # 无认证不应添加 Authorization 头
        self.assertNotIn("Authorization", call_kwargs[1]["headers"])

    @mock.patch('services.web.tool.executor.tool.requests.request')
    def test_execute_with_bk_app_auth(self, mock_request):
        """测试蓝鲸应用认证方式执行API工具"""
        import json

        from services.web.tool.executor.tool import ApiToolExecutor

        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"code": 0, "message": "success"}
        mock_request.return_value = mock_response

        executor = ApiToolExecutor(self.bk_auth_config.model_dump())
        params = {"tool_variables": [{"raw_name": "user_id", "value": "12345"}]}
        result = executor.execute(params)

        self.assertEqual(result.status_code, 200)

        # 验证请求调用
        mock_request.assert_called_once()
        call_kwargs = mock_request.call_args
        headers = call_kwargs[1]["headers"]
        self.assertIn("X-Bkapi-Authorization", headers)

        # 验证认证信息
        auth_data = json.loads(headers["X-Bkapi-Authorization"])
        self.assertEqual(auth_data["bk_app_code"], "test_app")
        self.assertEqual(auth_data["bk_app_secret"], "test_secret_12345")

    @mock.patch('services.web.tool.executor.tool.requests.request')
    def test_execute_with_hmac_signature_auth(self, mock_request):
        """测试HMAC签名认证方式执行API工具"""
        from services.web.tool.executor.tool import ApiToolExecutor

        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"code": 0, "message": "success"}
        mock_request.return_value = mock_response

        executor = ApiToolExecutor(self.hmac_auth_config.model_dump())
        params = {"tool_variables": [{"raw_name": "user_id", "value": "12345"}]}
        result = executor.execute(params)

        self.assertEqual(result.status_code, 200)

        # 验证请求调用
        mock_request.assert_called_once()
        call_kwargs = mock_request.call_args
        headers = call_kwargs[1]["headers"]

        # 验证HMAC签名认证头
        self.assertIn("Authorization", headers)
        self.assertIn("Date", headers)
        self.assertIn("X-APP-CODE", headers)
        self.assertEqual(headers["X-APP-CODE"], "test_app_code")

        # 验证Authorization格式
        auth_header = headers["Authorization"]
        self.assertIn('Signature keyId="test_secret_id"', auth_header)
        self.assertIn('algorithm="hmac-sha256"', auth_header)
        self.assertIn('headers="(request-target) host date"', auth_header)
        self.assertIn('signature="', auth_header)

    @mock.patch('services.web.tool.executor.tool.requests.request')
    def test_execute_with_hmac_auth_without_app_code(self, mock_request):
        """测试HMAC签名认证方式执行API工具（不带app_code）"""
        from services.web.tool.constants import (
            ApiAuthMethod,
            ApiConfig,
            ApiOutputConfiguration,
            ApiRequestMethod,
            ApiStandardInputVariable,
            ApiToolConfig,
            ApiVariablePosition,
            HmacSignatureAuthConfig,
            HmacSignatureAuthItem,
        )
        from services.web.tool.executor.tool import ApiToolExecutor

        config = ApiToolConfig(
            api_config=ApiConfig(
                url="https://api.example.com/v1/users",
                method=ApiRequestMethod.POST,
                auth_config=HmacSignatureAuthItem(
                    method=ApiAuthMethod.HMAC_SIGNATURE,
                    config=HmacSignatureAuthConfig(
                        secret_id="test_id",
                        secret_key="test_key",
                        app_code="",  # 空app_code
                    ),
                ),
                headers=[],
            ),
            input_variable=[
                ApiStandardInputVariable(
                    raw_name="data",
                    display_name="数据",
                    description="",
                    var_name="data",
                    required=True,
                    field_category=FieldCategory.INPUT,
                    is_show=True,
                    position=ApiVariablePosition.BODY,
                )
            ],
            output_config=ApiOutputConfiguration(enable_grouping=False, groups=[]),
        )

        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"code": 0}
        mock_request.return_value = mock_response

        executor = ApiToolExecutor(config.model_dump())
        params = {"tool_variables": [{"raw_name": "data", "value": "test_data"}]}
        result = executor.execute(params)

        self.assertEqual(result.status_code, 200)

        # 验证请求调用
        call_kwargs = mock_request.call_args
        headers = call_kwargs[1]["headers"]

        # 验证没有X-APP-CODE头
        self.assertNotIn("X-APP-CODE", headers)
        # 但应该有Authorization和Date头
        self.assertIn("Authorization", headers)
        self.assertIn("Date", headers)

    @mock.patch('services.web.tool.executor.tool.requests.request')
    def test_execute_with_path_params(self, mock_request):
        """测试带路径参数的API工具执行"""
        from services.web.tool.constants import (
            ApiAuthMethod,
            ApiConfig,
            ApiOutputConfiguration,
            ApiRequestMethod,
            ApiStandardInputVariable,
            ApiToolConfig,
            ApiVariablePosition,
            NoAuthItem,
        )
        from services.web.tool.executor.tool import ApiToolExecutor

        config = ApiToolConfig(
            api_config=ApiConfig(
                url="https://api.example.com/v1/users/{user_id}/profile",
                method=ApiRequestMethod.GET,
                auth_config=NoAuthItem(method=ApiAuthMethod.NONE),
                headers=[],
            ),
            input_variable=[
                ApiStandardInputVariable(
                    raw_name="user_id",
                    display_name="用户ID",
                    description="",
                    var_name="user_id",
                    required=True,
                    field_category=FieldCategory.INPUT,
                    is_show=True,
                    position=ApiVariablePosition.PATH,
                )
            ],
            output_config=ApiOutputConfiguration(enable_grouping=False, groups=[]),
        )

        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"profile": {"name": "test"}}
        mock_request.return_value = mock_response

        executor = ApiToolExecutor(config.model_dump())
        params = {"tool_variables": [{"raw_name": "user_id", "value": "12345"}]}
        result = executor.execute(params)

        self.assertEqual(result.status_code, 200)

        # 验证URL中的路径参数被正确替换
        call_kwargs = mock_request.call_args
        self.assertEqual(call_kwargs[1]["url"], "https://api.example.com/v1/users/12345/profile")

    @mock.patch('services.web.tool.executor.tool.requests.request')
    def test_execute_with_body_params(self, mock_request):
        """测试带请求体参数的API工具执行"""
        from services.web.tool.constants import (
            ApiAuthMethod,
            ApiConfig,
            ApiOutputConfiguration,
            ApiRequestMethod,
            ApiStandardInputVariable,
            ApiToolConfig,
            ApiVariablePosition,
            NoAuthItem,
        )
        from services.web.tool.executor.tool import ApiToolExecutor

        config = ApiToolConfig(
            api_config=ApiConfig(
                url="https://api.example.com/v1/users",
                method=ApiRequestMethod.POST,
                auth_config=NoAuthItem(method=ApiAuthMethod.NONE),
                headers=[],
            ),
            input_variable=[
                ApiStandardInputVariable(
                    raw_name="username",
                    display_name="用户名",
                    description="",
                    var_name="username",
                    required=True,
                    field_category=FieldCategory.INPUT,
                    is_show=True,
                    position=ApiVariablePosition.BODY,
                ),
                ApiStandardInputVariable(
                    raw_name="age",
                    display_name="年龄",
                    description="",
                    var_name="age",
                    required=True,
                    field_category=FieldCategory.NUMBER_INPUT,
                    is_show=True,
                    position=ApiVariablePosition.BODY,
                ),
            ],
            output_config=ApiOutputConfiguration(enable_grouping=False, groups=[]),
        )

        mock_response = mock.Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": 1, "username": "test"}
        mock_request.return_value = mock_response

        executor = ApiToolExecutor(config.model_dump())
        params = {
            "tool_variables": [
                {"raw_name": "username", "value": "test_user"},
                {"raw_name": "age", "value": 25},
            ]
        }
        result = executor.execute(params)

        self.assertEqual(result.status_code, 201)

        # 验证请求体参数
        call_kwargs = mock_request.call_args
        self.assertEqual(call_kwargs[1]["json"], {"username": "test_user", "age": 25})

    @mock.patch('services.web.tool.executor.tool.requests.request')
    def test_execute_with_query_params(self, mock_request):
        """测试带查询参数的API工具执行"""
        from services.web.tool.constants import (
            ApiAuthMethod,
            ApiConfig,
            ApiOutputConfiguration,
            ApiRequestMethod,
            ApiStandardInputVariable,
            ApiToolConfig,
            ApiVariablePosition,
            NoAuthItem,
        )
        from services.web.tool.executor.tool import ApiToolExecutor

        config = ApiToolConfig(
            api_config=ApiConfig(
                url="https://api.example.com/v1/users",
                method=ApiRequestMethod.GET,
                auth_config=NoAuthItem(method=ApiAuthMethod.NONE),
                headers=[],
            ),
            input_variable=[
                ApiStandardInputVariable(
                    raw_name="page",
                    display_name="页码",
                    description="",
                    var_name="page",
                    required=True,
                    field_category=FieldCategory.NUMBER_INPUT,
                    is_show=True,
                    position=ApiVariablePosition.QUERY,
                ),
                ApiStandardInputVariable(
                    raw_name="size",
                    display_name="每页数量",
                    description="",
                    var_name="page_size",
                    required=True,
                    field_category=FieldCategory.NUMBER_INPUT,
                    is_show=True,
                    position=ApiVariablePosition.QUERY,
                ),
            ],
            output_config=ApiOutputConfiguration(enable_grouping=False, groups=[]),
        )

        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"users": [], "total": 0}
        mock_request.return_value = mock_response

        executor = ApiToolExecutor(config.model_dump())
        params = {
            "tool_variables": [
                {"raw_name": "page", "value": 1},
                {"raw_name": "size", "value": 10},
            ]
        }
        result = executor.execute(params)

        self.assertEqual(result.status_code, 200)

        # 验证查询参数
        call_kwargs = mock_request.call_args
        self.assertEqual(call_kwargs[1]["params"], {"page": 1, "page_size": 10})

    @mock.patch('services.web.tool.executor.tool.requests.request')
    def test_execute_missing_required_variable(self, mock_request):
        """测试缺少必填变量时抛出异常"""
        from services.web.tool.executor.tool import ApiToolExecutor

        executor = ApiToolExecutor(self.no_auth_config.model_dump())
        params = {"tool_variables": []}  # 没有提供必填的 user_id

        with self.assertRaises(InputVariableMissingError) as cm:
            executor.execute(params)
        self.assertIn("用户ID", cm.exception.message)

    @mock.patch('services.web.tool.executor.tool.requests.request')
    def test_execute_non_json_response(self, mock_request):
        """测试响应非JSON时的处理"""
        from services.web.tool.constants import ApiToolErrorType
        from services.web.tool.executor.tool import ApiToolExecutor

        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.text = "Plain text response"
        mock_request.return_value = mock_response

        executor = ApiToolExecutor(self.no_auth_config.model_dump())
        params = {"tool_variables": [{"raw_name": "user_id", "value": "12345"}]}
        result = executor.execute(params)

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.err_type, ApiToolErrorType.NON_JSON_RESPONSE)
        self.assertEqual(result.message, "Plain text response")
        self.assertIsNone(result.result)

    @mock.patch('services.web.tool.executor.tool.requests.request')
    def test_execute_request_error(self, mock_request):
        """测试请求异常时的处理"""
        import requests as req

        from services.web.tool.constants import ApiToolErrorType
        from services.web.tool.executor.tool import ApiToolExecutor

        mock_request.side_effect = req.RequestException("Connection timeout")

        executor = ApiToolExecutor(self.no_auth_config.model_dump())
        params = {"tool_variables": [{"raw_name": "user_id", "value": "12345"}]}
        result = executor.execute(params)

        self.assertEqual(result.status_code, 500)
        self.assertEqual(result.err_type, ApiToolErrorType.REQUEST_ERROR)
        self.assertIn("Connection timeout", result.message)

    @mock.patch('services.web.tool.executor.tool.requests.request')
    def test_execute_hmac_auth_url_parsing(self, mock_request):
        """测试HMAC认证自动从URL解析host和path"""
        from services.web.tool.constants import (
            ApiAuthMethod,
            ApiConfig,
            ApiOutputConfiguration,
            ApiRequestMethod,
            ApiStandardInputVariable,
            ApiToolConfig,
            ApiVariablePosition,
            HmacSignatureAuthConfig,
            HmacSignatureAuthItem,
        )
        from services.web.tool.executor.tool import ApiToolExecutor

        # 使用不同的URL来验证解析
        config = ApiToolConfig(
            api_config=ApiConfig(
                url="https://prod-api.example.com:8080/api/v2/blacklist/create",
                method=ApiRequestMethod.POST,
                auth_config=HmacSignatureAuthItem(
                    method=ApiAuthMethod.HMAC_SIGNATURE,
                    config=HmacSignatureAuthConfig(
                        secret_id="prod_id",
                        secret_key="prod_key",
                        app_code="prod_app",
                    ),
                ),
                headers=[],
            ),
            input_variable=[
                ApiStandardInputVariable(
                    raw_name="data",
                    display_name="数据",
                    description="",
                    var_name="data",
                    required=True,
                    field_category=FieldCategory.INPUT,
                    is_show=True,
                    position=ApiVariablePosition.BODY,
                )
            ],
            output_config=ApiOutputConfiguration(enable_grouping=False, groups=[]),
        )

        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"code": 0}
        mock_request.return_value = mock_response

        executor = ApiToolExecutor(config.model_dump())
        params = {"tool_variables": [{"raw_name": "data", "value": "test"}]}
        result = executor.execute(params)

        self.assertEqual(result.status_code, 200)

        # 验证请求头
        call_kwargs = mock_request.call_args
        headers = call_kwargs[1]["headers"]
        auth_header = headers["Authorization"]

        # 签名应该包含正确的host（含端口）和path
        # 签名字符串格式: (request-target): post /api/v2/blacklist/create\nhost: prod-api.example.com:8080\ndate: ...
        self.assertIn('Signature keyId="prod_id"', auth_header)


class TestApiToolExecutorWithTool(TestCase):
    """测试通过Tool对象创建API工具执行器"""

    def setUp(self):
        """设置测试环境"""
        from services.web.tool.constants import (
            ApiAuthMethod,
            ApiConfig,
            ApiOutputConfiguration,
            ApiRequestMethod,
            ApiStandardInputVariable,
            ApiToolConfig,
            ApiVariablePosition,
            HmacSignatureAuthConfig,
            HmacSignatureAuthItem,
            ParamField,
        )

        self.api_tool_config = ApiToolConfig(
            api_config=ApiConfig(
                url="https://api.example.com/v1/data",
                method=ApiRequestMethod.POST,
                auth_config=HmacSignatureAuthItem(
                    method=ApiAuthMethod.HMAC_SIGNATURE,
                    config=HmacSignatureAuthConfig(
                        secret_id="tool_secret_id",
                        secret_key="tool_secret_key",
                        app_code="tool_app",
                    ),
                ),
                headers=[ParamField(key="X-Custom-Header", value="custom_value")],
            ),
            input_variable=[
                ApiStandardInputVariable(
                    raw_name="name",
                    display_name="名称",
                    description="",
                    var_name="name",
                    required=True,
                    field_category=FieldCategory.INPUT,
                    is_show=True,
                    position=ApiVariablePosition.BODY,
                )
            ],
            output_config=ApiOutputConfiguration(enable_grouping=False, groups=[]),
        )

        self.api_tool = Tool.objects.create(
            namespace="test",
            name="api_tool",
            uid="api_tool_123",
            version=1,
            tool_type=ToolTypeEnum.API.value,
            config=self.api_tool_config.model_dump(),
            updated_by="test_user",
        )

    def tearDown(self):
        mock.patch.stopall()

    @mock.patch('services.web.tool.executor.tool.requests.request')
    def test_create_executor_from_tool(self, mock_request):
        """测试通过Tool对象创建执行器并执行"""
        from services.web.tool.executor.tool import ApiToolExecutor

        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"code": 0, "data": "success"}
        mock_request.return_value = mock_response

        executor = ApiToolExecutor(self.api_tool)
        params = {"tool_variables": [{"raw_name": "name", "value": "test_name"}]}
        result = executor.execute(params)

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.result, {"code": 0, "data": "success"})

        # 验证HMAC认证头
        call_kwargs = mock_request.call_args
        headers = call_kwargs[1]["headers"]
        self.assertIn("Authorization", headers)
        self.assertIn("X-APP-CODE", headers)
        self.assertEqual(headers["X-APP-CODE"], "tool_app")
        self.assertIn("X-Custom-Header", headers)
        self.assertEqual(headers["X-Custom-Header"], "custom_value")

    @mock.patch('services.web.tool.executor.tool.requests.request')
    def test_create_executor_from_factory(self, mock_request):
        """测试通过工厂创建API执行器"""
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"code": 0}
        mock_request.return_value = mock_response

        analyzer_cls = SqlQueryAnalysis
        factory = ToolExecutorFactory(analyzer_cls)
        executor = factory.create_from_tool(self.api_tool)

        from services.web.tool.executor.tool import ApiToolExecutor

        self.assertIsInstance(executor, ApiToolExecutor)

        params = {"tool_variables": [{"raw_name": "name", "value": "factory_test"}]}
        result = executor.execute(params)

        self.assertEqual(result.status_code, 200)


class TestApiToolExecutorTimeRange(TestCase):
    """测试时间范围变量的API工具执行"""

    @mock.patch('services.web.tool.executor.tool.requests.request')
    def test_execute_with_time_range_variable(self, mock_request):
        """测试时间范围变量拆分为开始和结束时间"""
        from services.web.tool.constants import (
            ApiAuthMethod,
            ApiConfig,
            ApiOutputConfiguration,
            ApiRequestMethod,
            ApiToolConfig,
            ApiVariablePosition,
            NoAuthItem,
            TimeRangeInputVariable,
            TimeRangeSplitConfig,
        )
        from services.web.tool.executor.tool import ApiToolExecutor

        config = ApiToolConfig(
            api_config=ApiConfig(
                url="https://api.example.com/v1/logs",
                method=ApiRequestMethod.GET,
                auth_config=NoAuthItem(method=ApiAuthMethod.NONE),
                headers=[],
            ),
            input_variable=[
                TimeRangeInputVariable(
                    raw_name="time_range",
                    display_name="时间范围",
                    description="",
                    required=True,
                    is_show=True,
                    position=ApiVariablePosition.QUERY,
                    split_config=TimeRangeSplitConfig(
                        start_field="start_time",
                        end_field="end_time",
                    ),
                )
            ],
            output_config=ApiOutputConfiguration(enable_grouping=False, groups=[]),
        )

        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"logs": []}
        mock_request.return_value = mock_response

        executor = ApiToolExecutor(config.model_dump())
        # 时间范围值: [开始时间戳, 结束时间戳]
        params = {"tool_variables": [{"raw_name": "time_range", "value": [1704067200000, 1704153600000]}]}
        result = executor.execute(params)

        self.assertEqual(result.status_code, 200)

        # 验证时间范围被拆分为两个查询参数
        call_kwargs = mock_request.call_args
        query_params = call_kwargs[1]["params"]
        self.assertIn("start_time", query_params)
        self.assertIn("end_time", query_params)
        self.assertEqual(query_params["start_time"], 1704067200000)
        self.assertEqual(query_params["end_time"], 1704153600000)

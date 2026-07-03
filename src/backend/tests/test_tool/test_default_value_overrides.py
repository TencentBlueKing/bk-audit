# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
Copyright (C) 2023 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""
from unittest import mock

from django.test import TestCase

from services.web.tool.constants import (
    ApiToolConfig,
    BkVisionConfig,
    DefaultValueOverrides,
    SmartPageToolConfig,
    SQLDataSearchConfig,
    SQLDataSearchInputVariable,
    SQLDataSearchOutputField,
    Table,
)
from services.web.tool.resources import ExecuteTool, GetToolDetail


class MockTool:
    """模拟 Tool 对象用于测试"""

    def __init__(self, config, tool_type="data_search"):
        self.config = config
        self.tool_type = tool_type


class DefaultValueOverridesModelTest(TestCase):
    """测试 DefaultValueOverrides 模型"""

    def test_default_values(self):
        """测试默认值为空字典"""
        overrides = DefaultValueOverrides()
        self.assertEqual(overrides.scenes, {})
        self.assertEqual(overrides.systems, {})

    def test_with_scene_overrides(self):
        """测试带场景覆盖的配置"""
        overrides = DefaultValueOverrides(
            scenes={
                "1001": {"username": "admin", "limit": 100},
                "1002": {"username": "user1"},
            }
        )
        self.assertEqual(len(overrides.scenes), 2)
        self.assertEqual(overrides.scenes["1001"]["username"], "admin")
        self.assertEqual(overrides.scenes["1001"]["limit"], 100)
        self.assertEqual(overrides.systems, {})

    def test_with_system_overrides(self):
        """测试带系统覆盖的配置"""
        overrides = DefaultValueOverrides(
            systems={
                "sys001": {"env": "prod"},
                "sys002": {"env": "test", "debug": True},
            }
        )
        self.assertEqual(overrides.scenes, {})
        self.assertEqual(len(overrides.systems), 2)
        self.assertEqual(overrides.systems["sys001"]["env"], "prod")

    def test_with_both_overrides(self):
        """测试同时带场景和系统覆盖的配置"""
        overrides = DefaultValueOverrides(
            scenes={"1001": {"username": "admin"}},
            systems={"sys001": {"env": "prod"}},
        )
        self.assertEqual(len(overrides.scenes), 1)
        self.assertEqual(len(overrides.systems), 1)

    def test_model_dump(self):
        """测试 model_dump 正确序列化"""
        overrides = DefaultValueOverrides(
            scenes={"1001": {"username": "admin"}},
            systems={"sys001": {"env": "prod"}},
        )
        data = overrides.model_dump()
        self.assertEqual(data["scenes"]["1001"]["username"], "admin")
        self.assertEqual(data["systems"]["sys001"]["env"], "prod")


class SQLDataSearchConfigWithOverridesTest(TestCase):
    """测试 SQLDataSearchConfig 支持 default_value_overrides"""

    def test_create_with_default_value_overrides(self):
        """测试创建带默认值覆盖的 SQL 工具配置"""
        config = SQLDataSearchConfig(
            sql="SELECT * FROM table WHERE username = :username",
            referenced_tables=[Table(table_name="test_table")],
            input_variable=[
                SQLDataSearchInputVariable(
                    raw_name="username",
                    display_name="用户名",
                    required=True,
                    field_category="input",
                    default_value="default_user",
                )
            ],
            output_fields=[SQLDataSearchOutputField(raw_name="col1", display_name="列1")],
            default_value_overrides=DefaultValueOverrides(
                scenes={"1001": {"username": "admin"}},
                systems={"sys001": {"username": "system_user"}},
            ),
        )
        self.assertEqual(config.default_value_overrides.scenes["1001"]["username"], "admin")
        self.assertEqual(config.default_value_overrides.systems["sys001"]["username"], "system_user")

    def test_create_without_default_value_overrides(self):
        """测试创建不带默认值覆盖的 SQL 工具配置（应使用默认值）"""
        config = SQLDataSearchConfig(
            sql="SELECT * FROM table",
            referenced_tables=[Table(table_name="test_table")],
            input_variable=[],
            output_fields=[SQLDataSearchOutputField(raw_name="col1", display_name="列1")],
        )
        self.assertEqual(config.default_value_overrides.scenes, {})
        self.assertEqual(config.default_value_overrides.systems, {})

    def test_model_validate_with_default_value_overrides(self):
        """测试使用 model_validate 解析带默认值覆盖的配置"""
        config_dict = {
            "sql": "SELECT * FROM table WHERE username = :username",
            "referenced_tables": [{"table_name": "test_table"}],
            "input_variable": [
                {
                    "raw_name": "username",
                    "display_name": "用户名",
                    "required": True,
                    "field_category": "input",
                    "default_value": "default_user",
                }
            ],
            "output_fields": [{"raw_name": "col1", "display_name": "列1"}],
            "default_value_overrides": {
                "scenes": {"1001": {"username": "admin"}},
                "systems": {"sys001": {"username": "system_user"}},
            },
        }
        config = SQLDataSearchConfig.model_validate(config_dict)
        self.assertEqual(config.default_value_overrides.scenes["1001"]["username"], "admin")

    def test_model_validate_without_default_value_overrides(self):
        """测试使用 model_validate 解析不带默认值覆盖的配置"""
        config_dict = {
            "sql": "SELECT * FROM table",
            "referenced_tables": [{"table_name": "test_table"}],
            "input_variable": [],
            "output_fields": [{"raw_name": "col1", "display_name": "列1"}],
        }
        config = SQLDataSearchConfig.model_validate(config_dict)
        self.assertEqual(config.default_value_overrides.scenes, {})
        self.assertEqual(config.default_value_overrides.systems, {})


class BkVisionConfigWithOverridesTest(TestCase):
    """测试 BkVisionConfig 支持 default_value_overrides"""

    def test_create_with_default_value_overrides(self):
        """测试创建带默认值覆盖的 BK Vision 工具配置"""
        from services.web.tool.constants import BKVisionInputVariable

        config = BkVisionConfig(
            uid="panel_123",
            input_variable=[
                BKVisionInputVariable(
                    raw_name="time_range",
                    display_name="时间范围",
                    field_category="time-ranger",
                )
            ],
            default_value_overrides=DefaultValueOverrides(
                scenes={"1001": {"time_range": "last_7_days"}},
            ),
        )
        self.assertEqual(config.default_value_overrides.scenes["1001"]["time_range"], "last_7_days")

    def test_model_validate_with_default_value_overrides(self):
        """测试使用 model_validate 解析带默认值覆盖的 BK Vision 配置"""
        config_dict = {
            "uid": "panel_123",
            "input_variable": [],
            "default_value_overrides": {
                "scenes": {"1001": {"time_range": "last_7_days"}},
            },
        }
        config = BkVisionConfig.model_validate(config_dict)
        self.assertEqual(config.default_value_overrides.scenes["1001"]["time_range"], "last_7_days")


class ApiToolConfigWithOverridesTest(TestCase):
    """测试 ApiToolConfig 支持 default_value_overrides"""

    def test_create_with_default_value_overrides(self):
        """测试创建带默认值覆盖的 API 工具配置"""
        from services.web.tool.constants import (
            ApiConfig,
            ApiOutputConfiguration,
            ApiRequestMethod,
            ApiStandardInputVariable,
            FieldCategory,
        )

        config = ApiToolConfig(
            api_config=ApiConfig(
                url="http://example.com/api",
                method=ApiRequestMethod.GET,
                auth_config={"method": "none"},
                headers=[],
            ),
            input_variable=[
                ApiStandardInputVariable(
                    raw_name="query",
                    display_name="查询参数",
                    required=True,
                    var_name="q",
                    field_category=FieldCategory.INPUT,
                    is_show=True,
                    position="query",
                )
            ],
            output_config=ApiOutputConfiguration(enable_grouping=False, groups=[]),
            default_value_overrides=DefaultValueOverrides(
                systems={"sys001": {"q": "default_query"}},
            ),
        )
        self.assertEqual(config.default_value_overrides.systems["sys001"]["q"], "default_query")

    def test_model_validate_with_default_value_overrides(self):
        """测试使用 model_validate 解析带默认值覆盖的 API 配置"""
        config_dict = {
            "api_config": {
                "url": "http://example.com/api",
                "method": "GET",
                "auth_config": {"method": "none"},
                "headers": [],
            },
            "input_variable": [],
            "output_config": {"enable_grouping": False, "groups": []},
            "default_value_overrides": {
                "systems": {"sys001": {"q": "default_query"}},
            },
        }
        config = ApiToolConfig.model_validate(config_dict)
        self.assertEqual(config.default_value_overrides.systems["sys001"]["q"], "default_query")


class SmartPageToolConfigWithOverridesTest(TestCase):
    """测试 SmartPageToolConfig 支持 default_value_overrides"""

    def test_create_with_default_value_overrides(self):
        """测试创建带默认值覆盖的智能页面工具配置"""
        config = SmartPageToolConfig(
            data_sources=[],
            default_value_overrides=DefaultValueOverrides(
                scenes={"1001": {"page_size": 20}},
            ),
        )
        self.assertEqual(config.default_value_overrides.scenes["1001"]["page_size"], 20)

    def test_model_validate_with_default_value_overrides(self):
        """测试使用 model_validate 解析带默认值覆盖的智能页面配置"""
        config_dict = {
            "data_sources": [],
            "default_value_overrides": {
                "scenes": {"1001": {"page_size": 20}},
            },
        }
        config = SmartPageToolConfig.model_validate(config_dict)
        self.assertEqual(config.default_value_overrides.scenes["1001"]["page_size"], 20)


class GetToolDetailOverrideDefaultValuesTest(TestCase):
    """测试 GetToolDetail._override_default_values 方法"""

    def setUp(self):
        """设置测试数据"""
        self.tool = mock.MagicMock()
        self.tool.config = {
            "input_variable": [
                {"raw_name": "username", "default_value": "default_user"},
                {"raw_name": "limit", "default_value": 50},
                {"raw_name": "env", "default_value": "test"},
            ],
            "default_value_overrides": {
                "scenes": {
                    "1001": {"username": "admin", "limit": 100},
                },
                "systems": {
                    "sys001": {"env": "prod", "limit": 200},
                },
            },
        }

    def test_override_by_scene_id(self):
        """测试根据 scene_id 覆盖默认值"""
        resource = GetToolDetail()
        resource._override_default_values(self.tool, "1001", None)

        # 验证场景级别的覆盖生效
        input_vars = self.tool.config["input_variable"]
        self.assertEqual(input_vars[0]["default_value"], "admin")
        self.assertEqual(input_vars[1]["default_value"], 100)
        # env 没有在场景覆盖中，保持原默认值
        self.assertEqual(input_vars[2]["default_value"], "test")

    def test_override_by_system_id(self):
        """测试根据 system_id 覆盖默认值"""
        resource = GetToolDetail()
        resource._override_default_values(self.tool, None, "sys001")

        input_vars = self.tool.config["input_variable"]
        # env 应该被系统覆盖
        self.assertEqual(input_vars[2]["default_value"], "prod")
        # limit 应该被系统覆盖
        self.assertEqual(input_vars[1]["default_value"], 200)

    def test_system_override_takes_precedence(self):
        """测试系统覆盖优先级高于场景覆盖"""
        self.tool.config["default_value_overrides"]["systems"]["sys001"] = {
            "username": "system_admin",
            "limit": 200,
        }
        resource = GetToolDetail()
        resource._override_default_values(self.tool, "1001", "sys001")

        input_vars = self.tool.config["input_variable"]
        # 系统覆盖应该覆盖场景覆盖
        self.assertEqual(input_vars[0]["default_value"], "system_admin")
        self.assertEqual(input_vars[1]["default_value"], 200)

    def test_no_override_without_scene_or_system(self):
        """测试不传 scene_id 和 system_id 时不覆盖"""
        resource = GetToolDetail()
        resource._override_default_values(self.tool, None, None)

        input_vars = self.tool.config["input_variable"]
        # 应保持原默认值
        self.assertEqual(input_vars[0]["default_value"], "default_user")
        self.assertEqual(input_vars[1]["default_value"], 50)

    def test_no_default_value_overrides_configured(self):
        """测试工具未配置 default_value_overrides 时不覆盖"""
        self.tool.config = {
            "input_variable": [
                {"raw_name": "username", "default_value": "default_user"},
            ],
        }
        resource = GetToolDetail()
        resource._override_default_values(self.tool, "1001", None)

        input_vars = self.tool.config["input_variable"]
        self.assertEqual(input_vars[0]["default_value"], "default_user")

    def test_partial_override(self):
        """测试部分参数覆盖（只覆盖部分参数）"""
        self.tool.config["default_value_overrides"]["scenes"]["1001"] = {
            "username": "admin",
            # limit 不在覆盖中
        }
        resource = GetToolDetail()
        resource._override_default_values(self.tool, "1001", None)

        input_vars = self.tool.config["input_variable"]
        self.assertEqual(input_vars[0]["default_value"], "admin")
        # limit 保持原默认值
        self.assertEqual(input_vars[1]["default_value"], 50)

    def test_empty_input_variables(self):
        """测试输入变量为空时不报错"""
        self.tool.config["input_variable"] = []
        resource = GetToolDetail()
        # 不应抛出异常
        resource._override_default_values(self.tool, "1001", None)

    def test_input_variable_without_raw_name(self):
        """测试输入变量没有 raw_name 时跳过"""
        self.tool.config["input_variable"] = [
            {"display_name": "无名称字段"},
            {"raw_name": "username", "default_value": "user"},
        ]
        resource = GetToolDetail()
        resource._override_default_values(self.tool, "1001", None)

        # 第一个变量没有 raw_name，应被跳过
        # 第二个变量应该被覆盖
        self.assertEqual(self.tool.config["input_variable"][1]["default_value"], "admin")

    def test_scene_id_string_conversion(self):
        """测试 scene_id 正确转换为字符串"""
        resource = GetToolDetail()
        # 传入整数 scene_id
        resource._override_default_values(self.tool, 1001, None)

        input_vars = self.tool.config["input_variable"]
        # scene_id 1001 应被转换为 "1001"
        self.assertEqual(input_vars[0]["default_value"], "admin")


class ExecuteToolValidateDefaultValuePermissionsTest(TestCase):
    """测试 ExecuteTool._validate_default_value_permissions 方法"""

    def setUp(self):
        """设置测试数据"""
        self.resource = ExecuteTool()
        self.username = "test_user"

    @mock.patch.object(ExecuteTool, "_get_user_allowed_scopes")
    def test_is_show_true_no_validation(self, mock_get_scopes):
        """测试 is_show=True 的参数不校验权限"""
        tool = MockTool(
            config={
                "input_variable": [
                    {
                        "raw_name": "username",
                        "is_show": True,
                        "default_value": "default",
                    }
                ],
                "default_value_overrides": {
                    "scenes": {"1001": {"username": "admin"}},
                },
            }
        )
        params = {"tool_variables": [{"raw_name": "username", "value": "admin"}]}

        # 该用例所有参数均为 is_show=True，无需校验权限；显式设置 mock 返回值避免解包失败
        mock_get_scopes.return_value = ([], [])

        # 不应抛出异常
        self.resource._validate_default_value_permissions(tool, params, self.username)

    @mock.patch.object(ExecuteTool, "_get_user_allowed_scopes")
    def test_use_original_default_without_overrides(self, mock_get_scopes):
        """测试使用原始默认值且不在覆盖列表中时不报错"""
        mock_get_scopes.return_value = (["1001"], ["sys001"])

        tool = MockTool(
            config={
                "input_variable": [
                    {
                        "raw_name": "username",
                        "is_show": False,
                        "default_value": "default_user",
                    }
                ],
                "default_value_overrides": {
                    "scenes": {"1001": {"username": "admin"}},
                },
            }
        )
        # 使用原始默认值
        params = {"tool_variables": [{"raw_name": "username", "value": "default_user"}]}

        # 不应抛出异常
        self.resource._validate_default_value_permissions(tool, params, self.username)

    @mock.patch.object(ExecuteTool, "_get_user_allowed_scopes")
    def test_use_allowed_scene_default(self, mock_get_scopes):
        """测试使用用户有权限的场景的默认值"""
        mock_get_scopes.return_value = (["1001", "1002"], [])

        tool = MockTool(
            config={
                "input_variable": [
                    {
                        "raw_name": "username",
                        "is_show": False,
                        "default_value": "default_user",
                    }
                ],
                "default_value_overrides": {
                    "scenes": {"1001": {"username": "admin"}},
                },
            }
        )
        params = {"tool_variables": [{"raw_name": "username", "value": "admin"}]}

        # 不应抛出异常（用户在场景 1001 中有权限）
        self.resource._validate_default_value_permissions(tool, params, self.username)

    @mock.patch.object(ExecuteTool, "_get_user_allowed_scopes")
    def test_use_allowed_system_default(self, mock_get_scopes):
        """测试使用用户有权限的系统的默认值"""
        mock_get_scopes.return_value = ([], ["sys001"])

        tool = MockTool(
            config={
                "input_variable": [
                    {
                        "raw_name": "env",
                        "is_show": False,
                        "default_value": "test",
                    }
                ],
                "default_value_overrides": {
                    "systems": {"sys001": {"env": "prod"}},
                },
            }
        )
        params = {"tool_variables": [{"raw_name": "env", "value": "prod"}]}

        # 不应抛出异常（用户在系统 sys001 中有权限）
        self.resource._validate_default_value_permissions(tool, params, self.username)

    @mock.patch.object(ExecuteTool, "_get_user_allowed_scopes")
    def test_use_unauthorized_default_raises_exception(self, mock_get_scopes):
        """测试使用无权使用的默认值抛出异常"""
        from core.exceptions import PermissionException

        mock_get_scopes.return_value = (["1001"], [])  # 用户只有场景 1001 的权限

        tool = MockTool(
            config={
                "input_variable": [
                    {
                        "raw_name": "username",
                        "is_show": False,
                        "default_value": "default_user",
                    }
                ],
                "default_value_overrides": {
                    "scenes": {
                        "1001": {"username": "admin"},
                        "1002": {"username": "unauthorized"},  # 用户没有场景 1002 的权限
                    },
                },
            }
        )
        # 尝试使用场景 1002 的默认值
        params = {"tool_variables": [{"raw_name": "username", "value": "unauthorized"}]}

        with self.assertRaises(PermissionException):
            self.resource._validate_default_value_permissions(tool, params, self.username)

    @mock.patch.object(ExecuteTool, "_get_user_allowed_scopes")
    def test_no_default_value_overrides(self, mock_get_scopes):
        """测试工具没有配置 default_value_overrides 时不校验"""
        mock_get_scopes.return_value = ([], [])

        tool = MockTool(
            config={
                "input_variable": [
                    {
                        "raw_name": "username",
                        "is_show": False,
                        "default_value": "default_user",
                    }
                ],
                # 没有 default_value_overrides
            }
        )
        params = {"tool_variables": [{"raw_name": "username", "value": "default_user"}]}

        # 不应抛出异常
        self.resource._validate_default_value_permissions(tool, params, self.username)

    @mock.patch.object(ExecuteTool, "_get_user_allowed_scopes")
    def test_empty_params(self, mock_get_scopes):
        """测试没有传入参数时不校验"""
        mock_get_scopes.return_value = ([], [])

        tool = MockTool(
            config={
                "input_variable": [],
                "default_value_overrides": {"scenes": {"1001": {"username": "admin"}}},
            }
        )
        params = {"tool_variables": []}

        # 不应抛出异常
        self.resource._validate_default_value_permissions(tool, params, self.username)

    @mock.patch.object(ExecuteTool, "_get_user_allowed_scopes")
    def test_multiple_input_variables(self, mock_get_scopes):
        """测试多个输入变量的权限校验"""
        mock_get_scopes.return_value = (["1001"], ["sys001"])

        tool = MockTool(
            config={
                "input_variable": [
                    {
                        "raw_name": "username",
                        "is_show": False,
                        "default_value": "default",
                    },
                    {
                        "raw_name": "env",
                        "is_show": False,
                        "default_value": "test",
                    },
                ],
                "default_value_overrides": {
                    "scenes": {"1001": {"username": "admin"}},
                    "systems": {"sys001": {"env": "prod"}},
                },
            }
        )
        params = {
            "tool_variables": [
                {"raw_name": "username", "value": "admin"},
                {"raw_name": "env", "value": "prod"},
            ]
        }

        # 不应抛出异常（两个值都在允许范围内）
        self.resource._validate_default_value_permissions(tool, params, self.username)

    @mock.patch.object(ExecuteTool, "_get_user_allowed_scopes")
    def test_value_not_in_allowed_defaults(self, mock_get_scopes):
        """测试传入的值不在允许范围内抛出异常"""
        from core.exceptions import PermissionException

        mock_get_scopes.return_value = (["1001"], [])

        tool = MockTool(
            config={
                "input_variable": [
                    {
                        "raw_name": "username",
                        "is_show": False,
                        "default_value": "default_user",
                    }
                ],
                "default_value_overrides": {
                    "scenes": {"1001": {"username": "admin"}},
                },
            }
        )
        # 传入的值既不是原始默认值，也不在覆盖列表中
        params = {"tool_variables": [{"raw_name": "username", "value": "hacker_value"}]}

        with self.assertRaises(PermissionException):
            self.resource._validate_default_value_permissions(tool, params, self.username)


class ToolRetrieveRequestSerializerTest(TestCase):
    """测试 ToolRetrieveRequestSerializer 的 system_id 字段"""

    def test_with_system_id(self):
        """测试传入 system_id"""
        from services.web.tool.serializers import ToolRetrieveRequestSerializer

        serializer = ToolRetrieveRequestSerializer(
            data={
                "uid": "test_tool_123",
                "system_id": "sys001",
            }
        )
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["system_id"], "sys001")

    def test_without_system_id(self):
        """测试不传 system_id（可选字段）"""
        from services.web.tool.serializers import ToolRetrieveRequestSerializer

        serializer = ToolRetrieveRequestSerializer(
            data={
                "uid": "test_tool_123",
            }
        )
        self.assertTrue(serializer.is_valid())
        self.assertIsNone(serializer.validated_data.get("system_id"))

    def test_with_empty_system_id(self):
        """测试传入空 system_id"""
        from services.web.tool.serializers import ToolRetrieveRequestSerializer

        serializer = ToolRetrieveRequestSerializer(
            data={
                "uid": "test_tool_123",
                "system_id": "",
            }
        )
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["system_id"], "")

    def test_with_scene_id_and_system_id(self):
        """测试同时传入 scene_id 和 system_id"""
        from services.web.tool.serializers import ToolRetrieveRequestSerializer

        serializer = ToolRetrieveRequestSerializer(
            data={
                "uid": "test_tool_123",
                "scene_id": 1001,
                "system_id": "sys001",
            }
        )
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["scene_id"], 1001)
        self.assertEqual(serializer.validated_data["system_id"], "sys001")


class ApiToolVarNameMatchingTest(TestCase):
    """测试 API 工具覆盖按 var_name 匹配

    前端传入的 default_value_overrides 以 var_name 为键；而工具执行时 tool_variables
    仅携带 raw_name（无 var_name）。因此执行阶段需借助 input_variable 把覆盖配置的
    var_name 转换成 raw_name，再与 tool_variables 按 raw_name 匹配。
    """

    def setUp(self):
        self.resource = ExecuteTool()
        self.username = "test_user"

    @mock.patch.object(ExecuteTool, "_get_user_allowed_scopes")
    def test_override_keyed_by_var_name(self, mock_get_scopes):
        """覆盖配置按 var_name 匹配：用户传入 var_name 对应的允许值应通过"""
        mock_get_scopes.return_value = ([], ["sys001"])

        tool = MockTool(
            config={
                "input_variable": [
                    {
                        "raw_name": "query",
                        "var_name": "q",
                        "is_show": False,
                        "default_value": "default_query",
                    }
                ],
                "default_value_overrides": {
                    "systems": {"sys001": {"q": "system_query"}},
                },
            }
        )
        # tool_variables 以 raw_name 标识，值为 var_name 对应的允许值
        params = {"tool_variables": [{"raw_name": "query", "value": "system_query"}]}

        # 不应抛出异常（覆盖按 var_name="q" 匹配）
        self.resource._validate_default_value_permissions(tool, params, self.username)

    @mock.patch.object(ExecuteTool, "_get_user_allowed_scopes")
    def test_override_not_matched_by_wrong_var_name(self, mock_get_scopes):
        """覆盖配置按 var_name 匹配：var_name 无法对应到任何 raw_name 时不生效"""
        from core.exceptions import PermissionException

        mock_get_scopes.return_value = ([], ["sys001"])

        tool = MockTool(
            config={
                "input_variable": [
                    {
                        "raw_name": "query",
                        "var_name": "q",
                        "is_show": False,
                        "default_value": "default_query",
                    }
                ],
                "default_value_overrides": {
                    # var_name "wrong" 无法对应到任何 raw_name，覆盖不生效
                    "systems": {"sys001": {"wrong": "wrong_query"}},
                },
            }
        )
        # 用户传入非默认值，且覆盖不生效（var_name 无法映射到 raw_name）
        params = {"tool_variables": [{"raw_name": "query", "value": "wrong_query"}]}

        with self.assertRaises(PermissionException):
            self.resource._validate_default_value_permissions(tool, params, self.username)

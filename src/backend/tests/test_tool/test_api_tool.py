import hashlib
import json
import os
from copy import deepcopy
from unittest.mock import MagicMock, patch

import requests
from django.test import TestCase

from services.web.tool.constants import (
    ApiAuthMethod,
    ApiOutputFieldType,
    ApiToolConfig,
    ApiToolErrorType,
    ApiVariablePosition,
    FieldCategory,
    ToolTypeEnum,
)
from services.web.tool.exceptions import InputVariableMissingError
from services.web.tool.executor.model import APIToolExecuteParams, ApiToolExecuteResult
from services.web.tool.executor.tool import ApiToolExecutor
from services.web.tool.models import Tool
from services.web.tool.resources import CreateTool, UpdateTool


class ApiToolResourceTestCase(TestCase):
    def setUp(self):
        self.uid = "api_tool_test_uid"
        self.tool_type = ToolTypeEnum.API.value

        # Base configuration for API tool
        self.api_config_data = {
            "api_config": {
                "url": "http://example.com/api",
                "method": "GET",
                "auth_config": {"method": "none"},
                "headers": [{"key": "Content-Type", "value": "application/json"}],
            },
            "input_variable": [
                {
                    "raw_name": "query_param",
                    "var_name": "query_param",
                    "display_name": "Query Param",
                    "description": "A query parameter",
                    "required": True,
                    "field_category": FieldCategory.INPUT.value,
                    "is_show": True,
                    "position": ApiVariablePosition.QUERY.value,
                },
                # New Time Range Variable (Required, Query Position)
                {
                    "raw_name": "time_range_required",
                    "var_name": "time_range_required",
                    "display_name": "Time Range Required",
                    "description": "A required time range parameter",
                    "required": True,
                    "field_category": FieldCategory.TIME_RANGE_SELECT.value,
                    "is_show": True,
                    "position": ApiVariablePosition.QUERY.value,
                    "split_config": {"start_field": "start_ts", "end_field": "end_ts"},
                },
                # New Time Range Variable (Optional, Body Position)
                {
                    "raw_name": "time_range_optional",
                    "var_name": "time_range_optional",
                    "display_name": "Time Range Optional",
                    "description": "An optional time range parameter",
                    "required": False,
                    "field_category": FieldCategory.TIME_RANGE_SELECT.value,
                    "is_show": True,
                    "position": ApiVariablePosition.BODY.value,
                    "split_config": {"start_field": "body_start", "end_field": "body_end"},
                },
                # Path Variable
                {
                    "raw_name": "path_id",
                    "var_name": "path_id",
                    "display_name": "Path ID",
                    "description": "An ID in path",
                    "required": True,
                    "field_category": FieldCategory.NUMBER_INPUT.value,
                    "is_show": True,
                    "position": ApiVariablePosition.PATH.value,
                },
                # Body Variable
                {
                    "raw_name": "body_data",
                    "var_name": "body_data",
                    "display_name": "Body Data",
                    "description": "Data in body",
                    "required": False,
                    "field_category": FieldCategory.INPUT.value,
                    "is_show": True,
                    "position": ApiVariablePosition.BODY.value,
                },
            ],
            "output_config": {
                "enable_grouping": True,
                "groups": [
                    {
                        "name": "Default Group",
                        "is_group": True,
                        "output_fields": [
                            # 1. Top level field with enum mapping
                            {
                                "json_path": "status",
                                "raw_name": "status",
                                "display_name": "Status",
                                "description": "Status field",
                                "field_config": {"field_type": "kv"},
                                "enum_mappings": {"mappings": [{"key": "1", "name": "Active"}]},
                            },
                            # 2. Nested table field with sub-field enum mapping
                            {
                                "json_path": "items",
                                "raw_name": "items",
                                "display_name": "Items List",
                                "description": "List of items",
                                "field_config": {
                                    "field_type": ApiOutputFieldType.TABLE.value,
                                    "output_fields": [
                                        {
                                            "json_path": "type",
                                            "raw_name": "item_type",
                                            "display_name": "Item Type",
                                            "description": "Type of item",
                                            "enum_mappings": {"mappings": [{"key": "A", "name": "Type A"}]},
                                        }
                                    ],
                                },
                            },
                        ],
                    }
                ],
            },
        }

        # Mock resource.meta
        self.mock_meta = MagicMock()
        self.mock_meta.batch_update_enum_mappings.return_value = None

        # Manual patch
        from services.web.tool import resources

        self.original_meta = resources.resource.meta
        resources.resource.meta = self.mock_meta

    def tearDown(self):
        from services.web.tool import resources

        resources.resource.meta = self.original_meta

    def test_create_api_tool_with_new_fields(self):
        """Test that creating an API tool with split_config and enable_grouping works"""
        data = {
            "uid": self.uid,
            "name": "Test API Tool",
            "namespace": "default",
            "tool_type": self.tool_type,
            "config": self.api_config_data,
            "description": "Test Description",
            "tags": [],
            "version": 1,
        }

        with patch('services.web.tool.resources.get_request_username', return_value="admin"):
            result = CreateTool()(data)

        tool = Tool.objects.get(uid=result['uid'], version=result['version'])

        # Verify split_config
        input_vars = tool.config['input_variable']
        time_range_var = next(v for v in input_vars if v['raw_name'] == 'time_range_required')
        self.assertEqual(time_range_var['split_config']['start_field'], 'start_ts')
        self.assertEqual(time_range_var['split_config']['end_field'], 'end_ts')

        # Verify enable_grouping
        output_config = tool.config['output_config']
        self.assertTrue(output_config['enable_grouping'])

        # Verify enum mapping calls still work
        self.assertEqual(self.mock_meta.batch_update_enum_mappings.call_count, 2)

        status_key = hashlib.md5(b'Default Group-status-status').hexdigest()
        item_type_key = hashlib.md5(b'Default Group-type-item_type').hexdigest()

        self.mock_meta.batch_update_enum_mappings.assert_any_call(
            collection_id=f"tool_{tool.uid}_output_fields_{status_key}",
            mappings=[{"key": "1", "name": "Active"}],
            related_object_id=tool.uid,
            related_type="tool",
        )

        self.mock_meta.batch_update_enum_mappings.assert_any_call(
            collection_id=f"tool_{tool.uid}_output_fields_{item_type_key}",
            mappings=[{"key": "A", "name": "Type A"}],
            related_object_id=tool.uid,
            related_type="tool",
        )

    def test_update_api_tool_syncs_enum_mappings(self):
        """Test that updating an API tool re-syncs enum mappings"""
        # First create the tool
        Tool.objects.create(
            uid=self.uid,
            version=1,
            name="Original Tool",
            namespace="default",
            tool_type=ToolTypeEnum.API.value,
            config=ApiToolConfig.model_validate(self.api_config_data).model_dump(),
            created_by="admin",
        )

        # Prepare update data with modified enum mappings
        new_config_data = deepcopy(self.api_config_data)
        # Modify 'status' mapping
        new_config_data['output_config']['groups'][0]['output_fields'][0]['enum_mappings']['mappings'] = [
            {"key": "1", "name": "Active"},
            {"key": "0", "name": "Inactive"},
        ]

        update_data = {"uid": self.uid, "config": new_config_data, "tags": []}

        self.mock_meta.reset_mock()

        with patch('services.web.tool.resources.get_request_username', return_value="admin"):
            result = UpdateTool()(update_data)

        self.assertEqual(result['version'], 2)

        status_key = hashlib.md5(b'Default Group-status-status').hexdigest()

        self.mock_meta.batch_update_enum_mappings.assert_any_call(
            collection_id=f"tool_{self.uid}_output_fields_{status_key}",
            mappings=[{"key": "1", "name": "Active"}, {"key": "0", "name": "Inactive"}],
            related_object_id=self.uid,
            related_type="tool",
        )


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

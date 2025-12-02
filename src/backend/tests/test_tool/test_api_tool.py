import hashlib
from copy import deepcopy
from unittest.mock import MagicMock, patch

from django.test import TestCase

from services.web.tool.constants import (
    ApiOutputFieldType,
    ApiToolConfig,
    ApiVariablePosition,
    FieldCategory,
    ToolTypeEnum,
)
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
                    "display_name": "Query Param",
                    "description": "A query parameter",
                    "required": True,
                    "field_category": FieldCategory.INPUT.value,
                    "is_show": True,
                    "position": ApiVariablePosition.QUERY.value,
                },
                # New Time Range Variable
                {
                    "raw_name": "time_range",
                    "display_name": "Time Range",
                    "description": "A time range parameter",
                    "required": False,
                    "field_category": FieldCategory.TIME_RANGE_SELECT.value,
                    "is_show": True,
                    "position": ApiVariablePosition.QUERY.value,
                    "split_config": {"start_field": "start_ts", "end_field": "end_ts"},
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
        time_range_var = next(v for v in input_vars if v['raw_name'] == 'time_range')
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

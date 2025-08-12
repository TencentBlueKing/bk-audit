import uuid
from unittest import mock
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from api.bk_base.default import UserAuthBatchCheck
from apps.meta.models import Tag
from core.testing import assert_list_contains
from services.web.tool.constants import DataSearchConfigTypeEnum, ToolTypeEnum
from services.web.tool.models import (
    BkVisionToolConfig,
    DataSearchToolConfig,
    Tool,
    ToolTag,
)
from services.web.tool.resources import (
    CreateTool,
    DeleteTool,
    GetToolDetail,
    GetToolEnumMappingByCollection,
    GetToolEnumMappingByCollectionKeys,
    ListTool,
    UpdateTool,
    UserQueryTableAuthCheck,
)
from services.web.vision.models import Scenario, VisionPanel


class ToolResourceTestCase(TestCase):
    def setUp(self):
        self.uid = str(uuid.uuid4())
        self.uid_2 = str(uuid.uuid4())
        self.namespace = "default_ns"

        self.sql_tool = Tool.objects.create(
            uid=self.uid,
            version=1,
            name="SQL Tool",
            namespace=self.namespace,
            tool_type=ToolTypeEnum.DATA_SEARCH.value,
            config={
                "sql": "select 1",
                "referenced_tables": [{"table_name": "test_table"}],
                "input_variable": [{"raw_name": "date_range", "required": True}],
                "output_fields": [{"raw_name": "thedate", "display_name": "日期"}],
            },
            is_deleted=False,
            description="SQL Tool Desc",
            updated_at=timezone.now(),
        )
        DataSearchToolConfig.objects.create(
            tool=self.sql_tool,
            data_search_config_type=DataSearchConfigTypeEnum.SQL,
            sql="select 1",
        )

        self.bkvision_uid = str(uuid.uuid4())
        self.bk_tool = self._create_bkvision_tool(self.uid_2, self.bkvision_uid, self.namespace)

        self.tag1 = Tag.objects.create(tag_name="tag1")
        self.tag2 = Tag.objects.create(tag_name="tag2")
        ToolTag.objects.create(tool_uid=self.sql_tool.uid, tag_id=self.tag1.tag_id)
        ToolTag.objects.create(tool_uid=self.bk_tool.uid, tag_id=self.tag2.tag_id)
        self.auth_patcher = patch('api.bk_base.default.UserAuthBatchCheck.perform_request')
        self.mock_auth_check = self.auth_patcher.start()
        self.mock_auth_check.return_value = [
            {"object_id": "test_table", "result": True, "user_id": "test_user", "permission": {"read": True}}
        ]

    def tearDown(self):
        self.auth_patcher.stop()  # 清理Mock
        super().tearDown()

    def _create_bkvision_tool(self, tool_uid, vision_uid, namespace):
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
        tool = Tool.objects.create(
            uid=tool_uid,
            version=1,
            name="BK Vision Tool",
            namespace=namespace,
            tool_type=ToolTypeEnum.BK_VISION.value,
            config={"uid": vision_uid, "input_variable": [example_var, example_var2]},
            is_deleted=False,
            description="BK Vision Tool Desc",
            updated_at=timezone.now(),
        )
        panel = VisionPanel.objects.create(
            id=uuid.uuid4(),
            vision_id=vision_uid,
            name=tool.name,
            scenario=Scenario.TOOL.value,
            handler="VisionHandler",
        )
        BkVisionToolConfig.objects.create(tool=tool, panel=panel)
        return tool

    def _call_resource_with_request(self, resource_cls, data):
        factory = APIRequestFactory()
        django_request = factory.post('/fake-url/', data, format='json')
        drf_request = Request(django_request)

        resource = resource_cls()
        validated_data = resource.validate_request_data(data)
        validated_data['_request'] = drf_request
        response = resource.perform_request(validated_data)
        return response.data.get("results", [])

    def test_list_tool(self):
        data = {"keyword": "SQL", "page": 1, "page_size": 10}
        result = self._call_resource_with_request(ListTool, data)
        tool_names = [item["name"] for item in result]
        self.assertIn("SQL Tool", tool_names)

        data_empty = {"keyword": "", "page": 1, "page_size": 10}
        all_result = self._call_resource_with_request(ListTool, data_empty)
        self.assertGreaterEqual(len(all_result), 2)

        data_paged = {"keyword": "", "page": 1, "page_size": 2}
        paged_result = self._call_resource_with_request(ListTool, data_paged)
        self.assertEqual(len(paged_result), 2)

        tag_result = self._call_resource_with_request(
            ListTool, {"keyword": "", "page": 1, "page_size": 10, "tags": [self.tag1.tag_id]}
        )
        tag_names = [item["name"] for item in tag_result]
        self.assertIn("SQL Tool", tag_names)
        self.assertNotIn("BK Vision Tool", tag_names)

        tag_result_2 = self._call_resource_with_request(
            ListTool, {"keyword": "", "page": 1, "page_size": 10, "tags": [self.tag1.tag_id, self.tag2.tag_id]}
        )
        tag_names_2 = [item["name"] for item in tag_result_2]
        self.assertIn("SQL Tool", tag_names_2)
        self.assertIn("BK Vision Tool", tag_names_2)

    def test_create_tool_sql(self):
        resource = CreateTool()
        new_uid = str(uuid.uuid4())
        data = {
            "uid": new_uid,
            "version": 1,
            "name": "New SQL Tool",
            "namespace": "default_ns",
            "tool_type": ToolTypeEnum.DATA_SEARCH.value,
            "data_search_config_type": DataSearchConfigTypeEnum.SQL.value,
            "config": {
                "sql": "select * from test",
                "referenced_tables": [],
                "input_variable": [],
                "output_fields": [],
            },
            "description": "desc",
        }
        tool = resource.perform_request(data)
        self.assertEqual(tool.uid, new_uid)
        self.assertEqual(tool.tool_type, ToolTypeEnum.DATA_SEARCH.value)

        ToolTag.objects.create(tool_uid=tool.uid, tag_id=self.tag1.tag_id)
        self.assertTrue(ToolTag.objects.filter(tool_uid=tool.uid, tag_id=self.tag1.tag_id).exists())

        config = DataSearchToolConfig.objects.filter(tool=tool).first()
        self.assertIsNotNone(config)
        self.assertEqual(config.sql, "select * from test")

    def test_create_tool_bkvision(self):
        resource = CreateTool()
        new_uid = str(uuid.uuid4())
        vision_uid = str(uuid.uuid4())
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
        data = {
            "uid": new_uid,
            "version": 1,
            "name": "New BK Vision Tool",
            "namespace": "default_ns",
            "tool_type": ToolTypeEnum.BK_VISION.value,
            "config": {"uid": vision_uid, "input_variable": [example_var, example_var2]},
            "description": "desc",
        }
        tool = resource.perform_request(data)
        self.assertEqual(tool.tool_type, ToolTypeEnum.BK_VISION.value)
        panel = VisionPanel.objects.filter(vision_id=vision_uid, is_deleted=False).first()
        self.assertIsNotNone(panel)
        bk_config = BkVisionToolConfig.objects.filter(tool=tool).first()
        self.assertIsNotNone(bk_config)
        self.assertEqual(bk_config.panel.id, panel.id)
        # bkvision config should include the example input_variable
        self.assertEqual(tool.config.get("input_variable"), [example_var, example_var2])

    def test_update_tool_no_config_change(self):
        resource = UpdateTool()
        data = {
            "uid": self.sql_tool.uid,
            "version": 1,
            "name": "Updated SQL Tool",
            "namespace": self.sql_tool.namespace,
            "config": self.sql_tool.config,
            "description": "updated desc",
            "tags": [],
        }
        updated_tool = resource.perform_request(data)
        self.assertEqual(updated_tool.name, "Updated SQL Tool")
        self.assertEqual(updated_tool.description, "updated desc")
        self.assertEqual(updated_tool.version, 1)
        self.assertEqual(updated_tool.id, self.sql_tool.id)

    def test_update_tool_with_config_change(self):
        resource = UpdateTool()
        new_config = {
            "sql": "select * from dual",
            "referenced_tables": [],
            "input_variable": [],
            "output_fields": [],
        }
        data = {
            "uid": self.sql_tool.uid,
            "name": "Updated SQL Tool v2",
            "namespace": self.sql_tool.namespace,
            "config": new_config,
            "description": "updated desc",
            "update_fields": ["name", "description"],
            "tags": [self.tag2.tag_name],
        }
        new_tool = resource.perform_request(data)
        self.assertNotEqual(new_tool.version, self.sql_tool.version)
        self.assertEqual(new_tool.version, self.sql_tool.version + 1)
        self.assertEqual(new_tool.config, new_config)
        self.assertEqual(new_tool.name, "Updated SQL Tool v2")

        ToolTag.objects.create(tool_uid=new_tool.uid, tag_id=self.tag2.tag_id)
        tag_ids = ToolTag.objects.filter(tool_uid=new_tool.uid).values_list("tag_id", flat=True)
        self.assertIn(self.tag2.tag_id, tag_ids)

    def test_delete_tool(self):
        resource = DeleteTool()
        uid = self.sql_tool.uid

        self.assertTrue(ToolTag.objects.filter(tool_uid=uid).exists())  # 删除前存在 tag

        resource.perform_request({"uid": uid})
        tool_exists = Tool.objects.filter(uid=uid, is_deleted=False).exists()
        self.assertFalse(tool_exists)

        # 补充：tag 自动删除
        self.assertFalse(ToolTag.objects.filter(tool_uid=uid).exists())

    def test_list_tool_filter_only_created_by_me(self):
        with patch("services.web.tool.resources.get_request_username", return_value=self.uid):
            data = {
                "keyword": "",
                "tags": [],
                "my_created": True,
                "recent_used": False,
                "page": 1,
                "page_size": 10,
            }
            result = self._call_resource_with_request(ListTool, data)
            self.assertTrue(all(tool["created_by"] == self.uid for tool in result))

    def test_list_tool_filter_recent_uids_flag(self):
        recent_uids = [self.sql_tool.uid, self.bk_tool.uid]

        with patch(
            "services.web.tool.resources.recent_tool_usage_manager.get_recent_uids",
            return_value=recent_uids,
        ), patch("services.web.tool.resources.get_request_username", return_value=self.uid):
            data = {
                "keyword": "",
                "tags": [],
                "my_created": False,
                "recent_used": True,
                "page": 1,
                "page_size": 10,
            }
            result = self._call_resource_with_request(ListTool, data)
            result_uids = [tool["uid"] for tool in result]
            self.assertCountEqual(result_uids, recent_uids)

    def test_tool_detail(self):
        tool_detail_resource = GetToolDetail()
        result = tool_detail_resource.perform_request({"uid": self.sql_tool.uid})

        self.assertEqual(result.uid, self.sql_tool.uid)  # 使用 . 访问属性
        self.assertEqual(result.name, "SQL Tool")

        self.assertIsNotNone(getattr(result, "tags", None))
        self.assertIsNotNone(getattr(result, "strategies", None))

        if result.tool_type == ToolTypeEnum.DATA_SEARCH.value:
            for table in result.config["referenced_tables"]:
                self.assertIn("permission", table)


class UserQueryTableAuthCheckTestCase(TestCase):
    def setUp(self):
        self.patcher_auth = mock.patch.object(
            UserAuthBatchCheck,
            "perform_request",
            return_value=[
                {"result": True, "user_id": "test_user", "object_id": "mocked_table1"},
                {"result": False, "user_id": "test_user", "object_id": "mocked_table2"},
            ],
        )
        self.mock_auth_api = self.patcher_auth.start()

    def tearDown(self):
        mock.patch.stopall()

    def test_user_query_table_auth_check(self):
        req_data = {'tables': ['mocked_table1', 'mocked_table2']}
        resource = UserQueryTableAuthCheck()
        actual = resource(req_data)
        expect = [
            {"result": True, "user_id": "test_user", "object_id": "mocked_table1"},
            {"result": False, "user_id": "test_user", "object_id": "mocked_table2"},
        ]
        assert_list_contains(actual, expect)


class ToolEnumMappingTests(TestCase):
    """工具枚举映射功能测试"""

    def setUp(self):
        self.tool_uid = "test_tool_123"
        self.field_name = "status"
        self.collection_id = f"tool_{self.tool_uid}_output_fields_{self.field_name}"

        self.tool = Tool.objects.create(
            uid=self.tool_uid,
            version=1,
            name="Test Tool",
            tool_type=ToolTypeEnum.DATA_SEARCH.value,
            config={
                "sql": "SELECT 1",
                "referenced_tables": [{"table_name": "test"}],
                "input_variable": [{"raw_name": "param", "display_name": "Parameter", "required": False}],
                "output_fields": [
                    {
                        "raw_name": self.field_name,
                        "display_name": "Status",
                        "enum_mappings": {"mappings": [{"key": "1", "name": "Active"}]},
                    }
                ],
            },
        )

        # 创建关联的DataSearchToolConfig
        DataSearchToolConfig.objects.create(
            tool=self.tool, data_search_config_type=DataSearchConfigTypeEnum.SQL.value, sql="SELECT 1"
        )

        # Mock配置
        self.mock_meta = MagicMock()
        self.mock_meta.batch_update_enum_mappings.return_value = None
        self.mock_meta.get_enum_mapping_by_collection_keys.return_value = [
            {"collection_id": self.collection_id, "key": "1", "name": "Active"},
            {"collection_id": "invalid", "key": "99", "name": None},
        ]
        self.mock_meta.get_enum_mapping_by_collection.return_value = [
            {"key": "1", "name": "Active"},
            {"key": "0", "name": "Inactive"},
        ]

        # 手动替换资源中的meta引用
        from services.web.tool import resources

        self.original_meta = resources.resource.meta
        resources.resource.meta = self.mock_meta

    def tearDown(self):
        # 恢复原始meta引用
        from services.web.tool import resources

        resources.resource.meta = self.original_meta

    def test_create_tool_generates_enum_mapping(self):
        """测试创建工具时自动生成枚举映射"""
        test_data = {
            "uid": "new_tool_456",
            "version": 1,  # 必须包含version
            "name": "New SQL Tool",
            "namespace": "default",
            "tool_type": ToolTypeEnum.DATA_SEARCH.value,
            "data_search_config_type": DataSearchConfigTypeEnum.SQL.value,
            "config": {
                "sql": "SELECT * FROM test",
                "referenced_tables": [{"table_name": "test_table"}],
                "input_variable": [{"raw_name": "param", "display_name": "Parameter", "required": False}],
                "output_fields": [
                    {
                        "raw_name": "status",
                        "display_name": "Status",
                        "enum_mappings": {"mappings": [{"key": "1", "name": "Active"}]},
                    }
                ],
            },
        }

        # 使用patch避免实际数据库操作
        with patch('services.web.tool.tool._create_sql_tool') as mock_create_sql:
            mock_create_sql.return_value = MagicMock(uid="new_tool_456")
            CreateTool().perform_request(test_data)

            # 验证枚举映射参数
            self.mock_meta.batch_update_enum_mappings.assert_called_once_with(
                collection_id="tool_new_tool_456_output_fields_status",
                mappings=[{"key": "1", "name": "Active"}],
                related_object_id="new_tool_456",
                related_type="tool",
            )

    def test_update_tool_syncs_enum_mapping(self):
        """测试更新工具配置时同步枚举映射"""
        new_mappings = [{"key": "2", "name": "Pending"}]

        # 使用patch模拟工具查询
        with patch('services.web.tool.models.Tool.last_version_tool', return_value=self.tool):
            UpdateTool().perform_request(
                {
                    "uid": self.tool_uid,
                    "version": 2,  # 更新版本号
                    "config": {
                        "sql": "SELECT 2",
                        "referenced_tables": [],
                        "input_variable": [],
                        "output_fields": [
                            {
                                "raw_name": self.field_name,
                                "display_name": "Status",
                                "enum_mappings": {"mappings": new_mappings},
                            }
                        ],
                    },
                    "tags": [],
                }
            )

        # 验证枚举更新
        self.mock_meta.batch_update_enum_mappings.assert_called_with(
            collection_id=self.collection_id,
            mappings=new_mappings,
            related_object_id=self.tool_uid,
            related_type="tool",
        )

    def test_delete_tool_cleans_enum_mapping(self):
        """测试删除工具时清理关联枚举映射"""
        # 模拟存在关联枚举
        self.mock_meta.get_enum_mappings_relation.return_value = [self.collection_id]

        DeleteTool().perform_request({"uid": self.tool_uid})

        # 验证枚举集合被清空
        self.mock_meta.batch_update_enum_mappings.assert_called_with(
            collection_id=self.collection_id, mappings=[], related_object_id=self.tool_uid, related_type="tool"
        )

    def test_query_enum_by_keys(self):
        """测试按Key查询枚举值"""
        test_keys = [{"collection_id": self.collection_id, "key": "1"}, {"collection_id": "invalid", "key": "99"}]

        results = GetToolEnumMappingByCollectionKeys().perform_request(
            {"collection_keys": test_keys, "related_object_id": self.tool_uid}
        )

        # 验证返回结构
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["name"], "Active")
        self.assertIsNone(results[1]["name"])

    def test_query_all_enum_in_collection(self):
        """测试获取集合内所有枚举值"""
        results = GetToolEnumMappingByCollection().perform_request(
            {"collection_id": self.collection_id, "related_object_id": self.tool_uid}
        )

        # 验证返回数据完整性
        self.assertEqual(len(results), 2)
        self.assertEqual({r["key"] for r in results}, {"0", "1"})

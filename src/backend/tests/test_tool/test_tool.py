import uuid
from unittest import mock
from unittest.mock import patch

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

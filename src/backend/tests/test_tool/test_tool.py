import uuid
from datetime import timedelta
from typing import Type
from unittest import mock
from unittest.mock import MagicMock, PropertyMock, patch

from bk_resource import Resource
from django.db.models import Q
from django.test import TestCase
from django.utils import timezone
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from api.bk_base.default import UserAuthBatchCheck
from apps.meta.models import Tag
from core.sql.parser.praser import SqlQueryAnalysis
from core.testing import assert_list_contains
from services.web.tool.constants import (
    ApiVariablePosition,
    DataSearchConfigTypeEnum,
    FieldCategory,
    SQLDataSearchConfig,
    SQLDataSearchInputVariable,
    SQLDataSearchOutputField,
    Table,
    ToolTypeEnum,
)
from services.web.tool.exceptions import ToolTypeNotSupport
from services.web.tool.models import (
    BkVisionToolConfig,
    DataSearchToolConfig,
    Tool,
    ToolTag,
)
from services.web.tool.permissions import ToolPermission
from services.web.tool.resources import (
    CreateTool,
    DeleteTool,
    GetToolDetail,
    GetToolEnumMappingByCollection,
    GetToolEnumMappingByCollectionKeys,
    ListTool,
    ToolExecuteDebug,
    UpdateTool,
    UserQueryTableAuthCheck,
)
from services.web.vision.models import Scenario, VisionPanel
from tests.test_tool.constants import MOCK_FETCH_TOOL_PERMISSION_TAGS_EMPTY


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
            config=SQLDataSearchConfig(
                sql="select f1 from test_table",
                referenced_tables=[Table(table_name="test_table")],
                input_variable=[
                    SQLDataSearchInputVariable(
                        raw_name="date_range",
                        required=True,
                        display_name="日期范围",
                        field_category=FieldCategory.TIME_RANGE_SELECT,
                        default_value=None,
                    ),
                ],
                output_fields=[SQLDataSearchOutputField(raw_name="thedate", display_name="日期")],
            ).model_dump(),
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
        self.api_debug_config = {
            "api_config": {
                "url": "http://example.com/{path_id}",
                "method": "GET",
                "auth_config": {"method": "none"},
                "headers": [],
            },
            "input_variable": [
                {
                    "raw_name": "path_id",
                    "display_name": "Path ID",
                    "required": True,
                    "var_name": "path_id",
                    "field_category": FieldCategory.INPUT.value,
                    "is_show": True,
                    "position": ApiVariablePosition.PATH.value,
                }
            ],
            "output_config": {"enable_grouping": False, "groups": []},
        }
        # Mock 权限校验
        self.patcher_auth = mock.patch.object(
            UserAuthBatchCheck,
            "perform_request",
            return_value=[
                {"object_id": "test_table", "result": True, "user_id": "test_user", "permission": {"read": True}}
            ],
        )
        self.mock_auth_check = self.patcher_auth.start()

    def tearDown(self):
        mock.patch.stopall()

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

    def _call_resource_with_request(self, resource_cls: Type[Resource], data):
        factory = APIRequestFactory()
        django_request = factory.post('/fake-url/', data, format='json')
        drf_request = Request(django_request)

        resource = resource_cls()
        response = resource.request(data, _request=drf_request)
        return response.data.get("results", [])

    @patch.object(ToolPermission, 'fetch_tool_permission_tags', return_value=MOCK_FETCH_TOOL_PERMISSION_TAGS_EMPTY)
    @patch.object(ToolPermission, 'authed_tool_filter', new_callable=PropertyMock)
    def test_list_tool(self, mock_authed_tool_filter, fetch_tool_permission_tags):
        mock_authed_tool_filter.return_value = Q()
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

        tag_result_2 = self._call_resource_with_request(
            ListTool, {"keyword": "", "page": 1, "page_size": 10, "tags": [self.tag1.tag_id, self.tag2.tag_id]}
        )
        tag_names_2 = [item["name"] for item in tag_result_2]
        self.assertIn("SQL Tool", tag_names_2)
        self.assertIn("BK Vision Tool", tag_names_2)

    def test_create_tool_sql(self):
        resource = CreateTool()
        data = {
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
        tool = resource(data)

        ToolTag.objects.create(tool_uid=tool["uid"], tag_id=self.tag1.tag_id)
        self.assertTrue(ToolTag.objects.filter(tool_uid=tool["uid"], tag_id=self.tag1.tag_id).exists())

        config = DataSearchToolConfig.objects.filter(tool__uid=tool["uid"]).first()
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
            "raw_default_value": "default_val",
            "is_default_value": True,
        }
        example_var2 = {
            "raw_name": "list_field",
            "display_name": "列表字段",
            "description": "列表默认值",
            "field_category": "selector",
            "required": False,
            "default_value": [1, 2, 3],
            "raw_default_value": [1, 2, 3],
            "is_default_value": True,
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
        tool = resource(data)
        panel = VisionPanel.objects.filter(vision_id=vision_uid, is_deleted=False).first()
        self.assertIsNotNone(panel)

        bk_config = BkVisionToolConfig.objects.filter(tool__uid=tool['uid']).first()
        self.assertIsNotNone(bk_config)
        self.assertEqual(bk_config.panel.id, panel.id)
        # bkvision config should include the example input_variable
        tool_obj: Tool = Tool.objects.get(uid=tool['uid'], version=tool['version'])
        self.assertEqual(tool_obj.config.get("input_variable"), [example_var, example_var2])

    def test_update_tool_no_config_change(self):
        data = {
            "uid": self.sql_tool.uid,
            "version": 1,
            "name": "Updated SQL Tool",
            "namespace": self.sql_tool.namespace,
            "config": self.sql_tool.config,
            "description": "updated desc",
            "tags": [],
        }
        updated_tool = UpdateTool()(data)
        # 修改：全部改为字典键访问
        self.assertEqual(updated_tool['version'], 1)
        self.assertEqual(updated_tool['uid'], self.sql_tool.uid)

    def test_update_tool_with_config_change(self):
        resource = UpdateTool()
        new_config = {
            "sql": "select a from dual",
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
        new_tool = resource(data)
        # 修改：全部改为字典键访问
        self.assertEqual(new_tool['version'], self.sql_tool.version + 1)
        self.assertEqual(new_tool['uid'], self.sql_tool.uid)

    def test_update_tool_preserve_creator_on_new_version(self):
        """创建新版本时应保持创建人与旧版本一致"""
        # 将旧版本创建人设为特定用户
        self.sql_tool.created_by = "origin_user"
        # 将旧版本创建时间设为固定时间
        fixed_created_at = timezone.now() - timedelta(days=7)
        self.sql_tool.created_at = fixed_created_at
        # 不更新操作记录，以免被自动覆盖
        self.sql_tool.save(update_record=False, update_fields=["created_by", "created_at"])

        new_config = {
            "sql": "select now()",
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
            "tags": [],
        }

        # 模拟当前操作者与创建人不同
        with patch("services.web.tool.resources.get_request_username", return_value="another_user"):
            UpdateTool().perform_request(data)

        # 校验：新版本创建人应与旧版本一致
        created_new = Tool.objects.get(uid=self.sql_tool.uid, version=self.sql_tool.version + 1)
        self.assertEqual(created_new.created_by, "origin_user")
        # 校验：新版本创建时间应与旧版本一致
        self.assertEqual(created_new.created_at, fixed_created_at)

    def test_delete_tool(self):
        resource = DeleteTool()
        uid = self.sql_tool.uid

        self.assertTrue(ToolTag.objects.filter(tool_uid=uid).exists())  # 删除前存在 tag

        resource({"uid": uid})
        tool_exists = Tool.objects.filter(uid=uid, is_deleted=False).exists()
        self.assertFalse(tool_exists)

        # 补充：tag 自动删除
        self.assertFalse(ToolTag.objects.filter(tool_uid=uid).exists())

    @patch.object(ToolPermission, 'authed_tool_filter', new_callable=PropertyMock)
    def test_list_tool_filter_only_created_by_me(self, mock_authed_tool_filter):
        mock_authed_tool_filter.return_value = Q()
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

    @patch.object(ToolPermission, 'fetch_tool_permission_tags', return_value=MOCK_FETCH_TOOL_PERMISSION_TAGS_EMPTY)
    @patch.object(ToolPermission, 'authed_tool_filter', new_callable=PropertyMock)
    def test_list_tool_filter_recent_uids_flag(self, mock_authed_tool_filter, mock_fetch_tool_permission_tags):
        mock_authed_tool_filter.return_value = Q()
        recent_uids = [self.sql_tool.uid, self.bk_tool.uid]

        with (
            patch(
                "services.web.tool.resources.recent_tool_usage_manager.get_recent_uids",
                return_value=recent_uids,
            ),
            patch("services.web.tool.resources.get_request_username", return_value=self.uid),
        ):
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

    @patch.object(ToolPermission, 'fetch_tool_permission_tags', return_value=MOCK_FETCH_TOOL_PERMISSION_TAGS_EMPTY)
    @patch.object(ToolPermission, 'authed_tool_filter', new_callable=PropertyMock)
    def test_tool_detail(self, mock_authed_tool_filter, fetch_tool_permission_tags):
        mock_authed_tool_filter.return_value = Q()
        tool_detail_resource = GetToolDetail()
        result = tool_detail_resource({"uid": self.sql_tool.uid})

        self.assertEqual(result["uid"], self.sql_tool.uid)
        self.assertEqual(result["name"], "SQL Tool")

        self.assertIsNotNone(result["tags"])
        self.assertIsNotNone(result["strategies"])

        if result["tool_type"] == ToolTypeEnum.DATA_SEARCH.value:
            for table in result["config"]["referenced_tables"]:
                self.assertIn("permission", table)

    @patch("services.web.tool.resources.ToolExecutorFactory")
    def test_tool_execute_debug_api(self, mock_factory):
        mock_executor = MagicMock()
        mock_result = MagicMock()
        mock_result.model_dump.return_value = {
            "status_code": 200,
            "result": {"message": "ok"},
            "err_type": "none",
            "message": "",
        }
        mock_executor.execute.return_value = mock_result
        mock_factory.return_value.create_from_config.return_value = mock_executor

        request_data = {
            "tool_type": ToolTypeEnum.API.value,
            "config": self.api_debug_config,
            "params": {
                "tool_variables": [{"raw_name": "path_id", "value": "123", "position": ApiVariablePosition.PATH.value}]
            },
        }

        resource = ToolExecuteDebug()
        response = resource(request_data)

        self.assertEqual(response["tool_type"], ToolTypeEnum.API.value)
        self.assertEqual(
            response["data"],
            {"status_code": 200, "result": {"message": "ok"}, "err_type": "none", "message": ""},
        )
        mock_factory.assert_called_once_with(sql_analyzer_cls=SqlQueryAnalysis)
        mock_factory.return_value.create_from_config.assert_called_once_with(
            tool_type=ToolTypeEnum.API.value,
            config=self.api_debug_config,
        )
        mock_executor.execute.assert_called_once_with(request_data["params"])

    @patch("services.web.tool.resources.ToolExecutorFactory")
    def test_tool_execute_debug_not_support(self, mock_factory):
        mock_factory.return_value.create_from_config.side_effect = ToolTypeNotSupport()
        request_data = {
            "tool_type": ToolTypeEnum.BK_VISION.value,
            "config": {"uid": "vision_demo"},
            "params": {},
        }
        resource = ToolExecuteDebug()
        with self.assertRaises(ToolTypeNotSupport):
            resource(request_data)


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
                "input_variable": [
                    {
                        "raw_name": "param",
                        "display_name": "Parameter",
                        "required": False,
                        "field_category": FieldCategory.INPUT.value,
                    }
                ],
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
                "input_variable": [
                    {
                        "raw_name": "param",
                        "display_name": "Parameter",
                        "required": False,
                        "field_category": FieldCategory.INPUT.value,
                    }
                ],
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

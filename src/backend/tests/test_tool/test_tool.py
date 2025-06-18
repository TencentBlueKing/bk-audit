import uuid

from django.test import TestCase
from django.utils import timezone

from services.web.tool.constants import DataSearchConfigTypeEnum, ToolTypeEnum
from services.web.tool.models import BkvisionToolConfig, DataSearchToolConfig, Tool
from services.web.tool.resources import (
    CreateTool,
    DeleteTool,
    GetToolDetail,
    ListTool,
    UpdateTool,
)
from services.web.vision.models import Scenario, VisionPanel


class ToolResourceTestCase(TestCase):
    def setUp(self):
        self.uid = str(uuid.uuid4())
        self.uid_2 = str(uuid.uuid4())
        self.namespace = "default_ns"

        # 创建 SQL 类型工具
        self.sql_tool = Tool.objects.create(
            uid=self.uid,
            version=1,
            name="SQL Tool",
            namespace=self.namespace,
            tool_type=ToolTypeEnum.DATA_SEARCH.value,
            config={
                "sql": "select 1",
                "referenced_tables": [],
                "input_variable": [],
                "output_fields": [],
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

        # 创建 BK_VISION 类型工具
        self.bkvision_uid = str(uuid.uuid4())
        self.bk_tool = self._create_bkvision_tool(self.uid_2, self.bkvision_uid, self.namespace)

    def _create_bkvision_tool(self, tool_uid, vision_uid, namespace):
        tool = Tool.objects.create(
            uid=tool_uid,
            version=1,
            name="BK Vision Tool",
            namespace=namespace,
            tool_type=ToolTypeEnum.BK_VISION.value,
            config={"uid": vision_uid},
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
        BkvisionToolConfig.objects.create(tool=tool, panel=panel)
        return tool

    def test_list_tool(self):
        resource = ListTool()

        data = {"keyword": "SQL", "limit": 10, "offset": 0}
        result = resource.perform_request(data)

        self.assertIsInstance(result, list)

        tool_names = [item["name"] for item in result]
        self.assertIn("SQL Tool", tool_names)

        data_empty = {"keyword": "", "limit": 10, "offset": 0}
        all_result = resource.perform_request(data_empty)
        self.assertGreaterEqual(len(all_result), 2)

        data_paged = {"keyword": "", "limit": 2, "offset": 0}
        paged_result = resource.perform_request(data_paged)
        self.assertEqual(len(paged_result), 2)

    def test_create_tool_sql(self):
        resource = CreateTool()
        new_uid = str(uuid.uuid4())
        data = {
            "uid": new_uid,
            "version": 1,
            "name": "New SQL Tool",
            "namespace": "default_ns",
            "tool_type": ToolTypeEnum.DATA_SEARCH.value,
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

        config = DataSearchToolConfig.objects.filter(tool=tool).first()
        self.assertIsNotNone(config)
        self.assertEqual(config.sql, "select * from test")

    def test_create_tool_bkvision(self):
        resource = CreateTool()
        new_uid = str(uuid.uuid4())
        vision_uid = str(uuid.uuid4())
        data = {
            "uid": new_uid,
            "version": 1,
            "name": "New BK Vision Tool",
            "namespace": "default_ns",
            "tool_type": ToolTypeEnum.BK_VISION.value,
            "config": {"uid": vision_uid},
            "description": "desc",
        }
        tool = resource.perform_request(data)
        self.assertEqual(tool.tool_type, ToolTypeEnum.BK_VISION.value)
        panel = VisionPanel.objects.filter(vision_id=vision_uid, is_deleted=False).first()
        self.assertIsNotNone(panel)
        bk_config = BkvisionToolConfig.objects.filter(tool=tool).first()
        self.assertIsNotNone(bk_config)
        self.assertEqual(bk_config.panel.id, panel.id)

    def test_update_tool_no_config_change(self):
        resource = UpdateTool()
        data = {
            "uid": self.sql_tool.uid,
            "version": 1,
            "name": "Updated SQL Tool",
            "namespace": self.sql_tool.namespace,
            "config": self.sql_tool.config,
            "description": "updated desc",
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
        }
        new_tool = resource.perform_request(data)
        self.assertNotEqual(new_tool.version, self.sql_tool.version)
        self.assertEqual(new_tool.version, self.sql_tool.version + 1)
        self.assertEqual(new_tool.config, new_config)
        self.assertEqual(new_tool.name, "Updated SQL Tool v2")

    def test_delete_tool(self):
        resource = DeleteTool()
        uid = self.sql_tool.uid

        resource.perform_request({"uid": uid})
        tool_exists = Tool.objects.filter(uid=uid, is_deleted=False).exists()
        self.assertFalse(tool_exists)

    def test_get_tool_detail(self):
        resource = GetToolDetail()
        data = {"uid": self.sql_tool.uid}
        tool = resource.perform_request(data)
        self.assertEqual(tool.uid, self.sql_tool.uid)
        self.assertEqual(tool.name, self.sql_tool.name)

import uuid

from django.test import TestCase
from django.utils import timezone

from apps.meta.models import Tag
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

        self.bkvision_uid = str(uuid.uuid4())
        self.bk_tool = self._create_bkvision_tool(self.uid_2, self.bkvision_uid, self.namespace)

        self.tag1 = Tag.objects.create(tag_name="tag1")
        self.tag2 = Tag.objects.create(tag_name="tag2")
        ToolTag.objects.create(tool_uid=self.sql_tool.uid, tag_id=self.tag1.tag_id)
        ToolTag.objects.create(tool_uid=self.bk_tool.uid, tag_id=self.tag2.tag_id)

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
        BkVisionToolConfig.objects.create(tool=tool, panel=panel)
        return tool

    def test_list_tool(self):
        resource = ListTool()

        data = {"keyword": "SQL", "limit": 10, "offset": 0}
        result = resource(data)
        tool_names = [item["name"] for item in result]
        self.assertIn("SQL Tool", tool_names)

        data_empty = {"keyword": "", "limit": 10, "offset": 0}
        all_result = resource(data_empty)
        self.assertGreaterEqual(len(all_result), 2)

        data_paged = {"keyword": "", "limit": 2, "offset": 0}
        paged_result = resource(data_paged)
        self.assertEqual(len(paged_result), 2)

        tag_result = resource({"keyword": "", "limit": 10, "offset": 0, "tags": [self.tag1.tag_id]})
        tag_names = [item["name"] for item in tag_result]
        self.assertIn("SQL Tool", tag_names)
        self.assertNotIn("BK Vision Tool", tag_names)

        tag_result_2 = resource({"keyword": "", "limit": 10, "offset": 0, "tags": [self.tag1.tag_id, self.tag2.tag_id]})
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
        bk_config = BkVisionToolConfig.objects.filter(tool=tool).first()
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

    def test_get_tool_detail(self):
        resource = GetToolDetail()
        data = {"uid": self.sql_tool.uid}
        tool = resource.perform_request(data)
        self.assertEqual(tool.uid, self.sql_tool.uid)
        self.assertEqual(tool.name, self.sql_tool.name)

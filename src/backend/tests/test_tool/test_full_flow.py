from unittest import mock

from api.bk_base.default import QuerySyncResource, UserAuthBatchCheck
from apps.permission.handlers.permission import Permission
from services.web.tool.constants import (
    DataSearchConfigTypeEnum,
    FieldCategory,
    ToolTypeEnum,
)
from services.web.tool.models import BkVisionToolConfig, Tool
from services.web.vision.models import VisionPanel
from tests.test_tool.constants import MOCK_API_RESPONSE

from ..base import TestCase


class TestToolFullFlow(TestCase):
    def test_sql_tool_full_flow(self):
        sql = "SELECT id, name FROM users WHERE id = :uid"
        resp = self.resource.tool.sql_analyse(sql=sql)
        config = {
            "sql": sql,
            "referenced_tables": resp["referenced_tables"],
            "input_variable": [
                {
                    "raw_name": v["raw_name"],
                    "display_name": v.get("display_name") or v["raw_name"],
                    "description": v.get("description") or "",
                    "required": v.get("required", True),
                    "field_category": FieldCategory.INPUT.value,
                    "choices": [],
                }
                for v in resp["sql_variables"]
            ],
            "output_fields": [
                {
                    "raw_name": f.get("raw_name") or f["display_name"],
                    "display_name": f["display_name"],
                    "description": "",
                }
                for f in resp["result_fields"]
            ],
            "prefer_storage": "doris",
        }
        uid = str("full_tool_123")
        resp = self.resource.tool.create_tool(
            {
                "version": 1,
                "name": "full_tool",
                "namespace": "default",
                "tool_type": ToolTypeEnum.DATA_SEARCH.value,
                "config": config,
                "description": "desc",
                "uid": uid,
                "data_search_config_type": DataSearchConfigTypeEnum.SQL.value,
            }
        )
        uid = resp["uid"]
        self.assertTrue(Tool.objects.filter(uid=uid).exists())

        with mock.patch.object(QuerySyncResource, 'bulk_request', return_value=MOCK_API_RESPONSE), mock.patch.object(
            UserAuthBatchCheck,
            'perform_request',
            return_value=[{"result": True, "user_id": "tester", "object_id": "users"}],
        ):
            result = self.resource.tool.execute_tool(
                {
                    "uid": uid,
                    "params": {
                        "tool_variables": [{"raw_name": "uid", "value": "1"}],
                        "page": 1,
                        "page_size": 10,
                    },
                }
            )
            result = result["data"]
            assert result["query_sql"] == "SELECT id, name FROM users WHERE id = '1' LIMIT 10"
            assert (
                result["count_sql"]
                == "SELECT COUNT(*) AS count FROM (SELECT id, name FROM users WHERE id = '1') AS _sub"
            )

        self.resource.tool.delete_tool({"uid": uid})
        self.assertFalse(Tool.objects.filter(uid=uid, is_deleted=False).exists())

    def test_vision_tool_full_flow(self):
        """测试 BK Vision 工具的全流程（创建、执行、删除）"""
        vision_uid = "vision_full_123"
        # 创建工具，使用丰富的 input_variable 示例
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
        resp = self.resource.tool.create_tool(
            {
                "uid": vision_uid,
                "version": 1,
                "name": "vision_full",
                "namespace": "default",
                "tool_type": ToolTypeEnum.BK_VISION.value,
                "config": {"uid": vision_uid, "input_variable": [example_var, example_var2]},
                "description": "desc",
            }
        )
        uid = resp["uid"]
        self.assertTrue(Tool.objects.filter(uid=uid).exists())

        # 执行工具（CreateTool 已自动创建 VisionPanel 及 BkVisionToolConfig）
        with mock.patch.object(Permission, "is_allowed", return_value=True):
            result = self.resource.tool.execute_tool({"uid": uid, "params": {}})
        # 校验执行结果包含 panel_id 且工具类型正确
        panel_id = result["data"]["panel_id"]
        self.assertTrue(VisionPanel.objects.filter(vision_id=vision_uid, id=panel_id).exists())
        self.assertTrue(BkVisionToolConfig.objects.filter(tool__uid=uid, panel_id=panel_id).exists())
        self.assertEqual(result["tool_type"], ToolTypeEnum.BK_VISION.value)

        # 删除工具
        self.resource.tool.delete_tool({"uid": uid})
        self.assertFalse(Tool.objects.filter(uid=uid, is_deleted=False).exists())

from unittest import mock

from api.bk_base.default import QuerySyncResource, UserAuthBatchCheck
from services.web.tool.constants import (
    DataSearchConfigTypeEnum,
    FieldCategory,
    ToolTypeEnum,
)
from services.web.tool.models import Tool
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

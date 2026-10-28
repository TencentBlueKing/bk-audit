"""普通检索、AI 快照、MCP 明细与导出保持同一用户快照脱敏边界。"""

import json
from copy import deepcopy
from unittest import mock

from api.bk_base.default import SafeQuerySyncResource
from apps.meta.constants import SensitiveResourceTypeEnum, SensitiveUserData
from apps.meta.models import SensitiveObject
from services.web.databus.models import CollectorPlugin
from services.web.query.ai_assistant.log_tools.context import LogQueryContext
from services.web.query.ai_assistant.schemas import SearchCondition
from services.web.query.ai_assistant.services.log_search import LogSearchService
from services.web.query.export.data_fetcher import DataFetcher
from services.web.query.resources.ai_assistant import MCPSearchLogs
from services.web.query.resources.doris import CollectorSearchAllResource
from tests.base import TestCase


class TestRawLogRedactionIntegration(TestCase):
    def setUp(self):
        self.plugin = CollectorPlugin.objects.create(
            namespace=self.namespace,
            collector_plugin_id=101,
            collector_plugin_name="example_plugin",
            collector_plugin_name_en="example_plugin",
            bkdata_biz_id=100,
            table_id=100,
            index_set_id=100,
        )
        SensitiveObject._objects.create(
            name="example private field",
            system_id=SensitiveUserData.SYSTEM_ID,
            resource_type=SensitiveResourceTypeEnum.RESOURCE.value,
            resource_id=SensitiveUserData.RESOURCE_ID,
            is_private=True,
            fields=[{"field_name": "snapshot_user_info.secret"}],
        )
        self.row = {
            "system_id": "example-system",
            "resource_type_id": "document",
            "action_id": "read",
            "snapshot_user_info": {"secret": "synthetic-hidden", "public": "visible"},
            "log": '{"secret":"synthetic-hidden","alias":"synthetic-hidden","action":"read","count":1}',
        }
        self.condition = SearchCondition(
            scope_type="system",
            scope_id="example-system",
            start_time="2026-01-01T00:00:00+08:00",
            end_time="2026-01-02T00:00:00+08:00",
        )
        self.query_params = {
            "namespace": self.namespace,
            "start_time": "2026-01-01 00:00:00",
            "end_time": "2026-01-02 00:00:00",
            "conditions": [],
            "page": 1,
            "page_size": 10,
            "bind_system_info": False,
        }

    def query_response(self, *args, **kwargs):
        """仅替代外部 SQL 请求，真实序列化、规则加载和格式化保持运行。"""
        return ({"list": [deepcopy(self.row)]}, {"list": [{"count": 1}]})

    def assert_clean_rows(self, rows):
        self.assertEqual(len(rows), 1)
        self.assertEqual(set(rows[0]["snapshot_user_info"]), {"public"})
        self.assertEqual(rows[0]["log"], self.row["log"])

    def test_collector_resource_and_export_preserve_raw_log_and_remove_private_snapshot(self):
        with (
            mock.patch("services.web.query.resources.doris.GlobalMetaConfig.get", return_value=101),
            mock.patch("services.web.query.resources.doris.api.bk_base.query_sync.bulk_request", self.query_response),
        ):
            result = CollectorSearchAllResource().request(**self.query_params)
            self.assert_clean_rows(result["results"])
            exported = DataFetcher.fetch_patch_logs(self.query_params, 1, 10)
            self.assert_clean_rows(exported)
            self.assertEqual(exported[0]["log"], result["results"][0]["log"])

    def test_ai_snapshot_preserves_upstream_json_without_exposing_internal_columns(self):
        module = "services.web.query.ai_assistant.services.log_search"
        with (
            mock.patch(f"{module}.CollectorPlugin.build_collector_rt", return_value=self.plugin.result_table_id),
            mock.patch(f"{module}.SearchLogPermission.get_scope_auth_systems", return_value=["example-system"]),
            mock.patch(f"{module}.api.bk_base.query_sync.bulk_request", self.query_response),
            mock.patch(f"{module}.resource.meta.system_list", return_value=[]),
        ):
            result = LogSearchService.search(
                condition=self.condition, namespace=self.namespace, username="admin", column_fields=["log"]
            )
        self.assertEqual(result.total, 1)
        self.assertEqual(result.samples, [{"log": json.loads(self.row["log"])}])

    def test_mcp_public_resource_preserves_raw_log_and_only_returns_requested_columns(self):
        context = LogQueryContext(
            username="admin",
            namespace=self.namespace,
            condition=self.condition,
            table=self.plugin.result_table_id,
            conditions=(),
        )
        with (
            mock.patch("services.web.query.resources.ai_assistant.get_request_username", return_value="admin"),
            mock.patch(
                "services.web.query.ai_assistant.log_tools.search.LogQueryContextService.build", return_value=context
            ),
            mock.patch.object(SafeQuerySyncResource, "bulk_request", side_effect=self.query_response),
        ):
            result = MCPSearchLogs().request(
                namespace=self.namespace,
                condition=self.condition.model_dump(mode="json"),
                fields=[{"raw_name": "log"}],
            )
        self.assertEqual(result["total"], 1)
        self.assertEqual([column["key"] for column in result["columns"]], ["log"])
        self.assertEqual(list(result["items"][0]), ["log"])
        self.assertEqual(result["items"][0]["log"], self.row["log"])

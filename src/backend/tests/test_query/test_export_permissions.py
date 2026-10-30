# -*- coding: utf-8 -*-
"""日志导出创建时的系统授权回归。

经真实 Resource.request、序列化、任务落库及后台分页链路验证数据范围。
仅替换外部授权决策、BKBase 和 Celery 投递，SQL 在合成 SQLite 日志上执行。
"""

import sqlite3
from copy import deepcopy
from unittest.mock import patch

from bk_resource.exceptions import ValidateException
from django.test import TestCase

from apps.meta.constants import ConfigLevelChoices
from apps.meta.models import GlobalMetaConfig
from services.web.common.scope_permission import ScopePermission
from services.web.databus.constants import COLLECTOR_PLUGIN_ID
from services.web.databus.models import CollectorPlugin
from services.web.query.ai_assistant.exceptions import AIPermissionDeniedError
from services.web.query.ai_assistant.schemas import SearchCondition
from services.web.query.ai_assistant.services.export import FullExportService
from services.web.query.export.data_fetcher import DataFetcher
from services.web.query.models import LogExportTask
from services.web.query.resources.doris import (
    CollectorSearchResource,
    CreateCollectorSearchExportTask,
)


class TestLogExportPermissions(TestCase):
    """预检、保存的查询及后台分页均只能命中创建时授权的系统。"""

    def setUp(self):
        plugin = CollectorPlugin.objects.create(
            namespace="example",
            collector_plugin_id=991,
            collector_plugin_name="synthetic_export",
            collector_plugin_name_en="synthetic_export",
            bkdata_biz_id=1,
            table_id=0,
            index_set_id=0,
        )
        GlobalMetaConfig.set(
            COLLECTOR_PLUGIN_ID, 991, config_level=ConfigLevelChoices.NAMESPACE.value, instance_key="example"
        )
        self.log_table = plugin.result_table_id
        self.logs = sqlite3.connect(":memory:")
        self.logs.row_factory = sqlite3.Row
        self.addCleanup(self.logs.close)
        self.logs.execute(
            f'CREATE TABLE "{plugin.result_table_id}"'
            "(system_id TEXT, thedate TEXT, dtEventTimeStamp INTEGER, log TEXT, "
            "gseIndex INTEGER DEFAULT 0, iterationIndex INTEGER DEFAULT 0)"
        )
        self.logs.executemany(
            f'INSERT INTO "{plugin.result_table_id}" (system_id, thedate, dtEventTimeStamp, log) VALUES (?, ?, ?, ?)',
            [
                ("allowed-system", "20260101", 1767268800000, "allowed-one"),
                ("allowed-system", "20260101", 1767272400000, "allowed-two"),
                ("other-system", "20260101", 1767276000000, "other"),
            ],
        )
        self.policy = self.enterContext(
            patch.object(ScopePermission, "get_system_ids_for_scope", return_value=["allowed-system"])
        )
        self.enterContext(patch("services.web.query.serializers.get_request_username", return_value="export-user"))
        self.enterContext(patch("core.models.get_request_username", return_value="export-user"))
        self.queries = []
        self.enterContext(patch("services.web.query.resources.doris.api.bk_base.query_sync.bulk_request", self._query))
        self.enterContext(patch("services.web.query.resources.doris.process_one_log_export_task.apply_async"))
        self.params = {
            "namespace": "example",
            "scope_type": "system",
            "scope_id": "allowed-system",
            "start_time": "2026-01-01T00:00:00+00:00",
            "end_time": "2026-01-02T00:00:00+00:00",
            "conditions": [],
            "page": 1,
            "page_size": 10,
            "sort_list": [{"order_field": "dtEventTimeStamp", "order_type": "asc"}],
            "bind_system_info": False,
        }

    def _query(self, requests):
        """以真实生成的 SQL 查询合成数据，不接受忽略条件的固定成功响应。"""
        results = []
        for request in requests:
            self.queries.append(request["sql"])
            # Doris RT 名以数字开头可直接引用，SQLite 需为这个固定表名补引号。
            sql = request["sql"].replace(f"FROM {self.log_table}", f'FROM "{self.log_table}"')
            rows = self.logs.execute(sql).fetchall()
            results.append({"list": [dict(row) for row in rows]})
        return results

    def _create(self, params=None, **extra):
        payload = {
            "namespace": "example",
            "query_params": deepcopy(self.params if params is None else params),
            "export_config": {"field_scope": "all"},
            **extra,
        }
        response = CreateCollectorSearchExportTask().request(**payload)
        return LogExportTask.objects.get(id=response["id"])

    @staticmethod
    def _system_condition(system_id):
        return {
            "field": {"raw_name": "system_id", "field_type": "string", "keys": []},
            "operator": "include",
            "filters": [system_id],
        }

    def test_export_matches_search_for_each_scope(self):
        for scope_type, scope_id in [
            ("system", "allowed-system"),
            ("scene", "42"),
            ("cross_system", None),
            ("cross_scene", None),
        ]:
            with self.subTest(scope_type=scope_type):
                params = {**self.params, "scope_type": scope_type, "scope_id": scope_id}
                searched = CollectorSearchResource().request(**deepcopy(params))
                self.assertEqual(searched["total"], 2)
                task = self._create(params)
                self.assertEqual(task.total, 2)
                self.assertEqual(task.created_by, "export-user")
                self.assertEqual(task.query_params["conditions"], [self._system_condition("allowed-system")])
                rows = DataFetcher.fetch_patch_logs(task.query_params, 1, 10)
                self.assertEqual([row["log"] for row in rows], ["allowed-one", "allowed-two"])

    def test_no_authorized_systems_yields_zero_in_precheck_and_fetch(self):
        self.policy.return_value = []
        task = self._create()
        self.assertEqual(task.total, 0)
        self.assertEqual(task.query_params["conditions"], [self._system_condition("")])
        self.assertEqual(DataFetcher.fetch_patch_logs(task.query_params, 1, 10), [])

    def test_user_system_filter_intersects_server_authorization(self):
        self.params["conditions"] = [self._system_condition("other-system")]
        task = self._create()
        self.assertEqual(task.total, 0)
        self.assertEqual(
            task.query_params["conditions"],
            [self._system_condition("allowed-system"), self._system_condition("other-system")],
        )
        self.assertEqual(DataFetcher.fetch_patch_logs(task.query_params, 1, 10), [])

    def test_missing_scope_is_rejected_before_query_or_task_creation(self):
        self.params.pop("scope_type")
        self.params.pop("scope_id")
        with self.assertRaises(ValidateException):
            self._create()
        self.assertEqual(self.queries, [])
        self.assertEqual(LogExportTask.objects.count(), 0)

    def test_client_ai_source_cannot_bypass_missing_scope(self):
        self.params.pop("scope_type")
        self.params.pop("scope_id")
        with self.assertRaises(ValidateException):
            self._create(
                source="ai_assistant",
                skip_permission=True,
                export_config={"field_scope": "all", "source": "ai_assistant"},
            )
        self.assertEqual(self.queries, [])
        self.assertEqual(LogExportTask.objects.count(), 0)

    def test_client_identity_cannot_override_system_authorization(self):
        self.params.update(username="admin", authorized_systems=["other-system"], skip_permission=True)
        task = self._create()
        self.assertEqual(task.total, 2)
        self.assertEqual(task.query_params["conditions"], [self._system_condition("allowed-system")])

    def test_pagination_preserves_created_scope_without_adding_time_conditions_to_task(self):
        task = self._create()
        self.policy.return_value = ["other-system"]
        self.assertEqual([row["log"] for row in DataFetcher.fetch_patch_logs(task.query_params, 1, 1)], ["allowed-one"])
        self.assertEqual([row["log"] for row in DataFetcher.fetch_patch_logs(task.query_params, 2, 1)], ["allowed-two"])
        self.assertEqual(DataFetcher.fetch_patch_logs(task.query_params, 3, 1), [])
        task.refresh_from_db()
        self.assertEqual(task.query_params["conditions"], [self._system_condition("allowed-system")])

    def test_ai_export_keeps_existing_authorized_target_without_system_scope_recheck(self):
        self.policy.side_effect = AssertionError("AI 已复检目标权限，不应新增仅系统视角鉴权")
        condition = SearchCondition(
            scope_type="system",
            scope_id="allowed-system",
            start_time=self.params["start_time"],
            end_time=self.params["end_time"],
        )
        with patch(
            "services.web.query.ai_assistant.services.export.SearchLogPermission.has_system_search_permission",
            return_value=True,
        ):
            response = FullExportService.create_task(
                condition=condition,
                namespace="example",
                export_config={"field_scope": "all"},
                task_name="synthetic-export",
                username="export-user",
            )
        task = LogExportTask.objects.get(id=response["id"])
        self.assertEqual(task.total, 2)
        self.assertEqual(task.query_params["conditions"], [self._system_condition("allowed-system")])
        self.assertEqual(
            [row["log"] for row in DataFetcher.fetch_patch_logs(task.query_params, 1, 10)],
            ["allowed-two", "allowed-one"],
        )

    def test_ai_export_denied_before_query_or_task_creation(self):
        condition = SearchCondition(
            scope_id="other-system",
            start_time=self.params["start_time"],
            end_time=self.params["end_time"],
        )
        with patch(
            "services.web.query.ai_assistant.services.export.SearchLogPermission.has_system_search_permission",
            return_value=False,
        ):
            with self.assertRaises(AIPermissionDeniedError):
                FullExportService.create_task(
                    condition=condition,
                    namespace="example",
                    export_config={"field_scope": "all"},
                    task_name="synthetic-denied",
                    username="export-user",
                )
        self.assertEqual(self.queries, [])
        self.assertEqual(LogExportTask.objects.count(), 0)

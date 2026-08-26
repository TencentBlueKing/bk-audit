# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
Copyright (C) 2023 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the specific language governing
permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.

F3 检索快照服务测试
"""

from unittest import mock

from services.web.query.ai_assistant.constants import (
    LOG_SEARCH_SNAPSHOT_VALUE_MAX_LENGTH,
)
from services.web.query.ai_assistant.exceptions import AIOutputInvalidError
from services.web.query.ai_assistant.services.log_search import LogSearchService
from tests.test_query.test_ai_assistant.base import AIAssistantTestCase

LOG_SEARCH_MODULE = "services.web.query.ai_assistant.services.log_search"

MOCK_HITS = [
    {
        "start_time": "2026-08-13 12:00:00",
        "username": "admin",
        "user_identify_type": "个人账号",
        "system_id": "bk_log",
        "action_id": "delete",
        "resource_type_id": "ticket",
        "instance_id": "Story-3000",
        "result_code": "成功(0)",
        "access_type": "WEB",
        "access_source_ip": "127.0.0.1",
        "dtEventTimeStamp": 1755057600000,
        "log": "原始日志内容",
        "extend_data": {"ticket_id": "Story-3000"},
    },
    {
        "start_time": "2026-08-13 11:00:00",
        "username": "zhangsan",
        "user_identify_type": "个人账号",
        "system_id": "bk_log",
        "action_id": "edit",
        "resource_type_id": "resource",
        "instance_id": "i-001",
        "result_code": "失败(-1)",
        "access_type": "API",
        "access_source_ip": "127.0.0.2",
        "dtEventTimeStamp": 1755054000000,
        "log": "另一条日志",
        "extend_data": {},
    },
]


@mock.patch(f"{LOG_SEARCH_MODULE}.resource.meta.system_list")
@mock.patch(f"{LOG_SEARCH_MODULE}.api.bk_base.query_sync")
@mock.patch(f"{LOG_SEARCH_MODULE}.SearchLogPermission.get_scope_auth_systems")
@mock.patch(f"{LOG_SEARCH_MODULE}.CollectorPlugin.build_collector_rt")
class TestLogSearchService(AIAssistantTestCase):
    """F3 LOG_SEARCH 快照执行

    注意：mock.patch 装饰器参数从下到上注入（最下面的装饰器对应第一个参数）。
    """

    def _setup_mocks(self, mock_build_rt, mock_get_authed, mock_query_sync, mock_system_list, **kwargs):
        mock_build_rt.return_value = "test_rt.doris"
        mock_get_authed.return_value = kwargs.get("authed_systems", [self.target_system_id])
        hits = kwargs.get("hits", MOCK_HITS)
        total = kwargs.get("total", len(hits))
        mock_query_sync.bulk_request.return_value = ({"list": hits}, {"list": [{"count": total}]})
        mock_system_list.return_value = [
            {"system_id": self.target_system_id, "name": self.target_system_name, "extra_field": "x"}
        ]

    def _search(self, condition=None, **kwargs):
        with mock.patch.object(LogSearchService, "_format_hits", side_effect=lambda rows, username: rows):
            return LogSearchService.search(
                condition=condition or self.make_condition(),
                namespace=self.namespace,
                username=self.username,
                **kwargs,
            )

    @staticmethod
    def _data_sql(mock_query_sync) -> str:
        (bulk_params,), _ = mock_query_sync.bulk_request.call_args
        return bulk_params[0]["sql"]

    def test_search_success(self, mock_build_rt, mock_get_authed, mock_query_sync, mock_system_list):
        self._setup_mocks(mock_build_rt, mock_get_authed, mock_query_sync, mock_system_list)

        output = self._search()

        self.assertEqual(output.total, 2)
        self.assertEqual(len(output.samples), 2)
        # 快照四键，无 query_sql
        self.assertEqual(set(output.model_dump().keys()), {"total", "columns", "samples", "query_summary"})
        # 产品需求 9 列固定展示字段（2026-08-14），首列 start_time
        expected_columns = [
            "start_time",
            "username",
            "system_id",
            "action_id",
            "resource_type_id",
            "instance_id",
            "result_code",
            "extend_data",
            "log",
        ]
        self.assertEqual([column.raw_name for column in output.columns], expected_columns)
        # 显示名用产品文案
        display_map = {column.raw_name: column.display_name for column in output.columns}
        self.assertEqual(display_map["system_id"], "来源系统(ID)")
        self.assertEqual(display_map["action_id"], "操作事件名(ID)")
        self.assertEqual(display_map["result_code"], "操作结果(Code)")
        # samples 按 columns 裁剪 + system_info 裁剪到 2 键
        column_keys = {column.full_key for column in output.columns}
        for sample in output.samples:
            self.assertTrue(set(sample.keys()) <= column_keys | {"system_info"})
            self.assertEqual(
                sample["system_info"], {"system_id": self.target_system_id, "name": self.target_system_name}
            )
        self.assertEqual(output.samples[0]["username"], "admin")
        # query_summary
        summary = output.query_summary
        self.assertEqual(summary.scope_id, self.target_system_id)
        self.assertEqual(summary.source, "field_condition")
        self.assertEqual(summary.time_range["start_time"], self.start_time)
        self.assertGreaterEqual(summary.took_ms, 0)
        self.assertTrue(summary.executed_at)

    def test_permission_injection_sql(self, mock_build_rt, mock_get_authed, mock_query_sync, mock_system_list):
        self._setup_mocks(mock_build_rt, mock_get_authed, mock_query_sync, mock_system_list)

        self._search()

        data_sql = self._data_sql(mock_query_sync)
        # 权限条件注入（显式 username 取得的授权系统）
        self.assertIn("`system_id` IN ('bk_log')", data_sql)
        # 时间条件注入（4 条 GTE/LTE）
        self.assertIn("`thedate`>='20260813'", data_sql)
        self.assertIn("`thedate`<='20260814'", data_sql)
        mock_get_authed.assert_called_once_with(
            scope_type="system", scope_id=self.target_system_id, username=self.username
        )

    def test_no_permission_natural_zero_hit(self, mock_build_rt, mock_get_authed, mock_query_sync, mock_system_list):
        """无权限时 get_scope_auth_systems 返回 [""]，SQL 自然零命中"""
        self._setup_mocks(
            mock_build_rt,
            mock_get_authed,
            mock_query_sync,
            mock_system_list,
            hits=[],
            total=0,
            authed_systems=[""],
        )

        output = self._search()

        self.assertIn("IN ('')", self._data_sql(mock_query_sync))
        self.assertEqual(output.total, 0)
        self.assertEqual(output.samples, [])

    def test_zero_hit_is_success(self, mock_build_rt, mock_get_authed, mock_query_sync, mock_system_list):
        self._setup_mocks(mock_build_rt, mock_get_authed, mock_query_sync, mock_system_list, hits=[], total=0)

        output = self._search()
        self.assertEqual(output.total, 0)
        self.assertEqual(output.samples, [])

    def test_invalid_field_rejected(self, mock_build_rt, mock_get_authed, mock_query_sync, mock_system_list):
        self._setup_mocks(mock_build_rt, mock_get_authed, mock_query_sync, mock_system_list)
        condition = self.make_condition(conditions=[self.make_field_condition(raw_name="not_a_field")])

        with self.assertRaises(AIOutputInvalidError) as ctx:
            self._search(condition=condition)
        self.assertEqual(ctx.exception.error_code, "AI_OUTPUT_INVALID")
        mock_query_sync.bulk_request.assert_not_called()

    def test_invalid_operator_rejected(self, mock_build_rt, mock_get_authed, mock_query_sync, mock_system_list):
        self._setup_mocks(mock_build_rt, mock_get_authed, mock_query_sync, mock_system_list)
        # username 白名单操作符为 [include, eq]，like 越权
        condition = self.make_condition(
            conditions=[self.make_field_condition(raw_name="username", operator="like", filters=["adm"])]
        )

        with self.assertRaises(AIOutputInvalidError):
            self._search(condition=condition)
        mock_query_sync.bulk_request.assert_not_called()

    def test_sample_value_truncated(self, mock_build_rt, mock_get_authed, mock_query_sync, mock_system_list):
        long_value = "x" * (LOG_SEARCH_SNAPSHOT_VALUE_MAX_LENGTH + 100)
        hits = [dict(MOCK_HITS[0], username=long_value)]
        self._setup_mocks(mock_build_rt, mock_get_authed, mock_query_sync, mock_system_list, hits=hits, total=1)

        output = self._search()
        self.assertEqual(len(output.samples[0]["username"]), LOG_SEARCH_SNAPSHOT_VALUE_MAX_LENGTH)

    def test_snapshot_size_fixed(self, mock_build_rt, mock_get_authed, mock_query_sync, mock_system_list):
        """固化口径：page=1 / size=100 / 最新排序"""
        self._setup_mocks(mock_build_rt, mock_get_authed, mock_query_sync, mock_system_list)

        self._search()

        data_sql = self._data_sql(mock_query_sync)
        self.assertIn("LIMIT 100", data_sql)
        self.assertIn("ORDER BY", data_sql)

    def test_source_natural_language(self, mock_build_rt, mock_get_authed, mock_query_sync, mock_system_list):
        self._setup_mocks(mock_build_rt, mock_get_authed, mock_query_sync, mock_system_list)
        output = self._search(source="natural_language")
        self.assertEqual(output.query_summary.source, "natural_language")

    def test_key_normalization_fallback(self, mock_build_rt, mock_get_authed, mock_query_sync, mock_system_list):
        """Doris 返回小写键时按归一逻辑取值"""
        hits = [{key.lower(): value for key, value in MOCK_HITS[0].items()}]
        self._setup_mocks(mock_build_rt, mock_get_authed, mock_query_sync, mock_system_list, hits=hits, total=1)

        output = self._search()
        self.assertEqual(output.samples[0]["username"], "admin")

    def test_format_hits_with_explicit_username(
        self, mock_build_rt, mock_get_authed, mock_query_sync, mock_system_list
    ):
        """D1：脱敏判定身份显式传递，不依赖请求上下文"""
        with mock.patch(f"{LOG_SEARCH_MODULE}.SearchDataParser") as mock_parser:
            rows = [{"a": 1}]
            LogSearchService._format_hits(rows, "alice")
            mock_parser.return_value.parse_data.assert_called_once_with(rows, username="alice")

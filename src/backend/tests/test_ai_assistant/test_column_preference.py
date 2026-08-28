# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
Copyright (C) 2023 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

"""
展示字段偏好（AI 日志检索列自定义）：服务层 + 检索快照列 + 用户隔离。
"""

from unittest import mock

from services.web.ai_assistant.models import UserColumnPreference
from services.web.ai_assistant.resources.column import ApplyColumnConfig, ListColumnConfig
from services.web.ai_assistant.services.column_preference import (
    LOCKED_COLUMN_NAMES,
    ColumnPreferenceService,
)
from services.web.query.ai_assistant.constants import SNAPSHOT_DEFAULT_COLUMNS
from tests.test_ai_assistant.base import AIAssistantPlatformTestCase
from tests.test_query.test_ai_assistant.base import AIAssistantTestCase

LOG_SEARCH_MODULE = "services.web.query.ai_assistant.services.log_search"
PREFERENCE_MODULE = "services.web.ai_assistant.services.column_preference"

EXPECTED_DEFAULT_COLUMNS = [raw_name for raw_name, _ in SNAPSHOT_DEFAULT_COLUMNS]


class ColumnPreferenceServiceTest(AIAssistantPlatformTestCase):
    """展示字段偏好服务"""

    def test_list_columns_default(self):
        """无偏好记录：已选 = 九个固定列；可选 = 全量字段（固定列标记 is_locked）"""

        config = ColumnPreferenceService(username=self.user).list_columns()

        self.assertEqual(config["selected_fields"], EXPECTED_DEFAULT_COLUMNS)
        available_map = {field["raw_name"]: field for field in config["available_fields"]}
        # 固定列 is_locked 且 display_name 用产品文案
        for raw_name, display_name in SNAPSHOT_DEFAULT_COLUMNS:
            self.assertTrue(available_map[raw_name]["is_locked"])
            self.assertEqual(available_map[raw_name]["display_name"], display_name)
        # 自选字段不锁死
        self.assertFalse(available_map["request_id"]["is_locked"])
        # 可选字段与日志检索字段清单同源（全量）
        self.assertIn("request_id", available_map)
        self.assertIn("event_id", available_map)

    def test_apply_columns_normalization(self):
        """应用：非法字段过滤 + 去重 + 固定列兜底补齐且顺序在前"""

        selected = ColumnPreferenceService(username=self.user).apply_columns(
            ["request_id", "not_a_field", "event_id", "request_id"]
        )

        self.assertEqual(selected, EXPECTED_DEFAULT_COLUMNS + ["request_id", "event_id"])
        # 落库
        preference = UserColumnPreference.objects.get(created_by=self.user)
        self.assertEqual(preference.selected_fields, EXPECTED_DEFAULT_COLUMNS + ["request_id", "event_id"])

    def test_apply_columns_locked_always_included(self):
        """固定列锁死：提交不含固定列时后端自动补齐"""

        selected = ColumnPreferenceService(username=self.user).apply_columns(["request_id"])

        self.assertEqual(selected, EXPECTED_DEFAULT_COLUMNS + ["request_id"])

    def test_apply_columns_overrides_previous(self):
        """再次应用覆盖旧偏好"""

        service = ColumnPreferenceService(username=self.user)
        service.apply_columns(["request_id"])
        selected = service.apply_columns(["event_id"])

        self.assertEqual(selected, EXPECTED_DEFAULT_COLUMNS + ["event_id"])
        self.assertEqual(UserColumnPreference.objects.filter(created_by=self.user).count(), 1)

    def test_user_isolation(self):
        """用户隔离：A 的偏好不影响 B（B 仍为默认九列）"""

        ColumnPreferenceService(username=self.user).apply_columns(["request_id"])

        other_selected = ColumnPreferenceService(username="other_user").get_selected_fields()

        self.assertEqual(other_selected, EXPECTED_DEFAULT_COLUMNS)
        self.assertFalse(UserColumnPreference.objects.filter(created_by="other_user").exists())


@mock.patch(f"{LOG_SEARCH_MODULE}.resource.meta.system_list")
@mock.patch(f"{LOG_SEARCH_MODULE}.api.bk_base.query_sync")
@mock.patch(f"{LOG_SEARCH_MODULE}.SearchLogPermission.get_scope_auth_systems")
@mock.patch(f"{LOG_SEARCH_MODULE}.CollectorPlugin.build_collector_rt")
class ColumnPreferenceSearchTest(AIAssistantTestCase):
    """检索快照列按用户偏好输出（query 组件测试保持零 DB 纪律：偏好读取 mock）"""

    def _setup_mocks(self, mock_build_rt, mock_get_authed, mock_query_sync, mock_system_list, hits):
        mock_build_rt.return_value = "test_rt.doris"
        mock_get_authed.return_value = [self.target_system_id]
        mock_query_sync.bulk_request.return_value = ({"list": hits}, {"list": [{"count": len(hits)}]})
        mock_system_list.return_value = [
            {"system_id": self.target_system_id, "name": self.target_system_name, "extra_field": "x"}
        ]

    def test_search_columns_follow_preference(
        self, mock_build_rt, mock_get_authed, mock_query_sync, mock_system_list
    ):
        """有偏好：快照 columns = 九列 + 自选列，samples 按列裁剪输出自选值"""

        hits = [
            {
                "username": "admin",
                "system_id": self.target_system_id,
                "request_id": "req-001",
                "dtEventTimeStamp": 1755057600000,
            }
        ]
        self._setup_mocks(mock_build_rt, mock_get_authed, mock_query_sync, mock_system_list, hits)

        from services.web.query.ai_assistant.services.log_search import LogSearchService

        with mock.patch.object(LogSearchService, "_format_hits", side_effect=lambda rows, username: rows):
            output = LogSearchService.search(
                condition=self.make_condition(),
                namespace=self.namespace,
                username=self.username,
                column_fields=EXPECTED_DEFAULT_COLUMNS + ["request_id"],
            )

        column_names = [column.raw_name for column in output.columns]
        self.assertEqual(column_names, EXPECTED_DEFAULT_COLUMNS + ["request_id"])
        # 自选列值进入 samples
        self.assertEqual(output.samples[0]["request_id"], "req-001")

    def test_search_columns_default_without_preference(
        self, mock_build_rt, mock_get_authed, mock_query_sync, mock_system_list
    ):
        """无偏好：快照 columns 仍为九个固定列"""

        hits = [{"username": "admin", "system_id": self.target_system_id, "dtEventTimeStamp": 1755057600000}]
        self._setup_mocks(mock_build_rt, mock_get_authed, mock_query_sync, mock_system_list, hits)

        from services.web.query.ai_assistant.services.log_search import LogSearchService

        with mock.patch.object(LogSearchService, "_format_hits", side_effect=lambda rows, username: rows):
            output = LogSearchService.search(
                condition=self.make_condition(), namespace=self.namespace, username=self.username
            )

        self.assertEqual([column.raw_name for column in output.columns], EXPECTED_DEFAULT_COLUMNS)


class ColumnConfigResourceTest(AIAssistantPlatformTestCase):
    """展示字段配置接口（查询 + 应用）"""

    def test_list_resource(self):
        with mock.patch(
            "services.web.ai_assistant.resources.column.get_request_username", return_value=self.user
        ):
            config = ListColumnConfig().perform_request({})

        self.assertEqual(config["selected_fields"], EXPECTED_DEFAULT_COLUMNS)
        self.assertTrue(any(field["is_locked"] for field in config["available_fields"]))

    def test_apply_resource(self):
        with mock.patch(
            "services.web.ai_assistant.resources.column.get_request_username", return_value=self.user
        ):
            result = ApplyColumnConfig().perform_request({"fields": ["request_id"]})

        self.assertEqual(result["selected_fields"], EXPECTED_DEFAULT_COLUMNS + ["request_id"])
        self.assertTrue(UserColumnPreference.objects.filter(created_by=self.user).exists())

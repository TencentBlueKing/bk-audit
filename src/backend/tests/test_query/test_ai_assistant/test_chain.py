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
"""

"""
组件串联集成演练（D6）

F1（字段上下文）→ F2（NL2JSON）→ F3（检索快照）→ F4（预览/全量导出）
全链路仅 mock 外部调用（IAM / system_list / AIDev / bk_base / 导出任务创建），
验证「NL 输出 = LOG_SEARCH 输入 = 导出 query_params 数据源」的零转换设计承诺。
"""

import io
import json
from unittest import mock

import openpyxl

from services.web.query.ai_assistant.services.export import (
    FullExportService,
    PreviewExportService,
)
from services.web.query.ai_assistant.services.field_context import FieldContextService
from services.web.query.ai_assistant.services.log_search import LogSearchService
from services.web.query.ai_assistant.services.nl2json import NL2JSONService
from tests.test_query.test_ai_assistant.base import AIAssistantTestCase

FIELD_CONTEXT_MODULE = "services.web.query.ai_assistant.services.field_context"
NL2JSON_MODULE = "services.web.query.ai_assistant.services.nl2json"
LOG_SEARCH_MODULE = "services.web.query.ai_assistant.services.log_search"
EXPORT_MODULE = "services.web.query.ai_assistant.services.export"


class TestComponentChain(AIAssistantTestCase):
    """F1 → F2 → F3 → F4 组件串联"""

    def test_full_chain(self):
        # ---------- F1：SYSTEM_SELECTION ----------
        with (
            mock.patch(
                f"{FIELD_CONTEXT_MODULE}.SearchLogPermission.has_system_search_permission", return_value=True
            ),
            mock.patch(f"{FIELD_CONTEXT_MODULE}.resource.meta.system_list") as mock_system_list,
            mock.patch(f"{FIELD_CONTEXT_MODULE}.GlobalMetaConfig.get") as mock_meta_get,
        ):
            mock_system_list.return_value = [
                {"system_id": self.target_system_id, "name": self.target_system_name}
            ]
            mock_meta_get.return_value = {
                "systems": {
                    self.target_system_id: {
                        "extension_fields": [
                            {"raw_name": "extend_data", "keys": ["ticket_id"], "display_name": "工单内容"}
                        ]
                    }
                }
            }
            selection = FieldContextService.build_selection(
                namespace=self.namespace, system_ids=[self.target_system_id], username=self.username
            )
        self.assertEqual(len(selection.systems), 1)
        self.assertEqual(len(selection.systems[0].extension_fields), 1)

        # ---------- F2：NATURAL_LANGUAGE_SEARCH（AI 输出拓展字段条件） ----------
        ai_output = {
            "conditions": [
                {
                    "raw_name": "extend_data",
                    "keys": ["ticket_id"],
                    "field_type": None,
                    "operator": "eq",
                    "filters": ["Story-3000"],
                }
            ],
            "start_time": self.start_time,
            "end_time": self.end_time,
        }
        with mock.patch(f"{NL2JSON_MODULE}.api.bk_plugins_ai_agent.chat_completion") as mock_chat:
            mock_chat.return_value = json.dumps(ai_output)
            condition = NL2JSONService.convert(
                query_text="查一下工单内容为 Story-3000 的日志",
                selection=selection,
                scope_id=self.target_system_id,
                username=self.username,
            )
        # 零转换断言：condition 形态即 LOG_SEARCH 输入
        self.assertEqual(condition.scope_id, self.target_system_id)
        self.assertEqual(condition.conditions[0].field.keys, ["ticket_id"])

        # ---------- F3：LOG_SEARCH ----------
        hits = [
            {
                "start_time": "2026-08-13 12:00:00",
                "username": "admin",
                "user_identify_type": "个人账号",
                "system_id": self.target_system_id,
                "result_code": "成功(0)",
                "access_type": "WEB",
                "access_source_ip": "127.0.0.1",
                "extend_data": {"ticket_id": "Story-3000"},
            }
        ]
        with (
            mock.patch(f"{LOG_SEARCH_MODULE}.CollectorPlugin.build_collector_rt", return_value="test_rt.doris"),
            mock.patch(
                f"{LOG_SEARCH_MODULE}.SearchLogPermission.get_scope_auth_systems",
                return_value=[self.target_system_id],
            ),
            mock.patch(f"{LOG_SEARCH_MODULE}.api.bk_base.query_sync") as mock_query_sync,
            mock.patch(f"{LOG_SEARCH_MODULE}.resource.meta.system_list") as mock_system_list,
            mock.patch.object(LogSearchService, "_format_hits", side_effect=lambda rows, username: rows),
        ):
            mock_query_sync.bulk_request.return_value = ({"list": hits}, {"list": [{"count": 1}]})
            mock_system_list.return_value = [
                {"system_id": self.target_system_id, "name": self.target_system_name}
            ]
            output = LogSearchService.search(
                condition=condition,
                namespace=self.namespace,
                username=self.username,
                source="natural_language",
            )
        self.assertEqual(output.total, 1)
        self.assertEqual(len(output.samples), 1)
        self.assertEqual(output.query_summary.source, "natural_language")

        # ---------- F4a：预览导出（快照不重查） ----------
        preview = PreviewExportService.export(output)
        workbook = openpyxl.load_workbook(io.BytesIO(preview.content))
        sheet = workbook.active
        first_data_row = [cell.value for cell in sheet[4]]
        self.assertIn("admin", first_data_row)

        # ---------- F4b：全量导出（condition 原样重建 query_params） ----------
        with (
            mock.patch(
                f"{EXPORT_MODULE}.SearchLogPermission.has_system_search_permission", return_value=True
            ),
            mock.patch(f"{EXPORT_MODULE}.resource.query.create_collector_search_export_task") as mock_create,
        ):
            FullExportService.create_task(
                condition=condition,
                namespace=self.namespace,
                export_config={"field_scope": "all", "fields": []},
                task_name=FullExportService.build_task_name("abcd1234-5678"),
                username=self.username,
            )
        _, kwargs = mock_create.call_args
        query_params = kwargs["query_params"]
        # 数据范围来自快照 condition（前端不能覆盖）
        self.assertEqual(query_params["start_time"], self.start_time)
        self.assertEqual(query_params["end_time"], self.end_time)
        # 拓展字段条件原样透传（零转换）
        extension_conditions = [
            cond for cond in query_params["conditions"] if cond["field"]["raw_name"] == "extend_data"
        ]
        self.assertEqual(len(extension_conditions), 1)
        self.assertEqual(extension_conditions[0]["field"]["keys"], ["ticket_id"])
        self.assertEqual(extension_conditions[0]["filters"], ["Story-3000"])

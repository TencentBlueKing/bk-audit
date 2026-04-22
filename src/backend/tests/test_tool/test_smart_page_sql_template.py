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
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

import uuid
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase
from pydantic import ValidationError

from services.web.tool.constants import SmartPageToolConfig, ToolTypeEnum
from services.web.tool.exceptions import (
    SmartPageBindParamMissingError,
    SmartPageSqlTemplateRenderError,
)
from services.web.tool.executor.model import (
    SmartPageExecuteParams,
    SmartPageExecuteResult,
    SmartPageSqlTemplateExecuteResult,
)
from services.web.tool.executor.smart_page import render_sql_template
from services.web.tool.models import Tool
from services.web.tool.resources import CreateTool, ExecuteTool, UpdateTool


def normalize_sql(sql: str) -> str:
    """规范化 SQL 空白字符，便于稳定断言。"""
    return " ".join(sql.split())


class TestSmartPageConfig(SimpleTestCase):
    """SmartPage 工具配置模型测试"""

    def test_should_validate_sql_template_datasource_with_typed_config(self):
        cfg = {
            "marker_type": "risk_profile",
            "data_sources": [
                {
                    "name": "risk_event_source",
                    "description": "风险事件",
                    "data_source_type": "sql_template",
                    "config": {"sql_template": "SELECT 1"},
                }
            ],
        }
        model = SmartPageToolConfig.model_validate(cfg)
        self.assertEqual(model.marker_type, "risk_profile")
        self.assertEqual(model.data_sources[0].name, "risk_event_source")
        self.assertEqual(model.data_sources[0].data_source_type, "sql_template")
        self.assertEqual(model.data_sources[0].config.sql_template, "SELECT 1")

    def test_should_reject_duplicate_datasource_name(self):
        cfg = {
            "data_sources": [
                {
                    "name": "dup",
                    "data_source_type": "sql_template",
                    "config": {"sql_template": "SELECT 1"},
                },
                {
                    "name": "dup",
                    "data_source_type": "sql_template",
                    "config": {"sql_template": "SELECT 2"},
                },
            ]
        }
        with self.assertRaises(ValidationError):
            SmartPageToolConfig.model_validate(cfg)

    def test_should_reject_unsupported_datasource_type(self):
        cfg = {
            "data_sources": [
                {
                    "name": "unknown_source",
                    "data_source_type": "unsupported_type",
                    "config": {"sql_template": "SELECT 1"},
                }
            ]
        }
        with self.assertRaises(ValidationError):
            SmartPageToolConfig.model_validate(cfg)


class TestSmartPageExecuteModels(SimpleTestCase):
    """SmartPage 执行参数/结果模型测试"""

    def test_execute_models_should_validate(self):
        params = SmartPageExecuteParams.model_validate(
            {
                "data_source_name": "risk_event_source",
                "params": {"kw": "risk", "enabled": "yes"},
            }
        )
        self.assertEqual(params.data_source_name, "risk_event_source")
        self.assertEqual(params.params, {"kw": "risk", "enabled": "yes"})

        result = SmartPageExecuteResult.model_validate(
            {
                "data_source_name": "risk_event_source",
                "result": {
                    "data_source_type": "sql_template",
                    "results": [],
                    "rendered_sql": "SELECT 1",
                },
            }
        )
        typed_result = SmartPageSqlTemplateExecuteResult.model_validate(result.result.model_dump())
        self.assertEqual(typed_result.data_source_type, "sql_template")
        self.assertEqual(typed_result.rendered_sql, "SELECT 1")


class TestSqlTemplateRenderer(SimpleTestCase):
    """SQL 模板渲染器测试"""

    def test_render_template_should_support_has_and_bind(self):
        sql = "SELECT * FROM t WHERE 1=1 {% if has('kw') %} AND name = '{{ bind('kw') }}' {% endif %}"
        rendered = render_sql_template(sql, {"kw": "alice"})
        self.assertEqual(normalize_sql(rendered), "SELECT * FROM t WHERE 1=1 AND name = 'alice'")

    def test_bind_should_raise_when_missing_param(self):
        sql = "SELECT * FROM t WHERE name='{{ bind('kw') }}'"
        with self.assertRaises(SmartPageBindParamMissingError):
            render_sql_template(sql, {})

    def test_bind_should_convert_by_output_type_enum(self):
        sql = "SELECT * FROM t WHERE id = {{ bind('id', output_type='int') }}"
        rendered = render_sql_template(sql, {"id": "42"})
        self.assertEqual(normalize_sql(rendered), "SELECT * FROM t WHERE id = 42")

    def test_bind_should_output_raw_string_without_auto_quotes(self):
        sql = "SELECT * FROM t WHERE name='{{ bind('kw') }}'"
        rendered = render_sql_template(sql, {"kw": "alice"})
        self.assertEqual(normalize_sql(rendered), "SELECT * FROM t WHERE name='alice'")

    def test_bind_should_escape_single_quote_when_template_has_quotes(self):
        sql = "SELECT * FROM t WHERE name='{{ bind('kw') }}'"
        rendered = render_sql_template(sql, {"kw": "a'lice"})
        self.assertEqual(normalize_sql(rendered), "SELECT * FROM t WHERE name='a\\'lice'")

    def test_bind_should_raise_for_invalid_output_type(self):
        sql = "SELECT * FROM t WHERE id = {{ bind('id', output_type='bad_type') }}"
        with self.assertRaises(SmartPageSqlTemplateRenderError):
            render_sql_template(sql, {"id": "1"})

    def test_bind_should_render_empty_list_for_in_clause(self):
        sql = "SELECT * FROM t WHERE id IN ({{ bind('ids', output_type='int') }})"
        rendered = render_sql_template(sql, {"ids": []})
        self.assertEqual(normalize_sql(rendered), "SELECT * FROM t WHERE id IN ()")

    def test_bind_should_quote_string_list_items_for_in_clause(self):
        sql = "SELECT * FROM t WHERE username IN ({{ bind('users') }})"
        rendered = render_sql_template(sql, {"users": ["alice", "bob"]})
        self.assertEqual(normalize_sql(rendered), "SELECT * FROM t WHERE username IN ('alice', 'bob')")

    def test_bind_should_render_bool_variants(self):
        sql = "SELECT * FROM t WHERE enabled = {{ bind('enabled', output_type='bool') }}"
        rendered = render_sql_template(sql, {"enabled": "yes"})
        self.assertEqual(normalize_sql(rendered), "SELECT * FROM t WHERE enabled = TRUE")

    def test_bind_should_render_various_scalar_types(self):
        cases = [
            ("SELECT * FROM t WHERE id = {{ bind('value') }}", {"value": 7}, "SELECT * FROM t WHERE id = 7"),
            (
                "SELECT * FROM t WHERE score = {{ bind('value', output_type='float') }}",
                {"value": "1.5"},
                "SELECT * FROM t WHERE score = 1.5",
            ),
            (
                "SELECT * FROM t WHERE enabled = {{ bind('value', output_type='bool') }}",
                {"value": 0},
                "SELECT * FROM t WHERE enabled = FALSE",
            ),
            (
                "SELECT * FROM t WHERE value IS {{ bind('value') }}",
                {"value": None},
                "SELECT * FROM t WHERE value IS NULL",
            ),
        ]
        for sql, params, expected in cases:
            with self.subTest(sql=sql, params=params):
                rendered = render_sql_template(sql, params)
                self.assertEqual(normalize_sql(rendered), expected)

    def test_render_template_should_cover_various_sql_patterns(self):
        cases = [
            (
                "SELECT * FROM t WHERE 1=1 {% if has('kw') %} AND name LIKE '%{{ bind('kw') }}%' {% endif %}",
                {"kw": "audit"},
                "SELECT * FROM t WHERE 1=1 AND name LIKE '%audit%'",
            ),
            (
                "SELECT * FROM t WHERE 1=1 {% if has('kw') %} AND name = '{{ bind('kw') }}' {% endif %}",
                {},
                "SELECT * FROM t WHERE 1=1",
            ),
            (
                "SELECT * FROM t WHERE id IN ({{ bind('ids', output_type='int') }})",
                {"ids": ["1", 2, 3]},
                "SELECT * FROM t WHERE id IN (1, 2, 3)",
            ),
            (
                "SELECT * FROM t WHERE username IN ({{ bind('users') }})",
                {"users": ["alice", "o'bob"]},
                "SELECT * FROM t WHERE username IN ('alice', 'o\\'bob')",
            ),
            (
                (
                    "SELECT * FROM t WHERE enabled = {{ bind('enabled', output_type='bool') }} "
                    "AND deleted = {{ bind('deleted', output_type='bool') }}"
                ),
                {"enabled": "true", "deleted": "no"},
                "SELECT * FROM t WHERE enabled = TRUE AND deleted = FALSE",
            ),
            (
                (
                    "SELECT * FROM t WHERE score >= {{ bind('min_score', output_type='float') }} "
                    "AND score < {{ bind('max_score', output_type='float') }}"
                ),
                {"min_score": "1.25", "max_score": 9},
                "SELECT * FROM t WHERE score >= 1.25 AND score < 9.0",
            ),
            (
                "SELECT * FROM t WHERE updated_at IS {{ bind('updated_at') }}",
                {"updated_at": None},
                "SELECT * FROM t WHERE updated_at IS NULL",
            ),
            (
                "SELECT * FROM t WHERE env = '{{ bind('env') }}' AND id IN ({{ bind('ids', output_type='int') }})",
                {"env": "prod", "ids": [10, 11]},
                "SELECT * FROM t WHERE env = 'prod' AND id IN (10, 11)",
            ),
        ]
        for sql, params, expected in cases:
            with self.subTest(sql=sql, params=params):
                rendered = render_sql_template(sql, params)
                self.assertEqual(normalize_sql(rendered), expected)


class SmartPageAPITestCase(TestCase):
    """Smart Page 工具 API 层集成测试"""

    def setUp(self):
        self.namespace = "default_ns"

    def test_create_smart_page_tool(self):
        create_resource = CreateTool()
        create_data = {
            "name": f"Smart Page Demo {uuid.uuid4()}",
            "namespace": self.namespace,
            "tool_type": ToolTypeEnum.SMART_PAGE.value,
            "config": {
                "data_sources": [
                    {
                        "name": "risk_event_source",
                        "data_source_type": "sql_template",
                        "config": {"sql_template": "SELECT 1"},
                    }
                ]
            },
            "description": "smart page test",
        }
        created = create_resource(create_data)

        saved_tool = Tool.last_version_tool(uid=created["uid"])
        self.assertEqual(saved_tool.tool_type, ToolTypeEnum.SMART_PAGE.value)

    def test_execute_smart_page_tool(self):
        create_resource = CreateTool()
        created = create_resource(
            {
                "name": f"Smart Page Execute {uuid.uuid4()}",
                "namespace": self.namespace,
                "tool_type": ToolTypeEnum.SMART_PAGE.value,
                "config": {
                    "data_sources": [
                        {
                            "name": "risk_event_source",
                            "data_source_type": "sql_template",
                            "config": {"sql_template": "SELECT 1"},
                        }
                    ]
                },
                "description": "smart page execute",
            }
        )

        with patch("services.web.tool.executor.tool.api.bk_base.query_sync.bulk_request") as mock_bulk:
            mock_bulk.return_value = [{"list": [{"col": "val"}]}]
            execute_resource = ExecuteTool()
            execute_resp = execute_resource(
                {
                    "uid": created["uid"],
                    "params": {
                        "data_source_name": "risk_event_source",
                        "params": {},
                    },
                }
            )

        self.assertEqual(execute_resp["tool_type"], ToolTypeEnum.SMART_PAGE.value)
        self.assertEqual(execute_resp["data"]["result"]["data_source_type"], "sql_template")
        self.assertEqual(execute_resp["data"]["result"]["results"], [{"col": "val"}])

    def test_update_smart_page_tool(self):
        create_resource = CreateTool()
        created = create_resource(
            {
                "name": f"Smart Page Update {uuid.uuid4()}",
                "namespace": self.namespace,
                "tool_type": ToolTypeEnum.SMART_PAGE.value,
                "config": {
                    "data_sources": [
                        {
                            "name": "risk_event_source",
                            "data_source_type": "sql_template",
                            "config": {"sql_template": "SELECT 1"},
                        }
                    ]
                },
                "description": "smart page update",
            }
        )

        update_resource = UpdateTool()
        updated = update_resource(
            {
                "uid": created["uid"],
                "config": {
                    "data_sources": [
                        {
                            "name": "risk_event_source",
                            "data_source_type": "sql_template",
                            "config": {"sql_template": "SELECT 2"},
                        }
                    ]
                },
                "tags": [],
            }
        )
        self.assertEqual(updated["version"], 2)

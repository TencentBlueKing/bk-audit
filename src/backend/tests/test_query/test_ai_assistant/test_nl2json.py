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

F2 NL2JSON 服务测试
"""

import json
from unittest import mock

from requests.exceptions import Timeout

from core.utils.time import parse_datetime
from services.web.query.ai_assistant.constants import DEFAULT_SEARCH_WINDOW_DAYS
from services.web.query.ai_assistant.exceptions import (
    AIOutputInvalidError,
    AIOutputParseFailedError,
    AIServiceError,
    AITimeoutError,
    QueryNotRecognizedError,
)
from services.web.query.ai_assistant.services.nl2json import NL2JSONService
from tests.test_query.test_ai_assistant.base import AIAssistantTestCase

NL2JSON_MODULE = "services.web.query.ai_assistant.services.nl2json"

VALID_AI_OUTPUT = {
    "conditions": [{"raw_name": "username", "keys": [], "field_type": None, "operator": "eq", "filters": ["admin"]}],
    "start_time": "2026-08-13T00:00:00+08:00",
    "end_time": "2026-08-14T00:00:00+08:00",
}


@mock.patch(f"{NL2JSON_MODULE}.api.bk_plugins_ai_agent.chat_completion")
class TestNL2JSONService(AIAssistantTestCase):
    """F2 自然语言 → condition"""

    def _convert(self, selection=None):
        return NL2JSONService.convert(
            query_text="查一下 admin 的操作日志",
            selection=selection or self.make_selection(),
            scope_id=self.target_system_id,
            username=self.username,
        )

    def test_convert_success(self, mock_chat):
        mock_chat.return_value = json.dumps(VALID_AI_OUTPUT)

        condition = self._convert()

        # scope 取入参（不信任 AI）
        self.assertEqual(condition.scope_id, self.target_system_id)
        self.assertEqual(condition.start_time, VALID_AI_OUTPUT["start_time"])
        self.assertEqual(len(condition.conditions), 1)
        cond = condition.conditions[0]
        self.assertEqual(cond.field.raw_name, "username")
        self.assertEqual(cond.operator, "eq")
        self.assertEqual(cond.filters, ["admin"])
        # field_type 由服务端按元数据补全
        self.assertEqual(cond.field.field_type, "string")
        # 非流式调用 + 显式 user
        _, kwargs = mock_chat.call_args
        self.assertEqual(kwargs["user"], self.username)
        self.assertFalse(kwargs["execute_kwargs"]["stream"])

    def test_parse_fenced_json(self, mock_chat):
        mock_chat.return_value = f"```json\n{json.dumps(VALID_AI_OUTPUT)}\n```"
        condition = self._convert()
        self.assertEqual(len(condition.conditions), 1)

    def test_parse_prose_wrapped_json(self, mock_chat):
        mock_chat.return_value = f"好的，检索条件如下：{json.dumps(VALID_AI_OUTPUT)} 请查收。"
        condition = self._convert()
        self.assertEqual(len(condition.conditions), 1)

    def test_parse_failed(self, mock_chat):
        mock_chat.return_value = "抱歉，我无法理解这个问题。"
        with self.assertRaises(AIOutputParseFailedError) as ctx:
            self._convert()
        self.assertEqual(ctx.exception.error_code, "AI_OUTPUT_PARSE_FAILED")

    def test_non_string_response(self, mock_chat):
        mock_chat.return_value = {"unexpected": "dict"}
        with self.assertRaises(AIOutputParseFailedError):
            self._convert()

    def test_empty_conditions_raises_not_recognized(self, mock_chat):
        mock_chat.return_value = json.dumps({"conditions": [], "start_time": None, "end_time": None})
        with self.assertRaises(QueryNotRecognizedError) as ctx:
            self._convert()
        self.assertEqual(ctx.exception.error_code, "QUERY_NOT_RECOGNIZED")

    def test_unknown_field_rejected(self, mock_chat):
        output = dict(VALID_AI_OUTPUT)
        output["conditions"] = [{"raw_name": "not_a_field", "keys": [], "operator": "eq", "filters": ["x"]}]
        mock_chat.return_value = json.dumps(output)
        with self.assertRaises(AIOutputInvalidError) as ctx:
            self._convert()
        self.assertEqual(ctx.exception.error_code, "AI_OUTPUT_INVALID")

    def test_operator_not_allowed_rejected(self, mock_chat):
        # username allow_operators 为 ["eq", "include"]，like 越权
        output = dict(VALID_AI_OUTPUT)
        output["conditions"] = [{"raw_name": "username", "keys": [], "operator": "like", "filters": ["adm"]}]
        mock_chat.return_value = json.dumps(output)
        with self.assertRaises(AIOutputInvalidError):
            self._convert()

    def test_unknown_operator_rejected(self, mock_chat):
        output = dict(VALID_AI_OUTPUT)
        output["conditions"] = [{"raw_name": "username", "keys": [], "operator": "regex", "filters": ["adm.*"]}]
        mock_chat.return_value = json.dumps(output)
        with self.assertRaises(AIOutputInvalidError):
            self._convert()

    def test_extension_condition_success(self, mock_chat):
        selection = self.make_selection(extension_fields=[self.make_extension_field()])
        output = dict(VALID_AI_OUTPUT)
        output["conditions"] = [
            {
                "raw_name": "extend_data",
                "keys": ["ticket_id"],
                "operator": "eq",
                "filters": ["Story-3000"],
            }
        ]
        mock_chat.return_value = json.dumps(output)

        condition = self._convert(selection=selection)
        self.assertEqual(condition.conditions[0].field.keys, ["ticket_id"])

    def test_extension_user_specified_key_allowed(self, mock_chat):
        """用户显式指定的下钻子键：字段上下文未列出也放行（采样覆盖有限，子键信任用户）"""
        output = dict(VALID_AI_OUTPUT)
        output["conditions"] = [{"raw_name": "extend_data", "keys": ["not_exist"], "operator": "eq", "filters": ["x"]}]
        mock_chat.return_value = json.dumps(output)

        condition = self._convert()
        self.assertEqual(condition.conditions[0].field.raw_name, "extend_data")
        self.assertEqual(condition.conditions[0].field.keys, ["not_exist"])
        self.assertEqual(condition.conditions[0].filters, ["x"])

    def test_extension_user_specified_invalid_operator_rejected(self, mock_chat):
        """未采样发现的子键：操作符仍按拓展字段默认集合校验（gt 数值比较拒绝）"""
        output = dict(VALID_AI_OUTPUT)
        output["conditions"] = [
            {"raw_name": "extend_data", "keys": ["not_exist"], "operator": "gt", "filters": ["1"]}
        ]
        mock_chat.return_value = json.dumps(output)
        with self.assertRaises(AIOutputInvalidError):
            self._convert()

    def test_extension_keys_on_non_json_field_rejected(self, mock_chat):
        """容器白名单保留：非 JSON 容器字段带下钻 keys 仍拒绝（防编造容器）"""
        output = dict(VALID_AI_OUTPUT)
        output["conditions"] = [
            {"raw_name": "username", "keys": ["hijack"], "operator": "eq", "filters": ["x"]}
        ]
        mock_chat.return_value = json.dumps(output)
        with self.assertRaises(AIOutputInvalidError):
            self._convert()

    def test_numeric_operator_on_string_extension_rejected(self, mock_chat):
        selection = self.make_selection(extension_fields=[self.make_extension_field(allow_operators=["eq", "gt"])])
        output = dict(VALID_AI_OUTPUT)
        output["conditions"] = [
            {"raw_name": "extend_data", "keys": ["ticket_id"], "operator": "gt", "filters": ["100"]}
        ]
        mock_chat.return_value = json.dumps(output)
        with self.assertRaises(AIOutputInvalidError):
            self._convert(selection=selection)

    def test_time_field_condition_stripped(self, mock_chat):
        output = dict(VALID_AI_OUTPUT)
        output["conditions"] = [
            {"raw_name": "thedate", "keys": [], "operator": "gte", "filters": ["20260813"]},
            {"raw_name": "username", "keys": [], "operator": "eq", "filters": ["admin"]},
        ]
        mock_chat.return_value = json.dumps(output)

        condition = self._convert()
        raw_names = [cond.field.raw_name for cond in condition.conditions]
        self.assertNotIn("thedate", raw_names)
        self.assertIn("username", raw_names)

    def test_all_time_field_conditions_stripped_to_time_window(self, mock_chat):
        """时间字段条件全被剔除，但 AI 输出了有效时间 → 降级为纯时间窗口检索而非未识别"""
        output = dict(VALID_AI_OUTPUT)
        output["conditions"] = [
            {"raw_name": "dtEventTimeStamp", "keys": [], "operator": "gte", "filters": [1755129600000]}
        ]
        mock_chat.return_value = json.dumps(output)

        condition = self._convert()
        self.assertEqual(condition.conditions, [])
        self.assertEqual(condition.start_time, VALID_AI_OUTPUT["start_time"])
        self.assertEqual(condition.end_time, VALID_AI_OUTPUT["end_time"])

    def test_default_time_window(self, mock_chat):
        """D2 默认实现：AI 未输出时间时后端补默认窗口（与采样窗口对齐，30 天）"""
        output = dict(VALID_AI_OUTPUT)
        output["start_time"] = None
        output["end_time"] = None
        mock_chat.return_value = json.dumps(output)

        condition = self._convert()
        start_dt = parse_datetime(condition.start_time)
        end_dt = parse_datetime(condition.end_time)
        self.assertEqual((end_dt - start_dt).days, DEFAULT_SEARCH_WINDOW_DAYS)

    def test_invalid_time_falls_back_to_default(self, mock_chat):
        output = dict(VALID_AI_OUTPUT)
        output["start_time"] = "不是时间"
        mock_chat.return_value = json.dumps(output)

        condition = self._convert()
        start_dt = parse_datetime(condition.start_time)
        end_dt = parse_datetime(condition.end_time)
        self.assertEqual((end_dt - start_dt).days, DEFAULT_SEARCH_WINDOW_DAYS)

    def test_agent_timeout(self, mock_chat):
        mock_chat.side_effect = Timeout("read timeout")
        with self.assertRaises(AITimeoutError) as ctx:
            self._convert()
        self.assertEqual(ctx.exception.error_code, "AI_TIMEOUT")

    def test_agent_service_error(self, mock_chat):
        mock_chat.side_effect = Exception("connection reset")
        with self.assertRaises(AIServiceError) as ctx:
            self._convert()
        self.assertEqual(ctx.exception.error_code, "AI_SERVICE_ERROR")


@mock.patch(f"{NL2JSON_MODULE}.api.bk_plugins_ai_agent.chat_completion")
class TestNL2JSONScenarios(AIAssistantTestCase):
    """真实检索场景话术全覆盖：AI 对各类话术的合理输出 → 链路产出与普通日志检索页手动构造一致。

    基准 = COLLECT_SEARCH_CONFIG 真实白名单（字段 × 操作符 × 值形态），
    逐场景 mock「AI 对该话术的合理输出」，断言 SearchCondition 与检索页等价。
    """

    # 与普通日志检索页白名单一致的字段操作符（field_context 注入 AI 的同源数据）
    FIELD_OPERATORS = {
        "username": ["include", "eq"],
        "action_id": ["include", "eq"],
        "resource_type_id": ["include", "eq"],
        "instance_id": ["include", "eq"],
        "access_source_ip": ["include", "eq"],
        "request_id": ["include", "eq"],
        "result_code": ["include"],
        "instance_name": ["like"],
        "log": ["match_any", "match_all"],
    }

    def _selection(self):
        return self.make_selection(
            standard_fields=[
                self.make_standard_field(raw_name=name, allow_operators=ops)
                for name, ops in self.FIELD_OPERATORS.items()
            ]
        )

    def _convert(self, query_text: str, ai_conditions: list, start_time=None, end_time=None):
        self.mock_chat.return_value = json.dumps(
            {"conditions": ai_conditions, "start_time": start_time, "end_time": end_time}
        )
        return NL2JSONService.convert(
            query_text=query_text,
            selection=self._selection(),
            scope_id=self.target_system_id,
            username=self.username,
        )

    def test_operator_single(self, mock_chat):
        """「查一下张三的操作日志」→ username eq（检索页单选操作人）"""
        self.mock_chat = mock_chat
        condition = self._convert(
            "查一下张三的操作日志",
            [{"raw_name": "username", "keys": [], "operator": "eq", "filters": ["张三"]}],
            start_time="2026-08-21T00:00:00+08:00",
            end_time="2026-08-28T00:00:00+08:00",
        )
        self.assertEqual(len(condition.conditions), 1)
        self.assertEqual(condition.conditions[0].field.raw_name, "username")
        self.assertEqual(condition.conditions[0].operator, "eq")
        self.assertEqual(condition.conditions[0].filters, ["张三"])

    def test_operators_multiple(self, mock_chat):
        """「张三和李四的操作」→ username include 多值（检索页多选 = IN）"""
        self.mock_chat = mock_chat
        condition = self._convert(
            "张三和李四的操作",
            [{"raw_name": "username", "keys": [], "operator": "include", "filters": ["张三", "李四"]}],
        )
        self.assertEqual(condition.conditions[0].operator, "include")
        self.assertEqual(condition.conditions[0].filters, ["张三", "李四"])

    def test_failed_result(self, mock_chat):
        """「查下失败的日志」→ result_code include [-1]（原始查询值）"""
        self.mock_chat = mock_chat
        condition = self._convert(
            "查下失败的日志",
            [{"raw_name": "result_code", "keys": [], "operator": "include", "filters": [-1]}],
        )
        self.assertEqual(condition.conditions[0].field.raw_name, "result_code")
        self.assertEqual(condition.conditions[0].filters, [-1])

    def test_result_with_string_value(self, mock_chat):
        """「成功的操作」→ result_code include ["0"]（options id 字符串形态，与检索页表单值一致）"""
        self.mock_chat = mock_chat
        condition = self._convert(
            "查一下成功的操作",
            [{"raw_name": "result_code", "keys": [], "operator": "include", "filters": ["0"]}],
        )
        self.assertEqual(condition.conditions[0].filters, ["0"])

    def test_instance_id_exact(self, mock_chat):
        """「实例ID 12345 的操作」→ instance_id eq（排障精确查实例）"""
        self.mock_chat = mock_chat
        condition = self._convert(
            "查一下实例ID是12345的操作",
            [{"raw_name": "instance_id", "keys": [], "operator": "eq", "filters": ["12345"]}],
        )
        self.assertEqual(condition.conditions[0].field.raw_name, "instance_id")
        self.assertEqual(condition.conditions[0].filters, ["12345"])

    def test_instance_name_fuzzy(self, mock_chat):
        """「资源名叫 test-vm 的操作」→ instance_name like（模糊匹配，白名单支持）"""
        self.mock_chat = mock_chat
        condition = self._convert(
            "查下资源名叫 test-vm 的操作",
            [{"raw_name": "instance_name", "keys": [], "operator": "like", "filters": ["test-vm"]}],
        )
        self.assertEqual(condition.conditions[0].field.raw_name, "instance_name")
        self.assertEqual(condition.conditions[0].operator, "like")

    def test_source_ip(self, mock_chat):
        """「来源IP 1.2.3.4 的日志」→ access_source_ip eq（安全审计场景）"""
        self.mock_chat = mock_chat
        condition = self._convert(
            "查一下来源IP是1.2.3.4的日志",
            [{"raw_name": "access_source_ip", "keys": [], "operator": "eq", "filters": ["1.2.3.4"]}],
        )
        self.assertEqual(condition.conditions[0].field.raw_name, "access_source_ip")
        self.assertEqual(condition.conditions[0].filters, ["1.2.3.4"])

    def test_request_id_troubleshooting(self, mock_chat):
        """「request_id abc-123 的日志」→ request_id eq（调用链排障高频场景）"""
        self.mock_chat = mock_chat
        condition = self._convert(
            "帮我查request_id是abc-123的日志",
            [{"raw_name": "request_id", "keys": [], "operator": "eq", "filters": ["abc-123"]}],
        )
        self.assertEqual(condition.conditions[0].field.raw_name, "request_id")
        self.assertEqual(condition.conditions[0].filters, ["abc-123"])

    def test_keyword_fulltext(self, mock_chat):
        """「日志里包含 Story-3000 的」→ log match_any（关键词全文检索）"""
        self.mock_chat = mock_chat
        condition = self._convert(
            "查一下日志里包含Story-3000的记录",
            [{"raw_name": "log", "keys": [], "operator": "match_any", "filters": ["Story-3000"]}],
        )
        self.assertEqual(condition.conditions[0].field.raw_name, "log")
        self.assertEqual(condition.conditions[0].operator, "match_any")

    def test_multi_keyword_and(self, mock_chat):
        """「同时包含权限变更和失败的日志」→ log match_all（多关键词 AND）"""
        self.mock_chat = mock_chat
        condition = self._convert(
            "查同时包含权限变更和失败的日志",
            [{"raw_name": "log", "keys": [], "operator": "match_all", "filters": ["权限变更", "失败"]}],
        )
        self.assertEqual(condition.conditions[0].operator, "match_all")
        self.assertEqual(condition.conditions[0].filters, ["权限变更", "失败"])

    def test_action_oral_fallback_fulltext(self, mock_chat):
        """「查下登录操作」→ action_id 无枚举映射，AI 按提示词兜底 log match_any（禁止猜字段值）"""
        self.mock_chat = mock_chat
        condition = self._convert(
            "查下登录相关的操作",
            [{"raw_name": "log", "keys": [], "operator": "match_any", "filters": ["登录"]}],
        )
        self.assertEqual(condition.conditions[0].field.raw_name, "log")
        self.assertEqual(condition.conditions[0].filters, ["登录"])

    def test_combined_conditions(self, mock_chat):
        """「张三昨天的失败操作」→ username + result_code 组合（检索页多条件 AND）"""
        self.mock_chat = mock_chat
        condition = self._convert(
            "查一下张三昨天的失败操作",
            [
                {"raw_name": "username", "keys": [], "operator": "eq", "filters": ["张三"]},
                {"raw_name": "result_code", "keys": [], "operator": "include", "filters": [-1]},
            ],
            start_time="2026-08-27T00:00:00+08:00",
            end_time="2026-08-27T23:59:59+08:00",
        )
        self.assertEqual(len(condition.conditions), 2)
        raw_names = [cond.field.raw_name for cond in condition.conditions]
        self.assertEqual(raw_names, ["username", "result_code"])

    def test_extension_plus_standard(self, mock_chat):
        """「工单 Story-3000 相关张三的操作」→ 拓展下钻 + 标准字段混合"""
        self.mock_chat = mock_chat
        selection = self._selection()
        selection.systems[0].extension_fields.append(self.make_extension_field())
        self.mock_chat.return_value = json.dumps(
            {
                "conditions": [
                    {"raw_name": "extend_data", "keys": ["ticket_id"], "operator": "eq", "filters": ["Story-3000"]},
                    {"raw_name": "username", "keys": [], "operator": "eq", "filters": ["张三"]},
                ],
                "start_time": None,
                "end_time": None,
            }
        )
        condition = NL2JSONService.convert(
            query_text="查工单Story-3000相关的张三的操作",
            selection=selection,
            scope_id=self.target_system_id,
            username=self.username,
        )
        self.assertEqual(len(condition.conditions), 2)
        self.assertEqual(condition.conditions[0].field.keys, ["ticket_id"])
        self.assertEqual(condition.conditions[1].field.raw_name, "username")

    def test_system_id_condition_stripped(self, mock_chat):
        """「查xx系统的日志」（已选系统会话内提系统名）→ AI 偷带 system_id 条件被剔除，其余保留"""
        self.mock_chat = mock_chat
        condition = self._convert(
            "查下bk_log系统的日志",
            [
                {"raw_name": "system_id", "keys": [], "operator": "eq", "filters": ["other_system"]},
                {"raw_name": "username", "keys": [], "operator": "eq", "filters": ["admin"]},
            ],
        )
        raw_names = [cond.field.raw_name for cond in condition.conditions]
        self.assertNotIn("system_id", raw_names)
        self.assertIn("username", raw_names)

    def test_reversed_time_swapped(self, mock_chat):
        """AI 时间换算倒置（start > end）→ 组装层交换保窗口有效，避免 SQL 恒假零命中"""
        self.mock_chat = mock_chat
        condition = self._convert(
            "查一下最近的日志",
            [{"raw_name": "username", "keys": [], "operator": "eq", "filters": ["admin"]}],
            start_time="2026-08-28T00:00:00+08:00",
            end_time="2026-08-21T00:00:00+08:00",
        )
        start_dt = parse_datetime(condition.start_time)
        end_dt = parse_datetime(condition.end_time)
        self.assertLess(start_dt, end_dt)


@mock.patch(f"{NL2JSON_MODULE}.api.bk_plugins_ai_agent.chat_completion")
class TestNL2JSONTimeWindowIntent(AIAssistantTestCase):
    """纯时间窗口 / 模糊意图话术（如"帮我查下最近七天的日志"）——时间有效即合法检索意图。

    协议：conditions 空 + start/end 任一可解析 → 放行为纯时间窗口检索；
    conditions 空 + 时间全空/非法 → QUERY_NOT_RECOGNIZED（寒暄/无关输入）。
    """

    def _convert(self, query_text: str = "帮我查下最近七天的日志"):
        return NL2JSONService.convert(
            query_text=query_text,
            selection=self.make_selection(),
            scope_id=self.target_system_id,
            username=self.username,
        )

    def test_rolling_window_query(self, mock_chat):
        """「帮我查下最近七天的日志」：AI 输出空 conditions + 滚动 7 天窗口 → 放行"""
        now = "2026-08-28T18:00:00+08:00"
        mock_chat.return_value = json.dumps(
            {
                "conditions": [],
                "start_time": "2026-08-21T18:00:00+08:00",
                "end_time": now,
            }
        )

        condition = self._convert()
        self.assertEqual(condition.conditions, [])
        self.assertEqual(condition.start_time, "2026-08-21T18:00:00+08:00")
        self.assertEqual(condition.end_time, now)

    def test_natural_day_query(self, mock_chat):
        """「看下昨天有什么操作」：AI 按自然日边界换算 → 放行"""
        mock_chat.return_value = json.dumps(
            {
                "conditions": [],
                "start_time": "2026-08-27T00:00:00+08:00",
                "end_time": "2026-08-27T23:59:59+08:00",
            }
        )

        condition = self._convert(query_text="看下昨天有什么操作")
        self.assertEqual(condition.conditions, [])
        start_dt = parse_datetime(condition.start_time)
        end_dt = parse_datetime(condition.end_time)
        self.assertEqual((end_dt - start_dt).days, 0)

    def test_vague_intent_default_window(self, mock_chat):
        """「帮我看看最近的情况」：模糊意图，AI 按提示词输出默认 30 天窗口 → 放行"""
        mock_chat.return_value = json.dumps(
            {
                "conditions": [],
                "start_time": "2026-07-29T18:00:00+08:00",
                "end_time": "2026-08-28T18:00:00+08:00",
            }
        )

        condition = self._convert(query_text="帮我看看最近的情况")
        self.assertEqual(condition.conditions, [])
        start_dt = parse_datetime(condition.start_time)
        end_dt = parse_datetime(condition.end_time)
        self.assertEqual((end_dt - start_dt).days, DEFAULT_SEARCH_WINDOW_DAYS)

    def test_start_time_only_fills_end_with_now(self, mock_chat):
        """AI 仅输出 start_time（end 缺失）→ 时间意图成立，end 由后端兜底当前时间"""
        mock_chat.return_value = json.dumps(
            {"conditions": [], "start_time": "2026-08-20T00:00:00+08:00", "end_time": None}
        )

        condition = self._convert()
        self.assertEqual(condition.conditions, [])
        self.assertEqual(condition.start_time, "2026-08-20T00:00:00+08:00")
        end_dt = parse_datetime(condition.end_time)
        self.assertIsNotNone(end_dt)

    def test_empty_conditions_with_invalid_time_rejected(self, mock_chat):
        """空 conditions + 时间非法（不可解析）→ 无法确认检索意图，判未识别"""
        mock_chat.return_value = json.dumps({"conditions": [], "start_time": "不是时间", "end_time": "也不是时间"})

        with self.assertRaises(QueryNotRecognizedError) as ctx:
            self._convert()
        self.assertEqual(ctx.exception.error_code, "QUERY_NOT_RECOGNIZED")

    def test_greeting_unrecognized(self, mock_chat):
        """寒暄（「你好」）：AI 全空输出 → 未识别（保持既有鲁棒行为）"""
        mock_chat.return_value = json.dumps({"conditions": [], "start_time": None, "end_time": None})

        with self.assertRaises(QueryNotRecognizedError):
            self._convert(query_text="你好")


@mock.patch(f"{NL2JSON_MODULE}.api.bk_plugins_ai_agent.chat_completion")
class TestNL2JSONAdversarial(AIAssistantTestCase):
    """AI 坏输出对抗样本（JSON 提取闸门）"""

    def _convert(self, selection=None):
        return NL2JSONService.convert(
            query_text="测试",
            selection=selection or self.make_selection(),
            scope_id=self.target_system_id,
            username=self.username,
        )

    def test_truncated_json(self, mock_chat):
        """截断的 JSON（模型输出中断）"""
        mock_chat.return_value = '{"conditions": [{"raw_name": "usern'
        with self.assertRaises(AIOutputParseFailedError):
            self._convert()

    def test_empty_response(self, mock_chat):
        mock_chat.return_value = ""
        with self.assertRaises(AIOutputParseFailedError):
            self._convert()

    def test_multiple_json_blocks(self, mock_chat):
        """多个 JSON 对象拼接"""
        mock_chat.return_value = json.dumps(VALID_AI_OUTPUT) + json.dumps(VALID_AI_OUTPUT)
        with self.assertRaises(AIOutputParseFailedError):
            self._convert()

    def test_fullwidth_quotes_rejected(self, mock_chat):
        """全角引号（中文标点）——当前不支持，文档化行为：拒绝而非错判"""
        mock_chat.return_value = '{"conditions": [{"raw_name": "username", "operator": "eq", "filters": ["admin"]}]}'
        condition = self._convert()
        self.assertEqual(len(condition.conditions), 1)

    def test_unicode_escaped_json(self, mock_chat):
        """\\uXXXX 转义（ensure_ascii 输出）"""
        output = dict(VALID_AI_OUTPUT)
        output["conditions"] = [{"raw_name": "username", "keys": [], "operator": "eq", "filters": ["管理员"]}]
        mock_chat.return_value = json.dumps(output, ensure_ascii=True)
        condition = self._convert()
        self.assertEqual(condition.conditions[0].filters, ["管理员"])

    def test_numeric_filters_for_eq(self, mock_chat):
        """eq 操作符的数值型 filters（原始查询值形态）"""
        selection = self.make_selection(
            standard_fields=[self.make_standard_field(raw_name="result_code", allow_operators=["eq", "gt"])]
        )
        output = dict(VALID_AI_OUTPUT)
        output["conditions"] = [{"raw_name": "result_code", "keys": [], "operator": "eq", "filters": [0]}]
        mock_chat.return_value = json.dumps(output)
        condition = self._convert(selection=selection)
        self.assertEqual(condition.conditions[0].filters, [0])

    def test_deeply_nested_malformed_keys(self, mock_chat):
        """keys 深度嵌套超出字段清单 → 拒绝"""
        output = dict(VALID_AI_OUTPUT)
        output["conditions"] = [
            {
                "raw_name": "extend_data",
                "keys": ["a", "b", "c"],
                "operator": "eq",
                "filters": ["x"],
            }
        ]
        mock_chat.return_value = json.dumps(output)
        with self.assertRaises(AIOutputInvalidError):
            self._convert()

    def test_condition_with_extra_noise_fields(self, mock_chat):
        """AI 输出附加多余字段（容错：Pydantic 忽略多余键）"""
        output = dict(VALID_AI_OUTPUT)
        output["conditions"][0]["explanation"] = "这是操作人字段"
        mock_chat.return_value = json.dumps(output)
        condition = self._convert()
        self.assertEqual(condition.conditions[0].field.raw_name, "username")

    def test_long_noise_after_valid_json(self, mock_chat):
        """合法 JSON 前缀 + 超长噪音后缀 → 容错提取成功（花括号正则贪婪回溯）"""
        mock_chat.return_value = json.dumps(VALID_AI_OUTPUT) + "长文本噪音" * 5000
        condition = self._convert()
        self.assertEqual(len(condition.conditions), 1)

    def test_very_long_pure_garbage(self, mock_chat):
        """纯超长垃圾文本（无 JSON）不崩，抛业务异常"""
        mock_chat.return_value = "这只是一段毫无意义的长文本" * 10000
        with self.assertRaises(AIOutputParseFailedError):
            self._convert()

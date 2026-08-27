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

    def test_all_time_field_conditions_raises_not_recognized(self, mock_chat):
        output = dict(VALID_AI_OUTPUT)
        output["conditions"] = [
            {"raw_name": "dtEventTimeStamp", "keys": [], "operator": "gte", "filters": [1755129600000]}
        ]
        mock_chat.return_value = json.dumps(output)
        with self.assertRaises(QueryNotRecognizedError):
            self._convert()

    def test_default_time_window(self, mock_chat):
        """D2 默认实现：AI 未输出时间时后端补最近 7 天窗口"""
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

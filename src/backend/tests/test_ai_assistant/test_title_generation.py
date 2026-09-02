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

# 会话标题自动生成（一期复刻 risk 调用方式）：input 拼接 + 共用智能体调用 + 清洗 + Celery 任务 + NL/条件检索触发链路。

from unittest import mock

from api.constants import AIAgentCode
from services.web.ai_assistant.constants import ExecutionStatus, MessageType
from services.web.ai_assistant.models import Conversation
from services.web.ai_assistant.schemas import parse_snapshot
from services.web.ai_assistant.services.message import MessageService
from services.web.ai_assistant.services.message_execution import MessageExecution
from services.web.ai_assistant.services.title_agent import (
    TitleAgentService,
    build_condition_title_input,
)
from services.web.ai_assistant.tasks.audit_search import execute_natural_language_search
from services.web.ai_assistant.tasks.conversation import generate_conversation_title
from tests.test_ai_assistant.base import (
    TARGET_SYSTEM_ID,
    AIAssistantPlatformTestCase,
    make_condition,
    make_log_search_output,
)

TITLE_AGENT_MODULE = "services.web.ai_assistant.services.title_agent"


class TitleAgentServiceTest(AIAssistantPlatformTestCase):
    """User Prompt 拼接（与 risk 同构的单行 label 格式）+ 共用智能体调用 + 清洗"""

    def test_generate_title_calls_shared_agent(self):
        """复刻 risk 调用：同一智能体 ALS_TITLE_SUM，input 为单行 label 前缀格式"""

        with mock.patch(f"{TITLE_AGENT_MODULE}.api.bk_plugins_ai_agent.chat_completion") as mock_chat:
            mock_chat.return_value = '```"张三王五登录失败记录"```'
            title = TitleAgentService.generate_title(
                input_text="查一下张三和王五最近三天的登录失败记录",
                username=self.user,
                max_length=20,
            )

        self.assertEqual(title, "张三王五登录失败记录")
        mock_chat.assert_called_once_with(
            agent_code=AIAgentCode.ALS_TITLE_SUM,
            user=self.user,
            input='用户自然语言检索描述: "查一下张三和王五最近三天的登录失败记录"',
            chat_history=[],
            execute_kwargs={"stream": False},
        )

    def test_normalize_title_cleans_and_truncates(self):
        """清洗：去代码块/引号/空白折叠/截断（与 risk 标题清洗规则一致）"""

        raw = '```json\n"张三 和五   的登录 失败记录查询啊测试超长标题"\n```'
        title = TitleAgentService.normalize_title(raw, 20)

        # 空白折叠后按 20 字符截断（空格计入长度）
        self.assertEqual(title, "张三 和五 的登录 失败记录查询啊测试超")
        # 空输入/非字符串返回空串（调用方按跳过处理，防异常对象污染标题）
        self.assertEqual(TitleAgentService.normalize_title(None, 20), "")
        self.assertEqual(TitleAgentService.normalize_title('```""```', 20), "")
        self.assertEqual(TitleAgentService.normalize_title(object(), 20), "")

    def test_generate_title_condition_source_uses_condition_template(self):
        """条件检索来源：label 换为「用户条件检索描述」，仍为单行 label 前缀格式"""

        with mock.patch(f"{TITLE_AGENT_MODULE}.api.bk_plugins_ai_agent.chat_completion") as mock_chat:
            mock_chat.return_value = "admin登录操作记录"
            title = TitleAgentService.generate_title(
                input_text="系统 bk-audit，操作人 等于 admin",
                username=self.user,
                max_length=20,
                source="field_condition",
            )

        self.assertEqual(title, "admin登录操作记录")
        mock_chat.assert_called_once_with(
            agent_code=AIAgentCode.ALS_TITLE_SUM,
            user=self.user,
            input='用户条件检索描述: "系统 bk-audit，操作人 等于 admin"',
            chat_history=[],
            execute_kwargs={"stream": False},
        )

    def test_build_condition_title_input_full_summary(self):
        """条件快照 → 单行中文摘要：系统 + 时间 + 逐条件「字段 操作符 值」；
        字段中文名动态取自字段元数据（与条件筛选回传前端同源）；未知字段/操作符回退原文"""

        summary = build_condition_title_input(
            {
                "condition": {
                    "scope_type": "system",
                    "scope_id": "bk-audit",
                    "start_time": "2026-09-01T00:00:00+08:00",
                    "end_time": "2026-09-01T23:59:59+08:00",
                    "conditions": [
                        {
                            "field": {"raw_name": "username", "keys": [], "field_type": "string"},
                            "operator": "eq",
                            "filters": ["admin"],
                        },
                        {
                            "field": {"raw_name": "action_id", "keys": [], "field_type": "string"},
                            "operator": "include",
                            "filters": ["login", "logout"],
                        },
                        {
                            "field": {"raw_name": "log", "keys": [], "field_type": "string"},
                            "operator": "match_any",
                            "filters": ["登录"],
                        },
                        {
                            "field": {"raw_name": "instance_origin_data", "keys": [], "field_type": "string"},
                            "operator": "include",
                            "filters": ["v1"],
                        },
                        {
                            "field": {"raw_name": "snapshot_resource_type_info", "keys": [], "field_type": "string"},
                            "operator": "eq",
                            "filters": ["host"],
                        },
                        {
                            "field": {"raw_name": "custom_field", "keys": [], "field_type": "string"},
                            "operator": "weird_op",
                            "filters": ["v1"],
                        },
                        # 空 filters / 缺 raw_name：跳过不产生片段
                        {"field": {"raw_name": "log"}, "operator": "match_any", "filters": []},
                        {"field": {"raw_name": ""}, "operator": "eq", "filters": ["x"]},
                    ],
                }
            }
        )

        # 标准字段（username=操作人用户名）、系统字段（log=原始数据内容）、
        # 对象字段（instance_origin_data=实例变更前内容）、快照字段（snapshot_resource_type_info=资源类型快照）
        # 均动态取 Field.description；未知字段/操作符回退原文；时间为日期级（同日单值）
        self.assertEqual(
            summary,
            "系统 bk-audit，时间 2026-09-01，"
            "操作人用户名 等于 admin，操作ID 包含 login,logout，"
            "原始数据内容 任一包含 登录，实例变更前内容 包含 v1，"
            "资源类型快照 等于 host，custom_field weird_op v1",
        )

    def test_build_condition_title_input_enum_values_translated(self):
        """枚举字段值翻译为展示值：操作途径 0→WebUI、操作结果 -1→其他、账号类型 1→平台账号；
        非枚举字段值不变；跨日时间为区间表述"""

        summary = build_condition_title_input(
            {
                "condition": {
                    "scope_id": "bk-audit",
                    "start_time": "2026-09-01T00:00:00+08:00",
                    "end_time": "2026-09-02T23:59:59+08:00",
                    "conditions": [
                        {
                            "field": {"raw_name": "access_type", "keys": [], "field_type": "int"},
                            "operator": "include",
                            "filters": [0, 2],  # int 形态（DRF 归一后）
                        },
                        {
                            "field": {"raw_name": "result_code", "keys": [], "field_type": "int"},
                            "operator": "eq",
                            "filters": ["-1"],  # str 形态
                        },
                        {
                            "field": {"raw_name": "user_identify_type", "keys": [], "field_type": "int"},
                            "operator": "eq",
                            "filters": [1],
                        },
                        {
                            "field": {"raw_name": "username", "keys": [], "field_type": "string"},
                            "operator": "eq",
                            "filters": ["admin"],
                        },
                    ],
                }
            }
        )

        self.assertEqual(
            summary,
            "系统 bk-audit，时间 2026-09-01 至 2026-09-02，"
            "操作途径 包含 WebUI,Console，操作结果 等于 其他，"
            "操作人账号类型 等于 平台账号，操作人用户名 等于 admin",
        )

    def test_build_condition_title_input_extension_subkey(self):
        """拓展子键条件：展示名取父消息快照 extension_fields 的 display_name；缺元数据回退子键名"""

        condition_input = {
            "condition": {
                "scope_id": "bk-audit",
                "conditions": [
                    {
                        "field": {"raw_name": "extend_data", "keys": ["ticket_id"], "field_type": "string"},
                        "operator": "eq",
                        "filters": ["TICKET-1"],
                    },
                    {
                        "field": {"raw_name": "extend_data", "keys": ["unknown_sub"], "field_type": "string"},
                        "operator": "like",
                        "filters": ["abc"],
                    },
                ],
            }
        }
        # 提供父消息拓展字段元数据：ticket_id → 工单ID
        summary = build_condition_title_input(
            condition_input,
            extension_fields=[
                {"raw_name": "extend_data", "keys": ["ticket_id"], "display_name": "工单ID"},
                {"raw_name": "instance_data", "keys": ["name"], "display_name": "非拓展容器忽略"},
            ],
        )
        self.assertEqual(summary, "系统 bk-audit，工单ID 等于 TICKET-1，unknown_sub 模糊匹配 abc")

        # 无元数据：子键名回退
        self.assertEqual(
            build_condition_title_input(condition_input),
            "系统 bk-audit，ticket_id 等于 TICKET-1，unknown_sub 模糊匹配 abc",
        )

    def test_build_condition_title_input_empty_and_truncate(self):
        """空条件 → 空串；超长条件截断到上限"""

        self.assertEqual(build_condition_title_input({}), "")
        self.assertEqual(build_condition_title_input({"condition": {}}), "")
        long_summary = build_condition_title_input(
            {
                "condition": {
                    "scope_id": "bk-audit",
                    "start_time": "2026-09-01T00:00:00+08:00",
                    "end_time": "2026-09-01T23:59:59+08:00",
                    "conditions": [
                        {
                            "field": {"raw_name": "log"},
                            "operator": "match_any",
                            "filters": ["超长关键词" * 60],
                        }
                    ],
                }
            }
        )
        self.assertEqual(len(long_summary), 200)

    def test_normalize_title_handles_request_context_payload(self):
        """bk_resource chat_completion 在 bkop 返回 RequestContext：payload 字符串化 tuple，
        含错误响应（error_code）→ 空串；正常响应 → 解析后清洗"""

        # 错误响应（bad request / 权限等）
        class Ctx:
            pass

        bad = Ctx()
        bad.payload = '[{"error_code": 1, "message": "bad request", "data": {}}, {"input": "x"}]'
        self.assertEqual(TitleAgentService.normalize_title(bad, 20), "")

        # 错误响应含 data 字段嵌套
        bad_data = Ctx()
        bad_data.payload = '[{"error_code": 403, "message": "no permission", "data": None}]'
        self.assertEqual(TitleAgentService.normalize_title(bad_data, 20), "")

        # 正常响应（payload 含 content）
        normal = Ctx()
        normal.payload = '[{"content": "```json\\n\\"张三王五登录记录\\"\\n```"}, {"role": "user"}]'
        self.assertEqual(TitleAgentService.normalize_title(normal, 20), "张三王五登录记录")

        # 正常响应（payload 含 message）
        normal_msg = Ctx()
        normal_msg.payload = '[{"message": "30天高危风险分析"}]'
        self.assertEqual(TitleAgentService.normalize_title(normal_msg, 20), "30天高危风险分析")

        # 异常输入（payload 以 [ 开头但语法不可解析）→ 空串，绝不污染标题
        garbage = Ctx()
        garbage.payload = "[garbage syntax without closing"
        self.assertEqual(TitleAgentService.normalize_title(garbage, 20), "")


class GenerateConversationTitleTaskTest(AIAssistantPlatformTestCase):
    """会话标题 Celery 任务：默认标题判断 / 原子写 / 失败静默"""

    def test_task_updates_default_title(self):
        """默认标题"新对话"被 AI 标题替换"""

        with mock.patch.object(TitleAgentService, "generate_title", return_value="张三王五登录失败记录") as mock_generate:
            result = generate_conversation_title.run(self.conversation.id, "查一下张三和王五的登录失败")

        self.assertEqual(result["title"], "张三王五登录失败记录")
        mock_generate.assert_called_once()
        self.conversation.refresh_from_db()
        self.assertEqual(self.conversation.title, "张三王五登录失败记录")

    def test_task_skips_renamed_conversation(self):
        """用户已手动改名 → 不覆盖"""

        Conversation.objects.filter(id=self.conversation.id).update(title="客户事故排查")

        with mock.patch.object(TitleAgentService, "generate_title") as mock_generate:
            result = generate_conversation_title.run(self.conversation.id, "查一下张三的日志")

        self.assertTrue(result["skipped"])
        mock_generate.assert_not_called()
        self.conversation.refresh_from_db()
        self.assertEqual(self.conversation.title, "客户事故排查")

    def test_task_agent_failure_silent(self):
        """智能体异常 → 静默降级保持默认标题（标题非关键路径）"""

        with mock.patch.object(TitleAgentService, "generate_title", side_effect=RuntimeError("agent down")):
            result = generate_conversation_title.run(self.conversation.id, "查一下张三的日志")

        self.assertTrue(result["skipped"])
        self.conversation.refresh_from_db()
        self.assertEqual(self.conversation.title, "新对话")

    def test_task_empty_title_skipped(self):
        """清洗后为空 → 跳过不落库"""

        with mock.patch.object(TitleAgentService, "generate_title", return_value=""):
            result = generate_conversation_title.run(self.conversation.id, "你好")

        self.assertTrue(result["skipped"])
        self.conversation.refresh_from_db()
        self.assertEqual(self.conversation.title, "新对话")

    def test_task_passes_source_to_agent(self):
        """source 透传：条件检索来源任务把 field_condition 传给标题生成服务"""

        with mock.patch.object(TitleAgentService, "generate_title", return_value="admin操作记录") as mock_generate:
            result = generate_conversation_title.run(
                self.conversation.id, "系统 bk-audit，操作人 等于 admin", source="field_condition"
            )

        self.assertEqual(result["title"], "admin操作记录")
        _, kwargs = mock_generate.call_args
        self.assertEqual(kwargs["source"], "field_condition")


class NLTitleDispatchTest(AIAssistantPlatformTestCase):
    """NL 消息成功后触发标题任务派发（不阻塞消息终态）"""

    def _create_processing_nl(self):
        selection = self.create_selection_message()
        nl_message = self.create_nl_message(
            query_text="查一下张三和王五最近三天的登录失败记录",
            auto_execute=False,
            parent=selection,
            status=ExecutionStatus.PROCESSING,
        )
        from services.web.ai_assistant.handlers import message_handler_registry

        nl_handler = message_handler_registry.require(MessageType.NATURAL_LANGUAGE_SEARCH)
        execution = MessageExecution(
            message=nl_message,
            input_data=parse_snapshot(nl_handler.input_model, nl_message.input_data, field_name="input_data"),
            context_data=parse_snapshot(nl_handler.context_model, nl_message.context_data, field_name="context_data"),
        )
        return nl_message, execution

    def test_nl_finish_success_dispatches_title(self):
        """NL 成功收敛后派发标题任务（携带会话 ID 与 query_text）"""

        nl_message, execution = self._create_processing_nl()

        with mock.patch(
            "services.web.ai_assistant.tasks.audit_search.NL2JSONService.convert",
            return_value=make_condition(),
        ), mock.patch("services.web.ai_assistant.tasks.conversation.generate_conversation_title.delay") as mock_delay:
            execute_natural_language_search._finish_success(
                execution=execution,
                task_id="task-1",
                output_data=execute_natural_language_search.run(execution),
            )

        mock_delay.assert_called_once_with(
            conversation_id=self.conversation.id,
            query_text="查一下张三和王五最近三天的登录失败记录",
        )

    def test_dispatch_failure_does_not_break_finish(self):
        """标题任务派发异常不影响消息终态（静默吞掉）"""

        nl_message, execution = self._create_processing_nl()

        with mock.patch(
            "services.web.ai_assistant.tasks.audit_search.NL2JSONService.convert",
            return_value=make_condition(),
        ), mock.patch(
            "services.web.ai_assistant.tasks.conversation.generate_conversation_title.delay",
            side_effect=RuntimeError("broker down"),
        ):
            result = execute_natural_language_search._finish_success(
                execution=execution,
                task_id="task-1",
                output_data=execute_natural_language_search.run(execution),
            )

        # 消息仍正常收敛
        nl_message.refresh_from_db()
        self.assertEqual(nl_message.status, ExecutionStatus.SUCCESS)
        self.assertTrue(result)


class FieldConditionTitleDispatchTest(AIAssistantPlatformTestCase):
    """条件检索消息创建成功后触发标题任务派发（与 NL 链路对齐；不阻塞消息创建）"""

    def test_field_condition_log_search_dispatches_title(self):
        """用户直接发起条件检索（source=field_condition）：派发标题任务，素材=条件中文摘要"""

        self.create_selection_message()
        with mock.patch(
            "services.web.ai_assistant.handlers.audit_search.LogSearchService.search",
            return_value=make_log_search_output(),
        ), mock.patch("services.web.ai_assistant.tasks.conversation.generate_conversation_title.delay") as mock_delay:
            message = MessageService(user=self.user).create(
                conversation=self.conversation,
                message_type=MessageType.LOG_SEARCH,
                input_data={"condition": make_condition().model_dump(mode="json")},
            )

        mock_delay.assert_called_once_with(
            conversation_id=self.conversation.id,
            query_text=build_condition_title_input(
                message.input_data,
                extension_fields=MessageService._extract_parent_extension_fields(message.parent_message),
            ),
            source="field_condition",
        )
        # 素材内容：系统 + 时间 + 条件摘要（字段中文名动态取字段元数据，与条件筛选回传前端同源）
        dispatched_text = mock_delay.call_args.kwargs["query_text"]
        self.assertIn(f"系统 {TARGET_SYSTEM_ID}", dispatched_text)
        self.assertIn("操作人用户名 等于 admin", dispatched_text)

    def test_nl_chained_log_search_not_dispatched(self):
        """NL 续链子消息（source=natural_language）：标题由父 NL 消息链路派发，此处不重复"""

        selection = self.create_selection_message()
        nl_message = self.create_nl_message(query_text="查一下 admin 的日志", parent=selection)
        with mock.patch(
            "services.web.ai_assistant.handlers.audit_search.LogSearchService.search",
            return_value=make_log_search_output(),
        ), mock.patch("services.web.ai_assistant.tasks.conversation.generate_conversation_title.delay") as mock_delay:
            MessageService(user=self.user).create(
                conversation=self.conversation,
                message_type=MessageType.LOG_SEARCH,
                input_data={"condition": make_condition().model_dump(mode="json")},
                parent_message_uid=str(nl_message.uid),
            )

        mock_delay.assert_not_called()

    def test_dispatch_failure_does_not_break_creation(self):
        """标题任务派发异常不影响条件检索消息创建（静默吞掉）"""

        self.create_selection_message()
        with mock.patch(
            "services.web.ai_assistant.handlers.audit_search.LogSearchService.search",
            return_value=make_log_search_output(),
        ), mock.patch(
            "services.web.ai_assistant.tasks.conversation.generate_conversation_title.delay",
            side_effect=RuntimeError("broker down"),
        ):
            message = MessageService(user=self.user).create(
                conversation=self.conversation,
                message_type=MessageType.LOG_SEARCH,
                input_data={"condition": make_condition().model_dump(mode="json")},
            )

        self.assertEqual(message.status, ExecutionStatus.SUCCESS)

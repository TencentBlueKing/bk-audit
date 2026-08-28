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

"""会话标题自动生成（一期复刻 risk 调用方式）：input 拼接 + 共用智能体调用 + 清洗 + Celery 任务 + NL 触发链路。"""

from unittest import mock

from api.constants import AIAgentCode
from services.web.ai_assistant.constants import ExecutionStatus, MessageType
from services.web.ai_assistant.models import Conversation, Message
from services.web.ai_assistant.schemas import parse_snapshot
from services.web.ai_assistant.services.message_execution import MessageExecution
from services.web.ai_assistant.services.title_agent import TitleAgentService
from services.web.ai_assistant.tasks.audit_search import execute_natural_language_search
from services.web.ai_assistant.tasks.conversation import generate_conversation_title
from tests.test_ai_assistant.base import AIAssistantPlatformTestCase, make_condition

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

        with mock.patch.object(
            TitleAgentService, "generate_title", return_value="张三王五登录失败记录"
        ) as mock_generate:
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

        with mock.patch.object(
            TitleAgentService, "generate_title", side_effect=RuntimeError("agent down")
        ):
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
        ), mock.patch(
            "services.web.ai_assistant.tasks.conversation.generate_conversation_title.delay"
        ) as mock_delay:
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

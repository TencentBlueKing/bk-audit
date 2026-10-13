# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
Copyright (C) 2023 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

from enum import StrEnum

# 本模块保留已知事件类型和旧客户端的正文聚合器。回调模式不解释事件顺序、
# RUN 生命周期或最终业务产物；具体业务可按需复用事件枚举实现自己的提取器。


class AGUIEventType(StrEnum):
    """当前接入场景会消费的 AG-UI 事件类型。"""

    RUN_ERROR = "RUN_ERROR"
    TEXT_MESSAGE_START = "TEXT_MESSAGE_START"
    TEXT_MESSAGE_CONTENT = "TEXT_MESSAGE_CONTENT"
    TEXT_MESSAGE_END = "TEXT_MESSAGE_END"


class AGUIFinalMessageParser:
    """旧 ChatCompletion 兼容路径使用的 assistant 文本聚合器。"""

    def __init__(self):
        self._active_messages: dict[str, list[str]] = {}
        self._last_completed_content = ""
        self._has_completed_message = False
        self.error_reason = "未收到完整的 assistant 文本消息"

    def consume(self, event: dict) -> None:
        """消费文本消息事件，只提交已经收到 END 的 assistant 正文。"""

        event_type = event.get("type")
        message_id = event.get("messageId")
        if not isinstance(event_type, str) or not isinstance(message_id, str) or not message_id:
            return
        if event_type == AGUIEventType.TEXT_MESSAGE_START:
            role = event.get("role")
            if isinstance(role, str) and role.lower() == "assistant":
                self._active_messages[message_id] = []
            else:
                self._active_messages.pop(message_id, None)
            return
        if event_type == AGUIEventType.TEXT_MESSAGE_CONTENT:
            if message_id not in self._active_messages:
                return
            delta = event.get("delta", "")
            if isinstance(delta, str):
                self._active_messages[message_id].append(delta)
            return
        if event_type == AGUIEventType.TEXT_MESSAGE_END and message_id in self._active_messages:
            self._last_completed_content = "".join(self._active_messages.pop(message_id))
            self._has_completed_message = True
            self.error_reason = ""

    def get_final_content(self) -> str:
        """返回最后一条完整正文，并通过 error_reason 暴露失败原因。"""

        if not self._has_completed_message:
            self.error_reason = "未收到完整的 assistant 文本消息"
            return ""
        if not self._last_completed_content.strip():
            self.error_reason = "最后一条 assistant 文本消息正文为空"
            return ""
        return self._last_completed_content

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
AI 助手组件异常定义

error_code 与平台错误码对齐（协议 §8）；
error_message 只承载用户可读的脱敏摘要，prompt / 字段上下文 / AI 原始输出
一律放 extra 仅落日志，不进 message。
"""


class AIAssistantError(Exception):
    """AI 助手业务异常基类"""

    error_code = "AI_SERVICE_ERROR"
    error_message = "AI 服务异常，请稍后重试"

    def __init__(self, message: str = None, error_code: str = None, extra: dict = None):
        self.message = message or self.error_message
        if error_code:
            self.error_code = error_code
        self.extra = extra or {}
        super().__init__(self.message)

    def __str__(self):
        return f"[{self.error_code}] {self.message}"


class QueryNotRecognizedError(AIAssistantError):
    """无法从输入中识别出有效的检索条件"""

    error_code = "QUERY_NOT_RECOGNIZED"
    error_message = "未能理解检索需求，请换一种描述或补充关键信息"


class AIOutputParseFailedError(AIAssistantError):
    """AI 返回内容不是合法 JSON 或契约结构"""

    error_code = "AI_OUTPUT_PARSE_FAILED"
    error_message = "AI 返回内容解析失败"


class AIOutputInvalidError(AIAssistantError):
    """AI 返回 JSON 合法但字段/操作符/取值形态非法"""

    error_code = "AI_OUTPUT_INVALID"
    error_message = "AI 生成的检索条件不合法"


class AIServiceError(AIAssistantError):
    """AIDev 调用返回错误（5xx / 网络错误）；error_code 沿用基类默认 AI_SERVICE_ERROR"""

    error_message = "AI 服务调用失败，请稍后重试"


class AITimeoutError(AIAssistantError):
    """AIDev 调用超时"""

    error_code = "AI_TIMEOUT"
    error_message = "AI 服务响应超时，请稍后重试"


class AIPermissionDeniedError(AIAssistantError):
    """无对应系统的日志检索权限"""

    error_code = "PERMISSION_DENIED"
    error_message = "无目标系统的日志检索权限"

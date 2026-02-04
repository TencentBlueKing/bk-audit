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

# 智能体对话请求参数
CHAT_COMPLETION_PARAMS = {
    "user": "admin",  # 会话用户名，通过 X-BKAIDEV-USER 请求头传递
    "input": "你好，请介绍一下自己",
    "chat_history": [
        {"role": "user", "content": "你是谁？"},
        {"role": "assistant", "content": "我是AI审计报告智能助手，可以帮助您进行审计相关的分析和报告。"},
    ],
    "execute_kwargs": {"stream": False},
}

# 智能体对话响应（非流式）
CHAT_COMPLETION_RESPONSE = {
    "result": True,
    "data": {
        "content": "您好！我是AI审计报告智能助手，专门用于协助您进行审计相关的工作。",
    },
    "message": "success",
}

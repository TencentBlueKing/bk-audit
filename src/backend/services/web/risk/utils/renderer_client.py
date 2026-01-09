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
from typing import Any, Dict, List, Optional


class RendererClient:
    """
    渲染器服务客户端

    负责：
    1. 封装渲染器服务调用
    2. 传递风险数据、事件数据、模板配置
    3. 获取渲染结果

    注意：当前为 Mock 实现，待渲染器服务接口文档后替换为真实实现
    """

    def render_full_report(
        self,
        risk_data: Dict[str, Any],
        template_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        渲染完整报告（异步）

        Args:
            risk_data: 风险数据
            template_config: 模板配置（包含 template、ai_variables）

        Returns:
            {"task_id": "xxx", "status": "PENDING"}
        """
        # TODO: 待渲染器接口文档后实现
        task_id = f"mock_render_{uuid.uuid4().hex[:8]}"
        return {"task_id": task_id, "status": "PENDING"}

    def render_preview(
        self,
        risk_data: Dict[str, Any],
        template: str,
        ai_variables: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        报告预览（异步）

        Args:
            risk_data: 风险数据
            template: Jinja2 模板内容
            ai_variables: AI 变量配置列表

        Returns:
            {"task_id": "xxx", "status": "PENDING"}
        """
        # TODO: 待渲染器接口文档后实现
        task_id = f"mock_preview_{uuid.uuid4().hex[:8]}"
        return {"task_id": task_id, "status": "PENDING"}

    def query_result(self, task_id: str) -> Dict[str, Any]:
        """
        查询渲染结果

        Args:
            task_id: 渲染任务 ID

        Returns:
            {"task_id": "xxx", "status": "SUCCESS|PENDING|FAILURE", "content": "...", "error": ""}
        """
        # TODO: 待渲染器接口文档后实现
        # Mock: 返回成功结果
        return {
            "task_id": task_id,
            "status": "SUCCESS",
            "content": f"## Mock 报告内容\n\n这是一个 Mock 生成的报告内容。\n\n任务ID: {task_id}",
            "error": "",
        }


# 单例实例
renderer_client = RendererClient()

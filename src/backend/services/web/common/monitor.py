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

from core.monitor import Event

__all__ = ["LostSceneDetectedEvent", "RiskReportRenderFailedEvent"]


class LostSceneDetectedEvent(Event):
    name = "lost_scene_detected"
    documentation = "丢失场景检测"
    labelnames = ["strategy_id", "control_id", "control_version", "strategy_name"]


class RiskReportRenderFailedEvent(Event):
    """风险报告渲染失败事件"""

    name = "risk_report_render_failed"
    documentation = "风险报告渲染失败"
    labelnames = ["risk_id", "task_id"]

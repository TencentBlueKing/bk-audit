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

"""AI 助手组件测试公共基类与夹具"""

from typing import Any, Dict, List, Optional

from django.conf import settings
from django.test import SimpleTestCase

from services.web.query.ai_assistant.schemas import (
    Condition,
    ConditionField,
    LogSearchOutput,
    QuerySummary,
    ResultColumn,
    SearchCondition,
    SelectionFieldMeta,
    SelectionSystem,
    SystemSelectionOutput,
)


class AIAssistantTestCase(SimpleTestCase):
    """
    AI 助手组件测试基类。

    组件设计为零 DB 依赖（全部外部调用 mock），故用 SimpleTestCase：
    - 本地无 MySQL 凭据时可直接运行；
    - 强制「组件不触 ORM」的设计纪律（任何 DB 泄漏会直接报错）。
    """

    namespace = settings.DEFAULT_NAMESPACE
    username = "tester"
    target_system_id = "bk_log"
    target_system_name = "日志平台"
    start_time = "2026-08-13T00:00:00+08:00"
    end_time = "2026-08-14T00:00:00+08:00"

    def make_standard_field(
        self,
        raw_name: str = "username",
        display_name: str = "",
        allow_operators: Optional[List[str]] = None,
        **kwargs,
    ) -> SelectionFieldMeta:
        return SelectionFieldMeta(
            raw_name=raw_name,
            keys=[],
            display_name=display_name or raw_name,
            nl_name=kwargs.pop("nl_name", "") or display_name or raw_name,
            description=kwargs.pop("description", ""),
            allow_operators=allow_operators if allow_operators is not None else ["eq", "include"],
            **kwargs,
        )

    def make_extension_field(
        self,
        raw_name: str = "extend_data",
        keys: Optional[List[str]] = None,
        display_name: str = "工单内容",
        allow_operators: Optional[List[str]] = None,
        **kwargs,
    ) -> SelectionFieldMeta:
        keys = keys or ["ticket_id"]
        return SelectionFieldMeta(
            raw_name=raw_name,
            keys=keys,
            display_name=display_name,
            nl_name=kwargs.pop("nl_name", "") or f"extend.{display_name}",
            allow_operators=allow_operators if allow_operators is not None else ["eq"],
            system_id=self.target_system_id,
            **kwargs,
        )

    def make_selection(
        self,
        standard_fields: Optional[List[SelectionFieldMeta]] = None,
        extension_fields: Optional[List[SelectionFieldMeta]] = None,
    ) -> SystemSelectionOutput:
        return SystemSelectionOutput(
            systems=[
                SelectionSystem(
                    system_id=self.target_system_id,
                    name=self.target_system_name,
                    standard_fields=standard_fields or [self.make_standard_field()],
                    extension_fields=extension_fields or [],
                )
            ]
        )

    def make_condition(
        self,
        conditions: Optional[List[Condition]] = None,
        scope_id: str = None,
        **kwargs,
    ) -> SearchCondition:
        return SearchCondition(
            scope_type="system",
            scope_id=scope_id or self.target_system_id,
            start_time=kwargs.pop("start_time", self.start_time),
            end_time=kwargs.pop("end_time", self.end_time),
            conditions=conditions or [],
        )

    def make_field_condition(
        self,
        raw_name: str = "username",
        operator: str = "eq",
        filters: Optional[List[Any]] = None,
        keys: Optional[List[str]] = None,
        field_type: Optional[str] = None,
    ) -> Condition:
        return Condition(
            field=ConditionField(raw_name=raw_name, field_type=field_type, keys=keys or []),
            operator=operator,
            filters=filters if filters is not None else ["admin"],
        )

    def make_log_search_output(
        self,
        samples: Optional[List[Dict[str, Any]]] = None,
        columns: Optional[List[ResultColumn]] = None,
        total: int = 0,
    ) -> LogSearchOutput:
        return LogSearchOutput(
            total=total,
            columns=columns
            or [
                ResultColumn(raw_name="start_time", display_name="开始时间"),
                ResultColumn(raw_name="username", display_name="操作人"),
            ],
            samples=samples or [],
            query_summary=QuerySummary(
                scope_type="system",
                scope_id=self.target_system_id,
                time_range={"start_time": self.start_time, "end_time": self.end_time},
                condition_count=0,
                source="field_condition",
                took_ms=10,
                executed_at=self.end_time,
            ),
        )

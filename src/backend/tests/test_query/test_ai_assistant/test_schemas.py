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

协议层模型（schemas）形态校验测试
"""

from pydantic import ValidationError as PydanticValidationError

from services.web.query.ai_assistant.schemas import (
    AIConditionPayload,
    Condition,
    ConditionField,
    ResultColumn,
    SystemSelectionInput,
)
from tests.test_query.test_ai_assistant.base import AIAssistantTestCase


class TestCondition(AIAssistantTestCase):
    """单条检索条件形态校验"""

    def test_eq_with_filters(self):
        cond = Condition(field=ConditionField(raw_name="username"), operator="eq", filters=["admin"])
        self.assertEqual(cond.field.raw_name, "username")
        self.assertEqual(cond.field.keys, [])

    def test_isnull_requires_empty_filters(self):
        with self.assertRaises(PydanticValidationError):
            Condition(field=ConditionField(raw_name="username"), operator="isnull", filters=["x"])

    def test_isnull_empty_filters_ok(self):
        cond = Condition(field=ConditionField(raw_name="username"), operator="isnull", filters=[])
        self.assertEqual(cond.operator, "isnull")

    def test_filters_required(self):
        with self.assertRaises(PydanticValidationError):
            Condition(field=ConditionField(raw_name="username"), operator="eq", filters=[])

    def test_between_requires_two_filters(self):
        with self.assertRaises(PydanticValidationError):
            Condition(field=ConditionField(raw_name="result_code"), operator="between", filters=[1])
        cond = Condition(field=ConditionField(raw_name="result_code"), operator="between", filters=[0, 1])
        self.assertEqual(len(cond.filters), 2)


class TestSearchCondition(AIAssistantTestCase):
    """统一条件结构（NL 输出 = LOG_SEARCH 输入）"""

    def test_iso8601_with_timezone(self):
        condition = self.make_condition()
        self.assertEqual(condition.scope_type, "system")
        self.assertEqual(condition.scope_id, self.target_system_id)

    def test_naive_datetime_format(self):
        condition = self.make_condition(start_time="2026-08-13 00:00:00", end_time="2026-08-14 00:00:00")
        self.assertEqual(condition.start_time, "2026-08-13 00:00:00")

    def test_invalid_time_format(self):
        with self.assertRaises(PydanticValidationError):
            self.make_condition(start_time="2026/08/13")

    def test_model_dump_isomorphic_with_drf(self):
        """model_dump 输出与 QuerySearchConditionSerializer 输入同构（time_shortcut 为前端展示标记，不参与 DRF 校验）"""
        condition = self.make_condition(conditions=[self.make_field_condition(keys=[])])
        dumped = condition.model_dump()
        self.assertEqual(
            set(dumped.keys()),
            {"scope_type", "scope_id", "start_time", "end_time", "conditions", "time_shortcut"},
        )
        self.assertIsNone(dumped["time_shortcut"])
        self.assertEqual(set(dumped["conditions"][0].keys()), {"field", "operator", "filters"})
        self.assertEqual(set(dumped["conditions"][0]["field"].keys()), {"raw_name", "field_type", "keys"})


class TestSystemSelectionInput(AIAssistantTestCase):
    def test_limit_one_system(self):
        with self.assertRaises(PydanticValidationError):
            SystemSelectionInput(system_ids=["a", "b"])
        payload = SystemSelectionInput(system_ids=["a"])
        self.assertEqual(payload.system_ids, ["a"])

    def test_empty_system_ids(self):
        with self.assertRaises(PydanticValidationError):
            SystemSelectionInput(system_ids=[])


class TestAIConditionPayloadTimeShortcut(AIAssistantTestCase):
    """相对时间窗快捷标记形态校验（pattern 约束自动进 model_json_schema 注入 prompt）"""

    def test_valid_hour_and_day_forms(self):
        for value in ("now-1h", "now-24h", "now-1d", "now-7d", "now-30d", "now-365d"):
            payload = AIConditionPayload(conditions=[], time_shortcut=value)
            self.assertEqual(payload.time_shortcut, value)

    def test_none_and_omitted_allowed(self):
        self.assertIsNone(AIConditionPayload(conditions=[]).time_shortcut)
        self.assertIsNone(AIConditionPayload(conditions=[], time_shortcut=None).time_shortcut)

    def test_invalid_form_rejected(self):
        for value in ("now-1w", "now-1M", "now--1d", "now-0d", "now-7D", "now", "yesterday", "now-1.5d", "now-1h30m"):
            with self.assertRaises(PydanticValidationError):
                AIConditionPayload(conditions=[], time_shortcut=value)


class TestResultColumn(AIAssistantTestCase):
    def test_full_key_standard(self):
        column = ResultColumn(raw_name="username")
        self.assertEqual(column.full_key, "username")

    def test_full_key_with_keys(self):
        column = ResultColumn(raw_name="extend_data", keys=["ticket_id"])
        self.assertEqual(column.full_key, "extend_data/ticket_id")

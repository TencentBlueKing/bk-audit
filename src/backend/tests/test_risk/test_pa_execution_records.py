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
software distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

import time

import pytest
from bk_resource import resource

from apps.sops.constants import SOPSTaskStatus
from services.web.risk.models import ProcessApplication, Risk, RiskRule, TicketNode
from tests.test_risk.test_tickets.constants import RISK_INFO


def _create_node(
    risk_id: str,
    state: str,
    task_id: int = 1,
    action: str = "AutoProcess",
    pa_id: int = None,
    pa_name: str = "",
    task_name: str = "",
    trigger: str = "",
    start_time: str = "",
    finish_time: str = "",
) -> TicketNode:
    process_result = {"task": {"task_id": task_id}, "status": {"state": state}}
    # 执行时套餐快照（新链路写入；pa_id=None 模拟历史节点）
    if pa_id is not None:
        process_result.update({"pa_id": pa_id, "pa_name": pa_name})
    if task_name or trigger:
        process_result.update({"task_name": task_name, "trigger": trigger})
    if start_time or finish_time:
        process_result["status"].update({"start_time": start_time, "finish_time": finish_time})
    return TicketNode.objects.create(
        risk_id=risk_id,
        operator="admin",
        current_operator=[],
        action=action,
        timestamp=time.time(),
        time="2026-09-20 12:00:00",
        process_result=process_result,
        extra={},
    )


@pytest.mark.django_db
class TestListPAExecutionRecords:
    def _prepare(self):
        ProcessApplication.objects.all().delete()
        RiskRule.objects.all().delete()
        Risk.objects.all().delete()
        TicketNode.objects.all().delete()
        from services.web.strategy_v2.models import Strategy

        strategy_id = RISK_INFO["strategy_id"]
        Strategy.objects.get_or_create(
            strategy_id=strategy_id, defaults={"strategy_name": f"test_strategy_{strategy_id}"}
        )
        pa_a = ProcessApplication.objects.create(name="套餐A", sops_template_id=1)
        pa_b = ProcessApplication.objects.create(name="套餐B", sops_template_id=2)
        rule_a = RiskRule.objects.create(name="规则A", scope=[], pa_id=pa_a.id, version=1, rule_id=101)
        risk_a = Risk.objects.create(**{**RISK_INFO, "risk_id": "R-A", "rule_id": rule_a.rule_id, "rule_version": 1})
        risk_b = Risk.objects.create(**{**RISK_INFO, "risk_id": "R-B", "raw_event_id": "raw-b"})
        RiskRule.objects.create(name="规则B", scope=[], pa_id=pa_b.id, version=1, rule_id=102)
        risk_b.rule_id = 102
        risk_b.save(update_fields=["rule_id"])
        return pa_a, pa_b, risk_a, risk_b

    def test_filter_by_pa(self):
        pa_a, pa_b, risk_a, risk_b = self._prepare()
        _create_node(risk_a.risk_id, SOPSTaskStatus.FINISHED.value, task_id=11)
        _create_node(risk_b.risk_id, SOPSTaskStatus.RUNNING.value, task_id=22)
        resp = resource.risk.list_pa_execution_records.perform_request({"pa_id": pa_a.id})
        records = resp["results"]
        assert resp["count"] == 1
        assert len(records) == 1
        assert records[0]["pa_name"] == "套餐A"
        assert records[0]["risk_id"] == "R-A"
        assert records[0]["sops_task_id"] == "11"
        assert records[0]["result"] == "success"
        assert records[0]["risk_title"] == (risk_a.title or "")

    def test_filter_by_risk(self):
        pa_a, pa_b, risk_a, risk_b = self._prepare()
        _create_node(risk_a.risk_id, SOPSTaskStatus.RUNNING.value, task_id=1)
        _create_node(risk_a.risk_id, SOPSTaskStatus.FAILED.value, task_id=2)
        _create_node(risk_b.risk_id, SOPSTaskStatus.FINISHED.value, task_id=3)
        resp = resource.risk.list_pa_execution_records.perform_request({"risk_id": risk_a.risk_id})
        records = resp["results"]
        assert resp["count"] == 2
        assert len(records) == 2
        results = {r["sops_task_id"] for r in records}
        assert results == {"1", "2"}

    def test_result_mapping_and_action_filter(self):
        pa_a, pa_b, risk_a, risk_b = self._prepare()
        _create_node(risk_a.risk_id, SOPSTaskStatus.RUNNING.value, task_id=1)
        _create_node(risk_a.risk_id, SOPSTaskStatus.FAILED.value, task_id=2)
        # 无状态（仅 task 无 status）→ unknown
        TicketNode.objects.create(
            risk_id=risk_a.risk_id,
            operator="admin",
            action="AutoProcess",
            timestamp=time.time(),
            time="2026-09-20 12:00:00",
            process_result={"task": {"task_id": 3}},
            extra={},
        )
        # 非 AutoProcess 节点不进执行记录
        _create_node(risk_a.risk_id, SOPSTaskStatus.FINISHED.value, task_id=4, action="NewRisk")
        resp = resource.risk.list_pa_execution_records.perform_request({})
        records = resp["results"]
        by_task = {r["sops_task_id"]: r["result"] for r in records}
        assert by_task == {"1": "running", "2": "failed", "3": "unknown"}

    def test_pa_snapshot_priority_over_rule_chain(self):
        """套餐归属：执行时快照优先，历史节点（无快照）走规则链路兜底"""
        pa_a, pa_b, risk_a, risk_b = self._prepare()
        # 场景1：手动分派——风险无规则（rule_id 空），节点带快照 → 归属正确
        risk_manual = Risk.objects.create(**{**RISK_INFO, "risk_id": "R-M", "raw_event_id": "raw-m", "rule_id": None})
        _create_node(
            risk_manual.risk_id,
            SOPSTaskStatus.FINISHED.value,
            task_id=9,
            pa_id=pa_b.id,
            pa_name="套餐B",
            task_name="套餐B_1790000000000",
            trigger="manual",
            start_time="2026-09-22 10:32:37 +0800",
            finish_time="2026-09-22 10:32:40 +0800",
        )
        # 场景2：历史节点（无快照）+ 风险规则 → 规则链路兜底
        _create_node(risk_a.risk_id, SOPSTaskStatus.FINISHED.value, task_id=10)
        # 场景3：快照与规则指向不同套餐（规则后来改绑）→ 以快照为准
        _create_node(risk_a.risk_id, SOPSTaskStatus.FINISHED.value, task_id=11, pa_id=pa_b.id, pa_name="套餐B")
        resp = resource.risk.list_pa_execution_records.perform_request({})
        records = resp["results"]
        by_task = {r["sops_task_id"]: (r["pa_id"], r["pa_name"]) for r in records}
        assert by_task["9"] == (pa_b.id, "套餐B")  # 无规则也能归属
        rec9 = next(r for r in records if r["sops_task_id"] == "9")
        assert rec9["task_name"] == "套餐B_1790000000000"
        assert rec9["trigger"] == "manual"
        assert rec9["duration"] == 3  # finish - start（秒）
        assert next(r for r in records if r["sops_task_id"] == "10")["duration"] is None  # 未结束无耗时
        assert by_task["10"] == (pa_a.id, "套餐A")  # 兜底链路
        assert by_task["11"] == (pa_b.id, "套餐B")  # 快照优先于规则

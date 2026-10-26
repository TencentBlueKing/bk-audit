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
from unittest import mock

import pytest
from bk_resource import resource
from django.db.models import Q
from django.http import Http404

from apps.sops.constants import SOPSTaskStatus
from core.exceptions import RiskStatusInvalid
from services.web.risk.constants import TicketNodeStatus
from services.web.risk.models import ProcessApplication, Risk, RiskRule, TicketNode
from tests.test_risk.test_tickets.constants import RISK_INFO


@pytest.fixture(autouse=True)
def _auth_all_risks():
    """测试环境无 IAM：默认放开风险数据范围（越权用例内层按需收窄）"""
    with mock.patch.object(Risk, "iam_risk_filter", return_value=~Q(pk=None)):
        yield


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
    task_url: str = "",
) -> TicketNode:
    process_result = {"task": {"task_id": task_id, "task_url": task_url}, "status": {"state": state}}
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
        _create_node(risk_a.risk_id, SOPSTaskStatus.FINISHED.value, task_id=11, task_url="https://sops.example/11")
        _create_node(risk_b.risk_id, SOPSTaskStatus.RUNNING.value, task_id=22)
        resp = resource.risk.list_pa_execution_records.perform_request({"pa_id": pa_a.id})
        records = resp["results"]
        assert resp["count"] == 1
        assert len(records) == 1
        assert records[0]["pa_name"] == "套餐A"
        assert records[0]["risk_id"] == "R-A"
        assert records[0]["sops_task_id"] == "11"
        assert records[0]["sops_task_url"] == "https://sops.example/11"
        assert records[0]["result"] == "success"
        assert records[0]["risk_title"] == (risk_a.title or "")

    def test_sops_task_url_empty_when_missing(self):
        """历史节点无 task_url 时透出空串，前端降级纯文本"""
        pa_a, pa_b, risk_a, risk_b = self._prepare()
        _create_node(risk_a.risk_id, SOPSTaskStatus.FINISHED.value, task_id=11)
        resp = resource.risk.list_pa_execution_records.perform_request({"pa_id": pa_a.id})
        assert resp["results"][0]["sops_task_url"] == ""

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

    def test_list_scoped_by_authed_risks(self):
        """数据范围收敛：无权查看的风险的执行记录不返回（对齐风险列表口径）"""
        pa_a, pa_b, risk_a, risk_b = self._prepare()
        _create_node(risk_a.risk_id, SOPSTaskStatus.FINISHED.value, task_id=11)
        _create_node(risk_b.risk_id, SOPSTaskStatus.FINISHED.value, task_id=22)
        with mock.patch.object(Risk, "iam_risk_filter", return_value=Q(risk_id__in=[risk_a.risk_id])):
            resp = resource.risk.list_pa_execution_records.perform_request({})
        assert resp["count"] == 1
        assert resp["results"][0]["risk_id"] == risk_a.risk_id

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

    def test_filter_trigger_multi_select(self):
        """触发方式支持多选（逗号分隔，任一命中）"""
        pa_a, pa_b, risk_a, risk_b = self._prepare()
        _create_node(risk_a.risk_id, SOPSTaskStatus.FINISHED.value, task_id=1, trigger="auto")
        _create_node(risk_a.risk_id, SOPSTaskStatus.FINISHED.value, task_id=2, trigger="manual")
        _create_node(risk_a.risk_id, SOPSTaskStatus.FINISHED.value, task_id=3, trigger="test")
        # 单值（兼容旧调用方）
        resp = resource.risk.list_pa_execution_records.perform_request({"trigger": "auto"})
        assert {r["sops_task_id"] for r in resp["results"]} == {"1"}
        # 多值
        resp = resource.risk.list_pa_execution_records.perform_request({"trigger": "auto,test"})
        assert {r["sops_task_id"] for r in resp["results"]} == {"1", "3"}
        # 多值含空白容错
        resp = resource.risk.list_pa_execution_records.perform_request({"trigger": " manual , test ,"})
        assert {r["sops_task_id"] for r in resp["results"]} == {"2", "3"}
        # 无命中
        resp = resource.risk.list_pa_execution_records.perform_request({"trigger": "unknown_type"})
        assert resp["count"] == 0

    def test_filter_result_multi_select(self):
        """状态支持多选（逗号分隔，任一命中）"""
        pa_a, pa_b, risk_a, risk_b = self._prepare()
        _create_node(risk_a.risk_id, SOPSTaskStatus.FINISHED.value, task_id=1)
        _create_node(risk_a.risk_id, SOPSTaskStatus.RUNNING.value, task_id=2)
        _create_node(risk_a.risk_id, SOPSTaskStatus.FAILED.value, task_id=3)
        _create_node(risk_a.risk_id, SOPSTaskStatus.REVOKED.value, task_id=4)
        # 无状态（仅 task 无 status）→ unknown
        TicketNode.objects.create(
            risk_id=risk_a.risk_id,
            operator="admin",
            action="AutoProcess",
            timestamp=time.time(),
            time="2026-09-20 12:00:00",
            process_result={"task": {"task_id": 5}},
            extra={},
        )
        # 单值（兼容旧调用方）
        resp = resource.risk.list_pa_execution_records.perform_request({"result": "success"})
        assert {r["sops_task_id"] for r in resp["results"]} == {"1"}
        # 多值：失败态（FAILED + REVOKED）与执行中组合
        resp = resource.risk.list_pa_execution_records.perform_request({"result": "failed,running"})
        assert {r["sops_task_id"] for r in resp["results"]} == {"2", "3", "4"}
        # 多值含 unknown
        resp = resource.risk.list_pa_execution_records.perform_request({"result": "success,unknown"})
        assert {r["sops_task_id"] for r in resp["results"]} == {"1", "5"}
        # 全量四种状态
        resp = resource.risk.list_pa_execution_records.perform_request({"result": "success,failed,running,unknown"})
        assert resp["count"] == 5

    def test_filter_trigger_and_result_combined(self):
        """触发方式 + 状态可组合多选"""
        pa_a, pa_b, risk_a, risk_b = self._prepare()
        _create_node(risk_a.risk_id, SOPSTaskStatus.FINISHED.value, task_id=1, trigger="auto")
        _create_node(risk_a.risk_id, SOPSTaskStatus.FAILED.value, task_id=2, trigger="auto")
        _create_node(risk_a.risk_id, SOPSTaskStatus.FINISHED.value, task_id=3, trigger="manual")
        _create_node(risk_a.risk_id, SOPSTaskStatus.RUNNING.value, task_id=4, trigger="test")
        resp = resource.risk.list_pa_execution_records.perform_request(
            {"trigger": "auto,test", "result": "failed,running"}
        )
        assert {r["sops_task_id"] for r in resp["results"]} == {"2", "4"}

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
        # 展示时间归一：SOPS 原始串带 +0800 偏移，输出统一本地 %Y-%m-%d %H:%M:%S
        assert rec9["finish_time"] == "2026-09-22 10:32:40"
        assert next(r for r in records if r["sops_task_id"] == "10")["duration"] is None  # 未结束无耗时
        assert by_task["10"] == (pa_a.id, "套餐A")  # 兜底链路
        assert by_task["11"] == (pa_b.id, "套餐B")  # 快照优先于规则

    def test_filter_pa_snapshot_priority(self):
        """筛选与展示同口径：快照与规则不一致时按快照命中（规则改绑/手动换套餐）"""
        pa_a, pa_b, risk_a, risk_b = self._prepare()
        # risk_a 规则指向套餐A，但执行时快照是套餐B
        _create_node(risk_a.risk_id, SOPSTaskStatus.FINISHED.value, task_id=51, pa_id=pa_b.id, pa_name="套餐B")
        # 筛套餐A（旧规则口径会误命中）：不应返回
        resp = resource.risk.list_pa_execution_records.perform_request({"pa_id": pa_a.id})
        assert resp["count"] == 0
        # 筛套餐B（快照口径）：命中且展示套餐B
        resp = resource.risk.list_pa_execution_records.perform_request({"pa_id": pa_b.id})
        records = resp["results"]
        assert [r["sops_task_id"] for r in records] == ["51"]
        assert records[0]["pa_id"] == pa_b.id
        assert records[0]["pa_name"] == "套餐B"

    def test_filter_pa_manual_dispatch(self):
        """手动分派（无规则）只有快照归属：按快照套餐可筛出"""
        pa_a, pa_b, risk_a, risk_b = self._prepare()
        risk_manual = Risk.objects.create(**{**RISK_INFO, "risk_id": "R-M", "rule_id": None})
        _create_node(risk_manual.risk_id, SOPSTaskStatus.FINISHED.value, task_id=52, pa_id=pa_a.id, pa_name="套餐A")
        resp = resource.risk.list_pa_execution_records.perform_request({"pa_id": pa_a.id})
        assert {r["sops_task_id"] for r in resp["results"]} == {"52"}

    def test_filter_pa_rule_version(self):
        """历史无快照节点按 (rule_id, rule_version) 归属：规则改绑新版本不影响旧版本归属"""
        pa_a, pa_b, risk_a, risk_b = self._prepare()
        # 规则101 出 v2 改绑套餐B；risk_a 固定 rule_version=1（v1 指向套餐A）
        RiskRule.objects.create(name="规则A-v2", scope=[], pa_id=pa_b.id, version=2, rule_id=101)
        _create_node(risk_a.risk_id, SOPSTaskStatus.FINISHED.value, task_id=53)
        # 筛套餐A（v1）：命中，展示套餐A
        resp = resource.risk.list_pa_execution_records.perform_request({"pa_id": pa_a.id})
        records = resp["results"]
        assert {r["sops_task_id"] for r in records} == {"53"}
        assert records[0]["pa_id"] == pa_a.id
        assert records[0]["pa_name"] == "套餐A"
        # 筛套餐B（v2）：不应命中旧版本风险的记录
        resp = resource.risk.list_pa_execution_records.perform_request({"pa_id": pa_b.id})
        assert "53" not in {r["sops_task_id"] for r in resp["results"]}

    def test_keyword_text_fields(self):
        """keyword 全量模糊：文本字段任一命中即返回"""
        pa_a, pa_b, risk_a, risk_b = self._prepare()
        _create_node(
            risk_a.risk_id,
            SOPSTaskStatus.FINISHED.value,
            task_id=61,
            pa_id=pa_a.id,
            pa_name="套餐A",
            task_name="云账号未启用MFA_1790000000000",
            trigger="auto",
        )
        _create_node(risk_b.risk_id, SOPSTaskStatus.FINISHED.value, task_id=62001, pa_id=pa_b.id, pa_name="套餐B")
        # 任务名称
        resp = resource.risk.list_pa_execution_records.perform_request({"keyword": "MFA"})
        assert {r["sops_task_id"] for r in resp["results"]} == {"61"}
        # 套餐名称（快照）
        resp = resource.risk.list_pa_execution_records.perform_request({"keyword": "套餐B"})
        assert {r["sops_task_id"] for r in resp["results"]} == {"62001"}
        # 风险 ID
        resp = resource.risk.list_pa_execution_records.perform_request({"keyword": "R-A"})
        assert {r["sops_task_id"] for r in resp["results"]} == {"61"}
        # 执行记录 ID
        node = TicketNode.objects.get(risk_id=risk_a.risk_id, action="AutoProcess")
        resp = resource.risk.list_pa_execution_records.perform_request({"keyword": node.id})
        assert {r["sops_task_id"] for r in resp["results"]} == {"61"}
        # 任务 ID（sops_task_id，str/int 兼容）
        resp = resource.risk.list_pa_execution_records.perform_request({"keyword": "62001"})
        assert {r["sops_task_id"] for r in resp["results"]} == {"62001"}
        # 执行人
        resp = resource.risk.list_pa_execution_records.perform_request({"keyword": "admin"})
        assert resp["count"] == 2

    def test_keyword_risk_fields(self):
        """keyword 命中风险标题/状态/等级（Risk 跨表子查询）"""
        pa_a, pa_b, risk_a, risk_b = self._prepare()
        risk_a.title = "云账号未启用MFA"
        risk_a.risk_level = "high"
        risk_a.save(update_fields=["title", "risk_level"])
        risk_b.risk_level = "low"
        risk_b.save(update_fields=["risk_level"])
        _create_node(risk_a.risk_id, SOPSTaskStatus.FINISHED.value, task_id=71)
        _create_node(risk_b.risk_id, SOPSTaskStatus.FINISHED.value, task_id=72)
        resp = resource.risk.list_pa_execution_records.perform_request({"keyword": "未启用MFA"})
        assert {r["sops_task_id"] for r in resp["results"]} == {"71"}
        resp = resource.risk.list_pa_execution_records.perform_request({"keyword": "high"})
        assert {r["sops_task_id"] for r in resp["results"]} == {"71"}
        resp = resource.risk.list_pa_execution_records.perform_request({"keyword": "new"})
        assert resp["count"] == 2

    def test_keyword_trigger_labels(self):
        """触发方式：中文展示词/内部值/标签片段命中"""
        pa_a, pa_b, risk_a, risk_b = self._prepare()
        _create_node(risk_a.risk_id, SOPSTaskStatus.FINISHED.value, task_id=81, trigger="auto")
        _create_node(risk_a.risk_id, SOPSTaskStatus.FINISHED.value, task_id=82, trigger="manual")
        _create_node(risk_a.risk_id, SOPSTaskStatus.FINISHED.value, task_id=83, trigger="test")
        # 中文展示词
        resp = resource.risk.list_pa_execution_records.perform_request({"keyword": "自动"})
        assert {r["sops_task_id"] for r in resp["results"]} == {"81"}
        # 内部值（大小写不敏感）
        resp = resource.risk.list_pa_execution_records.perform_request({"keyword": "MANUAL"})
        assert {r["sops_task_id"] for r in resp["results"]} == {"82"}
        # 标签片段（keyword 是展示词子串）
        resp = resource.risk.list_pa_execution_records.perform_request({"keyword": "测试"})
        assert {r["sops_task_id"] for r in resp["results"]} == {"83"}
        # 单字不展开枚举（防噪音），测试记录 trigger 无中文文本，应无命中
        resp = resource.risk.list_pa_execution_records.perform_request({"keyword": "动"})
        assert resp["count"] == 0

    def test_keyword_result_labels(self):
        """执行状态：中文展示词/内部值命中（result 为计算字段，按 state 集合展开）"""
        pa_a, pa_b, risk_a, risk_b = self._prepare()
        _create_node(risk_a.risk_id, SOPSTaskStatus.FINISHED.value, task_id=91)
        _create_node(risk_a.risk_id, SOPSTaskStatus.FAILED.value, task_id=92)
        _create_node(risk_a.risk_id, SOPSTaskStatus.REVOKED.value, task_id=93)
        _create_node(risk_a.risk_id, SOPSTaskStatus.RUNNING.value, task_id=94)
        # 中文：执行成功 / 执行失败 / 执行中
        resp = resource.risk.list_pa_execution_records.perform_request({"keyword": "执行成功"})
        assert {r["sops_task_id"] for r in resp["results"]} == {"91"}
        resp = resource.risk.list_pa_execution_records.perform_request({"keyword": "执行失败"})
        assert {r["sops_task_id"] for r in resp["results"]} == {"92", "93"}  # 失败态含 REVOKED
        resp = resource.risk.list_pa_execution_records.perform_request({"keyword": "执行中"})
        assert {r["sops_task_id"] for r in resp["results"]} == {"94"}
        # 标签片段
        resp = resource.risk.list_pa_execution_records.perform_request({"keyword": "成功"})
        assert {r["sops_task_id"] for r in resp["results"]} == {"91"}
        # 内部值
        resp = resource.risk.list_pa_execution_records.perform_request({"keyword": "failed"})
        assert {r["sops_task_id"] for r in resp["results"]} == {"92", "93"}
        # 英文部分匹配不展开枚举，但 sops_state 原文 icontains 兜底（RUNNING）
        resp = resource.risk.list_pa_execution_records.perform_request({"keyword": "RUNN"})
        assert {r["sops_task_id"] for r in resp["results"]} == {"94"}

    def test_keyword_or_semantics_and_combine(self):
        """多字段 OR；与其他筛选 AND 叠加"""
        pa_a, pa_b, risk_a, risk_b = self._prepare()
        _create_node(risk_a.risk_id, SOPSTaskStatus.FINISHED.value, task_id=101, pa_id=pa_a.id, pa_name="套餐A")
        _create_node(risk_b.risk_id, SOPSTaskStatus.FINISHED.value, task_id=102, pa_id=pa_b.id, pa_name="套餐B")
        # 一个关键词命中两个不同字段的两条记录（OR）
        resp = resource.risk.list_pa_execution_records.perform_request({"keyword": "R-A"})
        assert {r["sops_task_id"] for r in resp["results"]} == {"101"}
        resp = resource.risk.list_pa_execution_records.perform_request({"keyword": "R-"})
        assert {r["sops_task_id"] for r in resp["results"]} == {"101", "102"}
        # 与 pa_id 筛选 AND 叠加
        resp = resource.risk.list_pa_execution_records.perform_request({"keyword": "R-", "pa_id": pa_a.id})
        assert {r["sops_task_id"] for r in resp["results"]} == {"101"}
        # 空串不过滤
        resp = resource.risk.list_pa_execution_records.perform_request({"keyword": "  "})
        assert resp["count"] == 2
        # 无命中返回空
        resp = resource.risk.list_pa_execution_records.perform_request({"keyword": "不存在的关键词xyz"})
        assert resp["count"] == 0

    def test_keyword_legacy_pa_name_fallback(self):
        """历史无快照记录的套餐名兜底：快照 pa_name 为空时按规则链路反查套餐名命中"""
        pa_a, pa_b, risk_a, risk_b = self._prepare()
        # risk_a(rule 101 → 套餐A) 历史节点无快照；展示 pa_name 走规则兜底为「套餐A」
        _create_node(risk_a.risk_id, SOPSTaskStatus.FINISHED.value, task_id=111)
        resp = resource.risk.list_pa_execution_records.perform_request({"keyword": "套餐A"})
        assert {r["sops_task_id"] for r in resp["results"]} == {"111"}
        resp = resource.risk.list_pa_execution_records.perform_request({"keyword": "套餐B"})
        assert resp["count"] == 0


@pytest.mark.django_db
class TestGetPAExecutionRecordDetail:
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
        risk = Risk.objects.create(**{**RISK_INFO, "risk_id": "R-D", "title": "详情风险标题"})
        return risk

    def test_detail_returns_risk_fields(self):
        """详情顶层返回风险单关联字段（重试接口需以 risk_id 为 URL 入参）"""
        risk = self._prepare()
        node = _create_node(risk.risk_id, SOPSTaskStatus.FINISHED.value, task_id=1, task_url="https://sops.example/1")
        resp = resource.risk.get_pa_execution_record_detail.perform_request({"id": node.id})
        assert resp["id"] == node.id
        assert resp["risk_id"] == "R-D"
        assert resp["risk_title"] == "详情风险标题"
        assert resp["risk_status"] == (risk.status or "")
        assert resp["sops_task_url"] == "https://sops.example/1"
        # 风险描述 / 风险证据来自 params（重试场景需展示）
        assert resp["params"]["risk_description"] == RISK_INFO["event_content"]
        assert resp["params"]["risk_evidence"] == RISK_INFO["event_evidence"]
        # 无重试记录
        assert resp["retry_count"] == 0
        assert resp["retry_history"] == []

    def test_detail_retry_history_passthrough(self):
        """重试快照原样透传（全量节点，被重试节点带 retried 标记，不再有 time 字段）"""
        risk = self._prepare()
        node = _create_node(risk.risk_id, SOPSTaskStatus.FINISHED.value, task_id=3)
        retry_entry = {
            "state": SOPSTaskStatus.FAILED.value,
            "operator": "tester",
            "attempts": [
                {
                    "node_id": "node0",
                    "node_name": "前置节点",
                    "state": SOPSTaskStatus.FINISHED.value,
                    "start_time": "2026-10-16 20:44:20",
                    "end_time": "2026-10-16 20:44:30",
                    "duration": 10,
                    "error_message": "",
                    "retried": False,
                },
                {
                    "node_id": "node1",
                    "node_name": "发单节点",
                    "state": SOPSTaskStatus.FAILED.value,
                    "start_time": "2026-10-16 20:44:31",
                    "end_time": "2026-10-16 20:44:32",
                    "duration": 1,
                    "error_message": "调用 IAM 接口超时",
                    "retried": True,
                },
            ],
        }
        node.process_result["retry_history"] = [retry_entry]
        node.save(update_fields=["process_result"])
        resp = resource.risk.get_pa_execution_record_detail.perform_request({"id": node.id})
        assert resp["retry_count"] == 1
        assert resp["retry_history"] == [retry_entry]

    def test_detail_denied_for_unauthorized_risk(self):
        """数据范围收敛：风险存在但调用者无权查看 → 404（对齐 RetrieveRisk 口径）"""
        risk = self._prepare()
        node = _create_node(risk.risk_id, SOPSTaskStatus.FINISHED.value, task_id=5)
        with mock.patch.object(Risk, "iam_risk_filter", return_value=Q(risk_id__in=["R-OTHER"])):
            with pytest.raises(Http404):
                resource.risk.get_pa_execution_record_detail.perform_request({"id": node.id})

    def test_detail_marks_retried_nodes(self):
        """顶层 attempts 的重试标记：取 retry_history 各次快照中 retried=True 的节点并集"""
        risk = self._prepare()
        node = _create_node(risk.risk_id, SOPSTaskStatus.RUNNING.value, task_id=7)
        node.process_result["status"]["children"] = {
            "node0": {
                "id": "node0",
                "name": "前置节点",
                "state": SOPSTaskStatus.FINISHED.value,
                "start_time": "2026-10-21 11:00:02",
                "finish_time": "2026-10-21 11:00:02",
                "elapsed_time": 0,
            },
            "node1": {
                "id": "node1",
                "name": "回调",
                "state": SOPSTaskStatus.RUNNING.value,
                "start_time": "2026-10-26 16:49:55",
                "finish_time": "",
                "elapsed_time": 3,
            },
        }
        node.process_result["retry_history"] = [
            {
                "operator": "tester",
                "attempts": [
                    {"node_id": "node0", "node_name": "前置节点", "state": SOPSTaskStatus.FINISHED.value, "retried": False},
                    {"node_id": "node1", "node_name": "回调", "state": SOPSTaskStatus.FAILED.value, "retried": False},
                ],
            }
        ]
        # 累计被重试过的节点（上一次重试命中了 node1）
        node.process_result["retried_node_ids"] = ["node1"]
        node.save(update_fields=["process_result"])
        resp = resource.risk.get_pa_execution_record_detail.perform_request({"id": node.id})
        attempts = {item["node_id"]: item for item in resp["attempts"]}
        # 全量返回，被重试过的节点带标记；重试时刻体现在该节点最新一次 start_time
        assert set(attempts) == {"node0", "node1"}
        assert attempts["node1"]["retried"] is True
        assert attempts["node1"]["start_time"] == "2026-10-26 16:49:55"
        assert attempts["node0"]["retried"] is False


@pytest.mark.django_db
class TestRetryAutoProcessRetryHistory:
    def test_retry_writes_history_snapshot(self):
        """重试前固化失败快照，多次重试仅 append；详情可见重试记录"""
        ProcessApplication.objects.all().delete()
        RiskRule.objects.all().delete()
        Risk.objects.all().delete()
        TicketNode.objects.all().delete()
        risk = Risk.objects.create(**{**RISK_INFO, "risk_id": "R-R"})
        node = _create_node(risk.risk_id, SOPSTaskStatus.FAILED.value, task_id=99)
        status_with_failure = {
            "state": SOPSTaskStatus.FAILED.value,
            "children": {
                "node0": {
                    "id": "node0",
                    "name": "前置节点",
                    "state": SOPSTaskStatus.FINISHED.value,
                    "start_time": "2026-10-16 20:44:20",
                    "finish_time": "2026-10-16 20:44:30",
                    "elapsed_time": 10,
                    "error_message": "",
                },
                "node1": {
                    "id": "node1",
                    "name": "发单节点",
                    "state": SOPSTaskStatus.FAILED.value,
                    "start_time": "2026-10-16 20:44:31",
                    "finish_time": "2026-10-16 20:44:32",
                    "elapsed_time": 1,
                    "error_message": "调用 IAM 接口超时",
                },
            },
        }
        with mock.patch(
            "services.web.risk.resources.risk.api.bk_sops.get_task_status",
            mock.Mock(return_value=status_with_failure),
        ), mock.patch(
            "services.web.risk.resources.risk.api.bk_sops.get_node_data",
            mock.Mock(return_value={"inputs": {}}),
        ), mock.patch(
            "services.web.risk.resources.risk.api.bk_sops.operate_node",
            mock.Mock(return_value=None),
        ), mock.patch(
            "services.web.risk.resources.risk.sync_auto_result.apply_async",
            mock.Mock(return_value=None),
        ), mock.patch(
            "services.web.risk.resources.risk.get_request_username",
            mock.Mock(return_value="tester"),
        ):
            resource.risk.retry_auto_process.perform_request({"risk_id": risk.risk_id, "node_id": node.id})
        node.refresh_from_db()
        assert node.status == TicketNodeStatus.RUNNING
        history = node.process_result["retry_history"]
        assert len(history) == 1
        entry = history[0]
        assert entry["operator"] == "tester"
        # 该轮任务级状态（与顶层 sops_state 同口径），不因落库时乐观改为执行中而丢失
        assert entry["state"] == SOPSTaskStatus.FAILED.value
        # 重试时刻由 attempts 的 start_time 表达，不再冗余 time 字段
        assert "time" not in entry
        # 快照全量：成功节点与失败节点都在
        snapshot = {item["node_id"]: item for item in entry["attempts"]}
        assert set(snapshot) == {"node0", "node1"}
        # 这是首次执行现场，此时还没有发生过任何重试 → retried 全为 false
        assert snapshot["node1"]["retried"] is False
        assert snapshot["node0"]["retried"] is False
        # 本次重试命中的节点并入累计集合，供后续快照与当前 attempts 标记
        assert node.process_result["retried_node_ids"] == ["node1"]
        # 快照固化重试前的失败现场
        failed = snapshot["node1"]
        assert failed["state"] == SOPSTaskStatus.FAILED.value
        assert failed["error_message"] == "调用 IAM 接口超时"
        assert failed["duration"] == 1
        # 详情透传
        detail = resource.risk.get_pa_execution_record_detail.perform_request({"id": node.id})
        assert detail["retry_count"] == 1
        assert detail["retry_history"] == history

    def test_retry_history_appends(self):
        """多次重试逐次追加，不覆盖"""
        ProcessApplication.objects.all().delete()
        RiskRule.objects.all().delete()
        Risk.objects.all().delete()
        TicketNode.objects.all().delete()
        risk = Risk.objects.create(**{**RISK_INFO, "risk_id": "R-R2"})
        node = _create_node(risk.risk_id, SOPSTaskStatus.FAILED.value, task_id=98)
        status_with_failure = {
            "state": SOPSTaskStatus.FAILED.value,
            "children": {
                "node1": {
                    "id": "node1",
                    "name": "发单节点",
                    "state": SOPSTaskStatus.FAILED.value,
                    "error_message": "第 N 次失败",
                }
            },
        }
        with mock.patch(
            "services.web.risk.resources.risk.api.bk_sops.get_task_status",
            # 每次回源返回新对象，避免落库时把 state 改成执行中后污染下一次调用
            mock.Mock(side_effect=lambda *args, **kwargs: dict(status_with_failure)),
        ), mock.patch(
            "services.web.risk.resources.risk.api.bk_sops.get_node_data",
            mock.Mock(return_value={"inputs": {}}),
        ), mock.patch(
            "services.web.risk.resources.risk.api.bk_sops.operate_node",
            mock.Mock(return_value=None),
        ), mock.patch(
            "services.web.risk.resources.risk.sync_auto_result.apply_async",
            mock.Mock(return_value=None),
        ), mock.patch(
            "services.web.risk.resources.risk.get_request_username",
            mock.Mock(return_value="tester"),
        ):
            resource.risk.retry_auto_process.perform_request({"risk_id": risk.risk_id, "node_id": node.id})
            resource.risk.retry_auto_process.perform_request({"risk_id": risk.risk_id, "node_id": node.id})
        node.refresh_from_db()
        history = node.process_result["retry_history"]
        assert len(history) == 2
        assert all(item["attempts"][0]["error_message"] == "第 N 次失败" for item in history)
        # 每次快照都固化该轮的任务级状态
        assert all(item["state"] == SOPSTaskStatus.FAILED.value for item in history)
        # 重试标记是累计口径：首次现场全 false，之后的现场才标记上一轮被重试的节点
        assert all("time" not in item for item in history)
        assert history[0]["attempts"][0]["retried"] is False
        assert history[1]["attempts"][0]["retried"] is True
        assert node.process_result["retried_node_ids"] == ["node1"]

    def test_retry_rejected_without_failed_node(self):
        """无可重试的失败节点（任务已终止）：不写快照、不假置 RUNNING，并落库回源到的真实状态"""
        ProcessApplication.objects.all().delete()
        RiskRule.objects.all().delete()
        Risk.objects.all().delete()
        TicketNode.objects.all().delete()
        risk = Risk.objects.create(**{**RISK_INFO, "risk_id": "R-R3"})
        node = _create_node(risk.risk_id, SOPSTaskStatus.FAILED.value, task_id=97)
        revoked_status = {
            "state": SOPSTaskStatus.REVOKED.value,
            "children": {"node1": {"id": "node1", "name": "发单节点", "state": SOPSTaskStatus.FINISHED.value}},
        }
        with mock.patch(
            "services.web.risk.resources.risk.api.bk_sops.get_task_status",
            mock.Mock(return_value=revoked_status),
        ), mock.patch(
            "services.web.risk.resources.risk.api.bk_sops.operate_node", mock.Mock(return_value=None)
        ) as mock_operate:
            with pytest.raises(RiskStatusInvalid):
                resource.risk.retry_auto_process.perform_request({"risk_id": risk.risk_id, "node_id": node.id})
        mock_operate.assert_not_called()
        node.refresh_from_db()
        assert node.process_result.get("retry_history") is None
        assert node.process_result["status"]["state"] == SOPSTaskStatus.REVOKED.value

    def test_detail_without_risk(self):
        """Risk 不存在时 risk_id 仍有值，风险单字段为空串、params 为空"""
        ProcessApplication.objects.all().delete()
        RiskRule.objects.all().delete()
        Risk.objects.all().delete()
        TicketNode.objects.all().delete()
        node = _create_node("R-GONE", SOPSTaskStatus.FAILED.value, task_id=2)
        resp = resource.risk.get_pa_execution_record_detail.perform_request({"id": node.id})
        assert resp["risk_id"] == "R-GONE"
        assert resp["risk_title"] == ""
        assert resp["risk_status"] == ""
        assert resp["params"] == {}


class TestSopsTimeFormat:
    """SOPS 时间展示归一：本地 %Y-%m-%d %H:%M:%S，不透传时区偏移"""

    def test_format_sops_time(self):
        from services.web.risk.utils import format_sops_time

        assert format_sops_time("2026-10-22 11:51:54 +0800") == "2026-10-22 11:51:54"
        assert format_sops_time("2026-10-22 11:42:48") == "2026-10-22 11:42:48"
        assert format_sops_time("2026-10-22T03:51:54+00:00") == "2026-10-22 11:51:54"  # 外源时区转本地墙钟
        assert format_sops_time("bad-value") == "bad-value"  # 解析失败原样返回，不吞数据
        assert format_sops_time("") == ""
        assert format_sops_time(None) == ""

    def test_calc_task_finish_time_normalized(self):
        from services.web.risk.utils import calc_task_finish_time

        children = {
            "node1": {"start_time": "2026-10-22 11:42:48", "finish_time": "2026-10-22 11:51:54 +0800"},
            "node2": {"start_time": "2026-10-22 11:50:00", "finish_time": "2026-10-22 11:55:00"},
        }
        # 任务级优先
        assert calc_task_finish_time({"finish_time": "2026-10-22 11:51:54 +0800", "children": children}) == (
            "2026-10-22 11:51:54"
        )
        # 任务级缺失退化取子节点最晚结束时间，同样归一
        assert calc_task_finish_time({"children": children}) == "2026-10-22 11:55:00"
        assert calc_task_finish_time({}) == ""

    def test_extract_attempt_records_normalized(self):
        from services.web.risk.utils import extract_attempt_records

        status = {
            "children": {
                "node1": {
                    "name": "发单节点",
                    "state": "FAILED",
                    "start_time": "2026-10-22 11:42:48",
                    "finish_time": "2026-10-22 11:51:54 +0800",
                }
            }
        }
        attempts = extract_attempt_records(status)
        assert attempts[0]["start_time"] == "2026-10-22 11:42:48"
        assert attempts[0]["end_time"] == "2026-10-22 11:51:54"


@pytest.mark.django_db
class TestHasExecutionRecords:
    """「有无执行记录」判定与执行记录列表同口径（_pa_filter_q 归属 + load_authed_risks 范围）"""

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
        return pa_a, pa_b, risk_a

    def _bind_scene(self, scene, *pas):
        from services.web.scene.constants import ResourceVisibilityType
        from services.web.scene.filters import BindingMetadataHelper

        for pa in pas:
            BindingMetadataHelper.create_resource_binding(
                resource_id=str(pa.id),
                resource_type=ResourceVisibilityType.PROCESS_APPLICATION,
                scene_id=scene.scene_id,
            )

    def _query(self, scene, has_execution_records):
        resp = resource.risk.list_all_process_applications.perform_request(
            {"scene_id": scene.scene_id, "has_execution_records": has_execution_records}
        )
        return sorted(item["id"] for item in resp)

    def test_legacy_snapshotless_records_counted(self):
        """历史无快照记录经规则链路归属：有记录筛选含它、无记录筛选不含它（孤儿口径不漏）"""
        from services.web.scene.models import Scene

        pa_a, pa_b, risk_a = self._prepare()
        scene = Scene.objects.create(name="has-exec-scene-legacy")
        self._bind_scene(scene, pa_a, pa_b)
        _create_node(risk_a.risk_id, SOPSTaskStatus.FINISHED.value, task_id=11, pa_id=None)
        assert self._query(scene, True) == [pa_a.id]
        assert self._query(scene, False) == [pa_b.id]

    def test_snapshot_records_counted(self):
        """快照记录正常计入（基线）"""
        from services.web.scene.models import Scene

        pa_a, pa_b, risk_a = self._prepare()
        scene = Scene.objects.create(name="has-exec-scene-snapshot")
        self._bind_scene(scene, pa_a, pa_b)
        _create_node(risk_a.risk_id, SOPSTaskStatus.FINISHED.value, task_id=11, pa_id=pa_b.id)
        assert self._query(scene, True) == [pa_b.id]
        assert self._query(scene, False) == [pa_a.id]

    def test_unauthed_risk_records_not_counted(self):
        """无权风险的记录不计入「有记录」（与列表所见一致，不会点进去空列表）"""
        from services.web.scene.models import Scene

        pa_a, pa_b, risk_a = self._prepare()
        scene = Scene.objects.create(name="has-exec-scene-auth")
        self._bind_scene(scene, pa_a, pa_b)
        _create_node(risk_a.risk_id, SOPSTaskStatus.FINISHED.value, task_id=11, pa_id=pa_a.id)
        with mock.patch.object(Risk, "iam_risk_filter", return_value=Q(risk_id__in=["R-OTHER"])):
            assert self._query(scene, True) == []
            assert self._query(scene, False) == [pa_a.id, pa_b.id]

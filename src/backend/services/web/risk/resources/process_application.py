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

import abc

from django.db import transaction
from django.db.models import Count, F, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.translation import gettext, gettext_lazy
from rest_framework import serializers
from rest_framework.settings import api_settings

from apps.audit.resources import AuditMixinResource
from apps.meta.constants import OrderTypeChoices
from apps.permission.handlers.actions import ActionEnum
from apps.permission.handlers.resource_types import ResourceEnum
from apps.sops.constants import SOPSTaskStatus
from services.web.risk.constants import ApproveTicketFields, RiskStatus
from services.web.risk.models import (
    ProcessApplication,
    Risk,
    RiskRule,
    TicketNode,
    calc_task_duration,
)
from services.web.risk.serializers import (
    CreateProcessApplicationsReqSerializer,
    ListAllProcessApplicationsReqSerializer,
    ListProcessApplicationsReqSerializer,
    ListRiskResponseSerializer,
    ProcessApplicationsInfoSerializer,
    RiskRuleInfoSerializer,
    ToggleProcessApplicationReqSerializer,
    UpdateProcessApplicationsReqSerializer,
)
from services.web.scene.constants import ResourceVisibilityType
from services.web.scene.filters import BindingMetadataHelper, SceneScopeFilter
from services.web.strategy_v2.models import Strategy


class ProcessApplicationMeta(AuditMixinResource, abc.ABC):
    tags = ["ProcessApplication"]


class ListProcessApplications(ProcessApplicationMeta):
    name = gettext_lazy("获取处理套餐列表")
    RequestSerializer = ListProcessApplicationsReqSerializer
    ResponseSerializer = ProcessApplicationsInfoSerializer
    many_response_data = True
    audit_action = ActionEnum.LIST_PA

    def perform_request(self, validated_request_data):
        # 场景过滤
        scene_id = validated_request_data.pop("scene_id", None)
        order_field = validated_request_data.pop("order_field", "-created_at")
        # 构造筛选条件
        q = Q()
        for key, val in validated_request_data.items():
            _q = Q()
            for item in val:
                _q |= Q(**{key: item})
            q &= _q
        # 场景过滤
        # 筛选数据（SceneScopeFilter 会处理 scene_id 过滤，未指定时返回全部）
        process_applications = SceneScopeFilter.filter_queryset(
            queryset=ProcessApplication.objects.filter(q),
            scene_id=scene_id,
            resource_type=ResourceVisibilityType.PROCESS_APPLICATION,
            pk_field="id",
        ).order_by("-is_enabled", order_field)
        # 获取关联的规则
        rule_map = {
            item["pa_id"]: item["count"]
            for item in RiskRule.load_latest_rules()
            .filter(pa_id__in=process_applications.values("id"))
            .values("pa_id")
            .annotate(count=Count("pa_id"))
            .order_by()
        }
        for pa in process_applications:
            setattr(pa, "rule_count", rule_map.get(pa.id, 0))
        return process_applications


class ListAllProcessApplications(ProcessApplicationMeta):
    name = gettext_lazy("获取所有处理套餐列表")
    RequestSerializer = ListAllProcessApplicationsReqSerializer
    audit_action = ActionEnum.LIST_PA

    def perform_request(self, validated_request_data):
        # 风险处理人不一定有处理套餐相关 action 权限，但风险单展示需要按场景加载套餐名称。
        scene_id = validated_request_data["scene_id"]
        process_applications = ProcessApplication.objects.all()
        process_applications = SceneScopeFilter.filter_queryset(
            queryset=process_applications,
            scene_id=scene_id,
            resource_type=ResourceVisibilityType.PROCESS_APPLICATION,
            pk_field="id",
        )
        return [
            {"id": pa.id, "name": pa.name, "sops_template_id": pa.sops_template_id, "is_enabled": pa.is_enabled}
            for pa in process_applications
        ]


class CreateProcessApplication(ProcessApplicationMeta):
    name = gettext_lazy("创建处理套餐")
    RequestSerializer = CreateProcessApplicationsReqSerializer
    ResponseSerializer = ProcessApplicationsInfoSerializer
    audit_action = ActionEnum.CREATE_PA

    @transaction.atomic
    def perform_request(self, validated_request_data):
        scene_id = validated_request_data.pop("scene_id", None)
        pa = ProcessApplication.objects.create(**validated_request_data)
        # 创建 ResourceBinding 关联（scene_id 必传，序列化器已校验）
        BindingMetadataHelper.create_resource_binding(
            resource_id=str(pa.id),
            resource_type=ResourceVisibilityType.PROCESS_APPLICATION,
            scene_id=scene_id,
        )
        return pa


def _reject_builtin_edit(pa: ProcessApplication) -> None:
    """
    内置套餐（BKSEC 发单）禁止编辑/启停：

    参数由策略配置生成并挂在自动规则上，套餐本身不承载配置；
    修改 need_approve/sops_template_id 等会破坏发送契约。
    """
    if pa.is_builtin:
        raise serializers.ValidationError(
            gettext("内置套餐【%s】由系统维护，不支持编辑或启停；如需调整 SOPS 模板请修改 BKSEC_SOPS_TEMPLATE_ID 环境变量") % pa.name
        )


class UpdateProcessApplication(ProcessApplicationMeta):
    name = gettext_lazy("更新处理套餐")
    RequestSerializer = UpdateProcessApplicationsReqSerializer
    ResponseSerializer = ProcessApplicationsInfoSerializer
    audit_action = ActionEnum.EDIT_PA

    def perform_request(self, validated_request_data):
        pa = get_object_or_404(ProcessApplication, id=validated_request_data["id"])
        _reject_builtin_edit(pa)
        for key, val in validated_request_data.items():
            setattr(pa, key, val)
        pa.save()
        return pa


class ListRiskByPA(ProcessApplicationMeta):
    name = gettext_lazy("获取处理套餐命中的风险")
    ResponseSerializer = ListRiskResponseSerializer
    many_response_data = True
    audit_action = ActionEnum.LIST_RISK
    audit_resource_type = ResourceEnum.RISK

    def perform_request(self, validated_request_data):
        # 获取处理套餐实例
        pa = get_object_or_404(ProcessApplication, id=validated_request_data["id"])
        # 获取规则列表
        rules = RiskRule.objects.filter(pa_id=pa.id)
        # 拼接筛选条件
        q = Q()
        for rule in rules:
            q |= Q(rule_id=rule.rule_id, rule_version=rule.version)
        qs = Risk.load_authed_risks(action=ActionEnum.LIST_RISK)
        risks = Risk.annotated_queryset(qs).exclude(status=RiskStatus.CLOSED).filter(q)
        return risks


class ListRuleByPA(ProcessApplicationMeta):
    name = gettext_lazy("获取处理套餐关联的规则")
    ResponseSerializer = RiskRuleInfoSerializer
    many_response_data = True
    audit_action = ActionEnum.LIST_RULE

    def perform_request(self, validated_request_data):
        # 获取处理套餐实例
        pa = get_object_or_404(ProcessApplication, id=validated_request_data["id"])
        # 获取规则列表
        order_field = validated_request_data.get("order_field", "-created_at")
        order_field = (
            f"-{order_field}" if validated_request_data.get("order_type") == OrderTypeChoices.DESC else order_field
        )
        return RiskRule.load_latest_rules().filter(pa_id=pa.id).order_by("-is_enabled", order_field)


class ListPAExecutionRecords(ProcessApplicationMeta):
    """
    获取处理套餐执行记录（执行记录侧滑：套餐页看全部/单套餐，风险入口按风险ID筛选）

    数据链路：TicketNode(action=AutoProcess) → Risk(rule_id) → RiskRule(pa_id) → 套餐
    """

    name = gettext_lazy("获取处理套餐执行记录")
    # 分页响应：返回 {count, page, page_size, num_pages, results[]}；框架无 serializer 时直接透传 dict
    audit_action = ActionEnum.LIST_PA

    @staticmethod
    def _build_failure_hint(process_result: dict) -> str:
        """读取写入点已落库的失败提示（渠道无关，无需在此翻译）"""
        return process_result.get("failure_hint") or ""

    class RequestSerializer(serializers.Serializer):
        pa_id = serializers.IntegerField(label=gettext_lazy("套餐ID"), required=False, allow_null=True)
        risk_id = serializers.CharField(label=gettext_lazy("风险ID"), required=False, allow_blank=True, allow_null=True)
        scene_id = serializers.IntegerField(label=gettext_lazy("场景ID"), required=False, allow_null=True)
        task_id = serializers.CharField(label=gettext_lazy("任务ID"), required=False, allow_blank=True)
        task_name = serializers.CharField(label=gettext_lazy("任务名称"), required=False, allow_blank=True)
        pa_name = serializers.CharField(label=gettext_lazy("套餐名称"), required=False, allow_blank=True)
        trigger = serializers.CharField(label=gettext_lazy("触发方式"), required=False, allow_blank=True)
        result = serializers.CharField(label=gettext_lazy("状态"), required=False, allow_blank=True)
        operator = serializers.CharField(label=gettext_lazy("执行人"), required=False, allow_blank=True)
        order_by = serializers.CharField(
            label=gettext_lazy("排序字段"), required=False, allow_blank=True, default="-start_time"
        )
        page = serializers.IntegerField(label=gettext_lazy("页码"), required=False, min_value=1, default=1)
        page_size = serializers.IntegerField(
            label=gettext_lazy("单页数量"), required=False, min_value=1, max_value=100, default=20
        )

    def perform_request(self, validated_request_data):
        pa_id = validated_request_data.get("pa_id")
        risk_id = validated_request_data.get("risk_id")
        scene_id = validated_request_data.get("scene_id")
        task_id = validated_request_data.get("task_id", "").strip()
        task_name = validated_request_data.get("task_name", "").strip()
        pa_name = validated_request_data.get("pa_name", "").strip()
        trigger = validated_request_data.get("trigger", "").strip()
        result_filter = validated_request_data.get("result", "").strip()
        operator = validated_request_data.get("operator", "").strip()
        order_by = validated_request_data.get("order_by", "-start_time").strip()
        page = validated_request_data.get("page", 1)
        page_size = validated_request_data.get("page_size", 20)

        # 处理套餐执行记录包含测试单（is_test 不过滤）
        nodes = TicketNode.objects.filter(action="AutoProcess")

        # 套餐筛选 / 场景范围：套餐 → 规则 → 风险 → 执行节点
        if pa_id or scene_id:
            pa_queryset = ProcessApplication.objects.all()
            if pa_id:
                pa_queryset = pa_queryset.filter(id=pa_id)
            if scene_id:
                pa_queryset = SceneScopeFilter.filter_queryset(
                    queryset=pa_queryset,
                    scene_id=scene_id,
                    resource_type=ResourceVisibilityType.PROCESS_APPLICATION,
                    pk_field="id",
                )
            rule_ids = RiskRule.objects.filter(pa_id__in=pa_queryset.values("id")).values("rule_id")
            nodes = nodes.filter(risk_id__in=Risk.objects.filter(rule_id__in=rule_ids).values("risk_id"))

        # 风险入口：按风险 ID 筛选
        if risk_id:
            nodes = nodes.filter(risk_id=risk_id)

        # 执行人筛选
        if operator:
            nodes = nodes.filter(operator__icontains=operator)

        # 任务名称筛选（快照字段，ORM 下沉）
        if task_name:
            nodes = nodes.filter(process_result__task_name__icontains=task_name)

        # 套餐名称筛选（快照字段，ORM 下沉；历史无快照记录由展示逻辑 rule→pa 兜底，筛选不覆盖）
        if pa_name:
            nodes = nodes.filter(process_result__pa_name__icontains=pa_name)

        # 触发方式筛选
        if trigger:
            nodes = nodes.filter(process_result__trigger=trigger)

        # 任务 ID 筛选（JSON 内 task_id 可能为 int/str，同时兼容）
        if task_id:
            task_id_cond = Q(process_result__task__task_id=task_id)
            try:
                task_id_cond |= Q(process_result__task__task_id=int(task_id))
            except (TypeError, ValueError):
                pass
            nodes = nodes.filter(task_id_cond)

        # 状态筛选：result → SOPS state 映射（state 为固定枚举字符串）
        if result_filter == "success":
            nodes = nodes.filter(process_result__status__state=SOPSTaskStatus.FINISHED.value)
        elif result_filter == "failed":
            nodes = nodes.filter(
                process_result__status__state__in=[s.value for s in SOPSTaskStatus.get_failed_status()]
            )
        elif result_filter == "running":
            nodes = nodes.filter(
                process_result__status__state__in=[
                    SOPSTaskStatus.CREATED.value,
                    SOPSTaskStatus.RUNNING.value,
                    SOPSTaskStatus.SUSPENDED.value,
                    SOPSTaskStatus.NODE_SUSPENDED.value,
                ]
            )
        elif result_filter == "unknown":
            nodes = nodes.filter(
                Q(process_result__status__isnull=True)
                | Q(process_result__status__state="")
                | Q(process_result__status__state__isnull=True)
            )

        # 排序
        order_field_map = {
            # start_time 为对外字段名；time 保留为兼容旧调用方的别名
            "start_time": "timestamp",
            "-start_time": "-timestamp",
            "time": "timestamp",
            "-time": "-timestamp",
            "operator": "operator",
            "-operator": "-operator",
        }
        # 耗时排序：未完成的记录 duration 为 null，统一置顶（nulls_first），
        # 并以开始时间作为次键 —— 对未完成记录而言「已耗时 = now - start_time」，
        # 同一时刻 now 相同，故组内按开始时间升序即等价于「已运行越久越靠前」
        duration_order_map = {
            "duration": [F("duration").asc(nulls_first=True), "-timestamp"],
            "-duration": [F("duration").desc(nulls_first=True), "timestamp"],
        }
        if order_by in duration_order_map:
            nodes = nodes.order_by(*duration_order_map[order_by])
        else:
            nodes = nodes.order_by(order_field_map.get(order_by, "-timestamp"))

        # 分页：count 先于切片（总数）；切片后仅组装当前页数据
        total = nodes.count()
        start = (page - 1) * page_size
        nodes = nodes[start : start + page_size]

        # 批量装配：风险信息 + 套餐信息
        risk_map = {
            risk["risk_id"]: risk
            for risk in Risk.objects.filter(risk_id__in=[n.risk_id for n in nodes]).values(
                "risk_id", "title", "status", "rule_id"
            )
        }
        rule_pa_map = {}
        for item in RiskRule.objects.filter(
            rule_id__in={r["rule_id"] for r in risk_map.values() if r["rule_id"]}
        ).values("rule_id", "pa_id"):
            rule_pa_map.setdefault(item["rule_id"], item["pa_id"])
        pa_name_map = {
            pa["id"]: pa["name"]
            for pa in ProcessApplication.objects.filter(id__in=set(rule_pa_map.values())).values("id", "name")
        }

        records = []
        for node in nodes:
            risk = risk_map.get(node.risk_id, {})
            process_result = node.process_result or {}
            # 套餐归属：优先取执行时快照（手动分派/规则改绑套餐均正确），历史节点无快照时走规则链路兜底
            pa_id_of_record = process_result.get("pa_id") or rule_pa_map.get(risk.get("rule_id"))
            state = (process_result.get("status") or {}).get("state", "")
            if state in SOPSTaskStatus.get_success_status():
                result = "success"
            elif state in SOPSTaskStatus.get_failed_status():
                result = "failed"
            elif state:
                result = "running"
            else:
                result = "unknown"

            sops_task_id = str((process_result.get("task") or {}).get("task_id", "") or "")
            current_task_name = process_result.get("task_name") or ""
            current_pa_name = process_result.get("pa_name") or pa_name_map.get(pa_id_of_record, "")
            current_trigger = process_result.get("trigger") or ""

            records.append(
                {
                    "id": node.id,
                    "risk_id": node.risk_id,
                    "risk_title": risk.get("title") or "",
                    "risk_status": risk.get("status") or "",
                    "pa_id": pa_id_of_record or 0,
                    "pa_name": current_pa_name,
                    "operator": node.operator,
                    # start_time 为记录创建（派单）时间；finish_time 取自 SOPS 任务结束时间，未结束为空串
                    "start_time": node.time,
                    "finish_time": (process_result.get("status") or {}).get("finish_time") or "",
                    "sops_task_id": sops_task_id,
                    "sops_state": state,
                    "result": result,
                    "task_name": current_task_name,
                    "trigger": current_trigger,
                    "duration": calc_task_duration(process_result.get("status") or {}),
                    "is_test": node.is_test,
                    "failure_hint": self._build_failure_hint(process_result) if result == "failed" else "",
                }
            )

        return {
            "count": total,
            "page": page,
            "page_size": page_size,
            "num_pages": (total + page_size - 1) // page_size,
            "results": records,
        }


class GetPAExecutionRecordDetail(ProcessApplicationMeta):
    """
    获取执行记录详情

    返回基本信息 + 参数 + 尝试记录，信息来源与执行记录列表一致（TicketNode）。
    """

    name = gettext_lazy("获取执行记录详情")
    audit_action = ActionEnum.LIST_PA

    class RequestSerializer(serializers.Serializer):
        id = serializers.CharField(label=gettext_lazy("执行记录ID"), required=True)

    def perform_request(self, validated_request_data):
        node_id = validated_request_data["id"]
        node = get_object_or_404(TicketNode, id=node_id)
        risk = Risk.objects.filter(risk_id=node.risk_id).first()
        process_result = node.process_result or {}

        # 套餐信息
        pa_id = process_result.get("pa_id") or 0
        pa_name = process_result.get("pa_name") or ""
        if not pa_name and risk:
            rule = RiskRule.objects.filter(rule_id=risk.rule_id).first()
            if rule:
                pa = ProcessApplication.objects.filter(id=rule.pa_id).first()
                pa_name = pa.name if pa else ""

        # 状态映射
        state = (process_result.get("status") or {}).get("state", "")
        if state in SOPSTaskStatus.get_success_status():
            result = "success"
        elif state in SOPSTaskStatus.get_failed_status():
            result = "failed"
        elif state:
            result = "running"
        else:
            result = "unknown"

        # 尝试记录（从 SOPS 状态中提取每次尝试）
        status_info = process_result.get("status") or {}
        attempts = self._extract_attempts(status_info)

        # 参数信息（从 Risk 获取）
        params = {}
        if risk:
            strategy = Strategy.objects.filter(strategy_id=risk.strategy_id).first()
            params = {
                "strategy_id": risk.strategy_id,
                "strategy_name": getattr(strategy, "strategy_name", "") if strategy else "",
                "risk_type": risk.event_type or [],
                "risk_evidence": risk.event_evidence or [],
                "risk_source": risk.event_source or "",
                "risk_description": risk.event_content or "",
                "risk_time": (
                    timezone.localtime(risk.event_time).strftime(api_settings.DATETIME_FORMAT)
                    if risk.event_time
                    else ""
                ),
                "operator": risk.operator or [],
                "raw_event_id": risk.raw_event_id or "",
            }

        return {
            # 基本信息
            "id": node.id,
            "task_name": process_result.get("task_name") or "",
            "pa_id": pa_id,
            "pa_name": pa_name,
            "trigger": process_result.get("trigger") or "",
            "operator": node.operator,
            # start_time 为记录创建（派单）时间；finish_time 取自 SOPS 任务结束时间，未结束为空串
            "start_time": node.time,
            "finish_time": status_info.get("finish_time") or "",
            "sops_task_id": str((process_result.get("task") or {}).get("task_id", "") or ""),
            "sops_state": state,
            "result": result,
            "duration": calc_task_duration(status_info),
            "is_test": node.is_test,
            "failure_hint": ListPAExecutionRecords._build_failure_hint(process_result) if result == "failed" else "",
            # 参数信息
            "params": params,
            # 尝试记录
            "attempts": attempts,
        }

    @staticmethod
    def _extract_attempts(status_info: dict) -> list:
        """从 SOPS 状态中提取每次尝试记录"""
        attempts = []
        children = status_info.get("children") or {}
        for node_id, child in children.items():
            attempts.append(
                {
                    "node_id": node_id,
                    "node_name": child.get("name") or "",
                    "state": child.get("state") or "",
                    "start_time": child.get("start_time") or "",
                    "end_time": child.get("finish_time") or "",
                    "duration": child.get("elapsed_time") or 0,
                    "error_message": child.get("error_message") or "",
                }
            )
        return attempts


class ToggleProcessApplication(ProcessApplicationMeta):
    name = gettext_lazy("启停处理套餐")
    RequestSerializer = ToggleProcessApplicationReqSerializer
    audit_action = ActionEnum.EDIT_PA

    def perform_request(self, validated_request_data):
        pa = get_object_or_404(ProcessApplication, id=validated_request_data["id"])
        _reject_builtin_edit(pa)
        pa.is_enabled = validated_request_data["is_enabled"]
        pa.save(update_fields=["is_enabled"])


class ApproveBuildInFields(ProcessApplicationMeta):
    name = gettext_lazy("审批内置字段")

    def perform_request(self, validated_request_data):
        return [
            {"id": getattr(ApproveTicketFields, f).key, "name": getattr(ApproveTicketFields, f).key}
            for f in dir(ApproveTicketFields)
            if not f.startswith("_") and f not in ["RISK_LEVEL", "DESCRIPTION"]
        ]

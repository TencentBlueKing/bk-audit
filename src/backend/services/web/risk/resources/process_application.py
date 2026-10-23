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
from services.web.risk.bksec.service import FAILURE_HINT_MAX_LEN, iter_status_nodes
from services.web.risk.constants import ApproveTicketFields, RiskStatus
from services.web.risk.models import ProcessApplication, Risk, RiskRule, TicketNode
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
from services.web.risk.utils import (
    calc_task_duration,
    calc_task_finish_time,
    extract_attempt_records,
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
        has_execution_records = validated_request_data.get("has_execution_records")
        process_applications = ProcessApplication.objects.all()
        process_applications = SceneScopeFilter.filter_queryset(
            queryset=process_applications,
            scene_id=scene_id,
            resource_type=ResourceVisibilityType.PROCESS_APPLICATION,
            pk_field="id",
        )
        # 按「是否有执行记录」过滤：执行记录即 action=AutoProcess 的 TicketNode（与执行记录列表口径一致，含测试单）
        if has_execution_records is not None:
            pa_ids = {
                int(pa_id)
                for pa_id in TicketNode.objects.filter(action="AutoProcess")
                .exclude(process_result__pa_id__isnull=True)
                .values_list("process_result__pa_id", flat=True)
                if str(pa_id).isdigit()
            }
            process_applications = (
                process_applications.filter(id__in=pa_ids)
                if has_execution_records
                else process_applications.exclude(id__in=pa_ids)
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
        """失败提示：优先读写入点已落库的文本，为空时从当前状态里兜底取首个节点错误（只读，不回源）"""
        hint = process_result.get("failure_hint") or ""
        if hint:
            return hint
        for child in iter_status_nodes(process_result.get("status") or {}):
            error_message = str(child.get("error_message") or "").strip()
            if error_message:
                return error_message[:FAILURE_HINT_MAX_LEN]
        return ""

    @staticmethod
    def _split_multi(raw: str) -> list:
        """多选参数归一化：逗号分隔拆列表，去空白，保序去重"""
        values = []
        for value in str(raw or "").split(","):
            value = value.strip()
            if value and value not in values:
                values.append(value)
        return values

    @staticmethod
    def _filter_by_record_id(nodes, record_id: str):
        """执行记录 ID 精确过滤（字符串比较，与 task_id 筛选同风格）；空值不过滤"""
        return nodes.filter(id=record_id) if record_id else nodes

    @staticmethod
    def _pa_filter_q(pa_ids: list) -> Q:
        """套餐归属过滤条件：与展示口径一致（快照优先，无快照走规则链路兜底）

        - 执行时快照 process_result.pa_id 优先：覆盖手动分派 / 测试单 / 规则改绑后的历史记录
        - 无快照的历史节点走规则链路：按 (rule_id, rule_version) 精确命中；
          风险无 rule_version 时按规则最新版本归属（与展示兜底一致）
        """
        # 快照命中：pa_id 写入为 int，JSON 路径查询类型敏感，兼容 str（同 task_id 筛选）
        snapshot_q = Q()
        for value in pa_ids:
            snapshot_q |= Q(process_result__pa_id=value) | Q(process_result__pa_id=str(value))
        # 无快照判定：与展示的 `process_result.get("pa_id") or 兜底` 语义一致（缺失/None/0/空串）
        no_snapshot_q = Q(process_result__pa_id__isnull=True) | Q(process_result__pa_id=0) | Q(process_result__pa_id="")
        # 规则链路：目标套餐当前/历史版本绑定的 (rule_id, version) 精确匹配
        legacy_rule_q = Q()
        for item in (
            RiskRule.objects.filter(pa_id__in=pa_ids).exclude(rule_id__isnull=True).values("rule_id", "version")
        ):
            if item["version"] is None:
                legacy_rule_q |= Q(rule_id=item["rule_id"], rule_version__isnull=True)
            else:
                legacy_rule_q |= Q(rule_id=item["rule_id"], rule_version=item["version"])
        # 风险无 rule_version：按规则最新版本归属（升序遍历，最后写入即最新版本）
        latest_pa = {}
        for item in RiskRule.objects.exclude(rule_id__isnull=True).order_by("version").values("rule_id", "pa_id"):
            latest_pa[item["rule_id"]] = item["pa_id"]
        for rule_id, pa_of_latest in latest_pa.items():
            if pa_of_latest in pa_ids:
                legacy_rule_q |= Q(rule_id=rule_id, rule_version__isnull=True)
        if not legacy_rule_q:
            return snapshot_q
        legacy_q = no_snapshot_q & Q(risk_id__in=Risk.objects.filter(legacy_rule_q).values("risk_id"))
        return snapshot_q | legacy_q

    class RequestSerializer(serializers.Serializer):
        id = serializers.CharField(
            label=gettext_lazy("执行记录ID"),
            required=False,
            allow_blank=True,
            help_text=gettext_lazy(
                "按执行记录唯一 ID（TicketNode.id，即响应中的 id 字段）精确过滤，留空不过滤；" "注意与 task_id（SOPS 任务 ID，响应中的 sops_task_id）区分"
            ),
        )
        pa_id = serializers.IntegerField(label=gettext_lazy("套餐ID"), required=False, allow_null=True)
        risk_id = serializers.CharField(label=gettext_lazy("风险ID"), required=False, allow_blank=True, allow_null=True)
        scene_id = serializers.IntegerField(label=gettext_lazy("场景ID"), required=False, allow_null=True)
        task_id = serializers.CharField(label=gettext_lazy("任务ID"), required=False, allow_blank=True)
        task_name = serializers.CharField(label=gettext_lazy("任务名称"), required=False, allow_blank=True)
        pa_name = serializers.CharField(
            label=gettext_lazy("套餐名称"),
            required=False,
            allow_blank=True,
            help_text=gettext_lazy("精确匹配，支持多选，逗号分隔（如 套餐A,套餐B），任一命中即返回"),
        )
        trigger = serializers.CharField(
            label=gettext_lazy("触发方式"),
            required=False,
            allow_blank=True,
            help_text=gettext_lazy("支持多选，逗号分隔（如 auto,test），任一命中即返回"),
        )
        result = serializers.CharField(
            label=gettext_lazy("状态"),
            required=False,
            allow_blank=True,
            help_text=gettext_lazy("支持多选，逗号分隔（如 failed,running），任一命中即返回"),
        )
        operator = serializers.CharField(label=gettext_lazy("执行人"), required=False, allow_blank=True)
        order_by = serializers.CharField(
            label=gettext_lazy("排序字段"), required=False, allow_blank=True, default="-start_time"
        )
        page = serializers.IntegerField(label=gettext_lazy("页码"), required=False, min_value=1, default=1)
        page_size = serializers.IntegerField(
            label=gettext_lazy("单页数量"), required=False, min_value=1, max_value=200, default=20
        )

    def perform_request(self, validated_request_data):
        record_id = (validated_request_data.get("id") or "").strip()
        pa_id = validated_request_data.get("pa_id")
        risk_id = validated_request_data.get("risk_id")
        scene_id = validated_request_data.get("scene_id")
        task_id = validated_request_data.get("task_id", "").strip()
        task_name = validated_request_data.get("task_name", "").strip()
        pa_name_values = self._split_multi(validated_request_data.get("pa_name", ""))
        trigger_values = self._split_multi(validated_request_data.get("trigger", ""))
        result_values = self._split_multi(validated_request_data.get("result", ""))
        operator = validated_request_data.get("operator", "").strip()
        order_by = validated_request_data.get("order_by", "-start_time").strip()
        page = validated_request_data.get("page", 1)
        page_size = validated_request_data.get("page_size", 20)

        # 处理套餐执行记录包含测试单（is_test 不过滤）
        nodes = TicketNode.objects.filter(action="AutoProcess")

        # 执行记录 ID 精确过滤（TicketNode.id 为 UUID，格式校验在 RequestSerializer.validate_id）
        nodes = self._filter_by_record_id(nodes, record_id)

        # 套餐筛选 / 场景范围：归属口径与展示一致——执行时快照优先，无快照走规则（含版本）链路兜底
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
            nodes = nodes.filter(self._pa_filter_q(list(pa_queryset.values_list("id", flat=True))))

        # 风险入口：按风险 ID 筛选
        if risk_id:
            nodes = nodes.filter(risk_id=risk_id)

        # 执行人筛选
        if operator:
            nodes = nodes.filter(operator__icontains=operator)

        # 任务名称筛选（快照字段，ORM 下沉）
        if task_name:
            nodes = nodes.filter(process_result__task_name__icontains=task_name)

        # 套餐名称筛选（精确匹配，支持多选，任一命中；快照字段，ORM 下沉；
        # 历史无快照记录由展示逻辑 rule→pa 兜底，筛选不覆盖）
        if pa_name_values:
            nodes = nodes.filter(process_result__pa_name__in=pa_name_values)

        # 触发方式筛选（支持多选，任一命中）
        if trigger_values:
            nodes = nodes.filter(process_result__trigger__in=trigger_values)

        # 任务 ID 筛选（JSON 内 task_id 可能为 int/str，同时兼容）
        if task_id:
            task_id_cond = Q(process_result__task__task_id=task_id)
            try:
                task_id_cond |= Q(process_result__task__task_id=int(task_id))
            except (TypeError, ValueError):
                pass
            nodes = nodes.filter(task_id_cond)

        # 状态筛选（支持多选，任一命中）：result → SOPS state 映射（state 为固定枚举字符串）
        result_q = Q()
        for value in result_values:
            if value == "success":
                result_q |= Q(process_result__status__state=SOPSTaskStatus.FINISHED.value)
            elif value == "failed":
                result_q |= Q(process_result__status__state__in=[s.value for s in SOPSTaskStatus.get_failed_status()])
            elif value == "running":
                result_q |= Q(
                    process_result__status__state__in=[
                        SOPSTaskStatus.CREATED.value,
                        SOPSTaskStatus.RUNNING.value,
                        SOPSTaskStatus.SUSPENDED.value,
                        SOPSTaskStatus.NODE_SUSPENDED.value,
                    ]
                )
            elif value == "unknown":
                result_q |= (
                    Q(process_result__status__isnull=True)
                    | Q(process_result__status__state="")
                    | Q(process_result__status__state__isnull=True)
                )
        if result_values:
            nodes = nodes.filter(result_q)

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
                "risk_id", "title", "status", "risk_level", "rule_id", "rule_version"
            )
        }
        # 规则 → 套餐映射按 (rule_id, version) 精确匹配（规则改绑会出新版本）；
        # 另记最新版本，供风险无 rule_version 的历史记录兜底
        rule_pa_map = {}
        rule_latest_pa = {}
        for item in (
            RiskRule.objects.filter(rule_id__in={r["rule_id"] for r in risk_map.values() if r["rule_id"]})
            .order_by("version")
            .values("rule_id", "version", "pa_id")
        ):
            rule_pa_map[(item["rule_id"], item["version"])] = item["pa_id"]
            rule_latest_pa[item["rule_id"]] = item["pa_id"]
        pa_name_map = {
            pa["id"]: pa["name"]
            for pa in ProcessApplication.objects.filter(id__in=set(rule_pa_map.values())).values("id", "name")
        }

        records = []
        for node in nodes:
            risk = risk_map.get(node.risk_id, {})
            process_result = node.process_result or {}
            # 套餐归属：优先取执行时快照（手动分派/规则改绑套餐均正确），历史节点无快照时按
            # (rule_id, rule_version) 精确兜底，风险无版本时按规则最新版本兜底
            pa_id_of_record = process_result.get("pa_id")
            if not pa_id_of_record:
                pa_id_of_record = rule_pa_map.get((risk.get("rule_id"), risk.get("rule_version")))
                if pa_id_of_record is None and risk.get("rule_id") and risk.get("rule_version") is None:
                    pa_id_of_record = rule_latest_pa.get(risk.get("rule_id"))
            state = (process_result.get("status") or {}).get("state", "")
            if state in SOPSTaskStatus.get_success_status():
                result = "success"
            elif state in SOPSTaskStatus.get_failed_status():
                result = "failed"
            elif state:
                result = "running"
            else:
                result = "unknown"

            task_info = process_result.get("task") or {}
            sops_task_id = str(task_info.get("task_id", "") or "")
            sops_task_url = str(task_info.get("task_url", "") or "")
            current_task_name = process_result.get("task_name") or ""
            current_pa_name = process_result.get("pa_name") or pa_name_map.get(pa_id_of_record, "")
            current_trigger = process_result.get("trigger") or ""

            records.append(
                {
                    "id": node.id,
                    "risk_id": node.risk_id,
                    "risk_title": risk.get("title") or "",
                    "risk_status": risk.get("status") or "",
                    "risk_level": risk.get("risk_level") or "",
                    "pa_id": pa_id_of_record or 0,
                    "pa_name": current_pa_name,
                    "operator": node.operator,
                    # start_time 为记录创建（派单）时间；finish_time 取自 SOPS 任务结束时间，未结束为空串
                    "start_time": node.time,
                    "finish_time": calc_task_finish_time(process_result.get("status") or {}),
                    "sops_task_id": sops_task_id,
                    "sops_task_url": sops_task_url,
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

        # 套餐信息：快照优先，历史节点无快照时按 (rule_id, rule_version) 兜底（与列表同口径）
        pa_id = process_result.get("pa_id") or 0
        pa_name = process_result.get("pa_name") or ""
        if risk and (not pa_id or not pa_name):
            rule = None
            if risk.rule_id:
                rule = RiskRule.objects.filter(rule_id=risk.rule_id, version=risk.rule_version).first()
                if not rule and risk.rule_version is None:
                    rule = RiskRule.objects.filter(rule_id=risk.rule_id).order_by("-version").first()
            if rule:
                pa = ProcessApplication.objects.filter(id=rule.pa_id).first()
                pa_id = pa_id or rule.pa_id or 0
                pa_name = pa_name or (pa.name if pa else "")

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
        attempts = extract_attempt_records(status_info)
        # 重试记录（RetryAutoProcess 重试前写入的快照，仅 append 不覆盖）
        retry_history = process_result.get("retry_history") or []

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
            "finish_time": calc_task_finish_time(status_info),
            "sops_task_id": str((process_result.get("task") or {}).get("task_id", "") or ""),
            "sops_task_url": str((process_result.get("task") or {}).get("task_url", "") or ""),
            "sops_state": state,
            "result": result,
            "duration": calc_task_duration(status_info),
            "is_test": node.is_test,
            "failure_hint": ListPAExecutionRecords._build_failure_hint(process_result) if result == "failed" else "",
            # 风险单关联
            "risk_id": node.risk_id,
            "risk_title": (risk.title or "") if risk else "",
            "risk_status": (risk.status or "") if risk else "",
            "risk_level": (risk.risk_level or "") if risk else "",
            # 参数信息
            "params": params,
            # 重试记录
            "retry_count": len(retry_history),
            "retry_history": retry_history,
            # 尝试记录
            "attempts": attempts,
        }


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

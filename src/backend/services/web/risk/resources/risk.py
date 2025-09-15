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
import json
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Type

from bk_resource import CacheResource, api, resource
from bk_resource.settings import bk_resource_settings
from bk_resource.utils.cache import CacheTypeItem
from bk_resource.utils.common_utils import ignored
from django.conf import settings
from django.db import transaction
from django.db.models import Count, Q, QuerySet
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext, gettext_lazy
from rest_framework.settings import api_settings

from apps.audit.resources import AuditMixinResource
from apps.itsm.constants import TicketOperate, TicketStatus
from apps.meta.models import Tag
from apps.permission.handlers.actions import ActionEnum
from apps.permission.handlers.drf import wrapper_permission_field
from apps.permission.handlers.resource_types import ResourceEnum
from apps.sops.constants import SOPSTaskOperation, SOPSTaskStatus
from core.exceptions import RiskStatusInvalid
from core.exporter.constants import ExportField
from core.models import get_request_username
from core.utils.data import choices_to_dict, data2string, preserved_order_sort
from core.utils.page import paginate_queryset
from core.utils.time import mstimestamp_to_date_string
from core.utils.tools import get_app_info
from services.web.risk.constants import (
    EVENT_EXPORT_FIELD_PREFIX,
    RISK_EXPORT_FILE_NAME_TMP,
    RISK_LEVEL_ORDER_FIELD,
    RISK_SHOW_FIELDS,
    RiskExportField,
    RiskFields,
    RiskLabel,
    RiskStatus,
    RiskViewType,
    TicketNodeStatus,
)
from services.web.risk.exceptions import ExportRiskNoPermission
from services.web.risk.handlers.risk_export import MultiSheetRiskExporterXlsx
from services.web.risk.handlers.ticket import (
    AutoProcess,
    CloseRisk,
    CustomProcess,
    ForApprove,
    MisReport,
    ReOpen,
    ReOpenMisReport,
    TransOperator,
)
from services.web.risk.models import (
    ProcessApplication,
    Risk,
    RiskAuditInstance,
    RiskExperience,
    TicketNode,
)
from services.web.risk.serializers import (
    BulkCustomTransRiskReqSerializer,
    CustomAutoProcessReqSerializer,
    CustomCloseRiskRequestSerializer,
    CustomTransRiskReqSerializer,
    ForceRevokeApproveTicketReqSerializer,
    ForceRevokeAutoProcessReqSerializer,
    GetRiskFieldsByStrategyRequestSerializer,
    GetRiskFieldsByStrategyResponseSerializer,
    ListRiskMetaRequestSerializer,
    ListRiskRequestSerializer,
    ListRiskResponseSerializer,
    ListRiskStrategyRespSerializer,
    ListRiskTagsRespSerializer,
    ReopenRiskReqSerializer,
    RetrieveRiskStrategyInfoResponseSerializer,
    RetryAutoProcessReqSerializer,
    RiskExportReqSerializer,
    RiskInfoSerializer,
    TicketNodeSerializer,
    UpdateRiskLabelReqSerializer,
)
from services.web.risk.tasks import process_one_risk, sync_auto_result
from services.web.strategy_v2.constants import RiskLevel
from services.web.strategy_v2.models import Strategy, StrategyTag


class RiskMeta(AuditMixinResource, abc.ABC):
    tags = ["Risk"]
    audit_resource_type = ResourceEnum.RISK


class RetrieveRisk(RiskMeta):
    name = gettext_lazy("获取风险详情")
    audit_action = ActionEnum.LIST_RISK

    def perform_request(self, validated_request_data):
        risk = get_object_or_404(Risk, risk_id=validated_request_data["risk_id"])
        self.add_audit_instance_to_context(instance=RiskAuditInstance(risk))
        data = RiskInfoSerializer(risk).data
        data = wrapper_permission_field(
            data, actions=[ActionEnum.EDIT_RISK], id_field=lambda risk: risk["risk_id"], many=False
        )
        risk = data[0]
        nodes = TicketNode.objects.filter(risk_id=risk["risk_id"]).order_by("timestamp")
        risk["ticket_history"] = TicketNodeSerializer(nodes, many=True).data
        return risk


class RetrieveRiskStrategyInfo(RiskMeta):
    name = gettext_lazy("获取风险策略信息")
    ResponseSerializer = RetrieveRiskStrategyInfoResponseSerializer

    def perform_request(self, validated_request_data):
        risk: Risk = get_object_or_404(Risk, risk_id=validated_request_data["risk_id"])
        strategy = Strategy.objects.filter(strategy_id=risk.strategy_id).first()
        return strategy or {}


class RetrieveRiskAPIGW(RetrieveRisk):
    audit_action = None

    def perform_request(self, validated_request_data):
        get_app_info()
        risk = get_object_or_404(Risk, risk_id=validated_request_data["risk_id"])
        return RiskInfoSerializer(risk).data


class ListRisk(RiskMeta):
    name = gettext_lazy("获取风险列表")
    RequestSerializer = ListRiskRequestSerializer
    bind_request = True
    audit_action = ActionEnum.LIST_RISK

    def perform_request(self, validated_request_data):
        # 获取请求
        request = validated_request_data.pop("_request")
        # 获取风险
        order_field = validated_request_data.pop("order_field", "-event_time")
        base_qs = self.load_risks(validated_request_data)
        risks = self._apply_ordering(base_qs, order_field).only("pk")
        # 分页
        paged_risks, page = paginate_queryset(queryset=risks, request=request, base_queryset=Risk.annotated_queryset())
        # 预加载策略标签
        paged_risks: QuerySet[Risk] = self._apply_ordering(Risk.prefetch_strategy_tags(paged_risks), order_field)
        # 获取关联的经验
        experiences = {
            e["risk_id"]: e["count"]
            for e in RiskExperience.objects.filter(risk_id__in=paged_risks.values("risk_id"))
            .values("risk_id")
            .order_by("risk_id")
            .annotate(count=Count("risk_id"))
        }
        for risk in paged_risks:
            setattr(risk, "experiences", experiences.get(risk.risk_id, 0))
        # 响应
        return page.get_paginated_response(data=ListRiskResponseSerializer(instance=paged_risks, many=True).data)

    def _apply_ordering(self, queryset: QuerySet["Risk"], order_field: str) -> QuerySet["Risk"]:
        """Apply ordering, including custom order for strategy risk level.

        - Use ORM order_by for general fields
        - For strategy__risk_level, use custom numeric order: asc => LOW<MIDDLE<HIGH, desc => HIGH>MIDDLE>LOW
        """
        if not order_field:
            return queryset
        field = order_field.lstrip("-")
        if field == RISK_LEVEL_ORDER_FIELD:
            return preserved_order_sort(
                queryset,
                ordering_field=order_field,
                value_list=[RiskLevel.LOW, RiskLevel.MIDDLE, RiskLevel.HIGH],
                extra_order_by=["-event_time"],
            )
        return queryset.order_by(order_field)

    def load_risks(self, validated_request_data: dict) -> QuerySet["Risk"]:
        # 构造表达式
        q = Q()
        # 风险等级
        risk_level = validated_request_data.pop("risk_level", None)
        if risk_level:
            q &= Q(strategy_id__in=Strategy.objects.filter(risk_level__in=risk_level).values("strategy_id"))

        # 标签筛选条件
        if tag_filter := validated_request_data.pop("tag_objs__in", None):
            strategy_ids = StrategyTag.objects.filter(tag_id__in=tag_filter).values_list('strategy_id', flat=True)
            q &= Q(strategy_id__in=strategy_ids)

        for key, val in validated_request_data.items():
            if not val:
                continue
            # 普通匹配，针对单值匹配
            _q = Q()
            for i in val:
                _q |= Q(**{key: i})
            q &= _q
        # 获取有权限且符合表达式的
        return Risk.load_authed_risks(action=ActionEnum.LIST_RISK).filter(q).distinct()


class ListMineRisk(ListRisk):
    name = gettext_lazy("获取待我处理的风险列表")

    def load_risks(self, validated_request_data):
        queryset = super().load_risks(validated_request_data)
        queryset = queryset.filter(Q(current_operator__contains=get_request_username()))
        return queryset


class ListNoticingRisk(ListRisk):
    name = gettext_lazy("获取我关注的风险列表")

    def load_risks(self, validated_request_data):
        queryset = super().load_risks(validated_request_data)
        queryset = queryset.filter(Q(notice_users__contains=get_request_username()))
        return queryset


class ListRiskFields(RiskMeta):
    name = gettext_lazy("获取风险字段")

    def perform_request(self, validated_request_data):
        return [{"id": f.name, "name": str(f.verbose_name)} for f in Risk._meta.fields if f.name in RISK_SHOW_FIELDS]


class UpdateRiskLabel(RiskMeta):
    name = gettext_lazy("更新风险标记")
    RequestSerializer = UpdateRiskLabelReqSerializer
    ResponseSerializer = RiskInfoSerializer
    audit_action = ActionEnum.EDIT_RISK

    @transaction.atomic()
    def perform_request(self, validated_request_data):
        # 初始化风险
        risk = get_object_or_404(Risk, risk_id=validated_request_data["risk_id"])
        origin_data = RiskInfoSerializer(risk).data
        # 确认要变更的类型
        new_risk_label = validated_request_data["risk_label"]
        # 重开需要登记重开，并转单
        if new_risk_label == RiskLabel.NORMAL:
            ReOpenMisReport(risk_id=risk.risk_id, operator=get_request_username()).run(
                new_operators=validated_request_data.get("new_operators", [])
            )
        # 误报需要登记误报，并关单
        elif new_risk_label == RiskLabel.MISREPORT:
            MisReport(risk_id=risk.risk_id, operator=get_request_username()).run(
                description=validated_request_data["description"],
                revoke_process=validated_request_data["revoke_process"],
            )
        risk.refresh_from_db()
        setattr(risk, "instance_origin_data", origin_data)
        self.add_audit_instance_to_context(instance=RiskAuditInstance(risk))
        return risk


class RiskStatusCommon(RiskMeta):
    name = gettext_lazy("获取风险状态类型")

    def perform_request(self, validated_request_data):
        return choices_to_dict(RiskStatus)


class ListRiskBase(RiskMeta, CacheResource, abc.ABC):
    RequestSerializer = ListRiskMetaRequestSerializer
    many_response_data = True
    # 风险视图类型与风险类的映射
    risk_cls_map: Dict[str, Type[ListRisk]] = {
        RiskViewType.ALL.value: ListRisk,
        RiskViewType.TODO.value: ListMineRisk,
        RiskViewType.WATCH.value: ListNoticingRisk,
    }

    @classmethod
    def load_risk_view_type_risks(cls, risk_view_type: str, filter_dict: dict) -> QuerySet[Risk]:
        """
        加载指定风险视图下有权限的风险
        """

        risk_cls = cls.risk_cls_map.get(risk_view_type)
        if not risk_cls:
            return Risk.objects.none()
        return risk_cls().load_risks(filter_dict)


class ListRiskTags(ListRiskBase):
    """
    获取用户的风险标签列表，支持用户在不同风险视图下的数据展示
    注意：该接口的筛选条件主要需要风险列表的事件发生时间，当该参数变化时需要重新查询
    """

    name = gettext_lazy("获取风险的标签")
    ResponseSerializer = ListRiskTagsRespSerializer
    cache_type = CacheTypeItem(key="ListRiskTags", timeout=60, user_related=True)

    def perform_request(self, validated_request_data):
        tags = Tag.objects.all().only("tag_id", "tag_name")
        risk_view_type: str = validated_request_data.pop("risk_view_type", None)
        if not risk_view_type:
            return tags
        risk_ids = set(
            self.load_risk_view_type_risks(risk_view_type, validated_request_data).values_list("risk_id", flat=True)
        )
        if not risk_ids:
            return []

        # 1. 获取这些风险对应的策略ID
        strategy_ids = set(Risk.objects.filter(risk_id__in=risk_ids).values_list("strategy_id", flat=True))

        # 2. 查询这些策略关联的标签ID
        tag_ids = set(StrategyTag.objects.filter(strategy_id__in=strategy_ids).values_list("tag_id", flat=True))

        # 3. 返回对应的标签
        return tags.filter(tag_id__in=tag_ids)


class ListRiskStrategy(ListRiskBase):
    """
    获取风险的策略，支持不同风险视图下的数据展示
    注意：该接口的筛选条件主要需要风险列表的事件发生时间，当该参数变化时需要重新查询
    """

    name = gettext_lazy("获取风险的策略")
    ResponseSerializer = ListRiskStrategyRespSerializer
    cache_type = CacheTypeItem(key="ListRiskStrategy", timeout=60, user_related=True)

    def perform_request(self, validated_request_data):
        strategies: QuerySet[Strategy] = Strategy.objects.all().only("strategy_id", "strategy_name")
        risk_view_type: str = validated_request_data.pop("risk_view_type", None)
        if not risk_view_type:
            return strategies
        strategy_ids = set(
            self.load_risk_view_type_risks(risk_view_type, validated_request_data)
            .values_list("strategy_id", flat=True)
            .distinct()
        )
        if not strategy_ids:
            return []
        return strategies.filter(strategy_id__in=strategy_ids)


class CustomCloseRisk(RiskMeta):
    name = gettext_lazy("人工关单")
    RequestSerializer = CustomCloseRiskRequestSerializer
    audit_action = ActionEnum.EDIT_RISK

    @transaction.atomic()
    def perform_request(self, validated_request_data):
        username = get_request_username()
        risk = get_object_or_404(Risk, risk_id=validated_request_data["risk_id"])
        origin_data = RiskInfoSerializer(risk).data
        CustomProcess(risk_id=risk.risk_id, operator=username).run(
            custom_action=CloseRisk.__name__, description=validated_request_data["description"]
        )
        CloseRisk(risk_id=risk.risk_id, operator=username).run(description=gettext("%s 人工关单") % username)
        setattr(risk, "instance_origin_data", origin_data)
        self.add_audit_instance_to_context(instance=RiskAuditInstance(risk))


class CustomTransRisk(RiskMeta):
    name = gettext_lazy("人工转单")
    RequestSerializer = CustomTransRiskReqSerializer
    audit_action = ActionEnum.EDIT_RISK

    @transaction.atomic()
    def perform_request(self, validated_request_data):
        risk = get_object_or_404(Risk, risk_id=validated_request_data["risk_id"])
        if risk.status != RiskStatus.AWAIT_PROCESS.value:
            raise RiskStatusInvalid(message=RiskStatusInvalid.MESSAGE % risk.status)
        origin_data = RiskInfoSerializer(risk).data
        # 使用当前用户 or 并发请求时透传的用户
        operator = get_request_username(validated_request_data.get("_request", None))
        TransOperator(risk_id=risk.risk_id, operator=operator).run(
            new_operators=validated_request_data["new_operators"], description=validated_request_data["description"]
        )
        setattr(risk, "instance_origin_data", origin_data)
        self.add_audit_instance_to_context(instance=RiskAuditInstance(risk))


class BulkCustomTransRisk(RiskMeta):
    name = gettext_lazy("批量人工转单")
    RequestSerializer = BulkCustomTransRiskReqSerializer

    def perform_request(self, validated_request_data):
        bulk_req_params = [
            {
                "risk_id": risk_id,
                "new_operators": validated_request_data["new_operators"],
                "description": validated_request_data["description"],
            }
            for risk_id in validated_request_data["risk_ids"]
        ]
        CustomTransRisk().bulk_request(bulk_req_params, ignore_exceptions=True)


class CustomAutoProcess(RiskMeta):
    name = gettext_lazy("人工执行处理套餐")
    RequestSerializer = CustomAutoProcessReqSerializer
    audit_action = ActionEnum.EDIT_RISK

    @transaction.atomic()
    def perform_request(self, validated_request_data):
        username = get_request_username()
        risk = get_object_or_404(Risk, risk_id=validated_request_data["risk_id"])
        origin_data = RiskInfoSerializer(risk).data
        # 获取处理套餐
        pa = get_object_or_404(ProcessApplication, id=validated_request_data["pa_id"])
        # 记录执行
        CustomProcess(risk_id=risk.risk_id, operator=username).run(
            custom_action=AutoProcess.__name__,
            pa_id=validated_request_data["pa_id"],
            pa_params=validated_request_data["pa_params"],
            auto_close_risk=validated_request_data["auto_close_risk"],
        )
        # 处理节点
        if pa.need_approve:
            processor = ForApprove
        else:
            processor = AutoProcess
        processor(risk_id=risk.risk_id, operator=username).run(
            pa_config={
                "pa_id": validated_request_data["pa_id"],
                "pa_params": validated_request_data["pa_params"],
                "auto_close_risk": validated_request_data["auto_close_risk"],
            }
        )
        setattr(risk, "instance_origin_data", origin_data)
        self.add_audit_instance_to_context(instance=RiskAuditInstance(risk))


class ForceRevokeApproveTicket(RiskMeta):
    name = gettext_lazy("强制撤销审批单据")
    RequestSerializer = ForceRevokeApproveTicketReqSerializer
    audit_action = ActionEnum.EDIT_RISK

    def perform_request(self, validated_request_data):
        risk = get_object_or_404(Risk, risk_id=validated_request_data["risk_id"])
        origin_data = RiskInfoSerializer(risk).data
        node = get_object_or_404(TicketNode, risk_id=risk.risk_id, id=validated_request_data["node_id"])
        if node.action != ForApprove.__name__:
            raise RiskStatusInvalid(message=gettext("节点类型异常 => %s") % node.action)
        sn = node.process_result["ticket"]["sn"]
        # 判断单据状态
        status = api.bk_itsm.ticket_approve_result(sn=[sn])[0]
        if status["current_status"] in TicketStatus.get_finished_status():
            sync_auto_result(node_id=node.id)
            return
        # 关单
        api.bk_itsm.operate_ticket(
            sn=sn,
            operator=bk_resource_settings.PLATFORM_AUTH_ACCESS_USERNAME,
            action_type=TicketOperate.WITHDRAW,
            action_message=str(TicketOperate.WITHDRAW.label),
        )
        sync_auto_result(node_id=node.id)
        setattr(risk, "instance_origin_data", origin_data)
        self.add_audit_instance_to_context(instance=RiskAuditInstance(risk))


class ForceRevokeAutoProcess(RiskMeta):
    name = gettext_lazy("强制终止处理套餐")
    RequestSerializer = ForceRevokeAutoProcessReqSerializer
    audit_action = ActionEnum.EDIT_RISK

    def perform_request(self, validated_request_data):
        risk = get_object_or_404(Risk, risk_id=validated_request_data["risk_id"])
        origin_data = RiskInfoSerializer(risk).data
        node = get_object_or_404(TicketNode, risk_id=risk.risk_id, id=validated_request_data["node_id"])
        if node.action != AutoProcess.__name__:
            raise RiskStatusInvalid(message=gettext("节点类型异常 => %s") % node.action)
        task_id = node.process_result["task"]["task_id"]
        # 判断套餐状态
        status = api.bk_sops.get_task_status(task_id=task_id, bk_biz_id=settings.DEFAULT_BK_BIZ_ID)
        if status["state"] in SOPSTaskStatus.get_finished_status():
            sync_auto_result(node_id=node.id)
            return
        # 终止套餐
        api.bk_sops.operate_task(bk_biz_id=settings.DEFAULT_BK_BIZ_ID, task_id=task_id, action=SOPSTaskOperation.REVOKE)
        sync_auto_result(node_id=node.id)
        setattr(risk, "instance_origin_data", origin_data)
        self.add_audit_instance_to_context(instance=RiskAuditInstance(risk))


class RetryAutoProcess(RiskMeta):
    name = gettext_lazy("重试处理套餐")
    RequestSerializer = RetryAutoProcessReqSerializer

    def perform_request(self, validated_request_data):
        risk = get_object_or_404(Risk, risk_id=validated_request_data["risk_id"])
        node = get_object_or_404(TicketNode, risk_id=risk.risk_id, id=validated_request_data["node_id"])
        task_id = node.process_result.get("task", {}).get("task_id", "")
        # 获取节点状态
        status = api.bk_sops.get_task_status(task_id=task_id, bk_biz_id=settings.DEFAULT_BK_BIZ_ID)
        # 对每个失败的节点，获取节点输入并重试
        for item in status["children"].values():
            if item["state"] != SOPSTaskStatus.FAILED:
                continue
            io_data = api.bk_sops.get_node_data(
                task_id=task_id, bk_biz_id=settings.DEFAULT_BK_BIZ_ID, node_id=item["id"]
            )
            api.bk_sops.operate_node(
                task_id=task_id,
                bk_biz_id=settings.DEFAULT_BK_BIZ_ID,
                node_id=item["id"],
                action=SOPSTaskOperation.RETRY,
                inputs=io_data["inputs"],
            )
        with transaction.atomic():
            node.status = TicketNodeStatus.RUNNING
            node.process_result["status"]["state"] = SOPSTaskStatus.RUNNING
            node.save(update_fields=["status", "process_result"])
            # 若最后一个节点为处理套餐节点，则更新状态为自动处理中，并清理处理人
            if risk.last_history.id == node.id:
                risk.status = RiskStatus.AUTO_PROCESS
                risk.current_operator = []
                risk.save(update_fields=["status", "current_operator"])
        # 更新节点信息
        sync_auto_result.apply_async(countdown=60, kwargs={"node_id": node.id})


class ReopenRisk(RiskMeta):
    name = gettext_lazy("重开单据")
    RequestSerializer = ReopenRiskReqSerializer
    audit_action = ActionEnum.EDIT_RISK

    def perform_request(self, validated_request_data):
        risk = get_object_or_404(Risk, risk_id=validated_request_data["risk_id"])
        origin_data = RiskInfoSerializer(risk).data
        ReOpen(risk_id=risk.risk_id, operator=get_request_username()).run(
            new_operators=validated_request_data["new_operators"],
            description=gettext("%s 重开单据，指定处理人 %s")
            % (get_request_username(), ";".join(validated_request_data["new_operators"])),
        )
        setattr(risk, "instance_origin_data", origin_data)
        self.add_audit_instance_to_context(instance=RiskAuditInstance(risk))


class GetRiskFieldsByStrategy(RiskMeta):
    name = gettext_lazy("获取风险字段")
    RequestSerializer = GetRiskFieldsByStrategyRequestSerializer
    ResponseSerializer = GetRiskFieldsByStrategyResponseSerializer
    many_response_data = True

    def perform_request(self, validated_request_data):
        get_app_info()
        # 获取基础字段
        fields = [
            {
                "key": field.field_name,
                "name": str(field.alias_name),
                "unique": field.field_name in (RiskFields.RAW_EVENT_ID.field_name, RiskFields.STRATEGY_ID.field_name),
            }
            for field in RiskFields().fields
        ]
        # 获取风险
        risk: Risk = Risk.objects.filter(strategy_id=validated_request_data["strategy_id"]).first()
        # 风险不存在时直接返回
        if risk is None:
            return fields
        # 补充风险拓展字段
        for key in risk.event_data.keys():
            fields.append(
                {
                    "key": f"{RiskFields.RISK_DATA.field_name}__{key}",
                    "name": f"{str(RiskFields.RISK_DATA.alias_name)}.{key}",
                }
            )
        # 补充风险证据字段
        with ignored(Exception, log_exception=False):
            origin_data = json.loads(json.loads(risk.event_evidence)[0].get("origin_data", "{}"))
            for key in origin_data.keys():
                fields.append(
                    {
                        "key": f"{RiskFields.RISK_EVIDENCE.field_name}__{key}",
                        "name": f"{str(RiskFields.RISK_EVIDENCE.alias_name)}.{key}",
                    }
                )
        return fields


class ProcessRiskTicket(RiskMeta):
    name = gettext_lazy("风险单据流转")

    def perform_request(self, validated_request_data):
        process_one_risk(risk_id=validated_request_data["risk_id"])
        return


class RiskExport(RiskMeta):
    name = gettext_lazy("风险导出")
    RequestSerializer = RiskExportReqSerializer

    def perform_request(self, validated_request_data):
        risk_view_type: str = validated_request_data.get("risk_view_type", "")
        risk_ids: List[str] = validated_request_data["risk_ids"]

        # 1. 获取有权限的风险列表
        risks: QuerySet[Risk] = Risk.prefetch_strategy_tags(Risk.load_authed_risks(action=ActionEnum.LIST_RISK)).filter(
            risk_id__in=risk_ids
        )

        authed_risk_ids = list(risks.values_list("risk_id", flat=True))
        no_authed_risk_ids = set(risk_ids) - set(authed_risk_ids)
        if no_authed_risk_ids:
            raise ExportRiskNoPermission(risk_ids=",".join(no_authed_risk_ids))

        # 2. 按策略分组风险
        strategies = list(
            Strategy.objects.filter(strategy_id__in=risks.values_list("strategy_id", flat=True)).order_by("strategy_id")
        )

        # 3. 获取策略的导出字段
        strategy_export_fields: Dict[str, List[ExportField]] = defaultdict(list)
        for strategy in strategies:
            risk_basic_fields = RiskExportField.export_fields()
            event_fields = [
                ExportField(
                    raw_name=f"{EVENT_EXPORT_FIELD_PREFIX}{field['field_name']}",
                    display_name=field["display_name"] or field["field_name"],
                )
                for field in strategy.event_data_field_configs
            ]
            strategy_export_fields[strategy.build_sheet_name()] = risk_basic_fields + event_fields

        # 4. 获取风险关联的事件,按策略分组并格式化数据
        bulk_events_params = []
        formatted_risks_by_strategy = defaultdict(list)
        risk_map = {risk.risk_id: risk for risk in risks}
        for risk_id in risk_ids:
            risk = risk_map[risk_id]
            # 时间转为 +8 时间字符串
            start_time = mstimestamp_to_date_string(int(risk.event_time.timestamp() * 1000))
            end_time = mstimestamp_to_date_string(int(datetime.now().timestamp() * 1000))
            risk_id = risk.risk_id
            bulk_events_params.append(
                {"risk_id": risk_id, "start_time": start_time, "end_time": end_time, "page": 1, "page_size": 10}
            )
        bulk_resp = resource.risk.list_event.bulk_request(bulk_events_params)
        for risk_id, resp in zip(risk_ids, bulk_resp):
            risk = risk_map[risk_id]
            events = resp["results"]
            risk_basic_data = {
                RiskExportField.RISK_ID: risk_id,
                RiskExportField.RISK_TITLE: risk.title,
                RiskExportField.EVENT_CONTENT: risk.event_content,
                RiskExportField.RISK_TAGS: data2string(
                    [tag_rel.tag.tag_name for tag_rel in risk.strategy.prefetched_tags]
                ),
                RiskExportField.EVENT_TYPE: data2string(risk.event_type),
                RiskExportField.RISK_LEVEL: str(RiskLevel.get_label(risk.strategy.risk_level)),
                RiskExportField.STRATEGY_NAME: risk.strategy.strategy_name,
                RiskExportField.STRATEGY_ID: risk.strategy.strategy_id,
                RiskExportField.RAW_EVENT_ID: risk.raw_event_id,
                RiskExportField.EVENT_END_TIME: risk.event_end_time.strftime(api_settings.DATETIME_FORMAT),
                RiskExportField.EVENT_TIME: risk.event_time.strftime(api_settings.DATETIME_FORMAT),
                RiskExportField.RISK_HAZARD: risk.strategy.risk_hazard,
                RiskExportField.RISK_GUIDANCE: risk.strategy.risk_guidance,
                RiskExportField.STATUS: str(RiskStatus.get_label(risk.status)),
                RiskExportField.RULE_ID: risk.rule_id,
                RiskExportField.OPERATOR: data2string(risk.operator),
                RiskExportField.CURRENT_OPERATOR: data2string(risk.current_operator),
                RiskExportField.NOTICE_USERS: data2string(risk.notice_users),
            }
            if not events:
                formatted_risks_by_strategy[risk.strategy.build_sheet_name()].append(risk_basic_data)
                continue
            for event in events:
                event_data = {
                    field["field_name"]: event.get("event_data", {}).get(field["field_name"], "")
                    for field in risk.strategy.event_data_field_configs
                }
                # 合并风险和事件字段，事件字段增加前缀
                formatted_risk = {
                    **risk_basic_data,
                    **{f"{EVENT_EXPORT_FIELD_PREFIX}{k}": v for k, v in event_data.items()},
                }
                formatted_risks_by_strategy[risk.strategy.build_sheet_name()].append(formatted_risk)

        # 5. 导出 excel
        exporter = MultiSheetRiskExporterXlsx()
        exporter.write(sheets_data=formatted_risks_by_strategy, sheets_headers=strategy_export_fields)
        excel_file = exporter.save()
        filename = RISK_EXPORT_FILE_NAME_TMP.format(
            risk_view_type=str(RiskViewType.get_label(risk_view_type)),
            datetime=datetime.now().strftime('%Y%m%d_%H%M%S'),
        )
        stream_response = FileResponse(excel_file, as_attachment=True, filename=filename)
        stream_response["Content-Type"] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        return stream_response

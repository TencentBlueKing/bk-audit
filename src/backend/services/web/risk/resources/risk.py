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
import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Type

from bk_resource import CacheResource, api
from bk_resource.base import Empty
from bk_resource.settings import bk_resource_settings
from bk_resource.utils.cache import CacheTypeItem
from bk_resource.utils.common_utils import ignored
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models import Case, Count, IntegerField, Max, Q, QuerySet, Subquery, When
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.translation import gettext, gettext_lazy
from rest_framework import serializers as drf_serializers
from rest_framework.response import Response
from rest_framework.settings import api_settings

from api.bk_plugins_ai_agent.exceptions import AgentRateLimited
from api.constants import AIAgentCode
from apps.audit.resources import AuditMixinResource
from apps.itsm.constants import TicketOperate, TicketStatus
from apps.meta.constants import ConfigLevelChoices
from apps.meta.models import GlobalMetaConfig, Tag
from apps.permission.handlers.actions import ActionEnum
from apps.permission.handlers.drf import wrapper_permission_field
from apps.permission.handlers.resource_types import ResourceEnum
from apps.sops.constants import SOPSTaskOperation, SOPSTaskStatus
from core.exceptions import RiskStatusInvalid
from core.models import get_request_username
from core.observability import (
    OBSERVATION_METRIC_STATUS_ERROR,
    OBSERVATION_METRIC_STATUS_SUCCESS,
    report_observation_metric,
    set_span_attributes,
    start_observation_span,
)
from core.utils.data import (
    build_preserved_order_queryset,
    choices_to_dict,
    value_to_label,
)
from services.web.common.constants import ScopeQueryField
from services.web.common.monitor import NL2RiskFilterFailedEvent
from services.web.common.scope_permission import ScopeContext, ScopePermission
from services.web.databus.constants import (
    ASSET_RISK_BKBASE_RT_ID_KEY,
    ASSET_STRATEGY_BKBASE_RT_ID_KEY,
    ASSET_STRATEGY_TAG_BKBASE_RT_ID_KEY,
    ASSET_TICKET_NODE_BKBASE_RT_ID_KEY,
    ASSET_TICKET_PERMISSION_BKBASE_RT_ID_KEY,
    DORIS_EVENT_BKBASE_RT_ID_KEY,
)
from services.web.risk.constants import (
    RISK_LEVEL_ORDER_FIELD,
    RISK_RENDER_LOCK_KEY,
    RISK_SHOW_FIELDS,
    EventBasicField,
    ItsmVersion,
    NL2RiskFilterLogStatus,
    RiskDisplayStatus,
    RiskFields,
    RiskLabel,
    RiskStatus,
    RiskViewType,
    TicketNodeStatus,
)
from services.web.risk.converter.bkbase import (
    BkBaseCountExecutor,
    BkBaseCountQueryBuilder,
    BkBaseDataExecutor,
    BkBaseDataQueryBuilder,
    BkBaseEventJoiner,
    BkBaseFieldResolver,
    BkBasePaginationPlanner,
    BkBaseQueryComponentsBuilder,
    BkBaseQueryExpressionBuilder,
    BkBaseResponseAssembler,
    BkBaseSQLRunner,
    FinalSelectAssembler,
    ManualUnsyncedRiskPrepender,
)
from services.web.risk.exceptions import (
    BulkSelectionOverLimit,
    ExportRiskNoPermission,
    NL2RiskFilterServiceError,
)
from services.web.risk.handlers import EventHandler
from services.web.risk.handlers.nl2riskfilter import (
    attach_datetime_origin,
    build_nl2risk_user_message,
    extract_filter_conditions_from_ai_result,
)
from services.web.risk.handlers.risk_export_service import RiskExportService
from services.web.risk.handlers.ticket import (
    AutoProcess,
    CloseRisk,
    ConfirmRisk,
    CustomProcess,
    ForApprove,
    MisReport,
    ReOpen,
    ReOpenMisReport,
    RiskExperienceRecord,
    TransOperator,
    get_itsm_ticket_status,
)
from services.web.risk.models import (
    ManualEvent,
    NL2RiskFilterLog,
    ProcessApplication,
    Risk,
    RiskAuditInstance,
    RiskExperience,
    TicketNode,
    TicketPermission,
    UserType,
)
from services.web.risk.serializers import (
    BULK_ACTION_MAX_RISK_IDS,
    BULK_AUTO_PROCESS_MAX_RISK_IDS,
    BULK_SELECTION_REQUIRED,
    PROCESS_APPLICATION_NOT_FOUND,
    BatchActionsPreviewReqSerializer,
    BatchActionsPreviewRespSerializer,
    BatchConfirmAsMisReportRequestSerializer,
    BatchConfirmRiskRequestSerializer,
    BulkActionRespSerializer,
    BulkAutoProcessReqSerializer,
    BulkCloseReqSerializer,
    BulkCustomTransRiskReqSerializer,
    BulkMisreportReqSerializer,
    BulkUnmisreportReqSerializer,
    ConfirmAsMisReportRequestSerializer,
    ConfirmRiskRequestSerializer,
    CustomAutoProcessReqSerializer,
    CustomCloseRiskRequestSerializer,
    CustomTransRiskReqSerializer,
    EventFieldsBriefResponseSerializer,
    EventFieldsForAIRequestSerializer,
    ForceRevokeApproveTicketReqSerializer,
    ForceRevokeAutoProcessReqSerializer,
    GetRiskFieldsByStrategyRequestSerializer,
    GetRiskFieldsByStrategyResponseSerializer,
    ListEventFieldsByStrategyRequestSerializer,
    ListEventFieldsByStrategyResponseSerializer,
    ListNL2RiskFilterLogRequestSerializer,
    ListRiskAPIGWRequestSerializer,
    ListRiskBriefRequestSerializer,
    ListRiskBriefResponseSerializer,
    ListRiskMetaRequestSerializer,
    ListRiskRequestSerializer,
    ListRiskResponseSerializer,
    ListRiskScenesRespSerializer,
    ListRiskStrategyRespSerializer,
    ListRiskTagsRespSerializer,
    ManualEventSerializer,
    NL2RiskFilterLogResponseSerializer,
    NL2RiskFilterRequestSerializer,
    NL2RiskFilterResponseSerializer,
    ReopenRiskReqSerializer,
    RetrieveRiskStrategyInfoAPIGWRequestSerializer,
    RetrieveRiskStrategyInfoAPIGWResponseSerializer,
    RetrieveRiskStrategyInfoResponseSerializer,
    RetryAutoProcessReqSerializer,
    RiskExportAsyncRespSerializer,
    RiskExportReqSerializer,
    RiskInfoSerializer,
    RiskInfoWithoutReportSerializer,
    TicketNodeSerializer,
    UpdateRiskLabelReqSerializer,
    UpdateRiskRequestSerializer,
)
from services.web.risk.tasks import (
    _build_manual_event_time_range,
    export_risks_to_mail,
    process_one_risk,
    sync_auto_result,
)
from services.web.risk.utils import (
    extract_attempt_records,
    fill_failure_info,
    iter_status_nodes,
)
from services.web.scene.constants import ResourceVisibilityType
from services.web.scene.models import Scene
from services.web.strategy_v2.constants import RiskLevel, StrategyFieldSourceEnum
from services.web.strategy_v2.models import Strategy, StrategyTag

logger = logging.getLogger(__name__)


class RiskMeta(AuditMixinResource, abc.ABC):
    tags = ["Risk"]
    audit_resource_type = ResourceEnum.RISK


class RetrieveRisk(RiskMeta):
    name = gettext_lazy("获取风险详情")
    audit_action = ActionEnum.LIST_RISK

    def perform_request(self, validated_request_data):
        risk_obj = get_object_or_404(Risk, risk_id=validated_request_data["risk_id"])
        self.add_audit_instance_to_context(instance=RiskAuditInstance(risk_obj))
        data = RiskInfoSerializer(risk_obj).data
        data = wrapper_permission_field(
            data,
            actions=[ActionEnum.EDIT_RISK, ActionEnum.PROCESS_RISK],
            id_field=lambda risk: risk["risk_id"],
            many=False,
        )
        risk = data[0]
        nodes = (
            TicketNode.objects.filter(risk_id=risk["risk_id"], is_test=False)
            .exclude(action=RiskExperienceRecord.__name__)
            .order_by("timestamp")
        )
        risk["ticket_history"] = TicketNodeSerializer(nodes, many=True).data
        risk["unsynced_events"] = self._load_unsynced_manual_events(risk_obj=risk_obj)
        risk["report_generating"] = self._is_report_generating(risk_obj.risk_id)
        return risk

    def _is_report_generating(self, risk_id: str) -> bool:
        """检查报告是否正在生成（通过 Redis 锁判断）"""
        lock_key = RISK_RENDER_LOCK_KEY.format(risk_id=risk_id)
        return cache.get(lock_key) is not None

    def _load_unsynced_manual_events(self, risk_obj: Risk) -> List[dict]:
        start = risk_obj.event_time
        end = risk_obj.event_end_time
        queryset = ManualEvent.objects.filter(
            manual_synced=False,
            strategy_id=risk_obj.strategy_id,
            raw_event_id=risk_obj.raw_event_id,
            event_time__gte=start,
        )
        if end is not None:
            queryset = queryset.filter(event_time__lte=end)
        manual_events = list(queryset)
        if not manual_events:
            return []

        start_times: List[str] = []
        end_times: List[str] = []
        manual_event_ids: List[str] = []
        for event in manual_events:
            start_time, end_time = _build_manual_event_time_range(event.event_time, timedelta(hours=1))
            start_times.append(start_time)
            end_times.append(end_time)
            manual_event_ids.append(str(event.manual_event_id))

        search_start = min(start_times)
        search_end = max(end_times)
        manual_event_id_param = ",".join(manual_event_ids)
        page_size = max(len(manual_events), 10)

        try:
            resp = (
                EventHandler.search_event(
                    namespace=settings.DEFAULT_NAMESPACE,
                    start_time=search_start,
                    end_time=search_end,
                    page=1,
                    page_size=page_size,
                    manual_event_id=manual_event_id_param,
                )
                or {}
            )
        except Exception as err:  # NOCC:broad-except(需要兜底，详情接口不应因查询失败报错)
            logger.warning(
                "[RetrieveRisk] search manual_event_ids=%s failed when confirming manual_synced: %s",
                manual_event_id_param,
                err,
            )
            return ManualEventSerializer(instance=manual_events, many=True).data

        results = resp.get("results") or []
        synced_ids = {
            int(item["manual_event_id"])
            for item in results
            if isinstance(item, dict) and item.get("manual_event_id") is not None
        }

        if synced_ids:
            ManualEvent.objects.filter(manual_event_id__in=synced_ids, manual_synced=False).update(manual_synced=True)
            manual_events = [event for event in manual_events if event.manual_event_id not in synced_ids]

        if not manual_events:
            return []
        return ManualEventSerializer(instance=manual_events, many=True).data


class RetrieveRiskStrategyInfo(RiskMeta):
    name = gettext_lazy("获取风险策略信息")
    ResponseSerializer = RetrieveRiskStrategyInfoResponseSerializer

    def perform_request(self, validated_request_data):
        risk: Risk = get_object_or_404(Risk, risk_id=validated_request_data["risk_id"])
        strategy = Strategy.objects.filter(strategy_id=risk.strategy_id).first()
        if strategy is None:
            return {}
        # 按风险归属场景过滤不可见的下钻工具（展示态与执行鉴权同口径）
        serializer = RetrieveRiskStrategyInfoResponseSerializer(strategy, context={"risk_scene_id": risk.scene_id})
        return serializer.data


class RetrieveRiskStrategyInfoAPIGW(RiskMeta):
    name = gettext_lazy("获取风险策略信息(APIGW)")
    RequestSerializer = RetrieveRiskStrategyInfoAPIGWRequestSerializer
    ResponseSerializer = RetrieveRiskStrategyInfoAPIGWResponseSerializer
    audit_action = None

    def perform_request(self, validated_request_data):
        risk: Risk = get_object_or_404(Risk, risk_id=validated_request_data["risk_id"])
        strategy = Strategy.objects.filter(strategy_id=risk.strategy_id).first()
        if not strategy:
            return {}

        lite_mode = validated_request_data.get("lite_mode", True)
        serializer = RetrieveRiskStrategyInfoAPIGWResponseSerializer(
            strategy, lite_mode=lite_mode, context={"risk_scene_id": risk.scene_id}
        )
        return serializer.data


class RetrieveRiskAPIGW(RetrieveRisk):
    audit_action = None
    ResponseSerializer = RiskInfoWithoutReportSerializer

    def perform_request(self, validated_request_data):
        return get_object_or_404(Risk, risk_id=validated_request_data["risk_id"])


class MCPRetrieveRisk(RetrieveRiskAPIGW):
    """获取 MCP 可见的风险详情，不返回风险报告正文。"""

    name = gettext_lazy("获取风险详情(MCP)")


class ListRisk(RiskMeta):
    name = gettext_lazy("获取风险列表")
    RequestSerializer = ListRiskRequestSerializer
    bind_request = True
    audit_action = ActionEnum.LIST_RISK
    STORAGE_SUFFIX = "doris"
    # list_risk 接口同时承载"所有风险"(不传 scope) 与"场景风险"(传 scope) 两个视图，
    # 仅场景风险视图需排除待确认状态（待确认有独立的 pending_confirm 接口）。
    # 因此该开关只在带 scope 查询时生效；本身以待确认为主体的子类需置为 False，否则结果会被清空
    exclude_pending_confirm = True

    def perform_request(self, validated_request_data):
        request = validated_request_data.pop("_request")
        order_fields = validated_request_data.pop("order_fields", [])
        use_bkbase = bool(validated_request_data.pop("use_bkbase", False))
        event_filters = validated_request_data.pop("event_filters", [])
        scope_type = validated_request_data.pop("scope_type", None)
        scope_id = validated_request_data.pop("scope_id", None)
        scene_ids = validated_request_data.pop("scene_id", [])

        self._duplicate_event_field_map: Dict[int, Dict[str, Set[str]]] = {}
        thedate_range = self._extract_thedate_range(validated_request_data)
        base_queryset = self.load_risks(validated_request_data)

        # 仅在显式传入 scope 时应用场景过滤；个人视图可不传 scope
        if scope_type:
            scope = ScopeContext(scope_type=scope_type, scope_id=scope_id)
            scope_scene_ids = ScopePermission(get_request_username(request)).get_scene_ids(scope, ActionEnum.VIEW_SCENE)
            # 风险场景归属已固化到 Risk.scene_id，直接按模型字段过滤（不再经 ResourceBinding 反查）
            if scope_scene_ids:
                base_queryset = base_queryset.filter(scene_id__in=scope_scene_ids)
            else:
                base_queryset = base_queryset.none()
            # 场景风险视图排除待确认状态（待确认由独立列表承载）；
            # 所有风险视图不传 scope，保留全部状态
            if self.exclude_pending_confirm:
                base_queryset = base_queryset.exclude(display_status=RiskDisplayStatus.PENDING_CONFIRM)

        base_queryset = self._filter_queryset_by_scene_ids(base_queryset, scene_ids)
        base_queryset = self._filter_queryset_by_event_data_fields(base_queryset, event_filters)

        if use_bkbase:
            paged_risks, page, sql_statements = self.retrieve_via_bkbase(
                base_queryset=base_queryset,
                request=request,
                order_fields=order_fields,
                event_filters=event_filters,
                thedate_range=thedate_range,
            )
            return BkBaseResponseAssembler(self, ListRiskResponseSerializer).build_response(
                paged_risks, page, sql_statements
            )

        paged_risks, page, risk_ids = self.retrieve_via_db(
            base_queryset=base_queryset, request=request, order_fields=order_fields
        )

        experiences = self._fetch_experiences(risk_ids)
        for risk in paged_risks:
            setattr(risk, "experiences", experiences.get(risk.risk_id, 0))
        response = page.get_paginated_response(
            data=ListRiskResponseSerializer(instance=paged_risks, many=True).data
        ).data
        response["sql"] = []
        return response

    def _filter_queryset_by_scene_ids(self, queryset: QuerySet, scene_ids: List[str]) -> QuerySet:
        if not scene_ids:
            return queryset

        # 风险场景归属已固化到 Risk.scene_id，直接按模型字段过滤（不再经 ResourceBinding 反查）
        return queryset.filter(scene_id__in=scene_ids)

    def _extract_thedate_range(self, validated_request_data) -> Tuple[str, str]:
        end_dt = (
            validated_request_data['event_time__lt'][0]
            if validated_request_data.get('event_time__lt')
            else datetime.now()
        )
        start_dt = (
            validated_request_data['event_time__gte'][0]
            if validated_request_data.get('event_time__gte')
            else end_dt - timedelta(days=180)
        )
        start_date = start_dt.date().strftime("%Y%m%d")
        end_date = end_dt.date().strftime("%Y%m%d")
        return start_date, end_date

    def _paginate_queryset(self, queryset: QuerySet, request, base_queryset: QuerySet = None, pagination_class=None):
        """按指定分页器分页 QuerySet；导出场景会传入更高的分页上限，避免被列表分页上限截断。"""

        page = (pagination_class or api_settings.DEFAULT_PAGINATION_CLASS)()
        paged_queryset = page.paginate_queryset(queryset=queryset, request=request)
        if base_queryset is None:
            base_queryset = queryset.model.objects
        return base_queryset.filter(pk__in=[item.pk for item in paged_queryset]), page

    def retrieve_via_db(self, base_queryset: QuerySet, request, order_fields: List[str], pagination_class=None):
        # base_queryset 是不带注解的纯净 QS，用于 COUNT（避免 SUBSTRING/EXISTS 子查询开销）
        risks = self._apply_ordering(base_queryset, order_fields).only("pk")
        paged_queryset, page = self._paginate_queryset(
            queryset=risks,
            request=request,
            # 数据加载阶段套上展示注解（event_content_short / _has_report）
            base_queryset=Risk.annotated_queryset(),
            pagination_class=pagination_class,
        )
        paged_queryset = self._apply_ordering(Risk.prefetch_strategy_tags(paged_queryset), order_fields)
        paged_risks = list(paged_queryset)
        risk_ids = [risk.risk_id for risk in paged_risks]
        return paged_risks, page, risk_ids

    def _fetch_experiences(self, risk_ids: List[str]) -> Dict[str, int]:
        if not risk_ids:
            return {}
        return {
            row["risk_id"]: row["count"]
            for row in RiskExperience.objects.filter(risk_id__in=risk_ids)
            .values("risk_id")
            .order_by("risk_id")
            .annotate(count=Count("risk_id"))
        }

    def _filter_queryset_by_event_data_fields(
        self, queryset: QuerySet, event_filters: List[Dict[str, Any]]
    ) -> QuerySet:
        if not event_filters:
            return queryset

        # type = "basic_event_field" 的字段不参与策略配置 gate；
        data_filter_items = [item for item in event_filters if item.get("type") != "basic_event_field"]

        if not data_filter_items:
            return queryset

        strategy_ids = list(queryset.values_list("strategy_id", flat=True).distinct())
        if not strategy_ids:
            return queryset.none()

        # 使用JSONField contains能力在数据库侧完成过滤，避免加载并解析所有配置
        strategy_queryset = Strategy.objects.filter(strategy_id__in=strategy_ids)

        for item in data_filter_items:
            field = item.get("field") or ""
            display_name = item.get("display_name")
            strategy_queryset = strategy_queryset.filter(
                event_data_field_configs__contains=[{"field_name": field, "display_name": display_name}]
            )

        matched_strategy_ids = list(strategy_queryset.values_list("strategy_id", flat=True))
        if not matched_strategy_ids:
            return queryset.none()

        self._duplicate_event_field_map = self._collect_duplicate_event_fields(matched_strategy_ids)
        return queryset.filter(strategy_id__in=matched_strategy_ids)

    def _collect_duplicate_event_fields(self, strategy_ids: Sequence[str]) -> Dict[int, Dict[str, Set[str]]]:
        duplicate_map: Dict[int, Dict[str, Set[str]]] = defaultdict(lambda: defaultdict(set))
        if not strategy_ids:
            return {}
        configs_qs = Strategy.objects.filter(strategy_id__in=strategy_ids).values_list(
            "strategy_id",
            "event_basic_field_configs",
            "event_data_field_configs",
            "event_evidence_field_configs",
        )
        for strategy_id, basic_configs, data_configs, evidence_configs in configs_qs:
            strategy_map = duplicate_map[int(strategy_id)]
            self._collect_duplicate_fields_for_source(strategy_map, StrategyFieldSourceEnum.BASIC.value, basic_configs)
            self._collect_duplicate_fields_for_source(strategy_map, StrategyFieldSourceEnum.DATA.value, data_configs)
            self._collect_duplicate_fields_for_source(
                strategy_map, StrategyFieldSourceEnum.EVIDENCE.value, evidence_configs
            )
        cleaned: Dict[int, Dict[str, Set[str]]] = {}
        for strategy_id, source_map in duplicate_map.items():
            filtered = {src: fields for src, fields in source_map.items() if fields}
            if filtered:
                cleaned[strategy_id] = filtered
        return cleaned

    def _collect_duplicate_fields_for_source(
        self,
        source_map: Dict[str, Set[str]],
        source: str,
        configs: Optional[Sequence[Dict[str, Any]]],
    ) -> None:
        if not configs:
            return
        for field_config in configs:
            field_name = field_config.get("field_name")
            if not field_name or not field_config.get("duplicate_field"):
                continue
            source_map[source].add(field_name)

    def retrieve_via_bkbase(
        self,
        base_queryset: QuerySet,
        request,
        order_fields: List[str],
        event_filters: List[Dict[str, Any]],
        thedate_range: Optional[Tuple[str, str]] = None,
        pagination_class=None,
    ):
        pagination_class = pagination_class or api_settings.DEFAULT_PAGINATION_CLASS
        manual_helper = ManualUnsyncedRiskPrepender(base_queryset, order_fields, self._apply_ordering)
        manual_unsynced_count = manual_helper.count()
        resolver = BkBaseFieldResolver(order_fields, event_filters, self._duplicate_event_field_map)
        value_fields = resolver.resolve_value_fields(
            ["risk_id", "strategy_id", "raw_event_id", "event_time", "event_end_time"]
        )
        values_queryset = base_queryset.values(*value_fields).distinct()

        table_map = self._get_bkbase_table_map()
        expression_builder = BkBaseQueryExpressionBuilder(
            table_map=table_map,
            storage_suffix=self.STORAGE_SUFFIX,
        )
        base_sql = expression_builder.compile_queryset_sql(values_queryset.order_by())
        if base_sql is None:
            page = pagination_class()
            page.paginate_queryset(range(manual_unsynced_count), request)
            manual_ids = []
            if manual_unsynced_count and getattr(page, "page", None):
                limit = getattr(page.page.paginator, "per_page", 0)
                offset = (getattr(page.page, "number", 1) - 1) * limit if limit else 0
                manual_ids = manual_helper.slice_ids(offset, limit)
            paged_queryset = Risk.prefetch_strategy_tags(self._build_risk_queryset(manual_ids))
            paged_risks = list(paged_queryset)
            if getattr(page, "page", None):
                page.page.object_list = list(manual_ids)
            return paged_risks, page, []

        base_expression = expression_builder.convert_to_expression(base_sql)
        components_builder = BkBaseQueryComponentsBuilder(
            resolver=resolver,
            duplicate_field_map=self._duplicate_event_field_map,
            thedate_range=thedate_range,
            table_name=self._get_risk_event_table_reference(expression_builder, table_map),
        )
        assembler = FinalSelectAssembler(resolver)
        count_query_builder = BkBaseCountQueryBuilder(assembler)
        data_query_builder = BkBaseDataQueryBuilder(assembler)
        sql_runner = BkBaseSQLRunner(api.bk_base.query_sync)
        count_executor = BkBaseCountExecutor(
            components_builder=components_builder,
            count_query_builder=count_query_builder,
            sql_runner=sql_runner,
        )
        data_executor = BkBaseDataExecutor(
            components_builder=components_builder,
            data_query_builder=data_query_builder,
            sql_runner=sql_runner,
        )
        pagination_planner = BkBasePaginationPlanner(pagination_class)

        bkbase_total, components = count_executor.execute(base_expression)
        total = bkbase_total + manual_unsynced_count
        page, limit, offset = pagination_planner.paginate(total, request)

        manual_ids = manual_helper.slice_ids(offset, limit)
        manual_filled = len(manual_ids)
        bkbase_limit = max(limit - manual_filled, 0)
        bkbase_offset = max(offset - manual_unsynced_count, 0)

        risk_rows: List[Dict[str, Any]] = []
        if bkbase_limit and bkbase_total:
            risk_rows = data_executor.execute(
                base_expression,
                order_fields=order_fields,
                limit=bkbase_limit,
                offset=bkbase_offset,
                components=components,
            )

        risk_ids = manual_ids + [row["risk_id"] for row in risk_rows]
        paged_queryset = self._build_risk_queryset(risk_ids)
        paged_queryset = Risk.prefetch_strategy_tags(paged_queryset)
        paged_risks = list(paged_queryset)

        BkBaseEventJoiner(self).attach_events(paged_risks, risk_rows)

        if getattr(page, "page", None):
            page.page.object_list = list(risk_ids)

        return paged_risks, page, sql_runner.sql_statements

    def _apply_ordering(self, queryset: QuerySet["Risk"], order_fields: List[str]) -> QuerySet["Risk"]:
        if not order_fields:
            return queryset

        orm_order_args = []
        for field in order_fields:
            if field.lstrip("-") == RISK_LEVEL_ORDER_FIELD:
                queryset, sort_key = build_preserved_order_queryset(
                    queryset,
                    field,
                    [RiskLevel.LOW, RiskLevel.MIDDLE, RiskLevel.HIGH],
                    annotate_name="_risk_level_order",
                )
                orm_order_args.append(sort_key)
            else:
                orm_order_args.append(field)

        return queryset.order_by(*orm_order_args)

    def _build_filter_query(self, validated_request_data: dict) -> Q:
        """通用筛选条件构造：从请求参数中提取风险等级、标签等筛选条件并构造 Q 表达式，供所有 ListRisk 子类共享。"""
        q = Q()
        # 风险等级
        risk_level = validated_request_data.pop("risk_level", None)
        if risk_level:
            q &= Q(risk_level__in=risk_level)

        # 标签筛选条件
        if tag_filter := validated_request_data.pop("tag_objs__in", None):
            q &= Q(strategy__tags__tag_id__in=tag_filter)

        # 是否已生成报告
        has_report = validated_request_data.pop("has_report", None)
        if has_report is not None:
            q &= Q(has_report=has_report)

        for key, val in validated_request_data.items():
            if not val:
                continue
            # 普通匹配，针对单值匹配
            _q = Q()
            for i in val:
                _q |= Q(**{key: i})
            q &= _q
        return q

    def load_risks(self, validated_request_data: dict, username: str = None) -> QuerySet["Risk"]:
        q = self._build_filter_query(validated_request_data)
        return Risk.load_iam_authed_risks(action=ActionEnum.LIST_RISK, username=username).filter(q).distinct()

    def load_filter_risk_ids(self, validated_request_data: dict, username: str, risk_limit: int) -> List[str]:
        """复用列表筛选、权限过滤和 DB/BKBase 检索分支，按指定用户加载风险 ID。"""

        filter_data = dict(validated_request_data)

        order_fields = filter_data.pop("order_fields", [])
        use_bkbase = bool(filter_data.pop("use_bkbase", False))
        event_filters = filter_data.pop("event_filters", [])
        scope_type = filter_data.pop("scope_type", None)
        scope_id = filter_data.pop("scope_id", None)
        scene_ids = filter_data.pop("scene_id", [])

        self._duplicate_event_field_map = {}
        thedate_range = self._extract_thedate_range(filter_data)
        base_queryset = self.load_risks(filter_data, username=username)

        if scope_type:
            scope = ScopeContext(scope_type=scope_type, scope_id=scope_id)
            scope_scene_ids = ScopePermission(username).get_scene_ids(scope, ActionEnum.VIEW_SCENE)
            # 风险场景归属已固化到 Risk.scene_id，直接按模型字段过滤（不再经 ResourceBinding 反查）
            if scope_scene_ids:
                base_queryset = base_queryset.filter(scene_id__in=scope_scene_ids)
            else:
                base_queryset = base_queryset.none()
            # 场景风险视图排除待确认状态
            if self.exclude_pending_confirm:
                base_queryset = base_queryset.exclude(display_status=RiskDisplayStatus.PENDING_CONFIRM)

        base_queryset = self._filter_queryset_by_scene_ids(base_queryset, scene_ids)
        base_queryset = self._filter_queryset_by_event_data_fields(base_queryset, event_filters)

        if use_bkbase:
            request = SimpleNamespace(query_params={"page": "1", "page_size": str(risk_limit)})
            pagination_class = self._build_export_pagination_class(risk_limit)
            paged_risks, _, _ = self.retrieve_via_bkbase(
                base_queryset=base_queryset,
                request=request,
                order_fields=order_fields,
                event_filters=event_filters,
                thedate_range=thedate_range,
                pagination_class=pagination_class,
            )
            return [risk.risk_id for risk in paged_risks]

        return self._load_filter_risk_ids_via_db(
            base_queryset=base_queryset,
            order_fields=order_fields,
            risk_limit=risk_limit,
        )

    def _load_filter_risk_ids_via_db(
        self,
        base_queryset: QuerySet["Risk"],
        order_fields: List[str],
        risk_limit: int,
    ) -> List[str]:
        """范围导出 DB 分支只加载 risk_id，避免复用列表详情加载导致大批量模型对象和标签预取。"""

        risk_queryset = self._apply_ordering(base_queryset, order_fields)
        return list(risk_queryset.values_list("risk_id", flat=True)[:risk_limit])

    @staticmethod
    def _build_export_pagination_class(page_size: int) -> Type:
        """构造导出 ID 解析专用分页器，避免复用列表分页器时被 max_page_size=1000 截断。"""

        return type(
            "RiskExportPageNumberPagination",
            (api_settings.DEFAULT_PAGINATION_CLASS,),
            {"page_size": page_size, "max_page_size": page_size},
        )

    def _build_risk_queryset(self, risk_ids: List[str]) -> QuerySet["Risk"]:
        if not risk_ids:
            return Risk.annotated_queryset().none()

        order_cases = [When(risk_id=risk_id, then=index) for index, risk_id in enumerate(risk_ids)]
        order_expression = Case(*order_cases, default=len(risk_ids), output_field=IntegerField())
        return Risk.annotated_queryset().filter(risk_id__in=risk_ids).order_by(order_expression)

    def _get_bkbase_table_map(self) -> Dict[str, str]:
        if not hasattr(self, "_bkbase_table_map"):
            table_map = {
                Risk._meta.db_table: self._get_configured_table_name(
                    config_key=ASSET_RISK_BKBASE_RT_ID_KEY, fallback=Risk._meta.db_table
                ),
                Strategy._meta.db_table: self._get_configured_table_name(
                    config_key=ASSET_STRATEGY_BKBASE_RT_ID_KEY, fallback=Strategy._meta.db_table
                ),
                StrategyTag._meta.db_table: self._get_configured_table_name(
                    config_key=ASSET_STRATEGY_TAG_BKBASE_RT_ID_KEY, fallback=StrategyTag._meta.db_table
                ),
                TicketPermission._meta.db_table: self._get_configured_table_name(
                    config_key=ASSET_TICKET_PERMISSION_BKBASE_RT_ID_KEY, fallback=TicketPermission._meta.db_table
                ),
                TicketNode._meta.db_table: self._get_configured_table_name(
                    config_key=ASSET_TICKET_NODE_BKBASE_RT_ID_KEY, fallback=TicketNode._meta.db_table
                ),
                "risk_event": self._get_configured_table_name(
                    config_key=DORIS_EVENT_BKBASE_RT_ID_KEY, fallback="risk_event"
                ),
            }
            self._bkbase_table_map = {
                source: self._apply_storage_suffix(target) for source, target in table_map.items()
            }
        return self._bkbase_table_map

    def _get_configured_table_name(self, *, config_key: str, fallback: str) -> str:
        return GlobalMetaConfig.get(
            config_key=config_key,
            config_level=ConfigLevelChoices.NAMESPACE.value,
            instance_key=settings.DEFAULT_NAMESPACE,
            default=fallback,
        )

    @classmethod
    def _apply_storage_suffix(cls, table_name: str) -> str:
        cleaned = (table_name or "").strip()
        if not cleaned:
            return cleaned
        parts = [part for part in cleaned.split(".") if part]
        if parts and parts[-1].strip("`").lower() == cls.STORAGE_SUFFIX:
            return ".".join(parts)
        return ".".join(parts + [cls.STORAGE_SUFFIX])

    def _get_risk_event_table_reference(
        self,
        expression_builder: Optional[BkBaseQueryExpressionBuilder] = None,
        table_map: Optional[Dict[str, str]] = None,
    ) -> str:
        resolved_table_map = table_map or self._get_bkbase_table_map()
        builder = expression_builder or BkBaseQueryExpressionBuilder(
            table_map=resolved_table_map,
            storage_suffix=self.STORAGE_SUFFIX,
        )
        table_name = resolved_table_map.get("risk_event", "risk_event")
        formatted = builder.format_table_identifier(table_name)
        return formatted or "risk_event"


class ListRiskAPIGW(ListRisk):
    """APIGW 获取风险列表接口 - 继承 ListRisk，仅鉴权方式不同（App 鉴权替代 IAM 用户鉴权），其他逻辑完全一致"""

    name = gettext_lazy("获取风险列表(APIGW)")
    RequestSerializer = ListRiskAPIGWRequestSerializer
    bind_request = True
    audit_action = None

    def perform_request(self, validated_request_data):
        with_detail = validated_request_data.pop("with_detail", False)
        response = super().perform_request(validated_request_data)
        if with_detail and response.get("results"):
            # 获取当前页所有风险单的 risk_id
            risk_ids = [item["risk_id"] for item in response["results"]]
            # 批量查询风险单对象
            risk_objs = {
                risk.risk_id: risk for risk in Risk.objects.select_related("strategy").filter(risk_id__in=risk_ids)
            }
            # 用 RiskInfoSerializer 序列化详情并合并到每条结果中
            for item in response["results"]:
                risk_obj = risk_objs.get(item["risk_id"])
                if risk_obj:
                    item["detail"] = RiskInfoSerializer(risk_obj).data
                else:
                    item["detail"] = None
        return response

    def load_risks(self, validated_request_data: dict) -> QuerySet["Risk"]:
        """APIGW 不走 IAM 鉴权，仅校验 App 身份后直接查询全部风险"""
        q = self._build_filter_query(validated_request_data)
        return Risk.objects.filter(q).distinct()


class ListMineRisk(ListRisk):
    name = gettext_lazy("获取待我处理的风险列表")

    def load_risks(self, validated_request_data, username: str = None):
        username = username or get_request_username()
        q = self._build_filter_query(validated_request_data)
        # 个人视图只需查询窗口内新授权的工单权限，减少历史权限扫描量。
        event_time_start = next(iter(validated_request_data.get("event_time__gte") or []), None)
        return Risk.objects.filter(
            q,
            Risk.local_risk_filter(
                user_types=[UserType.OPERATOR],
                username=username,
                authorized_at_start=event_time_start,
            ),
            current_operator__contains=username,
            # 排除待确认状态（待确认有独立列表）
            display_status__in=[
                RiskDisplayStatus.NEW,
                RiskDisplayStatus.PROCESSING,
                RiskDisplayStatus.FOR_APPROVE,
                RiskDisplayStatus.AUTO_PROCESS,
                RiskDisplayStatus.AWAIT_PROCESS,
                RiskDisplayStatus.CLOSED,
                RiskDisplayStatus.STAND_BY,
            ],
        ).distinct()


class ListNoticingRisk(ListRisk):
    name = gettext_lazy("获取我关注的风险列表")

    def load_risks(self, validated_request_data, username: str = None):
        username = username or get_request_username()
        q = self._build_filter_query(validated_request_data)
        # 个人视图只需查询窗口内新授权的工单权限，减少历史权限扫描量。
        event_time_start = next(iter(validated_request_data.get("event_time__gte") or []), None)
        return Risk.objects.filter(
            q,
            Risk.local_risk_filter(
                user_types=[UserType.NOTICE_USER],
                username=username,
                authorized_at_start=event_time_start,
            ),
            notice_users__contains=username,
            # 排除待确认状态（待确认有独立列表）
            display_status__in=[
                RiskDisplayStatus.NEW,
                RiskDisplayStatus.PROCESSING,
                RiskDisplayStatus.FOR_APPROVE,
                RiskDisplayStatus.AUTO_PROCESS,
                RiskDisplayStatus.AWAIT_PROCESS,
                RiskDisplayStatus.CLOSED,
                RiskDisplayStatus.STAND_BY,
            ],
        ).distinct()


class ListProcessedRisk(ListRisk):
    """
    处理历史：曾作为处理人但当前不是处理人的风险。
    """

    name = gettext_lazy("获取处理历史风险列表")

    def load_risks(self, validated_request_data, username: str = None):
        q = self._build_filter_query(validated_request_data)
        username = username or get_request_username()
        # 包含所有 TicketNode 操作（含 RiskExperienceRecord），添加经验也视为"处理"
        processed_risk_ids = TicketNode.objects.filter(
            operator=username,
            is_test=False,
        ).values("risk_id")
        return Risk.objects.filter(
            q,
            risk_id__in=processed_risk_ids,
            # 排除待确认状态（待确认有独立列表）
            display_status__in=[
                RiskDisplayStatus.NEW,
                RiskDisplayStatus.PROCESSING,
                RiskDisplayStatus.FOR_APPROVE,
                RiskDisplayStatus.AUTO_PROCESS,
                RiskDisplayStatus.AWAIT_PROCESS,
                RiskDisplayStatus.CLOSED,
                RiskDisplayStatus.STAND_BY,
            ],
        ).exclude(current_operator__contains=username)


class ListPendingConfirmRisk(ListRisk):
    """获取待我确认的风险列表"""

    name = gettext_lazy("待我确认")
    # 本视图只展示待确认，必须关闭 scope 查询下的待确认排除，否则结果被清空
    exclude_pending_confirm = False

    def load_risks(self, validated_request_data, username: str = None):
        username = username or get_request_username()
        q = self._build_filter_query(validated_request_data)

        return (
            Risk.objects.filter(
                q,
                display_status=RiskDisplayStatus.PENDING_CONFIRM,
                confirmer__contains=username,  # 确认人包含当前用户
                is_deleted=False,
            )
            .distinct()
            .order_by("-event_time")
        )


class ListRiskFields(RiskMeta):
    name = gettext_lazy("获取风险字段")

    def perform_request(self, validated_request_data):
        show_fields = set(RISK_SHOW_FIELDS)
        return [
            {
                "id": f.attname if getattr(f, "attname", None) in show_fields else f.name,
                "name": str(f.verbose_name),
            }
            for f in Risk.fields()
            if f.name in show_fields or getattr(f, "attname", None) in show_fields
        ]


class UpdateRiskLabel(RiskMeta):
    name = gettext_lazy("更新风险标记")
    RequestSerializer = UpdateRiskLabelReqSerializer
    ResponseSerializer = RiskInfoSerializer
    audit_action = ActionEnum.PROCESS_RISK
    bind_request = True

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

            if risk.status == RiskStatus.PENDING_CONFIRM:
                ConfirmAsMisReportResource().perform_request(
                    {
                        "risk_id": risk.risk_id,
                        "description": validated_request_data.get("description", ""),
                        "_request": validated_request_data.get("_request"),
                    }
                )
            else:
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


class RiskDisplayStatusCommon(RiskMeta):
    """获取风险展示状态类型（供前端下拉框筛选使用）"""

    name = gettext_lazy("获取风险展示状态类型")

    def perform_request(self, validated_request_data):
        return choices_to_dict(RiskDisplayStatus)


class ListRiskMetaBase(RiskMeta, CacheResource, abc.ABC):
    RequestSerializer = ListRiskMetaRequestSerializer
    many_response_data = True
    # 风险视图类型与风险类的映射
    risk_cls_map: Dict[str, Type[ListRisk]] = {
        RiskViewType.ALL.value: ListRisk,
        RiskViewType.SCENE.value: ListRisk,
        RiskViewType.TODO.value: ListMineRisk,
        RiskViewType.WATCH.value: ListNoticingRisk,
        RiskViewType.PROCESSED.value: ListProcessedRisk,
        RiskViewType.CONFIRM.value: ListPendingConfirmRisk,
    }

    @classmethod
    def load_risk_view_type_risks(cls, risk_view_type: str, filter_dict: dict, scene_ids=None) -> QuerySet[Risk]:
        """
        加载指定风险视图下有权限的风险
        """

        risk_cls = cls.risk_cls_map.get(risk_view_type)
        if not risk_cls:
            return Risk.objects.none()
        risks = risk_cls().load_risks(filter_dict)
        if scene_ids is None:
            return risks

        if not scene_ids:
            return risks.none()
        return risks.filter(scene_id__in=scene_ids)


class ListRiskTags(ListRiskMetaBase):
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
        scope_type = validated_request_data.pop("scope_type", None)
        scope_id = validated_request_data.pop("scope_id", None)
        scene_ids = None
        if scope_type:
            scope = ScopeContext(scope_type=scope_type, scope_id=scope_id)
            scene_ids = ScopePermission(get_request_username()).get_scene_ids(scope, ActionEnum.VIEW_SCENE)
        risk_qs = self.load_risk_view_type_risks(risk_view_type, validated_request_data, scene_ids=scene_ids)
        strategy_id_qs = risk_qs.order_by().values("strategy_id").distinct()
        tag_id_qs = StrategyTag.objects.filter(strategy_id__in=strategy_id_qs).values("tag_id")
        return tags.filter(tag_id__in=tag_id_qs)


class ListRiskStrategy(ListRiskMetaBase):
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
        scope_type = validated_request_data.pop("scope_type", None)
        scope_id = validated_request_data.pop("scope_id", None)
        scene_ids = None
        if scope_type:
            scope = ScopeContext(scope_type=scope_type, scope_id=scope_id)
            scene_ids = ScopePermission(get_request_username()).get_scene_ids(scope, ActionEnum.VIEW_SCENE)
        strategy_id_qs = (
            self.load_risk_view_type_risks(risk_view_type, validated_request_data, scene_ids=scene_ids)
            .order_by()
            .values_list("strategy_id", flat=True)
            .distinct()
        )
        # 元数据接口只需要策略维度结果。先物化 distinct strategy_id，可以把风险过滤 SQL
        # 与后续策略/场景维表查询拆开，避免 MySQL 将嵌套子查询改写成 strategy -> risk 的执行计划，
        # 从而在大量风险行上执行 JSON_CONTAINS 等高成本条件。
        strategy_ids = list(strategy_id_qs)
        return strategies.filter(strategy_id__in=strategy_ids)


class ListRiskScenes(ListRiskStrategy):
    """
    获取风险关联的场景，复用风险策略筛选结果生成场景列表
    注意：该接口的筛选条件主要需要风险列表的事件发生时间，当该参数变化时需要重新查询
    """

    name = gettext_lazy("获取风险的场景")
    ResponseSerializer = ListRiskScenesRespSerializer
    cache_type = CacheTypeItem(key="ListRiskScenes", timeout=60, user_related=True)

    def perform_request(self, validated_request_data):
        # 风险场景归属已固化到 Risk.scene_id，直接按模型字段取去重场景，不再经策略绑定反查
        risk_view_type = validated_request_data.pop("risk_view_type", None)
        scope_type = validated_request_data.pop("scope_type", None)
        scope_id = validated_request_data.pop("scope_id", None)
        scene_ids = None
        if scope_type:
            scope = ScopeContext(scope_type=scope_type, scope_id=scope_id)
            scene_ids = ScopePermission(get_request_username()).get_scene_ids(scope, ActionEnum.VIEW_SCENE)
        if risk_view_type:
            risk_qs = self.load_risk_view_type_risks(risk_view_type, validated_request_data, scene_ids=scene_ids)
        else:
            # 未传 risk_view_type 时沿用全量策略逻辑：返回全部风险所属场景
            risk_qs = Risk.objects.all()
            if scene_ids:
                risk_qs = risk_qs.filter(scene_id__in=scene_ids)
        scene_id_qs = risk_qs.order_by().values_list("scene_id", flat=True).filter(scene_id__isnull=False).distinct()
        return Scene.objects.filter(scene_id__in=list(scene_id_qs)).only("scene_id", "name").distinct()


class CustomCloseRisk(RiskMeta):
    name = gettext_lazy("人工关单")
    RequestSerializer = CustomCloseRiskRequestSerializer
    audit_action = ActionEnum.PROCESS_RISK

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
    audit_action = ActionEnum.PROCESS_RISK

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


class CustomAutoProcess(RiskMeta):
    name = gettext_lazy("人工执行处理套餐")
    RequestSerializer = CustomAutoProcessReqSerializer
    audit_action = ActionEnum.PROCESS_RISK

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
    audit_action = ActionEnum.PROCESS_RISK

    def perform_request(self, validated_request_data):
        risk = get_object_or_404(Risk, risk_id=validated_request_data["risk_id"])
        origin_data = RiskInfoSerializer(risk).data
        node = get_object_or_404(TicketNode, risk_id=risk.risk_id, id=validated_request_data["node_id"])
        if node.action != ForApprove.__name__:
            raise RiskStatusInvalid(message=gettext("节点类型异常 => %s") % node.action)

        if node.itsm_version == ItsmVersion.V4:
            ticket = node.process_result.get("ticket") or {}
            ticket_id = str(ticket.get("id") or "")
            # 凡带 id 均可以用 itsm_v4 查询/撤销；下方仅当缺 id 时兜底。
            if not ticket_id:
                logger.warning(
                    "[ForceRevokeApproveTicket] legacy itsm ticket without v4 id, skip revoking: node=%s, sn=%s",
                    node.id,
                    ticket.get("sn", ""),
                )
                sync_auto_result(node_id=node.id)
                setattr(risk, "instance_origin_data", origin_data)
                self.add_audit_instance_to_context(instance=RiskAuditInstance(risk))
                return
            # 判断单据状态
            status = get_itsm_ticket_status(ticket_id)
            if status["current_status"] in TicketStatus.get_finished_status():
                sync_auto_result(node_id=node.id)
                return
            # 关单（强制撤销审批单据，对应 V4 终止工单 terminate，工单级操作无需 task_id/节点）
            api.bk_itsm_v4.ticket_handle(
                ticket_id=ticket_id,
                operator=bk_resource_settings.PLATFORM_AUTH_ACCESS_USERNAME,
                action={"method": "terminate", "params": {}},
            )
        else:
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
    audit_action = ActionEnum.PROCESS_RISK

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
        # 失败时回源补齐各失败节点的 error_message，保证重试快照固化到真实的失败现场
        if status.get("state") in SOPSTaskStatus.get_failed_status():
            fill_failure_info(status, task_id=task_id)
        # 对每个失败的节点（含子流程内嵌套的失败节点），获取节点输入并重试
        for item in iter_status_nodes(status):
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
            # 重试前快照：固化本次被覆盖前的失败现场（error_message 等），仅 append 不覆盖
            retry_history = node.process_result.get("retry_history") or []
            retry_history.append(
                {
                    "time": timezone.localtime().strftime(api_settings.DATETIME_FORMAT),
                    "operator": get_request_username(),
                    "attempts": extract_attempt_records(status),
                }
            )
            node.process_result["retry_history"] = retry_history
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
    audit_action = ActionEnum.PROCESS_RISK

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


@dataclass(frozen=True)
class RiskExportResolvedRequest:
    """风险导出解析结果：后续导出链路只消费已确定的风险 ID。"""

    username: str
    risk_ids: List[str]
    risk_view_type: str


class RiskExportRiskIDResolver:
    """将精确 ID 或列表筛选条件解析为导出使用的风险 ID，并保证权限只校验一次。"""

    # 多取 1 条即可判断是否超过导出上限，避免为了判断超限拉取全量风险 ID。
    OVER_LIMIT_DETECT_EXTRA = 1

    def __init__(self, username: str, risk_limit: Optional[int] = None) -> None:
        self.username = username
        self.risk_limit = settings.RISK_EXPORT_ASYNC_MAX_COUNT if risk_limit is None else risk_limit

    def resolve(self, validated_request_data: dict) -> RiskExportResolvedRequest:
        """根据请求模式解析风险 ID：risk_ids 为勾选导出，filters 为范围筛选导出。"""

        request_data = dict(validated_request_data)
        risk_view_type = request_data.pop("risk_view_type", "")
        risk_ids = request_data.pop("risk_ids", None)
        filters = request_data.pop("filters", {}) or {}
        if risk_ids:
            return self._resolve_explicit_risk_ids(risk_ids=risk_ids, risk_view_type=risk_view_type)
        return self._resolve_filter_risk_ids(filter_data=filters, risk_view_type=risk_view_type)

    def _resolve_explicit_risk_ids(self, risk_ids: List[str], risk_view_type: str) -> RiskExportResolvedRequest:
        """精确 ID 模式在入口统一鉴权，后续导出服务不再重复校验权限。"""

        risks = Risk.load_authed_risks(action=ActionEnum.LIST_RISK, username=self.username).filter(risk_id__in=risk_ids)
        authed_risk_ids = set(risks.values_list("risk_id", flat=True))
        no_authed_risk_ids = set(risk_ids) - authed_risk_ids
        if no_authed_risk_ids:
            raise ExportRiskNoPermission(risk_ids=",".join(sorted(no_authed_risk_ids)))
        return RiskExportResolvedRequest(
            username=self.username,
            risk_ids=risk_ids,
            risk_view_type=risk_view_type,
        )

    def _resolve_filter_risk_ids(self, filter_data: dict, risk_view_type: str) -> RiskExportResolvedRequest:
        """范围筛选模式根据视图复用对应列表资源，并统一校验空结果和导出上限。"""

        risk_cls = ListRiskMetaBase.risk_cls_map.get(risk_view_type)
        if not risk_cls:
            raise drf_serializers.ValidationError(gettext("风险视图类型无效"))

        risk_ids = self._load_filter_risk_ids(risk_cls=risk_cls, filter_data=filter_data)
        self._validate_filter_risk_ids(risk_ids)
        return RiskExportResolvedRequest(
            username=self.username,
            risk_ids=risk_ids,
            risk_view_type=risk_view_type,
        )

    def _load_filter_risk_ids(self, risk_cls: Type[ListRisk], filter_data: dict) -> List[str]:
        """按视图和筛选条件加载风险 ID；多取 1 条用于判断是否超过导出上限。"""

        risk_ids = risk_cls().load_filter_risk_ids(
            validated_request_data=filter_data,
            username=self.username,
            risk_limit=self.risk_limit + self.OVER_LIMIT_DETECT_EXTRA,
        )
        return risk_ids

    def _validate_filter_risk_ids(self, risk_ids: List[str]) -> None:
        """统一校验范围筛选结果，避免空结果或超过导出上限继续进入导出流程。"""

        if not risk_ids:
            raise drf_serializers.ValidationError(gettext("当前筛选条件未命中风险"))
        if len(risk_ids) > self.risk_limit:
            raise drf_serializers.ValidationError(gettext("当前筛选结果超过导出上限，请缩小筛选范围"))


def build_async_risk_export_response(username: str, risk_ids: List[str], risk_view_type: str) -> Response:
    """提交异步导出任务并返回 202 响应。"""

    requested_at = timezone.localtime().strftime(api_settings.DATETIME_FORMAT)
    task = export_risks_to_mail.apply_async(
        kwargs={
            "username": username,
            "risk_ids": risk_ids,
            "risk_view_type": risk_view_type,
            "requested_at": requested_at,
        }
    )
    serializer = RiskExportAsyncRespSerializer(
        data={
            "export_type": "async",
            "task_id": task.id,
            "notice_users": [username],
            "total": len(risk_ids),
            "message": gettext("导出任务已提交，完成后将邮件通知"),
        }
    )
    serializer.is_valid(raise_exception=True)
    return Response(data=serializer.data, status=202)


class RiskExport(RiskMeta):
    """风险导出

    根据风险数量自动选择导出方式：不超过同步阈值时直接返回 XLSX 文件；超过阈值时提交异步导出任务，
    返回 HTTP 202 和任务信息，任务完成后通过邮件附件通知当前用户。
    """

    name = gettext_lazy("风险导出")
    RequestSerializer = RiskExportReqSerializer

    def perform_request(self, validated_request_data):
        username = get_request_username()
        resolved = RiskExportRiskIDResolver(username=username).resolve(validated_request_data)
        service = RiskExportService(
            username=resolved.username,
            risk_ids=resolved.risk_ids,
            risk_view_type=resolved.risk_view_type,
        )

        if len(resolved.risk_ids) > settings.RISK_EXPORT_SYNC_MAX_COUNT:
            return build_async_risk_export_response(
                resolved.username,
                resolved.risk_ids,
                resolved.risk_view_type,
            )

        export_file = service.build_export_file()
        stream_response = FileResponse(export_file.file, as_attachment=True, filename=export_file.filename)
        stream_response["Content-Type"] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        return stream_response


class RiskExportAsync(RiskMeta):
    """主动发起风险异步导出，提交任务后通过邮件附件通知当前用户。"""

    name = gettext_lazy("风险异步导出")
    RequestSerializer = RiskExportReqSerializer

    def perform_request(self, validated_request_data):
        username = get_request_username()
        resolved = RiskExportRiskIDResolver(username=username).resolve(validated_request_data)
        return build_async_risk_export_response(
            resolved.username,
            resolved.risk_ids,
            resolved.risk_view_type,
        )


# ============== 风险报告相关接口 ==============
class ListEventFieldsByStrategy(RiskMeta):
    """
    新增接口：根据策略获取对应的事件字段；支持返回所有策略的事件字段（不传 strategy_ids）
    返回结构化字段 key，用于前端筛选构建
    """

    name = gettext_lazy("根据策略获取事件字段")
    RequestSerializer = ListEventFieldsByStrategyRequestSerializer
    ResponseSerializer = ListEventFieldsByStrategyResponseSerializer
    many_response_data = True

    def perform_request(self, validated_request_data):
        strategy_ids = validated_request_data.get("strategy_ids")
        if strategy_ids:
            strategies = Strategy.objects.filter(strategy_id__in=strategy_ids)
        else:
            strategies = Strategy.objects.all()

        extended = set()
        for s in strategies:
            for cfg in s.event_data_field_configs or []:
                field_name = cfg.get("field_name")
                display_name = cfg.get("display_name") or field_name
                if field_name:
                    extended.add((field_name, display_name))

        basic = [(field_name, str(label)) for field_name, label in EventBasicField.choices]
        basic_field_names = {field_name for field_name, _ in basic}
        extended = [
            (field_name, display_name) for field_name, display_name in extended if field_name not in basic_field_names
        ]

        basic_results = [
            {
                "field_name": field_name,
                "display_name": display_name,
                "id": f"{display_name}:{field_name}",
                "type": "basic_event_field",
            }
            for field_name, display_name in basic
        ]
        extended_results = [
            {"field_name": field_name, "display_name": display_name, "id": f"{display_name}:{field_name}"}
            for field_name, display_name in extended
        ]
        return basic_results + extended_results


# ============== 风险报告相关接口 ==============


class ListRiskBrief(RiskMeta):
    """
    获取风险简要列表

    用于策略配置时选择风险单进行预览。
    无权限控制，返回精简数据。
    """

    name = gettext_lazy("获取风险简要列表")
    RequestSerializer = ListRiskBriefRequestSerializer
    ResponseSerializer = ListRiskBriefResponseSerializer
    many_response_data = True

    def perform_request(self, validated_request_data):
        queryset = Risk.objects.all()

        # 策略过滤
        strategy_id = validated_request_data.get("strategy_id")
        if strategy_id:
            queryset = queryset.filter(strategy_id=strategy_id)

        # 时间范围过滤（必填）
        start_time = validated_request_data["start_time"]
        end_time = validated_request_data["end_time"]
        queryset = queryset.filter(created_at__gte=start_time, created_at__lte=end_time)

        # 只返回精简字段，不限制数量
        # 优化：使用 values 减少数据传输量
        return queryset.values("risk_id", "title", "strategy_id", "created_at").order_by("-created_at")


class NL2RiskFilter(RiskMeta):
    name = gettext_lazy("自然语言转风险筛选条件")
    RequestSerializer = NL2RiskFilterRequestSerializer
    ResponseSerializer = NL2RiskFilterResponseSerializer
    audit_action = ActionEnum.LIST_RISK

    def perform_request(self, validated_request_data):
        query = validated_request_data["query"]
        tags = validated_request_data.get("tags", [])
        strategies = validated_request_data.get("strategies", [])
        scenes = validated_request_data.get("scenes", [])
        scope_type = validated_request_data.get(ScopeQueryField.SCOPE_TYPE)
        scope_id = validated_request_data.get(ScopeQueryField.SCOPE_ID)
        input_thread_id = validated_request_data.get("thread_id")
        thread_id = input_thread_id or str(uuid.uuid4())
        risk_view_type = validated_request_data.get("risk_view_type", RiskViewType.ALL)
        username = get_request_username()
        metric_started_at = time.perf_counter()

        with start_observation_span(
            "risk.nl2risk_filter.generate",
            attributes={
                "bk_audit.service": "risk",
                "bk_audit.operation": "nl2risk_filter",
                "bk_audit.scope.type": scope_type,
                "bk_audit.scope.has_scope_id": bool(scope_id),
                "bk_audit.nl2risk.tags_count": len(tags),
                "bk_audit.nl2risk.strategies_count": len(strategies),
                "bk_audit.nl2risk.scenes_count": len(scenes),
                "bk_audit.nl2risk.has_thread_id": bool(input_thread_id),
            },
        ) as span:
            request_params = {
                "query": query,
                "tags": tags,
                "strategies": strategies,
                "scenes": scenes,
                "scope_type": scope_type,
                "scope_id": scope_id,
                "thread_id": thread_id,
                "risk_view_type": risk_view_type,
            }
            user_message = build_nl2risk_user_message(
                query=query,
                tags=tags,
                strategies=strategies,
                username=username,
                scenes=scenes,
                scope_type=scope_type,
                scope_id=scope_id,
            )

            try:
                with start_observation_span(
                    "risk.nl2risk_filter.call_ai_agent",
                    attributes={
                        "bk_audit.service": "risk",
                        "bk_audit.operation": "nl2risk_filter",
                        "bk_audit.stage": "call_ai_agent",
                        "bk_audit.scope.type": scope_type,
                    },
                ):
                    result = api.bk_plugins_ai_agent.chat_completion(
                        agent_code=AIAgentCode.RISK_SEARCH,
                        user=username,
                        input=user_message,
                        chat_history=[],
                        execute_kwargs={"stream": False, "thread_id": thread_id},
                    )
            except AgentRateLimited:
                raise
            except Exception as e:
                logger.exception("[NL2RiskFilter] AI platform call failed: %s", e)
                NL2RiskFilterLog.save_nl2risk_filter_log(
                    username=username,
                    query=query,
                    request_params=request_params,
                    response_data={},
                    status=NL2RiskFilterLogStatus.API_ERROR,
                    error_message=str(e),
                    risk_view_type=risk_view_type,
                )
                NL2RiskFilterFailedEvent(
                    target="nl2risk_filter",
                    context={
                        "status": NL2RiskFilterLogStatus.API_ERROR,
                        "scope_type": scope_type,
                        "error_type": e.__class__.__name__,
                    },
                    extra={"error": str(e)},
                ).async_report()
                report_observation_metric(
                    name="risk.nl2risk_filter.generate",
                    started_at=metric_started_at,
                    status=OBSERVATION_METRIC_STATUS_ERROR,
                    error_type=e.__class__.__name__,
                    dimensions={
                        "service": "risk",
                        "operation": "nl2risk_filter",
                        "scope_type": scope_type,
                        "business_status": NL2RiskFilterLogStatus.API_ERROR,
                    },
                )
                raise NL2RiskFilterServiceError()

            raw_text = str(result)
            with start_observation_span(
                "risk.nl2risk_filter.parse_result",
                attributes={
                    "bk_audit.service": "risk",
                    "bk_audit.operation": "nl2risk_filter",
                    "bk_audit.stage": "parse_result",
                },
            ):
                filter_conditions, message = extract_filter_conditions_from_ai_result(result)
            filter_conditions = attach_datetime_origin(filter_conditions)
            response_data = {"filter_conditions": filter_conditions, "thread_id": thread_id, "message": message}

            status = NL2RiskFilterLogStatus.SUCCESS if filter_conditions else NL2RiskFilterLogStatus.PARSE_FAILED
            metric_status = (
                OBSERVATION_METRIC_STATUS_SUCCESS
                if status == NL2RiskFilterLogStatus.SUCCESS
                else OBSERVATION_METRIC_STATUS_ERROR
            )
            metric_error_type = "" if status == NL2RiskFilterLogStatus.SUCCESS else status
            set_span_attributes(
                span,
                {
                    "bk_audit.nl2risk.status": status,
                    "bk_audit.nl2risk.filter_condition_count": len(filter_conditions),
                },
            )
            NL2RiskFilterLog.save_nl2risk_filter_log(
                username=username,
                query=query,
                request_params=request_params,
                response_data=response_data,
                status=status,
                risk_view_type=risk_view_type,
                result=raw_text,
                message=message,
            )
            report_observation_metric(
                name="risk.nl2risk_filter.generate",
                started_at=metric_started_at,
                status=metric_status,
                error_type=metric_error_type,
                dimensions={
                    "service": "risk",
                    "operation": "nl2risk_filter",
                    "scope_type": scope_type,
                    "business_status": status,
                },
            )

            return response_data


class ListEventFieldsByStrategyBrief(ListEventFieldsByStrategy):
    """简化版事件字段接口（供 APIGW/MCP 使用）

    复用 ListEventFieldsByStrategy 的查询逻辑，对结果做简化：
    1. 按 field_name 去重合并（优先保留有意义的 display_name）
    2. field_name == display_name 时只返回 field_name
    """

    name = gettext_lazy("获取事件字段（简化版）")
    RequestSerializer = EventFieldsForAIRequestSerializer
    ResponseSerializer = EventFieldsBriefResponseSerializer
    many_response_data = False

    def perform_request(self, validated_request_data):
        strategy_ids = validated_request_data.get("strategy_ids", [])
        raw_results = super().perform_request({"strategy_ids": strategy_ids})

        field_map = {}
        for item in raw_results:
            fn = item["field_name"]
            dn = item["display_name"]
            if fn not in field_map:
                field_map[fn] = dn
            elif field_map[fn] == fn and dn != fn:
                field_map[fn] = dn

        keywords = [k.strip().lower() for k in validated_request_data.get("keyword", "").split(",") if k.strip()]

        results = []
        for fn, dn in sorted(field_map.items()):
            if keywords:
                fn_lower, dn_lower = fn.lower(), dn.lower()
                if not any(kw in fn_lower or kw in dn_lower for kw in keywords):
                    continue
            entry = {"field_name": fn}
            if dn != fn:
                entry["display_name"] = dn
            results.append(entry)
            if len(results) >= settings.AI_EVENT_FIELDS_BRIEF_MAX:
                break
        return {"results": results}


class UpdateRisk(RiskMeta):
    """
    编辑风险

    目前支持编辑风险单标题。
    """

    name = gettext_lazy("编辑风险")
    audit_action = ActionEnum.EDIT_RISK
    RequestSerializer = UpdateRiskRequestSerializer

    # 允许更新的字段
    UPDATABLE_FIELDS = ["title"]

    def perform_request(self, validated_request_data):
        risk_id = validated_request_data.pop("risk_id")
        risk = get_object_or_404(Risk, risk_id=risk_id)
        origin_data = RiskInfoSerializer(risk).data

        # 动态更新字段
        update_fields = []
        for key in self.UPDATABLE_FIELDS:
            if key not in validated_request_data:
                continue
            new_val = validated_request_data[key]
            old_val = getattr(risk, key, Empty())
            if isinstance(old_val, Empty) or old_val == new_val:
                continue
            setattr(risk, key, new_val)
            update_fields.append(key)

        if update_fields:
            risk.save(update_fields=update_fields)

        setattr(risk, "instance_origin_data", origin_data)
        self.add_audit_instance_to_context(instance=RiskAuditInstance(risk))
        return RiskInfoSerializer(risk).data


class ListNL2RiskFilterLog(RiskMeta):
    """查询当前用户的 NL2RiskFilter 历史记录"""

    name = gettext_lazy("NL2RiskFilter查询历史")
    RequestSerializer = ListNL2RiskFilterLogRequestSerializer
    ResponseSerializer = NL2RiskFilterLogResponseSerializer
    many_response_data = True
    audit_action = ActionEnum.LIST_RISK

    def perform_request(self, validated_request_data):
        username = get_request_username()
        queryset = NL2RiskFilterLog.objects.filter(created_by=username)

        # 状态过滤
        status = validated_request_data.get("status")
        if status:
            queryset = queryset.filter(status=status)

        # 风险视图类型过滤
        risk_view_type = validated_request_data.get("risk_view_type")
        if risk_view_type:
            queryset = queryset.filter(risk_view_type=risk_view_type)

        # 时间范围过滤
        start_time = validated_request_data.get("start_time")
        end_time = validated_request_data.get("end_time")
        if start_time:
            queryset = queryset.filter(created_at__gte=start_time)
        if end_time:
            queryset = queryset.filter(created_at__lte=end_time)

        if validated_request_data.get("deduplicate", True):
            latest_log_ids = queryset.order_by().values("query_hash").annotate(latest_id=Max("id")).values("latest_id")
            queryset = queryset.filter(pk__in=Subquery(latest_log_ids))

        # 分页由框架 enable_paginate 自动处理
        return queryset.order_by("-id")


PENDING_CONFIRM_REQUIRED = "风险状态不是待确认"


class ConfirmRiskResource(RiskMeta):
    """确认风险"""

    name = gettext_lazy("确认风险")
    RequestSerializer = ConfirmRiskRequestSerializer

    def perform_request(self, validated_request_data):
        risk_id = validated_request_data["risk_id"]
        description = validated_request_data.get("description", "")
        risk = get_object_or_404(Risk, risk_id=risk_id)

        # 验证状态
        if risk.display_status != RiskDisplayStatus.PENDING_CONFIRM:
            from rest_framework.exceptions import ValidationError

            raise ValidationError(PENDING_CONFIRM_REQUIRED)

        username = get_request_username(validated_request_data.get("_request"))

        # 执行确认
        ConfirmRisk(risk_id=risk_id, operator=username).run(username=username, description=description)
        return {"success": True}


class ConfirmAsMisReportResource(RiskMeta):
    """确认为误报"""

    name = gettext_lazy("确认为误报")
    RequestSerializer = ConfirmAsMisReportRequestSerializer

    def perform_request(self, validated_request_data):
        risk_id = validated_request_data["risk_id"]
        description = validated_request_data.get("description", "")

        risk = get_object_or_404(Risk, risk_id=risk_id)

        # 验证状态
        if risk.display_status != RiskDisplayStatus.PENDING_CONFIRM:
            from rest_framework.exceptions import ValidationError

            raise ValidationError(PENDING_CONFIRM_REQUIRED)

        username = get_request_username(validated_request_data.get("_request"))

        # 执行误报确认
        from services.web.risk.handlers.ticket import ConfirmAsMisReport

        ConfirmAsMisReport(risk_id=risk_id, operator=username).run(username=username, description=description)
        return {"success": True}


# ---------------------------------------------------------------------------
# 批量处理：选单 / 执行管道 / 可执行动作与预览
# ---------------------------------------------------------------------------

BATCH_REASON_STRATEGY_SCENE = "所选风险策略不同/场景不同，不支持批量处理套餐"
BATCH_REASON_MISSING = "部分风险不存在或已被删除"
BATCH_REASON_UNAVAILABLE = "所选风险无法批量处理"

_ACTION_LABELS = {
    "confirm": ConfirmRisk.name,
    "close": CustomCloseRisk.name,
    "trans": TransOperator.name,
    "auto_process": ResourceVisibilityType.PROCESS_APPLICATION.label,
    "misreport": MisReport.name,
    "unmisreport": ReOpenMisReport.name,
}
_BATCH_ACTIONS = tuple(_ACTION_LABELS)
_PROCESS_ACTIONS = frozenset({"close", "trans", "auto_process", "misreport"})
_CONFIRM_ACTIONS = frozenset({"confirm", "misreport"})
_CLOSED_ACTIONS = frozenset({"misreport"})
_MISREPORT_CLOSED_ACTIONS = frozenset({"unmisreport"})
_BLOCKING_STATUS = frozenset({RiskStatus.FOR_APPROVE, RiskStatus.AUTO_PROCESS})
_BLOCKING_DISPLAY = frozenset({RiskDisplayStatus.FOR_APPROVE, RiskDisplayStatus.AUTO_PROCESS})


class _SelectionError(Enum):
    OVER_LIMIT = "over_limit"
    MISSING = "missing"
    EMPTY = "empty"


@dataclass(frozen=True)
class _Reject:
    """这条风险不执行，reason 写入 failed。"""

    reason: str


@dataclass
class _BulkSelection:
    risk_ids: List[str]
    risks: List[Risk]
    risk_map: Dict[str, Risk]
    selected_count: int
    error: Optional[_SelectionError] = None


def _selection_token(values: Sequence[Any]) -> Tuple[bool, Optional[str]]:
    """去空白后是否完全相同。只选一条视为相同；多条空值、空值与有值混选都不算相同。"""

    tokens = ["" if value is None else str(value).strip() for value in values]
    if not tokens:
        return False, None
    if len(tokens) == 1:
        return True, tokens[0] or None
    if any(not token for token in tokens) or len(set(tokens)) != 1:
        return False, None
    return True, tokens[0]


def resolve_bulk_risk_ids(data: dict, username: str, limit: int = BULK_ACTION_MAX_RISK_IDS) -> List[str]:
    """权限校验用：勾选直接返回 risk_ids；筛选复用列表的 load_filter_risk_ids，只取上限 + 1 条。"""

    if not isinstance(data, dict):
        return []
    risk_ids = data.get("risk_ids") or []
    if risk_ids or not data.get("filters"):
        return list(risk_ids)
    serializer = ListRiskRequestSerializer(data=data["filters"])
    serializer.is_valid(raise_exception=True)
    return ListRisk().load_filter_risk_ids(serializer.validated_data, username=username, risk_limit=limit + 1)


def _load_bulk_selection(data: dict, limit: int, *, require_all_exist: bool = False) -> _BulkSelection:
    """勾选或筛选加载风险。require_all_exist 仅预览使用：缺条则整批不可处理。"""

    data = data or {}
    risk_ids = list(data.get("risk_ids") or [])
    if risk_ids:
        if len(risk_ids) > limit:
            return _BulkSelection([], [], {}, len(risk_ids), _SelectionError.OVER_LIMIT)
        risks = list(Risk.objects.filter(risk_id__in=risk_ids))
        risk_map = {risk.risk_id: risk for risk in risks}
        if require_all_exist and len(risks) != len(risk_ids):
            return _BulkSelection(risk_ids, risks, risk_map, len(risks), _SelectionError.MISSING)
        return _BulkSelection(risk_ids, risks, risk_map, len(risk_ids), None)

    matched_ids = ListRisk().load_filter_risk_ids(
        dict(data.get("filters") or {}),
        username=get_request_username(),
        risk_limit=limit + 1,
    )
    if len(matched_ids) > limit:
        return _BulkSelection([], [], {}, len(matched_ids), _SelectionError.OVER_LIMIT)
    if not matched_ids:
        return _BulkSelection([], [], {}, 0, _SelectionError.EMPTY)
    risks = list(Risk.objects.filter(risk_id__in=matched_ids))
    risk_map = {risk.risk_id: risk for risk in risks}
    return _BulkSelection([risk.risk_id for risk in risks], risks, risk_map, len(risks), None)


def _prepare_bulk_risks(validated_request_data: dict, limit: int) -> Tuple[List[str], List[Risk], Dict[str, Risk]]:
    pick = _load_bulk_selection(validated_request_data, limit)
    if pick.error is _SelectionError.OVER_LIMIT:
        raise BulkSelectionOverLimit()
    if pick.error is _SelectionError.EMPTY:
        raise drf_serializers.ValidationError(gettext("当前筛选条件未命中风险"))
    return pick.risk_ids, pick.risks, pick.risk_map


def _fail_all(risk_ids: Sequence[str], reason: str) -> Dict[str, Any]:
    return {"success_count": 0, "failed": [{"risk_id": rid, "reason": reason} for rid in risk_ids]}


def _description_renderer(template: str, risks: Sequence[Risk]):
    """按当前风险渲染说明模板。event_data 只在策略唯一时可用。"""

    from services.web.risk.placeholder import render_string

    username = get_request_username()
    allow_event_data, _token = _selection_token([risk.strategy_id for risk in risks])

    def render(risk: Risk) -> str:
        return render_string(template, risk=risk, operator=username, allow_event_data=allow_event_data)

    return render


def _collect_payloads(risk_ids: Sequence[str], risk_map: Dict[str, Risk], build):
    """build(risk) 返回 dict 则执行，返回 _Reject 则记为该条失败原因。"""

    failed: List[Dict[str, str]] = []
    payloads = []
    for rid in risk_ids:
        risk = risk_map.get(rid)
        if risk is None:
            failed.append({"risk_id": rid, "reason": gettext("风险不存在")})
            continue
        built = build(risk)
        if isinstance(built, _Reject):
            failed.append({"risk_id": rid, "reason": built.reason})
            continue
        payloads.append(built)
    return payloads, failed


def _complete_bulk(payloads: Sequence[dict], failed: List[Dict[str, str]], run_item) -> Dict[str, Any]:
    """用 Resource.bulk_request 并发执行。单条失败记入 failed，不中断其余条目。"""

    payloads = list(payloads)
    if not payloads:
        return {"success_count": 0, "failed": failed}

    from blueapps.utils.local import request_local
    from blueapps.utils.request_provider import get_local_request

    parent_request = get_local_request()

    class _BatchRunner(RiskMeta):
        def perform_request(self, validated_request_data):
            if parent_request is not None:
                request_local.request = parent_request
            try:
                run_item(validated_request_data)
            except Exception as exc:
                logger.exception("bulk item failed for %s", validated_request_data.get("risk_id"))
                return {"success": False, "reason": str(exc)}
            return {"success": True}

    try:
        results = _BatchRunner().bulk_request(payloads, ignore_exceptions=True)
    except Exception as exc:
        logger.exception("bulk_request failed")
        failed.extend({"risk_id": item.get("risk_id", ""), "reason": str(exc)} for item in payloads)
        return {"success_count": 0, "failed": failed}

    success_count = 0
    for payload, result in zip(payloads, results or []):
        if isinstance(result, dict) and result.get("success") is False:
            failed.append(
                {
                    "risk_id": payload.get("risk_id", ""),
                    "reason": result.get("reason") or gettext("执行失败"),
                }
            )
            continue
        success_count += 1
    return {"success_count": success_count, "failed": failed}


def _risk_batch_actions(risk: Risk) -> Optional[Set[str]]:
    """返回该风险可执行的批量动作。None 表示自动处理审批中或套餐处理中，整批不可处理。"""

    if risk.status in _BLOCKING_STATUS or risk.display_status in _BLOCKING_DISPLAY:
        return None
    if risk.status == RiskStatus.PENDING_CONFIRM or risk.display_status == RiskDisplayStatus.PENDING_CONFIRM:
        return set(_CONFIRM_ACTIONS)
    if risk.display_status in (RiskDisplayStatus.AWAIT_PROCESS, RiskDisplayStatus.PROCESSING):
        return set(_PROCESS_ACTIONS)
    if risk.display_status == RiskDisplayStatus.CLOSED or risk.status == RiskStatus.CLOSED:
        if risk.risk_label == RiskLabel.MISREPORT:
            return set(_MISREPORT_CLOSED_ACTIONS)
        return set(_CLOSED_ACTIONS)
    return set()


def _status_label(risk: Risk) -> str:
    if (
        risk.display_status == RiskDisplayStatus.CLOSED or risk.status == RiskStatus.CLOSED
    ) and risk.risk_label == RiskLabel.MISREPORT:
        return gettext("已误报")
    display = getattr(risk, "display_status", None)
    if display in RiskDisplayStatus.values:
        return value_to_label(RiskDisplayStatus, display)
    status = getattr(risk, "status", None)
    if status in RiskStatus.values:
        return value_to_label(RiskStatus, status)
    return str(display or status or "")


def _blocking_status_labels() -> tuple:
    return (
        value_to_label(RiskDisplayStatus, RiskDisplayStatus.FOR_APPROVE),
        value_to_label(RiskDisplayStatus, RiskDisplayStatus.AUTO_PROCESS),
    )


def _join_status_reason(risks: Sequence[Risk], pred, detail: str, *, fallback: Sequence[str] = ()) -> str:
    labels: List[str] = []
    for risk in risks:
        if not pred(risk):
            continue
        label = _status_label(risk)
        if label and label not in labels:
            labels.append(label)
    labels = labels or list(fallback)
    if not labels:
        return ""
    return gettext("所选风险包含%(statuses)s，%(detail)s") % {
        "statuses": "、".join(labels),
        "detail": detail,
    }


def _reject_reason(action: str, risk: Risk) -> str:
    """执行失败原因与预览里该动作的 disabled_reason 一致。"""

    if _risk_batch_actions(risk) is None:
        return _join_status_reason(
            [risk],
            lambda item: _risk_batch_actions(item) is None,
            gettext("不支持批量处理"),
            fallback=_blocking_status_labels(),
        )

    def misses(item: Risk) -> bool:
        actions = _risk_batch_actions(item)
        return actions is None or action not in actions

    return _join_status_reason(
        [risk],
        misses,
        gettext("不支持%(action)s") % {"action": _ACTION_LABELS[action]},
    )


def _disabled_preview(reason: str, selected_count: int) -> Dict[str, Any]:
    return {
        "batch_enabled": False,
        "batch_disabled_reason": reason,
        "actions": {act: {"enabled": False, "disabled_reason": reason} for act in _BATCH_ACTIONS},
        "unique_strategy_id": None,
        "scene_id": None,
        "selected_count": selected_count,
    }


def _auto_process_extra_reasons(risks: Sequence[Risk], strategy_unique: bool, scene_unique: bool) -> List[str]:
    reasons: List[str] = []
    if len(risks) > BULK_AUTO_PROCESS_MAX_RISK_IDS:
        reasons.append(str(BulkSelectionOverLimit.MESSAGE))
    if not strategy_unique or not scene_unique:
        reasons.append(gettext(BATCH_REASON_STRATEGY_SCENE))
    return reasons


def _build_batch_actions_preview(risks: Sequence[Risk]) -> Dict[str, Any]:
    """按状态取交集。处理套餐再看策略、场景和数量上限。

    整批被审批中或套餐处理中挡住时，所有动作共用同一句原因。
    否则每个不可用动作只列出挡掉它的状态；策略或场景不同只写在处理套餐上。
    """

    selected_count = len(risks)
    if any(_risk_batch_actions(risk) is None for risk in risks):
        return _disabled_preview(
            _join_status_reason(
                risks,
                lambda risk: _risk_batch_actions(risk) is None,
                gettext("不支持批量处理"),
                fallback=_blocking_status_labels(),
            ),
            selected_count,
        )

    allowed = set.intersection(*(_risk_batch_actions(risk) or set() for risk in risks)) if risks else set()
    strategy_unique, strategy_token = _selection_token([risk.strategy_id for risk in risks])
    scene_unique, scene_token = _selection_token([risk.scene_id for risk in risks])

    auto_reasons: List[str] = []
    if "auto_process" in allowed:
        auto_reasons = _auto_process_extra_reasons(risks, strategy_unique, scene_unique)
        if auto_reasons:
            allowed.discard("auto_process")

    batch_reason = ""
    if not allowed:
        # 整批无公共可用动作时，汇聚各风险的展示状态，给出具体原因而非笼统文案
        labels = []
        for risk in risks:
            label = _status_label(risk)
            if label and label not in labels:
                labels.append(label)
        if labels:
            batch_reason = gettext("所选风险包含%(statuses)s，不支持批量处理") % {"statuses": "、".join(labels)}
        else:
            batch_reason = gettext(BATCH_REASON_UNAVAILABLE)

    def token_int(unique: bool, token: Optional[str]) -> Optional[int]:
        if not unique or not token:
            return None
        try:
            return int(token)
        except (TypeError, ValueError):
            return None

    actions: Dict[str, Dict[str, Any]] = {}
    for act in _BATCH_ACTIONS:
        if act in allowed:
            actions[act] = {"enabled": True, "disabled_reason": ""}
            continue

        def misses(risk: Risk, action=act) -> bool:
            available = _risk_batch_actions(risk)
            return available is None or action not in available

        reasons: List[str] = []
        status_reason = _join_status_reason(
            risks,
            misses,
            gettext("不支持%(action)s") % {"action": _ACTION_LABELS[act]},
        )
        if status_reason:
            reasons.append(status_reason)
        if act == "auto_process":
            reasons.extend(auto_reasons)
        actions[act] = {"enabled": False, "disabled_reason": "；".join(reasons) or batch_reason}

    return {
        "batch_enabled": bool(allowed),
        "batch_disabled_reason": batch_reason,
        "actions": actions,
        "unique_strategy_id": token_int(strategy_unique, strategy_token),
        "scene_id": token_int(scene_unique, scene_token),
        "selected_count": selected_count,
    }


class BatchActionsPreviewResource(RiskMeta):
    """批量处理弹窗预览：每个动作在当前选中风险下是否可用。"""

    name = gettext_lazy("批量处理预览")
    RequestSerializer = BatchActionsPreviewReqSerializer
    ResponseSerializer = BatchActionsPreviewRespSerializer

    def perform_request(self, validated_request_data):
        pick = _load_bulk_selection(validated_request_data, BULK_ACTION_MAX_RISK_IDS, require_all_exist=True)
        if pick.error is _SelectionError.OVER_LIMIT:
            raise BulkSelectionOverLimit()
        if pick.error is _SelectionError.MISSING:
            return _disabled_preview(gettext(BATCH_REASON_MISSING), pick.selected_count)
        if pick.error is _SelectionError.EMPTY:
            return _disabled_preview(gettext(BULK_SELECTION_REQUIRED), 0)
        return _build_batch_actions_preview(pick.risks)


class BatchConfirmRiskResource(RiskMeta):
    """批量确认风险"""

    name = gettext_lazy("批量确认风险")
    RequestSerializer = BatchConfirmRiskRequestSerializer
    ResponseSerializer = BulkActionRespSerializer

    def perform_request(self, validated_request_data):
        risk_ids, risks, risk_map = _prepare_bulk_risks(validated_request_data, BULK_ACTION_MAX_RISK_IDS)
        render = _description_renderer(validated_request_data.get("description", "") or "", risks)

        def build(risk):
            reject = _reject_reason("confirm", risk)
            if reject:
                return _Reject(reject)
            return {"risk_id": risk.risk_id, "description": render(risk)}

        payloads, failed = _collect_payloads(risk_ids, risk_map, build)
        return _complete_bulk(payloads, failed, lambda item: ConfirmRiskResource().perform_request(item))


class BatchConfirmAsMisReportResource(RiskMeta):
    """批量确认为误报"""

    name = gettext_lazy("批量确认为误报")
    RequestSerializer = BatchConfirmAsMisReportRequestSerializer
    ResponseSerializer = BulkActionRespSerializer

    def perform_request(self, validated_request_data):
        risk_ids, risks, risk_map = _prepare_bulk_risks(validated_request_data, BULK_ACTION_MAX_RISK_IDS)
        render = _description_renderer(validated_request_data.get("description", "") or "", risks)

        def build(risk):
            if risk.display_status != RiskDisplayStatus.PENDING_CONFIRM:
                return _Reject(gettext(PENDING_CONFIRM_REQUIRED))
            return {"risk_id": risk.risk_id, "description": render(risk)}

        payloads, failed = _collect_payloads(risk_ids, risk_map, build)
        return _complete_bulk(payloads, failed, lambda item: ConfirmAsMisReportResource().perform_request(item))


class BulkCustomTransRisk(RiskMeta):
    name = gettext_lazy("批量人工转单")
    RequestSerializer = BulkCustomTransRiskReqSerializer
    ResponseSerializer = BulkActionRespSerializer

    def perform_request(self, validated_request_data):
        from services.web.risk.placeholder import (
            normalize_personnel_refs,
            resolve_personnel_refs,
        )

        risk_ids, risks, risk_map = _prepare_bulk_risks(validated_request_data, BULK_ACTION_MAX_RISK_IDS)
        raw_refs = validated_request_data["new_operators"]
        allow_event_data, _token = _selection_token([risk.strategy_id for risk in risks])
        render = _description_renderer(validated_request_data.get("description", "") or "", risks)

        try:
            normalize_personnel_refs(raw_refs)
        except Exception as exc:
            return _fail_all(risk_ids, f"人员参数非法：{exc}")

        def build(risk):
            reject = _reject_reason("trans", risk)
            if reject:
                return _Reject(reject)
            operators = resolve_personnel_refs(raw_refs, risk=risk, allow_event_data=allow_event_data)
            if not operators:
                return _Reject(gettext("解析后的处理人为空，请检查人员字段引用"))
            return {"risk_id": risk.risk_id, "new_operators": operators, "description": render(risk)}

        payloads, failed = _collect_payloads(risk_ids, risk_map, build)
        return _complete_bulk(payloads, failed, lambda item: CustomTransRisk().perform_request(item))


class BulkCloseRiskResource(RiskMeta):
    """批量人工关单"""

    name = gettext_lazy("批量人工关单")
    RequestSerializer = BulkCloseReqSerializer
    ResponseSerializer = BulkActionRespSerializer

    def perform_request(self, validated_request_data):
        risk_ids, risks, risk_map = _prepare_bulk_risks(validated_request_data, BULK_ACTION_MAX_RISK_IDS)
        render = _description_renderer(validated_request_data.get("description", "") or "", risks)

        def build(risk):
            reject = _reject_reason("close", risk)
            if reject:
                return _Reject(reject)
            return {"risk_id": risk.risk_id, "description": render(risk)}

        payloads, failed = _collect_payloads(risk_ids, risk_map, build)
        return _complete_bulk(payloads, failed, lambda item: CustomCloseRisk().perform_request(item))


class BulkMisreportResource(RiskMeta):
    """批量标记误报：display_status 为待确认时走 ConfirmAsMisReport，其余可误报状态走 MisReport。"""

    name = gettext_lazy("批量标记误报")
    RequestSerializer = BulkMisreportReqSerializer
    ResponseSerializer = BulkActionRespSerializer

    def perform_request(self, validated_request_data):
        risk_ids, risks, risk_map = _prepare_bulk_risks(validated_request_data, BULK_ACTION_MAX_RISK_IDS)
        revoke_process = validated_request_data.get("revoke_process", True)
        username = get_request_username()
        render = _description_renderer(validated_request_data.get("description", "") or "", risks)

        def build(risk):
            reject = _reject_reason("misreport", risk)
            if reject:
                return _Reject(reject)
            return {
                "risk_id": risk.risk_id,
                "description": render(risk),
                "operator": username,
                "revoke_process": revoke_process,
                "as_confirm": risk.display_status == RiskDisplayStatus.PENDING_CONFIRM,
            }

        def run_item(item):
            if item["as_confirm"]:
                ConfirmAsMisReportResource().perform_request(
                    {"risk_id": item["risk_id"], "description": item["description"]}
                )
                return
            MisReport(risk_id=item["risk_id"], operator=item["operator"]).run(
                description=item["description"], revoke_process=item["revoke_process"]
            )

        payloads, failed = _collect_payloads(risk_ids, risk_map, build)
        return _complete_bulk(payloads, failed, run_item)


class BulkUnmisreportResource(RiskMeta):
    """批量解除误报：已关单且标签为误报的风险解除误报并按原流程重开。"""

    name = gettext_lazy("批量解除误报")
    RequestSerializer = BulkUnmisreportReqSerializer
    ResponseSerializer = BulkActionRespSerializer

    def perform_request(self, validated_request_data):
        from services.web.risk.placeholder import (
            normalize_personnel_refs,
            resolve_personnel_refs,
        )

        risk_ids, risks, risk_map = _prepare_bulk_risks(validated_request_data, BULK_ACTION_MAX_RISK_IDS)
        raw_refs = validated_request_data.get("new_operators") or []
        username = get_request_username()

        try:
            normalize_personnel_refs(raw_refs)
        except Exception as exc:
            return _fail_all(risk_ids, gettext("人员参数非法：%(error)s") % {"error": exc})

        def build(risk):
            reject = _reject_reason("unmisreport", risk)
            if reject:
                return _Reject(reject)
            # 未指定处理人时沿用当前处理人，保证重开后单据仍有人跟进
            operators = resolve_personnel_refs(raw_refs, risk=risk) if raw_refs else list(risk.current_operator or [])
            if not operators:
                return _Reject(gettext("解除误报后处理人为空，请指定处理人"))
            return {"risk_id": risk.risk_id, "new_operators": operators, "operator": username}

        def run_item(item):
            ReOpenMisReport(risk_id=item["risk_id"], operator=item["operator"]).run(new_operators=item["new_operators"])

        payloads, failed = _collect_payloads(risk_ids, risk_map, build)
        return _complete_bulk(payloads, failed, run_item)


class BulkAutoProcessResource(RiskMeta):
    """批量执行处理套餐。

    - `pa_params` 中每个 `{value, field}` 结构：若 `value` 内含 `{{...}}` 会按当前风险渲染
    - `{{event_data.*}}` 仅在选中风险策略唯一时生效
    - 策略或场景不唯一时整批失败，不逐条执行
    """

    name = gettext_lazy("批量执行处理套餐")
    RequestSerializer = BulkAutoProcessReqSerializer
    ResponseSerializer = BulkActionRespSerializer

    def perform_request(self, validated_request_data):
        from services.web.risk.placeholder import render_payload

        risk_ids, risks, risk_map = _prepare_bulk_risks(validated_request_data, BULK_AUTO_PROCESS_MAX_RISK_IDS)
        pa_id = validated_request_data["pa_id"]
        pa_params = validated_request_data.get("pa_params") or {}
        auto_close_risk = validated_request_data.get("auto_close_risk", False)
        username = get_request_username()

        if risks:
            strategy_unique, _strategy_token = _selection_token([risk.strategy_id for risk in risks])
            scene_unique, _scene_token = _selection_token([risk.scene_id for risk in risks])
            extra_reasons = _auto_process_extra_reasons(risks, strategy_unique, scene_unique)
            if extra_reasons:
                return _fail_all(risk_ids, "；".join(extra_reasons))
        if ProcessApplication.objects.filter(id=pa_id).first() is None:
            return _fail_all(risk_ids, gettext(PROCESS_APPLICATION_NOT_FOUND))
        allow_event_data, _token = _selection_token([risk.strategy_id for risk in risks])

        def build(risk):
            reject = _reject_reason("auto_process", risk)
            if reject:
                return _Reject(reject)
            return {
                "risk_id": risk.risk_id,
                "pa_id": pa_id,
                "pa_params": render_payload(pa_params, risk=risk, operator=username, allow_event_data=allow_event_data),
                "auto_close_risk": auto_close_risk,
            }

        payloads, failed = _collect_payloads(risk_ids, risk_map, build)
        return _complete_bulk(payloads, failed, lambda item: CustomAutoProcess().perform_request(item))

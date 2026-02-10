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
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Type

from bk_resource import CacheResource, api, resource
from bk_resource.base import Empty
from bk_resource.settings import bk_resource_settings
from bk_resource.utils.cache import CacheTypeItem
from bk_resource.utils.common_utils import ignored
from django.conf import settings
from django.db import transaction
from django.db.models import Case, Count, IntegerField, Q, QuerySet, When
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext, gettext_lazy
from rest_framework.settings import api_settings

from apps.audit.resources import AuditMixinResource
from apps.itsm.constants import TicketOperate, TicketStatus
from apps.meta.constants import ConfigLevelChoices
from apps.meta.models import GlobalMetaConfig, Tag
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
from services.web.databus.constants import (
    ASSET_RISK_BKBASE_RT_ID_KEY,
    ASSET_STRATEGY_BKBASE_RT_ID_KEY,
    ASSET_STRATEGY_TAG_BKBASE_RT_ID_KEY,
    ASSET_TICKET_PERMISSION_BKBASE_RT_ID_KEY,
    DORIS_EVENT_BKBASE_RT_ID_KEY,
)
from services.web.risk.constants import (
    EVENT_EXPORT_FIELD_PREFIX,
    RISK_EXPORT_FILE_NAME_TMP,
    RISK_LEVEL_ORDER_FIELD,
    RISK_SHOW_FIELDS,
    RiskDisplayStatus,
    RiskExportField,
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
from services.web.risk.exceptions import ExportRiskNoPermission
from services.web.risk.handlers import EventHandler
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
    ManualEvent,
    ProcessApplication,
    Risk,
    RiskAuditInstance,
    RiskExperience,
    TicketNode,
    TicketPermission,
    UserType,
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
    ListEventFieldsByStrategyRequestSerializer,
    ListEventFieldsByStrategyResponseSerializer,
    ListRiskBriefRequestSerializer,
    ListRiskBriefResponseSerializer,
    ListRiskMetaRequestSerializer,
    ListRiskRequestSerializer,
    ListRiskResponseSerializer,
    ListRiskStrategyRespSerializer,
    ListRiskTagsRespSerializer,
    ManualEventSerializer,
    ReopenRiskReqSerializer,
    RetrieveRiskStrategyInfoAPIGWRequestSerializer,
    RetrieveRiskStrategyInfoAPIGWResponseSerializer,
    RetrieveRiskStrategyInfoResponseSerializer,
    RetryAutoProcessReqSerializer,
    RiskExportReqSerializer,
    RiskInfoSerializer,
    TicketNodeSerializer,
    UpdateRiskLabelReqSerializer,
    UpdateRiskRequestSerializer,
)
from services.web.risk.tasks import (
    _build_manual_event_time_range,
    process_one_risk,
    sync_auto_result,
)
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
        nodes = TicketNode.objects.filter(risk_id=risk["risk_id"]).order_by("timestamp")
        risk["ticket_history"] = TicketNodeSerializer(nodes, many=True).data
        risk["unsynced_events"] = self._load_unsynced_manual_events(risk_obj=risk_obj)
        return risk

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
        return strategy or {}


class RetrieveRiskStrategyInfoAPIGW(RiskMeta):
    name = gettext_lazy("获取风险策略信息(APIGW)")
    RequestSerializer = RetrieveRiskStrategyInfoAPIGWRequestSerializer
    ResponseSerializer = RetrieveRiskStrategyInfoAPIGWResponseSerializer
    audit_action = None

    def perform_request(self, validated_request_data):
        from core.utils import tools as core_tools

        core_tools.get_app_info()
        risk: Risk = get_object_or_404(Risk, risk_id=validated_request_data["risk_id"])
        strategy = Strategy.objects.filter(strategy_id=risk.strategy_id).first()
        if not strategy:
            return {}

        lite_mode = validated_request_data.get("lite_mode", True)
        serializer = RetrieveRiskStrategyInfoAPIGWResponseSerializer(strategy, lite_mode=lite_mode)
        return serializer.data


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
    STORAGE_SUFFIX = "doris"

    def perform_request(self, validated_request_data):
        request = validated_request_data.pop("_request")
        order_field = validated_request_data.pop("order_field", "-event_time")
        use_bkbase = bool(validated_request_data.pop("use_bkbase", False))
        event_filters = validated_request_data.pop("event_filters", [])
        self._duplicate_event_field_map: Dict[int, Dict[str, Set[str]]] = {}
        thedate_range = self._extract_thedate_range(validated_request_data)
        base_queryset = self.load_risks(validated_request_data)
        base_queryset = self._filter_queryset_by_event_data_fields(base_queryset, event_filters)

        if use_bkbase:
            paged_risks, page, sql_statements = self.retrieve_via_bkbase(
                base_queryset=base_queryset,
                request=request,
                order_field=order_field,
                event_filters=event_filters,
                thedate_range=thedate_range,
            )
            return BkBaseResponseAssembler(self, ListRiskResponseSerializer).build_response(
                paged_risks, page, sql_statements
            )

        paged_risks, page, risk_ids = self.retrieve_via_db(
            base_queryset=base_queryset, request=request, order_field=order_field
        )

        experiences = self._fetch_experiences(risk_ids)
        for risk in paged_risks:
            setattr(risk, "experiences", experiences.get(risk.risk_id, 0))

        response = page.get_paginated_response(
            data=ListRiskResponseSerializer(instance=paged_risks, many=True).data
        ).data
        response["sql"] = []
        return response

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

    def retrieve_via_db(self, base_queryset: QuerySet, request, order_field: str):
        risks = self._apply_ordering(base_queryset, order_field).only("pk")
        paged_queryset, page = paginate_queryset(
            queryset=risks, request=request, base_queryset=Risk.annotated_queryset()
        )
        paged_queryset = self._apply_ordering(Risk.prefetch_strategy_tags(paged_queryset), order_field)
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

        strategy_ids = list(queryset.values_list("strategy_id", flat=True).distinct())
        if not strategy_ids:
            return queryset.none()

        # 使用JSONField contains能力在数据库侧完成过滤，避免加载并解析所有配置
        strategy_queryset = Strategy.objects.filter(strategy_id__in=strategy_ids)

        for item in event_filters:
            field = item.get("field")
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
        order_field: str,
        event_filters: List[Dict[str, Any]],
        thedate_range: Optional[Tuple[str, str]] = None,
    ):
        order_field_name = order_field.lstrip("-")
        order_direction = "DESC" if order_field.startswith("-") else "ASC"

        manual_helper = ManualUnsyncedRiskPrepender(base_queryset, order_field, self._apply_ordering)
        manual_unsynced_count = manual_helper.count()
        resolver = BkBaseFieldResolver(order_field, event_filters, self._duplicate_event_field_map)
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
            page = api_settings.DEFAULT_PAGINATION_CLASS()
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
        pagination_class = api_settings.DEFAULT_PAGINATION_CLASS
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
                order_field=order_field_name,
                order_direction=order_direction,
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

    def _build_filter_query(self, validated_request_data: dict) -> Q:
        """通用筛选条件构造：从请求参数中提取风险等级、标签等筛选条件并构造 Q 表达式，供所有 ListRisk 子类共享。"""
        q = Q()
        # 风险等级
        risk_level = validated_request_data.pop("risk_level", None)
        if risk_level:
            q &= Q(strategy__risk_level__in=risk_level)

        # 标签筛选条件
        if tag_filter := validated_request_data.pop("tag_objs__in", None):
            q &= Q(strategy__tags__tag_id__in=tag_filter)

        for key, val in validated_request_data.items():
            if not val:
                continue
            # 普通匹配，针对单值匹配
            _q = Q()
            for i in val:
                _q |= Q(**{key: i})
            q &= _q
        return q

    def load_risks(self, validated_request_data: dict) -> QuerySet["Risk"]:
        q = self._build_filter_query(validated_request_data)
        return Risk.load_iam_authed_risks(action=ActionEnum.LIST_RISK).filter(q).distinct()

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


class ListMineRisk(ListRisk):
    name = gettext_lazy("获取待我处理的风险列表")

    def load_risks(self, validated_request_data):
        q = self._build_filter_query(validated_request_data)
        return Risk.annotated_queryset().filter(q, current_operator__contains=get_request_username()).distinct()


class ListNoticingRisk(ListRisk):
    name = gettext_lazy("获取我关注的风险列表")

    def load_risks(self, validated_request_data):
        q = self._build_filter_query(validated_request_data)
        return Risk.annotated_queryset().filter(q, notice_users__contains=get_request_username()).distinct()


class ListProcessedRisk(ListRisk):
    name = gettext_lazy("获取处理历史风险列表")

    def load_risks(self, validated_request_data):
        q = self._build_filter_query(validated_request_data)
        username = get_request_username()
        processed_risk_ids = TicketPermission.objects.filter(
            user=username,
            user_type=UserType.OPERATOR,
            action=ActionEnum.LIST_RISK.id,
        ).values("risk_id")
        return (
            Risk.annotated_queryset()
            .filter(q, risk_id__in=processed_risk_ids)
            .exclude(current_operator__contains=username)
            .distinct()
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


class RiskDisplayStatusCommon(RiskMeta):
    """获取风险展示状态类型（供前端下拉框筛选使用）"""

    name = gettext_lazy("获取风险展示状态类型")

    def perform_request(self, validated_request_data):
        return choices_to_dict(RiskDisplayStatus)


class ListRiskBase(RiskMeta, CacheResource, abc.ABC):
    RequestSerializer = ListRiskMetaRequestSerializer
    many_response_data = True
    # 风险视图类型与风险类的映射
    risk_cls_map: Dict[str, Type[ListRisk]] = {
        RiskViewType.ALL.value: ListRisk,
        RiskViewType.TODO.value: ListMineRisk,
        RiskViewType.WATCH.value: ListNoticingRisk,
        RiskViewType.PROCESSED.value: ListProcessedRisk,
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
                RiskExportField.STATUS: str(RiskDisplayStatus.get_label(risk.display_status)),
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
        # 决定策略集合
        strategy_ids = validated_request_data.get("strategy_ids")
        if strategy_ids:
            strategies = Strategy.objects.filter(strategy_id__in=strategy_ids)
        else:
            strategies = Strategy.objects.all()

        results = set()
        for s in strategies:
            for config_name in ["event_data_field_configs"]:
                for cfg in getattr(s, config_name) or []:
                    field_name = cfg.get("field_name")
                    display_name = cfg.get("display_name") or field_name
                    if not field_name:
                        continue
                    results.add((field_name, display_name))
        return [
            {"field_name": field_name, "display_name": display_name, "id": f"{display_name}:{field_name}"}
            for field_name, display_name in results
        ]


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

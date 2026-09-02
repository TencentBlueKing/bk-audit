# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
Copyright (C) 2023 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at https://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

import datetime
from typing import List, Optional, Tuple

from django.db import models
from django.db.models import QuerySet
from django.db.models.expressions import RawSQL
from django.db.models.functions import Substr
from django.utils import timezone
from iam import PathEqDjangoQuerySetConverter
from iam.resource.provider import ListResult
from iam.resource.utils import Page

from apps.permission.handlers.resource_types import ResourceEnum
from apps.permission.provider.base import IAMResourceProvider
from services.web.risk.constants import FETCH_INSTANCE_LIST_LARGE_FIELD_LIMIT_BYTES
from services.web.risk.converter.queryset import RiskPathEqDjangoQuerySetConverter
from services.web.risk.models import ManualEvent, Risk, TicketNode, TicketPermission
from services.web.risk.serializers import (
    ManualEventProviderSerializer,
    RiskProviderSerializer,
    TicketNodeProviderSerializer,
    TicketPermissionProviderSerializer,
)
from services.web.scene.constants import ResourceVisibilityType
from services.web.scene.models import ResourceBindingScene


class RiskResourceProvider(IAMResourceProvider):
    resource_provider_serializer = RiskProviderSerializer
    resource_type_index_fields = [
        "risk_id",
        "raw_event_id",
        "strategy_id",
        "event_time",
        "event_end_time",
        "event_source",
        "last_operate_time",
        "title",
        "event_time_timestamp",
        "event_end_time_timestamp",
        "last_operate_time_timestamp",
    ]

    # fetch_instance_list 反向拉取时需截断/置 NULL 的大字段
    # - event_content（TextField）：截断（文本截断合法，不涉及检索）
    # - event_data / event_evidence（实际是 dict/list 结构）：超阈值置 NULL（保证 JSON 合法性）
    _TEXT_FIELDS_TO_TRUNCATE = ("event_content",)
    _FIELDS_TO_NULLIFY = ("event_data", "event_evidence")

    def list_attr_value_choices(self, attr: str, page: Page) -> List:
        return []

    def _build_fetch_values_kwargs(self, limit_bytes: int):
        """动态构建 queryset.values() 的字段列表与注解，避免硬编码遗漏模型新字段。

        Django values() 不允许 annotation 名与 model 字段同名，因此截断/置 NULL 的字段
        用别名注解（_truncated_<field>），在 values() 列表中引用别名，
        fetch_instance_list 序列化前将别名 key 映射回原名。

        用 RawSQL 生成 CASE WHEN，绕过 Django ORM 对 TextField/JSONField 的 __length lookup 限制：
        - TextField（event_content）用 SUBSTR(field, 1, N) 截断
        - JSONField/TextField dict/list（event_data/event_evidence）用
          CASE WHEN LENGTH(COALESCE(field, '')) > N THEN NULL ELSE field END
        """
        values_fields = []
        annotated = {}

        for field in Risk._meta.fields:
            if field.is_relation:
                # FK 字段（strategy）跳过 annotation，但显式加入 values_fields
                # values() 会自动取 strategy_id 列，serializer 用 strategy_id 读取
                values_fields.append(field.attname)
                continue
            if field.name in self._TEXT_FIELDS_TO_TRUNCATE:
                # TextField：Substr 截断（生成 SUBSTR(field, 1, N)，截断后合法字符串）
                alias = f"_truncated_{field.name}"
                annotated[alias] = Substr(field.name, 1, limit_bytes)
                values_fields.append(alias)
            elif field.name in self._FIELDS_TO_NULLIFY:
                # JSONField / TextField dict/list：超阈值置 NULL（RawSQL 绕过 ORM lookup 限制）
                alias = f"_truncated_{field.name}"
                column = field.column
                annotated[alias] = RawSQL(
                    f"CASE WHEN LENGTH(COALESCE(`{column}`, '')) > %s THEN NULL ELSE `{column}` END",
                    [limit_bytes],
                    output_field=field.__class__(),
                )
                values_fields.append(alias)
            else:
                values_fields.append(field.name)

        return values_fields, annotated

    @staticmethod
    def _get_strategy_ids_by_scene(scene_id: str) -> List[int]:
        """通过策略绑定的场景反查 strategy_id 列表（风险不直接绑定场景，而是依赖策略所属的场景）

        注意：binding.resource_id 是 CharField(str)，需转为 int 与 Risk.strategy_id(ForeignKey int) 匹配。
        """
        str_ids = ResourceBindingScene.objects.filter(
            binding__resource_type=ResourceVisibilityType.STRATEGY,
            scene_id=scene_id,
            scene__is_deleted=False,
        ).values_list("binding__resource_id", flat=True)
        int_ids = []
        for sid in str_ids:
            try:
                int_ids.append(int(sid))
            except (TypeError, ValueError):
                continue
        return int_ids

    @staticmethod
    def _get_risk_ids_by_scene(scene_id: str) -> List[str]:
        """按 Risk.scene_id 反查 risk_id 列表（风险场景归属已固化到 Risk 模型）。"""
        from services.web.risk.models import Risk

        try:
            scene_id_int = int(scene_id)
        except (TypeError, ValueError):
            return []
        return list(Risk.objects.filter(scene_id=scene_id_int).values_list("risk_id", flat=True))

    def filter_list_instance_results(self, parent_id: Optional[str], resource_type: Optional[str], page: Page) -> Tuple:
        """
        根据过滤条件查询资源实例
        """
        if parent_id:
            if resource_type == ResourceEnum.SCENE.id:
                bound_risk_ids = self._get_risk_ids_by_scene(parent_id)
                queryset: QuerySet[Risk] = Risk.objects.filter(risk_id__in=bound_risk_ids)
            elif resource_type == ResourceEnum.STRATEGY.id:
                strategy_id = int(parent_id)
                queryset: QuerySet[Risk] = Risk.objects.filter(strategy_id=strategy_id)
            else:
                queryset: QuerySet[Risk] = Risk.objects.none()
        else:
            queryset: QuerySet[Risk] = Risk.objects.all()
        results = [
            {"id": str(instance.risk_id), "display_name": instance.risk_id}
            for instance in queryset[page.slice_from : page.slice_to]
        ]
        count = queryset.count()
        return results, count

    def filter_search_instance_results(
        self, parent_id: Optional[str], resource_type: Optional[str], keyword: str, page: Page
    ) -> Tuple[list, int]:
        """根据风险类型名称查询 ."""
        if parent_id:
            if resource_type == ResourceEnum.SCENE.id:
                bound_risk_ids = self._get_risk_ids_by_scene(parent_id)
                queryset: QuerySet[Risk] = Risk.objects.filter(risk_id__in=bound_risk_ids)
            elif resource_type == ResourceEnum.STRATEGY.id:
                strategy_id = int(parent_id)
                queryset: QuerySet[Risk] = Risk.objects.filter(strategy_id=strategy_id)
            else:
                queryset: QuerySet[Risk] = Risk.objects.none()
        else:
            queryset: QuerySet[Risk] = Risk.objects.all()

        queryset = queryset.filter(risk_id__contains=keyword)
        results = [
            {"id": str(instance.risk_id), "display_name": instance.risk_id}
            for instance in queryset[page.slice_from : page.slice_to]
        ]
        count = queryset.count()
        return results, count

    def filter_fetch_instance_results(self, ids: List[str]) -> Tuple:
        """
        批量查询资源实例
        """

        queryset = Risk.objects.filter(risk_id__in=ids)

        results = [{"id": item.risk_id, "display_name": item.risk_id} for item in queryset]
        return results, queryset.count()

    def list_instance_by_policy(self, filters, page, **options):
        expression = filters.expression
        if not expression:
            return ListResult(results=[], count=0)

        converter = RiskPathEqDjangoQuerySetConverter()
        filters = converter.convert(expression)
        queryset: QuerySet[Risk] = Risk.objects.filter(filters)
        results = [
            {"id": item.risk_id, "display_name": item.risk_id} for item in queryset[page.slice_from : page.slice_to]
        ]

        return ListResult(results=results, count=queryset.count())

    def fetch_instance_list(self, filter, page, **options):
        # 注意：filter.start_time/end_time 为毫秒时间戳，这里保持毫秒精度，避免边界被截断
        # 使用 tz=timezone.utc 生成 aware datetime，避免 USE_TZ=True 下的 naive datetime 警告
        start_time = datetime.datetime.fromtimestamp(float(filter.start_time) / 1000, tz=timezone.utc)
        end_time = datetime.datetime.fromtimestamp(float(filter.end_time) / 1000, tz=timezone.utc)
        # 使用 _objects（原始 manager）以包含已软删除记录，使 Doris 侧 is_deleted 值可靠同步。
        # 参考 strategy_v2/provider.py 在 fetch_instance_list 返回 is_deleted 的先例。
        base_qs = Risk._objects.filter(updated_at__gt=start_time, updated_at__lte=end_time)

        # 延迟关联优化：先在 updated_at 索引上做覆盖扫描定位主键，避免深分页时大量回表
        pk_list = list(
            base_qs.order_by("updated_at").values_list("risk_id", flat=True)[page.slice_from : page.slice_to]
        )
        # 回表查询：用 values() 显式列出字段，大字段在 SQL 侧截断/置 NULL
        # ⚠️ 不能用 defer()：defer 后 ModelSerializer 访问字段会触发 N+1 单条查询
        #   （实测 1000 条 × 3 字段 = 3000 次查询，序列化 15.87s，JSON 790MB，进程 OOM）
        # ⚠️ RiskProviderSerializer 可直接序列化 values() 返回的 dict（DRF 3.15+ Field.get_attribute
        #   原生支持 Mapping），无需新建独立序列化器
        values_fields, annotations = self._build_fetch_values_kwargs(FETCH_INSTANCE_LIST_LARGE_FIELD_LIMIT_BYTES)
        queryset = (
            Risk._objects.filter(risk_id__in=pk_list).order_by("updated_at").values(*values_fields, **annotations)
        )

        # 截断/置 NULL 字段用别名 _truncated_<field>，需映射回原名供 RiskProviderSerializer 读取
        alias_map = {f"_truncated_{f}": f for f in list(self._TEXT_FIELDS_TO_TRUNCATE) + list(self._FIELDS_TO_NULLIFY)}

        results = [
            {
                "id": item["risk_id"],
                "display_name": item["risk_id"],
                "creator": None,
                "created_at": None,
                "updater": None,
                "updated_at": None,
                "data": self.resource_provider_serializer({alias_map.get(k, k): v for k, v in item.items()}).data,
                "is_deleted": item["is_deleted"],
            }
            for item in queryset
        ]
        return ListResult(results=results, count=base_qs.count())


class ManualEventResourceProvider(IAMResourceProvider):
    resource_provider_serializer = ManualEventProviderSerializer
    resource_type_index_fields = [
        "manual_event_id",
        "raw_event_id",
        "strategy_id",
        "event_time",
        "event_source",
        "last_operate_time",
        "title",
        "event_time_timestamp",
        "last_operate_time_timestamp",
    ]

    def list_attr_value_choices(self, attr: str, page: Page) -> List:
        return []

    @staticmethod
    def _display_name(instance: ManualEvent) -> str:
        return instance.raw_event_id or str(instance.manual_event_id)

    def _filter_queryset(self, parent_id: Optional[str], resource_type: Optional[str]) -> QuerySet[ManualEvent]:
        if parent_id:
            if resource_type == ResourceEnum.SCENE.id:
                bound_strategy_ids = RiskResourceProvider._get_strategy_ids_by_scene(parent_id)
                return ManualEvent.objects.filter(strategy_id__in=bound_strategy_ids)
            if resource_type == ResourceEnum.STRATEGY.id:
                return ManualEvent.objects.filter(strategy_id=int(parent_id))
            return ManualEvent.objects.none()
        return ManualEvent.objects.all()

    def filter_list_instance_results(self, parent_id: Optional[str], resource_type: Optional[str], page: Page) -> Tuple:
        queryset = self._filter_queryset(parent_id, resource_type)
        page_qs = queryset[page.slice_from : page.slice_to]
        results = [{"id": str(item.manual_event_id), "display_name": self._display_name(item)} for item in page_qs]
        return results, queryset.count()

    def filter_search_instance_results(
        self, parent_id: Optional[str], resource_type: Optional[str], keyword: str, page: Page
    ) -> Tuple[list, int]:
        queryset = self._filter_queryset(parent_id, resource_type)
        queryset = queryset.filter(raw_event_id__icontains=keyword)
        page_qs = queryset[page.slice_from : page.slice_to]
        results = [{"id": str(item.manual_event_id), "display_name": self._display_name(item)} for item in page_qs]
        return results, queryset.count()

    def filter_fetch_instance_results(self, ids: List[str]) -> Tuple:
        queryset = ManualEvent.objects.filter(manual_event_id__in=ids)
        results = [{"id": str(item.manual_event_id), "display_name": self._display_name(item)} for item in queryset]
        return results, queryset.count()

    def list_instance_by_policy(self, filters, page, **options):
        expression = filters.expression
        if not expression:
            return ListResult(results=[], count=0)

        converter = RiskPathEqDjangoQuerySetConverter()
        django_filters = converter.convert(expression)
        queryset = ManualEvent.objects.filter(django_filters)
        page_qs = queryset[page.slice_from : page.slice_to]
        results = [{"id": str(item.manual_event_id), "display_name": self._display_name(item)} for item in page_qs]
        return ListResult(results=results, count=queryset.count())

    def fetch_instance_list(self, filter, page, **options):
        start_time = datetime.datetime.fromtimestamp(float(filter.start_time) / 1000)
        end_time = datetime.datetime.fromtimestamp(float(filter.end_time) / 1000)
        base_qs = ManualEvent.objects.filter(updated_at__gt=start_time, updated_at__lte=end_time)

        # 延迟关联优化：先在 updated_at 索引上做覆盖扫描定位主键，避免深分页时大量回表
        pk_list = list(
            base_qs.order_by("updated_at").values_list("manual_event_id", flat=True)[page.slice_from : page.slice_to]
        )
        # 用主键精确回表，只回表 page_size 条记录
        queryset = ManualEvent.objects.filter(manual_event_id__in=pk_list).order_by("updated_at")

        results = [
            {
                "id": str(item.manual_event_id),
                "display_name": self._display_name(item),
                "creator": None,
                "created_at": None,
                "updater": None,
                "updated_at": None,
                "data": self.resource_provider_serializer(instance=item).data,
            }
            for item in queryset
        ]
        return ListResult(results=results, count=base_qs.count())


class TicketPermissionResourceProvider(IAMResourceProvider):
    resource_type = ResourceEnum.TICKET_PERMISSION.id
    """TicketPermission 资源提供者（用于反向拉取快照）"""
    resource_provider_serializer = TicketPermissionProviderSerializer
    resource_type_index_fields = ["risk_id", "action", "user", "authorized_at", "user_type", "authorized_at_timestamp"]

    def list_attr_value_choices(self, attr: str, page: Page) -> List:
        return []

    def filter_list_instance_results(self, parent_id: Optional[str], resource_type: Optional[str], page: Page) -> Tuple:
        queryset = TicketPermission.objects.all()
        if parent_id and resource_type == ResourceEnum.RISK.id:
            queryset = queryset.filter(risk_id=str(parent_id))
        page_qs = queryset[page.slice_from : page.slice_to]
        results = [{"id": str(item.pk), "display_name": str(item.pk)} for item in page_qs]
        return results, queryset.count()

    def filter_fetch_instance_results(self, ids: List[str]) -> Tuple:
        int_ids = []
        for i in ids:
            try:
                int_ids.append(int(i))
            except (TypeError, ValueError):
                continue
        queryset = TicketPermission.objects.filter(pk__in=int_ids)
        results = [{"id": str(item.pk), "display_name": str(item.pk)} for item in queryset]
        return results, queryset.count()

    def filter_search_instance_results(
        self, parent_id: Optional[str], resource_type: Optional[str], keyword: str, page: Page
    ) -> Tuple[List[dict], int]:
        queryset = TicketPermission.objects.all()
        if parent_id and resource_type == ResourceEnum.RISK.id:
            queryset = queryset.filter(risk_id=str(parent_id))
        if keyword:
            queryset = queryset.filter(
                models.Q(risk_id__icontains=keyword)
                | models.Q(action__icontains=keyword)
                | models.Q(user__icontains=keyword)
            )
        page_qs = queryset[page.slice_from : page.slice_to]
        results = [{"id": str(item.pk), "display_name": str(item.pk)} for item in page_qs]
        return results, queryset.count()

    def list_instance_by_policy(self, filters, page, **options):
        expression = filters.expression
        if not expression:
            return ListResult(results=[], count=0)

        key_mapping = {f"{self.resource_type}.id": "id"}
        converter = PathEqDjangoQuerySetConverter(key_mapping)
        django_filters = converter.convert(expression)
        queryset = TicketPermission.objects.filter(django_filters)
        results = [
            {"id": str(item.pk), "display_name": str(item.pk)} for item in queryset[page.slice_from : page.slice_to]
        ]
        return ListResult(results=results, count=queryset.count())

    def fetch_instance_list(self, filter, page, **options):
        # 将毫秒级时间戳转换为 UTC aware datetime，避免边界/时区问题
        start_ms = float(filter.start_time)
        end_ms = float(filter.end_time)
        start_time = datetime.datetime.fromtimestamp(start_ms / 1000.0, tz=timezone.utc)
        end_time = datetime.datetime.fromtimestamp(end_ms / 1000.0, tz=timezone.utc)
        # 上界扩展 1ms，确保包含毫秒边界
        end_time_inclusive = end_time + datetime.timedelta(milliseconds=1)
        queryset = TicketPermission.objects.filter(
            authorized_at__gt=start_time, authorized_at__lte=end_time_inclusive
        ).order_by("authorized_at", "id")
        page_queryset = queryset[page.slice_from : page.slice_to]
        # 顶层时间戳要求为毫秒级
        results = [
            {
                "id": str(item.pk),
                "display_name": str(item.pk),
                "creator": None,
                "created_at": int(item.authorized_at.timestamp() * 1000) if item.authorized_at else None,
                "updater": None,
                "updated_at": int(item.authorized_at.timestamp() * 1000) if item.authorized_at else None,
                "data": self.resource_provider_serializer(item).data,
            }
            for item in page_queryset
        ]
        return ListResult(results=results, count=queryset.count())


class TicketNodeResourceProvider(IAMResourceProvider):
    resource_type = ResourceEnum.TICKET_NODE.id
    resource_provider_serializer = TicketNodeProviderSerializer
    resource_type_index_fields = ["risk_id", "operator"]

    def list_attr_value_choices(self, attr: str, page: Page) -> List:
        return []

    def filter_list_instance_results(self, parent_id: Optional[str], resource_type: Optional[str], page: Page) -> Tuple:
        queryset = TicketNode.objects.all()
        if parent_id and resource_type == ResourceEnum.RISK.id:
            queryset = queryset.filter(risk_id=str(parent_id))
        page_qs = queryset[page.slice_from : page.slice_to]
        results = [{"id": str(item.pk), "display_name": str(item.pk)} for item in page_qs]
        return results, queryset.count()

    def filter_fetch_instance_results(self, ids: List[str]) -> Tuple:
        queryset = TicketNode.objects.filter(pk__in=ids)
        results = [{"id": str(item.pk), "display_name": str(item.pk)} for item in queryset]
        return results, queryset.count()

    def filter_search_instance_results(
        self, parent_id: Optional[str], resource_type: Optional[str], keyword: str, page: Page
    ) -> Tuple[List[dict], int]:
        queryset = TicketNode.objects.all()
        if parent_id and resource_type == ResourceEnum.RISK.id:
            queryset = queryset.filter(risk_id=str(parent_id))
        if keyword:
            queryset = queryset.filter(models.Q(risk_id__icontains=keyword) | models.Q(operator__icontains=keyword))
        page_qs = queryset[page.slice_from : page.slice_to]
        results = [{"id": str(item.pk), "display_name": str(item.pk)} for item in page_qs]
        return results, queryset.count()

    def list_instance_by_policy(self, filters, page, **options):
        expression = filters.expression
        if not expression:
            return ListResult(results=[], count=0)

        key_mapping = {f"{self.resource_type}.id": "id"}
        converter = PathEqDjangoQuerySetConverter(key_mapping)
        django_filters = converter.convert(expression)
        queryset = TicketNode.objects.filter(django_filters)
        results = [
            {"id": str(item.pk), "display_name": str(item.pk)} for item in queryset[page.slice_from : page.slice_to]
        ]
        return ListResult(results=results, count=queryset.count())

    def fetch_instance_list(self, filter, page, **options):
        start_ts = float(filter.start_time) / 1000.0
        end_ts = float(filter.end_time) / 1000.0
        base_qs = TicketNode.objects.filter(timestamp__gt=start_ts, timestamp__lte=end_ts)

        pk_list = list(base_qs.order_by("timestamp").values_list("id", flat=True)[page.slice_from : page.slice_to])
        queryset = TicketNode.objects.filter(pk__in=pk_list).order_by("timestamp")

        results = [
            {
                "id": str(item.pk),
                "display_name": str(item.pk),
                "creator": None,
                "created_at": int(item.timestamp * 1000),
                "updater": None,
                "updated_at": int(item.timestamp * 1000),
                "data": self.resource_provider_serializer(item).data,
            }
            for item in queryset
        ]
        return ListResult(results=results, count=base_qs.count())

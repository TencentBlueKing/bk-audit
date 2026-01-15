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
import datetime
import json
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import cached_property
from typing import Dict, List, Optional

from bk_resource import CacheResource, api, resource
from bk_resource.base import Empty
from bk_resource.exceptions import APIRequestError
from bk_resource.utils.cache import CacheTypeItem
from blueapps.utils.logger import logger
from blueapps.utils.request_provider import get_local_request, get_request_username
from django.conf import settings
from django.db import models, transaction
from django.db.models import Count, IntegerField, OuterRef, Q, QuerySet, Subquery
from django.db.models.aggregates import Min
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.translation import gettext, gettext_lazy
from pypinyin import lazy_pinyin
from rest_framework.settings import api_settings

from apps.audit.resources import AuditMixinResource
from apps.feature.constants import FeatureTypeChoices
from apps.feature.handlers import FeatureHandler
from apps.meta.constants import NO_TAG_ID, NO_TAG_NAME
from apps.meta.models import DataMap, EnumMappingRelatedType, Tag
from apps.meta.serializers import EnumMappingSerializer
from apps.meta.utils.fields import (
    ACTION_ID,
    DIMENSION_FIELD_TYPES,
    EXTEND_DATA,
    FILED_DISPLAY_NAME_ALIAS_KEY,
    PYTHON_TO_ES,
    SNAPSHOT_USER_INFO,
    SNAPSHOT_USER_INFO_HIDE_FIELDS,
    STRATEGY_DISPLAY_FIELDS,
    SYSTEM_ID,
)
from apps.meta.utils.format import preprocess_data
from apps.permission.handlers.actions import ActionEnum
from apps.permission.handlers.drf import ActionPermission
from apps.permission.handlers.permission import Permission
from apps.permission.handlers.resource_types import ResourceEnum
from core.exceptions import PermissionException
from core.utils.data import choices_to_dict, compare_dict_specific_keys
from core.utils.page import paginate_queryset
from services.web.analyze.constants import (
    BaseControlTypeChoices,
    FilterOperator,
    OffsetUnit,
)
from services.web.analyze.controls.base import BaseControl
from services.web.analyze.tasks import call_controller
from services.web.analyze.utils import is_asset
from services.web.common.caller_permission import (
    CurrentType,
    should_skip_permission_from,
)
from services.web.query.utils.search_config import QueryConditionOperator
from services.web.risk.constants import (
    RAW_EVENT_ID_REMARK,
    EventMappingFields,
    RiskMetaFields,
)
from services.web.risk.models import Risk
from services.web.risk.permissions import RiskViewPermission
from services.web.risk.report.task_submitter import submit_render_task
from services.web.risk.report_config import ReportConfig
from services.web.strategy_v2.constants import (
    EVENT_BASIC_CONFIG_FIELD,
    EVENT_BASIC_CONFIG_REMOTE_FIELDS,
    EVENT_BASIC_CONFIG_SORT_FIELD,
    HAS_UPDATE_TAG_ID,
    HAS_UPDATE_TAG_NAME,
    LOCAL_UPDATE_FIELDS,
    STRATEGY_RISK_DEFAULT_INTERVAL,
    EventInfoField,
    LinkTableJoinType,
    LinkTableTableType,
    MappingType,
    RiskLevel,
    RuleAuditAggregateType,
    RuleAuditConditionOperator,
    RuleAuditConfigType,
    RuleAuditFieldType,
    RuleAuditSourceType,
    RuleAuditWhereConnector,
    StrategyAlgorithmOperator,
    StrategyFieldSourceEnum,
    StrategyOperator,
    StrategySource,
    StrategyStatusChoices,
    StrategyType,
    TableType,
)
from services.web.strategy_v2.exceptions import (
    ControlChangeError,
    LinkTableHasStrategy,
    NotSupportSourceType,
    StrategyPendingError,
    StrategyTypeCanNotChange,
)
from services.web.strategy_v2.handlers.rule_audit import RuleAuditSQLBuilder
from services.web.strategy_v2.handlers.strategy_running_status import (
    StrategyRunningStatusHandler,
)
from services.web.strategy_v2.models import (
    LinkTable,
    LinkTableAuditInstance,
    LinkTableTag,
    Strategy,
    StrategyAuditInstance,
    StrategyTag,
    StrategyTool,
)
from services.web.strategy_v2.serializers import (
    AggregationFunctionResponseSerializer,
    BulkGetRTFieldsRequestSerializer,
    BulkGetRTFieldsResponseSerializer,
    CreateLinkTableRequestSerializer,
    CreateLinkTableResponseSerializer,
    CreateStrategyRequestSerializer,
    CreateStrategyResponseSerializer,
    EnumMappingByCollectionKeysWithCallerSerializer,
    EnumMappingByCollectionWithCallerSerializer,
    GetEventInfoFieldsRequestSerializer,
    GetEventInfoFieldsResponseSerializer,
    GetLinkTableRequestSerializer,
    GetLinkTableResponseSerializer,
    GetRTFieldsRequestSerializer,
    GetRTFieldsResponseSerializer,
    GetRTLastDataRequestSerializer,
    GetRTMetaRequestSerializer,
    GetStrategyCommonResponseSerializer,
    GetStrategyDisplayInfoRequestSerializer,
    GetStrategyFieldValueRequestSerializer,
    GetStrategyFieldValueResponseSerializer,
    GetStrategyStatusRequestSerializer,
    LinkTableInfoSerializer,
    ListLinkTableAllResponseSerializer,
    ListLinkTableRequestSerializer,
    ListLinkTableResponseSerializer,
    ListLinkTableTagsResponseSerializer,
    ListStrategyFieldsRequestSerializer,
    ListStrategyFieldsResponseSerializer,
    ListStrategyRequestSerializer,
    ListStrategyResponseSerializer,
    ListStrategyTagsResponseSerializer,
    ListTablesRequestSerializer,
    PreviewReportRequestSerializer,
    PreviewReportResponseSerializer,
    RetrieveStrategyRequestSerializer,
    RetryStrategyRequestSerializer,
    RiskVariableResponseSerializer,
    RuleAuditSourceTypeCheckReqSerializer,
    RuleAuditSourceTypeCheckRespSerializer,
    StrategyDetailSerializer,
    StrategyInfoSerializer,
    StrategyRunningStatusListReqSerializer,
    StrategyRunningStatusListRespSerializer,
    ToggleStrategyRequestSerializer,
    UpdateLinkTableRequestSerializer,
    UpdateLinkTableResponseSerializer,
    UpdateStrategyRequestSerializer,
    UpdateStrategyResponseSerializer,
)
from services.web.strategy_v2.utils.field_value import FieldValueHandler
from services.web.strategy_v2.utils.table import (
    RuleAuditSourceTypeChecker,
    TableHandler,
    enhance_rt_fields,
)


class StrategyV2Base(AuditMixinResource, abc.ABC):
    tags = ["StrategyV2"]
    audit_resource_type = ResourceEnum.STRATEGY

    def _save_tags(self, strategy_id: int, tag_names: list) -> None:
        StrategyTag.objects.filter(strategy_id=strategy_id).delete()
        if not tag_names:
            return
        tags = resource.meta.save_tags([{"tag_name": t} for t in tag_names])
        StrategyTag.objects.bulk_create([StrategyTag(strategy_id=strategy_id, tag_id=t["tag_id"]) for t in tags])

    def _save_strategy_tools(self, strategy: Strategy, validated_request_data: dict) -> None:
        StrategyTool.objects.filter(strategy=strategy).delete()

        tools_to_create = []
        field_config_map = [
            (StrategyFieldSourceEnum.BASIC.value, "event_basic_field_configs"),
            (StrategyFieldSourceEnum.DATA.value, "event_data_field_configs"),
            (StrategyFieldSourceEnum.EVIDENCE.value, "event_evidence_field_configs"),
            (StrategyFieldSourceEnum.RISK_META.value, "risk_meta_field_config"),
        ]

        for field_source, config_key in field_config_map:
            for field_cfg in validated_request_data.get(config_key, []):
                drill_config = field_cfg.get("drill_config", [])

                for drill in drill_config:
                    tool = drill.get("tool", {})

                    if not tool.get("uid"):
                        continue

                    tools_to_create.append(
                        StrategyTool(
                            strategy=strategy,
                            field_name=field_cfg.get("field_name"),
                            tool_uid=tool["uid"],
                            tool_version=tool.get("version"),
                            field_source=field_source,
                        )
                    )

        if tools_to_create:
            # 批量创建 StrategyTool 对象
            StrategyTool.objects.bulk_create(tools_to_create)

    @staticmethod
    def has_sql_override(validated_request_data: dict) -> bool:
        """
        判断请求中是否显式携带可用的 SQL
        """

        sql_value = validated_request_data.get("sql", Empty)
        return sql_value not in [Empty, None, ""]

    @staticmethod
    def get_base_control_type(strategy_type: str) -> Optional[str]:
        """
        获取基础控制类型
        """

        return {
            StrategyType.RULE: BaseControlTypeChoices.RULE_AUDIT.value,
            StrategyType.MODEL: BaseControlTypeChoices.CONTROL.value,
        }.get(strategy_type)

    def build_rule_audit_sql(self, strategy: Strategy) -> str:
        """
        构建规则审计SQL
        """

        return RuleAuditSQLBuilder(strategy).build_sql()

    def _check_source_type(self, validated_request_data):
        """
        校验 source_type 是否支持
        """

        # 只对规则审计校验
        strategy_type = validated_request_data.get("strategy_type")
        if strategy_type != StrategyType.RULE.value:
            return

        configs = validated_request_data.get("configs", {})
        if not configs:
            return
        data_source: dict = configs["data_source"]
        source_type = data_source.get("source_type")
        try:
            support_source_types = resource.strategy_v2.rule_audit_source_type_check(
                {
                    "namespace": validated_request_data["namespace"],
                    "config_type": configs["config_type"],
                    "rt_id": data_source.get("rt_id"),
                    "link_table": data_source.get("link_table"),
                }
            )["support_source_types"]
        except APIRequestError as e:
            logger.error(f"[{self.__class__.__name__}] get support_source_types error{e}.")
            return
        if source_type not in support_source_types:
            raise NotSupportSourceType(source_type=source_type, support_source_types=support_source_types)

    def update_enum_mappings(
        self,
        enum_mapping: dict,
        strategy_id: int,
        field_name: str,
        field_category: str,
    ):
        """
        Generate immutable collection_id based on strategy_id, field_category, and field_name,
        then batch update enum mappings.
        """
        # override collection_id to ensure uniqueness and immutability
        field_type = field_category.replace('event_', '').replace('_field_configs', '')
        enum_mapping['collection_id'] = f"{strategy_id}_{field_type}_{field_name}"
        enum_mapping['related_object_id'] = str(strategy_id)
        enum_mapping['related_type'] = EnumMappingRelatedType.STRATEGY.value
        resource.meta.batch_update_enum_mappings(**enum_mapping)

    def delete_enum_mappings(self, strategy_id: int):
        collection_ids = resource.meta.get_enum_mappings_relation(
            related_object_id=str(strategy_id), related_type=EnumMappingRelatedType.STRATEGY.value
        )
        for collection_id in collection_ids:
            resource.meta.batch_update_enum_mappings(
                collection_id=collection_id,
                related_type=EnumMappingRelatedType.STRATEGY.value,
                related_object_id=str(strategy_id),
                mappings=[],
            )


class CreateStrategy(StrategyV2Base):
    """
    创建策略时附带枚举映射示例。
    ```
    {
            "strategy_name": "demo",
            "strategy_type": "model",
            "event_basic_field_configs": [
                {
                    "field_name": "status",
                    "display_name": "Status",
                    "is_priority": false,
                    "duplicate_field": false,
                    "enum_mappings": {
                        "collection_id": "status_collection_112233", # 枚举名字全局唯一，建议生成随机值
                        "mappings": [
                            {"key": "1", "name": "Running"},
                            {"key": "0", "name": "Stopped"}
                        ]
                    }
                }
            ]
        }
    ```
    """

    name = gettext_lazy("Create Strategy")
    RequestSerializer = CreateStrategyRequestSerializer
    ResponseSerializer = CreateStrategyResponseSerializer
    audit_action = ActionEnum.CREATE_STRATEGY

    def perform_request(self, validated_request_data):
        strategy_type = validated_request_data.get("strategy_type")
        self._check_source_type(validated_request_data)
        with transaction.atomic():
            # pop tag
            tag_names = validated_request_data.pop("tags", [])
            # save strategy
            strategy: Strategy = Strategy.objects.create(**validated_request_data)
            # save strategy tag
            self._save_tags(strategy_id=strategy.strategy_id, tag_names=tag_names)
            self._save_strategy_tools(strategy, validated_request_data)
            if strategy_type == StrategyType.RULE and not self.has_sql_override(validated_request_data):
                strategy.sql = self.build_rule_audit_sql(strategy)
                strategy.save(update_fields=["sql"])
            # 更新enum
            for field_category in [
                'event_basic_field_configs',
                'event_data_field_configs',
                'event_evidence_field_configs',
                'risk_meta_field_config',
            ]:
                for field_config in validated_request_data.get(field_category, []):
                    enum_mappings = field_config.get('enum_mappings')
                    if enum_mappings:
                        self.update_enum_mappings(
                            enum_mappings,
                            strategy.strategy_id,
                            field_config.get('field_name'),
                            field_category,
                        )
        # create
        try:
            call_controller(
                BaseControl.create.__name__, strategy.strategy_id, self.get_base_control_type(strategy_type)
            )
        except Exception as err:
            strategy.status = StrategyStatusChoices.START_FAILED
            strategy.status_msg = str(err)
            strategy.save(update_fields=["status", "status_msg"])
            raise err
        # auth
        username = get_request_username()
        if username:
            resource_instance = ResourceEnum.STRATEGY.create_instance(strategy.strategy_id)
            Permission(username).grant_creator_action(resource_instance)
        # audit
        self.add_audit_instance_to_context(instance=StrategyAuditInstance(strategy))
        # response
        return strategy


class UpdateStrategy(StrategyV2Base):
    name = gettext_lazy("Update Strategy")
    RequestSerializer = UpdateStrategyRequestSerializer
    ResponseSerializer = UpdateStrategyResponseSerializer
    audit_action = ActionEnum.EDIT_STRATEGY

    def perform_request(self, validated_request_data):
        self._check_source_type(validated_request_data)
        # load strategy
        strategy: Strategy = get_object_or_404(Strategy, strategy_id=validated_request_data.pop("strategy_id", int()))
        # check strategy status
        if strategy.status in [
            StrategyStatusChoices.STARTING,
            StrategyStatusChoices.UPDATING,
            StrategyStatusChoices.STOPPING,
        ]:
            raise StrategyPendingError()
        # 不允许修改策略类型
        if validated_request_data["strategy_type"] != strategy.strategy_type:
            raise StrategyTypeCanNotChange()
        # save origin data
        instance_origin_data = StrategyInfoSerializer(strategy).data
        # update db
        need_update_remote = self.update_db(strategy=strategy, validated_request_data=validated_request_data)
        # update remote
        if need_update_remote:
            self.update_remote(strategy)
        # audit
        setattr(strategy, "instance_origin_data", instance_origin_data)
        self.add_audit_instance_to_context(instance=StrategyAuditInstance(strategy))
        # response
        return strategy

    def check_need_update_remote(self, key: str, origin_value: any, new_value: any, strategy: Strategy) -> bool:
        """
        检查当前 key 的值是否需要更新远程服务
        :param key: 字段名
        :param origin_value: 原始值
        :param new_value: 新值
        :return: 是否需要更新远程
        """
        need_update_remote = False
        # 事件基本配置字段需要对指定字段检查
        if key == EVENT_BASIC_CONFIG_FIELD and isinstance(origin_value, list) and isinstance(new_value, list):
            need_update_remote = not all(
                compare_dict_specific_keys(d1, d2, EVENT_BASIC_CONFIG_REMOTE_FIELDS)
                for d1, d2 in zip(
                    sorted(origin_value, key=lambda x: x.get(EVENT_BASIC_CONFIG_SORT_FIELD)),
                    sorted(new_value, key=lambda x: x.get(EVENT_BASIC_CONFIG_SORT_FIELD)),
                )
            )
        # 如果两个值都为空，则不需要更新，避免 None 和 空值 的比较异常
        elif not origin_value and not new_value:
            need_update_remote = False
        # 不同且不在本地更新清单中的字段才触发远程flow更新
        elif origin_value != new_value and key not in LOCAL_UPDATE_FIELDS:
            need_update_remote = True
        logger.info(
            "[CheckNeedUpdateRemote]StrategyId: %s, Update Key: %s, Update Value: %s, Origin Value: %s, "
            "Need update remote: %s",
            strategy.strategy_id,
            key,
            origin_value,
            new_value,
            need_update_remote,
        )
        return need_update_remote

    @transaction.atomic()
    def update_db(self, strategy: Strategy, validated_request_data: dict) -> bool:
        # 用于控制是否更新真实的监控策略或计算平台Flow
        need_update_remote = False
        has_manual_sql = self.has_sql_override(validated_request_data)
        # pop tag
        tag_names = validated_request_data.pop("tags", [])
        # check control
        if (
            validated_request_data["strategy_type"] == StrategyType.MODEL
            and strategy.control_id != validated_request_data["control_id"]
        ):
            raise ControlChangeError()
        # save strategy
        for key, val in validated_request_data.items():
            inst_val = getattr(strategy, key, Empty())
            # 不同且不在本地更新清单中的字段才触发远程flow更新
            if self.check_need_update_remote(key, inst_val, val, strategy):
                need_update_remote = True
            setattr(strategy, key, val)
        strategy.save(update_fields=validated_request_data.keys())
        # save strategy tag
        self._save_tags(strategy_id=strategy.strategy_id, tag_names=tag_names)
        self._save_strategy_tools(strategy, validated_request_data)
        # update rule audit sql
        if need_update_remote and strategy.strategy_type == StrategyType.RULE and not has_manual_sql:
            strategy.sql = self.build_rule_audit_sql(strategy)
            strategy.save(update_fields=["sql"])
        # 更新enum
        for field_category in [
            'event_basic_field_configs',
            'event_data_field_configs',
            'event_evidence_field_configs',
            'risk_meta_field_config',
        ]:
            for field_config in validated_request_data.get(field_category, []):
                enum_mappings = field_config.get('enum_mappings')
                if enum_mappings:
                    self.update_enum_mappings(
                        enum_mappings,
                        strategy.strategy_id,
                        field_config.get('field_name'),
                        field_category,
                    )
        # return
        return need_update_remote

    def update_remote(self, strategy: Strategy) -> None:
        strategy.status = StrategyStatusChoices.UPDATING
        strategy.save(update_fields=["status"])
        try:
            call_controller(
                BaseControl.update.__name__, strategy.strategy_id, self.get_base_control_type(strategy.strategy_type)
            )
        except Exception as err:
            strategy.status = StrategyStatusChoices.UPDATE_FAILED
            strategy.status_msg = str(err)
            strategy.save(update_fields=["status", "status_msg"])
            raise err


class DeleteStrategy(StrategyV2Base):
    name = gettext_lazy("Delete Strategy")
    audit_action = ActionEnum.DELETE_STRATEGY

    @transaction.atomic()
    def perform_request(self, validated_request_data):
        strategy = get_object_or_404(Strategy, strategy_id=validated_request_data["strategy_id"])
        # delete tags
        StrategyTag.objects.filter(strategy_id=validated_request_data["strategy_id"]).delete()
        StrategyTool.objects.filter(strategy=strategy).delete()

        # delete
        try:
            call_controller(
                BaseControl.delete.__name__,
                validated_request_data["strategy_id"],
                self.get_base_control_type(strategy.strategy_type),
            )
        except Exception as err:
            strategy.status = StrategyStatusChoices.DELETE_FAILED
            strategy.status_msg = str(err)
            strategy.save(update_fields=["status", "status_msg"])
            raise err
        # delete strategy
        self.add_audit_instance_to_context(instance=StrategyAuditInstance(strategy))
        strategy.delete()
        self.delete_enum_mappings(strategy_id=strategy.strategy_id)


class ListStrategy(StrategyV2Base):
    name = gettext_lazy("List Strategy")
    RequestSerializer = ListStrategyRequestSerializer
    ResponseSerializer = ListStrategyResponseSerializer
    many_response_data = True
    audit_action = ActionEnum.LIST_STRATEGY

    def perform_request(self, validated_request_data):
        # init queryset
        order_field = validated_request_data.get("order_field") or "-strategy_id"
        # 策略关联风险起始时间
        strategy_risk_start_time = timezone.now() - datetime.timedelta(days=STRATEGY_RISK_DEFAULT_INTERVAL)
        # init queryset
        risk_count_subquery = (
            Risk.objects.filter(strategy_id=OuterRef('strategy_id'), event_time__gte=strategy_risk_start_time)
            .values('strategy_id')
            .annotate(count=Count('*'))
            .values('count')
        )

        queryset: QuerySet[Strategy] = (
            Strategy.objects.filter(
                namespace=validated_request_data["namespace"],
            )
            .annotate(risk_count=Subquery(risk_count_subquery, output_field=IntegerField()))
            .prefetch_related("tools")
        )
        queryset = queryset.exclude(source=StrategySource.SYSTEM)
        # 排序
        queryset = queryset.order_by(order_field)

        # 特殊筛选
        if HAS_UPDATE_TAG_ID in validated_request_data.get("tag", []):
            validated_request_data["tag"] = [t for t in validated_request_data["tag"] if t != HAS_UPDATE_TAG_ID]
            queryset = queryset.filter(
                strategy_id__in=[s.strategy_id for s in resource.strategy_v2.list_has_update_strategy()]
            )
        if NO_TAG_ID in validated_request_data.get("tag", []):
            validated_request_data["tag"] = [t for t in validated_request_data["tag"] if t != NO_TAG_ID]
            queryset = queryset.exclude(strategy_id__in=StrategyTag.objects.values_list("strategy_id").distinct())
        # tag filter
        if validated_request_data.get("tag"):
            # tag 筛选
            strategy_ids = StrategyTag.objects.filter(tag_id__in=validated_request_data["tag"]).values("strategy_id")
            queryset = queryset.filter(strategy_id__in=strategy_ids)
        # exact filter
        for key in ["strategy_id", "status", "strategy_type", "link_table_uid"]:
            if validated_request_data.get(key):
                queryset = queryset.filter(**{f"{key}__in": validated_request_data[key]})
        # fuzzy filter
        for key in ["strategy_name"]:
            if validated_request_data.get(key):
                q = Q()
                for item in validated_request_data[key]:
                    q |= Q(**{f"{key}__icontains": item})
                queryset = queryset.filter(q)

        # 预加载策略标签，避免N+1查询
        queryset = queryset.prefetch_related(
            models.Prefetch(
                'tags',  # 使用StrategyTag的related_name
                queryset=StrategyTag.objects.select_related('tag'),
                to_attr='prefetched_tags',
            )
        )

        # response
        return queryset


class ListStrategyAll(StrategyV2Base):
    name = gettext_lazy("List All Strategy")

    def perform_request(self, validated_request_data):
        if not ActionPermission(
            actions=[ActionEnum.LIST_STRATEGY, ActionEnum.LIST_RISK, ActionEnum.EDIT_RISK]
        ).has_permission(request=get_local_request(), view=self):
            return []
        strategies: List[Strategy] = Strategy.objects.exclude(source=StrategySource.SYSTEM)
        data = [{"label": s.strategy_name, "value": s.strategy_id} for s in strategies]
        data.sort(key=lambda s: s["label"])
        return data


class GetStrategyEnumMappingByCollectionKeys(StrategyV2Base):
    """
    获取某个策略的某个集合中的某个枚举值的信息。可以一次性获取多个不同集合中的多个枚举值的信息。
    请求：
    ```
        {
            "collection_keys": [
                {"collection_id": "status_collection_112233", "key": "1"},
                {"collection_id": "user_collection_112233", "key": "2"},
            ],
            "related_type": "strategy",
            "related_object_id": 1 # 策略ID
        }
    ```
    响应：
    ```
    [{"collection_id":"status_collection_112233","key": "1", "name": "未处理"},
    {"collection_id":"user_collection_112233","key": "2", "name": "张三"}]
    ```

    可选权限上下文（调用方透传）：
    - caller_resource_type：调用方资源类型（当前支持：risk）
    - caller_resource_id：调用方资源ID（如风险ID）
    行为：若提供且鉴权通过，则基于调用方上下文放行（跳过原有权限）；若鉴权失败，返回标准权限异常。
    """

    name = gettext_lazy("获取某个策略的某个集合中的某个枚举值的信息")
    RequestSerializer = EnumMappingByCollectionKeysWithCallerSerializer
    ResponseSerializer = EnumMappingSerializer
    many_response_data = True

    def perform_request(self, validated_request_data):
        # 特殊权限分支：当来自调用方上下文（目前支持 risk）时，校验其权限
        validated_request_data["related_type"] = EnumMappingRelatedType.STRATEGY.value

        validated_request_data["caller_validated"] = True
        validated_request_data["current_type"] = CurrentType.STRATEGY.value
        validated_request_data["current_object_id"] = validated_request_data["related_object_id"]
        should_skip_permission_from(validated_request_data, get_request_username())

        return resource.meta.get_enum_mapping_by_collection_keys(**validated_request_data)


class GetStrategyEnumMappingByCollection(StrategyV2Base):
    """
    获取某个策略的某个集合中的所有枚举值的信息。
    请求：
    ```
    {
        "collection_id": "status_collection_112233",
        "related_type": "strategy",
        "related_object_id": 1
    }
    ```
    响应：
    ```
    [{"collection_id":"status_collection_112233","key": "1", "name": "未处理"},
    {"collection_id":"status_collection_112233","key": "2", "name": "已处理"}]
    ```

    可选权限上下文（调用方透传）：
    - caller_resource_type：调用方资源类型（当前支持：risk）
    - caller_resource_id：调用方资源ID（如风险ID）
    行为：若提供且鉴权通过，则基于调用方上下文放行（跳过原有权限）；若鉴权失败，返回标准权限异常。
    """

    name = gettext_lazy("获取某个策略的某个集合中的所有枚举值的信息")
    RequestSerializer = EnumMappingByCollectionWithCallerSerializer
    ResponseSerializer = EnumMappingSerializer
    many_response_data = True

    def perform_request(self, validated_request_data):
        validated_request_data["related_type"] = EnumMappingRelatedType.STRATEGY.value

        # 特殊权限分支：当来自调用方上下文（目前支持 risk）时，校验其权限
        validated_request_data["caller_validated"] = True
        validated_request_data["current_type"] = CurrentType.STRATEGY.value
        validated_request_data["current_object_id"] = validated_request_data["related_object_id"]
        should_skip_permission_from(validated_request_data, get_request_username())

        return resource.meta.get_enum_mapping_by_collection(**validated_request_data)


class ToggleStrategy(StrategyV2Base):
    name = gettext_lazy("Toggle Strategy")
    RequestSerializer = ToggleStrategyRequestSerializer
    audit_action = ActionEnum.EDIT_STRATEGY

    def perform_request(self, validated_request_data):
        strategy = get_object_or_404(Strategy, strategy_id=validated_request_data["strategy_id"])
        self.add_audit_instance_to_context(instance=StrategyAuditInstance(strategy))
        controller_cls = self.get_base_control_type(strategy.strategy_type)
        # 更新处理人
        strategy.updated_by = get_request_username()
        strategy.save(update_fields=["updated_by"])
        if validated_request_data["toggle"]:
            call_controller(BaseControl.enable.__name__, strategy.strategy_id, controller_cls)
            return
        call_controller(BaseControl.disabled.__name__, strategy.strategy_id, controller_cls)


class RetryStrategy(StrategyV2Base):
    name = gettext_lazy("Retry Strategy")
    RequestSerializer = RetryStrategyRequestSerializer

    def perform_request(self, validated_request_data):
        # load strategy
        strategy = get_object_or_404(Strategy, strategy_id=validated_request_data["strategy_id"])
        # try update
        controller_cls = self.get_base_control_type(strategy.strategy_type)
        need_update = strategy.backend_data and (
            strategy.backend_data.get("id") or strategy.backend_data.get("flow_id")
        )
        # 更新处理人
        strategy.updated_by = get_request_username()
        strategy.save(update_fields=["updated_by"])
        func_name = BaseControl.update.__name__ if need_update else BaseControl.create.__name__
        try:
            call_controller(func_name, strategy.strategy_id, controller_cls)
        except Exception as err:
            strategy.status = StrategyStatusChoices.FAILED
            strategy.status_msg = str(err)
            strategy.save(update_fields=["status", "status_msg"])
            raise err


class StrategyJudge:
    """
    抽象基类，定义判断策略接口
    """

    def judge(self, strategy) -> bool:
        raise NotImplementedError


class ControlVersionJudge(StrategyJudge):
    """
    判断控制版本是否需要更新
    """

    @cached_property
    def controls(self) -> dict:
        # load last control versions
        all_controls = resource.analyze.control()
        controls = {}
        # 获取每个版本的最新版本
        for cv in all_controls:
            if cv["control_id"] not in controls.keys():
                controls[cv["control_id"]] = cv["versions"][0]["control_version"]
        return controls

    def judge(self, strategy) -> bool:
        if any(
            [
                strategy.strategy_type != StrategyType.MODEL.value,
                not strategy.control_id,
                not strategy.control_version,
            ]
        ):
            return False
        return self.controls.get(strategy.control_id, strategy.control_version) > strategy.control_version


class LinkTableVersionJudge(StrategyJudge):
    """
    判断联表版本是否需要更新
    """

    @cached_property
    def link_tables(self) -> dict:
        # 获取最新版本的联表
        return {
            link_table.uid: link_table.version
            for link_table in list(LinkTable.list_max_version_link_table().only("uid", "version"))
        }

    def judge(self, strategy) -> bool:
        if any(
            [
                strategy.strategy_type != StrategyType.RULE.value,
                not strategy.link_table_uid,
                not strategy.link_table_version,
            ]
        ):
            return False
        return self.link_tables.get(strategy.link_table_uid, 0) > strategy.link_table_version


class CompositeJudge(StrategyJudge):
    """
    组合多个判断策略
    """

    def __init__(self, *judges: StrategyJudge):
        self.judges = judges

    def judge(self, strategy) -> bool:
        return any(judge.judge(strategy) for judge in self.judges)

    def batch_judge(self, strategies: List[Strategy]) -> List[Strategy]:
        return [s for s in strategies if self.judge(s)]


class ListHasUpdateStrategy(StrategyV2Base):
    name = gettext_lazy("List Has Update Strategy")
    audit_action = ActionEnum.LIST_STRATEGY

    def perform_request(self, validated_request_data):
        # 获取所有策略
        all_strategies: List[Strategy] = list(Strategy.objects.all().defer("configs"))
        # 判断需要更新的数量
        composite_judge = CompositeJudge(
            ControlVersionJudge(),
            LinkTableVersionJudge(),
        )
        return composite_judge.batch_judge(all_strategies)


class ListStrategyTags(StrategyV2Base):
    name = gettext_lazy("List Strategy Tags")
    ResponseSerializer = ListStrategyTagsResponseSerializer
    many_response_data = True

    def perform_request(self, validated_request_data):
        # load all tags
        tag_count = list(StrategyTag.objects.all().values("tag_id").annotate(strategy_count=Count("tag_id")).order_by())
        tag_map = {t.tag_id: {"name": t.tag_name} for t in Tag.objects.all()}
        for t in tag_count:
            t.update({"tag_name": tag_map.get(t["tag_id"], {}).get("name", t["tag_id"])})
        # sort
        tag_count.sort(key=lambda tag: [lazy_pinyin(tag["tag_name"].lower(), errors="ignore"), tag["tag_name"].lower()])
        # add has update
        tag_count = [
            {
                "tag_name": str(HAS_UPDATE_TAG_NAME),
                "tag_id": HAS_UPDATE_TAG_ID,
                "strategy_count": len(resource.strategy_v2.list_has_update_strategy()),
            }
        ] + tag_count
        # response
        return tag_count


class ListStrategyFields(StrategyV2Base):
    name = gettext_lazy("List Strategy Fields")
    RequestSerializer = ListStrategyFieldsRequestSerializer
    ResponseSerializer = ListStrategyFieldsResponseSerializer
    many_response_data = True

    def perform_request(self, validated_request_data):
        # check permission
        if not ActionPermission(
            actions=[
                ActionEnum.CREATE_STRATEGY,
                ActionEnum.LIST_STRATEGY,
                ActionEnum.EDIT_STRATEGY,
                ActionEnum.DELETE_STRATEGY,
            ]
        ).has_permission(request=get_local_request(), view=self):
            return []
        # load log field
        system_id = validated_request_data.get("system_id")
        action_id = validated_request_data.get("action_id")
        if system_id and action_id:
            data = self.load_action_fields(validated_request_data["namespace"], system_id, action_id)
        else:
            data = self.load_public_fields()
        # sort and response
        data.sort(key=lambda field: (field["priority_index"], field["field_name"]), reverse=True)
        return data

    @classmethod
    def load_action_fields(cls, namespace: str, system_id: str, action_id: str) -> List[dict]:
        data = []
        end_time = datetime.datetime.now()
        start_time = end_time - datetime.timedelta(days=7)
        if FeatureHandler(FeatureTypeChoices.ENABLE_DORIS).check():
            logs = resource.query.collector_search_all(
                namespace=namespace,
                start_time=start_time.strftime(api_settings.DATETIME_FORMAT),
                end_time=end_time.strftime(api_settings.DATETIME_FORMAT),
                page=1,
                page_size=1,
                bind_system_info=False,
                filters=[
                    {
                        "field_name": SYSTEM_ID.field_name,
                        "operator": QueryConditionOperator.INCLUDE.value,
                        "filters": [system_id],
                    },
                    {
                        "field_name": ACTION_ID.field_name,
                        "operator": QueryConditionOperator.INCLUDE.value,
                        "filters": [action_id],
                    },
                ],
            )
        else:
            logs = resource.query.search_all(
                namespace=namespace,
                start_time=start_time.strftime(api_settings.DATETIME_FORMAT),
                end_time=end_time.strftime(api_settings.DATETIME_FORMAT),
                query_string="*",
                sort_list="",
                page=1,
                page_size=1,
                bind_system_info=False,
                system_id=system_id,
                action_id=action_id,
            )
        if logs.get("results", []):
            for key, _ in logs["results"][0].get("extend_data", {}).items():
                data.append(
                    {
                        "field_name": f"{EXTEND_DATA.field_name}.{key}",
                        "description": f"{str(EXTEND_DATA.description)}.{key}",
                        "field_type": PYTHON_TO_ES.get(type(key), type(key)),
                        "priority_index": EXTEND_DATA.priority_index,
                        "is_dimension": False,
                    }
                )
        return data

    def load_public_fields(self) -> List[dict]:
        # load exist fields
        data = [
            {
                "field_name": field.field_name,
                "description": f"{str(field.description)}({field.field_name})",
                "field_type": field.field_type,
                "priority_index": field.priority_index,
                "is_dimension": field.field_type in DIMENSION_FIELD_TYPES,
            }
            for field in STRATEGY_DISPLAY_FIELDS
        ]
        # 没有配置用户信息来源则直接返回
        if not settings.SNAPSHOT_USERINFO_RESOURCE_URL:
            return data
        # load snapshot user info fields
        try:
            schema = api.user_manage.get_snapshot_schema()
        except APIRequestError:
            schema = {}
        for field_name, field_data in schema.items():
            if field_name in SNAPSHOT_USER_INFO_HIDE_FIELDS:
                continue
            data.append(
                {
                    "field_name": "{}.{}".format(SNAPSHOT_USER_INFO.field_name, field_name),
                    "description": "{}.{}({})".format(
                        gettext(
                            DataMap.get_alias(
                                FILED_DISPLAY_NAME_ALIAS_KEY,
                                SNAPSHOT_USER_INFO.field_name,
                                default=SNAPSHOT_USER_INFO.description,
                            )
                        ),
                        gettext(field_data.get("description", field_name)),
                        field_name,
                    ),
                    "field_type": field_data.get("type", ""),
                    "priority_index": SNAPSHOT_USER_INFO.priority_index,
                    "is_dimension": True,
                }
            )
        return data


class GetStrategyFieldValue(StrategyV2Base):
    name = gettext_lazy("Get Strategy Field Value")
    RequestSerializer = GetStrategyFieldValueRequestSerializer
    ResponseSerializer = GetStrategyFieldValueResponseSerializer
    many_response_data = True

    def perform_request(self, validated_request_data):
        # check permission
        if not ActionPermission(
            actions=[
                ActionEnum.CREATE_STRATEGY,
                ActionEnum.LIST_STRATEGY,
                ActionEnum.EDIT_STRATEGY,
                ActionEnum.DELETE_STRATEGY,
            ]
        ).has_permission(request=get_local_request(), view=self):
            return []
        handler = FieldValueHandler(
            field_name=validated_request_data["field_name"],
            namespace=validated_request_data["namespace"],
            system_id=validated_request_data.get("system_id"),
        )
        return handler.values


class GetStrategyCommon(StrategyV2Base):
    name = gettext_lazy("Get Strategy Common")
    ResponseSerializer = GetStrategyCommonResponseSerializer

    def perform_request(self, validated_request_data):
        return {
            "strategy_operator": choices_to_dict(StrategyOperator, val="value", name="label"),
            "filter_operator": choices_to_dict(FilterOperator, val="value", name="label"),
            "algorithm_operator": choices_to_dict(StrategyAlgorithmOperator, val="value", name="label"),
            "table_type": [{"value": value, "label": str(label)} for value, label in TableType.choices],
            "strategy_status": choices_to_dict(StrategyStatusChoices, val="value", name="label"),
            "offset_unit": choices_to_dict(OffsetUnit, val="value", name="label"),
            "mapping_type": choices_to_dict(MappingType, val="value", name="label"),
            "risk_level": choices_to_dict(RiskLevel, val="value", name="label"),
            "strategy_type": choices_to_dict(StrategyType, val="value", name="label"),
            "link_table_join_type": choices_to_dict(LinkTableJoinType, val="value", name="label"),
            "link_table_table_type": choices_to_dict(LinkTableTableType, val="value", name="label"),
            "rule_audit_aggregate_type": choices_to_dict(RuleAuditAggregateType, val="value", name="label"),
            "rule_audit_field_type": choices_to_dict(RuleAuditFieldType, val="value", name="label"),
            "rule_audit_config_type": choices_to_dict(RuleAuditConfigType, val="value", name="label"),
            "rule_audit_source_type": choices_to_dict(RuleAuditSourceType, val="value", name="label"),
            "rule_audit_condition_operator": choices_to_dict(RuleAuditConditionOperator, val="value", name="label"),
            "rule_audit_where_connector": choices_to_dict(RuleAuditWhereConnector, val="value", name="label"),
        }


class ListTables(StrategyV2Base, CacheResource):
    name = gettext_lazy("List Tables")
    RequestSerializer = ListTablesRequestSerializer
    cache_type = CacheTypeItem(key="ListTables", timeout=60, user_related=False)

    def perform_request(self, validated_request_data):
        return TableHandler(**validated_request_data).list_tables()


class GetRTFields(StrategyV2Base):
    name = gettext_lazy("Get RT Fields")
    RequestSerializer = GetRTFieldsRequestSerializer
    ResponseSerializer = GetRTFieldsResponseSerializer
    many_response_data = True

    def perform_request(self, validated_request_data):
        fields = api.bk_base.get_rt_fields(result_table_id=validated_request_data["table_id"])
        result = enhance_rt_fields(fields, validated_request_data["table_id"])
        return result


class BulkGetRTFields(StrategyV2Base):
    name = gettext_lazy("Bulk Get RT Fields")
    RequestSerializer = BulkGetRTFieldsRequestSerializer
    ResponseSerializer = BulkGetRTFieldsResponseSerializer
    many_response_data = True

    def perform_request(self, validated_request_data):
        table_ids = validated_request_data["table_ids"]
        bulk_request_params = [{"table_id": table_id} for table_id in table_ids]
        bulk_resp = resource.strategy_v2.get_rt_fields.bulk_request(bulk_request_params)
        return [
            {
                "table_id": params["table_id"],
                "fields": resp,
            }
            for params, resp in zip(bulk_request_params, bulk_resp)
        ]


class GetRTMeta(StrategyV2Base):
    name = gettext_lazy("Get RT Meta")
    RequestSerializer = GetRTMetaRequestSerializer

    def perform_request(self, validated_request_data):
        """获取数据表完整元信息"""
        result_table_id = validated_request_data["table_id"]
        futures = []

        # 创建一个线程池来并发执行任务
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures.append(executor.submit(self.get_meta, result_table_id))
            futures.append(executor.submit(self.get_data_manager, result_table_id))
            futures.append(executor.submit(self.get_sensitivity_info, result_table_id))

            # 获取并合并结果
            result = {}
            for future in as_completed(futures):
                result.update(future.result())

        result["formatted_fields"] = enhance_rt_fields(result["fields"], result_table_id)
        return result

    def get_meta(self, result_table_id):
        """获取数据表的元信息。"""
        return api.bk_base.get_result_table(result_table_id=result_table_id, related=["storages", "fields"])

    def get_data_manager(self, result_table_id):
        """获取数据表的维护者。"""
        result = {
            'managers': api.bk_base.get_role_users_list(role_id="result_table.manager", scope_id=result_table_id),
            'viewers': api.bk_base.get_role_users_list(role_id="result_table.viewer", scope_id=result_table_id),
        }
        return result

    def get_sensitivity_info(self, result_table_id):
        return {
            "sensitivity_info": api.bk_base.get_sensitivity_info_via_dataset(
                data_set_type="result_table", data_set_id=result_table_id
            )
        }


class GetRTLastData(StrategyV2Base):
    name = gettext_lazy("Get RT Last Data")
    RequestSerializer = GetRTLastDataRequestSerializer
    many_response_data = True

    def perform_request(self, validated_request_data):
        """获取数据表的最新数据"""
        result_table_id = validated_request_data["table_id"]
        limit = validated_request_data['limit']
        result = self.get_last_data(result_table_id, limit)
        return result

    def get_last_data(self, result_table_id, limit):
        """获取数据表的最新数据"""
        today = datetime.datetime.now().strftime('%Y%m%d')
        rt_info = api.bk_base.get_result_table(result_table_id=result_table_id)
        if not is_asset(rt_info):
            # 非维表，添加过滤条件 thedate = current_date
            sql = (
                f"SELECT * FROM {result_table_id} WHERE thedate = {today} ORDER BY dteventtimestamp DESC LIMIT {limit}"
            )
        else:
            # 维表，直接查询
            sql = f"SELECT * FROM {result_table_id} LIMIT {limit}"

        resp = api.bk_base.query_sync(sql=sql)
        return {"last_data": resp.get("list", [{}])}


class GetStrategyStatus(StrategyV2Base):
    name = gettext_lazy("Get Strategy Status")
    RequestSerializer = GetStrategyStatusRequestSerializer
    audit_action = ActionEnum.LIST_STRATEGY

    def perform_request(self, validated_request_data):
        return {
            s.strategy_id: {"status": s.status, "status_msg": s.status_msg}
            for s in Strategy.objects.filter(strategy_id__in=validated_request_data["strategy_ids"])
        }


class GetEventFieldsConfig(StrategyV2Base):
    name = gettext_lazy("Get Event Info Fields")
    RequestSerializer = GetEventInfoFieldsRequestSerializer
    ResponseSerializer = GetEventInfoFieldsResponseSerializer

    def get_event_basic_field_configs(self, risk: Optional[Risk], has_permission: bool) -> List[EventInfoField]:
        """
        基础字段
        """

        return [
            EventInfoField(
                field_name=field.field_name,
                display_name=str(field.description),
                description=(
                    str(RAW_EVENT_ID_REMARK)
                    if field == EventMappingFields.RAW_EVENT_ID
                    else str(field.property.get("remark", ""))
                ),
                example=preprocess_data(getattr(risk, field.field_name, "")) if risk and has_permission else "",
                is_show=True,
                duplicate_field=False,
            )
            for field in [
                EventMappingFields.RAW_EVENT_ID,
                EventMappingFields.OPERATOR,
                EventMappingFields.EVENT_TIME,
                EventMappingFields.EVENT_SOURCE,
                EventMappingFields.STRATEGY_ID,
                EventMappingFields.EVENT_CONTENT,
                EventMappingFields.EVENT_TYPE,
            ]
        ]

    def get_risk_meta_field_config(
        self, strategy: Optional[Strategy], risk: Optional[Risk], has_permission: bool
    ) -> List[EventInfoField]:
        """
        风险元字段配置（共17项），与 event_basic_field_configs 保持相同数据结构
        """
        return [
            EventInfoField(
                field_name=field.field_name,
                display_name=str(field.description),
                description="",
                example="",
                is_show=True,
                duplicate_field=False,
            )
            for field in RiskMetaFields().fields
        ]

    def get_event_data_field_configs(
        self, strategy: Optional[Strategy], risk: Optional[Risk], has_permission: bool
    ) -> List[EventInfoField]:
        """
        事件数据字段
        合并策略配置的event_data_field_configs和风险中的event_data
        """
        if not strategy:
            return []

        # 收集所有的字段
        field_dict: Dict[str, EventInfoField] = {}

        # 1. 从策略配置中获取字段
        for field in strategy.event_data_field_configs:
            field_dict[field["field_name"]] = EventInfoField(
                field_name=field["field_name"],
                display_name=field.get("display_name", field["field_name"]),
                example="",
                description="",
                is_show=field.get("is_show", True),
                duplicate_field=field.get("duplicate_field", False),
            )

        # 2. 从风险数据中获取字段
        if risk:
            risk_data = risk.event_data or {}
            for key, value in risk_data.items():
                if key not in field_dict:
                    field_dict[key] = EventInfoField(
                        field_name=key,
                        display_name=key,
                        example="",
                        description="",
                        is_show=True,
                        duplicate_field=False,
                    )
                if has_permission:
                    field_dict[key]["example"] = preprocess_data(value)

        return list(field_dict.values())

    def get_event_evidence_field_configs(
        self, strategy: Optional[Strategy], risk: Optional[Risk], has_permission: bool
    ) -> List[EventInfoField]:
        """
        事件证据字段
        合并策略配置的event_evidence_field_configs和风险中的event_evidence
        """
        if not strategy:
            return []

        # 收集所有的字段
        field_dict: Dict[str, EventInfoField] = {}

        # 1. 从策略配置中获取字段
        for field in strategy.event_evidence_field_configs or []:
            field_dict[field["field_name"]] = EventInfoField(
                field_name=field["field_name"],
                display_name=field.get("display_name", field["field_name"]),
                example="",
                description=field.get("description", ""),
                is_show=field.get("is_show", True),
                duplicate_field=field.get("duplicate_field", False),
            )

        # 2. 从风险数据中获取字段
        if risk:
            try:
                event_evidence = json.loads(risk.event_evidence)[0] if risk.event_evidence else {}
            except (json.JSONDecodeError, IndexError, KeyError):
                event_evidence = {}

            for key, value in event_evidence.items():
                if key not in field_dict:
                    field_dict[key] = EventInfoField(
                        field_name=key,
                        display_name=key,
                        example="",
                        description="",
                        is_show=True,
                        duplicate_field=False,
                    )
                if has_permission:
                    field_dict[key]["example"] = preprocess_data(value)

        return list(field_dict.values())

    def perform_request(self, validated_request_data):
        """
        获取策略配置字段
        1. 没有策略：返回基础字段
        2. 有策略：组合策略配置和实际风险数据
        """
        strategy_id = validated_request_data.get("strategy_id")
        strategy: Optional[Strategy] = Strategy.objects.filter(strategy_id=strategy_id).first()
        if not strategy:
            return {
                "event_basic_field_configs": self.get_event_basic_field_configs(None, False),
                "event_data_field_configs": [],
                "event_evidence_field_configs": [],
                "risk_meta_field_config": self.get_risk_meta_field_config(None, None, False),
            }

        # 有策略，查找相关风险
        risk: Optional[Risk] = Risk.objects.filter(strategy_id=strategy_id).order_by("-event_time").first()
        has_permission = False

        if risk:
            # 权限认证
            permission = RiskViewPermission(actions=[ActionEnum.LIST_RISK], resource_meta=ResourceEnum.RISK)
            try:
                has_permission = permission.has_risk_permission(risk_id=risk.risk_id, operator=get_request_username())
            except PermissionException:
                pass

        return {
            "event_basic_field_configs": self.get_event_basic_field_configs(risk, has_permission),
            "event_data_field_configs": self.get_event_data_field_configs(strategy, risk, has_permission),
            "event_evidence_field_configs": self.get_event_evidence_field_configs(strategy, risk, has_permission),
            "risk_meta_field_config": self.get_risk_meta_field_config(strategy, risk, has_permission),
        }


class GetStrategyDisplayInfo(StrategyV2Base):
    """
    获取策略展示信息
    """

    name = gettext_lazy("获取策略展示信息")
    RequestSerializer = GetStrategyDisplayInfoRequestSerializer

    def perform_request(self, validated_request_data):
        strategy_ids = validated_request_data["strategy_ids"]
        strategies: QuerySet[Strategy] = Strategy.objects.filter(strategy_id__in=strategy_ids).only("risk_level")
        return {strategy.strategy_id: {"risk_level": strategy.risk_level} for strategy in strategies}


class LinkTableBase(AuditMixinResource, abc.ABC):
    tags = ["LinkTable"]
    audit_resource_type = ResourceEnum.LINK_TABLE

    def add_audit_instance_to_context(self, link_table: LinkTable, old_link_table: Optional[dict] = None):
        if old_link_table:
            setattr(link_table, "instance_origin_data", old_link_table)
        super().add_audit_instance_to_context(instance=LinkTableAuditInstance(link_table))

    def _save_tags(self, link_table_uid: str, tag_names: list) -> None:
        LinkTableTag.objects.filter(link_table_uid=link_table_uid).delete()
        if not tag_names:
            return
        tags = resource.meta.save_tags([{"tag_name": t} for t in tag_names])
        LinkTableTag.objects.bulk_create(
            [LinkTableTag(link_table_uid=link_table_uid, tag_id=t["tag_id"]) for t in tags]
        )


class CreateLinkTable(LinkTableBase):
    name = gettext_lazy("创建联表")
    RequestSerializer = CreateLinkTableRequestSerializer
    ResponseSerializer = CreateLinkTableResponseSerializer
    audit_action = ActionEnum.CREATE_LINK_TABLE

    @transaction.atomic()
    def create_link_table(self, validated_request_data) -> LinkTable:
        # pop tag
        tag_names = validated_request_data.pop("tags", [])
        # save link table
        link_table: LinkTable = LinkTable.objects.create(**validated_request_data, version=1)
        # save tag
        self._save_tags(link_table_uid=link_table.uid, tag_names=tag_names)
        return link_table

    def perform_request(self, validated_request_data):
        link_table = self.create_link_table(validated_request_data)
        # audit
        self.add_audit_instance_to_context(link_table)
        # auth
        username = get_request_username()
        if username:
            resource_instance = ResourceEnum.LINK_TABLE.create_instance(link_table.uid)
            Permission(username).grant_creator_action(resource_instance)
        return link_table


class UpdateLinkTable(LinkTableBase):
    name = gettext_lazy("更新联表")
    RequestSerializer = UpdateLinkTableRequestSerializer
    ResponseSerializer = UpdateLinkTableResponseSerializer
    audit_action = ActionEnum.EDIT_LINK_TABLE

    @transaction.atomic()
    def update_link_table(self, validated_request_data) -> LinkTable:
        """
        更新联表
        如果更新联表的配置信息，则需要创建新版本的联表
        """
        uid = validated_request_data["uid"]
        tags = validated_request_data.pop("tags", Empty())
        # 获取最新版本的联表
        link_table = LinkTable.last_version_link_table(uid=uid)
        if not link_table:
            raise Http404(gettext("LinkTable not found: %s") % uid)
        # old link_table
        old_link_table = LinkTableInfoSerializer(link_table).data
        # 更新或创建新版本联表
        need_update_config = "config" in validated_request_data.keys()
        if not need_update_config:
            for key, value in validated_request_data.items():
                setattr(link_table, key, value)
            link_table.save(update_fields=validated_request_data.keys())
        else:
            create_link_table_params = {
                "namespace": link_table.namespace,
                "uid": link_table.uid,
                "version": link_table.version + 1,
                "name": link_table.name,
                "config": link_table.config,
                "description": link_table.description,
                "created_at": link_table.created_at,
                "created_by": link_table.created_by,
                **validated_request_data,
            }
            link_table = LinkTable.objects.create(**create_link_table_params)
        # save tag
        if not isinstance(tags, Empty):
            self._save_tags(link_table_uid=link_table.uid, tag_names=tags)
        # audit
        self.add_audit_instance_to_context(link_table, old_link_table)
        return link_table

    def perform_request(self, validated_request_data):
        return self.update_link_table(validated_request_data=validated_request_data)


class DeleteLinkTable(LinkTableBase):
    name = gettext_lazy("删除联表")
    audit_action = ActionEnum.DELETE_LINK_TABL

    @transaction.atomic()
    def perform_request(self, validated_request_data):
        uid = validated_request_data["uid"]
        # 如果有策略使用了该联表则不能删除
        if Strategy.objects.filter(strategy_type=StrategyType.RULE, link_table_uid=uid).exists():
            raise LinkTableHasStrategy()
        link_table = LinkTable.last_version_link_table(uid=uid)
        if not link_table:
            raise Http404(gettext("LinkTable not found: %s") % uid)
        # audit
        self.add_audit_instance_to_context(link_table)
        # 删除联表
        LinkTableTag.objects.filter(link_table_uid=uid).delete()
        LinkTable.objects.filter(uid=uid).delete()


class ListLinkTable(LinkTableBase):
    name = gettext_lazy("查询联表列表")
    RequestSerializer = ListLinkTableRequestSerializer
    audit_action = ActionEnum.LIST_LINK_TABLE
    bind_request = True

    def perform_request(self, validated_request_data):
        request = validated_request_data.pop("_request")
        tags = validated_request_data.pop("tags", [])
        sort = validated_request_data.pop("sort", [])
        no_tag = validated_request_data.pop("no_tag", False)
        # 获取最新版本的联表
        link_tables = LinkTable.list_max_version_link_table().filter(**validated_request_data)
        # 过滤标签
        if no_tag or int(NO_TAG_ID) in tags:
            link_table_uids = LinkTableTag.objects.values_list("link_table_uid").distinct()
            link_tables = link_tables.exclude(uid__in=link_table_uids)
        elif tags:
            link_table_uids = LinkTableTag.objects.filter(tag_id__in=tags).values_list("link_table_uid")
            link_tables = link_tables.filter(uid__in=link_table_uids)
        # 排序
        if sort:
            link_tables = link_tables.order_by(*sort)
        # 分页
        link_tables, page = paginate_queryset(queryset=link_tables, request=request)
        if sort:
            link_tables = link_tables.order_by(*sort)
        link_table_uids = link_tables.values("uid")
        # 填充标签
        all_tags = LinkTableTag.objects.filter(link_table_uid__in=link_table_uids)
        tag_map = defaultdict(list)
        for t in all_tags:
            tag_map[t.link_table_uid].append(t.tag_id)
        # 填充关联的策略数
        strategies = Strategy.objects.filter(strategy_type=StrategyType.RULE, link_table_uid__in=link_table_uids)
        strategy_cnt_map = {
            strategy["link_table_uid"]: strategy["count"]
            for strategy in strategies.values("link_table_uid").annotate(count=Count("link_table_uid")).order_by()
        }
        # 填充关联的最小联表版本
        strategy_version_map = {
            strategy["link_table_uid"]: strategy["version"]
            for strategy in strategies.values("link_table_uid").annotate(version=Min("link_table_version")).order_by()
        }
        for link_table in link_tables:
            # 填充关联的策略数
            setattr(link_table, "strategy_count", strategy_cnt_map.get(link_table.uid, 0))
            # 填充标签
            setattr(link_table, "tags", tag_map.get(link_table.uid, []))
            # 填充是否存在需要更新的策略
            setattr(
                link_table,
                "need_update_strategy",
                strategy_version_map.get(link_table.uid, link_table.version) < link_table.version,
            )
        # 响应
        return page.get_paginated_response(data=ListLinkTableResponseSerializer(instance=link_tables, many=True).data)


class ListLinkTableAll(LinkTableBase):
    name = gettext_lazy("查询所有联表")
    ResponseSerializer = ListLinkTableAllResponseSerializer
    many_response_data = True

    def perform_request(self, validated_request_data):
        return LinkTable.list_max_version_link_table()


class GetLinkTable(LinkTableBase):
    name = gettext_lazy("查询联表详情")
    RequestSerializer = GetLinkTableRequestSerializer
    ResponseSerializer = GetLinkTableResponseSerializer
    audit_action = ActionEnum.VIEW_LINK_TABLE

    def perform_request(self, validated_request_data):
        uid = validated_request_data["uid"]
        version = validated_request_data.get("version")
        if version:
            link_table = get_object_or_404(LinkTable, uid=uid, version=version)
        else:
            link_table = LinkTable.last_version_link_table(uid)
        if not link_table:
            raise Http404(gettext("LinkTable not found: %s") % uid)
        # 填充标签
        setattr(link_table, "tags", LinkTableTag.objects.filter(link_table_uid=uid).values_list("tag_id", flat=True))
        return link_table


class ListLinkTableTags(LinkTableBase):
    name = gettext_lazy("查询联表标签列表")
    ResponseSerializer = ListLinkTableTagsResponseSerializer
    many_response_data = True
    audit_action = ActionEnum.LIST_LINK_TABLE

    def perform_request(self, validated_request_data):
        # load all tags
        tag_count = list(
            LinkTableTag.objects.all().values("tag_id").annotate(link_table_count=Count("tag_id")).order_by()
        )
        tag_map = {t.tag_id: {"name": t.tag_name} for t in Tag.objects.all()}
        for t in tag_count:
            t.update({"tag_name": tag_map.get(t["tag_id"], {}).get("name", t["tag_id"])})
        # sort
        tag_count.sort(key=lambda tag: [lazy_pinyin(tag["tag_name"].lower(), errors="ignore"), tag["tag_name"].lower()])
        # add no tags
        tag_count = [
            {
                "tag_name": str(NO_TAG_NAME),
                "tag_id": NO_TAG_ID,
                "link_table_count": LinkTable.list_max_version_link_table()
                .exclude(uid__in=LinkTableTag.objects.values_list("link_table_uid").distinct())
                .count(),
            }
        ] + tag_count
        # response
        return tag_count


class RuleAuditSourceTypeCheck(StrategyV2Base):
    name = gettext_lazy("规则审计调度类型检查")
    RequestSerializer = RuleAuditSourceTypeCheckReqSerializer
    ResponseSerializer = RuleAuditSourceTypeCheckRespSerializer

    def perform_request(self, validated_request_data):
        namespace = validated_request_data["namespace"]
        config_type = validated_request_data["config_type"]
        rt_id = validated_request_data.get("rt_id")
        link_table_dict = validated_request_data.get("link_table")
        checker = RuleAuditSourceTypeChecker(namespace=namespace)
        if config_type == RuleAuditConfigType.LINK_TABLE.value:
            link_table: LinkTable = get_object_or_404(LinkTable, **link_table_dict)
            support_source_types = checker.link_table_support_source_types(link_table)
        else:
            support_source_types = checker.rt_support_source_types(rt_id)
        return {"support_source_types": support_source_types}


class StrategyRunningStatusList(StrategyV2Base):
    name = gettext_lazy("查询策略运行状态列表")
    RequestSerializer = StrategyRunningStatusListReqSerializer
    ResponseSerializer = StrategyRunningStatusListRespSerializer

    def perform_request(self, validated_request_data):
        strategy_id: int = validated_request_data["strategy_id"]
        start_time: datetime.datetime = validated_request_data["start_time"]
        end_time: datetime.datetime = validated_request_data["end_time"]
        limit = validated_request_data["limit"]
        offset = validated_request_data["offset"]
        strategy = get_object_or_404(Strategy, strategy_id=strategy_id)
        h = StrategyRunningStatusHandler.get_typed_handler(
            strategy=strategy,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
            offset=offset,
        )
        if not h:
            return {"strategy_running_status": []}
        strategy_running_status = h.get_strategy_running_status()
        return {"strategy_running_status": strategy_running_status}


# ============== 报告相关接口 ==============


class ReportBase(AuditMixinResource, abc.ABC):
    """报告相关接口基类"""

    tags = ["Report"]


class ListRiskVariables(ReportBase):
    """
    获取报告风险变量列表

    返回可用于报告模板的风险字段列表，前端使用时需加 `risk.` 前缀。
    """

    name = gettext_lazy("获取报告风险变量列表")
    ResponseSerializer = RiskVariableResponseSerializer
    many_response_data = True

    def perform_request(self, validated_request_data):
        from services.web.risk.report.serializers import ReportRiskVariableSerializer

        return ReportRiskVariableSerializer.get_field_definitions()


class ListAggregationFunctions(ReportBase):
    """
    获取聚合函数列表

    返回可用的聚合函数列表，包含每个函数适用的 BKBase 字段类型。
    """

    name = gettext_lazy("获取聚合函数列表")
    ResponseSerializer = AggregationFunctionResponseSerializer
    many_response_data = True

    def perform_request(self, validated_request_data):
        from services.web.risk.constants import AggregationFunction

        return [
            {
                "id": func.value,
                "name": str(func.label),
                "supported_field_types": AggregationFunction.get_supported_field_types(func.value),
            }
            for func in AggregationFunction
        ]


class RetrieveStrategy(StrategyV2Base):
    """
    获取策略详情

    返回策略全量配置（包含 report_config），用于策略编辑页面。
    复用 LIST_STRATEGY 权限。
    """

    name = gettext_lazy("获取策略详情")
    audit_action = ActionEnum.LIST_STRATEGY
    RequestSerializer = RetrieveStrategyRequestSerializer
    ResponseSerializer = StrategyDetailSerializer

    def perform_request(self, validated_request_data):
        strategy_id = validated_request_data["strategy_id"]
        strategy = get_object_or_404(Strategy, strategy_id=strategy_id)
        return strategy


class PreviewRiskReport(StrategyV2Base):
    """
    报告预览（异步）

    根据传入的 report_config，使用指定风险单数据进行渲染预览。
    用于策略配置页面预览模板效果。
    权限：通过 ViewSet 的 InstanceActionPermission 校验策略编辑权限。
    """

    name = gettext_lazy("报告预览")
    RequestSerializer = PreviewReportRequestSerializer
    ResponseSerializer = PreviewReportResponseSerializer

    def perform_request(self, validated_request_data):
        risk_id = validated_request_data["risk_id"]
        report_config_data = validated_request_data["report_config"]

        # 获取风险
        risk = get_object_or_404(Risk, risk_id=risk_id)

        # 解析报告配置（预览使用前端传入的配置）
        report_config = ReportConfig.model_validate(report_config_data)

        # 提交渲染任务（简化调用）
        async_result = submit_render_task(risk=risk, report_config=report_config)

        return {"task_id": async_result.id, "status": "PENDING"}

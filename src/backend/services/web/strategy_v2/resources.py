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
from functools import cached_property
from typing import List, Optional

from bk_resource import CacheResource, api, resource
from bk_resource.base import Empty
from bk_resource.exceptions import APIRequestError
from bk_resource.utils.cache import CacheTypeItem
from blueapps.utils.logger import logger
from blueapps.utils.request_provider import get_local_request, get_request_username
from django.conf import settings
from django.db import transaction
from django.db.models import Count, Q, QuerySet
from django.db.models.aggregates import Min
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext, gettext_lazy
from pypinyin import lazy_pinyin
from rest_framework.settings import api_settings

from apps.audit.resources import AuditMixinResource
from apps.feature.constants import FeatureTypeChoices
from apps.feature.handlers import FeatureHandler
from apps.meta.models import DataMap, Tag
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
from apps.permission.handlers.actions import ActionEnum
from apps.permission.handlers.drf import ActionPermission
from apps.permission.handlers.permission import Permission
from apps.permission.handlers.resource_types import ResourceEnum
from core.exceptions import PermissionException
from core.utils.page import paginate_queryset
from core.utils.tools import choices_to_dict
from services.web.analyze.constants import (
    BaseControlTypeChoices,
    FilterOperator,
    OffsetUnit,
)
from services.web.analyze.controls.base import BaseControl
from services.web.analyze.tasks import call_controller
from services.web.query.utils.search_config import QueryConditionOperator
from services.web.risk.constants import EventMappingFields
from services.web.risk.models import Risk
from services.web.risk.permissions import RiskViewPermission
from services.web.strategy_v2.constants import (
    BKBASE_INTERNAL_FIELD,
    HAS_UPDATE_TAG_ID,
    HAS_UPDATE_TAG_NAME,
    LOCAL_UPDATE_FIELDS,
    NO_TAG_ID,
    NO_TAG_NAME,
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
    StrategyOperator,
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
from services.web.strategy_v2.models import (
    LinkTable,
    LinkTableAuditInstance,
    LinkTableTag,
    Strategy,
    StrategyAuditInstance,
    StrategyTag,
)
from services.web.strategy_v2.serializers import (
    BulkGetRTFieldsRequestSerializer,
    BulkGetRTFieldsResponseSerializer,
    CreateLinkTableRequestSerializer,
    CreateLinkTableResponseSerializer,
    CreateStrategyRequestSerializer,
    CreateStrategyResponseSerializer,
    GetEventInfoFieldsRequestSerializer,
    GetEventInfoFieldsResponseSerializer,
    GetLinkTableRequestSerializer,
    GetLinkTableResponseSerializer,
    GetRTFieldsRequestSerializer,
    GetRTFieldsResponseSerializer,
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
    RetryStrategyRequestSerializer,
    RuleAuditSourceTypeCheckReqSerializer,
    RuleAuditSourceTypeCheckRespSerializer,
    StrategyInfoSerializer,
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


class CreateStrategy(StrategyV2Base):
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
            if strategy_type == StrategyType.RULE:
                strategy.sql = self.build_rule_audit_sql(strategy)
                strategy.save(update_fields=["sql"])
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
        if need_update_remote or strategy.status != StrategyStatusChoices.RUNNING:
            self.update_remote(strategy)
        # audit
        setattr(strategy, "instance_origin_data", instance_origin_data)
        self.add_audit_instance_to_context(instance=StrategyAuditInstance(strategy))
        # response
        return strategy

    @transaction.atomic()
    def update_db(self, strategy: Strategy, validated_request_data: dict) -> bool:
        # 用于控制是否更新真实的监控策略或计算平台Flow
        need_update_remote = False
        # pop tag
        tag_names = validated_request_data.pop("tags", [])
        # check control
        if (
            validated_request_data["strategy_type"] == StrategyType.MODEL
            and strategy.control_id != validated_request_data["control_id"]
        ):
            raise ControlChangeError()
        # check risk_level
        if strategy.risk_level is not None:
            validated_request_data.pop("risk_level")
        # save strategy
        for key, val in validated_request_data.items():
            inst_val = getattr(strategy, key, Empty())
            # 不同且不在本地更新清单中的字段才触发远程更新
            if inst_val != val and key not in LOCAL_UPDATE_FIELDS:
                need_update_remote = True
            setattr(strategy, key, val)
        strategy.save(update_fields=validated_request_data.keys())
        # save strategy tag
        self._save_tags(strategy_id=strategy.strategy_id, tag_names=tag_names)
        # update rule audit sql
        if strategy.strategy_type == StrategyType.RULE:
            strategy.sql = self.build_rule_audit_sql(strategy)
            strategy.save(update_fields=["sql"])
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


class ListStrategy(StrategyV2Base):
    name = gettext_lazy("List Strategy")
    RequestSerializer = ListStrategyRequestSerializer
    ResponseSerializer = ListStrategyResponseSerializer
    many_response_data = True
    audit_action = ActionEnum.LIST_STRATEGY

    def perform_request(self, validated_request_data):
        # init queryset
        order_field = validated_request_data.get("order_field") or "-strategy_id"
        queryset = Strategy.objects.filter(namespace=validated_request_data["namespace"]).order_by(order_field)
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
                    q |= Q(**{f"{key}__contains": item})
                queryset = queryset.filter(q)
        # add tags
        all_tags = StrategyTag.objects.filter(strategy_id__in=queryset.values("strategy_id"))
        tag_map = defaultdict(list)
        for t in all_tags:
            tag_map[t.strategy_id].append(t.tag_id)
        for item in queryset:
            setattr(item, "tags", tag_map.get(item.strategy_id, []))
        # response
        return queryset


class ListStrategyAll(StrategyV2Base):
    name = gettext_lazy("List All Strategy")

    def perform_request(self, validated_request_data):
        if not ActionPermission(
            actions=[ActionEnum.LIST_STRATEGY, ActionEnum.LIST_RISK, ActionEnum.EDIT_RISK]
        ).has_permission(request=get_local_request(), view=self):
            return []
        strategies: List[Strategy] = Strategy.objects.all()
        data = [{"label": s.strategy_name, "value": s.strategy_id} for s in strategies]
        data.sort(key=lambda s: s["label"])
        return data


class ToggleStrategy(StrategyV2Base):
    name = gettext_lazy("Toggle Strategy")
    RequestSerializer = ToggleStrategyRequestSerializer
    audit_action = ActionEnum.EDIT_STRATEGY

    def perform_request(self, validated_request_data):
        strategy = get_object_or_404(Strategy, strategy_id=validated_request_data["strategy_id"])
        self.add_audit_instance_to_context(instance=StrategyAuditInstance(strategy))
        controller_cls = self.get_base_control_type(strategy.strategy_type)
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
        return [
            {
                "label": "{}({})".format(field["field_alias"] or field["field_name"], field["field_name"]),
                "value": field["field_name"],
                "field_type": field["field_type"],
            }
            for field in fields
            if field["field_name"] not in BKBASE_INTERNAL_FIELD
        ]


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
                description="",
                example=getattr(risk, field.field_name, "") if risk and has_permission else "",
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
        field_dict = {}

        # 1. 从策略配置中获取字段
        for field in strategy.event_data_field_configs:
            field_dict[field["field_name"]] = {
                "display_name": field.get("display_name", field["field_name"]),
                "example": "",
                "description": "",
            }

        # 2. 从风险数据中获取字段
        if risk:
            risk_data = risk.event_data or {}
            for key, value in risk_data.items():
                if key not in field_dict:
                    field_dict[key] = {"display_name": key, "example": "", "description": ""}
                if has_permission:
                    field_dict[key]["example"] = value

        # 转换为EventInfoField列表
        return [
            EventInfoField(
                field_name=key,
                display_name=info["display_name"],
                description=info["description"],
                example=info["example"],
            )
            for key, info in field_dict.items()
        ]

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
        field_dict = {}

        # 1. 从策略配置中获取字段
        for field in strategy.event_evidence_field_configs or []:
            field_dict[field["field_name"]] = {
                "display_name": field.get("display_name", field["field_name"]),
                "example": "",
                "description": field.get("description", ""),
            }

        # 2. 从风险数据中获取字段
        if risk:
            try:
                event_evidence = json.loads(risk.event_evidence)[0] if risk.event_evidence else {}
            except (json.JSONDecodeError, IndexError, KeyError):
                event_evidence = {}

            for key, value in event_evidence.items():
                if key not in field_dict:
                    field_dict[key] = {"display_name": key, "example": "", "description": ""}
                if has_permission:
                    field_dict[key]["example"] = value

        # 转换为EventInfoField列表
        return [
            EventInfoField(
                field_name=key,
                display_name=info["display_name"],
                description=info["description"],
                example=info["example"],
            )
            for key, info in field_dict.items()
        ]

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
    ResponseSerializer = ListLinkTableResponseSerializer
    audit_action = ActionEnum.LIST_LINK_TABLE
    many_response_data = True
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
        return link_tables


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

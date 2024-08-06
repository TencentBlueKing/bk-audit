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
from typing import List, Optional

from bk_resource import api, resource
from bk_resource.base import Empty
from bk_resource.exceptions import APIRequestError
from blueapps.utils.request_provider import get_local_request, get_request_username
from django.conf import settings
from django.db import transaction
from django.db.models import Count, Q, QuerySet
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext, gettext_lazy
from pypinyin import lazy_pinyin
from rest_framework.settings import api_settings

from apps.audit.resources import AuditMixinResource
from apps.meta.models import DataMap, Tag
from apps.meta.utils.fields import (
    DIMENSION_FIELD_TYPES,
    EXTEND_DATA,
    FILED_DISPLAY_NAME_ALIAS_KEY,
    PYTHON_TO_ES,
    SNAPSHOT_USER_INFO,
    SNAPSHOT_USER_INFO_HIDE_FIELDS,
    STRATEGY_DISPLAY_FIELDS,
)
from apps.permission.handlers.actions import ActionEnum
from apps.permission.handlers.drf import ActionPermission
from apps.permission.handlers.permission import Permission
from apps.permission.handlers.resource_types import ResourceEnum
from core.exceptions import PermissionException
from core.utils.tools import choices_to_dict
from services.web.analyze.constants import (
    ControlTypeChoices,
    FilterOperator,
    OffsetUnit,
)
from services.web.analyze.controls.base import Controller
from services.web.analyze.exceptions import ControlNotExist
from services.web.analyze.models import Control
from services.web.analyze.tasks import call_controller
from services.web.risk.constants import EVENT_BASIC_EXCLUDE_FIELDS, EventMappingFields
from services.web.risk.models import Risk
from services.web.risk.permissions import RiskViewPermission
from services.web.strategy_v2.constants import (
    HAS_UPDATE_TAG_ID,
    HAS_UPDATE_TAG_NAME,
    LOCAL_UPDATE_FIELDS,
    EventInfoField,
    MappingType,
    RiskLevel,
    StrategyAlgorithmOperator,
    StrategyOperator,
    StrategyStatusChoices,
    TableType,
)
from services.web.strategy_v2.exceptions import ControlChangeError, StrategyPendingError
from services.web.strategy_v2.models import Strategy, StrategyAuditInstance, StrategyTag
from services.web.strategy_v2.serializers import (
    AIOPSConfigSerializer,
    BKMStrategySerializer,
    CreateStrategyRequestSerializer,
    CreateStrategyResponseSerializer,
    GetEventInfoFieldsRequestSerializer,
    GetEventInfoFieldsResponseSerializer,
    GetRTFieldsRequestSerializer,
    GetRTFieldsResponseSerializer,
    GetStrategyCommonResponseSerializer,
    GetStrategyDisplayInfoRequestSerializer,
    GetStrategyFieldValueRequestSerializer,
    GetStrategyFieldValueResponseSerializer,
    GetStrategyStatusRequestSerializer,
    ListStrategyFieldsRequestSerializer,
    ListStrategyFieldsResponseSerializer,
    ListStrategyRequestSerializer,
    ListStrategyResponseSerializer,
    ListStrategyTagsResponseSerializer,
    ListTablesRequestSerializer,
    RetryStrategyRequestSerializer,
    StrategyInfoSerializer,
    ToggleStrategyRequestSerializer,
    UpdateStrategyRequestSerializer,
    UpdateStrategyResponseSerializer,
)
from services.web.strategy_v2.utils.field_value import FieldValueHandler
from services.web.strategy_v2.utils.table import TableHandler


class StrategyV2Base(AuditMixinResource, abc.ABC):
    tags = ["StrategyV2"]
    audit_resource_type = ResourceEnum.STRATEGY

    def _save_tags(self, strategy_id: int, tag_names: list) -> None:
        StrategyTag.objects.filter(strategy_id=strategy_id).delete()
        if not tag_names:
            return
        tags = resource.meta.save_tags([{"tag_name": t} for t in tag_names])
        StrategyTag.objects.bulk_create([StrategyTag(strategy_id=strategy_id, tag_id=t["tag_id"]) for t in tags])

    def _validate_configs(self, validated_request_data: dict) -> None:
        control_type_id = Control.objects.get(control_id=validated_request_data["control_id"]).control_type_id
        if control_type_id == ControlTypeChoices.BKM.value:
            configs_serializer_class = BKMStrategySerializer
        elif control_type_id == ControlTypeChoices.AIOPS.value:
            configs_serializer_class = AIOPSConfigSerializer
        else:
            raise ControlNotExist()
        configs_serializer = configs_serializer_class(data=validated_request_data["configs"])
        configs_serializer.is_valid(raise_exception=True)
        validated_request_data["configs"] = configs_serializer.validated_data


class CreateStrategy(StrategyV2Base):
    name = gettext_lazy("Create Strategy")
    RequestSerializer = CreateStrategyRequestSerializer
    ResponseSerializer = CreateStrategyResponseSerializer
    audit_action = ActionEnum.CREATE_STRATEGY

    def perform_request(self, validated_request_data):
        with transaction.atomic():
            # pop tag
            tag_names = validated_request_data.pop("tags", [])
            # check configs
            self._validate_configs(validated_request_data)
            # save strategy
            strategy: Strategy = Strategy.objects.create(**validated_request_data)
            # save strategy tag
            self._save_tags(strategy_id=strategy.strategy_id, tag_names=tag_names)
        # create
        try:
            call_controller(Controller.create.__name__, strategy.strategy_id)
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
        # load strategy
        strategy: Strategy = get_object_or_404(Strategy, strategy_id=validated_request_data.pop("strategy_id", int()))
        # check strategy status
        if strategy.status in [
            StrategyStatusChoices.STARTING,
            StrategyStatusChoices.UPDATING,
            StrategyStatusChoices.STOPPING,
        ]:
            raise StrategyPendingError()
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
        # check configs
        self._validate_configs(validated_request_data)
        # check control
        if strategy.control_id != validated_request_data["control_id"]:
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
        # return
        return need_update_remote

    def update_remote(self, strategy: Strategy) -> None:
        strategy.status = StrategyStatusChoices.UPDATING
        strategy.save(update_fields=["status"])
        try:
            call_controller(Controller.update.__name__, strategy.strategy_id)
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
            call_controller(Controller.delete.__name__, validated_request_data["strategy_id"])
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
        # tag filter
        if validated_request_data.get("tag"):
            # tag 筛选
            strategy_ids = StrategyTag.objects.filter(tag_id__in=validated_request_data["tag"]).values("strategy_id")
            queryset = queryset.filter(strategy_id__in=strategy_ids)
        # exact filter
        for key in ["strategy_id", "status"]:
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
        if validated_request_data["toggle"]:
            call_controller(Controller.enable.__name__, strategy.strategy_id)
            return
        call_controller(Controller.disabled.__name__, strategy.strategy_id)


class RetryStrategy(StrategyV2Base):
    name = gettext_lazy("Retry Strategy")
    RequestSerializer = RetryStrategyRequestSerializer

    def perform_request(self, validated_request_data):
        # load strategy
        strategy = get_object_or_404(Strategy, strategy_id=validated_request_data["strategy_id"])
        # try update
        try:
            if strategy.backend_data and (strategy.backend_data.get("id") or strategy.backend_data.get("flow_id")):
                call_controller(Controller.update.__name__, strategy.strategy_id)
            else:
                call_controller(Controller.create.__name__, strategy.strategy_id)
        except Exception as err:
            strategy.status = StrategyStatusChoices.FAILED
            strategy.status_msg = str(err)
            strategy.save(update_fields=["status", "status_msg"])
            raise err


class ListHasUpdateStrategy(StrategyV2Base):
    name = gettext_lazy("List Has Update Strategy")

    def perform_request(self, validated_request_data):
        # load last control versions
        all_controls = resource.analyze.control()
        controls = {}
        # 获取每个版本的最新版本
        for cv in all_controls:
            if cv["control_id"] not in controls.keys():
                controls[cv["control_id"]] = cv["versions"][0]["control_version"]
        # 获取所有策略
        all_strategies = Strategy.objects.all()
        # 判断需要更新的数量
        has_update = []
        for s in all_strategies:
            if controls.get(s.control_id, s.control_version) > s.control_version:
                has_update.append(s)
        return has_update


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

    def load_action_fields(self, namespace: str, system_id: str, action_id: str) -> List[dict]:
        data = []
        end_time = datetime.datetime.now()
        start_time = end_time - datetime.timedelta(days=7)
        logs = resource.esquery.search_all(
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
            "table_type": [
                {"value": value, "label": str(label), "config": TableType.get_config(value)}
                for value, label in TableType.choices
            ],
            "strategy_status": choices_to_dict(StrategyStatusChoices, val="value", name="label"),
            "offset_unit": choices_to_dict(OffsetUnit, val="value", name="label"),
            "mapping_type": choices_to_dict(MappingType, val="value", name="label"),
            "risk_level": choices_to_dict(RiskLevel, val="value", name="label"),
        }


class ListTables(StrategyV2Base):
    name = gettext_lazy("List Tables")
    RequestSerializer = ListTablesRequestSerializer

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
        return TableHandler(**validated_request_data).list_tables()


class GetRTFields(StrategyV2Base):
    name = gettext_lazy("Get RT Fields")
    RequestSerializer = GetRTFieldsRequestSerializer
    ResponseSerializer = GetRTFieldsResponseSerializer
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
        fields = api.bk_base.get_rt_fields(result_table_id=validated_request_data["table_id"])
        return [
            {
                "label": "{}({})".format(field["field_alias"] or field["field_name"], field["field_name"]),
                "value": field["field_name"],
                "field_type": field["field_type"],
            }
            for field in fields
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
                display_name=field.alias_name,
                description=str(field.description),
                example=getattr(risk, field.field_name, "") if risk and has_permission else "",
            )
            for field in EventMappingFields().fields
            if field not in EVENT_BASIC_EXCLUDE_FIELDS
        ]

    def get_event_data_field_configs(self, risk: Optional[Risk], has_permission: bool) -> List[EventInfoField]:
        """
        事件数据字段
        """

        if not risk:
            return []
        return [
            EventInfoField(field_name=key, display_name=key, description="", example=value if has_permission else "")
            for key, value in (risk.event_data or {}).items()
        ]

    def get_event_evidence_field_configs(self, risk: Optional[Risk], has_permission: bool) -> List[EventInfoField]:
        """
        事件证据字段
        """

        if not risk:
            return []
        try:
            event_evidence = json.loads(risk.event_evidence)[0]
        except (json.JSONDecodeError, IndexError, KeyError):
            event_evidence = {}
        return [
            EventInfoField(field_name=key, display_name=key, description="", example=value if has_permission else "")
            for key, value in event_evidence.items()
        ]

    def perform_request(self, validated_request_data):
        # 风险不存在: 基础字段
        # 风险存在: 基础字段 + 事件数据字段 + 事件证据字段
        # 有权限: 字段样例为风险值
        # 无权限: 字段样例为空
        strategy_id = validated_request_data.get("strategy_id")
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
            "event_data_field_configs": self.get_event_data_field_configs(risk, has_permission),
            "event_evidence_field_configs": self.get_event_evidence_field_configs(risk, has_permission),
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
        return {
            strategy.strategy_id: {
                "risk_level": strategy.risk_level,
            }
            for strategy in strategies
        }

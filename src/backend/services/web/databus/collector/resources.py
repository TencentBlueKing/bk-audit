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
import math
from collections import defaultdict
from typing import List

import arrow
import requests
from bk_resource import api, resource
from bk_resource.contrib.model import ModelResource
from bk_resource.settings import bk_resource_settings
from bk_resource.utils.common_utils import uniqid
from blueapps.utils.logger import logger
from django.conf import settings
from django.db.transaction import atomic
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.translation import gettext, gettext_lazy
from rest_framework.settings import api_settings

from apps.audit.resources import AuditMixinResource
from apps.bk_crypto.crypto import asymmetric_cipher
from apps.exceptions import (
    JoinDataPreCheckFailed,
    MetaConfigNotExistException,
    ParamsNotValid,
    SnapshotPreparingException,
)
from apps.feature.constants import FeatureTypeChoices
from apps.feature.handlers import FeatureHandler
from apps.meta.constants import ConfigLevelChoices
from apps.meta.models import GlobalMetaConfig, ResourceType, System
from apps.meta.utils.saas import get_saas_url
from core.cache import CacheType
from core.utils.data import replenish_params
from core.utils.time import format_date_string
from services.web.databus.collector.bcs.yaml import YamlTemplate
from services.web.databus.collector.etl.base import EtlClean
from services.web.databus.collector.serializers import (
    ApplyDataIdSourceRequestSerializer,
    BulkSystemCollectorsStatusRequestSerializer,
    BulkSystemCollectorsStatusResponseSerializer,
    BulkSystemSnapshotsStatusRequestSerializer,
    CollectorCreateRequestSerializer,
    CollectorCreateResponseSerializer,
    CollectorStatusRequestSerializer,
    CollectorStatusResponseSerializer,
    CreateApiPushRequestSerializer,
    CreateBcsCollectorRequestSerializer,
    CreateCollectorEtlRequestSerializer,
    DataIdEtlPreviewRequestSerializer,
    DataIdEtlStorageRequestSerializer,
    DeleteDataIdRequestSerializer,
    EtlPreviewRequestSerializer,
    GetApiPushRequestSerializer,
    GetBcsYamlTemplateRequestSerializer,
    GetBcsYamlTemplateResponseSerializer,
    GetCollectorInfoResponseSerializer,
    GetCollectorsRequestSerializer,
    GetCollectorsResponseSerializer,
    GetDataIdDetailRequestSerializer,
    GetDataIdDetailResponseSerializer,
    GetDataIdListRequestSerializer,
    GetDataIdListResponseSerializer,
    GetDataIdTailRequestSerializer,
    GetDataIdTailResponseSerializer,
    GetSystemDataIdListRequestSerializer,
    GetSystemDataIdListResponseSerializer,
    SnapshotCheckStatisticSerializer,
    SnapshotStatusRequestSerializer,
    ToggleJoinDataRequestSerializer,
    ToggleJoinDataResponseSerializer,
    UpdateBcsCollectorRequestSerializer,
    UpdateCollectorRequestSerializer,
)
from services.web.databus.collector.snapshot.join.base import (
    AssetHandler,
    BasicJoinHandler,
)
from services.web.databus.collector.snapshot.join.http_pull import HttpPullHandler
from services.web.databus.constants import (
    API_PUSH_COLLECTOR_NAME_FORMAT,
    BKBASE_API_MAX_PAGESIZE,
    COLLECTOR_NAME_MAX_LENGTH,
    COLLECTOR_PLUGIN_ID,
    DEFAULT_CATEGORY_ID,
    DEFAULT_COLLECTOR_SCENARIO,
    DEFAULT_LAST_TIME_TIMESTAMP,
    PULL_HANDLER_PRE_CHECK_TIMEOUT,
    CustomTypeEnum,
    EnvironmentChoice,
    EtlConfigEnum,
    EtlProcessorChoice,
    JoinDataPullType,
    JoinDataType,
    LogReportStatus,
    SnapshotReportStatus,
    SnapshotRunningStatus,
    SourcePlatformChoices,
)
from services.web.databus.models import (
    CollectorConfig,
    Snapshot,
    SnapshotCheckStatistic,
    SnapshotStorage,
)
from services.web.databus.tasks import create_api_push_etl
from services.web.databus.utils import stop_bkbase_clean


class CollectorMeta(AuditMixinResource, abc.ABC):
    tags = ["Collector"]


class SnapshotStatusResource(CollectorMeta):
    """资源快照状态"""

    name = gettext_lazy("资源快照状态")
    RequestSerializer = SnapshotStatusRequestSerializer

    def perform_request(self, validated_request_data: dict) -> dict:
        resource_type_ids = validated_request_data["resource_type_ids"]
        snapshot = {
            item.resource_type_id: item
            for item in Snapshot.objects.filter(system_id=validated_request_data["system_id"])
        }
        result_dict = defaultdict(dict)
        for resource_type_id in resource_type_ids:
            result = result_dict[resource_type_id]
            # 注入接入系统ID，辅助鉴权字段输出
            result["system_id"] = validated_request_data["system_id"]
            # 是否已经集成快照数据
            item: Snapshot = snapshot.get(resource_type_id)
            if not item:
                result.update(
                    {
                        "status": SnapshotRunningStatus.CLOSED.value,
                        "bkbase_url": None,
                        "pull_type": JoinDataPullType.PARTIAL,
                        "status_msg": "",
                    }
                )
                continue
            result.update(
                {
                    "status": item.status,
                    "bkbase_url": (
                        get_saas_url(settings.BKBASE_APP_CODE)
                        + str(settings.BK_BASE_ACCESS_URL).rstrip("/")
                        + "/"
                        + str(item.bkbase_data_id)
                    )
                    if item.bkbase_data_id and (item.status == SnapshotRunningStatus.RUNNING)
                    else None,
                    "pull_type": item.pull_type,
                    "status_msg": item.status_msg,
                }
            )
        return result_dict


class GetCollectorsResource(CollectorMeta, ModelResource):
    name = gettext_lazy("获取采集列表")
    model = CollectorConfig
    action = "list"
    filter_fields = ["system_id"]
    RequestSerializer = GetCollectorsRequestSerializer
    serializer_class = GetCollectorsResponseSerializer
    many_response_data = True
    view_set_attrs = {"queryset": CollectorConfig.objects.filter(custom_type=CustomTypeEnum.LOG.value)}


class GetCollectorResource(CollectorMeta, ModelResource):
    name = gettext_lazy("获取采集项元数据")
    model = CollectorConfig
    action = "retrieve"
    lookup_field = "collector_config_id"
    serializer_class = GetCollectorsResponseSerializer
    view_set_attrs = {"queryset": CollectorConfig.objects.filter(source_platform=SourcePlatformChoices.BKLOG)}


class GetCollectorInfoResource(CollectorMeta, ModelResource):
    name = gettext_lazy("采集详情")
    model = CollectorConfig
    action = "retrieve"
    lookup_field = "collector_config_id"
    serializer_class = GetCollectorInfoResponseSerializer
    view_set_attrs = {"queryset": CollectorConfig.objects.filter(source_platform=SourcePlatformChoices.BKLOG)}

    def perform_request(self, validated_request_data: dict) -> any:
        data = super().perform_request(validated_request_data)
        bk_log_data = api.bk_log.get_collector(collector_config_id=validated_request_data["collector_config_id"])
        data = replenish_params(data, bk_log_data)
        data["updated_at"] = format_date_string(data.get("updated_at"))
        data["created_at"] = format_date_string(data.get("created_at"))
        return data


class CreateCollectorResource(CollectorMeta):
    name = gettext_lazy("新建采集")
    RequestSerializer = CollectorCreateRequestSerializer
    serializer_class = CollectorCreateResponseSerializer

    def get_collector_plugin_id(self, validated_request_data):
        try:
            return GlobalMetaConfig.get(
                COLLECTOR_PLUGIN_ID,
                config_level=ConfigLevelChoices.SYSTEM.value,
                instance_key=validated_request_data["system_id"],
            )
        except MetaConfigNotExistException:
            return GlobalMetaConfig.get(
                COLLECTOR_PLUGIN_ID,
                config_level=ConfigLevelChoices.NAMESPACE.value,
                instance_key=validated_request_data["namespace"],
            )

    def create_db_collector(self, collector_plugin_id, validated_request_data, resp):
        return CollectorConfig.objects.create(
            system_id=validated_request_data["system_id"],
            bk_biz_id=validated_request_data["bk_biz_id"],
            collector_plugin_id=collector_plugin_id,
            collector_config_id=resp["collector_config_id"],
            collector_config_name=validated_request_data["collector_config_name"],
            collector_config_name_en=validated_request_data["collector_config_name_en"],
            bk_data_id=resp["bk_data_id"],
            description=validated_request_data["collector_config_name"],
            record_log_type=validated_request_data["record_log_type"],
            select_sdk_type=validated_request_data["select_sdk_type"],
        )

    def perform_request(self, validated_request_data):
        collector_plugin_id = self.get_collector_plugin_id(validated_request_data)
        validated_request_data.update(
            {
                "collector_plugin_id": collector_plugin_id,
                "etl_processor": EtlProcessorChoice.BKBASE.value,
                "platform_username": bk_resource_settings.PLATFORM_AUTH_ACCESS_USERNAME,
            }
        )
        resp = api.bk_log.create_collector(validated_request_data)
        collector_config = self.create_db_collector(collector_plugin_id, validated_request_data, resp)
        data = self.serializer_class(collector_config).data
        data.update({"task_id_list": resp.get("task_id_list", [])})
        return data


class UpdateCollectorResource(CollectorMeta):
    name = gettext_lazy("更新采集")
    RequestSerializer = UpdateCollectorRequestSerializer
    serializer_class = CollectorCreateResponseSerializer

    def perform_request(self, validated_request_data):
        validated_request_data.update({"platform_username": bk_resource_settings.PLATFORM_AUTH_ACCESS_USERNAME})
        resp = api.bk_log.update_collector(**validated_request_data)
        collector_config = CollectorConfig.objects.get(
            collector_config_id=validated_request_data["collector_config_id"]
        )
        collector_config.collector_config_name = resp["collector_config_name"]
        collector_config.description = validated_request_data["collector_config_name"]
        update_fields = ["collector_config_name", "description"]
        if validated_request_data.get("record_log_type"):
            collector_config.record_log_type = validated_request_data["record_log_type"]
            update_fields.append("record_log_type")
        if validated_request_data.get("select_sdk_type"):
            collector_config.select_sdk_type = validated_request_data["select_sdk_type"]
            update_fields.append("select_sdk_type")
        collector_config.save(update_fields=update_fields)
        data = self.serializer_class(collector_config).data
        data.update({"task_id_list": resp.get("task_id_list", [])})
        return data


class GetBcsYamlTemplateResource(CollectorMeta):
    name = gettext_lazy("获取BCS Yaml模板")
    RequestSerializer = GetBcsYamlTemplateRequestSerializer
    serializer_class = GetBcsYamlTemplateResponseSerializer

    def perform_request(self, validated_request_data):
        return {"yaml_config": YamlTemplate.get(validated_request_data["log_config_type"])}


class CreateBcsCollectorResource(CreateCollectorResource):
    name = gettext_lazy("创建BCS采集")
    RequestSerializer = CreateBcsCollectorRequestSerializer

    def perform_request(self, validated_request_data):
        collector_plugin_id = self.get_collector_plugin_id(validated_request_data)
        validated_request_data.update(
            {
                "bkdata_biz_id": settings.DEFAULT_BK_BIZ_ID,
                "collector_plugin_id": collector_plugin_id,
                "collector_scenario_id": DEFAULT_COLLECTOR_SCENARIO,
                "category_id": DEFAULT_CATEGORY_ID,
                "configs": [],
                "yaml_config_enabled": True,
                "description": validated_request_data["collector_config_name"],
                "environment": EnvironmentChoice.CONTAINER.value,
                "add_pod_label": False,
                "extra_labels": [],
                "platform_username": bk_resource_settings.PLATFORM_AUTH_ACCESS_USERNAME,
            }
        )
        resp = api.bk_log.create_collector_normal(validated_request_data)
        collector_config = self.create_db_collector(collector_plugin_id, validated_request_data, resp)
        return self.serializer_class(collector_config).data


class UpdateBcsCollectorResource(CollectorMeta):
    name = gettext_lazy("更新BCS采集")
    RequestSerializer = UpdateBcsCollectorRequestSerializer
    serializer_class = CollectorCreateResponseSerializer

    def perform_request(self, validated_request_data):
        collector_config = CollectorConfig.objects.get(
            collector_config_id=validated_request_data["collector_config_id"]
        )
        validated_request_data.update(
            {
                "collector_scenario_id": DEFAULT_COLLECTOR_SCENARIO,
                "category_id": DEFAULT_CATEGORY_ID,
                "configs": [],
                "yaml_config_enabled": True,
                "description": validated_request_data["collector_config_name"],
                "environment": "container",
                "add_pod_label": False,
                "extra_labels": [],
            }
        )
        api.bk_log.update_collector_normal(validated_request_data)
        collector_config.collector_config_name = validated_request_data["collector_config_name"]
        collector_config.description = validated_request_data["collector_config_name"]
        update_fields = ["collector_config_name", "description"]
        if validated_request_data.get("record_log_type"):
            collector_config.record_log_type = validated_request_data["record_log_type"]
            update_fields.append("record_log_type")
        if validated_request_data.get("select_sdk_type"):
            collector_config.select_sdk_type = validated_request_data["select_sdk_type"]
            update_fields.append("select_sdk_type")
        collector_config.save(update_fields=update_fields)
        collector_config.save(update_fields=update_fields)
        return self.serializer_class(collector_config).data


class DeleteCollectorResource(CollectorMeta, ModelResource):
    name = gettext_lazy("删除采集")
    model = CollectorConfig
    action = "destroy"
    lookup_field = "collector_config_id"

    def perform_request(self, validated_request_data: dict) -> any:
        collector = get_object_or_404(
            CollectorConfig,
            collector_config_id=validated_request_data["collector_config_id"],
            source_platform=SourcePlatformChoices.BKLOG.value,
        )
        # 停止采集
        api.bk_log.stop_subscription(collector_config_id=collector.collector_config_id)
        # 停止清洗入库
        if collector.processing_id:
            stop_bkbase_clean(collector.bkbase_table_id, collector.processing_id)
        # 数据库软删除
        super().perform_request(validated_request_data)


class SystemCollectorsStatusResource(CollectorMeta):
    name = gettext_lazy("应用的采集数据上报状态")
    RequestSerializer = CollectorStatusRequestSerializer
    serializer_class = CollectorStatusResponseSerializer
    cache_type = CacheType.COLLECTOR

    def perform_request(self, validated_request_data):
        data = {"system_id": validated_request_data["system_id"]}
        # 获取系统下的采集信息
        collectors = CollectorConfig.objects.filter(system_id=validated_request_data["system_id"], is_deleted=False)
        # 未配置采集直接返回
        collector_count = collectors.count()
        if not collector_count:
            data.update(
                {
                    "status": LogReportStatus.UNSET.value,
                    "status_msg": str(LogReportStatus.UNSET.label),
                    "last_time": str(),
                    "collector_count": 0,
                }
            )
            return data
        # 判断采集数据状态
        data.update(
            {
                "status": LogReportStatus.NODATA.value,
                "status_msg": str(LogReportStatus.NODATA.label),
                "last_time": DEFAULT_LAST_TIME_TIMESTAMP,
            }
        )
        # 遍历采集项获取数据
        last_log_time = datetime.datetime.fromtimestamp(DEFAULT_LAST_TIME_TIMESTAMP).replace(tzinfo=None)
        for collector in collectors:
            # 如果比当前更新则更新为日志时间
            if collector.tail_log_time and collector.tail_log_time.replace(tzinfo=None) > last_log_time:
                data.update(
                    {
                        "last_time": collector.tail_log_time,
                        "status": LogReportStatus.NORMAL.value,
                        "status_msg": str(LogReportStatus.NORMAL.label),
                    }
                )
                last_log_time = collector.tail_log_time.replace(tzinfo=None)
        data["last_time"] = (
            data["last_time"].astimezone(timezone.get_default_timezone()).strftime(api_settings.DATETIME_FORMAT)
            if data["last_time"]
            else str()
        )
        data["collector_count"] = collector_count
        return data


class BulkSystemCollectorsStatusResource(CollectorMeta):
    name = gettext_lazy("批量获取应用采集状态")
    RequestSerializer = BulkSystemCollectorsStatusRequestSerializer
    serializer_class = BulkSystemCollectorsStatusResponseSerializer

    def perform_request(self, validated_request_data):
        result = {}
        for system_id in validated_request_data["system_ids"]:
            result[system_id] = resource.databus.collector.system_collectors_status(
                namespace=validated_request_data["namespace"], system_id=system_id
            )
        return result


class BulkSystemSnapshotsStatusResource(CollectorMeta):
    name = gettext_lazy("批量获取系统快照状态")
    RequestSerializer = BulkSystemSnapshotsStatusRequestSerializer
    cache_type = CacheType.SNAPSHOT

    def perform_request(self, validated_request_data):
        """
        获取系统快照状态
        1. 没有快照 -> 未配置
        2. 有快照&快照状态都不为失败 -> 正常
        3. 有快照&快照状态有失败 -> 异常
        """
        system_ids: List[str] = validated_request_data["system_ids"]
        sts = Snapshot.objects.filter(system_id__in=system_ids).values("system_id", "status")
        st_status_dict = defaultdict(list)
        for status in sts:
            st_status_dict[status["system_id"]].append(status["status"])
        result = {}
        for system_id in system_ids:
            st_status = st_status_dict.get(system_id, [])
            if len(st_status) == 0:
                status = SnapshotReportStatus.UNSET.value
            elif any([status == SnapshotRunningStatus.FAILED.value for status in st_status]):
                status = SnapshotReportStatus.ABNORMAL.value
            else:
                status = SnapshotReportStatus.NORMAL.value
            result[system_id] = {
                "status": status,
            }
        return result


class CollectorEtlResource(CollectorMeta, ModelResource):
    name = gettext_lazy("采集项清洗规则")
    lookup_field = "collector_config_id"
    action = "retrieve"
    model = CollectorConfig
    RequestSerializer = CreateCollectorEtlRequestSerializer

    def perform_request(self, validated_request_data):
        # 创建更新清洗规则
        collector_config_id = validated_request_data["collector_config_id"]
        etl_storage: EtlClean = EtlClean.get_instance(validated_request_data["etl_config"])
        etl_storage.update_or_create(
            collector_config_id=collector_config_id,
            etl_params=validated_request_data["etl_params"],
            fields=validated_request_data["fields"],
            namespace=validated_request_data["namespace"],
        )


class EtlPreviewResource(CollectorMeta):
    name = gettext_lazy("清洗预览")
    RequestSerializer = EtlPreviewRequestSerializer

    def perform_request(self, validated_request_data):
        etl_storage: EtlClean = EtlClean.get_instance(validated_request_data["etl_config"])
        return etl_storage.etl_preview(validated_request_data["data"], validated_request_data.get("etl_params"))


class ToggleJoinDataResource(CollectorMeta):
    name = gettext_lazy("切换数据关联状态")
    RequestSerializer = ToggleJoinDataRequestSerializer
    ResponseSerializer = ToggleJoinDataResponseSerializer

    def pre_check(self, system_id, resource_type_id, join_data_type):
        body = {
            "type": resource_type_id,
            "method": "fetch_instance_list",
            "filter": {"start_time": 0, "end_time": int(datetime.datetime.now().timestamp()) * 1000},
            "page": {"offset": 0, "limit": 1},
        }
        system = System.objects.get(system_id=system_id)
        resource_type = ResourceType.objects.get(system_id=system_id, resource_type_id=resource_type_id)
        pull_handler = HttpPullHandler(system, resource_type, Snapshot(), join_data_type)
        # 触发url校验
        _ = pull_handler.url
        web = requests.session()
        try:
            resp = web.post(
                pull_handler.url,
                json=body,
                headers={"Authorization": pull_handler.authorization},
                timeout=PULL_HANDLER_PRE_CHECK_TIMEOUT,
            )
            content = resp.json()
            status = resp.status_code
            result = content.get("result", True)
        except Exception as err:
            logger.exception("[JoinDataPreCheckFailed] Body => %s, Err => %s", body, err)
            raise JoinDataPreCheckFailed()
        if status == 200 and result:
            return
        logger.exception(
            "[JoinDataPreCheckFailed] SystemID => %s; StatusCode => %s; Content => %s",
            system_id,
            resp.status_code,
            resp.content,
        )
        raise JoinDataPreCheckFailed()

    @atomic
    def perform_request(self, validated_request_data):
        if validated_request_data["is_enabled"]:
            self.pre_check(
                validated_request_data["system_id"],
                validated_request_data["resource_type_id"],
                join_data_type=validated_request_data["join_data_type"],
            )
        snapshot = Snapshot.objects.get_or_create(
            system_id=validated_request_data["system_id"],
            resource_type_id=validated_request_data["resource_type_id"],
        )[0]
        if snapshot.status == SnapshotRunningStatus.PREPARING:
            raise SnapshotPreparingException()
        is_enabled = validated_request_data["is_enabled"]
        custom_config = validated_request_data.get("custom_config")
        if custom_config is not None:
            snapshot.custom_config = custom_config
        if is_enabled:
            snapshot.status = SnapshotRunningStatus.get_status(is_enabled)
            snapshot.pull_type = validated_request_data["pull_type"]
            snapshot.join_data_type = validated_request_data["join_data_type"]
            snapshot.save(update_fields=["status", "pull_type", "join_data_type", "custom_config"])
            for storage in snapshot.storages.all():
                if storage.storage_type not in validated_request_data["storage_type"]:
                    storage.delete()
            for st in validated_request_data["storage_type"]:
                SnapshotStorage.objects.get_or_create(snapshot=snapshot, storage_type=st)
        else:
            # Iterate over each storage associated with the snapshot
            ret = None
            for storage in snapshot.storages.all():
                if snapshot.join_data_type == JoinDataType.BASIC:
                    ret = BasicJoinHandler(
                        system_id=snapshot.system_id,
                        resource_type_id=snapshot.resource_type_id,
                        storage_type=storage.storage_type,
                    ).stop(multiple_storage=True)
                elif snapshot.join_data_type == JoinDataType.ASSET:
                    ret = AssetHandler(
                        system_id=snapshot.system_id,
                        resource_type_id=snapshot.resource_type_id,
                        storage_type=storage.storage_type,
                    ).stop(multiple_storage=True)
                if not ret:
                    break
            else:
                snapshot.status = SnapshotRunningStatus.CLOSED.value
                snapshot.save()
        snapshot.refresh_from_db()
        return snapshot


class EtlFieldHistory(CollectorMeta):
    name = gettext_lazy("清洗字段历史")

    def perform_request(self, validated_request_data):
        collector_config = get_object_or_404(
            CollectorConfig, collector_config_id=validated_request_data["collector_config_id"]
        )
        return {
            field["field_name"]: field["option"]["key"]
            for field in collector_config.fields
            if field.get("option", {}).get("key")
        }


class GetApiPushBaseResource(CollectorMeta, abc.ABC):
    name = gettext_lazy("获取 API PUSH")

    def get_collector(self, system_id: str):
        return (
            CollectorConfig.objects.filter(system_id=system_id, custom_type=CustomTypeEnum.OTLP_LOG.value)
            .order_by("-created_at")
            .first()
        )


class GetApiPushResource(GetApiPushBaseResource):
    name = gettext_lazy("获取 API PUSH")
    RequestSerializer = GetApiPushRequestSerializer

    def perform_request(self, validated_request_data):
        # 获取采集项
        collector_config = self.get_collector(validated_request_data["system_id"])
        # 获取详情
        if collector_config:
            report_info = api.bk_log.get_report_token(collector_config_id=collector_config.collector_config_id)
            return {
                "token": asymmetric_cipher.encrypt(report_info["bk_data_token"]),
                "collector_config_id": collector_config.collector_config_id,
                "bk_data_id": collector_config.bk_data_id,
                "collector_config_name": collector_config.collector_config_name,
                "collector_config_name_en": collector_config.collector_config_name_en,
            }
        # 没有时返回空
        return {"token": ""}


class CreateApiPushResource(GetApiPushBaseResource):
    name = gettext_lazy("创建 API PUSH")
    RequestSerializer = CreateApiPushRequestSerializer

    def perform_request(self, validated_request_data):
        # 初始化请求参数
        namespace = validated_request_data["namespace"]
        system_id = validated_request_data["system_id"]
        custom_collector_config_name = validated_request_data.get("custom_collector_config_name")

        plugin_id = GlobalMetaConfig.get(
            COLLECTOR_PLUGIN_ID,
            config_level=ConfigLevelChoices.NAMESPACE.value,
            instance_key=namespace,
        )
        if not custom_collector_config_name:
            collector_config_name = API_PUSH_COLLECTOR_NAME_FORMAT.format(
                system_id=system_id, date=datetime.datetime.now().strftime("%Y%m%d"), id=str(uniqid())[:10].lower()
            ).replace("-", "_")[:COLLECTOR_NAME_MAX_LENGTH]
        else:
            collector_config_name = custom_collector_config_name
        # 校验，重复则终止创建流程
        collector = self.get_collector(system_id)
        if collector:
            return {"collector_config_id": collector.collector_config_id}

        # 固定中文任务名称
        collector_config_name_ch = "API Push任务"

        # 创建自定义上报
        custom_params = {
            "bk_biz_id": settings.DEFAULT_BK_BIZ_ID,
            "collector_config_name": collector_config_name_ch,
            "collector_config_name_en": collector_config_name,
            "custom_type": CustomTypeEnum.OTLP_LOG.value,
            "category_id": DEFAULT_CATEGORY_ID,
            "is_display": False,
        }
        result = api.bk_log.create_api_push(**custom_params)

        # 存入数据库
        collector = CollectorConfig.objects.create(
            system_id=system_id,
            bk_biz_id=settings.DEFAULT_BK_BIZ_ID,
            bk_data_id=result["bk_data_id"],
            collector_plugin_id=plugin_id,
            collector_config_id=result["collector_config_id"],
            collector_config_name=collector_config_name_ch,
            collector_config_name_en=collector_config_name,
            custom_type=CustomTypeEnum.OTLP_LOG.value,
            description=collector_config_name,
        )

        # 异步创建ETL避免超时
        create_api_push_etl.delay(collector.collector_config_id)
        return {"collector_config_id": collector.collector_config_id}


class ApiPushTailLog(GetApiPushBaseResource):
    name = gettext_lazy("获取 API PUSH 最近日志")
    RequestSerializer = GetApiPushRequestSerializer

    def perform_request(self, validated_request_data):
        collector = self.get_collector(validated_request_data["system_id"])
        if collector:
            return api.bk_log.get_api_push_tail_log(collector_config_id=collector.collector_config_id)
        return []


class ApiPushHost(GetApiPushResource):
    name = gettext_lazy("获取 API PUSH 上报主机")

    def perform_request(self, validated_request_data):
        collector = self.get_collector(validated_request_data["system_id"])
        return {
            "enabled": bool(collector),
            "hosts": FeatureHandler(FeatureTypeChoices.BKLOG_OTLP).get_feature().config.get("hosts", []),
        }


class DataIdResource(AuditMixinResource, abc.ABC):
    tags = ["DataID"]


class GetSystemDataIdList(DataIdResource):
    name = gettext_lazy("获取系统下的DataID列表")
    RequestSerializer = GetSystemDataIdListRequestSerializer
    ResponseSerializer = GetSystemDataIdListResponseSerializer
    many_response_data = True

    def perform_request(self, validated_request_data):
        # 没有配置清洗的不算完成接入
        return CollectorConfig.objects.filter(
            system_id=validated_request_data["system_id"],
            source_platform=SourcePlatformChoices.BKBASE.value,
            bkbase_table_id__isnull=False,
        )


class GetMyDataIdList(DataIdResource):
    name = gettext_lazy("获取我的DataID列表")
    RequestSerializer = GetDataIdListRequestSerializer
    ResponseSerializer = GetDataIdListResponseSerializer
    many_response_data = True

    def perform_request(self, validated_request_data):
        # 获取数据
        params = {**validated_request_data, "page": 1, "page_size": 1}
        data = api.bk_base.get_my_rawdata_list(**params)
        total = data["count"]
        request_params = [
            {**validated_request_data, "page": i + 1, "page_size": BKBASE_API_MAX_PAGESIZE}
            for i in range(math.ceil(total / BKBASE_API_MAX_PAGESIZE))
        ]
        results = api.bk_base.get_my_rawdata_list.bulk_request(request_params)
        data = []
        for result in results:
            data.extend(result["results"])
        # 增加禁用
        applied_data_id = list(
            CollectorConfig.objects.all()
            .exclude(source_platform=SourcePlatformChoices.BKBASE.value, bkbase_table_id__isnull=True)
            .values_list("bk_data_id", flat=True)
        )
        for item in data:
            item["is_applied"] = item["id"] in applied_data_id
        data.sort(key=lambda x: [x.get("is_applied", False), x.get("raw_data_alias", "")])
        return data


class GetDataIdDetail(DataIdResource):
    name = gettext_lazy("获取DataID详情")
    RequestSerializer = GetDataIdDetailRequestSerializer
    ResponseSerializer = GetDataIdDetailResponseSerializer

    def perform_request(self, validated_request_data):
        # 获取数据
        data = api.bk_base.get_rawdata_detail(bk_data_id=validated_request_data["bk_data_id"])
        data["bkbase_url"] = (
            get_saas_url(settings.BKBASE_APP_CODE)
            + str(settings.BK_BASE_ACCESS_URL).rstrip("/")
            + "/"
            + str(validated_request_data["bk_data_id"])
        )
        # 补充信息
        collector = CollectorConfig.objects.filter(bk_data_id=validated_request_data["bk_data_id"]).first()
        if collector:
            data.update(
                {
                    "created_at": collector.created_at.astimezone(timezone.get_default_timezone()).strftime(
                        api_settings.DATETIME_FORMAT
                    ),
                    "created_by": collector.created_by,
                    "updated_at": collector.updated_at.astimezone(timezone.get_default_timezone()).strftime(
                        api_settings.DATETIME_FORMAT
                    ),
                    "updated_by": collector.updated_by,
                }
            )
        else:
            data.update(
                {
                    "created_at": arrow.get(data["created_at"]).strftime(api_settings.DATETIME_FORMAT),
                    "updated_at": arrow.get(data["updated_at"]).strftime(api_settings.DATETIME_FORMAT),
                }
            )
        return data


class GetDataIdTail(DataIdResource):
    name = gettext_lazy("获取最近源数据")
    RequestSerializer = GetDataIdTailRequestSerializer
    ResponseSerializer = GetDataIdTailResponseSerializer
    many_response_data = True

    def perform_request(self, validated_request_data):
        # 获取最近数据
        tail_data = api.bk_base.get_rawdata_tail(**validated_request_data)
        if validated_request_data["parse_json"]:
            for _data in tail_data:
                _data["parsed_value"] = json.loads(_data.pop("value", "{}"))
        return tail_data


class ApplyDataIdSource(DataIdResource):
    name = gettext_lazy("接入DataID数据源")
    RequestSerializer = ApplyDataIdSourceRequestSerializer

    def perform_request(self, validated_request_data):
        namespace = validated_request_data["namespace"]
        bk_data_id = validated_request_data["bk_data_id"]
        # 自定义名称
        custom_collector_ch_name = validated_request_data.get("custom_collector_ch_name")
        custom_collector_en_name = validated_request_data.get("custom_collector_en_name")
        plugin_id = GlobalMetaConfig.get(
            COLLECTOR_PLUGIN_ID,
            config_level=ConfigLevelChoices.NAMESPACE.value,
            instance_key=namespace,
        )
        # 校验当前用户是否有权限操作
        has_permission = False
        results = resource.databus.collector.get_my_data_id_list()
        for r in results:
            if r["bk_data_id"] == bk_data_id:
                has_permission = True
                break
        if not has_permission:
            raise ParamsNotValid(message=gettext("无数据源 %s 的访问权限") % bk_data_id)
        # 检验数据源存在状态，没有配置清洗的数据源可以二次接入
        if CollectorConfig.objects.filter(bk_data_id=bk_data_id, bkbase_table_id__isnull=False).exists():
            raise ParamsNotValid(message=gettext("DataID %s 已接入") % bk_data_id)
        # 获取数据源详情
        raw_data = resource.databus.collector.get_data_id_detail(bk_data_id=bk_data_id)
        # 兼容已存在的数据源
        collector = CollectorConfig._objects.filter(bk_data_id=bk_data_id).first()
        # 初始化参数
        params = {
            "system_id": validated_request_data["system_id"],
            "bk_biz_id": raw_data["bk_biz_id"],
            "bk_data_id": bk_data_id,
            "collector_plugin_id": plugin_id,
            "collector_config_id": -bk_data_id,
            "collector_config_name": raw_data["raw_data_alias"]
            if not custom_collector_ch_name
            else custom_collector_ch_name,
            "collector_config_name_en": raw_data["raw_data_name"]
            if not custom_collector_en_name
            else custom_collector_en_name,
            "source_platform": SourcePlatformChoices.BKBASE.value,
            "custom_type": raw_data["custom_type"],
            "description": raw_data["description"],
            "etl_config": EtlConfigEnum.BK_BASE_JSON.value,
            "is_deleted": False,
            "record_log_type": validated_request_data["record_log_type"],
            "select_sdk_type": validated_request_data["select_sdk_type"],
        }
        # 存在则更新
        if collector is not None:
            CollectorConfig.objects.filter(bk_data_id=bk_data_id, is_deleted=True).update(**params)
            collector.refresh_from_db()
        # 不存在则创建数据源
        else:
            collector = CollectorConfig.objects.create(**params)
        return {"bk_data_id": collector.bk_data_id}


class DataIdEtlPreview(DataIdResource):
    name = gettext_lazy("DataID清洗预览")
    RequestSerializer = DataIdEtlPreviewRequestSerializer

    def perform_request(self, validated_request_data):
        instance = EtlClean.get_instance(EtlConfigEnum.BK_BASE_JSON.value)
        return instance.etl_preview(**validated_request_data, etl_params={})


class DataIdEtlStorage(DataIdResource):
    name = gettext_lazy("创建或更新DataID清洗入库")
    RequestSerializer = DataIdEtlStorageRequestSerializer

    def perform_request(self, validated_request_data):
        # 创建更新清洗规则
        etl_storage: EtlClean = EtlClean.get_instance(EtlConfigEnum.BK_BASE_JSON.value)
        etl_storage.update_or_create(
            collector_config_id=-validated_request_data["bk_data_id"],
            etl_params=validated_request_data["etl_params"],
            fields=validated_request_data["fields"],
            namespace=validated_request_data["namespace"],
        )


class DataIdEtlFieldHistory(DataIdResource):
    name = gettext_lazy("DataID清洗字段历史")

    def perform_request(self, validated_request_data):
        collector_config = get_object_or_404(CollectorConfig, bk_data_id=validated_request_data["bk_data_id"])
        return {
            field["field_name"]: field["option"]["key"]
            for field in collector_config.fields
            if field.get("option", {}).get("key")
        }


class DeleteDataId(DataIdResource):
    name = gettext_lazy("删除DataID接入")
    RequestSerializer = DeleteDataIdRequestSerializer

    def perform_request(self, validated_request_data):
        collector = get_object_or_404(
            CollectorConfig,
            bk_data_id=validated_request_data["bk_data_id"],
            source_platform=SourcePlatformChoices.BKBASE.value,
        )
        # 停止并删除清洗入库
        if collector.processing_id:
            stop_bkbase_clean(collector.bkbase_table_id, collector.processing_id)
            api.bk_base.databus_cleans_delete(processing_id=collector.processing_id)
        # 数据库删除
        CollectorConfig._objects.filter(collector_config_id=collector.collector_config_id).delete()


class SnapshotStatisticResource(ModelResource, CollectorMeta):
    name = gettext_lazy("快照统计信息")
    model = SnapshotCheckStatistic
    action = "list"
    filter_fields = ["namespace"]
    serializer_class = SnapshotCheckStatisticSerializer

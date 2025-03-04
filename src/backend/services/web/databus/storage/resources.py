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

from bk_resource import api, resource
from bk_resource.utils.common_utils import ignored
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy
from rest_framework import serializers
from rest_framework.settings import api_settings

from apps.audit.resources import AuditMixinResource
from apps.bk_crypto.crypto import asymmetric_cipher
from apps.exceptions import MetaConfigNotExistException, StorageChanging
from apps.meta.constants import ConfigLevelChoices
from apps.meta.models import GlobalMetaConfig
from apps.permission.handlers.actions import ActionEnum
from services.web.databus.constants import (
    COLLECTOR_PLUGIN_ID,
    DEFAULT_REPLICA_WRITE_STORAGE_CONFIG_KEY,
    DEFAULT_STORAGE_CONFIG_KEY,
    EMPTY_CLUSTER_ID,
    ClusterMode,
    PluginSceneChoices,
)
from services.web.databus.models import CollectorPlugin, StorageOperateLog
from services.web.databus.storage.handler.es import StorageConfig
from services.web.databus.storage.handler.redis import RedisHandler
from services.web.databus.storage.serializers import (
    CreateRedisRequestSerializer,
    CreateRedisResponseSerializer,
    StorageActivateRequestSerializer,
    StorageCreateRequestSerializer,
    StorageDeleteRequestSerializer,
    StorageListRequestSerializer,
    StorageListResponseSerializer,
    StorageUpdateRequestSerializer,
)

# todo: 当bklog和bkbase相关支持完成后，直接管理predefined/bkbase的存储


class StorageMeta(AuditMixinResource):
    tags = ["Storage"]

    def record_config(self, cluster_id, validated_request_data):
        StorageConfig.set_allocation_min_days(
            validated_request_data["namespace"], cluster_id, validated_request_data["allocation_min_days"]
        )


class DeleteStorageResource(StorageMeta):
    name = "删除集群"
    RequestSerializer = StorageDeleteRequestSerializer
    audit_action = ActionEnum.DELETE_STORAGE

    def perform_request(self, validated_request_data):
        data = api.bk_log.delete_storage(validated_request_data)
        StorageOperateLog.create(validated_request_data["cluster_id"])
        return data


class UpdateStorageResource(StorageMeta):
    name = gettext_lazy("更新集群")
    RequestSerializer = StorageUpdateRequestSerializer
    audit_action = ActionEnum.EDIT_STORAGE

    def perform_request(self, validated_request_data):
        password = validated_request_data["auth_info"]["password"]
        if password:
            validated_request_data["auth_info"]["password"] = asymmetric_cipher.decrypt(password)
        data = None
        if not validated_request_data["pre_defined"]:
            data = api.bk_log.update_storage(validated_request_data)
        StorageOperateLog.create(validated_request_data["cluster_id"])
        self.record_config(
            data["cluster_config"]["cluster_id"] if data else validated_request_data["cluster_id"],
            validated_request_data,
        )
        # 更新采集插件
        namespace = validated_request_data["namespace"]
        CollectorPlugin.objects.filter(
            namespace=namespace, plugin_scene__in=[PluginSceneChoices.COLLECTOR.value]
        ).update(storage_changed=True)
        return data


class StorageActivateResource(StorageMeta):
    name = gettext_lazy("设置默认集群")
    RequestSerializer = StorageActivateRequestSerializer
    serializer_class = serializers.IntegerField

    @transaction.atomic
    def perform_request(self, validated_request_data):
        if cache.get("celery:change_storage_cluster"):
            raise StorageChanging()
        # 设置默认集群
        namespace = validated_request_data["namespace"]
        if validated_request_data["cluster_mode"] == ClusterMode.MAIN:
            _ = GlobalMetaConfig.set(
                DEFAULT_STORAGE_CONFIG_KEY,
                validated_request_data["cluster_id"],
                config_level=ConfigLevelChoices.NAMESPACE.value,
                instance_key=namespace,
            )
        else:
            _ = GlobalMetaConfig.set(
                DEFAULT_REPLICA_WRITE_STORAGE_CONFIG_KEY,
                {"cluster_id": validated_request_data["cluster_id"]}
                if not validated_request_data.get('config')
                else validated_request_data['config'],
                config_level=ConfigLevelChoices.NAMESPACE.value,
                instance_key=namespace,
            )
        # 设置采集插件
        CollectorPlugin.objects.filter(
            namespace=namespace, plugin_scene__in=[PluginSceneChoices.COLLECTOR.value]
        ).update(storage_changed=True)
        return validated_request_data["cluster_id"]


class StorageListResource(StorageMeta):
    name = gettext_lazy("集群列表")
    RequestSerializer = StorageListRequestSerializer
    ResponseSerializer = StorageListResponseSerializer
    many_response_data = True
    audit_action = ActionEnum.LIST_STORAGE

    def _check_filter_clusters(self, cluster: dict, validated_request_data: dict) -> bool:
        namespace = validated_request_data["namespace"]
        condition_namespace = cluster["cluster_config"].get("custom_option", {}).get("cluster_namespace") == namespace
        if not validated_request_data.get("keyword"):
            return condition_namespace
        keyword = validated_request_data["keyword"]
        name = cluster["cluster_config"].get("cluster_name", "")
        domain = cluster["cluster_config"].get("domain_name", "")
        condition_keyword = name.find(keyword) != -1 or domain.find(keyword) != -1
        return condition_namespace and condition_keyword

    def _update_default_option(self, default_cluster_id: int, cluster: dict, namespace: str) -> dict:
        option = cluster["cluster_config"]["custom_option"].get("option", {})
        option.update(
            {
                "is_default": bool(cluster["cluster_config"]["cluster_id"] == default_cluster_id),
                "updater": "",
                "update_at": "",
                "creator": "",
                "create_at": "",
            }
        )
        update_log = StorageOperateLog.objects.filter(cluster_id=cluster["cluster_config"]["cluster_id"]).first()
        if update_log:
            option.update(
                {
                    "updater": update_log.operator,
                    "update_at": update_log.operate_at.astimezone(timezone.get_default_timezone()).strftime(
                        api_settings.DATETIME_FORMAT
                    ),
                }
            )
        create_log = StorageOperateLog.objects.filter(cluster_id=cluster["cluster_config"]["cluster_id"]).last()
        if create_log:
            option.update(
                {
                    "creator": create_log.operator,
                    "create_at": create_log.operate_at.astimezone(timezone.get_default_timezone()).strftime(
                        api_settings.DATETIME_FORMAT
                    ),
                }
            )
        cluster["cluster_config"]["custom_option"]["option"] = option
        cluster["cluster_config"]["custom_option"]["allocation_min_days"] = StorageConfig.get_allocation_min_days(
            namespace, cluster["cluster_config"]["cluster_id"]
        )
        return cluster

    def perform_request(self, validated_request_data):
        namespace = validated_request_data["namespace"]
        bk_log_clusters = api.bk_log.get_storages(**validated_request_data)
        try:
            default_cluster_id = int(
                GlobalMetaConfig.get(
                    DEFAULT_STORAGE_CONFIG_KEY,
                    config_level=ConfigLevelChoices.NAMESPACE.value,
                    instance_key=namespace,
                )
            )
        except MetaConfigNotExistException:
            default_cluster_id = EMPTY_CLUSTER_ID
        clusters = [
            self._update_default_option(default_cluster_id, cluster, namespace)
            for cluster in bk_log_clusters
            if self._check_filter_clusters(cluster, validated_request_data)
        ]
        return clusters


class CreateStorageResource(StorageMeta):
    name = gettext_lazy("创建集群")
    RequestSerializer = StorageCreateRequestSerializer
    serializer_class = serializers.IntegerField
    audit_action = ActionEnum.CREATE_STORAGE

    @transaction.atomic()
    def perform_request(self, validated_request_data):
        password = validated_request_data["auth_info"]["password"]
        if password:
            validated_request_data["auth_info"]["password"] = asymmetric_cipher.decrypt(password)
        pre_defined = validated_request_data.pop("pre_defined", False)
        if pre_defined:
            data = validated_request_data['pre_defined_extra_config']["cluster_id"]
        else:
            data = api.bk_log.create_storage(validated_request_data)
        StorageOperateLog.create(data)
        self.record_config(data, validated_request_data)
        try:
            GlobalMetaConfig.get(
                DEFAULT_STORAGE_CONFIG_KEY,
                config_level=ConfigLevelChoices.NAMESPACE.value,
                instance_key=validated_request_data["namespace"],
            )
        except MetaConfigNotExistException:
            with ignored(StorageChanging):
                resource.databus.storage.storage_activate(
                    namespace=validated_request_data["namespace"], cluster_id=data
                )
        if (
            GlobalMetaConfig.get(
                COLLECTOR_PLUGIN_ID,
                config_level=ConfigLevelChoices.NAMESPACE.value,
                instance_key=validated_request_data["namespace"],
                default=None,
            )
            is None
        ):
            resource.databus.collector_plugin.create_plugin(
                namespace=validated_request_data["namespace"], is_default=True
            )
        return data


class CreateOrUpdateRedisResource(StorageMeta):
    name = gettext_lazy("创建或更新Redis")
    RequestSerializer = CreateRedisRequestSerializer
    ResponseSerializer = CreateRedisResponseSerializer

    def perform_request(self, validated_request_data):
        redis_id = validated_request_data.get("redis_id")
        return RedisHandler(redis_id).update_or_create(validated_request_data)

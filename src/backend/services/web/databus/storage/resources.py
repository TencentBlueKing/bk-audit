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

import json

from bk_resource import api, resource
from bk_resource.utils.common_utils import ignored
from blueapps.utils.logger import logger
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
from core.sensitive import redact_secrets
from services.web.bkbase import plugin_storage_switch
from services.web.bkbase.common import get_bkbase_version
from services.web.bkbase.constants import BKBaseVersion
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
        plugins = CollectorPlugin.objects.filter(
            namespace=namespace, plugin_scene__in=[PluginSceneChoices.COLLECTOR.value]
        )
        if get_bkbase_version() == BKBaseVersion.V4:
            plugin_storage_switch.mark_config_update(plugins)
        else:
            plugins.update(storage_changed=True)
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
        purpose = validated_request_data["cluster_mode"]
        if purpose == ClusterMode.MAIN:
            key, target = DEFAULT_STORAGE_CONFIG_KEY, validated_request_data["cluster_id"]
        else:
            key = DEFAULT_REPLICA_WRITE_STORAGE_CONFIG_KEY
            target = validated_request_data.get("config") or {"cluster_id": validated_request_data["cluster_id"]}
        # 设置采集插件
        plugins = CollectorPlugin.objects.filter(
            namespace=namespace, plugin_scene__in=[PluginSceneChoices.COLLECTOR.value]
        )
        is_v4 = get_bkbase_version() == BKBaseVersion.V4
        if is_v4:
            plugin_storage_switch.reserve(plugins, namespace=namespace, purpose=purpose, target=target)
        GlobalMetaConfig.set(key, target, config_level=ConfigLevelChoices.NAMESPACE.value, instance_key=namespace)
        if not is_v4:
            plugins.update(storage_changed=True)
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
    # BKSEC 1578945：框架 ResourceRequestLog 无脱敏能力（请求体含密码明文），关闭；
    # 排障日志由本资源 request() 以脱敏形式自记录，非敏感排障字段全保留
    support_data_collect = False

    def request(self, request_data=None, **kwargs):
        """脱敏版请求日志：完整保留排障上下文，仅敏感键名值打码"""
        # viewset 路由经 request_data 传入；resource 直调（init_redis 等）走 **kwargs，需归一化
        log_request_data = request_data if request_data is not None else kwargs
        try:
            response_data = super().request(request_data=request_data, **kwargs)
        except Exception as err:
            self._log_redacted(log_request_data, {"error": str(err)})
            raise
        self._log_redacted(log_request_data, response_data)
        return response_data

    @staticmethod
    def _log_redacted(request_data, response_data):
        logger.info(
            "[ResourceRequestLog][Redacted]\nResource => %s\nRequestData => %s\nResponseData => %s",
            "services.web.databus.storage.resources.CreateOrUpdateRedisResource",
            json.dumps(redact_secrets(request_data), ensure_ascii=False, default=str),
            json.dumps(redact_secrets(response_data), ensure_ascii=False, default=str),
        )

    def perform_request(self, validated_request_data):
        # 对齐 ES create/update 的 decrypt 预留位（resources.py:85-87,222-224 同款）：
        # 默认部署 FakeAsymmetricCipher 恒等透传零行为变化；启用 BKAPP_ENABLE_BKCRYPTO 后要求密文提交
        connection_info = validated_request_data.get("connection_info") or {}
        password = connection_info.get("password")
        if password:
            connection_info["password"] = asymmetric_cipher.decrypt(password)
        redis_id = validated_request_data.get("redis_id")
        return RedisHandler(redis_id).update_or_create(validated_request_data)

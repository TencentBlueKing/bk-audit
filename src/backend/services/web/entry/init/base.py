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
import os
from typing import List, Type

from bk_resource import resource
from django.conf import settings
from django.utils.translation import gettext_lazy

from apps.exceptions import InitSystemDisabled, ParamsNotValid
from apps.meta.models import Field, GlobalMetaConfig
from apps.meta.tasks import sync_iam_systems
from apps.meta.utils.fields import STANDARD_FIELDS
from apps.permission.handlers.resource_types import ResourceEnum, ResourceTypeMeta
from core.utils.distutils import strtobool
from services.web.databus.collector.snapshot.system.base import create_iam_data_link
from services.web.databus.constants import (
    ClusterMode,
    JoinDataType,
    SnapShotStorageChoices,
)
from services.web.databus.storage.serializers import (
    CreateRedisRequestSerializer,
    StorageCreateRequestSerializer,
)
from services.web.databus.tasks import create_or_update_plugin_etl
from services.web.entry.constants import (
    INIT_ASSET_FINISHED_KEY,
    INIT_DORIS_FISHED_KEY,
    INIT_ES_FISHED_KEY,
    INIT_EVENT_FINISHED_KEY,
    INIT_FIELDS_FINISHED_KEY,
    INIT_REDIS_FISHED_KEY,
    INIT_SNAPSHOT_FINISHED_KEY,
    INIT_SYSTEM_FINISHED_KEY,
    SDK_CONFIG_KEY,
)
from services.web.risk.constants import (
    EVENT_DORIS_CLUSTER_ID_KEY,
    EVENT_ES_CLUSTER_ID_KEY,
)
from services.web.risk.handlers import EventHandler


class SystemInitHelper:
    config_path = os.path.join(os.getcwd(), "support-files", "init-configs")

    def __init__(self):
        self.es_config = self.get_es_config()
        self.redis_config = self.get_redis_config()
        self.doris_config = self.get_doris_config()

    def generate_env(self):
        path = os.path.join(os.getcwd(), "init_env")
        with open(path, "w+") as file:
            file.write(f"BKAPP_INIT_ES_CONFIG={json.dumps(self.es_config)}\n")
            file.write(f"BKAPP_INIT_REDIS_CONFIG={json.dumps(self.redis_config)}\n")
            file.write(f"BKAPP_INIT_DORIS_CONFIG={json.dumps(self.doris_config)}\n")

    def get_es_config(self):
        path = os.path.join(self.config_path, "es.json")
        with open(path, "r") as file:
            config = json.loads(file.read())
        serializer = StorageCreateRequestSerializer(data=config, many=True)
        serializer.is_valid(raise_exception=True)
        return config

    def get_redis_config(self):
        path = os.path.join(self.config_path, "redis.json")
        with open(path, "r") as file:
            config = json.loads(file.read())
        serializer = CreateRedisRequestSerializer(data=config, many=True)
        serializer.is_valid(raise_exception=True)
        return config

    def get_doris_config(self):
        path = os.path.join(self.config_path, "doris.json")
        with open(path, "r") as file:
            config = json.loads(file.read())
        serializer = StorageCreateRequestSerializer(data=config, many=True)
        serializer.is_valid(raise_exception=True)
        return config


class SystemInitHandler:
    def init(self):
        print("[Main] Init Start")
        # self.pre_init()
        # self.init_standard_fields()
        # self.init_es()
        # self.init_doris()
        # self.init_redis()
        # self.init_snapshot()
        # self.init_event()
        # self.create_or_update_plugin_etl()
        # self.init_system()
        # self.init_asset()
        self.init_sdk_config()
        print("[Main] Init Finished")

    def pre_init(self):
        enable_system_init = strtobool(os.getenv("BKAPP_INIT_SYSTEM", "False"))
        print(f"[PreInit] Env BKAPP_INIT_SYSTEM => {enable_system_init}")
        if not enable_system_init:
            raise InitSystemDisabled()

    def pre_check(self, key):
        print(f"[PreCheck] {key}")
        inited = GlobalMetaConfig.get(key, default=False)
        print(f"[PreCheck] {key} {inited}")
        return inited

    def post_init(self, key):
        GlobalMetaConfig.set(key, True)
        print(f"[PostInit] {key} Finished")

    def _init_es(self, es_config: dict):
        print(f"[InitEs] Params => {es_config}")
        # 创建默认ES集群的时候，已经创建了默认namespace的collector plugin。
        cluster_id = resource.databus.storage.create_storage(es_config)
        print(f"[InitEs] Resp => {cluster_id}")
        GlobalMetaConfig.set(EVENT_ES_CLUSTER_ID_KEY, cluster_id)
        print("InitEs GlobalMetaConfig Set Success")
        resource.databus.storage.storage_activate(namespace=settings.DEFAULT_NAMESPACE, cluster_id=cluster_id)
        print(f"[InitEs] Default => {cluster_id}")

    def init_es(self):
        if self.pre_check(INIT_ES_FISHED_KEY):
            return
        es_configs = json.loads(os.getenv("BKAPP_INIT_ES_CONFIG"))
        for es_config in es_configs:
            self._init_es(es_config)
        self.post_init(INIT_ES_FISHED_KEY)

    def init_doris(self):
        if self.pre_check(INIT_DORIS_FISHED_KEY):
            return
        doris_configs = json.loads(os.getenv("BKAPP_INIT_DORIS_CONFIG"))
        for doris_config in doris_configs:
            self._init_doris(doris_config)
        self.post_init(INIT_DORIS_FISHED_KEY)

    def _init_doris(self, doris_config: dict):
        print(f"[InitDoris] Params => {doris_config}")
        if not doris_config.get('pre_defined', False):
            raise ParamsNotValid(message=gettext_lazy("Doris必须是预定义的"))
        cluster_id = resource.databus.storage.create_storage(doris_config)
        print(f"[InitDoris] Resp => {cluster_id}")
        GlobalMetaConfig.set(EVENT_DORIS_CLUSTER_ID_KEY, cluster_id)
        print("InitDoris GlobalMetaConfig Set Success")
        resource.databus.storage.storage_activate(
            namespace=settings.DEFAULT_NAMESPACE,
            cluster_id=cluster_id,
            cluster_mode=ClusterMode.REPLICA,
            config=doris_config['pre_defined_extra_config'],
        )
        print(f"[InitDoris] Default => {cluster_id}")

    def _init_redis(self, redis_config: dict):
        print(f"[InitRedis] Params => {redis_config}")
        resp = resource.databus.storage.create_or_update_redis(redis_config)
        print(f"[InitRedis] Resp => {resp}")

    def init_redis(self):
        if self.pre_check(INIT_REDIS_FISHED_KEY):
            return
        redis_configs = json.loads(os.getenv("BKAPP_INIT_REDIS_CONFIG"))
        for redis_config in redis_configs:
            self._init_redis(redis_config)
        self.post_init(INIT_REDIS_FISHED_KEY)

    def init_snapshot(self):
        if self.pre_check(INIT_SNAPSHOT_FINISHED_KEY):
            return
        print("[InitSnapshot] Type => Action")
        create_iam_data_link("action")
        print("[InitSnapshot] Type => ResourceType")
        create_iam_data_link("resource_type")
        print("[InitSnapshot] Type => User")
        if settings.SNAPSHOT_USERINFO_RESOURCE_URL:
            create_iam_data_link("user")
        self.post_init(INIT_SNAPSHOT_FINISHED_KEY)

    def init_standard_fields(self):
        if self.pre_check(INIT_FIELDS_FINISHED_KEY):
            return
        print("[InitStandardFields] Start")
        Field.objects.filter(is_built_in=True).delete()
        fields = Field.objects.bulk_create(STANDARD_FIELDS)
        print(
            "[InitStandardFields] Count => {}; FieldNames => {};".format(
                len(fields), ", ".join([field.field_name for field in fields])
            )
        )
        print("[InitStandardFields] End")
        self.post_init(INIT_FIELDS_FINISHED_KEY)

    def init_event(self):
        if self.pre_check(INIT_EVENT_FINISHED_KEY):
            return
        print("[InitEvent] Start")
        EventHandler().update_or_create_rt()
        print("[InitEvent] Stop")
        self.post_init(INIT_EVENT_FINISHED_KEY)

    def init_system(self):
        if self.pre_check(INIT_SYSTEM_FINISHED_KEY):
            return
        print("[InitSystem] Start")
        sync_iam_systems()
        print("[InitSystem] Finished")
        self.post_init(INIT_SYSTEM_FINISHED_KEY)

    def init_sdk_config(self):
        sdk_config = {
            "go_sdk": "https://github.com/TencentBlueKing/bk-audit-go-sdk",
            "java_sdk": "https://github.com/TencentBlueKing/bk-audit-java-sdk",
            "python_sdk": "https://github.com/TencentBlueKing/bk-audit-python-sdk"
        }
        GlobalMetaConfig.set(SDK_CONFIG_KEY, sdk_config)

    def create_or_update_plugin_etl(self):
        """创建或更新采集入库"""
        print("[CreateOrUpdatePluginEtl] Start")
        create_or_update_plugin_etl()
        print("[CreateOrUpdatePluginEtl] Stop")

    def init_asset(self):
        """
        初始化资产
        """

        print("[InitAsset] Start")
        status_map = GlobalMetaConfig.get(INIT_ASSET_FINISHED_KEY, default={})
        assets: List[Type[ResourceTypeMeta]] = [
            ResourceEnum.RISK,
            ResourceEnum.STRATEGY,
            ResourceEnum.STRATEGY_TAG,
            ResourceEnum.TICKET_PERMISSION,
        ]
        for asset in assets:
            system_id, resource_type_id = asset.system_id, asset.id
            map_key = f"{system_id}-{resource_type_id}"
            if status_map.get(map_key):
                continue
            try:
                resource.databus.collector.toggle_join_data(
                    {
                        "system_id": system_id,
                        "resource_type_id": resource_type_id,
                        "is_enabled": True,
                        "join_data_type": JoinDataType.ASSET.value,
                        "storage_type": [
                            SnapShotStorageChoices.HDFS.value,
                            SnapShotStorageChoices.DORIS.value,
                        ],
                    }
                )
                status_map[map_key] = True
            except Exception as err:  # pylint: disable=broad-except
                print(f"[InitAsset] Failed => {system_id}-{resource_type_id}: {err}")
                status_map[map_key] = False
        GlobalMetaConfig.set(INIT_ASSET_FINISHED_KEY, status_map)
        print("[InitAsset] Finished")

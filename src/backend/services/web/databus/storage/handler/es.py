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

from bk_resource import api
from django.conf import settings

from apps.meta.constants import ConfigLevelChoices
from apps.meta.models import GlobalMetaConfig
from services.web.databus.constants import (
    DEFAULT_ALLOCATION_MIN_DAYS,
    DEFAULT_RETENTION,
    DEFAULT_STORAGE_REPLIES,
    DEFAULT_STORAGE_SHARD_SIZE,
    DEFAULT_STORAGE_SHARDS,
    STORAGE_ALLOCATION_MIN_DAYS_KEY,
)


class StorageConfig:
    @classmethod
    def set_allocation_min_days(cls, namespace: str, cluster_id: int, allocation_min_days: int):
        GlobalMetaConfig.set(
            STORAGE_ALLOCATION_MIN_DAYS_KEY.format(id=cluster_id),
            allocation_min_days,
            ConfigLevelChoices.NAMESPACE.value,
            namespace,
        )

    @classmethod
    def get_allocation_min_days(cls, namespace: str, cluster_id: int):
        return GlobalMetaConfig.get(
            STORAGE_ALLOCATION_MIN_DAYS_KEY.format(id=cluster_id),
            ConfigLevelChoices.NAMESPACE.value,
            namespace,
            default=DEFAULT_ALLOCATION_MIN_DAYS,
        )

    @classmethod
    def get_default(cls, namespace: str, cluster_id: int) -> (int, int, int, int, int):
        # 默认配置
        retention, replicas, allocation_min_days, storage_shards_nums, storage_shards_size = (
            DEFAULT_RETENTION,
            DEFAULT_STORAGE_REPLIES,
            DEFAULT_ALLOCATION_MIN_DAYS,
            DEFAULT_STORAGE_SHARDS,
            DEFAULT_STORAGE_SHARD_SIZE,
        )
        # 获取集群信息
        clusters = api.bk_log.get_storages(bk_biz_id=settings.DEFAULT_BK_BIZ_ID)
        cluster_obj = None
        for cluster in clusters:
            if cluster["cluster_config"]["cluster_id"] == int(cluster_id):
                cluster_obj = cluster
        # 没有时返回默认的
        if not cluster_obj:
            return retention, replicas, allocation_min_days, storage_shards_nums, storage_shards_size
        # 集群信息
        cluster_config = cluster_obj["cluster_config"]
        custom_option = cluster_config["custom_option"]
        setup_config = custom_option["setup_config"]
        # 获取节点信息
        nodes = api.bk_log.batch_connectivity_detect(cluster_ids=cluster_id, origin_resp=True)
        nodes = nodes[str(cluster_id)]["cluster_stats"]["data_node_count"]
        # 返回配置
        retention = setup_config["retention_days_default"]
        replicas = setup_config["number_of_replicas_default"]
        allocation_min_days = cls.get_allocation_min_days(namespace, cluster_id)
        storage_shards_nums = nodes
        return retention, replicas, allocation_min_days, storage_shards_nums, storage_shards_size

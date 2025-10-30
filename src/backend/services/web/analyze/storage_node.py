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
from abc import ABC, abstractmethod
from typing import List, Union

from bk_resource import resource
from django.conf import settings

from apps.meta.constants import ConfigLevelChoices
from apps.meta.models import GlobalMetaConfig
from apps.meta.utils.fields import BKDATA_ES_TYPE_MAP
from services.web.analyze.constants import (
    DEFAULT_HDFS_STORAGE_CLUSTER_KEY,
    DEFAULT_QUEUE_STORAGE_CLUSTER_KEY,
)
from services.web.analyze.exceptions import ClusterNotExists
from services.web.databus.constants import (
    DEFAULT_REPLICA_WRITE_STORAGE_CONFIG_KEY,
    DEFAULT_RETENTION,
    DEFAULT_STORAGE_CONFIG_KEY,
    DORIS_EVENT_PHYSICAL_TABLE_NAME_KEY,
)
from services.web.risk.constants import EventMappingFields
from services.web.risk.handlers import EventHandler


class BaseStorageNode(ABC):
    def __init__(self, namespace: str):
        self.namespace = namespace

    @property
    @abstractmethod
    def node_type(self) -> str:
        raise NotImplementedError()

    @property
    @abstractmethod
    def expires(self) -> int:
        raise NotImplementedError()

    @property
    @abstractmethod
    def cluster(self) -> Union[str, int]:
        raise NotImplementedError()

    @classmethod
    def build_rt_id(cls, bk_biz_id: int, table_name: str) -> str:
        return f"{bk_biz_id}_{table_name}"

    def build_node_config(self, bk_biz_id: int, raw_table_name: str, from_result_table_ids: List[str]) -> dict:
        if not self.cluster:
            return {}
        result_table_id = self.build_rt_id(bk_biz_id, raw_table_name)
        from_ids = from_result_table_ids or [result_table_id]
        return {
            "node_type": self.node_type,
            "from_result_table_ids": from_ids,
            "bk_biz_id": bk_biz_id,
            "result_table_id": result_table_id,
            "name": f"{self.node_type}_{raw_table_name}",
            "expires": self.expires,
            "cluster": self.cluster,
        }


class ESStorageNode(BaseStorageNode):
    node_type = "elastic_storage"
    expires = DEFAULT_RETENTION

    @property
    def cluster(self) -> Union[str, int]:
        default_cluster_id = int(
            GlobalMetaConfig.get(
                DEFAULT_STORAGE_CONFIG_KEY,
                config_level=ConfigLevelChoices.NAMESPACE.value,
                instance_key=self.namespace,
            )
        )
        cluster_info = None
        clusters = resource.databus.storage.storage_list(namespace=self.namespace)
        for item in clusters:
            if item["cluster_config"]["cluster_id"] == default_cluster_id:
                cluster_info = item
        if cluster_info is None:
            raise ClusterNotExists()

        bkbase_cluster_id = cluster_info["cluster_config"].get("custom_option", {}).get("bkbase_cluster_id")
        return bkbase_cluster_id

    def build_node_config(self, bk_biz_id: int, raw_table_name: str, from_result_table_ids: List[str]) -> dict:
        table_id = EventHandler.get_table_id().replace(".", "_")
        return {
            **super().build_node_config(bk_biz_id, raw_table_name, from_result_table_ids),
            "indexed_fields": [],
            "has_replica": False,
            "has_unique_key": False,
            "storage_keys": [],
            "analyzed_fields": [],
            "doc_values_fields": [],
            "json_fields": [],
            "physical_table_name": f"write_{{yyyyMMdd}}_{table_id}",
        }


class QueueStorageNode(BaseStorageNode):
    node_type = "queue_storage"
    expires = settings.DEFAULT_QUEUE_STORAGE_EXPIRES

    @property
    def cluster(self) -> Union[str, int]:
        return GlobalMetaConfig.get(
            DEFAULT_QUEUE_STORAGE_CLUSTER_KEY,
            config_level=ConfigLevelChoices.NAMESPACE.value,
            instance_key=self.namespace,
            default="",
        )


class HDFSStorageNode(BaseStorageNode):
    node_type = "hdfs_storage"
    expires = settings.DEFAULT_HDFS_STORAGE_EXPIRES

    @property
    def cluster(self) -> Union[str, int]:
        return GlobalMetaConfig.get(
            DEFAULT_HDFS_STORAGE_CLUSTER_KEY,
            config_level=ConfigLevelChoices.NAMESPACE.value,
            instance_key=self.namespace,
            default="",
        )


class DorisStorageNode(BaseStorageNode):
    node_type = "doris"
    expires = settings.EVENT_DORIS_EXPIRES

    @property
    def cluster(self) -> Union[str, int]:
        """
        获取当前命名空间下的 Doris 集群 ID
        """

        replica_config = GlobalMetaConfig.get(
            DEFAULT_REPLICA_WRITE_STORAGE_CONFIG_KEY,
            config_level=ConfigLevelChoices.NAMESPACE.value,
            instance_key=self.namespace,
        )
        if not replica_config:
            return ""
        return replica_config["bkbase_cluster_id"]

    def build_node_config(self, bk_biz_id: int, raw_table_name: str, from_result_table_ids: List[str]) -> dict:
        fields = []
        for field in EventMappingFields().fields:
            field_type = BKDATA_ES_TYPE_MAP.get(field.field_type, field.field_type)
            fields.append(
                {
                    "type": field_type,
                    "config": "json" if field.is_json else "",
                    "field": field.field_name,
                    "alias": str(field.description or field.alias_name or field.field_name),
                }
            )

        # 从全局配置中获取物理表名，合流写入
        physical_table_name = GlobalMetaConfig.get(
            config_key=DORIS_EVENT_PHYSICAL_TABLE_NAME_KEY,
            config_level=ConfigLevelChoices.NAMESPACE.value,
            instance_key=self.namespace,
        )

        return {
            **super().build_node_config(bk_biz_id, raw_table_name, from_result_table_ids),
            "indexed_fields": [],
            "has_replica": False,
            "has_unique_key": False,
            "storage_keys": [],
            "analyzed_fields": [],
            "doc_values_fields": [],
            "json_fields": [EventMappingFields.EVENT_EVIDENCE.field_name, EventMappingFields.EVENT_DATA.field_name],
            "physical_table_name": physical_table_name,
            "original_json_fields": [],
            "udc_name": "doris",
            "storage_field_config": {},
            "custom_param_config": {
                "fields": fields,
                "expires_dup": settings.EVENT_DORIS_EXPIRES,
                "expires_uniq": "-1",
                "data_model": "duplicate",
            },
        }

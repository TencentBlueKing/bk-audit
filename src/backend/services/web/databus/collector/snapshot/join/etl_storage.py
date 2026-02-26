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

import copy
import json
from functools import cached_property
from typing import List

from bk_resource import api, resource
from bk_resource.settings import bk_resource_settings
from django.conf import settings

from api.bk_base.constants import StorageType
from apps.meta.constants import ConfigLevelChoices
from apps.meta.models import GlobalMetaConfig, ResourceType, System
from core.models import get_request_username
from services.web.databus.constants import (
    ASSET_RT_FORMAT,
    CLEAN_CONFIG_JSON_CONF_KEY,
    DEFAULT_REPLICA_WRITE_STORAGE_CONFIG_KEY,
    JOIN_DATA_PHYSICAL_RT_FORMAT,
    JOIN_DATA_RT_FORMAT,
    JsonSchemaFieldType,
    SnapShotStorageChoices,
)
from services.web.databus.exceptions import SchemaEmptyError
from services.web.databus.models import Snapshot
from services.web.databus.storage.handler.redis import RedisHandler
from services.web.databus.utils import restart_bkbase_clean, start_bkbase_clean


class JoinDataEtlStorageHandler:
    def __init__(
        self,
        data_id: int,
        system: System,
        resource_type: ResourceType,
        storage_type: str,
        snapshot: Snapshot = None,
    ):
        self.data_id = data_id
        self.system = system
        self.system_id = system.system_id
        self.resource_type = resource_type
        self.resource_type_id = resource_type.resource_type_id
        self.storage_type = storage_type
        self.snapshot = snapshot

    def create_clean(self, update: bool = False):
        """创建或更新清洗"""
        if update:
            # 更新清洗链路
            clean_config = self.clean_config.copy()
            clean_config["processing_id"] = self.snapshot.bkbase_processing_id
            api.bk_base.databus_cleans_put(
                clean_config,
            )
            restart_bkbase_clean(
                self.snapshot.bkbase_table_id, self.snapshot.bkbase_processing_id, get_request_username()
            )
            return self.snapshot.bkbase_processing_id, self.snapshot.bkbase_table_id
        else:
            result = api.bk_base.databus_cleans_post(self.clean_config)
            start_bkbase_clean(result["result_table_id"], result["processing_id"], get_request_username())
            processing_id = result["processing_id"]
            bkbase_table_id = result["result_table_id"]
            return processing_id, bkbase_table_id

    def create_storage(self, update=False):
        """创建入库"""
        if update:
            # 更新入库
            storage_config = self.storage_config.copy()
            storage_config["result_table_id"] = self.storage_result_table_id
            api.bk_base.databus_storages_put(storage_config)
        else:
            api.bk_base.databus_storages_post(self.storage_config)

    @property
    def storage_result_table_id(self):
        result_table_id = '_'.join(
            str(item) for item in [self.storage_config['bk_biz_id'], self.storage_config['result_table_name']]
        )
        return result_table_id

    @property
    def config_name(self):
        return JOIN_DATA_RT_FORMAT.format(system_id=self.system_id, resource_type_id=self.resource_type_id).replace(
            "-", "_"
        )

    @property
    def physical_table_name(self):
        return JOIN_DATA_PHYSICAL_RT_FORMAT.format(system_id=self.system_id).replace("-", "_")

    @property
    def clean_config(self) -> dict:
        return {
            "bk_biz_id": settings.DEFAULT_BK_BIZ_ID,
            "bk_username": bk_resource_settings.PLATFORM_AUTH_ACCESS_USERNAME,
            "clean_config_name": self.config_name,
            "description": self.config_name,
            "fields": self.result_table_fields,
            "json_config": self.json_config,
            "raw_data_id": self.data_id,
            "result_table_name": self.config_name,
            "result_table_name_alias": self.config_name,
        }

    @property
    def storage_config(self):
        ret = {
            "bk_biz_id": settings.DEFAULT_BK_BIZ_ID,
            "raw_data_id": self.data_id,
            "data_type": "clean",
            "result_table_name": self.config_name,
            "result_table_name_alias": self.config_name,
            "storage_type": self.storage_type,
            "storage_cluster": self.get_storage_cluster(),
            "expires": self.get_storage_expires(),
            "fields": self.storage_fields,
            "physical_table_name": self.physical_table_name,
        }
        return ret

    def get_storage_cluster(self):
        return RedisHandler.pick_redis(self.system_id).redis_name_en

    def get_storage_expires(self):
        return settings.HTTP_PULL_REDIS_TIMEOUT

    @property
    def storage_fields(self):
        fields = copy.deepcopy(self.result_table_fields)
        for field in fields:
            field["physical_field"] = field["field_name"]
        return fields

    @property
    def result_table_fields(self):
        return [
            {
                "field_name": "utctime",
                "field_type": "string",
                "field_alias": "拉取时间",
                "is_dimension": False,
                "is_key": False,
                "field_index": 1,
            },
            {
                "field_name": "system_id",
                "field_type": "string",
                "field_alias": "系统ID",
                "is_dimension": False,
                "is_key": True,
                "field_index": 2,
            },
            {
                "field_name": "resource_type_id",
                "field_type": "string",
                "field_alias": "资源类型ID",
                "is_dimension": False,
                "is_key": True,
                "field_index": 3,
            },
            {
                "field_name": "id",
                "field_type": "string",
                "field_alias": "实例ID",
                "is_dimension": False,
                "is_key": True,
                "field_index": 4,
            },
            {
                "field_name": "display_name",
                "field_type": "string",
                "field_alias": "实例名称",
                "is_dimension": False,
                "is_key": False,
                "field_index": 5,
            },
            {
                "field_name": "creator",
                "field_type": "string",
                "field_alias": "创建人",
                "is_dimension": False,
                "is_key": False,
                "field_index": 6,
            },
            {
                "field_name": "created_at",
                "field_type": "long",
                "field_alias": "创建时间",
                "is_dimension": False,
                "is_key": False,
                "field_index": 7,
            },
            {
                "field_name": "updater",
                "field_type": "string",
                "field_alias": "更新人",
                "is_dimension": False,
                "is_key": False,
                "field_index": 8,
            },
            {
                "field_name": "updated_at",
                "field_type": "long",
                "field_alias": "更新时间",
                "is_dimension": False,
                "is_key": False,
                "field_index": 9,
            },
            {
                "field_name": "operator",
                "field_type": "string",
                "field_alias": "负责人",
                "is_dimension": False,
                "is_key": False,
                "field_index": 10,
            },
            {
                "field_name": "bk_bak_operator",
                "field_type": "string",
                "field_alias": "备份负责人",
                "is_dimension": False,
                "is_key": False,
                "field_index": 11,
            },
            {
                "field_name": "is_deleted",
                "field_type": "string",
                "field_alias": "软删除",
                "is_dimension": False,
                "is_key": False,
                "field_index": 12,
            },
            {
                "field_name": "data",
                "field_type": "text",
                "field_alias": "实例内容",
                "is_dimension": False,
                "is_key": False,
                "field_index": 13,
            },
        ]

    @property
    def json_config(self):
        config = {
            "extract": {
                "type": "fun",
                "method": "from_json",
                "result": "json_data",
                "label": "label947fd6",
                "args": [],
                "next": {
                    "type": "branch",
                    "name": "",
                    "label": None,
                    "next": [
                        {
                            "type": "assign",
                            "subtype": "assign_obj",
                            "label": "label38d38b",
                            "assign": [{"type": "string", "assign_to": "utctime", "key": "utctime"}],
                            "next": None,
                        },
                        {
                            "type": "access",
                            "subtype": "access_obj",
                            "label": "label54bcf0",
                            "key": "__system_id",
                            "result": "__system_id",
                            "default_type": "string",
                            "default_value": self.system_id,
                            "next": {
                                "type": "assign",
                                "subtype": "assign_value",
                                "label": "label85b48c",
                                "assign": {"type": "string", "assign_to": "system_id"},
                                "next": None,
                            },
                        },
                        {
                            "type": "access",
                            "subtype": "access_obj",
                            "label": "label8d5307",
                            "key": "__resource_type_id",
                            "result": "__resource_type_id",
                            "default_type": "string",
                            "default_value": self.resource_type_id,
                            "next": {
                                "type": "assign",
                                "subtype": "assign_value",
                                "label": "labeld0801e",
                                "assign": {"type": "string", "assign_to": "resource_type_id"},
                                "next": None,
                            },
                        },
                        {
                            "type": "access",
                            "subtype": "access_obj",
                            "label": "labela52a54",
                            "key": "data",
                            "result": "response_content",
                            "default_type": "null",
                            "default_value": "",
                            "next": {
                                "type": "fun",
                                "method": "from_json",
                                "result": "response_json",
                                "label": "label4c2264",
                                "args": [],
                                "next": {
                                    "type": "access",
                                    "subtype": "access_obj",
                                    "label": "label2f7109",
                                    "key": "data",
                                    "result": "response_data",
                                    "default_type": "null",
                                    "default_value": "",
                                    "next": {
                                        "type": "access",
                                        "subtype": "access_obj",
                                        "label": "labelac4cb6",
                                        "key": "results",
                                        "result": "response_ results",
                                        "default_type": "null",
                                        "default_value": "",
                                        "next": {
                                            "type": "fun",
                                            "label": "labela1f309",
                                            "result": "iter_item",
                                            "args": [],
                                            "method": "iterate",
                                            "next": {
                                                "type": "branch",
                                                "name": "",
                                                "label": None,
                                                "next": [
                                                    {
                                                        "type": "assign",
                                                        "subtype": "assign_obj",
                                                        "label": "label53e9f2",
                                                        "assign": [
                                                            {"type": "string", "assign_to": "id", "key": "id"},
                                                            {
                                                                "type": "string",
                                                                "assign_to": "display_name",
                                                                "key": "display_name",
                                                            },
                                                            {
                                                                "type": "string",
                                                                "assign_to": "creator",
                                                                "key": "creator",
                                                            },
                                                            {
                                                                "type": "long",
                                                                "assign_to": "created_at",
                                                                "key": "created_at",
                                                            },
                                                            {
                                                                "type": "string",
                                                                "assign_to": "updater",
                                                                "key": "updater",
                                                            },
                                                            {
                                                                "type": "long",
                                                                "assign_to": "updated_at",
                                                                "key": "updated_at",
                                                            },
                                                            {
                                                                "type": "string",
                                                                "assign_to": "operator",
                                                                "key": "operator",
                                                            },
                                                            {
                                                                "type": "string",
                                                                "assign_to": "bk_bak_operator",
                                                                "key": "bk_bak_operator",
                                                            },
                                                            {
                                                                "type": "string",
                                                                "assign_to": "is_deleted",
                                                                "key": "is_deleted",
                                                            },
                                                        ],
                                                        "next": None,
                                                    },
                                                    {
                                                        "type": "assign",
                                                        "subtype": "assign_json",
                                                        "label": "labeld66836",
                                                        "assign": [
                                                            {"type": "text", "assign_to": "data", "key": "data"}
                                                        ],
                                                        "next": None,
                                                    },
                                                ],
                                            },
                                        },
                                    },
                                },
                            },
                        },
                    ],
                },
            },
            "conf": {
                "time_format": "yyyy-MM-dd HH:mm:ss",
                "timezone": 0,
                "time_field_name": "utctime",
                "output_field_name": "timestamp",
                "timestamp_len": 0,
                "encoding": "UTF-8",
            },
        }
        return json.dumps(config)


class AssetEtlStorageHandler(JoinDataEtlStorageHandler):
    KEY_BUILTIN_FIELDS = {
        "utctime",
        "system_id",
        "resource_type_id",
        "id",
        "display_name",
        "creator",
        "updater",
        "created_at",
        "updated_at",
    }

    @property
    def config_name(self) -> str:
        return ASSET_RT_FORMAT.format(system_id=self.system_id, resource_type_id=self.resource_type_id).replace(
            "-", "_"
        )

    @property
    def result_table_fields(self) -> List[dict]:
        """
        资产表的结构为标准字段+资产的字段
        """
        # 初始化标准字段
        fields = super().result_table_fields
        fields = {field["field_name"]: field for field in fields[: len(fields) - 1]}

        # 获取资产表字段
        schema_fields = self.schema_fields
        fields.update(
            {
                field["field_name"]: field
                for field in schema_fields
                if field["field_name"] not in self.KEY_BUILTIN_FIELDS
            }
        )
        return list(fields.values())

    @cached_property
    def schema_fields(self) -> List[dict]:
        """
        获取资产字段
        """
        # 获取字段列表
        schema = resource.meta.resource_type_schema(system_id=self.system_id, resource_type_id=self.resource_type_id)
        # 如果没有数据需要报错，不正常创建清洗
        if not schema:
            raise SchemaEmptyError()
        fields = [
            {
                "field_name": field["id"],
                "field_type": JsonSchemaFieldType.get_bkbase_field_type(field["type"]),
                "field_alias": field["description"] or field["id"],
                "is_dimension": False,
                "is_key": False,
                "field_index": index,
                "is_json": field["type"] in [JsonSchemaFieldType.OBJECT.value, JsonSchemaFieldType.ARRAY.value],
                "is_original_json": field["type"] in [JsonSchemaFieldType.JSON.value],
                "is_index": field.get("is_index", False),
            }
            for index, field in enumerate(schema)
        ]
        return fields

    def get_asset_uniq_fields(self, is_json: bool = None) -> List[dict]:
        """
        获取资产唯一字段
        """
        # 关键标准字段，无法覆盖
        build_in_field_names = self.KEY_BUILTIN_FIELDS
        # 资产字段
        schema_fields = self.schema_fields
        return [
            f
            for f in schema_fields
            if f["field_name"] not in build_in_field_names
            and (is_json is None or any([f["is_json"], f["is_original_json"]]) == is_json)
        ]

    @property
    def storage_config(self):
        config = super().storage_config
        config.pop("physical_table_name", "")
        config.update(
            {
                "config": {"dimension_table": True},
                "index_fields": [
                    {"index": 0, "physical_field": "id"},
                    {"index": 0, "physical_field": "resource_type_id"},
                    {"index": 0, "physical_field": "system_id"},
                ],
            }
        )
        if self.storage_type == StorageType.DORIS:
            config["config"] = {"data_model": "primary_table", "is_profiling": False}
        return config

    def get_storage_cluster(self):
        if self.storage_type == SnapShotStorageChoices.DORIS.value:
            replica_config = GlobalMetaConfig.get(
                DEFAULT_REPLICA_WRITE_STORAGE_CONFIG_KEY,
                config_level=ConfigLevelChoices.NAMESPACE.value,
                instance_key=settings.DEFAULT_NAMESPACE,
            )
            replica_default_bkbase_cluster_id = replica_config["bkbase_cluster_id"]
            return replica_default_bkbase_cluster_id
        else:
            return settings.ASSET_RT_STORAGE_CLUSTER

    def get_storage_expires(self):
        return settings.ASSET_RT_EXPIRE_TIME

    @property
    def json_config(self):
        config = {
            "extract": {
                "type": "fun",
                "method": "from_json",
                "result": "json_data",
                "label": "label947fd6",
                "args": [],
                "next": {
                    "type": "branch",
                    "name": "",
                    "label": None,
                    "next": [
                        {
                            "type": "assign",
                            "subtype": "assign_obj",
                            "label": "label38d38b",
                            "assign": [{"type": "string", "assign_to": "utctime", "key": "utctime"}],
                            "next": None,
                        },
                        {
                            "type": "access",
                            "subtype": "access_obj",
                            "label": "label54bcf0",
                            "key": "__system_id",
                            "result": "__system_id",
                            "default_type": "string",
                            "default_value": self.system_id,
                            "next": {
                                "type": "assign",
                                "subtype": "assign_value",
                                "label": "label85b48c",
                                "assign": {"type": "string", "assign_to": "system_id"},
                                "next": None,
                            },
                        },
                        {
                            "type": "access",
                            "subtype": "access_obj",
                            "label": "label8d5307",
                            "key": "__resource_type_id",
                            "result": "__resource_type_id",
                            "default_type": "string",
                            "default_value": self.resource_type_id,
                            "next": {
                                "type": "assign",
                                "subtype": "assign_value",
                                "label": "labeld0801e",
                                "assign": {"type": "string", "assign_to": "resource_type_id"},
                                "next": None,
                            },
                        },
                        {
                            "type": "access",
                            "subtype": "access_obj",
                            "label": "labela52a54",
                            "key": "data",
                            "result": "response_content",
                            "default_type": "null",
                            "default_value": "",
                            "next": {
                                "type": "fun",
                                "method": "from_json",
                                "result": "response_json",
                                "label": "label4c2264",
                                "args": [],
                                "next": {
                                    "type": "access",
                                    "subtype": "access_obj",
                                    "label": "label2f7109",
                                    "key": "data",
                                    "result": "response_data",
                                    "default_type": "null",
                                    "default_value": "",
                                    "next": {
                                        "type": "access",
                                        "subtype": "access_obj",
                                        "label": "labelac4cb6",
                                        "key": "results",
                                        "result": "response_results",
                                        "default_type": "null",
                                        "default_value": "",
                                        "next": {
                                            "type": "fun",
                                            "label": "labela1f309",
                                            "result": "iter_item",
                                            "args": [],
                                            "method": "iterate",
                                            "next": {
                                                "type": "branch",
                                                "name": "",
                                                "label": None,
                                                "next": [
                                                    {
                                                        "type": "assign",
                                                        "subtype": "assign_obj",
                                                        "label": "label53e9f2",
                                                        "assign": [
                                                            item
                                                            for item in [
                                                                {"type": "string", "assign_to": "id", "key": "id"},
                                                                {
                                                                    "type": "string",
                                                                    "assign_to": "display_name",
                                                                    "key": "display_name",
                                                                },
                                                                {
                                                                    "type": "string",
                                                                    "assign_to": "creator",
                                                                    "key": "creator",
                                                                },
                                                                {
                                                                    "type": "long",
                                                                    "assign_to": "created_at",
                                                                    "key": "created_at",
                                                                },
                                                                {
                                                                    "type": "string",
                                                                    "assign_to": "updater",
                                                                    "key": "updater",
                                                                },
                                                                {
                                                                    "type": "long",
                                                                    "assign_to": "updated_at",
                                                                    "key": "updated_at",
                                                                },
                                                                {
                                                                    "type": "string",
                                                                    "assign_to": "operator",
                                                                    "key": "operator",
                                                                },
                                                                {
                                                                    "type": "string",
                                                                    "assign_to": "bk_bak_operator",
                                                                    "key": "bk_bak_operator",
                                                                },
                                                                {
                                                                    "type": "string",
                                                                    "assign_to": "is_deleted",
                                                                    "key": "is_deleted",
                                                                },
                                                            ]
                                                            if item["key"] in self.KEY_BUILTIN_FIELDS
                                                            or (
                                                                item["key"]
                                                                not in {
                                                                    field["field_name"] for field in self.schema_fields
                                                                }
                                                            )
                                                        ],
                                                        "next": None,
                                                    },
                                                    {
                                                        "type": "access",
                                                        "subtype": "access_obj",
                                                        "label": "label00001",
                                                        "key": "data",
                                                        "result": "iter_item_data",
                                                        "default_type": "null",
                                                        "default_value": "",
                                                        "next": {
                                                            "type": "branch",
                                                            "name": "",
                                                            "label": None,
                                                            "next": [
                                                                {
                                                                    "type": "assign",
                                                                    "subtype": "assign_obj",
                                                                    "label": "label00002",
                                                                    "assign": [
                                                                        {
                                                                            "type": field["field_type"],
                                                                            "assign_to": field["field_name"],
                                                                            "key": field["field_name"],
                                                                        }
                                                                        for field in self.get_asset_uniq_fields(
                                                                            is_json=False
                                                                        )
                                                                    ],
                                                                    "next": None,
                                                                },
                                                                {
                                                                    "type": "assign",
                                                                    "subtype": "assign_json",
                                                                    "label": "label00003",
                                                                    "assign": [
                                                                        {
                                                                            "type": field["field_type"],
                                                                            "assign_to": field["field_name"],
                                                                            "key": field["field_name"],
                                                                        }
                                                                        for field in self.get_asset_uniq_fields(
                                                                            is_json=True
                                                                        )
                                                                    ],
                                                                    "next": None,
                                                                },
                                                            ],
                                                        },
                                                    },
                                                ],
                                            },
                                        },
                                    },
                                },
                            },
                        },
                    ],
                },
            },
            "conf": {
                "time_format": "yyyy-MM-dd HH:mm:ss",
                "timezone": 0,
                "time_field_name": "utctime",
                "output_field_name": "timestamp",
                "timestamp_len": 0,
                "encoding": "UTF-8",
            },
        }
        return json.dumps(self.update_json_conf(config))

    def update_json_conf(self, config: dict) -> dict:
        """
        使用 Snapshot 自定义配置覆盖清洗 conf
        """
        if not self.snapshot or not self.snapshot.custom_config:
            return config
        conf_patch = self.snapshot.custom_config.get(CLEAN_CONFIG_JSON_CONF_KEY)
        if isinstance(conf_patch, dict):
            config.setdefault("conf", {})
            config["conf"].update(conf_patch)
        return config

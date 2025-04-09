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
from typing import List, Optional, Tuple

from bk_resource import api, resource
from bk_resource.settings import bk_resource_settings
from bk_resource.utils.common_utils import uniqid
from django.conf import settings
from django.utils.translation import gettext

from apps.meta.constants import ConfigLevelChoices
from apps.meta.models import GlobalMetaConfig
from apps.meta.utils.fields import (
    BKBASE_STORAGE_UNIQUE_KEYS,
    BKDATA_ES_TYPE_MAP,
    DYNAMIC_JSON_FIELDS,
    EXT_FIELD_CONFIG,
    FIELD_TYPE_OBJECT,
    FIELD_TYPE_STRING,
    REPORT_TIME,
    STANDARD_FIELDS,
    START_TIME,
    VERSION_ID,
)
from services.web.databus.constants import (
    DEFAULT_REPLICA_WRITE_STORAGE_CONFIG_KEY,
    DEFAULT_STORAGE_CONFIG_KEY,
    DEFAULT_TIME_FORMAT,
    DEFAULT_TIME_LEN,
    DEFAULT_TIME_ZONE,
    REPLICA_WRITE_INDEX_SET_CONFIG_KEY,
    REPLICA_WRITE_INDEX_SET_ID,
)
from services.web.databus.exceptions import MultiOrNoneRawDataError
from services.web.databus.models import CollectorPlugin
from services.web.databus.utils import restart_bkbase_clean, start_bkbase_clean


class PluginEtlHandler:
    def __init__(self, collector_plugin_id: int):
        self.plugin = CollectorPlugin.objects.get(collector_plugin_id=collector_plugin_id)
        self.bkbase_labels = []

    def create_or_update(self) -> None:
        self.create_or_update_clean()
        self.create_or_update_storage()

    def create_or_update_storage(self) -> None:
        main_storage_params, replica_storage_params = self.build_storage_config()
        # 创建合流入库物理表名
        table_id = f"{settings.DEFAULT_BK_BIZ_ID}_{self.get_table_id()}"
        main_storage_params["physical_table_name"] = f"write_{{yyyyMMdd}}_{table_id}"

        # 创建入库
        if not self.plugin.has_storage:
            api.bk_base.databus_storages_post(main_storage_params)
            self.plugin.has_storage = True
            self.plugin.save(update_fields=["has_storage"])
        # 更新入库
        else:
            main_storage_params.update({"result_table_id": self.plugin.bkbase_table_id})
            api.bk_base.databus_storages_put(main_storage_params)

        if replica_storage_params:
            if not self.plugin.has_replica_storage:
                api.bk_base.databus_storages_post(replica_storage_params)
                self.plugin.has_replica_storage = True
                self.plugin.save(update_fields=["has_replica_storage"])
            else:
                replica_storage_params.update({"result_table_id": self.plugin.bkbase_table_id})
                api.bk_base.databus_storages_put(replica_storage_params)

            replica_storage_params["bkbase_result_table_id"] = self.plugin.build_result_table_id(
                replica_storage_params["bk_biz_id"], self.plugin.collector_plugin_name_en
            )
            GlobalMetaConfig.set(
                REPLICA_WRITE_INDEX_SET_CONFIG_KEY,
                replica_storage_params,
                config_level=ConfigLevelChoices.NAMESPACE.value,
                instance_key=self.plugin.namespace,
            )
            GlobalMetaConfig.set(
                REPLICA_WRITE_INDEX_SET_ID,
                replica_storage_params["bkbase_result_table_id"],
                config_level=ConfigLevelChoices.NAMESPACE.value,
                instance_key=self.plugin.namespace,
            )

    def create_or_update_clean(self) -> None:
        bkbase_params = self.build_clean_config()
        # 更新
        if self.plugin.bkbase_table_id:
            bkbase_params.update({"processing_id": self.plugin.bkbase_processing_id})
            api.bk_base.databus_cleans_put(bkbase_params)
            restart_bkbase_clean(self.plugin.bkbase_table_id, self.plugin.bkbase_processing_id)
        # 创建
        else:
            result = api.bk_base.databus_cleans_post(bkbase_params)
            start_bkbase_clean(result["result_table_id"], self.plugin.bkbase_processing_id)
            self.plugin.bkbase_processing_id = result["processing_id"]
            self.plugin.bkbase_table_id = result["result_table_id"]
            self.plugin.save(update_fields=["bkbase_processing_id", "bkbase_table_id"])

    def get_config_name(self) -> str:
        return self.plugin.collector_plugin_name_en.lower()

    def get_table_id(self) -> str:
        return "bklog_{}".format(self.plugin.collector_plugin_name_en.lower())

    def build_clean_config(self) -> dict:
        config = {
            "bk_biz_id": settings.DEFAULT_BK_BIZ_ID,
            "bk_username": bk_resource_settings.PLATFORM_AUTH_ACCESS_USERNAME,
            "clean_config_name": self.get_config_name(),
            "description": self.get_config_name(),
            "fields": self.get_fields(),
            "json_config": self.get_config(),
            "raw_data_id": self.get_bk_data_id(),
            "result_table_name": self.get_table_id(),
            "result_table_name_alias": self.get_table_id(),
        }
        return config

    def build_storage_config(self) -> Tuple[dict, Optional[dict]]:
        # 主存储入库参数
        main_default_cluster_id = int(
            GlobalMetaConfig.get(
                DEFAULT_STORAGE_CONFIG_KEY,
                config_level=ConfigLevelChoices.NAMESPACE.value,
                instance_key=self.plugin.namespace,
            )
        )
        clusters = resource.databus.storage.storage_list(namespace=self.plugin.namespace)
        for item in clusters:
            if item["cluster_config"]["cluster_id"] == main_default_cluster_id:
                cluster_info = item
        bkbase_cluster_id = cluster_info["cluster_config"].get("custom_option", {})["bkbase_cluster_id"]
        # 更新入库字段
        es_fields = self.get_es_fields()
        # 获取主存储入库参数（目前为ES）
        main_storage_params = {
            "bk_biz_id": settings.DEFAULT_BK_BIZ_ID,
            "raw_data_id": self.get_bk_data_id(),
            "data_type": "clean",
            "result_table_name": self.get_table_id(),
            "result_table_name_alias": self.get_table_id(),
            "storage_type": "es",
            "storage_cluster": bkbase_cluster_id,
            "expires": "7d",  # 无效，实际由metadata控制
            "fields": es_fields,
            "config": {"has_unique_key": True},
            "from_raw_data": False,
        }

        # 双写存储入库参数
        replica_config = GlobalMetaConfig.get(
            DEFAULT_REPLICA_WRITE_STORAGE_CONFIG_KEY,
            config_level=ConfigLevelChoices.NAMESPACE.value,
            instance_key=self.plugin.namespace,
            default=None,
        )
        replica_default_cluster_id = replica_config["cluster_id"]
        replica_default_bkbase_cluster_id = replica_config["bkbase_cluster_id"]
        # 更新入库字段
        replica_fields = self.get_doris_fields()
        for field in replica_fields:
            field["physical_field"] = field["field_name"]
            # 计算平台无法识别 is_dimension 配置，使用 is_doc_values 配置
            field["is_doc_values"] = field.get("is_dimension", False)
        # 获取双写存储入库参数（目前为Doris

        if not replica_default_cluster_id:
            replica_storage_params = {}
        else:
            replica_storage_params = {
                "bk_biz_id": settings.DEFAULT_BK_BIZ_ID,
                "raw_data_id": self.get_bk_data_id(),
                "data_type": "clean",
                "result_table_name": self.get_table_id(),
                "result_table_name_alias": self.get_table_id(),
                "storage_type": "doris",
                "storage_cluster": replica_default_bkbase_cluster_id,
                "expires": "365d",  # 无效，实际由metadata控制
                "fields": replica_fields,
                "config": {"dimension_table": False, "data_model": "duplicate_table", "is_profiling": False},
            }
        return main_storage_params, replica_storage_params

    @classmethod
    def get_fields(cls) -> List[dict]:
        fields = cls.get_build_in_fields()
        fields.extend(
            [
                {
                    "field_name": field.field_name,
                    "field_type": BKDATA_ES_TYPE_MAP.get(field.field_type, FIELD_TYPE_STRING),
                    "field_alias": str(field.description or field.alias_name or field.field_name),
                    "is_dimension": field.is_dimension,
                    "field_index": index,
                    "is_json": field.is_json,
                    "is_key": bool(field.field_name in BKBASE_STORAGE_UNIQUE_KEYS),
                    "__field_type": field.field_type,
                }
                for index, field in enumerate([*STANDARD_FIELDS, EXT_FIELD_CONFIG])
                if field.field_name not in [REPORT_TIME.field_name, VERSION_ID.field_name]
            ]
        )
        fields.extend(
            [
                {
                    "field_name": "log",
                    "field_type": "text",
                    "field_alias": gettext("原始日志"),
                    "is_dimension": False,
                    "field_index": 1,
                },
                {
                    "field_name": "iterationIndex",
                    "field_type": "long",
                    "field_alias": gettext("迭代ID"),
                    "is_dimension": False,
                    "field_index": 2,
                },
            ]
        )
        # 需要使用确定的FieldIndex避免合流失败
        return [{**field, "field_index": index} for index, field in enumerate(fields, 1)]

    @classmethod
    def get_es_fields(cls) -> List[dict]:
        fields = cls.get_fields()
        es_not_json_field_names = {field.field_name for field in DYNAMIC_JSON_FIELDS}
        for field in fields:
            field["physical_field"] = field["field_name"]
            # 计算平台无法识别 is_dimension 配置，使用 is_doc_values 配置
            field["is_doc_values"] = field.get("is_dimension", False)
            if field["field_name"] in es_not_json_field_names:
                field["is_json"] = False
        return fields

    @classmethod
    def get_doris_fields(cls) -> List[dict]:
        fields = cls.get_fields()
        extra_info = {}
        for field in [*STANDARD_FIELDS, EXT_FIELD_CONFIG]:
            extra_info[field.field_name] = {'is_index': field.is_index, 'is_zh_analyzed': field.is_zh_analyzed}
        dynamic_json_fields = {field.field_name for field in DYNAMIC_JSON_FIELDS}
        for field in fields:
            if field["field_name"] in extra_info:
                field.update(extra_info[field["field_name"]])
            if field["field_name"] in ('log',):
                field["is_zh_analyzed"] = True
            if field.get('is_zh_analyzed'):
                field.pop("is_analyzed", None)
            # 在计算平台支持标准json类型之前，is_json置为False防止创建variant类型
            if field["field_name"] in dynamic_json_fields:
                field["is_json"] = False
        return fields

    @classmethod
    def get_build_in_fields(cls) -> List[dict]:
        fields = [
            {
                "field_name": "cloudId",
                "field_type": "int",
                "field_alias": gettext("云区域ID"),
                "is_dimension": True,
                "field_index": 5,
                "option": {"path": "cloudid"},
            },
            {
                "field_name": "serverIp",
                "field_type": "string",
                "field_alias": gettext("ip"),
                "is_dimension": True,
                "field_index": 6,
                "option": {"path": "ip"},
            },
            {
                "field_name": "path",
                "field_type": "string",
                "field_alias": gettext("日志路径"),
                "is_dimension": True,
                "field_index": 7,
                "option": {"path": "filename"},
            },
            {
                "field_name": "gseIndex",
                "field_type": "long",
                "field_alias": gettext("gse索引"),
                "field_index": 8,
                "is_dimension": True,
                "option": {"path": "gseindex"},
            },
            {
                "field_name": "time",
                "field_type": "long",
                "field_alias": gettext("time"),
                "is_dimension": True,
                "field_index": 9,
                "option": {"path": "time"},
            },
            {
                "field_name": REPORT_TIME.field_name,
                "field_type": REPORT_TIME.field_type,
                "field_alias": str(REPORT_TIME.description),
                "is_dimension": REPORT_TIME.is_dimension,
                "field_index": 10,
                "option": {"path": "time"},
            },
        ]
        return fields

    def get_bk_data_id(self) -> int:
        resp = api.bk_base.get_rawdata_list(
            bk_biz_id=settings.DEFAULT_BK_BIZ_ID, raw_data_name__icontains=self.plugin.collector_plugin_name_en
        )
        # 非一条数据则表示没有匹配上，需要报错提示
        if len(resp) != 1:
            raise MultiOrNoneRawDataError()
        return resp[0]["id"]

    def get_label(self) -> str:
        label = "label{}".format(uniqid()[:5])
        if label in self.bkbase_labels:
            return self.get_label()
        self.bkbase_labels.append(label)
        return label

    def assign_bkbase(self, field: dict) -> dict:
        return {"type": field["field_type"], "assign_to": field["field_name"], "key": field["field_name"]}

    def get_config(self) -> str:
        config = {
            "extract": {
                "type": "fun",
                "method": "from_json",
                "result": "json_data",
                "label": self.get_label(),
                "args": [],
                "next": {
                    "type": "branch",
                    "name": "",
                    "label": None,
                    "next": [
                        # 赋值非JSON内容
                        {
                            "type": "assign",
                            "subtype": "assign_obj",
                            "label": self.get_label(),
                            "assign": self.assign_normal_fields(),
                            "next": None,
                        },
                        # 赋值JSON内容
                        {
                            "type": "assign",
                            "subtype": "assign_json",
                            "label": self.get_label(),
                            "assign": self.assign_json_fields(),
                            "next": None,
                        },
                    ],
                },
            },
            "conf": {
                "time_format": DEFAULT_TIME_FORMAT,
                "timezone": DEFAULT_TIME_ZONE,
                "time_field_name": START_TIME.field_name,
                "output_field_name": "timestamp",
                "timestamp_len": DEFAULT_TIME_LEN,
                "encoding": "UTF-8",
            },
        }
        return json.dumps(config)

    def assign_normal_fields(self) -> List[dict]:
        fields = []
        for field in self.get_fields():
            if field.get("__field_type") != FIELD_TYPE_OBJECT:
                fields.append(self.assign_bkbase(field))
        return fields

    def assign_json_fields(self) -> List[dict]:
        fields = []
        for field in self.get_fields():
            if field.get("__field_type") == FIELD_TYPE_OBJECT:
                fields.append(self.assign_bkbase(field))
        return fields

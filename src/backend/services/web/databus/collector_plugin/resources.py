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
from typing import List

from bk_resource import api, resource
from bk_resource.contrib.model import ModelResource
from blueapps.utils.unique import uniqid
from django.conf import settings
from django.utils.translation import gettext, gettext_lazy

from api.bk_log.constants import INDEX_SET_ID
from apps.audit.resources import AuditMixinResource
from apps.exceptions import MetaConfigNotExistException
from apps.meta.constants import ConfigLevelChoices
from apps.meta.models import GlobalMetaConfig
from services.web.databus.collector_plugin.serializers import (
    CreatePluginRequestSerializer,
    CreatePluginResponseSerializer,
    PluginListResponseSerializer,
    UpdatePluginRequestSerializer,
)
from services.web.databus.constants import (
    BKLOG_INDEX_SET_SCENARIO_ID,
    COLLECTOR_PLUGIN_ID,
    DEFAULT_CATEGORY_ID,
    DEFAULT_COLLECTOR_SCENARIO,
    DEFAULT_DATA_ENCODING,
    DEFAULT_ETL_PROCESSOR,
    DEFAULT_STORAGE_CONFIG_KEY,
    DEFAULT_TIME_ZONE,
    EMPTY_INDEX_SET_ID,
    EMPTY_TABLE_ID,
    INDEX_SET_CONFIG_KEY,
    INDEX_SET_NAME_FORMAT,
    TRANSFER_TIME_FORMAT,
    PluginSceneChoices,
)
from services.web.databus.models import CollectorPlugin
from services.web.databus.storage.handler.es import StorageConfig
from services.web.databus.tasks import create_or_update_plugin_etl


class PluginBaseResource(AuditMixinResource, abc.ABC):
    tags = ["CollectorPlugin"]

    def build_in_config(self, namespace: str, extra_fields: List[dict] = None):
        now = datetime.datetime.now()
        uniq = str(uniqid())[:10].upper()
        fields = resource.meta.get_standard_fields(is_etl=False)
        # 兼容BkBase
        fields.append(
            {
                "field_name": "_iteration_idx",
                "field_type": "long",
                "alias_name": "_iteration_idx",
                "is_text": False,
                "is_time": False,
                "is_json": False,
                "is_analyzed": False,
                "is_dimension": True,
                "is_delete": False,
                "is_required": False,
                "is_display": False,
                "is_built_in": True,
                "option": {},
                "description": gettext("迭代ID"),
                "priority_index": 100,
            }
        )
        fields.extend(extra_fields or [])
        # time
        for field in fields:
            field["field_type"] = field["option"].get("meta_field_type") or field["field_type"]
            field["option"] = {key: val for key, val in field.get("option", {}).items() if key.startswith("es")}
            if not field["is_time"]:
                continue
            field["option"].update({"time_zone": DEFAULT_TIME_ZONE, "time_format": TRANSFER_TIME_FORMAT})
        # field name uniq
        _fields = []
        _field_names = []
        for field in fields:
            if field["field_name"] in _field_names:
                continue
            _field_names.append(field["field_name"])
            _fields.append(field)
        fields = _fields
        # 获取集群信息
        cluster_id = int(
            GlobalMetaConfig.get(
                DEFAULT_STORAGE_CONFIG_KEY, config_level=ConfigLevelChoices.NAMESPACE.value, instance_key=namespace
            )
        )
        (
            retention,
            replicas,
            allocation_min_days,
            storage_shards_nums,
            storage_shards_size,
        ) = StorageConfig.get_default(namespace, cluster_id)
        return {
            "bk_biz_id": settings.DEFAULT_BK_BIZ_ID,
            "bkdata_biz_id": settings.DEFAULT_BK_BIZ_ID,
            "collector_plugin_name_en": f"BKAudit_Plugin_{now.strftime('%Y%m%d')}_{uniq}",
            "collector_plugin_name": f"{gettext('审计中心采集插件')}({now.strftime('%Y%m%d%H%M%S')})",
            "collector_scenario_id": DEFAULT_COLLECTOR_SCENARIO,
            "description": gettext("审计中心采集插件"),
            "category_id": DEFAULT_CATEGORY_ID,
            "data_encoding": DEFAULT_DATA_ENCODING,
            "is_create_public_data_id": True,
            "is_display_collector": False,
            "is_allow_alone_data_id": True,
            "is_allow_alone_etl_config": True,
            "is_allow_alone_storage": False,
            "etl_processor": DEFAULT_ETL_PROCESSOR,
            "storage_cluster_id": cluster_id,
            "fields": fields,
            "index_settings": {
                "analysis": {
                    "analyzer": {
                        "delimiter_analyzer": {
                            "type": "custom",
                            "tokenizer": "delimiter_tokenizer",
                            "filter": ["lowercase", "trim"],
                        }
                    },
                    "tokenizer": {"delimiter_tokenizer": {"type": "char_group", "tokenize_on_chars": [",", "|"]}},
                }
            },
            "retention": retention,
            "allocation_min_days": allocation_min_days,
            "storage_replies": replicas,
            "storage_shards_nums": storage_shards_nums,
            "storage_shards_size": storage_shards_size,
        }

    def set_default(self, validated_request_data: dict, resp: dict, namespace: str):
        if validated_request_data["is_default"]:
            GlobalMetaConfig.set(
                COLLECTOR_PLUGIN_ID,
                resp["collector_plugin_id"],
                config_level=ConfigLevelChoices.NAMESPACE.value,
                instance_key=namespace,
            )


class CreatePluginResource(PluginBaseResource):
    name = gettext_lazy("创建采集插件")
    RequestSerializer = CreatePluginRequestSerializer
    serializer_class = CreatePluginResponseSerializer

    def replace_index_set(self, validated_request_data):
        bk_biz_id = settings.DEFAULT_BK_BIZ_ID
        result_table_id = CollectorPlugin.make_table_id(bk_biz_id, validated_request_data["collector_plugin_name_en"])
        params = {
            "index_set_name": INDEX_SET_NAME_FORMAT.format(namespace=validated_request_data["namespace"]),
            "bk_biz_id": bk_biz_id,
            "bk_app_code": settings.APP_CODE,
            "view_roles": [],
            "scenario_id": BKLOG_INDEX_SET_SCENARIO_ID,
            "category_id": validated_request_data["category_id"],
            "indexes": [
                {
                    "bk_biz_id": bk_biz_id,
                    "result_table_id": result_table_id,
                    "result_table_name_alias": result_table_id,
                    "permission": {"manage_collection": True},
                }
            ],
        }
        try:
            index_set_config = GlobalMetaConfig.get(
                INDEX_SET_CONFIG_KEY,
                config_level=ConfigLevelChoices.NAMESPACE.value,
                instance_key=validated_request_data["namespace"],
            )
            params["indexes"].extend(index_set_config["indexes"])
        except MetaConfigNotExistException:
            pass
        resp = api.bk_log.index_set_replace(**params)
        GlobalMetaConfig.set(
            INDEX_SET_CONFIG_KEY,
            params,
            config_level=ConfigLevelChoices.NAMESPACE.value,
            instance_key=validated_request_data["namespace"],
        )
        GlobalMetaConfig.set(
            INDEX_SET_ID,
            resp["index_set_id"],
            config_level=ConfigLevelChoices.NAMESPACE.value,
            instance_key=validated_request_data["namespace"],
        )

    def perform_request(self, validated_request_data):
        # 格式化数据
        namespace = validated_request_data["namespace"]
        validated_request_data.update(self.build_in_config(namespace, validated_request_data.pop("extra_fields", [])))

        # 创建采集插件
        resp = api.bk_log.create_collector_plugin(**validated_request_data)

        # todo: IndexSet相关信息应当在创建bkbase etl的时候创建设置，而不是在创建采集插件的时候创建。需要日志平台支持。

        # 存入数据库
        CollectorPlugin.objects.create(
            namespace=namespace,
            collector_plugin_id=resp["collector_plugin_id"],
            collector_plugin_name_en=validated_request_data["collector_plugin_name_en"],
            collector_plugin_name=validated_request_data["collector_plugin_name"],
            bkdata_biz_id=settings.DEFAULT_BK_BIZ_ID,
            table_id=EMPTY_TABLE_ID,
            index_set_id=EMPTY_INDEX_SET_ID,
            etl_config=validated_request_data["etl_config"],
            etl_params=validated_request_data["etl_params"],
            retention=validated_request_data["retention"],
            allocation_min_days=validated_request_data["allocation_min_days"],
            storage_replies=validated_request_data["storage_replies"],
            storage_shards_nums=validated_request_data["storage_shards_nums"],
            storage_shards_size=validated_request_data["storage_shards_size"],
            plugin_scene=validated_request_data["plugin_scene"],
        )

        # 设置默认
        self.set_default(validated_request_data, resp, namespace)

        # 仅在采集项时需要
        if validated_request_data["plugin_scene"] == PluginSceneChoices.COLLECTOR.value:
            self.replace_index_set(validated_request_data)

        # 响应
        return resp


class UpdatePluginResource(PluginBaseResource):
    name = gettext_lazy("更新采集插件")
    RequestSerializer = UpdatePluginRequestSerializer
    serializer_class = CreatePluginResponseSerializer

    def perform_request(self, validated_request_data):
        # 获取实例
        instance = CollectorPlugin.objects.get(collector_plugin_id=validated_request_data["collector_plugin_id"])
        validated_request_data.update(
            self.build_in_config(instance.namespace, validated_request_data.pop("extra_fields", instance.extra_fields))
        )
        validated_request_data.update(
            {
                "collector_plugin_name_en": instance.collector_plugin_name_en,
                "collector_plugin_name": instance.collector_plugin_name,
                "storage_cluster_id": int(
                    GlobalMetaConfig.get(
                        DEFAULT_STORAGE_CONFIG_KEY,
                        config_level=ConfigLevelChoices.NAMESPACE.value,
                        instance_key=instance.namespace,
                    )
                ),
            }
        )

        # 更新
        resp = api.bk_log.update_collector_plugin(**validated_request_data)

        # 存入数据库
        CollectorPlugin.objects.filter(collector_plugin_id=instance.collector_plugin_id).update(
            etl_config=validated_request_data["etl_config"],
            etl_params=validated_request_data["etl_params"],
            retention=validated_request_data["retention"],
            allocation_min_days=validated_request_data["allocation_min_days"],
            storage_replies=validated_request_data["storage_replies"],
            storage_shards_nums=validated_request_data["storage_shards_nums"],
            storage_shards_size=validated_request_data["storage_shards_size"],
        )

        # 设置默认
        self.set_default(validated_request_data, resp, instance.namespace)

        # 启动RT更新
        create_or_update_plugin_etl.delay(collector_plugin_id=instance.collector_plugin_id)

        # 响应
        return resp


class GetPluginListResource(ModelResource, PluginBaseResource):
    name = gettext_lazy("采集插件列表")
    model = CollectorPlugin
    action = "list"
    filter_fields = ["namespace"]
    serializer_class = PluginListResponseSerializer

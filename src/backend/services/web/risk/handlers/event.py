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

import datetime
import os

from bk_resource import api, resource
from bk_resource.utils.common_utils import uniqid
from blueapps.utils.logger import logger
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext

from apps.exceptions import MetaConfigNotExistException
from apps.meta.constants import ConfigLevelChoices, EtlConfigEnum
from apps.meta.models import GlobalMetaConfig
from core.utils.retry import FuncRunner
from services.web.databus.constants import (
    DEFAULT_CATEGORY_ID,
    DEFAULT_COLLECTOR_SCENARIO,
    DEFAULT_DATA_ENCODING,
    DEFAULT_ETL_PROCESSOR,
    DEFAULT_STORAGE_CONFIG_KEY,
    EMPTY_INDEX_SET_ID,
    EMPTY_TABLE_ID,
    PluginSceneChoices,
)
from services.web.databus.models import CollectorPlugin
from services.web.databus.storage.handler.es import StorageConfig
from services.web.query.utils.elastic import ElasticHandler
from services.web.query.utils.formatter import HitsFormatter
from services.web.risk.constants import (
    BKAUDIT_EVENT_RT_INDEX_NAME_FORMAT,
    BKAUDIT_EVENT_RT_INDEX_SET_ID,
    BULK_ADD_EVENT_SIZE,
    EVENT_ES_CLUSTER_ID_KEY,
    INDEX_TIME_FORMAT,
    RISK_SYNC_SCROLL,
    WRITE_INDEX_FORMAT,
    EventMappingFields,
)


class EventHandler(ElasticHandler):
    """
    Event
    """

    def __init__(self):
        try:
            cluster_id = GlobalMetaConfig.get(EVENT_ES_CLUSTER_ID_KEY)
        except MetaConfigNotExistException:
            cluster_id = GlobalMetaConfig.get(
                DEFAULT_STORAGE_CONFIG_KEY,
                config_level=ConfigLevelChoices.NAMESPACE.value,
                instance_key=settings.DEFAULT_NAMESPACE,
            )
            GlobalMetaConfig.set(EVENT_ES_CLUSTER_ID_KEY, cluster_id)
        super().__init__(cluster_id=cluster_id)

    @transaction.atomic()
    def update_or_create_rt(self) -> None:
        # 获取结果表
        collector_plugin = CollectorPlugin.objects.filter(plugin_scene=PluginSceneChoices.EVENT.value).first()
        if collector_plugin is not None:
            self.update_result_table(collector_plugin)
            return
        self.create_result_table()

    @transaction.atomic()
    def create_result_table(self) -> None:
        params = self._build_plugin_params()
        # 创建采集项
        resp = api.bk_log.create_collector_plugin(**params)
        # 存入数据库
        collector_plugin = CollectorPlugin.objects.create(
            namespace=settings.DEFAULT_NAMESPACE,
            collector_plugin_id=resp["collector_plugin_id"],
            collector_plugin_name_en=params["collector_plugin_name_en"],
            collector_plugin_name=params["collector_plugin_name"],
            bkdata_biz_id=settings.DEFAULT_BK_BIZ_ID,
            table_id=EMPTY_TABLE_ID,
            index_set_id=EMPTY_INDEX_SET_ID,
            etl_config=EtlConfigEnum.BK_LOG_JSON.value,
            etl_params={},
            retention=params["retention"],
            allocation_min_days=params["allocation_min_days"],
            storage_replies=params["storage_replies"],
            storage_shards_nums=params["storage_shards_nums"],
            storage_shards_size=params["storage_shards_size"],
            plugin_scene=PluginSceneChoices.EVENT.value,
        )
        # 创建索引集
        self.create_index_set(collector_plugin, BKAUDIT_EVENT_RT_INDEX_NAME_FORMAT)
        GlobalMetaConfig.set(config_key=BKAUDIT_EVENT_RT_INDEX_SET_ID, config_value=collector_plugin.index_set_id)

    @transaction.atomic()
    def update_result_table(self, collector_plugin: CollectorPlugin) -> None:
        params = self._build_plugin_params(collector_plugin)
        api.bk_log.update_collector_plugin(**params)
        # 存入数据库
        update_fields = [
            "retention",
            "allocation_min_days",
            "storage_replies",
            "storage_shards_nums",
            "storage_shards_size",
        ]
        for key in update_fields:
            setattr(collector_plugin, key, params[key])
        collector_plugin.save(update_fields=update_fields)

    def _build_plugin_params(self, collector_plugin: CollectorPlugin = None) -> dict:
        # 通用参数默认每次都会更新，特有的参数在更新时获取采集插件的
        fields = [field.to_json() for field in EventMappingFields().fields]
        for field in fields:
            if field["option"].get("meta_field_type"):
                field["field_type"] = field["option"]["meta_field_type"]
        now = datetime.datetime.now()
        uniq = str(uniqid())[:10].upper()
        (
            retention,
            replicas,
            allocation_min_days,
            storage_shards_nums,
            storage_shards_size,
        ) = StorageConfig.get_default(settings.DEFAULT_NAMESPACE, self.cluster_id)
        retention = os.getenv("BKAPP_EVENT_ES_RETENTION", retention)
        params = {
            "bk_biz_id": settings.DEFAULT_BK_BIZ_ID,
            "bkdata_biz_id": settings.DEFAULT_BK_BIZ_ID,
            "collector_plugin_name_en": collector_plugin.collector_plugin_name_en
            if collector_plugin
            else f"BKAudit_Event_{now.strftime('%Y%m%d')}_{uniq}",
            "collector_plugin_name": collector_plugin.collector_plugin_name
            if collector_plugin
            else f"{gettext('审计事件')}({now.strftime('%Y%m%d%H%M%S')})",
            "collector_scenario_id": DEFAULT_COLLECTOR_SCENARIO,
            "description": gettext("审计事件"),
            "category_id": DEFAULT_CATEGORY_ID,
            "data_encoding": DEFAULT_DATA_ENCODING,
            "is_create_public_data_id": True,
            "is_display_collector": False,
            "is_allow_alone_data_id": True,
            "is_allow_alone_etl_config": True,
            "is_allow_alone_storage": False,
            "etl_processor": DEFAULT_ETL_PROCESSOR,
            "storage_cluster_id": self.cluster_id,
            "fields": fields,
            "retention": retention,
            "allocation_min_days": allocation_min_days,
            "storage_replies": replicas,
            "storage_shards_nums": storage_shards_nums,
            "storage_shards_size": storage_shards_size,
            "etl_config": EtlConfigEnum.BK_LOG_JSON.value,
            "etl_params": dict(),
        }
        if collector_plugin:
            params["collector_plugin_id"] = collector_plugin.collector_plugin_id
        return params

    def add_event(self, data: list) -> None:
        if not data:
            logger.warning("[CreateEvent] No Data")
            return
        index = self._get_write_index(data[0][EventMappingFields.EVENT_TIME.field_name])
        for i in range(0, len(data), BULK_ADD_EVENT_SIZE):
            request_data = self._build_request_data(data[i : i + BULK_ADD_EVENT_SIZE])
            resp = self.client.bulk(index=index, body=request_data)
            logger.info(
                "[BulkAddEventResult] Index => %s; HasError => %s; Resp => %s", index, self._check_response(resp), resp
            )

    def _get_write_index(self, timestamp: int) -> str:
        if not timestamp:
            timestamp = int(datetime.datetime.now().timestamp() * 1000)
        date_string = (
            datetime.datetime.fromtimestamp(timestamp / 1000)
            .replace(tzinfo=timezone.get_current_timezone())
            .astimezone(timezone.utc)
            .strftime(INDEX_TIME_FORMAT)
        )
        return WRITE_INDEX_FORMAT.format(
            date=date_string,
            table_id=self.get_table_id().replace(".", "_"),
        )

    @classmethod
    def get_table_id(cls) -> str:
        collector_plugin = CollectorPlugin.objects.filter(plugin_scene=PluginSceneChoices.EVENT.value).first()
        return CollectorPlugin.make_table_id(collector_plugin.bkdata_biz_id, collector_plugin.collector_plugin_name_en)

    @classmethod
    def get_search_index_set_id(cls) -> int:
        return GlobalMetaConfig.get(config_key=BKAUDIT_EVENT_RT_INDEX_SET_ID)

    def _build_request_data(self, data: list) -> list:
        now = int(datetime.datetime.now().timestamp() * 1000)
        request_data = []
        for _data in data:
            event_id = _data["event_id"]
            event_time = _data[EventMappingFields.EVENT_TIME.field_name] or now
            request_data.extend(
                [
                    {"index": {"_id": event_id}},
                    {**_data, "event_id": event_id, "event_time": event_time, "dtEventTimeStamp": event_time},
                ]
            )
        return request_data

    def _check_response(self, resp: dict) -> bool:
        for data in resp.get("items", {}):
            for _, result in data.items():
                if result.get("_shards", {}).get("failed", 1) > 0:
                    return True
        return False

    @classmethod
    def search_all_event(cls, namespace: str, start_time: str, end_time: str, page: int, page_size: int, **kwargs):
        # 获取单次结果
        resp = FuncRunner(
            func=cls.search_event,
            kwargs={
                "namespace": namespace,
                "start_time": start_time,
                "end_time": end_time,
                "page": page,
                "page_size": page_size,
                "scroll": RISK_SYNC_SCROLL,
                **kwargs,
            },
        ).run()
        data: list = resp["results"]
        # 判断是否需要滚动查询
        if resp["total"] <= page_size:
            return data
        # 滚动查询
        scroll_id = resp["scroll_id"]
        while True:
            resp = FuncRunner(
                func=api.bk_log.es_query_scroll,
                kwargs={
                    "indices": cls.get_table_id().replace(".", "_"),
                    "scenario_id": "log",
                    "storage_cluster_id": GlobalMetaConfig.get(EVENT_ES_CLUSTER_ID_KEY),
                    "scroll": RISK_SYNC_SCROLL,
                    "scroll_id": scroll_id,
                },
            ).run()
            hits = [HitsFormatter(hit["_source"], []).value for hit in resp.get("hits", {}).get("hits", [])]
            if not hits:
                break
            data.extend(hits)
            scroll_id = resp["_scroll_id"]
        return data

    @classmethod
    def search_event(cls, namespace: str, start_time: str, end_time: str, page: int, page_size: int, **kwargs):
        return resource.query.search_all(
            namespace=namespace,
            start_time=start_time,
            end_time=end_time,
            page=page,
            page_size=page_size,
            index_set_id=cls.get_search_index_set_id(),
            storage_cluster_id=GlobalMetaConfig.get(EVENT_ES_CLUSTER_ID_KEY),
            bind_system_info=False,
            **kwargs,
        )

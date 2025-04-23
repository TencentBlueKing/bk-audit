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
from abc import ABCMeta, abstractmethod
from typing import Dict, Type

from bk_resource import api, resource
from blueapps.utils.logger import logger
from django.conf import settings
from django.utils.translation import gettext_lazy

from api.bk_base.constants import StorageType
from apps.meta.constants import ConfigLevelChoices
from apps.meta.models import GlobalMetaConfig
from apps.meta.utils.fields import BKDATA_ES_TYPE_MAP, STANDARD_FIELDS
from apps.permission.handlers.actions import ActionEnum
from core.sql.constants import FieldType
from services.web.databus.constants import COLLECTOR_PLUGIN_ID
from services.web.databus.models import CollectorPlugin
from services.web.query.constants import COLLECT_SEARCH_CONFIG
from services.web.query.serializers import (
    CollectorSearchAllReqSerializer,
    CollectorSearchAllStatisticReqSerializer,
    CollectorSearchConfigRespSerializer,
    CollectorSearchReqSerializer,
    CollectorSearchResponseSerializer,
    CollectorSearchStatisticReqSerializer,
    CollectorSearchStatisticRespSerializer,
)
from services.web.query.utils.doris import (
    BaseDorisSQLBuilder,
    DorisQuerySQLBuilder,
    DorisStatisticSQLBuilder,
)

from .base import QueryBaseResource, SearchDataParser


class CollectorSearchConfigResource(QueryBaseResource):
    name = gettext_lazy("日志查询配置")
    many_response_data = True
    ResponseSerializer = CollectorSearchConfigRespSerializer

    def perform_request(self, validated_request_data):
        return COLLECT_SEARCH_CONFIG.to_json()


class CollectorSearchBaseResource(QueryBaseResource, SearchDataParser, metaclass=ABCMeta):
    @property
    @abstractmethod
    def doris_sql_builder_class(self) -> Type[BaseDorisSQLBuilder]:
        pass

    @abstractmethod
    def build_sql(self, validated_request_data) -> BaseDorisSQLBuilder:
        """
        构建日志查询SQL
        """

        page = validated_request_data["page"]
        page_size = validated_request_data["page_size"]
        namespace = validated_request_data["namespace"]
        filters = validated_request_data["filters"]
        # 获取默认日志 RT
        collector_plugin_id = GlobalMetaConfig.get(
            config_key=COLLECTOR_PLUGIN_ID,
            config_level=ConfigLevelChoices.NAMESPACE.value,
            instance_key=namespace,
        )
        plugin = CollectorPlugin.objects.get(collector_plugin_id=collector_plugin_id)
        collector_rt_id = plugin.build_result_table_id(settings.DEFAULT_BK_BIZ_ID, plugin.collector_plugin_name_en)
        sql_builder = self.doris_sql_builder_class(
            table=collector_rt_id,
            filters=filters,
            sort_list=validated_request_data["sort_list"],
            page=page,
            page_size=page_size,
        )
        return sql_builder


class CollectorSearchAllResource(CollectorSearchBaseResource):
    name = gettext_lazy("日志搜索(All)")
    RequestSerializer = CollectorSearchAllReqSerializer
    serializer_class = CollectorSearchResponseSerializer
    doris_sql_builder_class = DorisQuerySQLBuilder

    def build_sql(self, validated_request_data) -> Dict[str, str]:
        """
        构建日志查询SQL，返回所有数据
        """
        sql_builder = super().build_sql(validated_request_data)
        data_sql = sql_builder.build_data_sql()
        count_sql = sql_builder.build_count_sql()
        logger.info(f"[{self.__class__.__name__}] search data_sql: {data_sql};count_sql:{count_sql}")
        return {"data": data_sql, "count": count_sql}

    def perform_request(self, validated_request_data):
        page = validated_request_data["page"]
        page_size = validated_request_data["page_size"]
        bind_system_info = validated_request_data["bind_system_info"]
        sqls = self.build_sql(validated_request_data)
        bulk_req_params = [
            {
                "sql": sqls["data"],
                "prefer_storage": StorageType.DORIS.value,
            },
            {
                "sql": sqls["count"],
                "prefer_storage": StorageType.DORIS.value,
            },
        ]
        # 请求BKBASE数据
        bulk_resp = api.bk_base.query_sync.bulk_request(bulk_req_params)
        data_resp, count_resp = bulk_resp
        data = self.parse_data(data_resp.get("list", []))
        # 补充系统信息
        if bind_system_info:
            systems = resource.meta.system_list(namespace=validated_request_data["namespace"])
            system_map = {system["system_id"]: system for system in systems}
            for value in data:
                value["system_info"] = system_map.get(value.get("system_id"), dict())
        # 请求总数
        total = count_resp.get("list", [{}])[0].get("count", 0)
        # 响应
        resp = {
            "page": page,
            "num_pages": page_size,
            "total": total,
            "results": data,
            "query_sql": sqls["data"],
            "count_sql": sqls["count"],
        }
        return resp


class CollectorSearchAllStatisticResource(CollectorSearchBaseResource):
    name = gettext_lazy("日志统计查询(All)")
    RequestSerializer = CollectorSearchAllStatisticReqSerializer
    ResponseSerializer = CollectorSearchStatisticRespSerializer
    audit_action = ActionEnum.REGULAR_EVENT_STATISTIC
    doris_sql_builder_class = DorisStatisticSQLBuilder
    standard_fields_types = {
        field.field_name: FieldType(BKDATA_ES_TYPE_MAP[field.field_type]) for field in STANDARD_FIELDS
    }

    def build_sql(self, validated_request_data) -> Dict[str, str]:
        """
        构建日志统计查询SQL
        """
        sql_builder = super().build_sql(validated_request_data)
        # 调用 build_data_statistic_sql 获取统计信息
        field_name = validated_request_data["field_name"]
        field_type = self.standard_fields_types[field_name]
        stats_sql = sql_builder.build_statistic_sql(
            field_name=validated_request_data["field_name"], field_type=field_type
        )
        logger.info(f"[{self.__class__.__name__}] search stats_sql: {stats_sql}")
        return stats_sql

    def perform_request(self, validated_request_data):
        stats_sql = self.build_sql(validated_request_data)

        # 创建请求参数，每个查询独立请求
        bulk_req_params = [
            {
                "sql": query_sql,
                "prefer_storage": StorageType.DORIS.value,
            }
            for query_sql in stats_sql.values()
            if query_sql  # 从 stats_sql 字典中获取每个查询 SQL
        ]
        # 请求 BKBASE 数据
        bulk_resp = api.bk_base.query_sync.bulk_request(bulk_req_params)
        results = {}
        for per_resp, sql_name in zip(bulk_resp, (k for k, v in stats_sql.items() if v)):
            per_ret = per_resp.get("list", [])
            if per_ret:
                results[sql_name] = per_ret
            else:
                results[sql_name] = None
        results.update((k, v) for k, v in stats_sql.items() if not v)
        resp = {
            "results": results,
            "sqls": stats_sql,  # 返回每个统计查询的 SQL
        }
        return resp


class CollectorSearchResource(CollectorSearchAllResource):
    name = gettext_lazy("日志查询")
    RequestSerializer = CollectorSearchReqSerializer
    serializer_class = CollectorSearchStatisticRespSerializer
    audit_action = ActionEnum.SEARCH_REGULAR_EVENT


class CollectorSearchStatisticResource(CollectorSearchAllStatisticResource):
    name = gettext_lazy("日志统计统计")
    RequestSerializer = CollectorSearchStatisticReqSerializer
    serializer_class = CollectorSearchStatisticRespSerializer
    audit_action = ActionEnum.SEARCH_REGULAR_EVENT

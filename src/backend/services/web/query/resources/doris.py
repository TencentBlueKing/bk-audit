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
from blueapps.utils.logger import logger
from django.conf import settings
from django.utils.translation import gettext_lazy

from api.bk_base.constants import StorageType
from apps.meta.constants import ConfigLevelChoices
from apps.meta.models import GlobalMetaConfig
from core.utils.tools import is_product
from services.web.databus.constants import COLLECTOR_PLUGIN_ID
from services.web.databus.models import CollectorPlugin
from services.web.query.constants import COLLECT_SEARCH_CONFIG
from services.web.query.serializers import (
    CollectorSearchConfigRespSerializer,
    CollectorSearchReqSerializer,
    QuerySearchResponseSerializer,
)
from services.web.query.utils.collector import CollectorSQLBuilder

from .base import QueryBaseResource, SearchDataParser


class CollectorSearchConfigResource(QueryBaseResource):
    name = gettext_lazy("日志查询配置")
    many_response_data = True
    ResponseSerializer = CollectorSearchConfigRespSerializer

    def perform_request(self, validated_request_data):
        return COLLECT_SEARCH_CONFIG.to_json()


class CollectorSearchResource(QueryBaseResource, SearchDataParser):
    name = gettext_lazy("日志查询")
    RequestSerializer = CollectorSearchReqSerializer
    serializer_class = QuerySearchResponseSerializer

    def build_sql(self, validated_request_data):
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
        sql_builder = CollectorSQLBuilder(
            table=collector_rt_id,
            filters=filters,
            sort_list=validated_request_data["sort_list"],
            page=page,
            page_size=page_size,
        )
        data_sql = sql_builder.build_data_sql()
        count_sql = sql_builder.build_count_sql()
        logger.info(f"[{self.__class__.__name__}] search data_sql: {data_sql};count_sql:{count_sql}")
        return data_sql, count_sql

    def perform_request(self, validated_request_data):
        page = validated_request_data["page"]
        page_size = validated_request_data["page_size"]
        bind_system_info = validated_request_data["bind_system_info"]
        data_sql, count_sql = self.build_sql(validated_request_data)
        bulk_req_params = [
            {
                "sql": data_sql,
                "prefer_storage": StorageType.DORIS.value,
            },
            {
                "sql": count_sql,
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
        }
        # 非正式环境返回原始SQL
        if not is_product():
            resp.update({"query_sql": data_sql, "count_sql": count_sql})
        return resp

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

from typing import List

from bk_resource import api
from django.conf import settings
from elasticsearch import Elasticsearch

from api.bk_monitor.constants import ClusterTypeChoices
from services.web.databus.constants import (
    BKLOG_INDEX_SET_SCENARIO_ID,
    DEFAULT_CATEGORY_ID,
)
from services.web.databus.models import CollectorPlugin
from services.web.esquery.exceptions import ClusterNotExist


class ElasticHandler:
    """
    ES
    """

    def __init__(self, cluster_id: int):
        self.cluster_id = cluster_id
        es_config = self.get_es_config(cluster_id)
        self.client = self.get_client(**es_config)

    @classmethod
    def get_client(
        cls,
        username: str,
        password: str,
        hosts: List[str],
        port: int,
        sniffer_timeout: int = 600,
        verify_certs: bool = False,
        **kwargs,
    ) -> Elasticsearch:
        http_auth = (username, password) if password else None
        return Elasticsearch(
            hosts, http_auth=http_auth, port=port, sniffer_timeout=sniffer_timeout, verify_certs=verify_certs, **kwargs
        )

    @classmethod
    def get_es_config(cls, cluster_id: int) -> dict:
        result = api.bk_monitor.get_cluster_info(
            cluster_type=ClusterTypeChoices.ES.value,
            cluster_id=cluster_id,
            is_plain_text=True,
            registered_system=settings.CLUSTER_REGISTRY_APP,
        )
        if result:
            cluster_info = result[0]
            cluster_config = cluster_info["cluster_config"]
            auth_info = cluster_info["auth_info"]
            return {
                "username": auth_info["username"],
                "password": auth_info["password"],
                "hosts": [cluster_config["domain_name"]],
                "port": cluster_config["port"],
            }
        raise ClusterNotExist()

    @classmethod
    def create_index_set(cls, collector_plugin: CollectorPlugin, index_set_format: str) -> None:
        bk_biz_id = settings.DEFAULT_BK_BIZ_ID
        result_table_id = CollectorPlugin.make_table_id(bk_biz_id, collector_plugin.collector_plugin_name_en)
        params = {
            "index_set_name": index_set_format.format(result_table=f"Plugin{collector_plugin.collector_plugin_id}"),
            "bk_biz_id": bk_biz_id,
            "bk_app_code": settings.APP_CODE,
            "view_roles": [],
            "scenario_id": BKLOG_INDEX_SET_SCENARIO_ID,
            "category_id": DEFAULT_CATEGORY_ID,
            "indexes": [
                {
                    "bk_biz_id": bk_biz_id,
                    "result_table_id": result_table_id,
                    "result_table_name_alias": result_table_id,
                    "permission": {"manage_collection": True},
                }
            ],
        }
        resp = api.bk_log.index_set_replace(**params)
        collector_plugin.index_set_id = resp["index_set_id"]
        collector_plugin.save(update_fields=["index_set_id"])

    def ping(self) -> bool:
        return self.client.ping()

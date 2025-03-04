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
from typing import List, Set

from bk_resource import api, resource
from django.conf import settings
from django.db.models import Q
from django.utils.module_loading import import_string

from apps.meta.constants import ConfigLevelChoices, SpaceType
from apps.meta.models import GlobalMetaConfig, ResourceType, System
from services.web.databus.constants import COLLECTOR_PLUGIN_ID, SnapshotRunningStatus
from services.web.databus.models import CollectorPlugin, Snapshot
from services.web.strategy_v2.constants import (
    BIZ_RT_TABLE_ALLOW_STORAGES,
    BKBaseProcessingType,
    ResultTableType,
)


class TableHandler:
    def __new__(cls, table_type: str, *args, **kwargs) -> "TableHandler":
        # check child
        if cls.__name__ != TableHandler.__name__:
            return super().__new__(cls)
        # load control
        handler_path = "services.web.strategy_v2.utils.table.{}TableHandler".format(table_type)
        handler_class = import_string(handler_path)
        # init controller
        return handler_class(table_type=table_type, *args, **kwargs)

    def __init__(self, table_type: str, *args, **kwargs):
        self.table_type = table_type

    @abc.abstractmethod
    def list_tables(self) -> List[dict]:
        raise NotImplementedError()

    def format_result_tables(self, result_tables: List[dict]) -> List[dict]:
        """
        格式化RT,配置映射关系
        """

        # 获取所有的空间
        spaces = {
            s["id"]: {"label": "{}({})".format(s["name"], s["id"]), "value": s["id"], "children": []}
            for s in resource.meta.get_spaces_mine()
            if s["space_type_id"] == SpaceType.BIZ.value
        }
        for rt in result_tables:
            bk_biz_id = str(rt["bk_biz_id"])
            if bk_biz_id not in spaces:
                spaces[bk_biz_id] = {"label": bk_biz_id, "value": bk_biz_id, "children": []}
            spaces[bk_biz_id]["children"].append({"label": rt["result_table_name"], "value": rt["result_table_id"]})
        # 响应
        data = list(spaces.values())
        data.sort(key=lambda biz: (not bool(biz["children"]), int(biz["value"])))
        return data


class EventLogTableHandler(TableHandler):
    def __init__(self, table_type: str, namespace: str):
        super().__init__(table_type)
        self.namespace = namespace

    def list_tables(self) -> List[dict]:
        collector_plugin_id = GlobalMetaConfig.get(
            config_key=COLLECTOR_PLUGIN_ID,
            config_level=ConfigLevelChoices.NAMESPACE.value,
            instance_key=self.namespace,
        )
        plugin = CollectorPlugin.objects.get(collector_plugin_id=collector_plugin_id)
        return [
            {
                "label": plugin.collector_plugin_name,
                "value": CollectorPlugin.make_table_id(
                    settings.DEFAULT_BK_BIZ_ID, plugin.collector_plugin_name_en
                ).replace(".", "_"),
            }
        ]


class BuildInTableHandler(TableHandler):
    def __init__(self, table_type: str, namespace: str, *args, **kwargs):
        super().__init__(table_type)
        self.namespace = namespace

    def list_tables(self) -> List[dict]:
        # 获取系统列表
        systems = {
            s.system_id: {"label": "{}({})".format(s.name, s.system_id), "value": s.system_id, "children": []}
            for s in System.objects.filter(namespace=self.namespace)
        }
        # 获取所有的快照
        snapshots = Snapshot.objects.filter(bkbase_table_id__isnull=False, status=SnapshotRunningStatus.RUNNING.value)
        # 获取所有的资源类型
        q = Q()
        for snapshot in snapshots:
            q |= Q(system_id=snapshot.system_id, resource_type_id=snapshot.resource_type_id)
        resource_types = {
            "{}.{}".format(r.system_id, r.resource_type_id): r.name for r in ResourceType.objects.filter(q)
        }
        # 映射到系统
        for snapshot in snapshots:
            systems[snapshot.system_id]["children"].append(
                {
                    "label": resource_types.get(
                        "{}.{}".format(snapshot.system_id, snapshot.resource_type_id), snapshot.resource_type_id
                    ),
                    "value": snapshot.bkbase_table_id,
                }
            )
        # 响应
        data = list(systems.values())
        data.sort(key=lambda system: (not bool(system["children"]), system["value"]))
        return data


class BizAssetTableHandler(TableHandler):
    def list_tables(self) -> List[dict]:
        # 获取所有的RT
        result_table_ids = [
            r["result_table_id"]
            for r in api.bk_base.get_project_data(project_id=settings.BKBASE_PROJECT_ID, extra_fields=True)
        ]
        request_params = []
        batch_size = 50
        for i in range(0, len(result_table_ids), batch_size):
            # fmt: off
            request_params.append({"result_table_ids": result_table_ids[i: i + batch_size]})
        # 获取RT信息
        result_tables = []
        for rts in api.bk_base.get_result_tables.bulk_request(request_params):
            result_tables.extend(
                rt
                for rt in rts
                if rt
                and (
                    rt["processing_type"] == BKBaseProcessingType.CDC
                    or rt.get("result_table_type") == ResultTableType.STATIC
                )
            )
        return self.format_result_tables(result_tables)


class BizRtTableHandler(TableHandler):
    """
    获取业务下 RT 数据(排除日志和资产)
    """

    def __init__(self, table_type: str, namespace: str, *args, **kwargs):
        super().__init__(table_type)
        self.namespace = namespace

    def get_exclude_rt_ids(self) -> Set[str]:
        """
        获取需要排除的 rt
        """

        # 资产 rt
        exclude_rt_ids = set(
            list(
                Snapshot.objects.filter(
                    bkbase_table_id__isnull=False, status=SnapshotRunningStatus.RUNNING.value
                ).values_list("bkbase_table_id", flat=True)
            )
        )
        # 日志 rt
        collector_plugin_id = GlobalMetaConfig.get(
            config_key=COLLECTOR_PLUGIN_ID, config_level=ConfigLevelChoices.NAMESPACE.value, instance_key=self.namespace
        )
        plugin = CollectorPlugin.objects.get(collector_plugin_id=collector_plugin_id)
        log_rt_id = CollectorPlugin.make_table_id(settings.DEFAULT_BK_BIZ_ID, plugin.collector_plugin_name_en).replace(
            ".", "_"
        )
        exclude_rt_ids.add(log_rt_id)
        return exclude_rt_ids

    def list_tables(self) -> List[dict]:
        exclude_rt_ids = self.get_exclude_rt_ids()
        # 获取业务下的RT
        result_table_ids = [
            r["result_table_id"]
            for r in api.bk_base.get_project_data(
                project_id=settings.BKBASE_PROJECT_ID, extra_fields=True, related=["storages"]
            )
            if r["result_table_id"] not in exclude_rt_ids
        ]
        request_params = []
        batch_size = 50
        for i in range(0, len(result_table_ids), batch_size):
            # fmt: off
            request_params.append({"result_table_ids": result_table_ids[i: i + batch_size], "related": ["storages"]})

        # 获取RT信息,过滤掉不包含指定存储的 RT
        result_tables = []
        for rts in api.bk_base.get_result_tables.bulk_request(request_params):
            result_tables.extend(
                rt for rt in rts if rt and (rt.get("storages", {}).keys() & BIZ_RT_TABLE_ALLOW_STORAGES)
            )
        return self.format_result_tables(result_tables)

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
from apps.meta.utils.fields import BKLOG_BUILD_IN_FIELDS, STANDARD_FIELDS
from services.web.analyze.utils import is_asset
from services.web.databus.constants import COLLECTOR_PLUGIN_ID, SnapshotRunningStatus
from services.web.databus.models import CollectorPlugin, Snapshot
from services.web.strategy_v2.constants import (
    BIZ_RT_TABLE_ALLOW_STORAGES,
    BKBASE_INTERNAL_FIELD,
    BKBaseProcessingType,
    BkBaseStorageType,
    ResultTableType,
    RuleAuditSourceType,
)
from services.web.strategy_v2.models import LinkTable


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
        log_rt_id = CollectorPlugin.build_collector_rt(namespace=self.namespace)
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


class RuleAuditSourceTypeChecker:
    def __init__(self, namespace: str):
        self.namespace = namespace

    def link_table_support_source_types(self, link_table: LinkTable) -> List[RuleAuditSourceType]:
        """
        判断联表是否支持某种调度类型
        1. 实时计算：必须是日志作为实时流水表，其余都是资产作为离线维表；例如：一个日志与其他资产维表关联
        2. 离线计算：全部都是资产作为离线维表，或者可以加上日志作为离线流水表；例如：一个日志和其他资产维表关联或者多个资产维表关联
        """

        support_source_types = []
        collector_log_rt = CollectorPlugin.build_collector_rt(namespace=self.namespace)
        rt_ids = link_table.rt_ids.copy()
        # 如果有日志表则可以作为实时任务
        if collector_log_rt in rt_ids:
            rt_ids.remove(collector_log_rt)
            support_source_types.append(RuleAuditSourceType.REALTIME)
        # 需要确保其他 rt 必须为维表
        rts = api.bk_base.get_result_tables(result_table_ids=rt_ids, related=["storages"])
        if len(rts) != len(rt_ids):
            return []
        for rt in rts:
            if not is_asset(rt):
                return []
        support_source_types.append(RuleAuditSourceType.BATCH)
        return support_source_types

    def rt_support_source_types(self, rt_id: str) -> List[RuleAuditSourceType]:
        """
        判断 rt 是否支持某种调度类型
        1. 实时计算：rt 入 kafka；例如：实时的日志，资产或其他数据
        2. 离线计算：入 HDFS 作为离线流水表，资产作为离线维表；例如：日志，资产，以及入 HDFS 存储的其他数据
        """

        support_source_types = []
        rt = api.bk_base.get_result_table(result_table_id=rt_id, related=["storages"])
        storage = rt.get("storages", {}).keys()
        # 实时计算中：kafka 可作为实时流水表
        if BkBaseStorageType.KAFKA in storage:
            support_source_types.append(RuleAuditSourceType.REALTIME)
        # 离线计算中：HDFS 可作为离线流水表；资产表可作为离线维表
        if BkBaseStorageType.HDFS in storage or is_asset(rt):
            support_source_types.append(RuleAuditSourceType.BATCH)
        return support_source_types


def enhance_rt_fields(fields, result_table_id):
    """在原始BKBase RT Field信息基础上，添加审计侧的附加信息。"""
    result = [
        {
            "label": "{}".format(field["field_alias"] or field["field_name"]),
            "alias": field["field_alias"] or field["field_name"],
            "value": field["field_name"],
            "field_type": field["field_type"],
            "spec_field_type": field["field_type"],
        }
        for field in fields
        if field["field_name"] not in BKBASE_INTERNAL_FIELD
    ]
    collector_plugin_id = GlobalMetaConfig.get(
        config_key=COLLECTOR_PLUGIN_ID,
        config_level=ConfigLevelChoices.NAMESPACE.value,
        instance_key='default',
        default=None,
    )
    if collector_plugin_id:
        plugin = CollectorPlugin.objects.get(collector_plugin_id=collector_plugin_id)
        if result_table_id == plugin.bkbase_table_id:
            standard_fields = {field.field_name: field for field in STANDARD_FIELDS + BKLOG_BUILD_IN_FIELDS}
            for field in result:
                if field["value"] in standard_fields:
                    field["spec_field_type"] = standard_fields[field["value"]].property.get(
                        "spec_field_type", standard_fields[field["value"]].field_type
                    )
    return result

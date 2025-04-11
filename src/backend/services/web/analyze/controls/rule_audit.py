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
import time
from functools import cached_property
from typing import List

from bk_resource import api
from bk_resource.exceptions import APIRequestError
from blueapps.utils.logger import logger
from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404

from services.web.analyze.constants import (
    AUDIT_EVENT_TABLE_FORMAT,
    BKBASE_DEFAULT_BASELINE_LOCATION,
    BKBASE_DEFAULT_COUNT_FREQ,
    BKBASE_DEFAULT_OFFSET,
    BKBASE_DEFAULT_WINDOW_COLOR,
    RULE_AUDIT_STRATEGY_STOP_MAX_SLEEP_TIMES,
    RULE_AUDIT_STRATEGY_STOP_SLEEP_TIME,
    BaseControlTypeChoices,
    FlowDataSourceNodeType,
    FlowNodeStatusChoices,
    FlowSQLNodeType,
    OffsetUnit,
    OutputBaselineType,
    WindowDependencyRule,
    WindowType,
)
from services.web.analyze.controls.base import BkbaseFlowController
from services.web.analyze.exceptions import NotSupportDataSource
from services.web.analyze.storage_node import (
    BaseStorageNode,
    ESStorageNode,
    HDFSStorageNode,
    QueueStorageNode,
)
from services.web.analyze.utils import calculate_offline_flow_start_time, is_asset
from services.web.databus.models import CollectorPlugin
from services.web.strategy_v2.constants import BkBaseStorageType, RuleAuditConfigType
from services.web.strategy_v2.models import LinkTable


class RuleAuditController(BkbaseFlowController):
    """
    RuleAuditController
    """

    base_control_type = BaseControlTypeChoices.RULE_AUDIT

    def __init__(self, strategy_id: int):
        super().__init__(strategy_id)
        self.rt_node_map = {}  # {rt_id: node_id}
        self.x_interval = 300
        self.y_interval = 100
        self.x = 0
        self.y = 0

    @cached_property
    def raw_table_name(self) -> str:
        """
        原始表名
        """

        return self.strategy.backend_data.get("raw_table_name") or AUDIT_EVENT_TABLE_FORMAT % (
            self.strategy.namespace,
            str(time.time_ns()),
        )

    def _create_flow(self) -> None:
        resp = api.bk_base.create_flow(project_id=settings.BKBASE_PROJECT_ID, flow_name=self.flow_name)
        self.strategy.backend_data["flow_id"] = resp["flow_id"]

    @cached_property
    def event_log_rt_id(self) -> str:
        """
        操作日志rt_id
        """

        return CollectorPlugin.build_collector_rt(self.strategy.namespace)

    def check_source_type(self, result_table_id: str) -> str:
        """
        check batch / batch_join
        """

        config_type = self.strategy.configs["config_type"]
        data_source = self.strategy.configs["data_source"]
        source_type = data_source["source_type"]
        result_table = api.bk_base.get_result_table(result_table_id=result_table_id, related=["storages"])
        # 1. 实时计算&(日志|其他单表)：实时流水表
        if source_type == FlowDataSourceNodeType.REALTIME and (
            self.event_log_rt_id == result_table_id or config_type != RuleAuditConfigType.LINK_TABLE
        ):
            return FlowDataSourceNodeType.REALTIME
        # 2. 资产表：离线维表/实时维表
        elif is_asset(result_table):
            if source_type == FlowDataSourceNodeType.REALTIME and BkBaseStorageType.REDIS in result_table.get(
                "storages", {}
            ):
                return FlowDataSourceNodeType.REDIS_KV_SOURCE
            return FlowDataSourceNodeType.BATCH
        # 3. 离线计算：离线流水表
        elif source_type == FlowDataSourceNodeType.BATCH:
            return FlowDataSourceNodeType.BATCH_REAL
        # 4. 未支持：异常
        else:
            raise NotSupportDataSource(source_type, result_table_id)

    @cached_property
    def rt_ids(self) -> List[str]:
        """
        当前策略的 rt_id 列表
        """

        config_type = self.strategy.configs["config_type"]
        data_source = self.strategy.configs["data_source"]

        if config_type == RuleAuditConfigType.LINK_TABLE:
            ltc = data_source["link_table"]
            link_table: LinkTable = get_object_or_404(LinkTable, uid=ltc["uid"], version=ltc["version"])
            rt_ids = list(link_table.rt_ids)
        else:
            rt_ids = [data_source["rt_id"]]
        return rt_ids

    def _build_data_source_node_config(self, rt_id: str) -> dict:
        """
        创建数据源节点配置
        """

        return {
            "node_type": self.check_source_type(result_table_id=rt_id),
            "from_result_table_ids": [rt_id],
            "result_table_id": rt_id,
            "name": rt_id,
        }

    def _build_sql_node_config(self, bk_biz_id: int) -> dict:
        """
        build sql node
        """

        # init params
        data_source = self.strategy.configs["data_source"]
        schedule_config = self.strategy.configs.get("schedule_config", {})

        # init sql node
        sql_node_type = FlowSQLNodeType.get_sql_node_type(data_source["source_type"])
        sql_node_params = {
            "node_type": sql_node_type,
            "bk_biz_id": bk_biz_id,
            "from_result_table_ids": self.rt_ids,
            "name": f"{sql_node_type}_{self.raw_table_name}",
            "table_name": self.raw_table_name,
            "output_name": self.raw_table_name,
        }
        # add realtime node
        if sql_node_type == FlowSQLNodeType.REALTIME:
            sql_node_params.update(
                {
                    "sql": self.strategy.sql,
                }
            )
            return sql_node_params
        if sql_node_type == FlowSQLNodeType.BATCH_V2:
            # 获取调度频率和周期
            count_freq = schedule_config.get("count_freq", BKBASE_DEFAULT_COUNT_FREQ)
            schedule_period = schedule_config.get("schedule_period", OffsetUnit.HOUR)
            start_time_str = calculate_offline_flow_start_time(schedule_period)
            sql_node_params.update(
                {
                    "outputs": [
                        {
                            "bk_biz_id": bk_biz_id,
                            "table_name": sql_node_params["table_name"],
                            "output_name": sql_node_params["output_name"],
                        }
                    ],
                    "inputs": [
                        {"id": self.rt_node_map[rt_id], "from_result_table_ids": [rt_id]} for rt_id in self.rt_ids
                    ],
                    "dedicated_config": {
                        "sql": self.strategy.sql,
                        "self_dependence": {
                            "self_dependency_config": {"fields": [], "dependency_rule": WindowDependencyRule.NO_FAILED},
                            "self_dependency": False,
                        },
                        "schedule_config": {
                            "count_freq": count_freq,
                            "schedule_period": schedule_period,
                            "start_time": start_time_str,
                        },
                        "output_config": {
                            "enable_customize_output": False,
                            "output_baseline_location": BKBASE_DEFAULT_BASELINE_LOCATION,
                            "output_offset": BKBASE_DEFAULT_OFFSET,
                            "output_offset_unit": OffsetUnit.HOUR,
                            "output_baseline_type": OutputBaselineType.SCHEDULE,
                            "output_baseline": "",
                        },
                    },
                    "window_info": [
                        {
                            "window_offset": BKBASE_DEFAULT_OFFSET,
                            "window_offset_unit": schedule_config.get("window_offset_unit", OffsetUnit.HOUR),
                            "window_size": count_freq,
                            "window_size_unit": schedule_period,
                            "dependency_rule": schedule_config.get(
                                "window_offset_unit", WindowDependencyRule.NO_FAILED
                            ),
                            "accumulate_start_time": start_time_str,
                            "result_table_id": rt_id,
                            "window_type": WindowType.WHOLE
                            if self.check_source_type(rt_id) == FlowDataSourceNodeType.BATCH
                            else WindowType.SCROLL,
                            "color": BKBASE_DEFAULT_WINDOW_COLOR,
                        }
                        for rt_id in self.rt_ids
                    ],
                }
            )
            return sql_node_params

    def _describe_from_links(self, last_node_ids: List[int]):
        return [
            {
                "source": {"node_id": last_node_id, "id": f"ch_{last_node_id}", "arrow": "Left"},
                "target": {"id": f"bk_node_{int(datetime.datetime.now().timestamp() * 1000)}", "arrow": "Left"},
            }
            for last_node_id in last_node_ids
        ]

    def delete_data_source_nodes(self, flow_id: int):
        """
        删除数据源节点
        """

        data_source_node_ids = self.strategy.backend_data.get("data_source_node_ids", [])
        bulk_delete_params = [
            {"flow_id": flow_id, "node_id": node_id, "confirm": "true"} for node_id in data_source_node_ids
        ]
        api.bk_base.delete_flow_node.bulk_request(bulk_delete_params, ignore_exceptions=True)
        logger.info("[DeleteDataSourceNodes] FlowID => %s; NodeIDS => %s", flow_id, data_source_node_ids)

    def create_or_update_data_source_nodes(self, need_create: bool, flow_id: int) -> List[int]:
        """
        创建/更新数据源节点
        """

        if not need_create:
            # 删除已有的数据源节点
            try:
                self.delete_data_source_nodes(flow_id)
            except APIRequestError as e:
                logger.warning(
                    "[DeleteDataSourceNodes] FlowID => %s; Error => %s",
                    flow_id,
                    e,
                )
        data_source_node_ids = []
        # 构建新的数据源节点
        self.y = self.y_interval
        self.x += self.x_interval
        for rt_id in self.rt_ids:
            node_config = self._build_data_source_node_config(rt_id=rt_id)
            node = {
                "flow_id": flow_id,
                "frontend_info": {"x": self.x, "y": self.y},
                "from_links": [],
                "node_type": node_config["node_type"],
                "config": node_config,
            }
            resp = api.bk_base.create_flow_node(**node)
            node_id = resp["node_id"]
            self.rt_node_map[rt_id] = node_id
            data_source_node_ids.append(node_id)
            self.y += self.y_interval
        self.strategy.backend_data["data_source_node_ids"] = data_source_node_ids
        logger.info(
            "[CreateOrUpdateDataSourceNodes] FlowID => %s; NodeIDS => %s",
            flow_id,
            data_source_node_ids,
        )
        return data_source_node_ids

    def create_or_update_sql_node(self, need_create: bool, flow_id: int, data_source_node_ids: List[int]) -> int:
        """
        创建/更新sql节点
        """

        bk_biz_id = int(self.rt_ids[0].split("_", 1)[0])
        sql_node_config = self._build_sql_node_config(bk_biz_id)
        self.x += self.x_interval
        self.y = self.y_interval
        sql_node = {
            "flow_id": flow_id,
            "frontend_info": {"x": self.x, "y": self.y},
            "from_links": self._describe_from_links(data_source_node_ids),
            "node_type": sql_node_config["node_type"],
            "config": sql_node_config,
        }
        if need_create:
            resp = api.bk_base.create_flow_node(**sql_node)
            sql_node_id = resp["node_id"]
            self.strategy.backend_data["sql_node_id"] = sql_node_id
        else:
            sql_node["node_id"] = self.strategy.backend_data["sql_node_id"]
            resp = api.bk_base.update_flow_node(**sql_node)
        sql_node_id = resp["node_id"]
        logger.info(
            "[CreateOrUpdateSqlNode] FlowID => %s; NodeID => %s",
            flow_id,
            sql_node_id,
        )
        return sql_node_id

    def create_or_update_storage_nodes(self, need_create: bool, flow_id: int, sql_node_id: int) -> List[int]:
        """
        创建/更新存储节点
        """

        self.x += self.x_interval
        self.y = self.y_interval
        bk_biz_id = int(self.rt_ids[0].split("_", 1)[0])
        from_result_table_ids = [BaseStorageNode.build_rt_id(bk_biz_id, self.raw_table_name)]
        storage_node_ids = [] if need_create else self.strategy.backend_data.get("storage_node_ids", [])
        storage_nodes = [ESStorageNode, QueueStorageNode, HDFSStorageNode]
        for idx, storage_node in enumerate(storage_nodes):
            node_config = storage_node(namespace=self.strategy.namespace).build_node_config(
                bk_biz_id=bk_biz_id, raw_table_name=self.raw_table_name, from_result_table_ids=from_result_table_ids
            )
            if not node_config:
                continue
            storage_node_config = {
                "flow_id": flow_id,
                "frontend_info": {"x": self.x, "y": self.y},
                "from_links": self._describe_from_links([sql_node_id]),
                "node_type": node_config["node_type"],
                "config": node_config,
            }
            if need_create:
                resp = api.bk_base.create_flow_node(**storage_node_config)
                storage_node_ids.append(resp["node_id"])
            else:
                storage_node_config["node_id"] = storage_node_ids[idx]
                api.bk_base.update_flow_node(**storage_node_config)
            self.y += self.y_interval
        self.strategy.backend_data["storage_node_ids"] = storage_node_ids
        logger.info(
            "[CreateOrUpdateStorageNodes] FlowID => %s; NodeIDS => %s",
            flow_id,
            storage_node_ids,
        )
        return storage_node_ids

    def stop_flow(self):
        flow_status = self._describe_flow_status()
        if flow_status not in [FlowNodeStatusChoices.RUNNING, FlowNodeStatusChoices.FAILED]:
            return
        params = self.build_update_flow_params()
        api.bk_base.stop_flow(**params)

    @transaction.atomic()
    def _update_or_create_bkbase_flow(self) -> bool:
        # check create flow
        need_create = not self.strategy.backend_data.get("flow_id")
        if need_create:
            self._create_flow()
        else:
            # 更新 flow 前需要先停止 flow
            self.stop_flow()
            # 等待停止
            for _ in range(int(RULE_AUDIT_STRATEGY_STOP_MAX_SLEEP_TIMES)):
                if self._describe_flow_status() == FlowNodeStatusChoices.NO_START:
                    break
                time.sleep(RULE_AUDIT_STRATEGY_STOP_SLEEP_TIME)
        flow_id = self.strategy.backend_data["flow_id"]
        data_source_node_ids = self.create_or_update_data_source_nodes(need_create, flow_id)
        # 构建 sql 节点
        sql_node_id = self.create_or_update_sql_node(need_create, flow_id, data_source_node_ids)
        # 构建存储节点
        self.create_or_update_storage_nodes(need_create, flow_id, sql_node_id)
        self.strategy.backend_data["raw_table_name"] = self.raw_table_name
        self.strategy.save(update_record=False, update_fields=["backend_data"])
        return need_create

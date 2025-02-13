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
from blueapps.utils.logger import logger
from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext

from apps.meta.constants import ConfigLevelChoices
from apps.meta.models import GlobalMetaConfig
from apps.notice.handlers import ErrorMsgHandler
from core.lock import lock
from services.web.analyze.constants import (
    AUDIT_EVENT_TABLE_FORMAT,
    BKBASE_DEFAULT_BASELINE_LOCATION,
    BKBASE_DEFAULT_COUNT_FREQ,
    BKBASE_DEFAULT_OFFSET,
    BKBASE_DEFAULT_WINDOW_COLOR,
    BKBASE_FLOW_CONSUMING_MODE,
    BaseControlTypeChoices,
    FlowDataSourceNodeType,
    FlowNodeStatusChoices,
    FlowSQLNodeType,
    FlowStatusToggleChoices,
    OffsetUnit,
    OutputBaselineType,
    ResultTableType,
    WindowDependencyRule,
    WindowType,
)
from services.web.analyze.controls.base import BaseControl
from services.web.analyze.exceptions import NotSupportDataSource
from services.web.analyze.storage_node import (
    BaseStorageNode,
    ESStorageNode,
    HDFSStorageNode,
    QueueStorageNode,
)
from services.web.analyze.tasks import (
    call_controller,
    check_flow_status,
    toggle_monitor,
)
from services.web.analyze.utils import calculate_offline_flow_start_time
from services.web.databus.constants import COLLECTOR_PLUGIN_ID
from services.web.databus.models import CollectorPlugin
from services.web.strategy_v2.constants import (
    BkBaseStorageType,
    RuleAuditConfigType,
    StrategyStatusChoices,
)
from services.web.strategy_v2.exceptions import StrategyStatusUnexpected
from services.web.strategy_v2.models import LinkTable


class RuleAuditController(BaseControl):
    """
    RuleAuditController
    """

    def __init__(self, strategy_id: int):
        super().__init__(strategy_id)
        self.rt_node_map = {}  # {rt_id: node_id}
        self.x_interval = 300
        self.y_interval = 100
        self.x = 0
        self.y = 0

    def create(self) -> None:
        """
        create bkbase flow
        """

        self.update_or_create(StrategyStatusChoices.STARTING)

    def update(self) -> None:
        """
        update bkbase flow
        """

        self.update_or_create(StrategyStatusChoices.UPDATING)

    @lock(load_lock_name=lambda self, status: f"RuleAuditHandler.update_or_create_{self.strategy.strategy_id}")
    def update_or_create(self, status: str):
        self.strategy.status = status
        self.strategy.save(update_fields=["status"])
        call_controller.delay(
            func_name=self._update_or_create.__name__,
            strategy_id=self.strategy.strategy_id,
            base_control_type=BaseControlTypeChoices.RULE_AUDIT.value,
            status=status,
        )

    @cached_property
    def flow_name(self) -> str:
        return f"RULE_AUDIT-{self.strategy.strategy_id}-{str(time.time_ns())}"

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

        collector_plugin_id = GlobalMetaConfig.get(
            config_key=COLLECTOR_PLUGIN_ID,
            config_level=ConfigLevelChoices.NAMESPACE.value,
            instance_key=self.strategy.namespace,
        )
        plugin = CollectorPlugin.objects.get(collector_plugin_id=collector_plugin_id)
        return plugin.build_result_table_id(settings.DEFAULT_BK_BIZ_ID, plugin.collector_plugin_name_en)

    def check_source_type(self, result_table_id: str) -> str:
        """
        check batch / batch_join
        """

        data_source = self.strategy.configs["data_source"]
        source_type = data_source["source_type"]
        result_table = api.bk_base.get_result_table(result_table_id=result_table_id, related=["storages"])
        # 1. 实时计算&日志：实时流水表
        if source_type == FlowDataSourceNodeType.REALTIME and self.event_log_rt_id == result_table_id:
            return FlowDataSourceNodeType.REALTIME
        # 2. 资产表：离线维表/实时维表
        elif (
            result_table["processing_type"] == ResultTableType.CDC
            or result_table["result_table_type"] == ResultTableType.STATIC
        ):
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
            rt_ids = link_table.rt_ids
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
                            "window_offset_unit": schedule_period.get("window_offset_unit", OffsetUnit.HOUR),
                            "window_size": count_freq,
                            "window_size_unit": schedule_period,
                            "dependency_rule": schedule_period.get(
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

    def create_or_update_data_source_nodes(self, need_create: bool, flow_id: int) -> List[int]:
        """
        创建/更新数据源节点
        """

        if not need_create:
            # 删除已有的数据源节点
            data_source_node_ids = self.strategy.backend_data.get("data_source_node_ids", [])
            bulk_delete_params = [
                {"flow_id": flow_id, "node_id": node_id, "confirm": "true"} for node_id in data_source_node_ids
            ]
            api.bk_base.delete_flow_node.bulk_request(bulk_delete_params, ignore_exceptions=True)
            logger.info("[DeleteDataSourceNodes] FlowID => %s; NodeIDS => %s", flow_id, data_source_node_ids)
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
        params = self.build_update_flow_params(flow_id=self.strategy.backend_data["flow_id"])
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
            time.sleep(3)
        flow_id = self.strategy.backend_data["flow_id"]
        data_source_node_ids = self.create_or_update_data_source_nodes(need_create, flow_id)
        # 构建 sql 节点
        sql_node_id = self.create_or_update_sql_node(need_create, flow_id, data_source_node_ids)
        # 构建存储节点
        self.create_or_update_storage_nodes(need_create, flow_id, sql_node_id)
        self.strategy.backend_data["raw_table_name"] = self.raw_table_name
        self.strategy.save(update_fields=["backend_data"])
        return need_create

    def _update_or_create(self, status: str) -> None:
        try:
            self._update_or_create_bkbase_flow()
            self.enable(force=True)
        except Exception as err:
            if status == StrategyStatusChoices.STARTING:
                self.strategy.status = StrategyStatusChoices.START_FAILED
            elif status == StrategyStatusChoices.UPDATING:
                self.strategy.status = StrategyStatusChoices.UPDATE_FAILED
            else:
                self.strategy.status = StrategyStatusChoices.FAILED
            self.strategy.status_msg = str(err)
            self.strategy.save(update_fields=["status", "status_msg"])
            logger.error("[CreateOrUpdateFlowFailed]\nStrategy ID => %s\nError => %s", self.strategy.strategy_id, err)
            ErrorMsgHandler(
                title=gettext("Create or Update Flow Failed"),
                content=gettext("Strategy ID:\t%s") % self.strategy.strategy_id,
            ).send()

    def check_flow_status(self, strategy_id: int, success_status: str, failed_status: str, other_status: str):
        """
        check bkbase flow status
        """

        return check_flow_status.delay(strategy_id, success_status, failed_status, other_status)

    def build_update_flow_params(self, flow_id: str) -> dict:
        """
        构建更新流参数
        """

        return {
            "flow_id": flow_id,
            "consuming_mode": BKBASE_FLOW_CONSUMING_MODE,
            "resource_sets": {
                "stream": settings.BKBASE_STREAM_RESOURCE_SET_ID,
                "batch": settings.BKBASE_BATCH_RESOURCE_SET_ID,
            },
        }

    def _toggle_strategy(self, status: str, force: bool = False) -> None:
        # update flow
        params = self.build_update_flow_params(flow_id=self.strategy.backend_data.get("flow_id"))
        if not force and (
            not params["flow_id"]
            or self.strategy.status
            in [
                StrategyStatusChoices.STARTING.value,
                StrategyStatusChoices.STOPPING.value,
                StrategyStatusChoices.UPDATING.value,
                StrategyStatusChoices.FAILED.value,
            ]
        ):
            return
        match status:
            case FlowStatusToggleChoices.START.value:
                api.bk_base.start_flow(**params)
                self.strategy.status = StrategyStatusChoices.STARTING
                self.strategy.save(update_fields=["status"])
                toggle_monitor.delay(strategy_id=self.strategy.strategy_id, is_active=True)
                self.check_flow_status(
                    strategy_id=self.strategy.strategy_id,
                    success_status=StrategyStatusChoices.RUNNING,
                    failed_status=StrategyStatusChoices.START_FAILED,
                    other_status=StrategyStatusChoices.STARTING,
                )
            case FlowStatusToggleChoices.RESTART.value:
                api.bk_base.restart_flow(**params)
                self.strategy.status = StrategyStatusChoices.UPDATING
                self.strategy.save(update_fields=["status"])
                toggle_monitor.delay(strategy_id=self.strategy.strategy_id, is_active=True)
                self.check_flow_status(
                    strategy_id=self.strategy.strategy_id,
                    success_status=StrategyStatusChoices.RUNNING,
                    failed_status=StrategyStatusChoices.UPDATE_FAILED,
                    other_status=StrategyStatusChoices.UPDATING,
                )
            case FlowStatusToggleChoices.STOP.value:
                api.bk_base.stop_flow(**params)
                self.strategy.status = StrategyStatusChoices.STOPPING
                self.strategy.save(update_fields=["status"])
                toggle_monitor.delay(strategy_id=self.strategy.strategy_id, is_active=False)
                self.check_flow_status(
                    strategy_id=self.strategy.strategy_id,
                    success_status=StrategyStatusChoices.DISABLED,
                    failed_status=StrategyStatusChoices.STOP_FAILED,
                    other_status=StrategyStatusChoices.STOPPING,
                )
            case _:
                raise StrategyStatusUnexpected()

    def _describe_flow_status(self) -> str:
        """
        获取Flow运行状态
        """

        flow_id = self.strategy.backend_data.get("flow_id")
        if not flow_id:
            return FlowNodeStatusChoices.NO_START
        data = api.bk_base.get_flow_deploy_data(flow_id=flow_id)
        if data:
            return data["flow_status"]
        return FlowNodeStatusChoices.NO_START

    def delete(self) -> None:
        flow_status = self._describe_flow_status()
        if flow_status in [FlowNodeStatusChoices.RUNNING, FlowNodeStatusChoices.FAILED]:
            self._toggle_strategy(FlowStatusToggleChoices.STOP.value)

    def enable(self, force: bool = False) -> None:
        """
        enable bkbase flow
        """

        flow_status = self._describe_flow_status()
        if flow_status in [FlowNodeStatusChoices.NO_START]:
            self._toggle_strategy(FlowStatusToggleChoices.START.value, force=force)
        else:
            self._toggle_strategy(FlowStatusToggleChoices.RESTART.value, force=force)

    def disabled(self, force: bool = False) -> None:
        flow_status = self._describe_flow_status()
        if flow_status in [FlowNodeStatusChoices.RUNNING, FlowNodeStatusChoices.FAILED]:
            self._toggle_strategy(FlowStatusToggleChoices.STOP.value, force=force)

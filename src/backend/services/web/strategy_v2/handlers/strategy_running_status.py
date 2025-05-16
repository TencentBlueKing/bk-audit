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
from typing import Dict, List, Optional, Type, TypedDict

from bk_resource import api
from django.db import models
from django.db.models import Count
from django.db.models.functions import TruncMinute

from core.utils.tools import mstimestamp_to_date_string
from services.web.risk.models import Risk
from services.web.strategy_v2.constants import RuleAuditSourceType, StrategyType
from services.web.strategy_v2.models import Strategy


class RunningStatus(TypedDict):
    schedule_time: str  # 调度时间
    data_time: str  # 数据时间
    err_msg: str  # 错误信息
    status: str  # 状态
    status_str: str  # 状态字符串
    risk_count: int  # 风险数量


class StrategyRunningStatusHandler(abc.ABC):
    @staticmethod
    def get_handler_cls(strategy: Strategy) -> Type["StrategyRunningStatusHandler"]:
        """
        根据策略获取对应的处理类
        """

        source_type = strategy.configs.get("data_source", {}).get("source_type")

        # 使用字典映射来简化条件判断
        handler_mapping: Dict[RuleAuditSourceType, Dict[StrategyType, Type[StrategyRunningStatusHandler]]] = {
            RuleAuditSourceType.REALTIME: {
                StrategyType.MODEL: RealtimeStrategyRunningStatusHandler,
                StrategyType.RULE: RealtimeStrategyRunningStatusHandler,
            },
            RuleAuditSourceType.BATCH: {
                StrategyType.MODEL: ModelAuditBatchV2StrategyRunningStatusHandler,
                StrategyType.RULE: RuleAuditBatchV2StrategyRunningStatusHandler,
            },
        }

        return handler_mapping.get(source_type, {}).get(strategy.strategy_type)

    @classmethod
    def get_typed_handler(cls, *args, **kwargs) -> Optional["StrategyRunningStatusHandler"]:
        """
        获取处理类实例
        """

        handler_cls = cls.get_handler_cls(kwargs["strategy"])
        if not handler_cls:
            return None
        return handler_cls(*args, **kwargs)

    def __init__(
        self, strategy: Strategy, start_time: datetime.datetime, end_time: datetime.datetime, limit: int, offset: int
    ):
        """
        :param strategy: 策略
        :param start_time: 开始时间
        :param end_time: 结束时间
        :param limit: 分页大小
        :param offset: 分页偏移量
        """

        self.strategy = strategy
        self.start_time = start_time
        self.end_time = end_time
        self.limit = limit
        self.offset = offset

    @abc.abstractmethod
    def get_strategy_running_status(self) -> List[RunningStatus]:
        """
        获取策略运行状态
        """

        raise NotImplementedError()


class RuleAuditBatchV2StrategyRunningStatusHandler(StrategyRunningStatusHandler):
    """
    规则审计离线策略运行状态
    """

    processing_node_type = "batchv2"

    def get_processing_node(self) -> Optional[dict]:
        """
        获取调度计算节点
        """

        node = None
        flow_id = self.strategy.backend_data.get("flow_id")
        bkbase_nodes = api.bk_base.get_flow_graph(flow_id=flow_id)["nodes"]
        for node in bkbase_nodes:
            if node["node_type"] == self.processing_node_type:
                node = node
                break
        return node

    def get_processing_id(self, processing_node: dict) -> str:
        """
        获取离线计算节点的RT ID
        """

        return processing_node["result_table_ids"][0]

    def get_running_status_list(self) -> List[dict]:
        """
        获取策略运行状态列表
        """

        processing_node = self.get_processing_node()
        if not processing_node:
            return []
        processing_id = self.get_processing_id(processing_node)
        data = api.bk_base.dataflow_batch_status_list(
            processing_id=processing_id,
            data_start=int(self.start_time.timestamp()) * 1000,
            data_end=int(self.end_time.timestamp()) * 1000,
            limit=self.limit,
            offset=self.offset,
        )
        return data

    def get_risk_count_map(self) -> Dict[int, int]:
        """
        获取离线策略累计风险数量:根据风险的事件时间进行聚合计数
        key: 数据时间
        value: 风险数量
        """

        risks = list(
            Risk.objects.filter(
                strategy_id=self.strategy.strategy_id, event_time__range=[self.start_time, self.end_time]
            )
            .values('event_time')
            .annotate(risk_count=Count('risk_id'))
            .order_by('-event_time')
        )
        risk_count_map = {int(risk['event_time'].timestamp()) * 1000: risk['risk_count'] for risk in risks}
        return risk_count_map

    def format_running_status(self, status: dict, risk_count_map: Dict[int, int]) -> RunningStatus:
        """
        格式化运行状态
        """

        return RunningStatus(
            schedule_time=mstimestamp_to_date_string(status["schedule_time"]),
            err_msg=status["err_msg"],
            status=status["status"],
            status_str=status["status_str"],
            risk_count=risk_count_map.get(status["data_time"], 0),
            data_time=mstimestamp_to_date_string(status["data_time"]),
        )

    def get_strategy_running_status(self) -> List[RunningStatus]:
        """
        获取策略运行状态
        """

        if not self.strategy.backend_data.get("flow_id"):
            return []
        running_status_list = self.get_running_status_list()
        if not running_status_list:
            return []
        risk_count_map = self.get_risk_count_map()
        formatted_running_status_list = []
        for status in running_status_list:
            formatted_running_status_list.append(self.format_running_status(status, risk_count_map))
        return formatted_running_status_list[self.offset : self.limit + self.offset]


class ModelAuditBatchV2StrategyRunningStatusHandler(RuleAuditBatchV2StrategyRunningStatusHandler):
    """
    模型审计离线策略运行状态
    """

    processing_node_type = "scenario_app"


class RealtimeStrategyRunningStatusHandler(StrategyRunningStatusHandler):
    """
    实时策略运行状态
    """

    def get_strategy_running_status(self) -> List[RunningStatus]:
        """
        获取策略运行状态(按event_end_time每分钟分组)
        """

        risks = list(
            Risk.objects.filter(
                strategy_id=self.strategy.strategy_id, event_end_time__range=[self.start_time, self.end_time]
            )
            .annotate(
                schedule_time=TruncMinute(
                    'event_end_time', tzinfo=datetime.timezone.utc, output_field=models.DateTimeField()
                )
            )
            .values('schedule_time')
            .annotate(risk_count=Count('risk_id'))
            .order_by('-schedule_time')[self.offset : self.limit + self.offset]
        )
        formatted_running_status_list = []
        for risk in risks:
            schedule_time = mstimestamp_to_date_string(int(risk['schedule_time'].timestamp()) * 1000)
            formatted_running_status_list.append(
                RunningStatus(
                    schedule_time=schedule_time,
                    err_msg="",
                    status="finished",
                    status_str="成功",
                    risk_count=risk['risk_count'],
                    data_time=schedule_time,
                )
            )
        return formatted_running_status_list

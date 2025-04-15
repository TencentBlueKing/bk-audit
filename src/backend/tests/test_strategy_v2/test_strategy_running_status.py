# -*- coding: utf-8 -*-
from datetime import datetime
from unittest import mock

import arrow

from services.web.risk.models import Risk
from services.web.strategy_v2.constants import RuleAuditSourceType, StrategyType
from services.web.strategy_v2.handlers.strategy_running_status import (
    ModelAuditBatchV2StrategyRunningStatusHandler,
    RealtimeStrategyRunningStatusHandler,
    RuleAuditBatchV2StrategyRunningStatusHandler,
    StrategyRunningStatusHandler,
)
from services.web.strategy_v2.models import Strategy
from tests.base import TestCase
from tests.conftest import (
    mock_bk_base_dataflow_batch_status_list,
    mock_bk_base_get_flow_graph,
)
from tests.constants import MOCK_FLOW_ID, RISK_EVENT_TIMESTAMP, RISK_START_TIMESTAMP


class BaseTest(TestCase):
    def mock_api(self):
        self.mock_bk_base_get_flow_graph = mock_bk_base_get_flow_graph().start()
        self.mock_bk_base_dataflow_batch_status_list = mock_bk_base_dataflow_batch_status_list().start()

    def setUp(self):
        self.strategy = Strategy(
            strategy_id=1,
            strategy_type=StrategyType.RULE,
            configs={"data_source": {"source_type": RuleAuditSourceType.BATCH}},
            backend_data={"flow_id": MOCK_FLOW_ID},
        )
        self.mock_api()
        self.risk_time = arrow.get(RISK_EVENT_TIMESTAMP).datetime
        self.end_time = self.risk_time
        self.start_time = arrow.get(RISK_START_TIMESTAMP).datetime

    def tearDown(self):
        mock.patch.stopall()


class TestHandlerMapping(TestCase):
    def test_handler_mapping(self):
        test_cases = [
            (RuleAuditSourceType.REALTIME, StrategyType.RULE, RealtimeStrategyRunningStatusHandler),
            (RuleAuditSourceType.REALTIME, StrategyType.MODEL, RealtimeStrategyRunningStatusHandler),
            (RuleAuditSourceType.BATCH, StrategyType.RULE, RuleAuditBatchV2StrategyRunningStatusHandler),
            (RuleAuditSourceType.BATCH, StrategyType.MODEL, ModelAuditBatchV2StrategyRunningStatusHandler),
        ]

        for source_type, strategy_type, expected_handler in test_cases:
            with self.subTest(source_type=source_type, strategy_type=strategy_type):
                strategy = Strategy(strategy_type=strategy_type, configs={"data_source": {"source_type": source_type}})
                handler_cls = StrategyRunningStatusHandler.get_handler_cls(strategy)
                self.assertIs(handler_cls, expected_handler)


class TestRuleAuditBatchV2StrategyRunningStatusHandler(BaseTest):
    node_type = "batchv2"

    def _test_get_running_status(self):
        # 创建测试风险数据
        Risk.objects.create(
            strategy_id=self.strategy.strategy_id, event_time=self.risk_time, event_end_time=self.risk_time
        )

        handler = StrategyRunningStatusHandler.get_typed_handler(
            strategy=self.strategy, start_time=self.start_time, end_time=self.end_time, limit=10, offset=0
        )

        # 验证处理节点获取
        processing_node = handler.get_processing_node()
        self.assertEqual(processing_node["node_type"], self.node_type)

        # 验证状态查询
        status_list = handler.get_strategy_running_status()
        self.assertEqual(len(status_list), 1)
        self.assertEqual(status_list[0]["risk_count"], 1)

    def test_get_running_status(self):
        self._test_get_running_status()


class TestModelAuditBatchV2StrategyRunningStatusHandler(TestRuleAuditBatchV2StrategyRunningStatusHandler):
    node_type = "scenario_app"

    def setUp(self):
        super().setUp()
        self.strategy = Strategy(
            strategy_id=1,
            strategy_type=StrategyType.MODEL,
            configs={"data_source": {"source_type": RuleAuditSourceType.BATCH}},
            backend_data={"flow_id": MOCK_FLOW_ID},
        )

    def test_get_running_status(self):
        self._test_get_running_status()


class TestRealtimeHandler(BaseTest):
    def test_realtime_status(self):
        # 修改策略类型为实时
        self.strategy.configs["data_source"]["source_type"] = RuleAuditSourceType.REALTIME

        # 创建每小时风险数据
        for i in range(3):
            Risk.objects.create(
                strategy_id=self.strategy.strategy_id,
                event_end_time=datetime(2023, 1, 1, 10 + i),
                event_time=datetime(2023, 1, 1, 10 + i),
            )

        handler = RealtimeStrategyRunningStatusHandler(
            strategy=self.strategy,
            start_time=datetime(2023, 1, 1, 10),
            end_time=datetime(2023, 1, 1, 13),
            limit=2,
            offset=0,
        )

        status_list = handler.get_strategy_running_status()
        self.assertEqual(len(status_list), 2)
        self.assertEqual(status_list[0]["schedule_time"], "2023-01-01 12:00:00")

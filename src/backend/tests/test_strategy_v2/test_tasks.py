# -*- coding: utf-8 -*-
from unittest import mock

from api.bk_base.default import GetFlowDeployData
from services.web.strategy_v2.constants import (
    RuleAuditSourceType,
    StrategyStatusChoices,
    StrategyType,
)
from services.web.strategy_v2.models import Strategy
from services.web.strategy_v2.tasks import (
    StrategyStatusChecker,
    check_strategy_status_anomalies,
)
from tests.base import TestCase


class TestStrategyStatusChecker(TestCase):
    """测试StrategyStatusChecker类"""

    def setUp(self):
        """设置测试数据"""
        self.checker = StrategyStatusChecker()

        # 创建测试策略
        self.strategy = Strategy(
            strategy_id=1,
            strategy_name="测试策略",
            strategy_type=StrategyType.RULE,
            status=StrategyStatusChoices.RUNNING.value,
            configs={"data_source": {"source_type": RuleAuditSourceType.REALTIME}},
            backend_data={"flow_id": 12345},
        )

        # Mock API调用
        self.mock_bk_base_get_flow_deploy_data = mock.Mock(return_value={"flow_status": "running"})

        # 应用Mock到API类
        self.get_flow_deploy_data_patch = mock.patch.object(
            GetFlowDeployData, 'perform_request', self.mock_bk_base_get_flow_deploy_data
        ).start()
        self.report_event_patch = mock.patch(
            "services.web.strategy_v2.tasks.api.bk_monitor.report_event",
            return_value={"result": True, "message": "success"},
        ).start()
        self.mock_bk_monitor_report_event = self.report_event_patch

    def tearDown(self):
        """清理Mock"""
        mock.patch.stopall()

    def test_fetch_flow_status_without_flow_id(self):
        """测试没有flow_id时的flow状态获取"""
        # 当flow_id为None时
        result = self.checker.fetch_flow_status(None)
        assert result == "no-start"

    def test_fetch_flow_status_with_flow_id_success(self):
        """测试有flow_id且API调用成功的flow状态获取"""
        # Mock成功的API响应
        self.mock_bk_base_get_flow_deploy_data.return_value = {"flow_status": "running"}

        result = self.checker.fetch_flow_status(12345)
        assert result == "running"

    def test_fetch_flow_status_with_flow_id_api_error(self):
        """测试API调用失败时的flow状态获取"""
        # Mock API异常
        self.mock_bk_base_get_flow_deploy_data.side_effect = Exception("API调用失败")

        result = self.checker.fetch_flow_status(12345)
        assert result == "error:API调用失败"

    def test_fetch_flow_status_empty_data(self):
        """测试API返回空数据时的flow状态获取"""
        # Mock空数据响应
        self.mock_bk_base_get_flow_deploy_data.return_value = None

        result = self.checker.fetch_flow_status(12345)
        assert result == "no-start"

    def test_fetch_flow_status_missing_flow_status(self):
        """测试API返回数据中缺少flow_status时的处理"""
        # Mock缺少flow_status的数据
        self.mock_bk_base_get_flow_deploy_data.return_value = {"other_field": "value"}

        result = self.checker.fetch_flow_status(12345)
        assert result == "no-start"

    def test_judge_with_error_flow_status(self):
        """测试flow_status包含错误信息时的判断"""
        result = self.checker.judge(self.strategy, "error:API调用失败")
        assert result == "error:API调用失败"

    def test_judge_normal_case_no_anomaly(self):
        """测试正常情况下的判断（无异常）"""
        result = self.checker.judge(self.strategy, "running")
        assert result is None

    def test_judge_status_mismatch(self):
        """测试策略状态与flow状态不匹配的情况"""
        # 策略状态为RUNNING，但flow状态为no-start
        result = self.checker.judge(self.strategy, "no-start")
        assert result == "expect_flow=running, actual=no-start"

    def test_judge_missing_flow_id(self):
        """测试缺少flow_id的情况"""
        # 移除策略的flow_id
        self.strategy.backend_data = {}
        self.strategy.status = StrategyStatusChoices.STARTING.value

        result = self.checker.judge(self.strategy, "running")
        assert result == "missing flow_id"

    def test_judge_disabled_strategy_without_flow_id(self):
        """测试DISABLED状态的策略没有flow_id时不报错"""
        self.strategy.backend_data = {}
        self.strategy.status = StrategyStatusChoices.DISABLED.value

        result = self.checker.judge(self.strategy, "no-start")
        assert result is None

    def test_judge_failed_status(self):
        """测试失败状态的策略"""
        self.strategy.status = StrategyStatusChoices.START_FAILED.value

        result = self.checker.judge(self.strategy, "failure")
        assert result == "start_failed operation failed"

    def test_judge_starting_with_error_messages(self):
        """测试启动中策略有错误消息的情况"""
        self.strategy.status = StrategyStatusChoices.RUNNING.value
        self.strategy.status_msg = "启动过程中出现错误"

        result = self.checker.judge(self.strategy, "running")
        assert result == "starting strategy has error messages: 启动过程中出现错误"

    def test_is_realtime_strategy(self):
        """测试实时策略判断"""
        # 实时策略
        self.strategy.configs = {"data_source": {"source_type": RuleAuditSourceType.REALTIME}}
        assert self.checker.is_realtime_strategy(self.strategy) is True

        # 批量策略
        self.strategy.configs = {"data_source": {"source_type": RuleAuditSourceType.BATCH}}
        assert self.checker.is_realtime_strategy(self.strategy) is False

    def test_check_no_schedule_records_normal_case(self):
        """测试离线策略调度记录检查的正常情况"""
        running_data = [{"status": "success", "schedule_time": "2023-01-01 10:00:00"}]

        result = self.checker.check_no_schedule_records(self.strategy, "running", running_data)
        assert result is None

    def test_check_no_schedule_records_no_data(self):
        """测试离线策略无调度记录的情况"""
        self.strategy.status = StrategyStatusChoices.RUNNING.value

        result = self.checker.check_no_schedule_records(self.strategy, "running", [])
        assert result == "running flow has no schedule records in last 1 day"

    def test_check_no_schedule_records_failed_schedule(self):
        """测试离线策略有失败调度记录的情况"""
        self.strategy.status = StrategyStatusChoices.RUNNING.value
        running_data = [{"status": "failed", "err_msg": "调度失败", "schedule_time": "2023-01-01 10:00:00"}]

        result = self.checker.check_no_schedule_records(self.strategy, "running", running_data)
        assert result == "schedule failed: 调度失败"

    def test_report_anomaly_with_string(self):
        """测试上报字符串异常"""
        anomaly = "策略状态异常"
        self.checker.report_anomaly(self.strategy, anomaly)

        # 验证监控事件上报被调用
        self.mock_bk_monitor_report_event.assert_called_once()

    def test_report_anomaly_with_dict(self):
        """测试上报字典异常"""
        anomaly = {"reason": "策略状态不匹配"}
        self.checker.report_anomaly(self.strategy, anomaly)

        self.mock_bk_monitor_report_event.assert_called_once()

    def test_report_anomaly_with_exception_object(self):
        """测试上报异常对象"""

        class CustomException(Exception):
            def __init__(self, reason):
                self.reason = reason

        anomaly = CustomException("自定义异常")
        self.checker.report_anomaly(self.strategy, anomaly)

        self.mock_bk_monitor_report_event.assert_called_once()

    def test_judge_all_expected_status_mappings(self):
        """测试EXPECTED_FLOW_STATUS中的所有状态映射"""
        from services.web.strategy_v2.tasks import EXPECTED_FLOW_STATUS

        # 测试所有期望的状态映射
        for strategy_status, expected_flow_status in EXPECTED_FLOW_STATUS.items():
            self.strategy.status = strategy_status
            self.strategy.backend_data = {"flow_id": 12345}

            # Mock返回期望的flow状态
            self.mock_bk_base_get_flow_deploy_data.return_value = {"flow_status": expected_flow_status}

            # 当实际flow状态与期望一致时，应该返回None（无异常）
            # 但对于失败状态的策略，即使flow状态匹配，也应该返回失败信息
            result = self.checker.judge(self.strategy, expected_flow_status)

            failed_statuses = ["start_failed", "update_failed", "stop_failed", "delete_failed"]
            if strategy_status in failed_statuses:
                # 失败状态的策略应该返回失败信息
                expected_failed_message = f"{strategy_status} operation failed"
                assert result == expected_failed_message, f"失败状态{strategy_status}应返回失败信息"
            else:
                # 非失败状态的策略在状态匹配时应返回None
                assert result is None, f"策略状态{strategy_status}期望flow状态{expected_flow_status}时不应报错"

            # 测试状态不匹配的情况
            if expected_flow_status != "no-start":
                # 使用一个不同的flow状态来触发不匹配
                different_status = "failure" if expected_flow_status != "failure" else "running"
                result = self.checker.judge(self.strategy, different_status)
                expected_message = f"expect_flow={expected_flow_status}, actual={different_status}"
                assert result == expected_message, f"策略状态{strategy_status}与flow状态{different_status}不匹配时应报错"

    def test_judge_missing_expected_status(self):
        """测试不在EXPECTED_FLOW_STATUS中的策略状态"""
        # 设置一个不在EXPECTED_FLOW_STATUS中的策略状态
        self.strategy.status = "unknown_status"
        self.strategy.backend_data = {"flow_id": 12345}

        # 这种情况下应该返回None（不检查未知状态）
        result = self.checker.judge(self.strategy, "running")
        assert result is None, "未知策略状态应返回None"


class TestCheckStrategyStatusAnomaliesTask(TestCase):
    """测试check_strategy_status_anomalies定时任务"""

    def setUp(self):
        """设置测试数据"""
        # Mock数据库查询
        self.mock_strategy_objects = mock.patch("services.web.strategy_v2.tasks.Strategy.objects.all").start()

        # 创建测试策略列表
        self.strategies = [
            Strategy(
                strategy_id=i,
                strategy_name=f"测试策略{i}",
                strategy_type=StrategyType.RULE,
                status=StrategyStatusChoices.RUNNING.value,
                configs={"data_source": {"source_type": RuleAuditSourceType.REALTIME}},
                backend_data={"flow_id": 10000 + i},
            )
            for i in range(3)
        ]

        self.mock_strategy_objects.return_value = self.strategies

        # Mock其他API调用
        self.mock_bk_base_get_flow_deploy_data = mock.Mock(return_value={"flow_status": "running"})

        # 应用Mock到API类
        self.get_flow_deploy_data_patch = mock.patch.object(
            GetFlowDeployData, 'perform_request', self.mock_bk_base_get_flow_deploy_data
        ).start()
        self.report_event_patch = mock.patch(
            "services.web.strategy_v2.tasks.api.bk_monitor.report_event",
            return_value={"result": True, "message": "success"},
        ).start()
        self.mock_bk_monitor_report_event = self.report_event_patch

    def tearDown(self):
        """清理Mock"""
        mock.patch.stopall()

    def test_task_execution_with_normal_strategies(self):
        """测试任务执行（所有策略正常）"""
        # Mock正常的flow状态
        self.mock_bk_base_get_flow_deploy_data.return_value = {"flow_status": "running"}

        # 执行任务
        check_strategy_status_anomalies()

        # 验证没有异常上报
        assert self.mock_bk_monitor_report_event.call_count == 0

    def test_task_execution_with_anomaly_strategies(self):
        """测试任务执行（有异常策略）"""
        # Mock异常的flow状态
        self.mock_bk_base_get_flow_deploy_data.return_value = {"flow_status": "no-start"}

        # 执行任务
        check_strategy_status_anomalies()

        # 验证异常上报被调用
        assert self.mock_bk_monitor_report_event.call_count == 3

    def test_task_execution_with_exception(self):
        """测试任务执行过程中出现异常"""
        # Mock API异常
        self.mock_bk_base_get_flow_deploy_data.side_effect = Exception("API异常")

        # 执行任务（应该不会抛出异常，而是记录错误日志）
        try:
            check_strategy_status_anomalies()
        except Exception:
            self.fail("任务执行不应该抛出异常")

    def test_task_with_mixed_strategies(self):
        """测试混合策略（实时和离线）"""
        # 修改一个策略为离线策略
        self.strategies[1].configs = {"data_source": {"source_type": RuleAuditSourceType.BATCH}}

        # Mock正常的flow状态
        self.mock_bk_base_get_flow_deploy_data.return_value = {"flow_status": "running"}

        # 执行任务
        check_strategy_status_anomalies()

        # 验证任务正常执行完成
        assert True  # 如果没有异常抛出，测试通过

# -*- coding: utf-8 -*-
import datetime
from unittest import mock

from django.core.cache import cache

from services.web.risk.constants import (
    RISK_EVENT_LATEST_TIME_KEY,
    RISK_RENDER_LOCK_KEY,
    RiskReportStatus,
)
from services.web.risk.handlers.report import RiskReportHandler
from services.web.risk.handlers.risk import RiskHandler
from services.web.risk.models import Risk, RiskReport
from services.web.risk.tasks import render_risk_report
from services.web.strategy_v2.models import Strategy
from tests.base import TestCase


class TestCanAutoGenerateReport(TestCase):
    """测试 Risk.can_auto_generate_report 方法"""

    def setUp(self):
        self.strategy = Strategy.objects.create(
            strategy_id=100,
            strategy_name="Test Strategy",
            report_enabled=True,
            report_auto_render=True,
            report_config={"template": "default"},
        )
        self.risk = Risk.objects.create(
            risk_id="test_can_auto_001",
            strategy=self.strategy,
            raw_event_id="evt_can_auto_001",
            event_time=datetime.datetime.now(),
            auto_generate_report=True,
        )

    def test_can_auto_generate_report_all_enabled(self):
        """测试所有条件都满足时返回 True"""
        self.assertTrue(self.risk.can_auto_generate_report())

    def test_can_auto_generate_report_report_enabled_false(self):
        """测试 report_enabled=False 时返回 False"""
        self.strategy.report_enabled = False
        self.strategy.save()
        self.risk.refresh_from_db()
        self.assertFalse(self.risk.can_auto_generate_report())

    def test_can_auto_generate_report_auto_render_false(self):
        """测试 report_auto_render=False 时返回 False"""
        self.strategy.report_auto_render = False
        self.strategy.save()
        self.risk.refresh_from_db()
        self.assertFalse(self.risk.can_auto_generate_report())

    def test_can_auto_generate_report_risk_auto_generate_false(self):
        """测试 risk.auto_generate_report=False 时返回 False"""
        self.risk.auto_generate_report = False
        self.risk.save()
        self.assertFalse(self.risk.can_auto_generate_report())

    def test_can_auto_generate_report_multiple_disabled(self):
        """测试多个条件同时关闭时返回 False"""
        self.strategy.report_enabled = False
        self.strategy.report_auto_render = False
        self.strategy.save()
        self.risk.auto_generate_report = False
        self.risk.save()
        self.risk.refresh_from_db()
        self.assertFalse(self.risk.can_auto_generate_report())


class TestRiskRenderTask(TestCase):
    def setUp(self):
        # Setup strategy and risk
        self.strategy = Strategy.objects.create(
            strategy_id=1, strategy_name="Test Strategy", report_enabled=True, report_config={"template": "default"}
        )
        self.risk = Risk.objects.create(
            risk_id="test_risk_001",
            strategy=self.strategy,
            raw_event_id="evt_001",
            event_time=datetime.datetime.now(),
            auto_generate_report=True,
        )
        self.lock_key = RISK_RENDER_LOCK_KEY.format(risk_id=self.risk.risk_id)
        self.latest_time_key = RISK_EVENT_LATEST_TIME_KEY.format(risk_id=self.risk.risk_id)

        # Clear cache
        cache.delete(self.lock_key)
        cache.delete(self.latest_time_key)

    @mock.patch("services.web.risk.tasks.render_risk_report.apply_async")
    def test_trigger_render_task_success(self, mock_apply_async):
        """测试：正常触发渲染任务"""
        handler = RiskHandler()
        handler.trigger_render_task(self.risk)

        # 验证 Redis 状态
        assert cache.get(self.lock_key) is not None
        assert cache.get(self.latest_time_key) is not None

        # 验证任务触发 (使用 apply_async 和 countdown)
        mock_apply_async.assert_called_once()
        call_kwargs = mock_apply_async.call_args.kwargs
        assert call_kwargs["kwargs"]["risk_id"] == self.risk.risk_id
        assert "countdown" in call_kwargs

    @mock.patch("services.web.risk.tasks.render_risk_report.apply_async")
    def test_trigger_render_task_debounce(self, mock_apply_async):
        """测试：防抖逻辑（已有锁时不触发）"""
        # 先手动上锁
        cache.set(self.lock_key, "some-other-uuid")

        handler = RiskHandler()
        handler.trigger_render_task(self.risk)

        # 验证 Redis 时间已更新
        assert cache.get(self.latest_time_key) is not None

        # 验证任务未再次触发
        mock_apply_async.assert_not_called()

    @mock.patch("services.web.risk.tasks.render_risk_report.apply_async")
    def test_trigger_render_task_disabled(self, mock_apply_async):
        """测试：功能关闭时不触发"""
        self.risk.auto_generate_report = False
        self.risk.save()

        handler = RiskHandler()
        handler.trigger_render_task(self.risk)

        mock_apply_async.assert_not_called()
        assert cache.get(self.lock_key) is None

    @mock.patch("services.web.risk.handlers.report.submit_render_task")
    def test_render_task_execution(self, mock_submit):
        """测试：任务正常执行流程（使用 submit_render_task）"""
        # Mock submit_render_task 返回的 AsyncResult
        mock_async_result = mock.MagicMock()
        mock_async_result.get.return_value = "Auto generated report"
        mock_submit.return_value = mock_async_result

        task_id = "test-task-uuid"
        # 上锁（模拟 Handler 触发，锁持有者是 task_id）
        cache.set(self.lock_key, task_id)

        # 执行任务
        render_risk_report(risk_id=self.risk.risk_id, task_id=task_id)

        # 验证 submit_render_task 被调用
        mock_submit.assert_called_once()

        # 验证 get() 被调用（同步等待）
        mock_async_result.get.assert_called_once()

        # 验证报告生成
        report = RiskReport.objects.get(risk_id=self.risk.risk_id)
        assert report.content == "Auto generated report"
        assert report.status == RiskReportStatus.AUTO

        # 验证锁释放
        assert cache.get(self.lock_key) is None

    def test_lock_ownership_fail(self):
        """测试：锁被抢占/过期，任务自动退出"""
        task_id = "my-task-uuid"
        # Redis 中是别人的锁
        cache.set(self.lock_key, "other-task-uuid")

        # 执行任务
        render_risk_report(risk_id=self.risk.risk_id, task_id=task_id)

        # 验证：没有进行渲染（因为没有 Mock render，如果执行了 render 会报错或需要 mock）
        # 我们可以验证锁没有被释放（依然是别人的）
        assert cache.get(self.lock_key) == "other-task-uuid"

    @mock.patch("services.web.risk.tasks.render_risk_report.apply_async")
    @mock.patch("services.web.risk.handlers.report.submit_render_task")
    def test_render_task_tail_trigger(self, mock_submit, mock_apply_async):
        """测试：尾部触发逻辑"""
        mock_async_result = mock.MagicMock()
        mock_async_result.get.return_value = "report content"
        mock_submit.return_value = mock_async_result

        task_id = "task-uuid-1"
        start_time = datetime.datetime.now().timestamp()

        # 模拟新事件
        new_event_time = start_time + 1000
        cache.set(self.latest_time_key, new_event_time)
        cache.set(self.lock_key, task_id)

        # 执行任务
        render_risk_report(risk_id=self.risk.risk_id, task_id=task_id)

        # 验证递归触发 (使用 apply_async 和 countdown)
        mock_apply_async.assert_called_once()
        call_kwargs = mock_apply_async.call_args.kwargs
        assert call_kwargs['kwargs']['risk_id'] == self.risk.risk_id
        assert call_kwargs['kwargs']['task_id'] != task_id  # 应该是新的 UUID
        assert 'countdown' in call_kwargs

        # 验证锁已释放（新任务会自己获取锁）
        assert cache.get(self.lock_key) is None

    def test_handler_validate_fail(self):
        """测试：校验失败释放锁"""
        self.risk.auto_generate_report = False
        self.risk.save()

        task_id = "test-uuid"
        cache.set(self.lock_key, task_id)

        handler = RiskReportHandler(self.risk.risk_id, task_id)
        handler.run()

        # 验证锁释放
        assert cache.get(self.lock_key) is None

    @mock.patch("services.web.risk.tasks.render_risk_report.retry")
    @mock.patch("services.web.risk.handlers.report.submit_render_task")
    def test_render_task_retry_on_failure(self, mock_submit, mock_retry):
        """测试：渲染失败触发重试"""
        mock_async_result = mock.MagicMock()
        mock_async_result.get.side_effect = Exception("Render service unavailable")
        mock_submit.return_value = mock_async_result

        task_id = "test-task-uuid"
        cache.set(self.lock_key, task_id)

        # 调用任务函数
        render_risk_report(risk_id=self.risk.risk_id, task_id=task_id)

        # 验证 retry 被调用且参数正确
        mock_retry.assert_called_once()
        call_kwargs = mock_retry.call_args[1]
        assert call_kwargs["countdown"] == 10
        assert isinstance(call_kwargs["exc"], Exception)
        assert "Render service unavailable" in str(call_kwargs["exc"])

    @mock.patch("services.web.risk.handlers.report.api.bk_monitor.report_event")
    @mock.patch("services.web.risk.tasks.render_risk_report.retry")
    @mock.patch("services.web.risk.handlers.report.submit_render_task")
    def test_render_task_max_retries_exceeded(self, mock_submit, mock_retry, mock_report_event):
        """测试：达到最大重试次数后正确处理"""
        mock_async_result = mock.MagicMock()
        mock_async_result.get.side_effect = Exception("Persistent failure")
        mock_submit.return_value = mock_async_result

        task_id = "test-task-uuid"
        cache.set(self.lock_key, task_id)

        # 模拟 retry 抛出 MaxRetriesExceededError（达到最大重试次数）
        from celery.exceptions import MaxRetriesExceededError

        mock_retry.side_effect = MaxRetriesExceededError("Max retries exceeded")

        # 调用任务函数
        render_risk_report(risk_id=self.risk.risk_id, task_id=task_id)

        # 验证锁被释放
        assert cache.get(self.lock_key) is None

        # 验证监控事件被上报
        mock_report_event.assert_called_once()


class TestRiskReportHandlerUnit(TestCase):
    """RiskReportHandler 单元测试 - 细粒度方法测试"""

    def setUp(self):
        self.strategy = Strategy.objects.create(
            strategy_id=2, strategy_name="Test Strategy 2", report_enabled=True, report_config={"template": "default"}
        )
        self.risk = Risk.objects.create(
            risk_id="test_risk_002",
            strategy=self.strategy,
            raw_event_id="evt_002",
            event_time=datetime.datetime.now(),
            auto_generate_report=True,
        )
        self.task_id = "handler-test-uuid"
        self.handler = RiskReportHandler(risk_id=self.risk.risk_id, task_id=self.task_id)
        self.lock_key = RISK_RENDER_LOCK_KEY.format(risk_id=self.risk.risk_id)
        self.latest_time_key = RISK_EVENT_LATEST_TIME_KEY.format(risk_id=self.risk.risk_id)

        # Clear cache
        cache.delete(self.lock_key)
        cache.delete(self.latest_time_key)

    def test_ensure_lock_ownership_renew(self):
        """测试锁续期场景"""
        # 锁属于自己
        cache.set(self.lock_key, self.task_id)

        result = self.handler._ensure_lock_ownership()

        self.assertTrue(result)
        # 验证锁仍然存在
        self.assertEqual(cache.get(self.lock_key), self.task_id)

    def test_ensure_lock_ownership_acquire(self):
        """测试新获取锁场景"""
        # 锁不存在
        cache.delete(self.lock_key)

        result = self.handler._ensure_lock_ownership()

        self.assertTrue(result)
        self.assertEqual(cache.get(self.lock_key), self.task_id)

    def test_ensure_lock_ownership_held_by_other(self):
        """测试锁被他人持有"""
        cache.set(self.lock_key, "other-task-id")

        result = self.handler._ensure_lock_ownership()

        self.assertFalse(result)
        # 验证锁未被篡改
        self.assertEqual(cache.get(self.lock_key), "other-task-id")

    def test_release_lock_ownership_check(self):
        """测试释放锁时验证所有权"""
        cache.set(self.lock_key, self.task_id)

        self.handler._release_lock()

        self.assertIsNone(cache.get(self.lock_key))

    def test_release_lock_not_delete_others(self):
        """测试不误删他人的锁"""
        cache.set(self.lock_key, "other-task-id")

        self.handler._release_lock()

        # 他人的锁应该仍然存在
        self.assertEqual(cache.get(self.lock_key), "other-task-id")

    @mock.patch("services.web.risk.tasks.render_risk_report.apply_async")
    def test_handle_tail_trigger_new_events(self, mock_apply_async):
        """测试尾部触发逻辑 - 有新事件"""
        self.handler.task_start_time = 1000.0
        cache.set(self.latest_time_key, "1500.0")  # 有新事件

        self.handler._handle_tail_trigger()

        mock_apply_async.assert_called_once()
        call_kwargs = mock_apply_async.call_args.kwargs
        self.assertEqual(call_kwargs["kwargs"]["risk_id"], self.handler.risk_id)
        self.assertNotEqual(call_kwargs["kwargs"]["task_id"], self.handler.task_id)
        self.assertIn("countdown", call_kwargs)

    @mock.patch("services.web.risk.tasks.render_risk_report.apply_async")
    def test_handle_tail_trigger_no_new_events(self, mock_apply_async):
        """测试尾部触发逻辑 - 无新事件"""
        self.handler.task_start_time = 1000.0
        cache.set(self.latest_time_key, "500.0")  # 无新事件

        self.handler._handle_tail_trigger()

        mock_apply_async.assert_not_called()

    @mock.patch("services.web.risk.tasks.render_risk_report.apply_async")
    def test_handle_tail_trigger_no_cache(self, mock_apply_async):
        """测试尾部触发逻辑 - 无缓存记录"""
        self.handler.task_start_time = 1000.0
        cache.delete(self.latest_time_key)

        self.handler._handle_tail_trigger()

        mock_apply_async.assert_not_called()

    def test_update_report_create_new(self):
        """测试创建新报告"""
        self.handler._update_report(content="Test Report Content")

        report = RiskReport.objects.get(risk_id=self.risk.risk_id)
        self.assertEqual(report.content, "Test Report Content")
        self.assertEqual(report.status, RiskReportStatus.AUTO)

    def test_update_report_update_existing(self):
        """测试更新已存在的报告"""
        # 先创建一个报告
        RiskReport.objects.create(risk=self.risk, content="Old Content", status=RiskReportStatus.MANUAL)

        self.handler._update_report(content="New Content")

        report = RiskReport.objects.get(risk_id=self.risk.risk_id)
        self.assertEqual(report.content, "New Content")
        self.assertEqual(report.status, RiskReportStatus.AUTO)

    @mock.patch.object(RiskReportHandler, "_ensure_lock_ownership", return_value=True)
    @mock.patch.object(RiskReportHandler, "_get_risk")
    @mock.patch.object(RiskReportHandler, "_render_report")
    @mock.patch.object(RiskReportHandler, "_update_report")
    @mock.patch.object(RiskReportHandler, "_release_lock")
    @mock.patch.object(RiskReportHandler, "_handle_tail_trigger")
    def test_run_success_flow(self, mock_tail, mock_release, mock_update, mock_render, mock_get_risk, mock_lock):
        """测试正常执行流程"""
        mock_risk = mock.MagicMock()
        mock_risk.can_auto_generate_report.return_value = True
        mock_get_risk.return_value = mock_risk
        mock_render.return_value = "渲染内容"

        self.handler.run()

        mock_lock.assert_called_once()
        mock_get_risk.assert_called_once()
        mock_render.assert_called_once_with(mock_risk)
        mock_update.assert_called_once()
        mock_release.assert_called_once()
        mock_tail.assert_called_once()

    @mock.patch.object(RiskReportHandler, "_ensure_lock_ownership", return_value=False)
    @mock.patch.object(RiskReportHandler, "_get_risk")
    @mock.patch.object(RiskReportHandler, "_release_lock")
    def test_run_lock_failed(self, mock_release, mock_get_risk, mock_lock):
        """测试获取锁失败时直接退出"""
        self.handler.run()

        mock_lock.assert_called_once()
        mock_get_risk.assert_not_called()
        mock_release.assert_called_once()  # finally 仍会执行

    @mock.patch.object(RiskReportHandler, "_ensure_lock_ownership", return_value=True)
    @mock.patch.object(RiskReportHandler, "_get_risk", return_value=None)
    @mock.patch.object(RiskReportHandler, "_render_report")
    @mock.patch.object(RiskReportHandler, "_release_lock")
    def test_run_risk_not_found(self, mock_release, mock_render, mock_get_risk, mock_lock):
        """测试风险不存在时退出"""
        self.handler.run()

        mock_render.assert_not_called()
        mock_release.assert_called_once()

    @mock.patch.object(RiskReportHandler, "_ensure_lock_ownership", return_value=True)
    @mock.patch.object(RiskReportHandler, "_get_risk")
    @mock.patch.object(RiskReportHandler, "_render_report")
    @mock.patch.object(RiskReportHandler, "_release_lock")
    def test_run_risk_cannot_generate(self, mock_release, mock_render, mock_get_risk, mock_lock):
        """测试风险不满足生成条件时退出"""
        mock_risk = mock.MagicMock()
        mock_risk.can_auto_generate_report.return_value = False
        mock_get_risk.return_value = mock_risk

        self.handler.run()

        mock_render.assert_not_called()
        mock_release.assert_called_once()

    @mock.patch.object(RiskReportHandler, "_ensure_lock_ownership", return_value=True)
    @mock.patch.object(RiskReportHandler, "_get_risk")
    @mock.patch.object(RiskReportHandler, "_render_report", side_effect=Exception("渲染失败"))
    @mock.patch.object(RiskReportHandler, "_release_lock")
    @mock.patch.object(RiskReportHandler, "_handle_tail_trigger")
    def test_run_render_exception(self, mock_tail, mock_release, mock_render, mock_get_risk, mock_lock):
        """测试渲染异常时正确释放锁"""
        mock_risk = mock.MagicMock()
        mock_risk.can_auto_generate_report.return_value = True
        mock_get_risk.return_value = mock_risk

        with self.assertRaises(Exception) as context:
            self.handler.run()

        self.assertIn("渲染失败", str(context.exception))
        mock_release.assert_called_once()  # finally 确保释放锁
        mock_tail.assert_not_called()  # 异常时不触发尾部

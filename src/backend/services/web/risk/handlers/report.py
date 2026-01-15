# -*- coding: utf-8 -*-
import datetime
import uuid
from typing import Optional

from blueapps.utils.logger import logger
from django.conf import settings
from django.core.cache import cache
from django.utils.translation import gettext

from apps.notice.handlers import ErrorMsgHandler
from services.web.risk.constants import (
    RISK_EVENT_LATEST_TIME_KEY,
    RISK_RENDER_LOCK_KEY,
    RiskReportStatus,
)
from services.web.risk.models import Risk, RiskReport
from services.web.risk.report.task_submitter import submit_render_task
from services.web.risk.report_config import ReportConfig


class RiskReportHandler:
    """
    风险报告渲染处理器
    负责：锁管理、前置校验、渲染执行、尾部触发检测
    """

    def __init__(self, risk_id: str, task_id: str):
        self.risk_id = risk_id
        self.task_id = task_id
        self.lock_key = RISK_RENDER_LOCK_KEY.format(risk_id=risk_id)
        self.latest_event_time_key = RISK_EVENT_LATEST_TIME_KEY.format(risk_id=risk_id)
        # 记录 Handler 初始化时间作为任务开始时间
        self.task_start_time = datetime.datetime.now().timestamp()

    def run(self):
        """
        执行渲染流程

        流程：
        1. 验证/获取锁
        2. 业务逻辑（获取风险、校验、渲染、更新）
        3. finally 释放锁
        4. 正常完成后检查尾部触发
        """
        logger.info(f"[RiskReportHandler] Start rendering for risk_id={self.risk_id}, task_id={self.task_id}")

        try:
            # 1. 验证/获取锁
            if not self._ensure_lock_ownership():
                logger.info(f"[RiskReportHandler] Failed to acquire lock. risk_id={self.risk_id}")
                return

            # 2. 获取风险单
            risk = self._get_risk()
            if not risk:
                logger.info(f"[RiskReportHandler] Risk not found. risk_id={self.risk_id}")
                return

            # 3. 校验风险单 (策略开启、报告开启)
            if not risk.can_generate_report():
                logger.info(f"[RiskReportHandler] Render disabled. risk_id={self.risk_id}")
                return

            # 4. 执行渲染
            report_content = self._render_report(risk)

            # 5. 更新前再次校验 (防止渲染期间配置变更)
            try:
                risk.refresh_from_db()
            except Risk.DoesNotExist:
                logger.info(f"[RiskReportHandler] Risk not found during execution. risk_id={self.risk_id}")
                return

            if not risk.can_generate_report():
                logger.info(f"[RiskReportHandler] Render disabled during execution. risk_id={self.risk_id}")
                return

            # 6. 更新报告
            self._update_report(content=report_content)

        finally:
            # 统一释放锁
            self._release_lock()

        # 7. 正常完成后检查尾部触发（在 finally 之后执行）
        self._handle_tail_trigger()

    def handle_max_retries_exceeded(self, exc: Exception):
        """
        处理重试次数耗尽的情况

        即使当前任务失败，也需要检查是否有新事件等待处理
        """
        logger.error(f"[RiskReportHandler] Max retries reached. risk_id={self.risk_id}, error={exc}")
        ErrorMsgHandler(gettext("Render Risk Report Failed"), f"RiskID: {self.risk_id}\nError: {exc}").send()

        # 检查是否需要尾部触发（让新事件有机会被处理）
        self._handle_tail_trigger()

    def _ensure_lock_ownership(self) -> bool:
        """
        验证锁所有权，如果锁不存在则尝试获取

        场景：
        1. 锁属于自己 → 续期并返回 True
        2. 锁不存在 → 尝试获取（nx=True 防止并发）
        3. 锁被他人持有 → 返回 False
        """
        current_lock = cache.get(self.lock_key)

        if current_lock == self.task_id:
            # 锁属于自己，续期
            cache.set(self.lock_key, self.task_id, timeout=settings.RENDER_TASK_TIMEOUT)
            return True
        elif current_lock is None:
            # 锁不存在，尝试获取（nx=True 防止并发）
            return cache.set(self.lock_key, self.task_id, nx=True, timeout=settings.RENDER_TASK_TIMEOUT)

        # 锁被他人持有
        return False

    def _release_lock(self):
        """释放锁（需验证所有权）"""
        current_lock = cache.get(self.lock_key)
        if current_lock == self.task_id:
            cache.delete(self.lock_key)
            logger.info(f"[RiskReportHandler] Lock released. risk_id={self.risk_id}")
        else:
            logger.info(f"[RiskReportHandler] Lock not owned. risk_id={self.risk_id}")

    def _get_risk(self) -> Optional[Risk]:
        """获取风险单"""
        try:
            return Risk.objects.select_related("strategy").get(risk_id=self.risk_id)
        except Risk.DoesNotExist:
            logger.error(f"[RiskReportHandler] Risk not found. risk_id={self.risk_id}")
            return None

    def _render_report(self, risk: Risk) -> str:
        """
        调用渲染器生成报告

        使用 submit_render_task 提交渲染任务，同步等待结果
        """
        # 解析报告配置
        report_config = ReportConfig.model_validate(risk.strategy.report_config)

        # 提交渲染任务并同步等待结果（简化调用）
        async_result = submit_render_task(risk=risk, report_config=report_config)

        # 同步等待渲染结果（阻塞直到完成）
        try:
            result = async_result.get(timeout=settings.RENDER_TASK_TIMEOUT)
            return result if isinstance(result, str) else str(result)
        except Exception as e:
            logger.exception(f"[RiskReportHandler] Render task failed: {e}")
            raise

    def _update_report(self, content: str):
        """更新报告内容"""
        RiskReport.objects.update_or_create(
            risk_id=self.risk_id, defaults={"content": content, "status": RiskReportStatus.AUTO}
        )
        logger.info(f"[RiskReportHandler] Render success. risk_id={self.risk_id}")

    def _handle_tail_trigger(self):
        """
        处理尾部触发：检查是否有新事件，直接触发新任务
        """
        latest_event_time = cache.get(self.latest_event_time_key)

        if latest_event_time and float(latest_event_time) > self.task_start_time:
            logger.info(f"[RiskReportHandler] New events arrived. Triggering new task. risk_id={self.risk_id}")

            # 直接触发新任务，新任务会自己获取锁
            from services.web.risk.tasks import render_risk_report

            render_risk_report.delay(risk_id=self.risk_id, task_id=str(uuid.uuid4()))
        else:
            logger.info(f"[RiskReportHandler] No new events. Task completed. risk_id={self.risk_id}")

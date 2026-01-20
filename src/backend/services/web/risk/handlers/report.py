# -*- coding: utf-8 -*-
import datetime
import uuid
from typing import Optional

from bk_resource import api
from blueapps.utils.logger import logger
from django.conf import settings
from django.core.cache import cache
from django.db import IntegrityError, transaction

from core.exceptions import ApiRequestError
from services.web.common.monitor import RiskReportRenderFailedEvent
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
        logger.info("[RiskReportHandler] Start rendering for risk_id=%s, task_id=%s", self.risk_id, self.task_id)

        try:
            # 1. 验证/获取锁
            if not self._ensure_lock_ownership():
                logger.info(
                    "[RiskReportHandler] Failed to acquire lock. risk_id=%s, task_id=%s", self.risk_id, self.task_id
                )
                return

            # 2. 获取风险单
            risk = self._get_risk()
            if not risk:
                logger.info("[RiskReportHandler] Risk not found. risk_id=%s, task_id=%s", self.risk_id, self.task_id)
                return

            # 3. 校验风险单 (策略开启、报告开启)
            if not risk.can_auto_generate_report():
                logger.info("[RiskReportHandler] Render disabled. risk_id=%s, task_id=%s", self.risk_id, self.task_id)
                return

            # 4. 执行渲染
            report_content = self._render_report(risk)

            # 5. 更新前再次校验 (防止渲染期间配置变更)
            try:
                risk.refresh_from_db()
            except Risk.DoesNotExist:
                logger.info(
                    "[RiskReportHandler] Risk not found during execution. risk_id=%s, task_id=%s",
                    self.risk_id,
                    self.task_id,
                )
                return

            if not risk.can_auto_generate_report():
                logger.info(
                    "[RiskReportHandler] Render disabled during execution. risk_id=%s, task_id=%s",
                    self.risk_id,
                    self.task_id,
                )
                return

            # 6. 更新报告
            self._update_report(content=report_content)

            logger.info("[RiskReportHandler] End rendering for risk_id=%s, task_id=%s", self.risk_id, self.task_id)
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
        logger.error(
            "[RiskReportHandler] Max retries reached. risk_id=%s, task_id=%s, error=%s", self.risk_id, self.task_id, exc
        )

        # 上报监控事件
        event = RiskReportRenderFailedEvent(
            target=f"risk_{self.risk_id}",
            context={"risk_id": self.risk_id, "task_id": self.task_id},
            extra={"error": str(exc)},
        )
        try:
            api.bk_monitor.report_event(event.to_json())
            logger.info("[RiskReportHandler] Report event success. risk_id=%s, task_id=%s", self.risk_id, self.task_id)
        except ApiRequestError as e:
            logger.error(
                "[RiskReportHandler] Report event failed. risk_id=%s, task_id=%s, error=%s",
                self.risk_id,
                self.task_id,
                e,
            )

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
            logger.info("[RiskReportHandler] Lock released. risk_id=%s, task_id=%s", self.risk_id, self.task_id)
        else:
            logger.info(
                "[RiskReportHandler] Lock not owned. risk_id=%s, task_id=%s, current_lock=%s",
                self.risk_id,
                self.task_id,
                current_lock,
            )

    def _get_risk(self) -> Optional[Risk]:
        """获取风险单"""
        try:
            return Risk.objects.select_related("strategy").get(risk_id=self.risk_id)
        except Risk.DoesNotExist:
            logger.error("[RiskReportHandler] Risk not found. risk_id=%s, task_id=%s", self.risk_id, self.task_id)
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
            logger.info("[RiskReportHandler] Render task completed. risk_id=%s, task_id=%s", self.risk_id, self.task_id)
            return result if isinstance(result, str) else str(result)
        except Exception as e:
            logger.exception(
                "[RiskReportHandler] Render task failed: risk_id=%s, task_id=%s, error=%s",
                self.risk_id,
                self.task_id,
                e,
            )
            raise

    def _update_report(self, content: str):
        """更新报告内容"""
        try:
            # 1. 尝试直接创建（最快，且原子）
            # 使用 atomic 包裹，确保 IntegrityError 只回滚这个 savepoint，不破坏外层事务
            with transaction.atomic():
                RiskReport.objects.create(risk_id=self.risk_id, content=content, status=RiskReportStatus.AUTO)
            logger.info("[RiskReportHandler] Report created. risk_id=%s", self.risk_id)
        except IntegrityError:
            # 2. 如果已存在（违反唯一约束），则更新
            RiskReport.objects.filter(risk_id=self.risk_id).update(content=content, status=RiskReportStatus.AUTO)
            logger.info("[RiskReportHandler] Report updated. risk_id=%s", self.risk_id)

    def _handle_tail_trigger(self):
        """
        处理尾部触发：检查是否有新事件，直接触发新任务
        """
        latest_event_time = cache.get(self.latest_event_time_key)

        if latest_event_time and float(latest_event_time) > self.task_start_time:
            new_task_id = str(uuid.uuid4())
            logger.info(
                "[RiskReportHandler] New events arrived. Triggering new task with %ds delay. "
                "risk_id=%s, current_task_id=%s, new_task_id=%s",
                settings.RENDER_TASK_DELAY,
                self.risk_id,
                self.task_id,
                new_task_id,
            )

            # 直接触发新任务，新任务会自己获取锁
            from services.web.risk.tasks import render_risk_report

            render_risk_report.apply_async(
                kwargs={"risk_id": self.risk_id, "task_id": new_task_id},
                countdown=settings.RENDER_TASK_DELAY,
            )
        else:
            logger.info(
                "[RiskReportHandler] No new events. Task completed. risk_id=%s, task_id=%s",
                self.risk_id,
                self.task_id,
            )

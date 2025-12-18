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
from datetime import datetime, timedelta
from typing import Optional

from bk_resource import api
from blueapps.contrib.celery_tools.periodic import periodic_task
from blueapps.core.celery import celery_app
from blueapps.utils.logger import logger_celery
from celery.schedules import crontab
from django.conf import settings
from django.db.models import Count, Max, QuerySet

from core.lock import lock
from services.web.query.constants import TaskEnum
from services.web.query.export.data_fetcher import DataFetcher
from services.web.query.export.data_processor import DataProcessor
from services.web.query.export.export import CollectorLogExporter
from services.web.query.export.file_exporter import XLSXExporter
from services.web.query.export.file_uploader import BKRepoUploader
from services.web.query.export.model import ExportConfig
from services.web.query.models import ExportFieldLog, LogExportTask
from services.web.query.utils.storage import LogExportStorage


@periodic_task(run_every=crontab(hour="*/1"))
@lock(load_lock_name=lambda **kwargs: "celery:clean_duplicate_export_fields")
def clean_duplicate_export_fields():
    """
    清理重复的导出字段配置，保留每组(raw_name+keys+display_name)的最新记录
    """

    # 时间范围
    end_time = datetime.now()
    start_time = end_time - timedelta(seconds=settings.LOG_FIELD_CLEAR_PERIODIC_TIME)

    # 找出需要保留的最新记录ID
    latest_ids = (
        ExportFieldLog.objects.filter(created_at__range=[start_time, end_time])
        .values("raw_name", "keys", "display_name")
        .annotate(latest_id=Max("id"))
        .values_list("latest_id", flat=True)
    )

    # 删除不在最新ID列表中的记录
    deleted_count, _ = (
        ExportFieldLog.objects.filter(created_at__range=[start_time, end_time]).exclude(id__in=latest_ids).delete()
    )

    logger_celery.info(f"Cleaned {deleted_count} duplicate export fields in {start_time} and {end_time}")


@periodic_task(
    run_every=crontab(minute=settings.PROCESS_LOG_EXPORT_TASK_MINUTE),
    queue="log_export",
    time_limit=settings.DEFAULT_CACHE_LOCK_TIMEOUT,
)
@lock(
    load_lock_name=lambda task_id=None, **kwargs: f"celery:process_log_export_task:{task_id}",
)
def process_log_export_task(task_id: int = None):
    """
    处理日志导出任务
    """

    end_time = datetime.now()
    start_time = end_time - timedelta(seconds=settings.LOG_EXPORT_TASK_MAX_PERIODIC_TIME)
    tasks: QuerySet[LogExportTask] = LogExportTask.objects.filter(updated_at__range=[start_time, end_time]).filter(
        status__in=TaskEnum.get_schedule_status(),
        repeat_times__lte=settings.PROCESS_LOG_EXPORT_TASK_MAX_REPEAT_TIMES,
    )
    if task_id:
        tasks = tasks.filter(id=task_id)
    for task in tasks:
        process_one_log_export_task.apply_async(kwargs={"task_id": task.id})


@celery_app.task(queue="log_export", time_limit=settings.PROCESS_LOG_EXPORT_TASK_LOCK_TIMEOUT)
@lock(
    load_lock_name=lambda task_id, **kwargs: f"celery:process_one_log_export_task:{task_id}",
)
def process_one_log_export_task(task_id: int):
    """
    处理单个日志导出任务
    """

    # 更新任务状态
    task: Optional[LogExportTask] = LogExportTask.objects.filter(id=task_id).first()
    if not task or task.status not in TaskEnum.get_schedule_status():
        return
    task.update_task_running()
    # 执行导出任务
    try:
        config = ExportConfig(task=task)
        CollectorLogExporter(
            config=config,
            data_fetcher=DataFetcher(config=config),
            data_processor=DataProcessor(config=config),
            file_exporter=XLSXExporter(config=config),
            file_uploader=BKRepoUploader(config=config),
        ).export()
    except Exception as e:  # pylint: disable=broad-except
        task.update_task_failed(str(e))
        raise e


@periodic_task(
    run_every=crontab(minute=settings.PROCESS_EXPIRED_LOG_TASK_HOUR),
    queue="log_export",
    time_limit=settings.DEFAULT_CACHE_LOCK_TIMEOUT,
)
@lock(
    load_lock_name=lambda task_id=None, **kwargs: f"celery:process_expired_log_task:{task_id}",
)
def process_expired_log_task(task_id: int = None):
    """
    处理过期的日志导出任务，将他们的文件删除掉，并将任务设置为过期
    :param task_id: 任务 ID；如果给定则加上这个筛选，没有给定则全部过期任务
    """

    storage = LogExportStorage()
    # 过期任务的时间范围
    start_time = datetime.now() - timedelta(days=settings.PROCESS_EXPIRED_LOG_TASK_MAX_DURATION)
    end_time = datetime.now() - timedelta(days=settings.LOG_EXPORT_MAX_DURATION)
    expired_tasks: QuerySet[LogExportTask] = LogExportTask.objects.filter(
        task_end_time__range=[start_time, end_time],
        status__in=[TaskEnum.SUCCESS.value],
    )
    if task_id:
        expired_tasks = expired_tasks.filter(id=task_id)
    for task in expired_tasks:
        try:
            if task.result and "storage_name" in task.result:
                storage.delete(task.result["storage_name"])
                task.update_task_expired()
                logger_celery.info(f"Processed expired task {task.id}")
            else:
                logger_celery.warning(f"Task has no result {task.id}")
        except Exception as e:  # pylint: disable=broad-except
            logger_celery.error(f"Failed to process expired task {task.id}: {e}")


@periodic_task(
    run_every=crontab(hour=settings.PROCESS_STUCK_LOG_TASK_HOUR),  # 每小时执行一次
    queue="log_export",
    time_limit=settings.DEFAULT_CACHE_LOCK_TIMEOUT,
)
@lock(
    load_lock_name=lambda **kwargs: "celery:handle_stuck_log_tasks",
)
def handle_stuck_running_tasks():
    """
    处理状态为运行中且卡住的日志导出任务（超过1小时未更新视为卡住）
    """
    # 时间范围配置（默认7天）
    max_search_days = settings.STUCK_TASK_SEARCH_DAYS
    search_start_time = datetime.now() - timedelta(days=max_search_days)

    # 卡住时间（1小时）
    stuck_time_threshold = datetime.now() - timedelta(hours=1)

    # 查询最近7天内，状态为RUNNING、超过1小时未更新、且未超过最大重试次数的任务
    stuck_tasks = LogExportTask.objects.filter(
        created_at__gte=search_start_time,  # 限制查询时间范围
        status=TaskEnum.RUNNING.value,
        updated_at__lte=stuck_time_threshold,
    )

    for task in stuck_tasks:
        try:
            # 更新任务状态为失败，并记录错误信息
            task.update_task_failed("Task stuck in 'RUNNING' status for over 1 hour")
            logger_celery.info(f"Marked stuck task {task.id} as FAILURE")
        except Exception as e:
            logger_celery.error(f"Failed to process task {task.id}: {str(e)}")


@periodic_task(
    run_every=crontab(hour=settings.PROCESS_STUCK_LOG_TASK_HOUR),
    queue="log_export",
    time_limit=settings.DEFAULT_CACHE_LOCK_TIMEOUT,
)
@lock(load_lock_name=lambda **kwargs: "celery:report_log_export_task_metrics")
def report_log_export_task_metrics():
    """
    每小时上报日志导出任务状态指标：READY、RUNNING、FAILURE、EXPIRED 的任务数量
    """

    now = datetime.now()
    timestamp = int(now.timestamp() * 1000)

    status_counts = LogExportTask.objects.values("status").annotate(count=Count("id"))
    status_map = {
        TaskEnum.READY.value: 0,
        TaskEnum.RUNNING.value: 0,
        TaskEnum.FAILURE.value: 0,
        TaskEnum.EXPIRED.value: 0,
        TaskEnum.SUCCESS.value: 0,
    }
    for entry in status_counts:
        status = entry["status"]
        if status in status_map:
            status_map[status] = entry["count"]
    payload = {
        "data_id": settings.LOG_EXPORT_STATUS_DATA_ID,
        "access_token": settings.LOG_EXPORT_STATUS_ACCESS_TOKEN,
        "data": [
            {
                "metrics": {"value": count},
                "target": "bk_audit",
                "dimension": {
                    "module": "log_export",
                    "location": "report_log_export_task_metrics",
                    "status": status,
                },
                "timestamp": timestamp,
            }
            for status, count in status_map.items()
        ],
    }

    try:
        api.bk_monitor.report_metric(payload)
        logger_celery.info(f"[report_log_export_task_metrics] 上报成功: {status_map}")
    except Exception as e:
        logger_celery.error(f"[report_log_export_task_metrics] 上报失败: {e}")


@periodic_task(
    run_every=crontab(hour=settings.PROCESS_STUCK_LOG_TASK_HOUR),
    queue="log_export",
    time_limit=settings.DEFAULT_CACHE_LOCK_TIMEOUT,
)
@lock(load_lock_name=lambda **kwargs: "celery:alert_failed_export_tasks")
def alert_failed_export_tasks():
    """
    扫描失败次数超过最大重试次数的任务进行告警
    """
    max_retries = settings.PROCESS_LOG_EXPORT_TASK_MAX_REPEAT_TIMES
    tasks = LogExportTask.objects.filter(
        status=TaskEnum.FAILURE.value, repeat_times__gte=max_retries, alert_sented=False
    )

    for task in tasks:
        try:
            now = datetime.now()
            timestamp = int(now.timestamp() * 1000)
            error_msg = task.error_msg
            payload = {
                "data_id": settings.ALERT_DATA_ID,
                "access_token": settings.ALERT_ACCESS_TOKEN,
                "data": [
                    {
                        "event_name": f"log_export_failed_task_{task.id}",
                        "event": {"content": f"任务 {task.id} 连续失败 {task.repeat_times} 次，错误信息: {error_msg}"},
                        "target": task.id,
                        "timestamp": timestamp,
                    }
                ],
            }

            api.bk_monitor.report_event(payload)
            logger_celery.info(f"失败任务告警上报成功，任务 ID={task.id}")

            # Update task status
            task.alert_sented = True
            task.save(update_fields=["alert_sented"])
            logger_celery.info(f"告警已发送，任务 ID={task.id}")

        except Exception as e:
            logger_celery.error(f"任务告警处理失败，任务 ID={task.id}, 错误: {str(e)}")

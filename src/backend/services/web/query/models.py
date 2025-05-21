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
from datetime import datetime

from bk_resource import resource
from blueapps.utils.db import MultiStrSplitCharField
from django.db import models
from django.utils.translation import gettext_lazy

from apps.notice.constants import MsgType, RelateType
from core.models import OperateRecordModel, SoftDeleteModel
from services.web.query.constants import TaskEnum


class ExportFieldLog(OperateRecordModel):
    """
    导出字段展示配置
    """

    raw_name = models.CharField(gettext_lazy("字段名称"), max_length=64, db_index=True)
    keys = MultiStrSplitCharField(gettext_lazy("字段键"), default="", blank=True, max_length=512, db_index=True)
    display_name = models.CharField(gettext_lazy("展示名称"), max_length=255, db_index=True)

    class Meta:
        verbose_name = gettext_lazy("字段展示配置")
        verbose_name_plural = verbose_name


class LogExportTask(SoftDeleteModel):
    """
    日志导出任务
    """

    namespace = models.CharField(gettext_lazy("namespace"), max_length=32, db_index=True)
    name = models.CharField(gettext_lazy("任务名称"), max_length=64, db_index=True, blank=True, default="")
    repeat_times = models.IntegerField(gettext_lazy("任务执行次数"), default=0)
    status = models.CharField(gettext_lazy("任务状态"), max_length=32, choices=TaskEnum.choices)
    result = models.JSONField(verbose_name=gettext_lazy("任务执行结果"), default=dict, blank=True, null=True)
    task_start_time = models.DateTimeField(gettext_lazy("任务执行开始时间"), null=True, default=None)
    task_end_time = models.DateTimeField(gettext_lazy("任务执行结束时间"), null=True, default=None)
    error_msg = models.TextField(gettext_lazy("错误信息"), blank=True, null=True)

    query_params = models.JSONField(gettext_lazy("检索参数"), default=dict, blank=True)
    export_config = models.JSONField(gettext_lazy("导出配置"), default=dict, blank=True)
    current_records = models.IntegerField(gettext_lazy("当前记录数"), default=0)
    total = models.IntegerField(gettext_lazy("总条数"), default=0)
    search_params_url = models.TextField(gettext_lazy("查询参数URL"), blank=True, null=True)

    class Meta:
        verbose_name = gettext_lazy("日志导出任务")
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]

    def update_current_records(self, current_records: int):
        """
        更新当前记录数
        """

        self.current_records = current_records
        self.save(update_fields=["current_records"])

    def update_task_success(self, current_records: int, result: dict):
        """
        更新任务状态为成功
        """

        self.error_msg = ""
        self.result = result
        self.task_end_time = datetime.now()
        self.current_records = current_records
        self.status = TaskEnum.SUCCESS.value
        self.save(update_fields=["error_msg", "result", "task_end_time", "current_records", "status"])

    def update_task_failed(self, error_msg: str):
        """
        更新任务状态为失败
        """

        self.status = TaskEnum.FAILURE.value
        self.error_msg = error_msg
        self.current_records = 0
        self.save(update_fields=["status", "error_msg", "current_records"])

    def update_task_running(self):
        """
        更新任务状态为运行中
        """

        self.status = TaskEnum.RUNNING.value
        self.task_start_time = datetime.now()
        self.repeat_times += 1
        self.save(update_fields=["status", "task_start_time", "repeat_times"])

    def update_task_expired(self):
        """
        更新任务状态为过期
        """

        self.status = TaskEnum.EXPIRED.value
        self.save(update_fields=["status"])

    def send_notify(self):
        """
        发送通知
        """

        resource.notice.send_notice(
            relate_type=RelateType.LOG_EXPORT,
            relate_id=self.id,
            agg_key=self.id,
            msg_type=[MsgType.MAIL],
            receivers=[self.created_by],
        )


class TaskDownloadRecord(models.Model):
    """
    任务下载记录表
    """

    task = models.ForeignKey(
        LogExportTask,
        on_delete=models.CASCADE,
        verbose_name=gettext_lazy("关联任务"),
        related_name="download_records",
    )
    downloaded_at = models.DateTimeField(
        gettext_lazy("下载时间"),
        auto_now_add=True,
    )
    downloaded_by = models.CharField(
        gettext_lazy("下载用户"),
        max_length=64,
        db_index=True,
    )

    class Meta:
        verbose_name = gettext_lazy("任务下载记录")
        verbose_name_plural = verbose_name
        ordering = ["-downloaded_at"]

    @classmethod
    def create_download_record(cls, task: LogExportTask, username: str):
        """
        创建下载记录
        :param task: 关联的任务
        :param username: 下载用户
        """

        return cls.objects.create(task=task, downloaded_by=username)

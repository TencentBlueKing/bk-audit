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
import traceback
from datetime import datetime

from blueapps.utils.logger import logger_celery
from django.core.files import File

from services.web.query.export.data_fetcher import DataFetcher
from services.web.query.export.data_processor import DataProcessor
from services.web.query.export.file_exporter import FileExporter
from services.web.query.export.file_uploader import FileUploader
from services.web.query.export.model import ExportConfig


class CollectorLogExporter:
    """
    检索日志导出器
    """

    def __init__(
        self,
        config: ExportConfig,
        data_fetcher: DataFetcher,
        data_processor: DataProcessor,
        file_exporter: FileExporter,
        file_uploader: FileUploader,
    ):
        self.config = config
        self.task = self.config.task
        self.data_fetcher = data_fetcher
        self.data_processor = data_processor
        self.file_exporter = file_exporter
        self.file_uploader = file_uploader
        self.current_records = 0

    def _finally_export(self):
        """
        最终的收尾工作
        """

        self.file_exporter.close()

    def search_and_write_file(self) -> File:
        """
        分页检索日志，处理并写入文件
        1. 分页检索日志
        2. 格式化数据
        3. 导出日志
        4. 上传文件
        """

        # 1. 分页检索日志
        for log_data in self.data_fetcher.fetch_logs():
            logger_celery.info(
                f"[{self.__class__.__name__}] fetch logs done; task {self.task.id}; data_count: {len(log_data)}"
            )
            # 2. 数据处理
            formatted_logs = self.data_processor.batch_format_data(log_data)
            logger_celery.info(
                f"[{self.__class__.__name__}] format logs done; task {self.task.id}; "
                f"formatted_logs_count: {len(formatted_logs)}"
            )
            # 3. 导出日志
            self.file_exporter.write(formatted_logs)
            logger_celery.info(
                f"[{self.__class__.__name__}] write logs done; task {self.task.id}; "
                f"written_logs_count: {len(formatted_logs)}"
            )
            # 4. 更新记录日志条数
            self.current_records += len(formatted_logs)
            self.task.update_current_records(current_records=self.current_records)
            logger_celery.info(
                f"[{self.__class__.__name__}] record logs done; task {self.task.id}; "
                f"current_logs_count: {self.current_records}"
            )
        return self.file_exporter.save()

    def export(self):
        """
        1. 检索日志并写入文件
            2.1 分页检索日志
            2.2 数据处理
            2.3 写入文件
        2. 上传文件
        3. 更新任务状态
        4. 消息通知
        """

        task_start_time = datetime.now()
        logger_celery.info(f"[{self.__class__.__name__}] export start; task {self.task.id}")
        try:
            # 1. 检索日志并写入文件
            file_obj = self.search_and_write_file()
            logger_celery.info(f"[{self.__class__.__name__}] search and write done; task {self.task.id}")
            # 2. 上传文件
            file_name = self.file_exporter.file_name
            logger_celery.info(
                f"[{self.__class__.__name__}] upload file start; task {self.task.id}; file_name: {file_name}"
            )
            upload_result = self.file_uploader.upload(file_obj, file_name)
            logger_celery.info(
                f"[{self.__class__.__name__}] upload file done; task {self.task.id}; file_name: {file_name}"
                f"upload_result: {upload_result}"
            )
            # 3. 更新任务状态
            self.task.update_task_success(
                current_records=self.current_records,
                result=upload_result.model_dump(),
            )
            logger_celery.info(
                f"[{self.__class__.__name__}] export success; task {self.task.id}; "
                f"consume_seconds: {(datetime.now() - task_start_time).total_seconds()}"
            )
            # 4. 消息通知
            self.task.send_notify()
            logger_celery.info(f"[{self.__class__.__name__}] notify done; task {self.task.id}")
        except Exception as e:  # NOCC:broad-except(需要处理所有错误)
            logger_celery.error(
                f"[{self.__class__.__name__}] export failed; task {self.task.id}; Err:{e}; "
                f"Detail => {traceback.format_exc()}"
            )
            self.task.update_task_failed(str(e))
        finally:
            # 4. 清理资源
            self._finally_export()
            logger_celery.info(f"[{self.__class__.__name__}] export finish; task {self.task.id}")

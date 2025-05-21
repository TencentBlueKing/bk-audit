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

from blueapps.utils.logger import logger
from django.core.files import File

from core.utils.retry import FuncRunner
from services.web.query.constants import LOG_EXPORT_FILE_NAME_FORMAT, FileExportResult
from services.web.query.export.model import ExportConfig
from services.web.query.utils.storage import LogExportStorage


class FileUploader(abc.ABC):
    def __init__(self, config: ExportConfig):
        self.config = config
        self.namespace = self.config.task.namespace

    @abc.abstractmethod
    def upload(self, file_obj: File, file_name: str) -> FileExportResult:
        raise NotImplementedError()


class BKRepoUploader(FileUploader):
    def __init__(self, config: ExportConfig):
        super().__init__(config=config)
        self.storage = LogExportStorage()

    def upload(self, file_obj: File, file_name: str) -> FileExportResult:
        file_path = LOG_EXPORT_FILE_NAME_FORMAT.format(namespace=self.namespace, file_name=file_name)
        # 保存文件
        file_obj.seek(0)
        storage_name = FuncRunner(func=self.storage.save, kwargs={"name": file_path, "content": File(file_obj)}).run()
        logger.info(f"save file success; storage_name: {storage_name}; file_path: {file_path}")
        return FileExportResult(
            url=self.storage.url(storage_name),
            size=self.storage.size(storage_name),
            origin_name=file_name,
            storage_name=storage_name,
        )

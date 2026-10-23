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
import math
from typing import Generator, List

from bk_resource import resource
from django.conf import settings

from core.utils.retry import FuncRunner
from services.web.query.exceptions import LogExportMaxCountError
from services.web.query.export.model import ExportConfig


class DataFetcher:
    """
    数据获取模块
    """

    def __init__(self, config: ExportConfig, page_size: int = settings.LOG_EXPORT_TASK_PAGE_SIZE):
        self.config = config
        self.page_size = page_size

    @classmethod
    def _fetch_data(cls, query_params: dict, page: int, page_size: int, *, query_timeout: float | None = None):
        """
        分页获取日志数据
        """

        query_params = query_params.copy()
        query_params["page"] = page
        query_params["page_size"] = page_size
        if query_timeout is not None:
            # 同步请求不重试，避免退避和重复查询耗尽预算；普通异步导出保留原重试。
            query_params["query_timeout"] = query_timeout
            return resource.query.collector_search_all(**query_params)
        resp = FuncRunner(
            func=resource.query.collector_search_all,
            kwargs=query_params,
        ).run()
        return resp

    @classmethod
    def get_total(cls, query_params: dict, *, query_timeout: float | None = None) -> int:
        """
        获取总条数
        """

        resp = cls._fetch_data(query_params, 1, 1, query_timeout=query_timeout)
        return resp["total"]

    @classmethod
    def fetch_patch_logs(cls, query_params: dict, page: int, page_size: int, *, query_timeout: float | None = None):
        """
        分页检索日志
        """

        resp = cls._fetch_data(query_params, page, page_size, query_timeout=query_timeout)
        return resp["results"]

    def fetch_logs(self) -> Generator[List[dict], None, None]:
        """
        检索日志
        """

        total = self.get_total(self.config.task.query_params)
        # 更新总条数
        if total != self.config.task.total:
            self.config.task.total = total
            self.config.task.save(update_fields=["total"])
        if total > settings.LOG_EXPORT_MAX_COUNT:
            raise LogExportMaxCountError(current_count=total, max_count=settings.LOG_EXPORT_MAX_COUNT)
        for i in range(0, math.ceil(total / self.page_size)):
            yield self.fetch_patch_logs(self.config.task.query_params, i + 1, self.page_size)

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
from services.web.query.export.model import ExportConfig


class DataFetcher:
    """
    数据获取模块
    """

    def __init__(self, config: ExportConfig, page_size: int = settings.LOG_EXPORT_TASK_PAGE_SIZE):
        self.config = config
        self.page_size = page_size

    @classmethod
    def _fetch_data(cls, query_params: dict, page: int, page_size: int):
        """
        分页获取日志数据
        """

        query_params = query_params.copy()
        query_params["page"] = page
        query_params["page_size"] = page_size
        resp = FuncRunner(
            func=resource.query.collector_search_all,
            kwargs=query_params,
        ).run()
        return resp

    @classmethod
    def get_total(cls, query_params: dict) -> int:
        """
        获取总条数
        """

        resp = cls._fetch_data(query_params, 1, 1)
        return resp["total"]

    @classmethod
    def fetch_patch_logs(cls, query_params: dict, page: int, page_size: int):
        """
        分页检索日志
        """

        resp = cls._fetch_data(query_params, page, page_size)
        return resp["results"]

    def fetch_logs(self) -> Generator[List[dict], None, None]:
        """
        检索日志
        """

        total = self.get_total(self.config.task.query_params)
        for i in range(0, math.ceil(total / self.page_size)):
            yield self.fetch_patch_logs(self.config.task.query_params, i + 1, self.page_size)

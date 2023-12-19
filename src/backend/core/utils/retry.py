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

import random
import time

from bk_resource.base import Empty
from blueapps.utils.logger import logger
from django.conf import settings


class FuncRunner:
    """
    可重试的执行器
    """

    def __init__(
        self,
        func: callable,
        args: tuple = None,
        kwargs: dict = None,
        max_retry: int = None,
        retry_sleep: float = None,
        max_retry_sleep: float = None,
    ):
        self.func = func
        self.args = args or tuple()
        self.kwargs = kwargs or {}
        self.max_retry = max_retry or settings.DEFAULT_MAX_RETRY
        self.retry_sleep = retry_sleep or settings.DEFAULT_RETRY_SLEEP_TIME
        self.max_retry_sleep = max_retry_sleep or settings.DEFAULT_MAX_RETRY_SLEEP_TIME

    def run(self) -> any:
        cur_retry = 0
        error = None
        while cur_retry < self.max_retry:
            try:
                return self.func(*self.args, **self.kwargs)
            except Exception as err:  # NOCC:broad-except(需要处理所有异常类型)
                cur_retry += 1
                error = err
                data = self.check_exit(error=error, args=self.args, kwargs=self.kwargs)
                if not isinstance(data, Empty):
                    return data
                logger.warning(
                    "[FuncRunnerException] %d/%d\nFunc:%s\nArgs:%s\nKwargs:%s\nError:%s",
                    cur_retry,
                    self.max_retry,
                    self.func,
                    self.args,
                    self.kwargs,
                    error,
                )
                time.sleep(random.uniform(self.retry_sleep, self.max_retry_sleep))
        raise error

    def check_exit(self, error: Exception, args: tuple, kwargs: dict) -> any:
        """
        判定是否要提前终止
        not Empty -> 提前终止
        """

        return Empty()

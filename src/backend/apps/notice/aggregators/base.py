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

from typing import Union

from django.core.cache import cache
from django.core.cache.backends.db import DatabaseCache
from django_redis.client import DefaultClient

from apps.meta.models import GlobalMetaConfig
from apps.notice.constants import (
    DEFAULT_NOTICE_AGG_DURATION,
    DEFAULT_NOTICE_AGG_MAX_NOTICE,
    NOTICE_AGG_DURATION_KEY,
    NOTICE_AGG_MAX_NOTICE_KEY,
    NOTICE_LAST_AGG_TIME_KEY,
)

cache: Union[DatabaseCache, DefaultClient]


class Aggregator:
    """
    聚合器
    """

    def __init__(self, schedule_time: float, agg_key: str, relate_type: str) -> None:
        self.schedule_time = schedule_time
        self.agg_key = agg_key
        self.relate_type = relate_type

    @property
    def cache_key(self) -> str:
        return NOTICE_LAST_AGG_TIME_KEY.format(relate_type=self.relate_type, agg_key=self.agg_key)

    def load_agg_config(self) -> (bool, int, int):
        """
        获取聚合配置: bool(是否需要调度), int(聚合周期), int(最大发送次数)
        """

        # 使用默认配置
        duration = GlobalMetaConfig.get(NOTICE_AGG_DURATION_KEY, default=DEFAULT_NOTICE_AGG_DURATION)
        max_send_times = GlobalMetaConfig.get(NOTICE_AGG_MAX_NOTICE_KEY, default=DEFAULT_NOTICE_AGG_MAX_NOTICE)

        # 获取上次调度时间
        last_schedule_time = float(cache.get(key=self.cache_key, default=self.schedule_time - duration))

        # 判断是否需要调度
        need_schedule = self.schedule_time - last_schedule_time >= duration

        return need_schedule, duration, max_send_times

    def update_agg_time(self):
        """
        更新上次调度时间
        """

        cache.set(key=self.cache_key, value=self.schedule_time, timeout=None)

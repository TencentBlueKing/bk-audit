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
import functools
import json

from blueapps.utils.base import md5_sum
from blueapps.utils.logger import logger
from django.core.cache import cache
from django.core.serializers.json import DjangoJSONEncoder

from core.constants import TimeEnum


def using_cache(key: str, duration, need_md5=False):
    """
    :param key: key 名可以使用format进行格式
    :param duration:
    :param need_md5: 缓冲是redis的时候 key不能带有空格等字符，需要用md5 hash一下
    :return:
    """

    def decorator(func):
        @functools.wraps(func)
        def inner(*args, **kwargs):

            try:
                actual_key = key.format(*args, **kwargs)
            except (IndexError, KeyError):
                actual_key = key

            logger.info(f"[using cache] build key => [{actual_key}] duration => [{duration}]")

            if need_md5:
                actual_key = md5_sum(actual_key)

            cache_result = cache.get(actual_key)

            if cache_result:
                return json.loads(cache_result)

            result = func(*args, **kwargs)
            if result:
                cache.set(actual_key, json.dumps(result, cls=DjangoJSONEncoder), duration)
            return result

        return inner

    return decorator


cache_half_minute = functools.partial(using_cache, duration=0.5 * TimeEnum.ONE_MINUTE_SECOND.value)
cache_one_minute = functools.partial(using_cache, duration=TimeEnum.ONE_MINUTE_SECOND.value)
cache_five_minute = functools.partial(using_cache, duration=5 * TimeEnum.ONE_MINUTE_SECOND.value)
cache_ten_minute = functools.partial(using_cache, duration=10 * TimeEnum.ONE_MINUTE_SECOND.value)
cache_one_hour = functools.partial(using_cache, duration=TimeEnum.ONE_HOUR_SECOND.value)
cache_one_day = functools.partial(using_cache, duration=TimeEnum.ONE_DAY_SECOND.value)


class CacheMixin(abc.ABC):
    @property
    @abc.abstractmethod
    def cache(self):
        ...

    @abc.abstractmethod
    def generate_cache_key(self, *args, **kwargs) -> str:
        ...

    def get_cache(self, key_params: dict) -> any:
        cache_key = self.generate_cache_key(**key_params)
        return self.cache.get(cache_key)

    def set_cache(self, key_params: dict, data: any, ex: int = None, *args, **kwargs) -> None:
        cache_key = self.generate_cache_key(**key_params)
        return self.cache.set(cache_key, data, ex, *args, **kwargs)

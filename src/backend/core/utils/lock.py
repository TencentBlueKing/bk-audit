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

import functools
import time
from contextlib import contextmanager

from blueapps.utils.unique import uniqid
from django.conf import settings
from django.core.cache import cache

from core.exceptions import LockError


class BaseLock(object):
    def __init__(self, name, ttl=None):
        self.name = name
        # 默认60秒过期
        self.ttl = ttl or 60

    def acquire(self, _wait=None):
        raise NotImplementedError

    def release(self):
        raise NotImplementedError

    def __exit__(self, t, v, tb):
        self.release()

    def __enter__(self):
        self.acquire()
        return self


class RedisLock(BaseLock):
    __token = None

    def __init__(self, name, ttl=None):
        super(RedisLock, self).__init__(name, ttl)
        self.client = cache

    def acquire(self, _wait=0.001):
        token = uniqid()
        wait_until = time.time() + _wait
        while not self.client.set(self.name, token, timeout=self.ttl, nx=True):
            if time.time() < wait_until:
                time.sleep(0.01)
            else:
                return False

        self.__token = token
        return True

    def release(self):
        if not self.__token:
            return False
        token = self.client.get(self.name)
        if not token or token != self.__token:
            return False
        return self.client.delete(self.name)


@contextmanager
def service_lock(key_instance, **kwargs):
    lock = None
    lock_key = key_instance.get_key(**kwargs)
    try:
        lock = RedisLock(lock_key, key_instance.ttl)
        if lock.acquire(0.1):
            yield lock
        else:
            raise LockError(msg="{} is already locked".format(lock_key))
    except LockError as err:
        raise err

    finally:
        if lock is not None:
            lock.release()


def share_lock(ttl=600, identify=None):
    """
    装饰定时任务时需要放在periodic_task下面
    @periodic_task(run_every=crontab(minute="*/1"), queue="sync")
    # 不填参数需要带括号执行
    @share_lock()
    def demo():
        pass
    :param ttl:
    :param identify:
    :return:
    """

    def wrapper(func):
        @functools.wraps(func)
        def _inner(*args, **kwargs):
            if not settings.USE_REDIS:
                return func(*args, **kwargs)
            token = str(time.time())
            # 防止函数重名导致方法失效，增加一个ID参数，可以通过ID参数屏蔽多模块函数名重复的问题
            # 例如，可以为`${module}_${method_used_for}`
            cache_key = "celery_%s" % func.__name__ if identify is None else identify
            client = cache
            lock_success = client.set(cache_key, token, timeout=ttl, nx=True)
            if not lock_success:
                return

            try:
                return func(*args, **kwargs)
            finally:
                if client.get(cache_key) == token:
                    client.delete(cache_key)

        return _inner

    return wrapper

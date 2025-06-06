# -*- coding: utf-8 -*-

from functools import wraps

from blueapps.utils.logger import logger
from django.conf import settings
from django.core.cache import cache
from redis.exceptions import ResponseError


class CacheLock:
    """
    基于缓存的并发锁
    """

    def __init__(self, lock_name: str, timeout=settings.DEFAULT_CACHE_LOCK_TIMEOUT) -> None:
        self.lock_name = lock_name
        self.lock_timeout = timeout
        self._locked = not self._init()

    @property
    def locked(self) -> bool:
        """
        True: 已经被锁定，触发了并发运行限制
        False：未被锁定，可以运行
        """

        return self._locked

    def _init(self) -> bool:
        """
        初始化锁
        """

        try:
            return cache.add(self.lock_name, True, timeout=self.lock_timeout)
        except ResponseError as err:
            logger.warning("[RedisResponseError] Key: %s; Error: %s", self.lock_name, err)
            return False

    def release(self) -> bool:
        """
        释放锁
        """

        return cache.delete(self.lock_name)


def lock(lock_name: str = "", *, load_lock_name: callable = None, timeout: int = settings.DEFAULT_CACHE_LOCK_TIMEOUT):
    """
    并发锁装饰器
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 初始化
            _lock_name = load_lock_name(*args, **kwargs) if callable(load_lock_name) else lock_name
            logger.info("[CacheLockDecorator] LockName: %s args: %s kwargs: %s", _lock_name, args, kwargs)
            _lock = CacheLock(lock_name=_lock_name, timeout=timeout)
            # 检查
            if _lock.locked:
                logger.warning("[CacheLockCheckFailed] MultiProcessRunning %s", _lock_name)
                return
            # 运行
            try:
                return func(*args, **kwargs)
            finally:
                _lock.release()

        return wrapper

    return decorator

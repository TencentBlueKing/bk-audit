# -*- coding: utf-8 -*-

from functools import wraps

from blueapps.utils.logger import logger
from blueapps.utils.unique import uniqid
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
        # owner token：释放前校验，锁过期后被他人持有时不会误删他人的锁
        self._token = uniqid()
        self._locked = not self._init()

    @property
    def locked(self) -> bool:
        """
        True: 已经被锁定，触发了并发运行限制
        False：未被锁定，可以运行
        """

        return self._locked

    def __enter__(self) -> bool:
        """返回是否成功获得锁；失败时不要调用 release，避免误删他人锁。"""

        return not self._locked

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if not self._locked:
            self.release()

    def _init(self) -> bool:
        """
        初始化锁
        """

        try:
            return cache.add(self.lock_name, self._token, timeout=self.lock_timeout)
        except ResponseError as err:
            logger.warning("[RedisResponseError] Key: %s; Error: %s", self.lock_name, err)
            return False

    def release(self) -> bool:
        """
        释放锁；仅当锁值仍是自己的 token 时才删除，避免误删他人的锁
        """

        if cache.get(self.lock_name) != self._token:
            return False
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

"""将审计 cache 配置接入组件的 Redis 实时尾流。

读写分池，避免阻塞 XREAD 占满业务写连接；只复制 cache 连接参数，不修改共享池。
客户端按角色缓存到进程结束，冷启动并发可能短暂创建额外池，上限属于单个池。
连接参数变更需重启，fork 后连接重建由 redis-py 负责；事件协议和原子追加由组件处理。
"""

from functools import lru_cache
from uuid import UUID

from django.conf import settings
from django.core.cache import caches
from django_redis import get_redis_connection
from redis import ConnectionPool, Redis
from ui_stream.redis import RedisLiveStore as ComponentRedisLiveStore

from services.web.ai_assistant.exceptions import InvalidStreamEvent
from services.web.ai_assistant.schemas import UIStreamEvent, serialize_stream_event

STREAM_KEY_PREFIX = "ai_assistant:attachment_stream"
READ_TIMEOUT_MARGIN_SECONDS = 5


def build_stream_key(*, attachment_uid: UUID, execution_id: UUID) -> str:
    """用附件与执行标识生成逻辑 key；cache 命名空间由存储适配器统一补充。"""

    return f"{STREAM_KEY_PREFIX}:{attachment_uid}:{execution_id}"


@lru_cache(maxsize=2)
def _stream_client(*, for_read: bool) -> Redis:
    """按读写角色复用有界客户端，不与 Django cache 或 Celery 共享连接池。

    读 socket 预算覆盖 XREAD 的最长阻塞并留出返回裕量；写 socket 使用短 I/O 预算。
    池满立即失败，交由组件的实时故障路径处理，而不在池上无限等待。
    """

    source_pool = get_redis_connection("redis").connection_pool
    socket_timeout = (
        min(15, settings.AI_ASSISTANT_STREAM_STATE_POLL_INTERVAL) + READ_TIMEOUT_MARGIN_SECONDS
        if for_read
        else settings.AI_ASSISTANT_STREAM_REDIS_IO_TIMEOUT
    )
    max_connections = (
        settings.AI_ASSISTANT_STREAM_REDIS_READ_MAX_CONNECTIONS
        if for_read
        else settings.AI_ASSISTANT_STREAM_REDIS_WRITE_MAX_CONNECTIONS
    )
    # 保留 TLS、解析器、认证和 DB 参数；新建连接池，避免改变缓存调用方的超时与容量。
    kwargs = dict(source_pool.connection_kwargs)
    kwargs.update(
        socket_connect_timeout=settings.AI_ASSISTANT_STREAM_REDIS_IO_TIMEOUT,
        socket_timeout=socket_timeout,
        retry_on_timeout=False,
    )
    pool = ConnectionPool(
        connection_class=source_pool.connection_class,
        max_connections=max_connections,
        **kwargs,
    )
    return Redis(connection_pool=pool)


class RedisLiveStore(ComponentRedisLiveStore):
    """将组件 Redis 尾流绑定到审计连接池、key 命名空间与事件协议。

    写端默认使用短超时写池，SSE 订阅显式使用 for_read=True 的阻塞读池。
    build_stream_key 产生的逻辑 key 经 cache.make_key 映射一次，避免跨环境冲突或重复加前缀。
    组件负责 XADD/EXPIRE 原子追加、游标回执与脏 entry 跳过；审计只注入事件校验和公开编码。
    客户端属于进程共享资源，单次订阅结束不应断开整个池。
    """

    def __init__(self, *, for_read: bool = False):
        """选择缓存客户端并装配协议；本身不执行读写或轮换执行。

        Args:
            for_read: SSE 阻塞读取使用 True，Worker 发布使用默认 False。
        """

        self._cache = caches["redis"]
        super().__init__(
            client=_stream_client(for_read=bool(for_read)),
            physical_key=self._cache.make_key,
            ttl_seconds=settings.AI_ASSISTANT_STREAM_TTL,
            event_type=UIStreamEvent,
            serializer=serialize_stream_event,
            invalid_event_errors=(InvalidStreamEvent,),
        )

    @property
    def ttl(self) -> int:
        """追加时读取当前进程的滑动 TTL；只影响 Redis key，不删除持久快照。"""

        return settings.AI_ASSISTANT_STREAM_TTL

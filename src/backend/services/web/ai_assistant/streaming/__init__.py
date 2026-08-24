"""AI 助手附件流式传输子系统。

架构概览
========

本包实现了 AI 助手附件执行过程中 UI 事件的实时推送与持久化归档，采用
Redis Stream（实时尾流）+ MySQL（持久归档）的双写架构：

    ┌─────────────┐     send()      ┌──────────────┐
    │ Celery Task │ ───────────────► │ Runtime 层   │
    └─────────────┘                  └──────┬───────┘
                                       ┌────┴────┐
                                       ▼         ▼
                              ┌────────────┐  ┌──────────────┐
                              │ Redis 实时  │  │ MySQL 归档    │
                              │ (推送+续传) │  │ (快照+终态)   │
                              └─────┬──────┘  └──────┬───────┘
                                    ▼                ▼
                              SSE EventSource     快照/详情接口

模块职责
--------
- **runtime** : 业务唯一出口，封装实时推送、归档缓冲与终态收敛，业务只需 send()。
- **archive** : MySQL 归档事务管理器，行锁串行化 + 双重 fencing 保证并发安全。
- **redis**   : Redis Stream 实时尾流，滑动 TTL + Lua 原子追加。
- **sse**     : 原生 SSE 帧编码，供 HTTP 响应直接输出。
- **types**   : 不可变数据类型，跨模块传递的运行绑定与结果值对象。

核心设计决策
------------
1. Redis 写入故障不阻断 MySQL 归档；checkpoint 失败会保留缓冲，终态事务失败则交由任务重试策略处理。
2. 双重 fencing（task_id + execution_id）：防止旧 Worker 延迟写入覆盖新执行。
3. 归档状态单向升级（COMPLETE → DEGRADED → TRUNCATED）：前端只需展示最坏情况。
4. terminal_event 不受业务容量限制：终态事务成功时与执行结果一并落库。
"""

from services.web.ai_assistant.streaming.archive import (
    AttachmentArchiveStore,
    fit_archive_events,
    merge_archive_status,
)
from services.web.ai_assistant.streaming.redis import (
    STREAM_KEY_PREFIX,
    RedisLiveStore,
    build_stream_key,
)
from services.web.ai_assistant.streaming.runtime import UIStreamRuntime
from services.web.ai_assistant.streaming.sse import (
    encode_sse_event,
    encode_sse_heartbeat,
)
from services.web.ai_assistant.streaming.types import (
    StreamCheckpointResult,
    StreamExecutionBinding,
    StreamReadResult,
    StreamRotation,
)

__all__ = [
    "STREAM_KEY_PREFIX",
    "AttachmentArchiveStore",
    "RedisLiveStore",
    "StreamCheckpointResult",
    "StreamExecutionBinding",
    "StreamReadResult",
    "StreamRotation",
    "UIStreamRuntime",
    "build_stream_key",
    "encode_sse_event",
    "encode_sse_heartbeat",
    "fit_archive_events",
    "merge_archive_status",
]

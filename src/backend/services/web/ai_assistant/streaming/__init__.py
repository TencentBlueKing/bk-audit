"""AI 助手附件流式传输子系统。

架构概览
========

本包实现了 AI 助手附件执行过程中 UI 事件的实时推送与持久化归档，采用
Redis Stream（实时尾流）与 MySQL（持久归档）两个独立通道：

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
- **runtime** : 业务唯一出口，向 ui_stream 运行时注入审计配置、执行生命周期及监控。
- **codec**   : 审计事件工厂与持久化编码，区分 Runtime 身份和合成控制事件。
- **archive** : MySQL 归档事务管理器，行锁串行化 + 双重 fencing 保证并发安全。
- **redis**   : 独立读写池、cache 命名空间和事件协议适配；组件负责 Lua 追加与读取。
- **sse**     : 复用组件的原生 SSE 编码，保留审计异常边界，供 HTTP 响应输出。
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
    StreamRotation,
    StreamTimeoutResult,
)

__all__ = [
    "STREAM_KEY_PREFIX",
    "AttachmentArchiveStore",
    "RedisLiveStore",
    "StreamCheckpointResult",
    "StreamExecutionBinding",
    "StreamRotation",
    "StreamTimeoutResult",
    "UIStreamRuntime",
    "build_stream_key",
    "encode_sse_event",
    "encode_sse_heartbeat",
    "merge_archive_status",
]

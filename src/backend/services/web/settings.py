import os

INSTALLED_APPS = (
    "services.web.analyze",
    "services.web.databus",
    "services.web.entry",
    "services.web.query",
    "services.web.ai_assistant",
    "services.web.log_subscription",
    "services.web.strategy_v2",
    "services.web.risk",
    "services.web.version",
    "services.web.vision",
    "services.web.tool",
    "services.web.blob_storage",
    "services.web.scene",
)

# ============== 渲染任务相关配置 ==============
# 渲染任务最大重试次数
RENDER_MAX_RETRY = int(os.getenv("BKAPP_RENDER_MAX_RETRY", 3))
# 渲染任务超时时间（秒），默认 30 分钟
RENDER_TASK_TIMEOUT = int(os.getenv("BKAPP_RENDER_TASK_TIMEOUT", 30 * 60))
# 渲染任务延迟触发时间（秒），默认 5 分钟
RENDER_TASK_DELAY = int(os.getenv("BKAPP_RENDER_TASK_DELAY", 60 * 5))
# 渲染任务限流，格式: "次数/时间单位"，如 "10/m", "100/m", "1000/h"
RENDER_TASK_RATE_LIMIT = os.getenv("BKAPP_RENDER_TASK_RATE_LIMIT", "5/m")
# 渲染任务重试延迟时间（秒），默认 10 秒
RENDER_RETRY_DELAY = int(os.getenv("BKAPP_RENDER_RETRY_DELAY", 10))
# AI Provider 缓存超时时间（秒），默认 2 小时
AI_PROVIDER_CACHE_TIMEOUT = int(os.getenv("BKAPP_AI_PROVIDER_CACHE_TIMEOUT", 7200))
# 报告内容最小有效长度，低于此长度上报质量告警（通过 BKAPP_REPORT_CONTENT_MIN_LENGTH 可配置）
REPORT_CONTENT_MIN_LENGTH = int(os.getenv("BKAPP_REPORT_CONTENT_MIN_LENGTH", 10))

# ============== AI 风险检索相关配置 ==============
# MCP 事件字段简化接口返回上限
AI_EVENT_FIELDS_BRIEF_MAX = int(os.getenv("BKAPP_AI_EVENT_FIELDS_BRIEF_MAX", 100))

# ============== AI 风险分析报告相关配置 ==============
ANALYSE_REPORT_TIME_LIMIT = int(os.getenv("BKAPP_ANALYSE_REPORT_TIME_LIMIT", 30 * 60))
ANALYSE_REPORT_AI_TITLE_MAX_LENGTH = int(os.getenv("BKAPP_ANALYSE_REPORT_AI_TITLE_MAX_LENGTH", 20))

# ============== AI 助手附件流式传输相关配置 ==============
# 单个 execution Redis Stream 的滑动 TTL（秒）。每次成功追加事件都会原子刷新；
# 任务结束后不再刷新并自然过期。过期只影响实时追赶，不删除 MySQL 快照或最终产物。
AI_ASSISTANT_STREAM_TTL = int(os.getenv("BKAPP_AI_ASSISTANT_STREAM_TTL", 60 * 60))
# 单个业务 UI 事件序列化后的字节上限。超限事件不写 Redis 也不归档，
# 当前 execution 标记为 TRUNCATED；平台终态事件和最终 output_data 不受此限制。
AI_ASSISTANT_STREAM_MAX_EVENT_BYTES = int(os.getenv("BKAPP_AI_ASSISTANT_STREAM_MAX_EVENT_BYTES", 256 * 1024))
# 单个 execution 允许归档的业务事件条数上限。超限后停止后续业务事件归档
# 并标记 TRUNCATED，但 Redis 实时写入仍继续，另受 REDIS_MAX_BYTES 限制；平台事件不计入。
AI_ASSISTANT_STREAM_MAX_EVENTS = int(os.getenv("BKAPP_AI_ASSISTANT_STREAM_MAX_EVENTS", 10_000))
# 单个 execution 在 MySQL `stream_archive` JSON 中允许持久化的编码字节上限。
# 超限后停止后续业务事件 checkpoint 并标记 TRUNCATED，不影响 Redis 实时流和最终产物。
AI_ASSISTANT_STREAM_ARCHIVE_MAX_BYTES = int(os.getenv("BKAPP_AI_ASSISTANT_STREAM_ARCHIVE_MAX_BYTES", 10 * 1024 * 1024))
# 单个 execution 写入 Redis 实时流的业务事件累计字节上限。超限后停止业务实时写入
# 并标记 DEGRADED，MySQL 归档和最终产物继续执行；平台控制事件不受此限制。
AI_ASSISTANT_STREAM_REDIS_MAX_BYTES = int(os.getenv("BKAPP_AI_ASSISTANT_STREAM_REDIS_MAX_BYTES", 10 * 1024 * 1024))
# SSE 连接连续未读到业务事件时的滑动空闲超时（秒）。只有有效业务事件刷新计时；
# heartbeat、平台控制事件和无法解析的 Redis entry 都不刷新，到期仅主动断开当前 SSE 连接。
AI_ASSISTANT_STREAM_IDLE_TIMEOUT = int(os.getenv("BKAPP_AI_ASSISTANT_STREAM_IDLE_TIMEOUT", 300))
# 流式 Worker 最长间隔多少秒向 MySQL 持久化一次 `last_activity_at`。该活动只能由业务
# send 触发，用于避免低频长任务被巡检误判失活；它不控制 SSE 连接超时。
AI_ASSISTANT_STREAM_ACTIVITY_INTERVAL_SECONDS = int(
    os.getenv("BKAPP_AI_ASSISTANT_STREAM_ACTIVITY_INTERVAL_SECONDS", 60)
)

# ============== AI 助手异步执行巡检与 SLO 配置 ==============
# 异步 Message 的 SLO 目标（秒），从对象首次 `created_at` 计算到终态。
# 该值用于计算 SLO Metric 及 BKM 达标率告警，不参与失活巡检或直接修改 Message 状态。
AI_ASSISTANT_MESSAGE_SLO_SECONDS = int(os.getenv("BKAPP_AI_ASSISTANT_MESSAGE_SLO_SECONDS", 120))
# 异步 Message 的无活动告警阈值（秒），从当前执行 `last_activity_at` 计算。
# 巡检只将达线对象计入 warning Metric，不修改状态；应小于硬失效阈值。
AI_ASSISTANT_MESSAGE_WARNING_SECONDS = int(os.getenv("BKAPP_AI_ASSISTANT_MESSAGE_WARNING_SECONDS", 300))
# 异步 Message 的硬失效阈值（秒），从当前执行 `last_activity_at` 计算。
# 达线且自动失败开关开启时，巡检通过 CAS 将 Message 收敛为 FAILED。
AI_ASSISTANT_MESSAGE_FAILURE_SECONDS = int(os.getenv("BKAPP_AI_ASSISTANT_MESSAGE_FAILURE_SECONDS", 900))
# 异步 Attachment 的 SLO 目标（秒），从对象首次 `created_at` 计算到终态。
# 该值用于计算 SLO Metric 及 BKM 达标率告警，不参与失活巡检或直接修改 Attachment 状态。
AI_ASSISTANT_ATTACHMENT_SLO_SECONDS = int(os.getenv("BKAPP_AI_ASSISTANT_ATTACHMENT_SLO_SECONDS", 1800))
# 异步 Attachment 的无活动告警阈值（秒），从当前执行 `last_activity_at` 计算。
# 巡检只将达线对象计入 warning Metric，不修改状态；应小于硬失效阈值。
AI_ASSISTANT_ATTACHMENT_WARNING_SECONDS = int(os.getenv("BKAPP_AI_ASSISTANT_ATTACHMENT_WARNING_SECONDS", 3600))
# 异步 Attachment 的硬失效阈值（秒），从当前执行 `last_activity_at` 计算。
# 达线且自动失败开关开启时，巡检通过 CAS 将 Attachment 收敛为 FAILED。
AI_ASSISTANT_ATTACHMENT_FAILURE_SECONDS = int(os.getenv("BKAPP_AI_ASSISTANT_ATTACHMENT_FAILURE_SECONDS", 7200))
# 失活巡检的 Celery Beat 调度间隔（秒），同时用于派生去重短锁 TTL。
# 应大于单次任务 time limit，避免正常执行重叠。
AI_ASSISTANT_RECONCILE_INTERVAL_SECONDS = int(os.getenv("BKAPP_AI_ASSISTANT_RECONCILE_INTERVAL_SECONDS", 60))
# 每轮巡检对 Message 和 Attachment 各自允许加载的硬失效候选数上限。
# 它只限制单轮收敛量，不限制 PROCESSING 聚合统计的数据范围。
AI_ASSISTANT_RECONCILE_BATCH_SIZE = int(os.getenv("BKAPP_AI_ASSISTANT_RECONCILE_BATCH_SIZE", 200))
# 单次巡检 Celery Task 的硬时限（秒），防止巡检自身长期占用 Worker。
# 该值不是 Message/Attachment 业务超时，并且必须小于巡检调度间隔。
AI_ASSISTANT_RECONCILE_TIME_LIMIT_SECONDS = int(os.getenv("BKAPP_AI_ASSISTANT_RECONCILE_TIME_LIMIT_SECONDS", 50))
# 是否执行失活巡检主体。关闭后 Beat 仍周期投递任务，但 Worker 在访问 Redis/DB 前
# 立即返回：不扫描、不上报存量/心跳，也不修改对象状态。该开关不能停止 Beat 入队。
AI_ASSISTANT_RECONCILE_ENABLED = os.getenv("BKAPP_AI_ASSISTANT_RECONCILE_ENABLED", "true").lower() == "true"
# 是否允许巡检将硬失效的 PROCESSING 对象 CAS 更新为 FAILED。关闭后仍扫描并上报
# PROCESSING/过期指标，但不修改业务状态；这是误判事故时的首选止损开关。
AI_ASSISTANT_RECONCILE_AUTO_FAIL_ENABLED = (
    os.getenv("BKAPP_AI_ASSISTANT_RECONCILE_AUTO_FAIL_ENABLED", "true").lower() == "true"
)

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
# Redis Stream 的滑动 TTL（秒）；过期后前端只能读取已持久化的附件快照。
AI_ASSISTANT_STREAM_TTL = int(os.getenv("BKAPP_AI_ASSISTANT_STREAM_TTL", 60 * 60))
# 单个 UI 事件序列化后的字节上限；超限事件直接丢弃并把归档标记为已截断。
AI_ASSISTANT_STREAM_MAX_EVENT_BYTES = int(os.getenv("BKAPP_AI_ASSISTANT_STREAM_MAX_EVENT_BYTES", 256 * 1024))
# 单次执行允许归档的业务事件条数上限；平台控制事件不计入该上限。
AI_ASSISTANT_STREAM_MAX_EVENTS = int(os.getenv("BKAPP_AI_ASSISTANT_STREAM_MAX_EVENTS", 10_000))
# MySQL 事件归档 JSON 的字节上限；超限后停止业务事件归档，最终产物不受影响。
AI_ASSISTANT_STREAM_ARCHIVE_MAX_BYTES = int(os.getenv("BKAPP_AI_ASSISTANT_STREAM_ARCHIVE_MAX_BYTES", 10 * 1024 * 1024))
# 单次执行写入 Redis 实时流的业务字节上限；超限后只降级实时推送。
AI_ASSISTANT_STREAM_REDIS_MAX_BYTES = int(os.getenv("BKAPP_AI_ASSISTANT_STREAM_REDIS_MAX_BYTES", 10 * 1024 * 1024))
# SSE 连接连续无业务事件时的滑动空闲超时；heartbeat 不刷新该时间。
AI_ASSISTANT_STREAM_IDLE_TIMEOUT = int(os.getenv("BKAPP_AI_ASSISTANT_STREAM_IDLE_TIMEOUT", 300))

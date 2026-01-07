import os

INSTALLED_APPS = (
    "services.web.analyze",
    "services.web.databus",
    "services.web.entry",
    "services.web.query",
    "services.web.log_subscription",
    "services.web.strategy_v2",
    "services.web.risk",
    "services.web.version",
    "services.web.vision",
    "services.web.tool",
    "services.web.blob_storage",
)

# ============== 渲染任务相关配置 ==============
# 渲染任务扫描间隔（秒），默认 5 分钟
RENDER_SCAN_INTERVAL = int(os.getenv("BKAPP_RENDER_SCAN_INTERVAL", "300"))
# 渲染任务批量大小
RENDER_BATCH_SIZE = int(os.getenv("BKAPP_RENDER_BATCH_SIZE", "50"))
# 渲染任务最大重试次数
RENDER_MAX_RETRY = int(os.getenv("BKAPP_RENDER_MAX_RETRY", "3"))
# 渲染任务时间范围（天）
RENDER_TASK_TIME_RANGE_DAYS = int(os.getenv("BKAPP_RENDER_TASK_TIME_RANGE_DAYS", "3"))
# 渲染任务超时时间（秒），默认 1 小时
RENDER_TASK_TIMEOUT = int(os.getenv("BKAPP_RENDER_TASK_TIMEOUT", "3600"))

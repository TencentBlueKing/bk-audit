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
# 渲染任务最大重试次数
RENDER_MAX_RETRY = int(os.getenv("BKAPP_RENDER_MAX_RETRY", "3"))
# 渲染任务超时时间（秒），默认 30 分钟
RENDER_TASK_TIMEOUT = int(os.getenv("BKAPP_RENDER_TASK_TIMEOUT", str(30 * 60)))
# 渲染任务延迟触发时间（秒），默认 30 秒
RENDER_TASK_DELAY = int(os.getenv("BKAPP_RENDER_TASK_DELAY", "30"))

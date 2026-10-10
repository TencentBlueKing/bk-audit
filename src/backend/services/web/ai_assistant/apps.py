from django.apps import AppConfig


class AIAssistantConfig(AppConfig):
    """AI 助手平台的会话、消息和产物数据。"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "services.web.ai_assistant"

    def ready(self) -> None:
        """模型加载完成后注册业务 Handler，统一 Web 和 Worker 的初始化顺序。"""

        # handlers 先提供基类/注册表，再绑定业务 Task；不能等 Worker 首次导入任务时反向触发。
        # 普通 import 利用模块缓存，不重复执行模块底部的注册，也不访问数据库。
        from services.web.ai_assistant import handlers  # noqa: F401

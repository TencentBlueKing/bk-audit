from django.apps import AppConfig


class AIAssistantConfig(AppConfig):
    """AI 助手平台的会话、消息和产物数据。"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "services.web.ai_assistant"

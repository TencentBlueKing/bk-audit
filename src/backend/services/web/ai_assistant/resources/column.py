from django.utils.translation import gettext_lazy

from core.models import get_request_username
from services.web.ai_assistant.resources.conversation import AIAssistantResource
from services.web.ai_assistant.serializers.column import (
    ColumnConfigApplyRequestSerializer,
    ColumnConfigApplyResponseSerializer,
    ColumnConfigResponseSerializer,
)
from services.web.ai_assistant.services import ColumnPreferenceService


class ListColumnConfig(AIAssistantResource):
    """查询当前用户的展示字段配置（可选字段 + 已选字段，九个固定列不可增减）。"""

    name = gettext_lazy("查询展示字段配置")
    RequestSerializer = None
    ResponseSerializer = ColumnConfigResponseSerializer

    def perform_request(self, validated_request_data):
        return ColumnPreferenceService(username=get_request_username()).list_columns()


class ApplyColumnConfig(AIAssistantResource):
    """应用展示字段选择：保存当前用户的自定义列偏好（跨设备同步，按用户隔离）。"""

    name = gettext_lazy("应用展示字段选择")
    RequestSerializer = ColumnConfigApplyRequestSerializer
    ResponseSerializer = ColumnConfigApplyResponseSerializer

    def perform_request(self, validated_request_data):
        selected_fields = ColumnPreferenceService(username=get_request_username()).apply_columns(
            list(validated_request_data["fields"])
        )
        return {"selected_fields": selected_fields}

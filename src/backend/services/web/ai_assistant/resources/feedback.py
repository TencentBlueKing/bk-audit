from django.utils.translation import gettext_lazy

from core.models import get_request_username
from services.web.ai_assistant.resources.conversation import AIAssistantResource
from services.web.ai_assistant.serializers.feedback import (
    FeedbackDeleteRequestSerializer,
    FeedbackResponseSerializer,
    FeedbackUpsertRequestSerializer,
)
from services.web.ai_assistant.services import FeedbackService


class UpsertFeedback(AIAssistantResource):
    """创建或覆盖当前用户对成功消息或附件的赞踩反馈。"""

    name = gettext_lazy("创建或覆盖反馈")
    RequestSerializer = FeedbackUpsertRequestSerializer
    ResponseSerializer = FeedbackResponseSerializer

    def perform_request(self, validated_request_data):
        data = dict(validated_request_data)
        data["source_uid"] = str(data["source_uid"])
        return FeedbackService(user=get_request_username()).upsert(**data)

    def validate_response_data(self, response_data):
        """FeedbackDTO 是领域 dataclass，按实例序列化以保留公开响应契约。"""

        self._response_serializer = self.ResponseSerializer(response_data)
        return self._response_serializer.data


class DeleteFeedback(AIAssistantResource):
    """按反馈 UUID 取消当前用户自己的反馈，不删除来源消息或附件。"""

    name = gettext_lazy("取消反馈")
    RequestSerializer = FeedbackDeleteRequestSerializer

    def perform_request(self, validated_request_data):
        FeedbackService(user=get_request_username()).delete(feedback_uid=str(validated_request_data["feedback_uid"]))

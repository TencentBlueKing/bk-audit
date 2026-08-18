from django.utils.translation import gettext_lazy

from core.models import get_request_username
from services.web.ai_assistant.resources.conversation import AIAssistantResource
from services.web.ai_assistant.serializers.message import (
    MessageCreateRequestSerializer,
    MessageDetailRequestSerializer,
    MessageListRequestSerializer,
    MessageResponseSerializer,
    MessageWindowResponseSerializer,
)
from services.web.ai_assistant.services import ConversationService, MessageService


class CreateMessage(AIAssistantResource):
    """创建并执行类型化消息；同步消息直接返回 SUCCESS，异步消息持久化后返回 PROCESSING。"""

    name = gettext_lazy("创建消息")
    RequestSerializer = MessageCreateRequestSerializer
    ResponseSerializer = MessageResponseSerializer

    def perform_request(self, validated_request_data):
        """加载用户会话后，将业务输入交给消息平台执行。"""

        user = get_request_username()
        message_data = dict(validated_request_data)
        conversation_uid = message_data.pop("conversation_uid")
        parent_message_uid = message_data.get("parent_message_uid")
        if parent_message_uid is not None:
            message_data["parent_message_uid"] = str(parent_message_uid)
        conversation = ConversationService(user=user).get_conversation(
            conversation_uid=str(conversation_uid),
        )
        return MessageService(user=user).create(conversation=conversation, **message_data)


class ListMessages(AIAssistantResource):
    """按消息 UID 锚点向 BEFORE 或 AFTER 获取窗口，结果始终按时间正序返回。"""

    name = gettext_lazy("获取消息历史")
    RequestSerializer = MessageListRequestSerializer
    ResponseSerializer = MessageWindowResponseSerializer

    def perform_request(self, validated_request_data):
        """转换外部 UUID 后读取指定会话的消息窗口。"""

        query = dict(validated_request_data)
        query["conversation_uid"] = str(query["conversation_uid"])
        if query.get("anchor_uid") is not None:
            query["anchor_uid"] = str(query["anchor_uid"])
        return MessageService(user=get_request_username()).list(**query)

    def validate_response_data(self, response_data):
        """MessageWindow 是领域 dataclass，按框架处理 Model 的方式执行实例序列化。"""

        self._response_serializer = self.ResponseSerializer(response_data)
        return self._response_serializer.data


class GetMessage(AIAssistantResource):
    """返回消息完整类型化快照，可用于轮询异步消息状态和最终结果。"""

    name = gettext_lazy("获取消息详情")
    RequestSerializer = MessageDetailRequestSerializer
    ResponseSerializer = MessageResponseSerializer

    def perform_request(self, validated_request_data):
        """详情始终返回完整类型化快照，供异步任务状态轮询。"""

        return MessageService(user=get_request_username()).get(
            message_uid=str(validated_request_data["message_uid"]),
        )


class RetryMessage(AIAssistantResource):
    """重试失败的异步消息；复用原 UID 和快照，返回 PROCESSING 后轮询原消息。"""

    name = gettext_lazy("重试消息")
    RequestSerializer = MessageDetailRequestSerializer
    ResponseSerializer = MessageResponseSerializer

    def perform_request(self, validated_request_data):
        return MessageService(user=get_request_username()).retry(
            message_uid=str(validated_request_data["message_uid"]),
        )

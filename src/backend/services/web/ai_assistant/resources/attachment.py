from django.utils.translation import gettext_lazy

from core.models import get_request_username
from services.web.ai_assistant.resources.conversation import AIAssistantResource
from services.web.ai_assistant.serializers.attachment import (
    AttachmentCreateRequestSerializer,
    AttachmentDetailRequestSerializer,
    AttachmentListItemSerializer,
    AttachmentListRequestSerializer,
    AttachmentResponseSerializer,
    AttachmentUpdateRequestSerializer,
)
from services.web.ai_assistant.services.attachment import AttachmentService


class CreateAttachment(AIAssistantResource):
    name = gettext_lazy("创建附件")
    RequestSerializer = AttachmentCreateRequestSerializer
    ResponseSerializer = AttachmentResponseSerializer

    def perform_request(self, validated_request_data):
        request_data = dict(validated_request_data)
        request_data["source_message_uid"] = str(request_data.pop("message_uid"))
        attachment = AttachmentService(user=get_request_username()).create(**request_data)
        attachment.refresh_from_db()
        return attachment


class ListAttachments(AIAssistantResource):
    name = gettext_lazy("获取附件列表")
    RequestSerializer = AttachmentListRequestSerializer
    ResponseSerializer = AttachmentListItemSerializer
    many_response_data = True

    def perform_request(self, validated_request_data):
        query = dict(validated_request_data)
        attachment_types = query.pop("attachment_type", None)
        statuses = query.pop("status", None)
        conversation_uid = query.get("conversation_uid")
        source_message_uid = query.get("source_message_uid")
        query.update(
            attachment_types=attachment_types,
            statuses=statuses,
            conversation_uid=str(conversation_uid) if conversation_uid else None,
            source_message_uid=str(source_message_uid) if source_message_uid else None,
        )
        return AttachmentService(user=get_request_username()).list(**query)


class GetAttachment(AIAssistantResource):
    name = gettext_lazy("获取附件详情")
    RequestSerializer = AttachmentDetailRequestSerializer
    ResponseSerializer = AttachmentResponseSerializer

    def perform_request(self, validated_request_data):
        return AttachmentService(user=get_request_username()).get(
            attachment_uid=str(validated_request_data["attachment_uid"]),
        )


class UpdateAttachment(AIAssistantResource):
    name = gettext_lazy("编辑附件")
    RequestSerializer = AttachmentUpdateRequestSerializer
    ResponseSerializer = AttachmentResponseSerializer

    def perform_request(self, validated_request_data):
        request_data = dict(validated_request_data)
        request_data["attachment_uid"] = str(request_data["attachment_uid"])
        return AttachmentService(user=get_request_username()).update(**request_data)


class RetryAttachment(AIAssistantResource):
    name = gettext_lazy("重试附件")
    RequestSerializer = AttachmentDetailRequestSerializer
    ResponseSerializer = AttachmentResponseSerializer

    def perform_request(self, validated_request_data):
        attachment = AttachmentService(user=get_request_username()).retry(
            attachment_uid=str(validated_request_data["attachment_uid"]),
        )
        attachment.refresh_from_db()
        return attachment

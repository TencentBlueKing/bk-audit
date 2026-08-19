from django.http import HttpResponse
from django.utils.http import content_disposition_header
from django.utils.translation import gettext_lazy

from core.models import get_request_username
from services.web.ai_assistant.resources.conversation import AIAssistantResource
from services.web.ai_assistant.serializers.attachment import (
    AttachmentCreateRequestSerializer,
    AttachmentDetailRequestSerializer,
    AttachmentExportRequestSerializer,
    AttachmentListItemSerializer,
    AttachmentListRequestSerializer,
    AttachmentResponseSerializer,
    AttachmentUpdateRequestSerializer,
)
from services.web.ai_assistant.services.attachment import AttachmentService


class CreateAttachment(AIAssistantResource):
    """基于当前用户可见的成功消息创建类型化产物；同步返回 SUCCESS，异步返回 PROCESSING。"""

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
    """一次性返回附件摘要列表，支持按类型、状态、来源消息、会话和关键词筛选。"""

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
    """返回附件完整类型化产物，不暴露任务 ID、内部上下文和流式事件归档。"""

    name = gettext_lazy("获取附件详情")
    RequestSerializer = AttachmentDetailRequestSerializer
    ResponseSerializer = AttachmentResponseSerializer

    def perform_request(self, validated_request_data):
        return AttachmentService(user=get_request_username()).get(
            attachment_uid=str(validated_request_data["attachment_uid"]),
        )


class ExportAttachment(AIAssistantResource):
    """实时导出成功 Attachment；格式读取详情 export_formats，文件不会被平台留存。"""

    name = gettext_lazy("导出附件")
    RequestSerializer = AttachmentExportRequestSerializer

    def perform_request(self, validated_request_data):
        result = AttachmentService(user=get_request_username()).export(
            attachment_uid=str(validated_request_data["attachment_uid"]),
            export_format=validated_request_data["export_format"],
        )
        response = HttpResponse(result.content, content_type=result.content_type)
        response["Content-Disposition"] = content_disposition_header(
            as_attachment=True,
            filename=result.filename,
        )
        return response


class UpdateAttachment(AIAssistantResource):
    """编辑附件元信息或产物；标题不受执行状态限制，产物仅允许成功且 Handler 开放编辑时修改。"""

    name = gettext_lazy("编辑附件")
    RequestSerializer = AttachmentUpdateRequestSerializer
    ResponseSerializer = AttachmentResponseSerializer

    def perform_request(self, validated_request_data):
        request_data = dict(validated_request_data)
        request_data["attachment_uid"] = str(request_data["attachment_uid"])
        return AttachmentService(user=get_request_username()).update(**request_data)


class RetryAttachment(AIAssistantResource):
    """重试 FAILED 异步附件；复用原对象和快照并切换新 task ID，不创建新附件。"""

    name = gettext_lazy("重试附件")
    RequestSerializer = AttachmentDetailRequestSerializer
    ResponseSerializer = AttachmentResponseSerializer

    def perform_request(self, validated_request_data):
        attachment = AttachmentService(user=get_request_username()).retry(
            attachment_uid=str(validated_request_data["attachment_uid"]),
        )
        attachment.refresh_from_db()
        return attachment

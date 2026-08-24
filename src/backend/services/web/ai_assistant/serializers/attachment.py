from drf_spectacular.utils import PolymorphicProxySerializer, extend_schema_field
from rest_framework import serializers

from core.serializers import FlexibleListField
from services.web.ai_assistant.constants import (
    AttachmentExportFormat,
    AttachmentType,
    ExecutionStatus,
    MessageType,
)
from services.web.ai_assistant.exceptions import AttachmentSnapshotValidationError
from services.web.ai_assistant.handlers import attachment_handler_registry
from services.web.ai_assistant.schemas import MessageSchema, parse_snapshot
from services.web.ai_assistant.serializers.feedback import FeedbackResponseSerializer


def _attachment_schema_mapping(model_attribute: str) -> dict[str, type[MessageSchema]]:
    """按已注册附件类型返回 Handler 快照模型。"""

    return {
        attachment_type: getattr(handler, model_attribute)
        for attachment_type, handler in attachment_handler_registry.handlers.items()
    }


def _editable_attachment_output_schema_mapping() -> dict[str, type[MessageSchema]]:
    """仅返回显式开放产物编辑能力的附件输出模型。"""

    return {
        attachment_type: handler.output_model
        for attachment_type, handler in attachment_handler_registry.handlers.items()
        if handler.supports_output_edit()
    }


def _unique_schema_models(schema_mapping: dict[str, type[MessageSchema]]) -> list[type[MessageSchema]]:
    """按注册顺序返回快照模型；无业务 Handler 时使用合法的空对象 schema 占位。"""

    return list(dict.fromkeys(schema_mapping.values())) or [MessageSchema]


@extend_schema_field(
    PolymorphicProxySerializer(
        component_name="AIAttachmentInputData",
        serializers=lambda: _unique_schema_models(_attachment_schema_mapping("input_model")),
        resource_type_field_name=None,
    )
)
class AttachmentInputDataField(serializers.JSONField):
    """在 OpenAPI 中按 attachment_type 展示对应 Handler 输入协议。"""


@extend_schema_field(
    PolymorphicProxySerializer(
        component_name="AIAttachmentOutputData",
        serializers=lambda: _unique_schema_models(_attachment_schema_mapping("output_model")),
        resource_type_field_name=None,
    )
)
class AttachmentOutputDataField(serializers.JSONField):
    """在 OpenAPI 中按 attachment_type 展示对应 Handler 输出协议。"""


@extend_schema_field(
    PolymorphicProxySerializer(
        component_name="EditableAIAttachmentOutputData",
        serializers=lambda: _unique_schema_models(_editable_attachment_output_schema_mapping()),
        resource_type_field_name=None,
    )
)
class EditableAttachmentOutputDataField(serializers.JSONField):
    """在 OpenAPI 中仅暴露允许编辑的附件产物协议。"""


class AttachmentCreateRequestSerializer(serializers.Serializer):
    """创建附件只接收来源消息、附件类型与业务输入。"""

    message_uid = serializers.UUIDField(help_text="来源消息对外 UUID")
    attachment_type = serializers.ChoiceField(choices=AttachmentType.choices, help_text="附件类型")
    input_data = AttachmentInputDataField(help_text="由附件类型对应 Pydantic 输入模型校验的业务数据")


class AttachmentDetailRequestSerializer(serializers.Serializer):
    attachment_uid = serializers.UUIDField(help_text="附件对外 UUID")


class AttachmentExportRequestSerializer(serializers.Serializer):
    """实时导出成功附件的路径和查询参数。"""

    attachment_uid = serializers.UUIDField(help_text="待导出附件 UUID")
    export_format = serializers.ChoiceField(
        choices=AttachmentExportFormat.choices,
        help_text="导出格式，必须包含在附件详情 export_formats 中",
    )


class AttachmentListRequestSerializer(serializers.Serializer):
    """附件列表筛选参数；对外仅暴露单数参数名。"""

    attachment_type = FlexibleListField(
        child=serializers.ChoiceField(choices=AttachmentType.choices),
        required=False,
        help_text="附件类型，支持单值、逗号或重复查询参数",
    )
    status = FlexibleListField(
        child=serializers.ChoiceField(choices=ExecutionStatus.choices),
        required=False,
        help_text="执行状态，支持单值、逗号或重复查询参数",
    )
    keyword = serializers.CharField(required=False, allow_blank=True, help_text="附件标题关键词")
    conversation_uid = serializers.UUIDField(required=False, help_text="所属会话对外 UUID")
    source_message_uid = serializers.UUIDField(required=False, help_text="来源消息对外 UUID")


class AttachmentUpdateRequestSerializer(serializers.Serializer):
    attachment_uid = serializers.UUIDField(help_text="附件对外 UUID")
    title = serializers.CharField(
        required=False,
        allow_blank=False,
        max_length=255,
        help_text="附件标题",
    )
    output_data = EditableAttachmentOutputDataField(
        required=False,
        help_text="完整替换的可编辑类型产物",
    )

    def validate(self, attrs):
        if "title" not in attrs and "output_data" not in attrs:
            raise serializers.ValidationError("至少提交 title 或 output_data")
        return attrs


class AttachmentSourceMessageSummarySerializer(serializers.Serializer):
    uid = serializers.UUIDField(help_text="来源消息对外 UUID")
    message_type = serializers.ChoiceField(choices=MessageType.choices, help_text="来源消息类型")
    created_at = serializers.DateTimeField(help_text="来源消息创建时间")


class AttachmentConversationSummarySerializer(serializers.Serializer):
    uid = serializers.UUIDField(help_text="所属会话对外 UUID")
    title = serializers.CharField(allow_blank=True, help_text="所属会话标题")
    created_at = serializers.DateTimeField(help_text="所属会话创建时间")
    updated_at = serializers.DateTimeField(help_text="所属会话最后更新时间")


class AttachmentResponseSerializer(serializers.Serializer):
    """附件详情响应；类型专属快照由已注册 Handler 的 Pydantic 模型解析。"""

    uid = serializers.UUIDField(help_text="附件对外 UUID")
    source_message_uid = serializers.UUIDField(help_text="来源消息对外 UUID")
    attachment_type = serializers.ChoiceField(choices=AttachmentType.choices, help_text="附件类型")
    status = serializers.ChoiceField(choices=ExecutionStatus.choices, help_text="附件执行状态")
    title = serializers.CharField(allow_blank=True, help_text="附件标题")
    content_updated_at = serializers.DateTimeField(allow_null=True, help_text="附件内容最后更新时间")
    input_data = AttachmentInputDataField(help_text="附件类型化输入快照")
    output_data = AttachmentOutputDataField(
        allow_null=True,
        required=False,
        help_text="附件类型化输出快照",
    )
    error_code = serializers.CharField(allow_blank=True, help_text="稳定公开错误码")
    error_message = serializers.CharField(allow_blank=True, help_text="脱敏后的公开错误信息")
    supports_feedback = serializers.BooleanField(help_text="附件类型是否支持当前用户反馈")
    is_stream = serializers.BooleanField(help_text="是否使用流式输出；为真时可订阅流快照与 SSE 接口")
    export_formats = serializers.ListField(
        child=serializers.ChoiceField(choices=AttachmentExportFormat.choices),
        help_text="当前类型支持的后端导出格式",
    )
    feedback = FeedbackResponseSerializer(allow_null=True, help_text="当前用户对附件的反馈")
    created_at = serializers.DateTimeField(help_text="附件创建时间")
    updated_at = serializers.DateTimeField(help_text="附件最后更新时间")

    def to_representation(self, instance):
        handler = attachment_handler_registry.require(instance.attachment_type)
        supports_feedback = handler.supports_feedback
        output_data = None
        if instance.output_data is not None:
            output_data = parse_snapshot(
                handler.output_model,
                instance.output_data,
                field_name="output_data",
                error_type=AttachmentSnapshotValidationError,
            ).model_dump(mode="json")

        return {
            "uid": str(instance.uid),
            "source_message_uid": str(instance.source_message.uid),
            "attachment_type": instance.attachment_type,
            "status": instance.status,
            "title": instance.title,
            "content_updated_at": instance.content_updated_at,
            "input_data": parse_snapshot(
                handler.input_model,
                instance.input_data,
                field_name="input_data",
                error_type=AttachmentSnapshotValidationError,
            ).model_dump(mode="json"),
            "output_data": output_data,
            "error_code": instance.error_code,
            "error_message": instance.error_message,
            "supports_feedback": supports_feedback,
            "is_stream": instance.is_stream,
            "export_formats": [str(export_format) for export_format in handler.export_formats],
            "feedback": (
                FeedbackResponseSerializer(getattr(instance, "_current_feedback", None)).data
                if supports_feedback and getattr(instance, "_current_feedback", None)
                else None
            ),
            "created_at": instance.created_at,
            "updated_at": instance.updated_at,
        }


class AttachmentListItemSerializer(serializers.Serializer):
    """附件列表项摘要，不读取输入和输出大 JSON。"""

    uid = serializers.UUIDField(help_text="附件对外 UUID")
    attachment_type = serializers.ChoiceField(choices=AttachmentType.choices, help_text="附件类型")
    status = serializers.ChoiceField(choices=ExecutionStatus.choices, help_text="附件执行状态")
    title = serializers.CharField(allow_blank=True, help_text="附件标题")
    created_at = serializers.DateTimeField(help_text="附件创建时间")
    content_updated_at = serializers.DateTimeField(allow_null=True, help_text="附件内容最后更新时间")
    source_message = AttachmentSourceMessageSummarySerializer(help_text="来源消息摘要")
    conversation = AttachmentConversationSummarySerializer(help_text="所属会话摘要")
    supports_feedback = serializers.BooleanField(help_text="附件类型是否支持当前用户反馈")
    export_formats = serializers.ListField(
        child=serializers.ChoiceField(choices=AttachmentExportFormat.choices),
        help_text="当前类型支持的后端导出格式",
    )

    def to_representation(self, instance):
        conversation = instance.source_message.conversation
        handler = attachment_handler_registry.require(instance.attachment_type)
        return {
            "uid": str(instance.uid),
            "attachment_type": instance.attachment_type,
            "status": instance.status,
            "title": instance.title,
            "created_at": instance.created_at,
            "content_updated_at": instance.content_updated_at,
            "source_message": {
                "uid": str(instance.source_message.uid),
                "message_type": instance.source_message.message_type,
                "created_at": instance.source_message.created_at,
            },
            "conversation": {
                "uid": str(conversation.uid),
                "title": conversation.title,
                "created_at": conversation.created_at,
                "updated_at": conversation.updated_at,
            },
            "supports_feedback": handler.supports_feedback,
            "export_formats": [str(export_format) for export_format in handler.export_formats],
        }

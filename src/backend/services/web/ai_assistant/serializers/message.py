from django.conf import settings
from drf_spectacular.utils import PolymorphicProxySerializer, extend_schema_field
from rest_framework import serializers

from services.web.ai_assistant.constants import (
    AttachmentExportFormat,
    AttachmentType,
    ExecutionStatus,
    MessageHistoryDirection,
    MessageType,
)
from services.web.ai_assistant.handlers import (
    attachment_handler_registry,
    message_handler_registry,
)
from services.web.ai_assistant.schemas import MessageSchema, parse_snapshot
from services.web.ai_assistant.serializers.feedback import FeedbackResponseSerializer


def _message_schema_mapping(model_attribute: str) -> dict[str, type[MessageSchema]]:
    """按消息类型返回 Handler 快照模型，未注册类型降级为通用对象。"""

    handlers = message_handler_registry.handlers
    return {
        str(message_type): getattr(handlers.get(str(message_type)), model_attribute, MessageSchema)
        for message_type in MessageType
    }


def _message_schema_models(model_attribute: str) -> list[type[MessageSchema]]:
    """按注册顺序返回唯一模型，避免多个消息类型生成重复 oneOf 分支。"""

    return list(dict.fromkeys(_message_schema_mapping(model_attribute).values()))


@extend_schema_field(
    PolymorphicProxySerializer(
        component_name="AIMessageInputData",
        serializers=lambda: _message_schema_models("input_model"),
        # message_type 位于外层消息对象，不在 input_data 内；这里只生成 oneOf，
        # 避免 OpenAPI 客户端错误地从嵌套 JSON 中读取 discriminator。
        resource_type_field_name=None,
    )
)
class MessageInputDataField(serializers.JSONField):
    """在 OpenAPI 中按 message_type 展示对应 Handler 输入协议。"""


@extend_schema_field(
    PolymorphicProxySerializer(
        component_name="AIMessageOutputData",
        serializers=lambda: _message_schema_models("output_model"),
        resource_type_field_name=None,
    )
)
class MessageOutputDataField(serializers.JSONField):
    """在 OpenAPI 中按 message_type 展示对应 Handler 输出协议。"""


class InitialMessageRequestSerializer(serializers.Serializer):
    """会话原子初始化时允许携带的一条系统选择消息。"""

    message_type = serializers.ChoiceField(
        choices=[MessageType.SYSTEM_SELECTION],
        help_text="初始化消息类型，一期固定为 SYSTEM_SELECTION",
    )
    input_data = MessageInputDataField(help_text="由系统选择 Handler 输入模型校验的业务数据")


class MessageCreateRequestSerializer(serializers.Serializer):
    """创建消息只接收业务输入，状态和输出均由平台生成。"""

    conversation_uid = serializers.UUIDField(help_text="所属会话对外 UUID")
    message_type = serializers.ChoiceField(choices=MessageType.choices, help_text="消息类型")
    parent_message_uid = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text="直接父消息对外 UUID；根消息可不传",
    )
    input_data = MessageInputDataField(help_text="由消息类型对应 Pydantic 输入模型校验的业务数据")


class MessageDetailRequestSerializer(serializers.Serializer):
    message_uid = serializers.UUIDField(help_text="消息对外 UUID")


class MessagePreviewExportRequestSerializer(serializers.Serializer):
    message_uid = serializers.UUIDField(help_text="成功日志检索消息对外 UUID")
    export_config = serializers.JSONField(
        required=False,
        default=dict,
        help_text=(
            "导出配置（field_scope/fields/flatten_extension/extension_keys）；"
            "flatten_extension=true 时把 extend_data 子键平铺为单独列"
        ),
    )


class MessageFullExportRequestSerializer(serializers.Serializer):
    """全量导出只接收输出列配置，数据范围由消息快照重建，前端不可覆盖。"""

    message_uid = serializers.UUIDField(help_text="成功日志检索消息对外 UUID")
    export_config = serializers.JSONField(
        required=False,
        default=dict,
        help_text=(
            "导出列配置（field_scope/fields/flatten_extension/extension_keys）；"
            "field_scope 支持 ai_standard（AI助手标准展示列，与预览导出一致），不影响检索数据范围"
        ),
    )


class MessageFullExportResponseSerializer(serializers.Serializer):
    export_task_id = serializers.IntegerField(help_text="既有 LogExportTask 整数 ID")
    status = serializers.CharField(help_text="导出任务公开状态")


class MessageListRequestSerializer(serializers.Serializer):
    """通过可选 UID 锚点向前或向后读取消息窗口。"""

    conversation_uid = serializers.UUIDField(help_text="所属会话对外 UUID")
    anchor_uid = serializers.UUIDField(required=False, help_text="历史窗口锚点消息 UUID")
    direction = serializers.ChoiceField(
        choices=MessageHistoryDirection.choices,
        required=False,
        help_text="BEFORE 获取更早消息，AFTER 获取更新消息",
    )
    limit = serializers.IntegerField(
        required=False,
        default=settings.AI_ASSISTANT_MESSAGE_HISTORY_DEFAULT_LIMIT,
        min_value=1,
        max_value=settings.AI_ASSISTANT_MESSAGE_HISTORY_MAX_LIMIT,
        help_text="单次返回消息数量，默认值和上限由服务配置控制",
    )
    include_content = serializers.BooleanField(
        required=False,
        default=True,
        help_text="是否返回输入和输出完整快照",
    )

    def validate(self, attrs):
        if bool(attrs.get("anchor_uid")) != bool(attrs.get("direction")):
            raise serializers.ValidationError("anchor_uid 和 direction 必须同时传入")
        return attrs


class AttachmentSummarySerializer(serializers.Serializer):
    """消息响应中的附件关系摘要，不包含附件完整产物。"""

    uid = serializers.UUIDField(help_text="附件对外 UUID")
    attachment_type = serializers.ChoiceField(choices=AttachmentType.choices, help_text="附件类型")
    status = serializers.ChoiceField(choices=ExecutionStatus.choices, help_text="附件执行状态")
    title = serializers.CharField(allow_blank=True, help_text="附件标题")
    content_updated_at = serializers.DateTimeField(allow_null=True, help_text="附件内容最后更新时间")
    created_at = serializers.DateTimeField(help_text="附件创建时间")
    supports_feedback = serializers.BooleanField(help_text="附件类型是否支持当前用户反馈")
    export_formats = serializers.ListField(
        child=serializers.ChoiceField(choices=AttachmentExportFormat.choices),
        help_text="当前类型支持的后端导出格式",
    )

    def to_representation(self, instance):
        handler = attachment_handler_registry.require(instance.attachment_type)
        return {
            "uid": str(instance.uid),
            "attachment_type": instance.attachment_type,
            "status": instance.status,
            "title": instance.title,
            "content_updated_at": instance.content_updated_at,
            "created_at": instance.created_at,
            "supports_feedback": handler.supports_feedback,
            "export_formats": [str(export_format) for export_format in handler.export_formats],
        }


class MessageResponseSerializer(serializers.Serializer):
    """消息通用响应；类型专属快照由已注册 Handler 的 Pydantic 模型解析。"""

    uid = serializers.UUIDField(help_text="消息对外 UUID")
    conversation_uid = serializers.UUIDField(help_text="所属会话对外 UUID")
    parent_message_uid = serializers.UUIDField(allow_null=True, help_text="直接父消息对外 UUID")
    message_type = serializers.ChoiceField(choices=MessageType.choices, help_text="消息类型")
    status = serializers.ChoiceField(choices=ExecutionStatus.choices, help_text="消息执行状态")
    input_data = MessageInputDataField(required=False, help_text="消息类型化输入快照")
    output_data = MessageOutputDataField(required=False, allow_null=True, help_text="消息类型化输出快照")
    error_code = serializers.CharField(allow_blank=True, help_text="稳定公开错误码")
    error_message = serializers.CharField(allow_blank=True, help_text="脱敏后的公开错误信息")
    attachments = AttachmentSummarySerializer(many=True, help_text="消息关联的附件摘要")
    supports_feedback = serializers.BooleanField(help_text="消息类型是否支持当前用户反馈")
    feedback = FeedbackResponseSerializer(allow_null=True, help_text="当前用户对消息的反馈")
    created_at = serializers.DateTimeField(help_text="消息创建时间")
    updated_at = serializers.DateTimeField(help_text="消息最后更新时间")

    def to_representation(self, instance):
        """读取 JSONField 时重新执行类型校验，避免损坏快照扩散到前端。"""

        handler = message_handler_registry.require(instance.message_type)
        supports_feedback = handler.supports_feedback
        data = {
            "uid": str(instance.uid),
            "conversation_uid": str(instance.conversation.uid),
            "parent_message_uid": str(instance.parent_message.uid) if instance.parent_message else None,
            "message_type": instance.message_type,
            "status": instance.status,
            "error_code": instance.error_code,
            "error_message": instance.error_message,
            "attachments": AttachmentSummarySerializer(instance.attachments.all(), many=True).data,
            "supports_feedback": supports_feedback,
            "feedback": (
                FeedbackResponseSerializer(getattr(instance, "_current_feedback", None)).data
                if supports_feedback and getattr(instance, "_current_feedback", None)
                else None
            ),
            "created_at": instance.created_at,
            "updated_at": instance.updated_at,
        }
        if self.context.get("include_content", True):
            input_data = parse_snapshot(
                handler.input_model,
                instance.input_data,
                field_name="input_data",
            ).model_dump(mode="json")
            output_data = None
            if instance.output_data is not None:
                output_data = parse_snapshot(
                    handler.output_model,
                    instance.output_data,
                    field_name="output_data",
                ).model_dump(mode="json")
            data.update(
                input_data=input_data,
                output_data=output_data,
            )
        return data


class MessageWindowResponseSerializer(serializers.Serializer):
    """消息历史窗口元数据及其正序消息列表。"""

    first_uid = serializers.UUIDField(allow_null=True, help_text="当前窗口第一条消息 UUID")
    last_uid = serializers.UUIDField(allow_null=True, help_text="当前窗口最后一条消息 UUID")
    has_before = serializers.BooleanField(help_text="当前窗口之前是否还有消息")
    has_after = serializers.BooleanField(help_text="当前窗口之后是否还有消息")
    results = MessageResponseSerializer(many=True, help_text="按内部递增 ID 正序返回的消息")

    def to_representation(self, instance):
        return {
            "first_uid": instance.first_uid,
            "last_uid": instance.last_uid,
            "has_before": instance.has_before,
            "has_after": instance.has_after,
            "results": MessageResponseSerializer(
                instance.results,
                many=True,
                context={"include_content": instance.include_content},
            ).data,
        }

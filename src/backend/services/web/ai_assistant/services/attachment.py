import logging
from collections.abc import Mapping
from typing import Any
from uuid import uuid4

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone

from services.web.ai_assistant.constants import (
    AttachmentErrorCode,
    AttachmentExportFormat,
    ExecutionMode,
    ExecutionStatus,
    FeedbackSourceType,
)
from services.web.ai_assistant.exceptions import (
    AIAssistantException,
    AttachmentExportFailed,
    AttachmentExportNotSupported,
    AttachmentNotEditable,
    AttachmentNotFound,
    AttachmentOutputValidationError,
    AttachmentSnapshotValidationError,
    InvalidAttachmentPreparation,
    InvalidAttachmentSource,
    InvalidAttachmentState,
    StreamNotEnabled,
)
from services.web.ai_assistant.handlers import (
    AttachmentExecutionContext,
    AttachmentExportResult,
    attachment_handler_registry,
)
from services.web.ai_assistant.models import Attachment, Conversation, Message
from services.web.ai_assistant.schemas import dump_snapshot, parse_snapshot
from services.web.ai_assistant.services.attachment_execution import (
    finish_attachment_failure,
)
from services.web.ai_assistant.services.feedback import FeedbackService

logger = logging.getLogger(__name__)


class AttachmentService:
    """在当前用户边界内创建、查询、编辑和重试附件。"""

    def __init__(self, *, user: str):
        self.user = user

    def create(
        self,
        *,
        source_message_uid: str,
        attachment_type: str,
        input_data: Mapping[str, Any],
    ) -> Attachment:
        """按固定顺序准备附件；prepare 只在首次创建时执行。"""

        source_message = self._get_visible_success_source_message(source_message_uid=source_message_uid)
        handler = attachment_handler_registry.require(attachment_type)
        parsed_input = parse_snapshot(
            handler.input_model,
            input_data,
            field_name="input_data",
            error_type=AttachmentSnapshotValidationError,
        )

        # prepare 可能访问外部上下文，必须放在事务外，避免把长耗时逻辑带进写事务。
        preparation = handler.prepare(
            user=self.user,
            source_message=source_message,
            input_data=parsed_input,
        )
        title = self._normalize_title(preparation.title)
        parsed_context = parse_snapshot(
            handler.context_model,
            preparation.context_data,
            field_name="context_data",
            error_type=AttachmentSnapshotValidationError,
        )

        if handler.execution_mode == ExecutionMode.ASYNC:
            return self._create_async(
                source_message=source_message,
                attachment_type=str(handler.attachment_type),
                title=title,
                input_snapshot=parsed_input.model_dump(mode="json"),
                context_snapshot=parsed_context.model_dump(mode="json"),
            )

        execution = AttachmentExecutionContext(
            source_message=source_message,
            input_data=parsed_input,
            context_data=parsed_context,
        )
        try:
            output_snapshot = dump_snapshot(
                handler.output_model,
                handler.execute(execution=execution),
                field_name="output_data",
                error_type=AttachmentSnapshotValidationError,
            )
        except AttachmentSnapshotValidationError as error:
            raise AttachmentOutputValidationError() from error

        now = timezone.now()
        with transaction.atomic():
            self._lock_active_source(source_message=source_message)
            return Attachment.objects.create(
                source_message=source_message,
                attachment_type=str(handler.attachment_type),
                title=title,
                status=ExecutionStatus.SUCCESS,
                task_id=None,
                input_data=parsed_input.model_dump(mode="json"),
                context_data=parsed_context.model_dump(mode="json"),
                output_data=output_snapshot,
                last_activity_at=now,
                finished_at=now,
                # 同步类型不进入流式通道，显式固化为 False，避免继承默认值歧义。
                is_stream=False,
                content_updated_at=now,
                created_by=self.user,
                updated_by=self.user,
            )

    def get(self, *, attachment_uid: str) -> Attachment:
        """返回当前用户可见会话中的一个附件详情。"""

        return self._get_visible_attachment(attachment_uid=attachment_uid, bind_feedback=True)

    def export(
        self,
        *,
        attachment_uid: str,
        export_format: str | AttachmentExportFormat,
    ) -> AttachmentExportResult:
        """实时导出当前用户可见的成功附件，不修改附件也不创建额外记录。"""

        attachment = self._get_visible_attachment(attachment_uid=attachment_uid, bind_feedback=False)
        if attachment.status != ExecutionStatus.SUCCESS:
            raise InvalidAttachmentState()
        try:
            normalized_format = AttachmentExportFormat(export_format)
        except (TypeError, ValueError) as error:
            raise AttachmentExportNotSupported() from error

        handler = attachment_handler_registry.require(attachment.attachment_type)
        if normalized_format not in handler.export_formats:
            raise AttachmentExportNotSupported()
        output_data = parse_snapshot(
            handler.output_model,
            attachment.output_data,
            field_name="output_data",
            error_type=AttachmentSnapshotValidationError,
        )
        try:
            result = handler.export(
                attachment=attachment,
                output_data=output_data,
                export_format=normalized_format,
            )
            if not isinstance(result, AttachmentExportResult):
                raise TypeError("Attachment Handler export() 必须返回 AttachmentExportResult")
            return result
        except AIAssistantException:
            raise
        except Exception as error:
            # 仅记录稳定元信息，导出快照可能含敏感 AI 内容，严禁写入日志。
            logger.exception(
                "AI 助手附件导出失败",
                extra={
                    "attachment_id": attachment.id,
                    "attachment_type": attachment.attachment_type,
                    "export_format": normalized_format,
                },
            )
            raise AttachmentExportFailed() from error

    def get_for_stream(self, *, attachment_uid: str, include_archive: bool = False) -> Attachment:
        """返回当前用户可见的流式附件，不绑定 Feedback 或解析大型产物。

        SSE 只需主键和流标识；快照额外读取 ``stream_archive``。
        两者均跳过 Feedback 与业务 input/output JSON，避免多端连接放大数据库传输。
        """

        fields = ["id", "uid", "status", "task_id", "is_stream", "stream_config"]
        if include_archive:
            fields.append("stream_archive")
        attachment = self._get_visible_attachment(
            attachment_uid=attachment_uid,
            bind_feedback=False,
            only_fields=fields,
        )
        if not attachment.is_stream:
            raise StreamNotEnabled()
        return attachment

    def _get_visible_attachment(
        self,
        *,
        attachment_uid: str,
        bind_feedback: bool,
        only_fields: list[str] | None = None,
    ) -> Attachment:
        """统一 UUID、用户及软删除会话边界；导出按需跳过无关的 Feedback 查询。"""

        try:
            queryset = self._visible_attachments()
            if only_fields is None:
                queryset = queryset.select_related("source_message__conversation")
            else:
                queryset = queryset.only(*only_fields)
            attachment = queryset.filter(uid=attachment_uid).first()
        except DjangoValidationError as error:
            raise AttachmentNotFound() from error
        if attachment is None:
            raise AttachmentNotFound()
        if bind_feedback:
            FeedbackService(user=self.user).bind_current_feedback(
                sources=[attachment], source_type=FeedbackSourceType.ATTACHMENT
            )
        return attachment

    def list(
        self,
        *,
        attachment_types: list[str] | None = None,
        statuses: list[str] | None = None,
        keyword: str = "",
        conversation_uid: str | None = None,
        source_message_uid: str | None = None,
    ):
        """返回当前用户可见附件列表，并只加载列表视图必需字段。"""

        filters: dict[str, Any] = {}
        if attachment_types:
            filters["attachment_type__in"] = attachment_types
        if statuses:
            filters["status__in"] = statuses
        if keyword.strip():
            filters["title__icontains"] = keyword.strip()
        if conversation_uid:
            filters["source_message__conversation__uid"] = conversation_uid
        if source_message_uid:
            filters["source_message__uid"] = source_message_uid

        return (
            self._visible_attachments()
            .filter(**filters)
            .select_related("source_message__conversation")
            .only(
                "id",
                "uid",
                "source_message_id",
                "source_message__id",
                "source_message__uid",
                "source_message__message_type",
                "source_message__created_at",
                "source_message__conversation_id",
                "source_message__conversation__id",
                "source_message__conversation__uid",
                "source_message__conversation__title",
                "source_message__conversation__created_at",
                "source_message__conversation__updated_at",
                "attachment_type",
                "status",
                "title",
                "content_updated_at",
                "created_at",
            )
            .order_by("-content_updated_at", "-id")
        )

    def update(
        self,
        *,
        attachment_uid: str,
        title: str | None = None,
        output_data: Mapping[str, Any] | None = None,
    ) -> Attachment:
        """编辑标题或产物；同一次 PATCH 始终收敛为一条 UPDATE。"""

        attachment = self.get(attachment_uid=attachment_uid)
        updates: dict[str, Any] = {}

        if title is not None:
            updates["title"] = self._normalize_title(title)

        if output_data is not None:
            if attachment.status != ExecutionStatus.SUCCESS:
                raise InvalidAttachmentState()
            handler = attachment_handler_registry.require(attachment.attachment_type)
            if not handler.supports_output_edit():
                raise AttachmentNotEditable()

            # 用户提交的数据格式错误属于 400；仅数据库旧快照或 Handler 返回值错误属于平台 500。
            submitted_output = parse_snapshot(
                handler.output_model,
                output_data,
                field_name="output_data",
                error_type=AttachmentSnapshotValidationError,
            )
            try:
                current_output = parse_snapshot(
                    handler.output_model,
                    attachment.output_data,
                    field_name="output_data",
                    error_type=AttachmentSnapshotValidationError,
                )
                updates["output_data"] = dump_snapshot(
                    handler.output_model,
                    handler.edit_output(
                        attachment=attachment,
                        current_output=current_output,
                        submitted_output=submitted_output,
                    ),
                    field_name="output_data",
                    error_type=AttachmentSnapshotValidationError,
                )
            except AttachmentSnapshotValidationError as error:
                raise AttachmentOutputValidationError() from error

        if not updates:
            return attachment

        now = timezone.now()
        updates.update(
            content_updated_at=now,
            updated_by=self.user,
            updated_at=now,
        )
        for field, value in updates.items():
            setattr(attachment, field, value)
        # Service 已显式绑定用户，跳过 OperateRecordModel 从请求上下文重写操作人。
        attachment.save(update_record=False, update_fields=list(updates))
        return attachment

    def retry(self, *, attachment_uid: str) -> Attachment:
        """仅 FAILED + ASYNC 附件允许重试，并用旧 task_id 做 CAS 抢占。"""

        attachment = self.get(attachment_uid=attachment_uid)
        handler = attachment_handler_registry.require(attachment.attachment_type)
        if (
            attachment.status != ExecutionStatus.FAILED
            or handler.execution_mode != ExecutionMode.ASYNC
            or not attachment.task_id
        ):
            raise InvalidAttachmentState()

        old_task_id = attachment.task_id
        new_task_id = str(uuid4())
        now = timezone.now()
        # 流式附件保留旧配置供新 Worker 补发 reset；非流式统一清空避免残留脏数据。
        stream_updates: dict[str, Any] = {"stream_archive": []}
        if not attachment.is_stream:
            stream_updates["stream_config"] = {}
        with transaction.atomic():
            # 会话锁隔离删除竞态；附件本身仍依赖 FAILED + old task_id CAS 抢占重试。
            self._lock_active_source(source_message=attachment.source_message)
            updated = Attachment.restart_failed(
                instance_id=attachment.id,
                old_task_id=old_task_id,
                new_task_id=new_task_id,
                extra_updates={
                    **stream_updates,
                    "content_updated_at": now,
                    "updated_by": self.user,
                    "updated_at": now,
                },
                now=now,
            )
            if not updated:
                raise InvalidAttachmentState()
            # CAS 使用 QuerySet 原子抢占；刷新实例供 on_commit 投递和接口返回共同使用。
            attachment.refresh_from_db()

            def after_commit() -> None:
                """事务提交后投递新任务，由下一次 execution 负责通知旧流。"""

                self._dispatch(handler=handler, attachment=attachment)

            # 只有 CAS 成功的请求才能注册 on_commit，避免旧 task_id 被重新投递。
            transaction.on_commit(after_commit)
        return attachment

    def _visible_attachments(self):
        """统一收敛附件可见边界，避免越权访问跨用户/已删除会话数据。"""

        return Attachment.objects.filter(
            created_by=self.user,
            source_message__conversation__created_by=self.user,
            source_message__conversation__is_deleted=False,
        )

    def _get_visible_success_source_message(self, *, source_message_uid: str) -> Message:
        """创建入口只接受当前用户未删除会话中的 SUCCESS 来源消息。"""

        try:
            source_message = Message.objects.filter(
                uid=source_message_uid,
                created_by=self.user,
                conversation__created_by=self.user,
                conversation__is_deleted=False,
                status=ExecutionStatus.SUCCESS,
            ).first()
        except DjangoValidationError as error:
            raise InvalidAttachmentSource() from error
        if source_message is None:
            raise InvalidAttachmentSource()
        return source_message

    def _lock_active_source(self, *, source_message: Message) -> None:
        """锁定来源会话并复核消息，避免删除提交后继续创建隐藏附件。"""

        conversation_exists = (
            Conversation.objects.select_for_update()
            .filter(
                id=source_message.conversation_id,
                created_by=self.user,
                is_deleted=False,
            )
            .exists()
        )
        message_exists = Message.objects.filter(
            id=source_message.id,
            conversation_id=source_message.conversation_id,
            created_by=self.user,
            status=ExecutionStatus.SUCCESS,
        ).exists()
        if not conversation_exists or not message_exists:
            raise InvalidAttachmentSource()

    @staticmethod
    def _normalize_title(title: str) -> str:
        """统一裁剪标题并复用同一业务异常，避免空白标题落库。"""

        normalized = title.strip()
        if not normalized or len(normalized) > 255:
            raise InvalidAttachmentPreparation()
        return normalized

    def _create_async(
        self,
        *,
        source_message: Message,
        attachment_type: str,
        title: str,
        input_snapshot: dict[str, Any],
        context_snapshot: dict[str, Any],
    ) -> Attachment:
        """短事务只负责落库和注册 on_commit，真正投递放到提交后。"""

        task_id = str(uuid4())
        now = timezone.now()
        handler = attachment_handler_registry.require(attachment_type)
        with transaction.atomic():
            self._lock_active_source(source_message=source_message)
            attachment = Attachment.objects.create(
                source_message=source_message,
                attachment_type=attachment_type,
                title=title,
                status=ExecutionStatus.PROCESSING,
                task_id=task_id,
                input_data=input_snapshot,
                context_data=context_snapshot,
                output_data=None,
                queued_at=now,
                last_activity_at=now,
                # 创建时固化 Handler 的流能力声明，后续执行和接口都以模型字段为准。
                is_stream=handler.is_stream,
                content_updated_at=now,
                created_by=self.user,
                updated_by=self.user,
            )
            transaction.on_commit(lambda: self._dispatch(handler=handler, attachment=attachment))
        return attachment

    @staticmethod
    def _dispatch(*, handler, attachment: Attachment) -> None:
        """始终使用数据库 task_id 投递；失败时刷新返回实例，避免调用方拿到旧状态。"""

        try:
            handler.async_task.apply_async(
                kwargs={"attachment_id": attachment.id, "task_id": attachment.task_id},
                task_id=attachment.task_id,
            )
        except Exception as error:
            logger.exception(
                "AI 助手附件任务投递失败",
                extra={
                    "attachment_id": attachment.id,
                    "attachment_type": attachment.attachment_type,
                    "task_id": attachment.task_id,
                },
            )
            if finish_attachment_failure(
                attachment_id=attachment.id,
                task_id=attachment.task_id,
                exception=error,
                error_code=AttachmentErrorCode.TASK_DISPATCH_FAILED,
            ):
                attachment.refresh_from_db()

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Generic, TypeVar
from uuid import uuid4

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone

from services.web.ai_assistant.constants import (
    AttachmentErrorCode,
    ExecutionMode,
    ExecutionStatus,
)
from services.web.ai_assistant.exceptions import (
    AIAssistantException,
    AttachmentNotFound,
    AttachmentOutputValidationError,
    AttachmentSnapshotValidationError,
    InvalidAttachmentPreparation,
    InvalidAttachmentSource,
    InvalidAttachmentState,
    StaleAttachmentTask,
)
from services.web.ai_assistant.handlers import (
    AttachmentExecutionContext,
    attachment_handler_registry,
)
from services.web.ai_assistant.models import Attachment, Message
from services.web.ai_assistant.schemas import (
    MessageSchema,
    SnapshotInput,
    dump_snapshot,
    parse_snapshot,
)

logger = logging.getLogger(__name__)

InputT = TypeVar("InputT", bound=MessageSchema)
ContextT = TypeVar("ContextT", bound=MessageSchema)


@dataclass(frozen=True, slots=True)
class AttachmentExecution(Generic[InputT, ContextT]):
    """业务 Task 执行时读取到的附件和类型化快照。"""

    attachment: Attachment
    input_data: InputT
    context_data: ContextT

    @property
    def source_message(self) -> Message:
        return self.attachment.source_message


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
        return Attachment.objects.create(
            source_message=source_message,
            attachment_type=str(handler.attachment_type),
            title=title,
            status=ExecutionStatus.SUCCESS,
            task_id=None,
            input_data=parsed_input.model_dump(mode="json"),
            context_data=parsed_context.model_dump(mode="json"),
            output_data=output_snapshot,
            content_updated_at=now,
            created_by=self.user,
            updated_by=self.user,
        )

    def get(self, *, attachment_uid: str) -> Attachment:
        """返回当前用户可见会话中的一个附件详情。"""

        try:
            attachment = (
                self._visible_attachments()
                .select_related("source_message__conversation")
                .filter(uid=attachment_uid)
                .first()
            )
        except DjangoValidationError as error:
            raise AttachmentNotFound() from error
        if attachment is None:
            raise AttachmentNotFound()
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
                raise handler.edit_output(
                    attachment=attachment,
                    current_output=None,  # pragma: no cover - 立即抛异常
                    submitted_output=None,
                )

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
        with transaction.atomic():
            # 不加行锁；依赖 FAILED + old task_id 的 CAS 让并发重试只有一个成功。
            updated = Attachment.objects.filter(
                id=attachment.id,
                status=ExecutionStatus.FAILED,
                task_id=old_task_id,
            ).update(
                status=ExecutionStatus.PROCESSING,
                task_id=new_task_id,
                output_data=None,
                error_code="",
                error_message="",
                stream_config={},
                stream_archive=[],
                content_updated_at=now,
                updated_by=self.user,
                updated_at=now,
            )
            if updated != 1:
                raise InvalidAttachmentState()
            # CAS 使用 QuerySet 原子抢占；刷新实例供 on_commit 投递和接口返回共同使用。
            # 流式配置与事件均属于单次运行，任务启动前先清空，避免排队或投递失败时暴露旧数据。
            attachment.refresh_from_db()
            # 只有 CAS 成功的请求才能注册 on_commit，避免旧 task_id 被重新投递。
            transaction.on_commit(lambda: self._dispatch(handler=handler, attachment=attachment))
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
            attachment = Attachment.objects.create(
                source_message=source_message,
                attachment_type=attachment_type,
                title=title,
                status=ExecutionStatus.PROCESSING,
                task_id=task_id,
                input_data=input_snapshot,
                context_data=context_snapshot,
                output_data=None,
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
            if AttachmentExecutor.mark_failed(
                attachment_id=attachment.id,
                task_id=attachment.task_id,
                exception=error,
                error_code=AttachmentErrorCode.TASK_DISPATCH_FAILED,
            ):
                attachment.refresh_from_db()


class AttachmentExecutor:
    """统一加载附件执行上下文，并以 CAS 条件收敛终态。"""

    @classmethod
    def load_execution(
        cls,
        *,
        attachment_id: int,
        task_id: str,
        celery_task_id: str,
    ) -> AttachmentExecution:
        """单次加载 PROCESSING 附件，并解析类型化快照。"""

        if celery_task_id != task_id:
            raise StaleAttachmentTask()
        attachment = (
            Attachment.objects.select_related("source_message__conversation")
            .filter(
                id=attachment_id,
                task_id=task_id,
                status=ExecutionStatus.PROCESSING,
            )
            .first()
        )
        if attachment is None:
            raise StaleAttachmentTask()
        handler = attachment_handler_registry.require(attachment.attachment_type)
        return AttachmentExecution(
            attachment=attachment,
            input_data=parse_snapshot(
                handler.input_model,
                attachment.input_data,
                field_name="input_data",
                error_type=AttachmentSnapshotValidationError,
            ),
            context_data=parse_snapshot(
                handler.context_model,
                attachment.context_data,
                field_name="context_data",
                error_type=AttachmentSnapshotValidationError,
            ),
        )

    @staticmethod
    def mark_success(
        *,
        execution: AttachmentExecution,
        task_id: str,
        output_data: SnapshotInput,
    ) -> dict[str, Any]:
        """校验输出并原子写入成功终态；并发任务只有首个终态写入者获胜。"""

        handler = attachment_handler_registry.require(execution.attachment.attachment_type)
        try:
            output_snapshot = dump_snapshot(
                handler.output_model,
                output_data,
                field_name="output_data",
                error_type=AttachmentSnapshotValidationError,
            )
        except AttachmentSnapshotValidationError as error:
            raise AttachmentOutputValidationError() from error
        updated = Attachment.objects.filter(
            id=execution.attachment.id,
            task_id=task_id,
            status=ExecutionStatus.PROCESSING,
        ).update(
            output_data=output_snapshot,
            status=ExecutionStatus.SUCCESS,
            error_code="",
            error_message="",
            content_updated_at=timezone.now(),
            updated_by=execution.attachment.created_by,
            updated_at=timezone.now(),
        )
        if updated != 1:
            raise StaleAttachmentTask()
        return output_snapshot

    @staticmethod
    def mark_failed(
        *,
        attachment_id: int,
        task_id: str,
        exception: Exception,
        error_code: str | AttachmentErrorCode = AttachmentErrorCode.TASK_EXECUTION_FAILED,
    ) -> bool:
        """提取可公开错误，并以相同 CAS 条件尝试写入失败终态。"""

        processing_attachment = Attachment.objects.filter(
            id=attachment_id,
            task_id=task_id,
            status=ExecutionStatus.PROCESSING,
        )
        created_by = processing_attachment.values_list("created_by", flat=True).first()
        if created_by is None:
            return False

        resolved_error_code = str(error_code)
        if resolved_error_code == AttachmentErrorCode.TASK_DISPATCH_FAILED:
            public_message = "附件任务投递失败，请稍后重试"
        elif isinstance(exception, AIAssistantException):
            public_message = exception.message
            if resolved_error_code == AttachmentErrorCode.TASK_EXECUTION_FAILED:
                resolved_error_code = exception.code
        else:
            public_message = "附件执行失败，请稍后重试"

        updated = processing_attachment.update(
            output_data=None,
            status=ExecutionStatus.FAILED,
            error_code=resolved_error_code,
            error_message=public_message,
            updated_by=created_by,
            updated_at=timezone.now(),
        )
        return updated == 1

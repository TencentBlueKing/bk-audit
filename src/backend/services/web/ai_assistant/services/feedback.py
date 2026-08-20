from dataclasses import dataclass
from datetime import datetime
from typing import TypeAlias
from uuid import UUID

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from services.web.ai_assistant.constants import ExecutionStatus, FeedbackSourceType
from services.web.ai_assistant.exceptions import (
    FeedbackNotSupported,
    FeedbackSourceNotFound,
    InvalidFeedbackSourceState,
)
from services.web.ai_assistant.handlers import (
    attachment_handler_registry,
    message_handler_registry,
)
from services.web.ai_assistant.models import Attachment, Feedback, Message

FeedbackSource: TypeAlias = Message | Attachment


@dataclass(frozen=True, slots=True)
class FeedbackDTO:
    """反馈公开快照，只保留外部 UID 和调用方可见字段。"""

    uid: UUID
    source_type: str
    source_uid: UUID
    feedback_type: str
    comment: str
    created_at: datetime
    updated_at: datetime


class FeedbackService:
    """在绑定用户边界内管理当前反馈。"""

    def __init__(self, *, user: str):
        self.user = user

    def upsert(
        self,
        *,
        source_type: str,
        source_uid: str,
        feedback_type: str,
        comment: str = "",
    ) -> FeedbackDTO:
        """创建或覆盖用户在单一来源对象上的反馈。"""

        source = self._resolve_source(source_type=source_type, source_uid=source_uid)
        lookup = {
            "created_by": self.user,
            "source_type": source_type,
            "source_id": source.id,
        }
        feedback = Feedback(
            **lookup,
            feedback_type=feedback_type,
            comment=comment,
            updated_at=timezone.now(),
            updated_by=self.user,
        )
        try:
            # 局部事务只提供 savepoint：唯一键冲突回滚后，外层事务仍可继续执行覆盖更新。
            with transaction.atomic():
                feedback.save(force_insert=True, update_record=False)
        except IntegrityError as error:
            updated = Feedback.objects.filter(**lookup).update(
                feedback_type=feedback_type,
                comment=comment,
                updated_by=self.user,
            )
            if not updated:
                # 仅将并发插入造成的唯一键冲突视为覆盖；其他完整性错误保持原始语义。
                raise error
            feedback = Feedback.objects.get(**lookup)
        return self._to_dto(feedback=feedback, source_uid=source.uid)

    def delete(self, *, feedback_uid: str) -> None:
        """删除当前用户自己的反馈，不暴露其他用户反馈是否存在。"""

        try:
            deleted, _ = Feedback.objects.filter(uid=feedback_uid, created_by=self.user).delete()
        except DjangoValidationError as error:
            raise FeedbackSourceNotFound() from error
        if not deleted:
            raise FeedbackSourceNotFound()

    def bind_current_feedback(self, *, sources: list[FeedbackSource], source_type: str) -> None:
        """批量给待序列化来源绑定当前用户反馈，避免 Serializer 触发 N+1 查询。"""

        if not sources:
            return
        source_uids = {source.id: source.uid for source in sources}
        feedbacks = Feedback.objects.filter(
            created_by=self.user,
            source_type=source_type,
            source_id__in=source_uids,
        )
        feedback_by_source_id = {
            feedback.source_id: self._to_dto(feedback=feedback, source_uid=source_uids[feedback.source_id])
            for feedback in feedbacks
        }
        # _current_feedback 是一次序列化的临时绑定，不是 Model 持久字段。
        for source in sources:
            source._current_feedback = feedback_by_source_id.get(source.id)

    def _resolve_source(self, *, source_type: str, source_uid: str) -> FeedbackSource:
        """按动态来源类型解析对象，并在同一查询内完成用户和软删除边界校验。"""

        try:
            if source_type == FeedbackSourceType.MESSAGE:
                source = (
                    Message.objects.filter(
                        uid=source_uid,
                        created_by=self.user,
                        conversation__created_by=self.user,
                        conversation__is_deleted=False,
                    )
                    .only("id", "uid", "status", "message_type")
                    .first()
                )
                handler_registry = message_handler_registry
                handler_type = source.message_type if source else None
            elif source_type == FeedbackSourceType.ATTACHMENT:
                source = (
                    Attachment.objects.filter(
                        uid=source_uid,
                        created_by=self.user,
                        source_message__conversation__created_by=self.user,
                        source_message__conversation__is_deleted=False,
                    )
                    .only("id", "uid", "status", "attachment_type")
                    .first()
                )
                handler_registry = attachment_handler_registry
                handler_type = source.attachment_type if source else None
            else:
                raise FeedbackSourceNotFound()
        except DjangoValidationError as error:
            raise FeedbackSourceNotFound() from error

        if source is None:
            raise FeedbackSourceNotFound()
        if source.status != ExecutionStatus.SUCCESS:
            raise InvalidFeedbackSourceState()
        if not handler_registry.require(handler_type).supports_feedback:
            raise FeedbackNotSupported()
        return source

    @staticmethod
    def _to_dto(*, feedback: Feedback, source_uid: UUID) -> FeedbackDTO:
        return FeedbackDTO(
            uid=feedback.uid,
            source_type=feedback.source_type,
            source_uid=source_uid,
            feedback_type=feedback.feedback_type,
            comment=feedback.comment,
            created_at=feedback.created_at,
            updated_at=feedback.updated_at,
        )

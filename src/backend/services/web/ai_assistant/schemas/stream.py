import json
from collections.abc import Mapping
from typing import Any, ClassVar
from uuid import UUID

from drf_pydantic import DrfPydanticSerializer
from pydantic import Field, ValidationError
from rest_framework import serializers

from services.web.ai_assistant.constants import PlatformStreamEvent, StreamArchiveStatus
from services.web.ai_assistant.exceptions import InvalidStreamEvent
from services.web.ai_assistant.schemas.message import MessageSchema


class UIStreamEventDrfSerializer(DrfPydanticSerializer):
    """``data`` 是协议无关的任意 JSON，无法由 drf_pydantic 自动推导，需显式声明。"""

    event = serializers.ChoiceField(
        choices=PlatformStreamEvent.choices,
        allow_null=True,
        help_text="平台事件名称；普通业务事件为空",
    )
    stream_id = serializers.CharField(allow_null=True, help_text="Redis 增量游标；实时写入失败时为空")
    data = serializers.JSONField(allow_null=True, help_text="平台不解析的业务或平台数据")


class AttachmentStreamConfig(MessageSchema):
    """当前执行的内部流配置；只在平台内部流转，禁止对外公开。"""

    # 手动重试会更换 Attachment.task_id 但暂时保留旧配置，SSE 用此字段
    # 识别旧流已不属于当前任务，避免新 Worker 排队期间重放旧事件。
    task_id: str = Field(min_length=1)
    execution_id: UUID
    redis_key: str = Field(min_length=1)
    archive_status: StreamArchiveStatus = StreamArchiveStatus.COMPLETE


class UIStreamEvent(MessageSchema):
    """Redis、MySQL 与 SSE 共用的协议无关 UI 事件记录。"""

    drf_serializer: ClassVar[type[DrfPydanticSerializer]] = UIStreamEventDrfSerializer

    event: PlatformStreamEvent | None = None
    stream_id: str | None = None
    data: Any = None
    # 归档重试身份独立于 Redis 游标；只由存储序列化器写入，不进入公开快照或实时协议。
    archive_id: UUID | None = Field(default=None, exclude=True, repr=False)


class AttachmentStreamSnapshot(MessageSchema):
    """当前执行已持久化的事件快照，用于首次进入或 reset 后恢复。"""

    events: list[UIStreamEvent]
    execution_id: UUID | None = None
    latest_stream_id: str | None = None
    archive_status: StreamArchiveStatus = StreamArchiveStatus.COMPLETE


def serialize_stream_event(event: UIStreamEvent, *, include_stream_id: bool = True) -> bytes:
    """验证事件可被 JSON 编码并返回 UTF-8 紧凑字节。

    Redis entry 不需要重复保存 Redis 自身生成的 ID，因此 ``include_stream_id=False``
    时只输出 ``event/data``；``stream_id`` 由 XADD 返回后再补充到事件对象。
    """

    payload: dict[str, Any] = {"event": event.event}
    if include_stream_id:
        payload["stream_id"] = event.stream_id
    payload["data"] = event.data
    return _serialize_json(payload, error_data={"event": event.event})


def dump_stream_archive_event(event: UIStreamEvent) -> dict[str, Any]:
    """持久化内部归档身份，公开 model_dump 仍保持原事件字段。"""

    payload = event.model_dump(mode="json")
    if event.archive_id is not None:
        payload["archive_id"] = str(event.archive_id)
    return payload


def serialize_stream_archive_event(event: UIStreamEvent, *, include_stream_id: bool = True) -> bytes:
    """按归档实际记录计量缓冲字节，实时编码继续使用原有公开协议。"""

    if not include_stream_id:
        return serialize_stream_event(event, include_stream_id=False)
    return _serialize_json(dump_stream_archive_event(event), error_data={"event": event.event})


def _serialize_json(value: Any, *, error_data: dict[str, Any]) -> bytes:
    """统一事件记录与 SSE data 的严格 JSON 编码。"""

    try:
        # allow_nan=False 让 NaN/Infinity 这类非法 JSON 数值在写入前就暴露。
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError):
        # 事件 data 可能包含业务私有内容，异常链和消息都不允许携带原值。
        raise InvalidStreamEvent(data=error_data) from None


def parse_stream_config(value: Mapping[str, Any] | None) -> AttachmentStreamConfig | None:
    """空字典返回 None，非法内部配置抛 InvalidStreamEvent。"""

    if value is None:
        return None
    # 非映射结构说明字段被写坏；内部配置不做兼容，直接暴露为平台异常。
    if not isinstance(value, Mapping):
        raise InvalidStreamEvent(data={"field_name": "stream_config"})
    if not value:
        return None
    try:
        return AttachmentStreamConfig.model_validate(dict(value))
    except ValidationError:
        raise InvalidStreamEvent(data={"field_name": "stream_config"}) from None


def parse_stream_archive(value: Any) -> tuple[list[UIStreamEvent], StreamArchiveStatus]:
    """逐项保留可解析事件；遇到脏数据返回有效部分并把状态提升为 DEGRADED。"""

    if not value:
        return [], StreamArchiveStatus.COMPLETE
    if not isinstance(value, list):
        return [], StreamArchiveStatus.DEGRADED

    events: list[UIStreamEvent] = []
    status = StreamArchiveStatus.COMPLETE
    for item in value:
        if not isinstance(item, Mapping):
            status = StreamArchiveStatus.DEGRADED
            continue
        try:
            event = UIStreamEvent.model_validate(dict(item))
            serialize_stream_event(event)
            events.append(event)
        except (ValidationError, InvalidStreamEvent):
            status = StreamArchiveStatus.DEGRADED
    return events, status

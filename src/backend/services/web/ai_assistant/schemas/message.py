from collections.abc import Mapping
from typing import Any, TypeAlias, TypeVar

from drf_pydantic import BaseModel
from pydantic import ConfigDict, ValidationError

from services.web.ai_assistant.exceptions import MessageSnapshotValidationError


class MessageSchema(BaseModel):
    """消息 JSON 快照基类：拒绝未知字段，解析后不可变。"""

    model_config = ConfigDict(extra="forbid", frozen=True)


SchemaT = TypeVar("SchemaT", bound=MessageSchema)
SnapshotInput: TypeAlias = Mapping[str, Any] | MessageSchema


def parse_snapshot(
    schema_type: type[SchemaT],
    data: SnapshotInput,
    *,
    field_name: str,
) -> SchemaT:
    """使用具体 Schema 统一解析请求和数据库中的消息快照。"""

    if isinstance(data, schema_type):
        return data
    raw_data = data.model_dump(mode="python") if isinstance(data, MessageSchema) else data
    try:
        return schema_type.model_validate(raw_data)
    except ValidationError as error:
        errors = [
            {"type": item["type"], "loc": list(item["loc"]), "msg": item["msg"]}
            for item in error.errors(include_input=False, include_url=False)
        ]
        # Pydantic 原始异常包含 input_value，禁止通过异常链进入任务日志。
        raise MessageSnapshotValidationError(data={"field_name": field_name, "errors": errors}) from None


def dump_snapshot(
    schema_type: type[SchemaT],
    data: SnapshotInput,
    *,
    field_name: str,
) -> dict[str, Any]:
    """校验消息快照并转换为 JSONField 可直接保存的标准数据。"""

    return parse_snapshot(schema_type, data, field_name=field_name).model_dump(mode="json")

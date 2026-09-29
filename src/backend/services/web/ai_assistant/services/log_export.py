"""日志检索消息的预览导出与全量导出编排。

平台文档 §13：预览导出直接读取快照同步生成 Excel（不建任务）；
全量导出复用既有 LogExportTask 链路（来源字段追踪）。
"""

import logging

from pydantic import ValidationError

from services.web.ai_assistant.constants import ExecutionStatus, MessageType
from services.web.ai_assistant.exceptions import (
    InvalidMessageSnapshot,
    InvalidMessageState,
    LogExportFailed,
    LogExportPermissionDenied,
)
from services.web.ai_assistant.models import Message
from services.web.ai_assistant.schemas.audit_search import (
    LogSearchContextSchema,
    LogSearchInputSchema,
    LogSearchOutputSchema,
)
from services.web.ai_assistant.services.message import MessageService
from services.web.query.ai_assistant.constants import SNAPSHOT_DEFAULT_COLUMNS
from services.web.query.ai_assistant.exceptions import (
    AIAssistantError as QueryAIAssistantError,
)
from services.web.query.ai_assistant.exceptions import (
    AIPermissionDeniedError as QueryAIPermissionDeniedError,
)
from services.web.query.ai_assistant.schemas import LogSearchOutput
from services.web.query.ai_assistant.services.export import (
    FullExportService,
    PreviewExportFile,
    PreviewExportService,
)
from services.web.query.constants import LogExportFieldScope

logger = logging.getLogger(__name__)


class MessageExportService:
    """在当前用户边界内编排日志检索消息的两种导出。"""

    def __init__(self, *, user: str):
        self.user = user
        self.message_service = MessageService(user=user)

    def preview_export(self, *, message_uid: str, export_config: dict = None) -> PreviewExportFile:
        """同步导出快照样例（≤100 条）；只校验所有权，不重查日志。"""

        message = self._get_success_log_search(message_uid=message_uid)
        try:
            snapshot = LogSearchOutputSchema.model_validate(message.output_data)
        except ValidationError as error:
            raise InvalidMessageSnapshot() from error
        query_output = LogSearchOutput(
            total=snapshot.total,
            columns=snapshot.columns,
            samples=snapshot.samples,
            query_summary=snapshot.query_summary,
        )
        try:
            return PreviewExportService.export(output=query_output, export_config=export_config or {})
        except QueryAIAssistantError as error:
            logger.warning(
                "[MessageExportService] preview export failed, message_id=%s, error=%s",
                message.id,
                error,
            )
            raise LogExportFailed() from error

    def create_full_export(self, *, message_uid: str, export_config: dict) -> dict:
        """从消息快照重建查询条件并创建全量导出任务（数据范围前端不可覆盖）。"""

        message = self._get_success_log_search(message_uid=message_uid)
        try:
            condition = LogSearchInputSchema.model_validate(message.input_data).condition
        except ValidationError as error:
            raise InvalidMessageSnapshot() from error
        namespace = str((message.context_data or {}).get("namespace") or "")
        export_config = dict(export_config or {})
        # AI 助手「标准字段」scope：翻译为 SPECIFIED + 快照默认展示列（与预览导出同构，
        # display_name 沿用产品文案），常规导出链路（白名单校验/ExportConfig）仅见 SPECIFIED，
        # 原检索页 standard（全量标准字段集）语义不变
        if export_config.get("field_scope") == LogExportFieldScope.AI_STANDARD.value:
            export_config["field_scope"] = LogExportFieldScope.SPECIFIED.value
            export_config["fields"] = [
                {"raw_name": raw_name, "display_name": display_name, "keys": []}
                for raw_name, display_name in SNAPSHOT_DEFAULT_COLUMNS
            ]
        # 扩展字段平铺开启且调用方未显式给子键清单时，从父消息的系统选择快照自动聚合
        # （前端只需传 flatten_extension 开关，无需感知子键清单）
        if export_config.get("flatten_extension") and not export_config.get("extension_keys"):
            extension_keys = self._extract_extension_keys(message)
            if extension_keys:
                export_config["extension_keys"] = extension_keys
                logger.info(
                    "[MessageExportService] auto inject extension_keys for flatten export, " "message_id=%s, keys=%s",
                    message.id,
                    extension_keys,
                )
        try:
            task = FullExportService.create_task(
                condition=condition,
                namespace=namespace,
                export_config=export_config,
                task_name=FullExportService.build_task_name(str(message.uid)),
                username=self.user,
            )
        except QueryAIPermissionDeniedError as error:
            raise LogExportPermissionDenied() from error
        except QueryAIAssistantError as error:
            logger.warning(
                "[MessageExportService] full export failed, message_id=%s, error=%s",
                message.id,
                error,
            )
            raise LogExportFailed() from error
        # resource 调用经 bk_resource 框架序列化后返回 ReturnDict（dict 子类），按键访问而非属性访问
        return {"export_task_id": task["id"], "status": task["status"]}

    @staticmethod
    def _extract_extension_keys(message: Message) -> list:
        """从 LOG_SEARCH 自身上下文聚合 extend_data 子键，兼容旧消息父快照。

        新消息在创建时固化 ``extension_fields``，导出不依赖同级系统选择是否完成。
        旧消息没有该键时，再按历史父消息结构回退。
        """

        context_data = message.context_data if isinstance(message.context_data, dict) else {}
        if "extension_fields" in context_data:
            try:
                fields = LogSearchContextSchema.model_validate(context_data).extension_fields
            except ValidationError as error:
                raise InvalidMessageSnapshot() from error
        else:
            parent = message.parent_message
            if parent is None:
                return []
            if parent.message_type == MessageType.USER_INTENT:
                selection = (
                    Message.objects.filter(
                        conversation=parent.conversation,
                        created_by=parent.created_by,
                        message_type=MessageType.SYSTEM_SELECTION,
                        status=ExecutionStatus.SUCCESS,
                        id__lte=message.id,
                    )
                    .order_by("-id")
                    .first()
                )
                systems = ((selection.output_data if selection else None) or {}).get("systems") or []
            else:
                systems = (parent.output_data or {}).get("systems") or []
            fields = [field for system in systems for field in (system or {}).get("extension_fields") or []]
        keys: list = []
        seen: set = set()
        for field in fields:
            payload = field.model_dump(mode="json") if hasattr(field, "model_dump") else field
            if not isinstance(payload, dict) or payload.get("raw_name") != "extend_data":
                continue
            # 一期下钻协议限单层，仅取第一层子键
            field_keys = payload.get("keys") or []
            key = field_keys[0] if field_keys else ""
            if isinstance(key, str) and key and key not in seen:
                seen.add(key)
                keys.append(key)
        return keys

    def _get_success_log_search(self, *, message_uid: str) -> Message:
        """复用平台统一用户边界获取消息，再校验类型与状态。"""

        message = self.message_service.get(message_uid=message_uid)
        if message.message_type != MessageType.LOG_SEARCH or message.status != ExecutionStatus.SUCCESS:
            raise InvalidMessageState(message="仅成功的日志检索消息支持导出")
        return message

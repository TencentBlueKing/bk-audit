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
    LogSearchInputSchema,
    LogSearchOutputSchema,
)
from services.web.ai_assistant.services.message import MessageService
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
        # 扩展字段平铺开启且调用方未显式给子键清单时，从父消息的系统选择快照自动聚合
        # （前端只需传 flatten_extension 开关，无需感知子键清单）
        if export_config.get("flatten_extension") and not export_config.get("extension_keys"):
            extension_keys = self._extract_extension_keys(message)
            if extension_keys:
                export_config["extension_keys"] = extension_keys
                logger.info(
                    "[MessageExportService] auto inject extension_keys for flatten export, "
                    "message_id=%s, keys=%s",
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
        """从父消息聚合 extend_data 单层子键清单（保序去重）。

        来源二选一：自然语言父消息的 context_data.system_selection.systems；
        系统选择父消息的 output_data.systems。两者均为
        systems[].extension_fields[]（SelectionFieldMeta dict 形态，raw_name+keys）。
        """

        parent = message.parent_message
        if parent is None:
            return []
        if parent.message_type == MessageType.NATURAL_LANGUAGE_SEARCH:
            systems = ((parent.context_data or {}).get("system_selection") or {}).get("systems") or []
        else:
            systems = (parent.output_data or {}).get("systems") or []
        keys: list = []
        seen: set = set()
        for system in systems:
            for field in (system or {}).get("extension_fields") or []:
                if not isinstance(field, dict) or field.get("raw_name") != "extend_data":
                    continue
                # 一期下钻协议限单层，仅取第一层子键
                field_keys = field.get("keys") or []
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

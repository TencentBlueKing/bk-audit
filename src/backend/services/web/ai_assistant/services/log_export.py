"""日志检索消息的预览导出与全量导出编排。

平台文档 §13：预览导出直接读取快照同步生成 Excel（不建任务）；
全量导出复用既有 LogExportTask 链路（来源字段追踪）；
F4.5 全量导出同步直出：条数守卫内尝试 API 进程内直出，任何降级信号自动转异步链路。
"""

import logging
from typing import Union

from django.conf import settings
from pydantic import ValidationError

from core.exceptions import ValidationError as RequestValidationError
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
from services.web.query.ai_assistant.constants import (
    AI_ASSISTANT_EXPORT_SOURCE,
    SNAPSHOT_DEFAULT_COLUMNS,
    SYNC_EXPORT_FALLBACK,
)
from services.web.query.ai_assistant.exceptions import (
    AIAssistantError as QueryAIAssistantError,
)
from services.web.query.ai_assistant.exceptions import AIOutputInvalidError
from services.web.query.ai_assistant.exceptions import (
    AIPermissionDeniedError as QueryAIPermissionDeniedError,
)
from services.web.query.ai_assistant.exceptions import SyncExportFallback
from services.web.query.ai_assistant.schemas import LogSearchOutput
from services.web.query.ai_assistant.services.export import (
    FullExportService,
    PreviewExportFile,
    PreviewExportService,
    SyncExportRunner,
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
        return self._create_full_export_with_message(message=message, export_config=export_config)

    def export_or_fallback(self, *, message_uid: str, export_config: dict) -> Union[PreviewExportFile, dict]:
        """F4.5 全量导出统一入口：同步优先、超限自动降级异步。

        - 开关关闭 → 100% 现行为（异步任务，行为与历史一致）；
        - 快照 total 超过同步条数上限 → 直接异步（廉价准入，不占并发槽不查 Doris）；
        - 同步尝试中任何降级信号（SyncExportFallback）→ 原样落入既有异步链路；
        - 权限/白名单校验失败 → 与异步路径同样报错（校验失败不降级）。

        :return: PreviewExportFile = 同步直出文件；dict = 已创建的异步任务信息
        """

        if not settings.AI_EXPORT_SYNC_ENABLED:
            return self.create_full_export(message_uid=message_uid, export_config=export_config)
        message = self._get_success_log_search(message_uid=message_uid)
        # 快照 total 预判（廉价准入）：超限直接异步，不发起同步尝试
        try:
            snapshot_total = LogSearchOutputSchema.model_validate(message.output_data).total
        except ValidationError as error:
            raise InvalidMessageSnapshot() from error
        if snapshot_total > settings.AI_EXPORT_SYNC_MAX_COUNT:
            logger.info(
                "[MessageExportService] sync export skipped by snapshot total, message_id=%s, total=%s",
                message.id,
                snapshot_total,
            )
            return self._create_full_export_with_message(message=message, export_config=export_config)
        try:
            condition = LogSearchInputSchema.model_validate(message.input_data).condition
        except ValidationError as error:
            raise InvalidMessageSnapshot() from error
        namespace = str((message.context_data or {}).get("namespace") or "")
        runner = SyncExportRunner(
            condition=condition,
            namespace=namespace,
            export_config=self._build_export_config(message=message, export_config=export_config),
            username=self.user,
        )
        try:
            return runner.run()
        except SyncExportFallback:
            # 降级 = 正常分流：原样落入既有异步链路（export_config 传原始值，内部预处理幂等）；
            # export_type 标记供前端分支提示（非"失败"，是数据量分流的正常结果）
            result = self._create_full_export_with_message(message=message, export_config=export_config)
            result["export_type"] = SYNC_EXPORT_FALLBACK
            return result
        except QueryAIPermissionDeniedError as error:
            raise LogExportPermissionDenied() from error
        except AIOutputInvalidError as error:
            raise RequestValidationError("日志导出配置无效，请检查字段范围和列配置") from error

    def _create_full_export_with_message(self, *, message: Message, export_config: dict) -> dict:
        """持有 message 的全量异步导出（供 create_full_export 与同步降级两路复用）。"""

        try:
            condition = LogSearchInputSchema.model_validate(message.input_data).condition
        except ValidationError as error:
            raise InvalidMessageSnapshot() from error
        namespace = str((message.context_data or {}).get("namespace") or "")
        export_config = self._build_export_config(message=message, export_config=export_config)
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
        except AIOutputInvalidError as error:
            raise RequestValidationError("日志导出配置无效，请检查字段范围和列配置") from error
        except QueryAIAssistantError as error:
            logger.warning(
                "[MessageExportService] full export failed, message_id=%s, error=%s",
                message.id,
                error,
            )
            raise LogExportFailed() from error
        # resource 调用经 bk_resource 框架序列化后返回 ReturnDict（dict 子类），按键访问而非属性访问
        return {"export_task_id": task["id"], "status": task["status"]}

    def _build_export_config(self, *, message: Message, export_config: dict) -> dict:
        """export_config 预处理（同步直出与异步导出双路径同源）。"""

        export_config = dict(export_config or {})
        # 公开接口配置可省略，默认列与 AI 助手预览保持一致。
        export_config.setdefault("field_scope", LogExportFieldScope.AI_STANDARD.value)
        # AI 导出启用专属样式；后端标记来源，调用方不可覆盖。
        export_config["source"] = AI_ASSISTANT_EXPORT_SOURCE
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
        return export_config

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

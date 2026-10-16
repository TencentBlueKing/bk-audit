# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
Copyright (C) 2023 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the specific language governing
permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.

F4 导出服务（预览导出 / 全量导出 / 同步直出）

- 预览导出：数据源 = LOG_SEARCH 快照 samples（≤100 条，不重查），列与列头 = output_data.columns，
  复用导出三件套（ExportConfig → DataProcessor → XLSXExporter），与全量导出文件视觉同构。
  纯函数：不查库、不写库、不依赖请求上下文。
- 全量导出：数据范围（系统、时间、条件）从来源快照 condition 原样重建（前端不能覆盖），
  复用现有 CreateCollectorSearchExportTask 全链路（预检/上限/落库/Celery 派发）。
  仅同步 Web 请求上下文使用（任务 created_by 取自请求身份）。
- 同步直出（F4.5）：条件重建/权限/白名单与全量导出同源（FullExportService.prepare 共享前置段），
  在 API 进程内大分页拉取 Doris 并直接生成 XLSX 返回；deadline 守卫（软超时）+ 硬超时分级
  保证端到端 30 秒承诺——任何降级信号（SyncExportFallback）由编排层捕获后自动转既有异步链路。
"""

import io
import math
import time
from dataclasses import dataclass
from typing import Callable, List

import xlsxwriter
from bk_resource import resource
from blueapps.utils.logger import logger
from django.conf import settings
from django.core.files import File

from apps.meta.permissions import SearchLogPermission
from core.sql.constants import FieldType
from core.sync_concurrency import SyncExportSlotLease
from services.web.query.ai_assistant.constants import (
    AI_ASSISTANT_EXPORT_SOURCE,
    AI_EXPORT_TASK_NAME_TEMPLATE,
    SYNC_EXPORT_SLOT_KEY_PREFIX,
    SyncExportFallbackReason,
)
from services.web.query.ai_assistant.exceptions import (
    AIOutputInvalidError,
    AIPermissionDeniedError,
    SyncExportFallback,
)
from services.web.query.ai_assistant.schemas import (
    LogSearchOutput,
    ResultColumn,
    SearchCondition,
)
from services.web.query.constants import (
    DEFAULT_COLLECTOR_SORT_LIST,
    LOG_FIELD_KEY_JOIN_CHAR,
    FieldCategoryEnum,
    LogExportFieldScope,
)
from services.web.query.export.data_fetcher import DataFetcher
from services.web.query.export.data_processor import DataProcessor
from services.web.query.export.file_exporter import XLSXExporter
from services.web.query.export.model import ExportConfig
from services.web.query.models import LogExportTask
from services.web.query.utils.field import LOG_SEARCH_ALL_FIELDS
from services.web.query.utils.search_config import QueryConditionOperator

# 导出字段白名单（raw_name 集合，与导出链路 LogExportField 序列化器同源）
LOG_EXPORT_FIELD_WHITELIST = {field.field_name for field in LOG_SEARCH_ALL_FIELDS}


@dataclass
class PreviewExportFile:
    """预览导出产物（内存字节 + 文件名，调用方直接写 HttpResponse）"""

    content: bytes
    file_name: str


class PreviewXLSXExporter(XLSXExporter):
    """
    XLSXExporter 的 BytesIO 变体。

    规避基类 NamedTemporaryFile(delete=True) 在 Windows 上的句柄冲突
    （生产 Linux 两者行为一致；BytesIO 同为 xlsxwriter 官方推荐方式，无磁盘 IO，
    与 core.exporter.BaseXlsxFileExporter 的跨平台修复同一思路）。
    """

    def __init__(self, config: ExportConfig, max_row: int = 65536):
        # 跳过 FileExporter.__init__ 的 NamedTemporaryFile，其余初始化与 XLSXExporter 保持一致
        self.config = config
        self.tmp_file = io.BytesIO()
        self.workbook = xlsxwriter.Workbook(self.tmp_file, {"constant_memory": True})
        self.title_fmt = self.workbook.add_format(self.display_format)
        self.key_fmt = self.workbook.add_format(self.full_key_format)
        self.data_fmt = self.workbook.add_format(self.data_format)
        self.category_header_fmts = {
            category: self.workbook.add_format({**self.category_format, "bg_color": category.color})
            for category in FieldCategoryEnum.get_orders()
        }
        self.max_row = max_row
        self._init_worksheet()

    def save(self) -> File:
        self.workbook.close()
        self.tmp_file.seek(0)
        return File(self.tmp_file)

    def close(self):
        self.tmp_file.close()


class PreviewExportService:
    """GET preview-export：快照 samples → XLSX"""

    @classmethod
    def export(cls, output: LogSearchOutput, export_config: dict = None) -> PreviewExportFile:
        """
        :param output: LOG_SEARCH 消息 output_data 解析结果
        :param export_config: 导出配置（field_scope/fields/flatten_extension/extension_keys）；
            flatten_extension=True 时把 extend_data 内子键平铺为单独列（聚合自 samples）
        零数据快照沿用正常流程，只输出分类和字段标题。
        """
        config = export_config or {}
        if config.get("flatten_extension"):
            return cls._export_with_flatten_extension(output)

        # ① 内存态 LogExportTask 作 ExportConfig 载体（不 save —— 预览导出无任务实体）
        #    samples 字典键 = 列 full_key，故导出字段按 full_key 直取（keys 置空不再二次下钻）
        export_fields = [
            {"raw_name": column.full_key, "display_name": column.display_name, "keys": []} for column in output.columns
        ]
        task_stub = LogExportTask(
            export_config={
                "field_scope": LogExportFieldScope.SPECIFIED.value,
                "fields": export_fields,
                # AI 导出来源标记：单行表头 + 字段保序 + 列宽自适应（检索页导出不带）
                "source": AI_ASSISTANT_EXPORT_SOURCE,
            }
        )
        config = ExportConfig(task=task_stub)

        # ② 复用导出三件套：ExportConfig → DataProcessor → XLSXExporter（BytesIO 变体）
        exporter = PreviewXLSXExporter(config)
        try:
            exporter.write(DataProcessor(config).batch_format_data(output.samples))
            file = exporter.save()
            content = file.read()
            file_name = exporter.file_name
        finally:
            exporter.close()
        return PreviewExportFile(content=content, file_name=file_name)

    @classmethod
    def _export_with_flatten_extension(cls, output: LogSearchOutput) -> PreviewExportFile:
        """扩展字段平铺：聚合所有 samples 的 extend_data 子键并集，把 extend_data 单列替换为每个子键单独一列。"""

        # ① 聚合所有 samples 的 extend_data 子键并集（保序去重）
        keys: List[str] = []
        seen: set = set()
        for sample in output.samples:
            ext = sample.get("extend_data")
            if isinstance(ext, dict):
                for key in ext.keys():
                    if isinstance(key, str) and key and key not in seen:
                        seen.add(key)
                        keys.append(key)

        # 无可平铺子键时沿用正常导出，零数据快照仍保留字段标题。
        if not keys:
            return cls.export(output)

        # 在原位置替换拓展数据列，保持与前端展示一致的列顺序。
        flat_columns: List[ResultColumn] = []
        for column in output.columns:
            if column.raw_name == "extend_data" and not column.keys:
                flat_columns.extend(ResultColumn(raw_name="extend_data", keys=[key], display_name=key) for key in keys)
            else:
                flat_columns.append(column)

        # ③ 内存态 LogExportTask 走 SPECIFIED 形态；携带 flatten_extension 标记——
        #    既是平铺语义自洽，也是 Excel 分组表头渲染"扩展字段"的开关（检索页导出不传）
        export_fields = [
            {"raw_name": column.full_key, "display_name": column.display_name, "keys": []} for column in flat_columns
        ]
        task_stub = LogExportTask(
            export_config={
                "field_scope": LogExportFieldScope.SPECIFIED.value,
                "fields": export_fields,
                "flatten_extension": True,
                # AI 导出来源标记：单行表头 + 字段保序 + 列宽自适应（检索页导出不带）
                "source": AI_ASSISTANT_EXPORT_SOURCE,
            }
        )
        config = ExportConfig(task=task_stub)

        # ④ 同步展平 samples：把 extend_data dict 拆为 extend_data/{key} 顶层键（与列 full_key 对齐）
        flat_samples: List[dict] = []
        for sample in output.samples:
            flat = {sample_key: value for sample_key, value in sample.items() if sample_key != "extend_data"}
            ext = sample.get("extend_data")
            if isinstance(ext, dict):
                for sub_key, sub_value in ext.items():
                    flat[LOG_FIELD_KEY_JOIN_CHAR.join(["extend_data", sub_key])] = sub_value
            flat_samples.append(flat)

        exporter = PreviewXLSXExporter(config)
        try:
            exporter.write(DataProcessor(config).batch_format_data(flat_samples))
            file = exporter.save()
            content = file.read()
            file_name = exporter.file_name
        finally:
            exporter.close()
        return PreviewExportFile(content=content, file_name=file_name)


class FullExportService:
    """POST full-export：快照 condition 原样重建 query_params → LogExportTask"""

    @classmethod
    def prepare(cls, *, condition: SearchCondition, namespace: str, export_config: dict, username: str) -> dict:
        """同步直出与异步任务共享的前置段：权限复检 + export_config 校验 + query_params 组装。

        数据范围（系统、时间、条件）由快照 condition 重建，调用方不能覆盖；
        同步直出与异步导出必须经过同一份校验，防止同步路径权限语义弱化。
        """
        # ① 当前日志权限复检
        if not SearchLogPermission.has_system_search_permission(condition.scope_id, username):
            raise AIPermissionDeniedError(extra={"system_id": condition.scope_id, "username": username})
        # ② export_config 字段白名单校验（协议 §6.2）
        cls._validate_export_config(export_config)
        # ③ query_params 组装：condition 原样 + scope 精确注入 system_id 条件 + 顶层时间字段
        #    （LogExportReqSerializer.run_validation 会回填 query_params.namespace；
        #      导出运行时 CollectorSearchAllReqSerializer 按顶层 start/end 注入时间条件）
        return {
            "namespace": namespace,
            "start_time": condition.start_time,
            "end_time": condition.end_time,
            "conditions": [
                {
                    "field": {"raw_name": "system_id", "field_type": FieldType.STRING.value, "keys": []},
                    "operator": QueryConditionOperator.INCLUDE.value,
                    "filters": [condition.scope_id],
                }
            ]
            + [cond.model_dump() for cond in condition.conditions],
            "page": 1,
            "page_size": 20,
            "sort_list": DEFAULT_COLLECTOR_SORT_LIST,
            "bind_system_info": True,
        }

    @classmethod
    def create_task(
        cls,
        *,
        condition: SearchCondition,
        namespace: str,
        export_config: dict,
        task_name: str,
        username: str,
    ) -> dict:
        """
        :param condition: 来源 LOG_SEARCH 消息的 input_data.condition（快照条件）
        :param namespace: 命名空间
        :param export_config: 前端请求的导出配置（field_scope + fields[]），仅控制字段范围
        :param task_name: 任务名（D4 默认由 build_task_name 生成）
        :param username: 操作人（显式传入）
        :return: 导出任务创建响应 dict（bk_resource 序列化后的 LogExportTask 字段，含 id/status；Celery 已派发）
        :raises AIPermissionDeniedError: 当前无 scope 系统检索权限（权限可能已变更，创建时复检）
        :raises AIOutputInvalidError: export_config 字段越权/形态非法
        """
        # 共享前置段（与同步直出同源）：权限复检 + 白名单校验 + query_params 组装
        query_params = cls.prepare(
            condition=condition,
            namespace=namespace,
            export_config=export_config,
            username=username,
        )
        # ④ 复用现有创建链路：get_total 预检 → 上限校验 → ExportFieldLog → 落库 → Celery 派发
        return resource.query.create_collector_search_export_task(
            namespace=namespace,
            name=task_name,
            query_params=query_params,
            export_config=export_config,
            search_params_url="",
        )

    @classmethod
    def build_task_name(cls, message_uid: str) -> str:
        """D4 默认实现：后端生成任务名（协议请求体无 name 字段）"""
        return str(AI_EXPORT_TASK_NAME_TEMPLATE) % message_uid[:8]

    @classmethod
    def _validate_export_config(cls, export_config: dict) -> None:
        field_scope = (export_config or {}).get("field_scope")
        if field_scope not in LogExportFieldScope.values:
            raise AIOutputInvalidError(extra={"export_config": export_config, "reason": "invalid field_scope"})
        if field_scope == LogExportFieldScope.SPECIFIED.value:
            fields: List[dict] = export_config.get("fields") or []
            if not fields:
                raise AIOutputInvalidError(
                    extra={"export_config": export_config, "reason": "fields required when specified"}
                )
            invalid_fields = [
                item.get("raw_name") for item in fields if item.get("raw_name") not in LOG_EXPORT_FIELD_WHITELIST
            ]
            if invalid_fields:
                raise AIOutputInvalidError(
                    extra={"export_config": export_config, "reason": f"fields not in whitelist: {invalid_fields}"}
                )
        # 扩展字段平铺开关：布尔（缺省 false）
        flatten = export_config.get("flatten_extension")
        if flatten is not None and not isinstance(flatten, bool):
            raise AIOutputInvalidError(
                extra={"export_config": export_config, "reason": "flatten_extension must be bool"}
            )
        # 扩展字段平铺子键清单（仅在调用方未传 flatten_extension 时由 PreviewExportService 自动聚合；
        # 全量导出场景无 samples 上下文，需由调用方预先传 extension_keys 触发子键列生成）
        keys = export_config.get("extension_keys")
        if keys is not None:
            if not isinstance(keys, list) or not all(isinstance(k, str) and k for k in keys):
                raise AIOutputInvalidError(
                    extra={"export_config": export_config, "reason": "extension_keys must be list[str]"}
                )


def _report_sync_export_metric(*, status: str, duration_ms: int, reason: str = "", rows: int = 0) -> None:
    """同步直出指标上报（BKM 自定义指标）：上报失败不影响导出主流程。

    duration 由注入 clock 计算后传入（而非 perf_counter 内部自算），保证单测假时钟可测。
    """
    try:
        from core.monitor import Metric

        Metric(
            metrics={"call_count": 1, "duration_ms": max(0, int(duration_ms)), "rows": rows},
            dimension={
                "span_name": "ai_assistant_export_sync.run",
                "status": status,
                "error_type": reason,
                "service": "query",
                "operation": "sync_export",
            },
        ).async_report()
    except Exception as error:  # pylint: disable=broad-except
        logger.warning(
            "[SyncExportRunner] report metric failed, status=%s, reason=%s, error=%s",
            status,
            reason,
            error,
        )


class SyncExportRunner:
    """F4.5 全量同步导出执行器：API 进程内直出，deadline 守卫是第一公民。

    与既有链路的关系：
    - 条件重建/权限/白名单走 FullExportService.prepare（与异步导出同源）；
    - 数据拉取复用 DataFetcher 的类方法（大 page_size 自行分页），不落 LogExportTask——
      任务列表语义保持"可二次下载的异步产物"，同步直出只留审计与指标；
    - 文件导出复用 PreviewXLSXExporter（BytesIO 变体），AI 单行表头/列宽样式天然同构。

    守卫分级（对齐端到端 30 秒承诺，详见设计文档 §3.3/§3.3.1）：
    - 每批拉取**开始前**检查：绝对预算（deadline - 收尾预留）与上批耗时外推（×1.5），
      超预算立即中止降级——宁可保守少拉一批，不可乐观超时一次；
    - 循环自然结束 = 数据全部拉完，批中波动导致的超软超时在此自然放行（只差收尾时
      中止是双输：用户白等同步时间还要重走异步全流程），收尾仅受硬超时约束；
    - 收尾前检查硬超时（hard_limit，绝对天花板）：超时果断降级，保证请求永不挂死。
    """

    # XLSX 收尾（workbook.close + BytesIO read）的预算预留（秒）
    FINALIZE_RESERVE_SECONDS = 2

    def __init__(self, *, condition: SearchCondition, namespace: str, export_config: dict, username: str):
        self.condition = condition
        self.namespace = namespace
        self.export_config = export_config or {}
        self.username = username

    def run(self, *, clock: Callable[[], float] = time.monotonic) -> PreviewExportFile:
        """执行同步导出；任何降级信号以 SyncExportFallback 抛出（编排层捕获转异步）。

        :param clock: 单调时钟函数，可注入假时钟实现零等待单测（对齐巡检模块 clock/sleep_fn 惯例）
        :raises SyncExportFallback: 并发槽满/条数超限/count 慢/软超时/硬超时
        """
        started_at = clock()
        # 共享前置段：权限复检 + 白名单校验 + query_params 组装（与异步导出同源）
        query_params = FullExportService.prepare(
            condition=self.condition,
            namespace=self.namespace,
            export_config=self.export_config,
            username=self.username,
        )
        # 全局并发槽：满槽即降级，不排队（等待本身就是超时源）
        lease = SyncExportSlotLease(
            key_prefix=SYNC_EXPORT_SLOT_KEY_PREFIX,
            max_concurrency=settings.AI_EXPORT_SYNC_CONCURRENCY,
            lease_seconds=settings.AI_EXPORT_SYNC_HARD_LIMIT_SECONDS + 5,
        )
        if lease.acquire() is None:
            self._fallback(started_at=started_at, clock=clock, reason=SyncExportFallbackReason.CONCURRENCY)
        try:
            return self._export(query_params=query_params, started_at=started_at, clock=clock)
        finally:
            lease.release()

    def _export(self, *, query_params: dict, started_at: float, clock: Callable[[], float]) -> PreviewExportFile:
        deadline = settings.AI_EXPORT_SYNC_DEADLINE_SECONDS
        hard_limit = settings.AI_EXPORT_SYNC_HARD_LIMIT_SECONDS
        page_size = settings.AI_EXPORT_SYNC_PAGE_SIZE

        # ① count 复检：以导出时点总数为准（快照 total 之后数据可能持续写入）
        count_started = clock()
        total = DataFetcher.get_total(query_params)
        count_cost = clock() - count_started
        if total > settings.AI_EXPORT_SYNC_MAX_COUNT:
            self._fallback(
                started_at=started_at,
                clock=clock,
                reason=SyncExportFallbackReason.TOTAL_EXCEED,
                extra={"total": total},
            )
        if count_cost > settings.AI_EXPORT_SYNC_COUNT_MAX_SECONDS:
            self._fallback(
                started_at=started_at,
                clock=clock,
                reason=SyncExportFallbackReason.COUNT_SLOW,
                extra={"count_cost": count_cost},
            )
        # ② 首批行均成本外推：count 正常但数据量超预算，拉取前拦截（第二道保险）
        estimated_seconds = total * settings.AI_EXPORT_SYNC_ROW_COST_BUDGET_MS / 1000
        if estimated_seconds > deadline:
            self._fallback(
                started_at=started_at,
                clock=clock,
                reason=SyncExportFallbackReason.DEADLINE,
                extra={"total": total, "estimated_seconds": estimated_seconds},
            )

        # ③ 内存态任务桩（同预览导出模式，不落库）：仅作 ExportConfig 载体
        task_stub = LogExportTask(
            namespace=self.namespace,
            query_params=query_params,
            export_config=self.export_config,
            total=total,
        )
        config = ExportConfig(task=task_stub)
        exporter = PreviewXLSXExporter(config)
        processor = DataProcessor(config=config)
        total_batches = math.ceil(total / page_size) if total > 0 else 0
        last_batch_cost = None
        rows_written = 0
        try:
            # ④ 分批拉取 + 写入；守卫在每批开始前（批一旦发起无法中止）
            for page in range(1, total_batches + 1):
                elapsed = clock() - started_at
                if elapsed > deadline - self.FINALIZE_RESERVE_SECONDS:
                    self._fallback(
                        started_at=started_at,
                        clock=clock,
                        reason=SyncExportFallbackReason.DEADLINE,
                        extra={"page": page, "elapsed": elapsed, "rows_written": rows_written},
                    )
                if last_batch_cost is not None and elapsed + last_batch_cost * 1.5 > deadline:
                    self._fallback(
                        started_at=started_at,
                        clock=clock,
                        reason=SyncExportFallbackReason.DEADLINE,
                        extra={"page": page, "elapsed": elapsed, "rows_written": rows_written},
                    )
                batch_started = clock()
                logs = DataFetcher.fetch_patch_logs(query_params, page, page_size)
                formatted = processor.batch_format_data(logs)
                exporter.write(formatted)
                rows_written += len(formatted)
                last_batch_cost = clock() - batch_started
            # 循环自然结束 = 数据全部拉完（批中波动的最后一批在此放行）；
            # 收尾硬上界：绝对天花板，超时果断降级
            if clock() - started_at > hard_limit:
                self._fallback(
                    started_at=started_at,
                    clock=clock,
                    reason=SyncExportFallbackReason.HARD_LIMIT,
                    extra={"rows_written": rows_written},
                )
            file = exporter.save()
            content = file.read()
            file_name = exporter.file_name
            duration_ms = (clock() - started_at) * 1000
            logger.info(
                "[SyncExportRunner] sync export success, total=%d, rows=%d, duration_ms=%d",
                total,
                rows_written,
                duration_ms,
            )
            _report_sync_export_metric(status="success", duration_ms=duration_ms, rows=rows_written)
            return PreviewExportFile(content=content, file_name=file_name)
        finally:
            exporter.close()

    def _fallback(
        self,
        *,
        started_at: float,
        clock: Callable[[], float],
        reason: str,
        extra: dict = None,
    ) -> None:
        """记录降级原因并抛出中止信号（编排层捕获后转既有异步链路）。"""
        duration_ms = (clock() - started_at) * 1000
        logger.warning(
            "[SyncExportRunner] sync export fallback, reason=%s, duration_ms=%d, extra=%s",
            reason,
            duration_ms,
            extra or {},
        )
        _report_sync_export_metric(status="fallback", duration_ms=duration_ms, reason=reason)
        raise SyncExportFallback(reason)

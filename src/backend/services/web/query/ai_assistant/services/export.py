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

F4 导出服务（预览导出 / 全量导出）

- 预览导出：数据源 = LOG_SEARCH 快照 samples（≤100 条，不重查），列与列头 = output_data.columns，
  复用导出三件套（ExportConfig → DataProcessor → XLSXExporter），与全量导出文件视觉同构。
  纯函数：不查库、不写库、不依赖请求上下文。
- 全量导出：数据范围（系统、时间、条件）从来源快照 condition 原样重建（前端不能覆盖），
  复用现有 CreateCollectorSearchExportTask 全链路（预检/上限/落库/Celery 派发）。
  仅同步 Web 请求上下文使用（任务 created_by 取自请求身份）。
"""

import io
from dataclasses import dataclass
from typing import List

import xlsxwriter
from bk_resource import resource
from django.core.files import File

from apps.meta.permissions import SearchLogPermission
from core.sql.constants import FieldType
from services.web.query.ai_assistant.constants import AI_EXPORT_TASK_NAME_TEMPLATE
from services.web.query.ai_assistant.exceptions import (
    AIAssistantError,
    AIOutputInvalidError,
    AIPermissionDeniedError,
)
from services.web.query.ai_assistant.schemas import LogSearchOutput, ResultColumn, SearchCondition
from services.web.query.constants import (
    DEFAULT_COLLECTOR_SORT_LIST,
    FieldCategoryEnum,
    LOG_FIELD_KEY_JOIN_CHAR,
    LogExportFieldScope,
)
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
        :raises AIAssistantError: 快照无样例数据
        """
        if not output.samples:
            raise AIAssistantError(message="快照无样例数据，无法导出", error_code="TASK_EXECUTION_FAILED")

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

        # ② 构造展平后的列：移除 extend_data 单列；为每个子键添加 ResultColumn
        flat_columns: List[ResultColumn] = [
            column
            for column in output.columns
            if not (column.raw_name == "extend_data" and not column.keys)
        ]
        for key in keys:
            flat_columns.append(ResultColumn(raw_name="extend_data", keys=[key], display_name=key))

        # ③ 内存态 LogExportTask 走 SPECIFIED 形态
        export_fields = [
            {"raw_name": column.full_key, "display_name": column.display_name, "keys": []}
            for column in flat_columns
        ]
        task_stub = LogExportTask(
            export_config={
                "field_scope": LogExportFieldScope.SPECIFIED.value,
                "fields": export_fields,
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
        # ① 当前日志权限复检
        if not SearchLogPermission.has_system_search_permission(condition.scope_id, username):
            raise AIPermissionDeniedError(extra={"system_id": condition.scope_id, "username": username})
        # ② export_config 字段白名单校验（协议 §6.2）
        cls._validate_export_config(export_config)
        # ③ query_params 组装：condition 原样 + scope 精确注入 system_id 条件 + 顶层时间字段
        #    （LogExportReqSerializer.run_validation 会回填 query_params.namespace；
        #      导出运行时 CollectorSearchAllReqSerializer 按顶层 start/end 注入时间条件）
        query_params = {
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

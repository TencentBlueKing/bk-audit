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

F1 字段上下文服务（SYSTEM_SELECTION 消息核心组件）

字段清单与现有检索白名单（COLLECT_SEARCH_CONFIG）同源全量，三层构建：
- L0 兜底：COLLECT_SEARCH_CONFIG 全量字段元数据
- L1 人工：GlobalMetaConfig（ai_assistant_field_meta）覆盖/新增，运行时写入立即生效
- L2 采样：Doris 最新 N 条采样——最新一条回填 sample_value，多条融合发现拓展字段

nl_name 规则（D-G）：通用字段缺省 = display_name；拓展字段缺省 = extend.{display_name}。
sample_value 给原始查询值（0/-1），不给展示值（"成功(0)"），防止 AI 照抄展示值构造查询。
"""

import json
from datetime import timedelta
from typing import Dict, List, Optional, Tuple

from bk_resource import api, resource
from blueapps.utils.logger import logger
from django.conf import settings
from django.utils import timezone

from api.bk_base.constants import StorageType
from apps.meta.models import GlobalMetaConfig
from apps.meta.permissions import SearchLogPermission
from services.web.databus.models import CollectorPlugin
from services.web.query.ai_assistant.constants import (
    AI_ASSISTANT_FIELD_META_CONFIG_KEY,
    AI_ASSISTANT_FIELD_SAMPLE_ENABLED,
    AI_ASSISTANT_FIELD_SAMPLE_ROWS,
    EXTENSION_NL_NAME_PREFIX,
    FIELD_SAMPLE_LOOKBACK_DAYS,
)
from services.web.query.ai_assistant.exceptions import AIPermissionDeniedError
from services.web.query.ai_assistant.schemas import (
    SelectionFieldMeta,
    SelectionFieldOption,
    SelectionSystem,
    SystemSelectionInput,
    SystemSelectionOutput,
)
from services.web.query.constants import (
    COLLECT_SEARCH_CONFIG,
    DEFAULT_COLLECTOR_SORT_LIST,
    DEFAULT_TIMEDELTA,
)
from services.web.query.serializers import CollectorSearchAllReqSerializer
from services.web.query.utils.doris import DorisQuerySQLBuilder
from services.web.query.utils.field_map import FieldMapHandler
from services.web.query.utils.search_config import (
    FieldSearchConfig,
    QueryConditionOperator,
)


class FieldContextService:
    """F1 字段上下文服务"""

    @classmethod
    def build_selection(cls, namespace: str, system_ids: List[str], username: str) -> SystemSelectionOutput:
        """
        SYSTEM_SELECTION 消息主入口。

        :param namespace: 命名空间
        :param system_ids: 用户选择的系统（一期限 1 个）
        :param username: 操作人（显式传入，不依赖请求上下文）
        :return: SystemSelectionOutput
        :raises AIPermissionDeniedError: 所选系统均无检索权限
        """
        payload = SystemSelectionInput(system_ids=system_ids)

        # ① 权限过滤：无权限系统静默剔除（与检索页 _build_system_conditions 语义一致）
        allowed_ids = [
            system_id
            for system_id in payload.system_ids
            if SearchLogPermission.has_system_search_permission(system_id, username)
        ]
        if not allowed_ids:
            raise AIPermissionDeniedError(
                extra={"system_ids": payload.system_ids, "username": username},
            )

        # ② 系统信息（与 CollectorSearchAllResource 同款 system_list 链路）
        system_map = cls._load_system_map(namespace, allowed_ids)

        # ③ 逐系统构建字段上下文（L0+L1+L2）；常见/历史操作由平台层组装
        systems = [cls._build_system(namespace, system_id, system_map.get(system_id, {})) for system_id in allowed_ids]
        return SystemSelectionOutput(systems=systems)

    # ------------------------------------------------------------------
    # 系统信息
    # ------------------------------------------------------------------

    @classmethod
    def _load_system_map(cls, namespace: str, system_ids: List[str]) -> Dict[str, dict]:
        systems = resource.meta.system_list(namespace=namespace)
        return {system["system_id"]: system for system in systems if system["system_id"] in system_ids}

    # ------------------------------------------------------------------
    # 字段清单（L0 + L1 + L2）
    # ------------------------------------------------------------------

    @classmethod
    def _build_system(cls, namespace: str, system_id: str, system: dict) -> SelectionSystem:
        sys_cfg = cls._load_l1_config(system_id)

        # L0 + L1：通用字段（白名单同源全量）；枚举字段 options 与日志检索页 field_map 同源
        field_overrides = sys_cfg.get("fields", {})
        options_map = cls._load_enum_options(namespace)
        standard_fields = [
            cls._to_standard_field(
                cfg, field_overrides.get(cfg.field.field_name, {}), options_map.get(cfg.field.field_name)
            )
            for cfg in COLLECT_SEARCH_CONFIG.field_configs
        ]

        # L2：采样回填 sample_value（原始查询值）+ 多行融合发现拓展字段（默认关闭）
        sample_rows = cls._sample_system_logs(namespace, system_id)
        extension_fields = []
        if sample_rows:
            cls._fill_sample_values(standard_fields, field_overrides, sample_rows[0])
            extension_fields = cls._discover_extension_fields(system_id, sample_rows)

        # L1：人工配置的拓展字段（L2 关闭时的唯一来源；与 L2 结果按 (raw_name, keys) 去重合并）
        extension_fields = cls._merge_extension_fields(extension_fields, cls._l1_extension_fields(system_id, sys_cfg))

        return SelectionSystem(
            system_id=system_id,
            name=system.get("name", ""),
            standard_fields=standard_fields,
            extension_fields=extension_fields,
        )

    @classmethod
    def _load_l1_config(cls, system_id: str) -> dict:
        """L1 人工配置（GlobalMetaConfig，运行时写入立即生效）"""
        config = GlobalMetaConfig.get(config_key=AI_ASSISTANT_FIELD_META_CONFIG_KEY, default={})
        return config.get("systems", {}).get(system_id, {})

    @staticmethod
    def _load_enum_options(namespace: str) -> Dict[str, List[dict]]:
        """
        枚举字段可选值（与日志检索页 es_query/field_map 接口同源；
        白名单未来新增枚举字段自动透出，无需改本服务）
        """
        return FieldMapHandler(
            fields=[cfg.field.field_name for cfg in COLLECT_SEARCH_CONFIG.field_configs],
            timedelta=DEFAULT_TIMEDELTA,
            namespace=namespace,
        ).field_map

    @staticmethod
    def _to_standard_field(
        cfg: FieldSearchConfig, override: dict, options: Optional[List[dict]] = None
    ) -> SelectionFieldMeta:
        """L0 兜底 + L1 覆盖（nl_name / description / sample_value）；枚举字段附 options"""
        # alias_name 均为字段名本身，中文显示名取 description
        display_name = str(cfg.field.description or cfg.field.alias_name or cfg.field.field_name)
        return SelectionFieldMeta(
            raw_name=cfg.field.field_name,
            keys=[],
            field_type=cfg.field.field_type,
            display_name=display_name,
            nl_name=override.get("nl_name") or display_name,
            description=override.get("description") or str(cfg.field.description or ""),
            allow_operators=[operator.value for operator in cfg.allow_operators],
            sample_value=override.get("sample_value"),
            options=[SelectionFieldOption(**item) for item in options] if options else None,
        )

    @staticmethod
    def _to_extension_field(system_id: str, raw_name: str, keys: List[str], override: dict) -> SelectionFieldMeta:
        """拓展字段（L2 发现或 L1 配置共用）；nl_name 缺省带 extend. 前缀（D-G）"""
        display_name = override.get("display_name") or (keys[-1] if keys else raw_name)
        return SelectionFieldMeta(
            raw_name=raw_name,
            keys=keys,
            # 一期拓展字段恒按 string 处理（协议待冻结 #6）
            field_type="string",
            display_name=display_name,
            nl_name=override.get("nl_name") or f"{EXTENSION_NL_NAME_PREFIX}{display_name}",
            description=override.get("description", ""),
            # 一期拓展字段恒按 string 处理（协议待冻结 #6），给出通用操作符
            allow_operators=override.get("allow_operators")
            or [
                QueryConditionOperator.EQ.value,
                QueryConditionOperator.NEQ.value,
                QueryConditionOperator.INCLUDE.value,
                QueryConditionOperator.EXCLUDE.value,
                QueryConditionOperator.LIKE.value,
            ],
            sample_value=override.get("sample_value"),
            system_id=system_id,
        )

    # ------------------------------------------------------------------
    # L2 采样（默认关闭）
    # ------------------------------------------------------------------

    @classmethod
    def _sample_system_logs(cls, namespace: str, system_id: str) -> List[dict]:
        """
        Doris 采样「最新 N 条」日志（按 dtEventTimeStamp 倒序）。

        standard_fields 的 sample_value 取自最新一条（产品口径不变）；
        其余样本用于融合发现更多拓展字段（单条日志的拓展子键覆盖不全）。
        时间窗口仅用于分区裁剪与性能兜底。
        系统级采样：调用前已做 has_system_search_permission 过滤，不走权限 Mixin。
        """
        if not getattr(settings, "AI_ASSISTANT_FIELD_SAMPLE_ENABLED", AI_ASSISTANT_FIELD_SAMPLE_ENABLED):
            return []
        try:
            table = CollectorPlugin.build_collector_rt(namespace)
            end_time = timezone.now()
            start_time = end_time - timedelta(days=FIELD_SAMPLE_LOOKBACK_DAYS)
            conditions = CollectorSearchAllReqSerializer._build_time_conditions(
                {"start_time": start_time.isoformat(), "end_time": end_time.isoformat()}
            )
            conditions.append(
                {
                    "field": {"raw_name": "system_id", "field_type": "string", "keys": []},
                    "operator": QueryConditionOperator.EQ.value,
                    "filters": [system_id],
                }
            )
            sql_builder = DorisQuerySQLBuilder(
                table=table,
                conditions=conditions,
                sort_list=DEFAULT_COLLECTOR_SORT_LIST,
                page=1,
                page_size=getattr(settings, "AI_ASSISTANT_FIELD_SAMPLE_ROWS", AI_ASSISTANT_FIELD_SAMPLE_ROWS),
            )
            records = api.bk_base.query_sync(
                sql=sql_builder.build_data_sql(),
                prefer_storage=StorageType.DORIS.value,
            )
            return records.get("list") or []
        except Exception as err:  # noqa: BLE001
            # 采样失败不阻断主流程，退化为 sample_value=None
            logger.warning(f"[FieldContextService] sample system log failed: {system_id}, err: {err}")
            return []

    @classmethod
    def _fill_sample_values(cls, standard_fields: List[SelectionFieldMeta], field_overrides: dict, row: dict) -> None:
        """采样值回填（原始查询值，取最新一条）；L1 人工配置的 sample_value 优先"""
        for item in standard_fields:
            if item.raw_name in field_overrides and "sample_value" in field_overrides[item.raw_name]:
                continue
            value = row.get(item.raw_name, row.get(item.raw_name.lower()))
            if value is not None:
                item.sample_value = value

    @classmethod
    def _discover_extension_fields(cls, system_id: str, rows: List[dict]) -> List[SelectionFieldMeta]:
        """从 is_json 容器字段发现第一层子键（多行融合，跳过白名单已声明的 sub_keys）

        rows 按时间倒序：同一 (容器, 子键) 保留最新一行的采样值，多行并集提升拓展字段覆盖率。
        """
        discovered: Dict[Tuple[str, Tuple[str, ...]], SelectionFieldMeta] = {}
        for row in rows:
            for cfg in COLLECT_SEARCH_CONFIG.field_configs:
                if not cfg.field.is_json:
                    continue
                raw_name = cfg.field.field_name
                container = row.get(raw_name, row.get(raw_name.lower()))
                if isinstance(container, str):
                    try:
                        container = json.loads(container)
                    except (json.JSONDecodeError, TypeError):
                        container = None
                if not isinstance(container, dict):
                    continue
                declared_keys = {sub["field_name"] for sub in (cfg.field.property or {}).get("sub_keys", [])}
                for key, value in container.items():
                    if key in declared_keys:
                        continue
                    dedup_key = (raw_name, tuple([key]))
                    if dedup_key in discovered:
                        continue
                    discovered[dedup_key] = cls._to_extension_field(system_id, raw_name, [key], {"sample_value": value})
        return list(discovered.values())

    # ------------------------------------------------------------------
    # L1 拓展字段
    # ------------------------------------------------------------------

    @classmethod
    def _l1_extension_fields(cls, system_id: str, sys_cfg: dict) -> List[SelectionFieldMeta]:
        return [
            cls._to_extension_field(system_id, item["raw_name"], list(item.get("keys") or []), item)
            for item in sys_cfg.get("extension_fields", [])
            if item.get("raw_name")
        ]

    @staticmethod
    def _merge_extension_fields(
        discovered: List[SelectionFieldMeta], configured: List[SelectionFieldMeta]
    ) -> List[SelectionFieldMeta]:
        """L1 配置优先，L2 发现补充（按 (raw_name, keys) 去重）"""
        merged: Dict[Tuple[str, Tuple[str, ...]], SelectionFieldMeta] = {}
        for item in discovered + configured:
            merged[(item.raw_name, tuple(item.keys))] = item
        return list(merged.values())

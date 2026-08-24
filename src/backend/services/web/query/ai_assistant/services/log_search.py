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
"""

"""
F3 检索快照服务（LOG_SEARCH 消息核心组件）

七步链路（设计文档 §17.3）：
① 组装 payload 走 CollectorSearchAllReqSerializer DRF 校验（字段白名单/操作符/时间条件注入复用）
② 权限注入（显式 username；无权限时 get_scope_auth_systems 返回 [""] 自然零命中）
③ Doris 检索（CollectorPlugin.build_collector_rt + DorisQuerySQLBuilder + bulk_request）
④ 展示化 + 脱敏（SearchDataParser.parse_data，显式 username）
⑤ system_info 补充
⑥ 快照组装（键名归一 / columns 裁剪 / 截断 / system_info 裁剪）

快照语义：samples 是执行时刻固化的展示化结果（脱敏后），历史展示与预览导出都读快照。
"""

import time
from typing import Dict, List

from bk_resource import api, resource
from bk_resource.base import Empty
from blueapps.utils.logger import logger
from django.utils import timezone
from opentelemetry import trace
from rest_framework.exceptions import ValidationError as DrfValidationError

from api.bk_base.constants import StorageType
from apps.meta.permissions import SearchLogPermission
from core.exceptions import ValidationError as CoreValidationError
from core.sql.constants import FieldType
from core.utils.data import extract_nested_value
from services.web.databus.models import CollectorPlugin
from services.web.query.ai_assistant.constants import (
    LOG_SEARCH_SNAPSHOT_PAGE_SIZE,
    LOG_SEARCH_SNAPSHOT_VALUE_MAX_LENGTH,
    SNAPSHOT_DEFAULT_COLUMNS,
    SYSTEM_INFO_SNAPSHOT_KEYS,
)
from services.web.query.ai_assistant.exceptions import AIOutputInvalidError
from services.web.query.ai_assistant.schemas import (
    LogSearchOutput,
    QuerySummary,
    ResultColumn,
    SearchCondition,
)
from services.web.query.constants import DEFAULT_COLLECTOR_SORT_LIST
from services.web.query.resources.base import SearchDataParser
from services.web.query.serializers import CollectorSearchAllReqSerializer
from services.web.query.utils.doris import DorisQuerySQLBuilder
from services.web.query.utils.field import LOG_SEARCH_ALL_FIELDS_MAP
from services.web.query.utils.search_config import QueryConditionOperator


class LogSearchService:
    """LOG_SEARCH 快照执行"""

    @classmethod
    def search(
        cls,
        condition: SearchCondition,
        namespace: str,
        username: str,
        source: str = "field_condition",
    ) -> LogSearchOutput:
        """
        :param condition: 统一条件结构（NL 输出或前端字段条件构造，同构）
        :param namespace: 命名空间（后端按会话/消息归属注入）
        :param username: 操作人（显式传入，不依赖请求上下文）
        :param source: 条件来源 natural_language / field_condition
        :return: LogSearchOutput（零命中也是成功态：total=0 + samples=[]）
        :raises AIOutputInvalidError: 条件整体校验失败（字段白名单/操作符/形态）
        """
        span = trace.get_current_span()
        span.set_attribute("ai.log_search.scope_id", condition.scope_id)
        span.set_attribute("ai.log_search.source", source)

        # ① DRF 校验（字段白名单/操作符/keys + 4 条时间条件注入，全复用）
        validated = cls._validate_condition(condition, namespace)
        # ② 权限注入（显式 username）
        validated["conditions"] = cls._inject_permission(validated["conditions"], condition, username)
        # ③ Doris 检索（固化 page=1 / size=100 / 最新排序）
        data = cls._execute_query(namespace, validated)
        # ④ 展示化 + 脱敏（显式身份，D1）
        results = cls._format_hits(data.pop("results", []), username)
        # ⑤ system_info 补充
        cls._bind_system_info(namespace, results)
        # ⑥ 快照组装
        return cls._build_output(condition, data, results, source)

    # ------------------------------------------------------------------
    # ① DRF 校验复用
    # ------------------------------------------------------------------

    @classmethod
    def _validate_condition(cls, condition: SearchCondition, namespace: str) -> dict:
        payload = {
            "namespace": namespace,
            "start_time": condition.start_time,
            "end_time": condition.end_time,
            "conditions": [cond.model_dump() for cond in condition.conditions],
            "page": 1,
            "page_size": LOG_SEARCH_SNAPSHOT_PAGE_SIZE,
            "sort_list": DEFAULT_COLLECTOR_SORT_LIST,
            "bind_system_info": True,
        }
        serializer = CollectorSearchAllReqSerializer(data=payload)
        try:
            serializer.is_valid(raise_exception=True)
        except (DrfValidationError, CoreValidationError) as err:
            raise AIOutputInvalidError(extra={"errors": str(err)})
        return serializer.validated_data

    # ------------------------------------------------------------------
    # ② 权限注入（与 CollectorSearchReqPermissionCheckMixIn 语义一致，显式 username）
    # ------------------------------------------------------------------

    @classmethod
    def _inject_permission(cls, conditions: List[dict], condition: SearchCondition, username: str) -> List[dict]:
        authorized_systems = SearchLogPermission.get_scope_auth_systems(
            scope_type=condition.scope_type,
            scope_id=condition.scope_id,
            username=username,
        )
        # 无权限时 authorized_systems 为 [""]，SQL system_id IN ("") 自然零命中，无需 short-circuit
        return [
            {
                "field": {"raw_name": "system_id", "field_type": FieldType.STRING.value, "keys": []},
                "operator": QueryConditionOperator.INCLUDE.value,
                "filters": authorized_systems,
            }
        ] + conditions

    # ------------------------------------------------------------------
    # ③ Doris 检索
    # ------------------------------------------------------------------

    @classmethod
    def _execute_query(cls, namespace: str, validated: dict) -> dict:
        table = CollectorPlugin.build_collector_rt(namespace)
        sql_builder = DorisQuerySQLBuilder(
            table=table,
            conditions=validated["conditions"],
            sort_list=validated["sort_list"],
            page=validated["page"],
            page_size=validated["page_size"],
        )
        data_sql = sql_builder.build_data_sql()
        count_sql = sql_builder.build_count_sql()
        logger.info(f"[LogSearchService] data sql: {data_sql}; count sql: {count_sql}")

        started_at = time.time() * 1000
        data_resp, count_resp = api.bk_base.query_sync.bulk_request(
            [
                {"sql": data_sql, "prefer_storage": StorageType.DORIS.value},
                {"sql": count_sql, "prefer_storage": StorageType.DORIS.value},
            ]
        )
        took_ms = int(time.time() * 1000 - started_at)

        results = data_resp.get("list", [])
        # 排序字段键名兜底（大小写/缺键）
        order_fields = [item["order_field"] for item in validated["sort_list"] if item.get("order_field")]
        for hit in results:
            for order_field in order_fields:
                hit.setdefault(order_field, hit.get(order_field.lower()))
        total = count_resp.get("list", [{}])[0].get("count", 0)
        return {"results": results, "total": total, "took_ms": took_ms}

    # ------------------------------------------------------------------
    # ④ 展示化 + 脱敏（D1 默认实现：复用 SearchDataParser，显式身份）
    # ------------------------------------------------------------------

    @classmethod
    def _format_hits(cls, results: List[dict], username: str) -> List[dict]:
        return SearchDataParser().parse_data(results, username=username)

    # ------------------------------------------------------------------
    # ⑤ system_info 补充（与 CollectorSearchAllResource 同款）
    # ------------------------------------------------------------------

    @classmethod
    def _bind_system_info(cls, namespace: str, results: List[dict]) -> None:
        systems = resource.meta.system_list(namespace=namespace)
        system_map = {system["system_id"]: system for system in systems}
        for value in results:
            value["system_info"] = system_map.get(value.get("system_id"), dict())

    # ------------------------------------------------------------------
    # ⑥ 快照组装
    # ------------------------------------------------------------------

    @classmethod
    def _build_output(
        cls, condition: SearchCondition, data: dict, results: List[dict], source: str
    ) -> LogSearchOutput:
        columns = cls.build_columns()
        samples = [cls._build_sample(row, columns) for row in results[:LOG_SEARCH_SNAPSHOT_PAGE_SIZE]]
        return LogSearchOutput(
            total=data["total"],
            columns=columns,
            samples=samples,
            query_summary=QuerySummary(
                scope_type=condition.scope_type,
                scope_id=condition.scope_id,
                time_range={"start_time": condition.start_time, "end_time": condition.end_time},
                condition_count=len(condition.conditions),
                source=source,
                took_ms=data.get("took_ms", 0),
                executed_at=timezone.now().isoformat(),
            ),
        )

    @classmethod
    def build_columns(cls) -> List[ResultColumn]:
        """
        快照列（产品需求 9 列固定展示字段，首列 start_time）。

        display_name 用产品文案（SNAPSHOT_DEFAULT_COLUMNS），description 取自全量
        字段元数据 LOG_SEARCH_ALL_FIELDS_MAP（COLLECT_SEARCH_CONFIG 只是条件字段白名单）。
        """
        columns = []
        for raw_name, display_name in SNAPSHOT_DEFAULT_COLUMNS:
            field = LOG_SEARCH_ALL_FIELDS_MAP.get(raw_name)
            if not field:
                continue
            columns.append(
                ResultColumn(
                    raw_name=raw_name,
                    keys=[],
                    display_name=display_name,
                    description=str(field.description or ""),
                )
            )
        return columns

    @classmethod
    def _build_sample(cls, row: dict, columns: List[ResultColumn]) -> Dict:
        """
        单行快照：按 columns 裁剪取值（键名归一 + keys 下钻 + 截断）。

        samples 字典键 = 列 full_key（标准列 = raw_name，拓展列 = raw_name/key/...）。
        """
        sample = {}
        for column in columns:
            value = extract_nested_value(row.get(column.raw_name, row.get(column.raw_name.lower())), column.keys)
            if isinstance(value, Empty) or value is None:
                continue
            if isinstance(value, str) and len(value) > LOG_SEARCH_SNAPSHOT_VALUE_MAX_LENGTH:
                value = value[:LOG_SEARCH_SNAPSHOT_VALUE_MAX_LENGTH]
            sample[column.full_key] = value
        # system_info 裁剪到展示必要键
        system_info = row.get("system_info")
        if isinstance(system_info, dict) and system_info:
            sample["system_info"] = {key: system_info.get(key) for key in SYSTEM_INFO_SNAPSHOT_KEYS}
        return sample

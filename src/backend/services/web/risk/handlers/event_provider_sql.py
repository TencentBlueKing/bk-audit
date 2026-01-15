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
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.

EventProvider SQL 生成器

纯 SQL 生成，不负责执行查询。
复用 RiskEventSubscriptionSqlGenerator 生成聚合、Latest、First 三种 SQL。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from pypika import Order as PypikaOrder

from core.sql.builder.builder import BKBaseQueryBuilder
from core.sql.constants import AggregateType, FieldType, Operator
from core.sql.model import (
    Condition,
    Field,
    Order,
    Pagination,
    SqlConfig,
    Table,
    WhereCondition,
)
from services.web.risk.handlers.subscription_sql import (
    RiskEventSubscriptionSqlGenerator,
)


def get_field_type_from_strategy(strategy, field_name: str) -> Optional[str]:
    """
    从策略 configs.select 获取字段的真实类型

    Args:
        strategy: 策略对象
        field_name: 字段名（对应 select.display_name）

    Returns:
        field_type 字符串，如 'string', 'long' 等；不存在则返回 None
    """
    if not strategy:
        return None

    configs = getattr(strategy, 'configs', None)
    if not configs or not isinstance(configs, dict):
        return None

    select_fields = configs.get("select", [])
    if not select_fields:
        return None

    field_type_map = {
        select["display_name"]: select["field_type"] for select in select_fields if select.get("field_type")
    }

    return field_type_map.get(field_name)


@dataclass
class EventFieldConfig:
    """事件字段配置"""

    raw_name: str  # JSON key 名称（中文字段名）
    display_name: str  # SQL 别名
    field_type: FieldType = FieldType.STRING
    aggregate: Optional[AggregateType] = None


class EventProviderSqlBuilder:
    """
    EventProvider SQL 构建器（纯 SQL 生成）

    复用 RiskEventSubscriptionSqlGenerator 生成 SQL，不执行查询。
    由调用方（EventProvider）收集 SQL 后并发执行。
    """

    TABLE_ALIAS: str = "t"
    JSON_COLUMN: str = "event_data"

    def __init__(
        self,
        table_name: str,
        strategy_id: int,
        raw_event_id: str,
        start_time: int,
        end_time: int,
    ):
        """
        初始化 SQL Builder

        Args:
            table_name: BKBase 表名，如 "591_xxx_1.doris"
            strategy_id: 策略 ID
            raw_event_id: 原始事件 ID
            start_time: 事件开始时间（毫秒时间戳）
            end_time: 事件结束时间（毫秒时间戳）
        """
        self.table_name = table_name
        self.strategy_id = strategy_id
        self.raw_event_id = raw_event_id
        self.start_time = start_time
        self.end_time = end_time

        self._generator = RiskEventSubscriptionSqlGenerator(BKBaseQueryBuilder())
        self._table = Table(table_name=table_name, alias=self.TABLE_ALIAS)
        self._base_where = self._build_base_where()

    def _build_base_where(self) -> WhereCondition:
        """构建基础 WHERE 条件"""
        conditions = [
            WhereCondition(
                condition=Condition(
                    field=Field(
                        table=self.TABLE_ALIAS,
                        raw_name="strategy_id",
                        display_name="strategy_id",
                        field_type=FieldType.LONG,
                    ),
                    operator=Operator.EQ,
                    filter=self.strategy_id,
                )
            ),
            WhereCondition(
                condition=Condition(
                    field=Field(
                        table=self.TABLE_ALIAS,
                        raw_name="raw_event_id",
                        display_name="raw_event_id",
                        field_type=FieldType.STRING,
                    ),
                    operator=Operator.EQ,
                    filter=self.raw_event_id,
                )
            ),
            WhereCondition(
                condition=Condition(
                    field=Field(
                        table=self.TABLE_ALIAS,
                        raw_name="dtEventTimeStamp",
                        display_name="dtEventTimeStamp",
                        field_type=FieldType.LONG,
                    ),
                    operator=Operator.BETWEEN,
                    filters=[self.start_time, self.end_time],
                )
            ),
        ]
        return WhereCondition(conditions=conditions)

    def _build_json_field(self, config: EventFieldConfig) -> Field:
        """
        构建 JSON 下钻字段

        keys 参数触发 RiskEventSubscriptionSqlGenerator._get_pypika_field 的逻辑：
        - JSON_EXTRACT_STRING(event_data, '$.字段名')
        - 非 STRING 类型会 CAST 到目标类型
        """
        return Field(
            table=self.TABLE_ALIAS,
            raw_name=self.JSON_COLUMN,
            display_name=config.display_name,
            field_type=config.field_type,
            keys=[config.raw_name],
            aggregate=config.aggregate,
        )

    def _build_order_field(self) -> Field:
        """构建排序字段（dtEventTimeStamp）"""
        return Field(
            table=self.TABLE_ALIAS,
            raw_name="dtEventTimeStamp",
            display_name="dtEventTimeStamp",
            field_type=FieldType.LONG,
        )

    def build_aggregate_sql(self, fields: List[EventFieldConfig]) -> Optional[str]:
        """
        构建聚合查询 SQL

        Args:
            fields: 聚合字段配置列表（必须有 aggregate 属性）

        Returns:
            SQL 字符串，或 None（字段为空时）
        """
        if not fields:
            return None

        select_fields = [self._build_json_field(f) for f in fields]

        config = SqlConfig(
            select_fields=select_fields,
            from_table=self._table,
            where=self._base_where,
            group_by=[],
        )

        return str(self._generator.generate(config))

    def build_first_sql(self, fields: List[EventFieldConfig]) -> Optional[str]:
        """
        构建 first 查询 SQL（ORDER BY ASC LIMIT 1）

        Args:
            fields: 字段配置列表

        Returns:
            SQL 字符串，或 None（字段为空时）
        """
        if not fields:
            return None

        select_fields = [self._build_json_field(f) for f in fields]
        order_by = [Order(field=self._build_order_field(), order=PypikaOrder.asc)]

        config = SqlConfig(
            select_fields=select_fields,
            from_table=self._table,
            where=self._base_where,
            order_by=order_by,
            pagination=Pagination(limit=1),
        )

        return str(self._generator.generate(config))

    def build_latest_sql(self, fields: List[EventFieldConfig]) -> Optional[str]:
        """
        构建 latest 查询 SQL（ORDER BY DESC LIMIT 1）

        Args:
            fields: 字段配置列表

        Returns:
            SQL 字符串，或 None（字段为空时）
        """
        if not fields:
            return None

        select_fields = [self._build_json_field(f) for f in fields]
        order_by = [Order(field=self._build_order_field(), order=PypikaOrder.desc)]

        config = SqlConfig(
            select_fields=select_fields,
            from_table=self._table,
            where=self._base_where,
            order_by=order_by,
            pagination=Pagination(limit=1),
        )

        return str(self._generator.generate(config))

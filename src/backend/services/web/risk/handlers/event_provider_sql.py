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
使用 BkbaseDorisSqlGenerator 生成聚合、Latest、First 三种 SQL。
"""
from __future__ import annotations

from typing import List, Optional

from django.conf import settings
from django.utils import timezone
from pypika import Order as PypikaOrder

from apps.meta.constants import ConfigLevelChoices
from apps.meta.models import GlobalMetaConfig
from core.sql.builder.builder import BKBaseQueryBuilder
from core.sql.builder.generator import BkbaseDorisSqlGenerator
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
from core.utils.time import ceil_to_second
from services.web.databus.constants import DORIS_EVENT_BKBASE_RT_ID_KEY
from services.web.risk.models import Risk


class EventFieldConfig(Field):
    """
    风险事件字段配置

    继承 core.sql.model.Field，预填 table 别名。
    对于 event_data JSON 下钻字段，使用 event_data() 工厂方法。
    """

    table: str = "t"

    @classmethod
    def event_data(
        cls,
        field_name: str,
        display_name: str,
        field_type: FieldType = FieldType.STRING,
        aggregate: Optional[AggregateType] = None,
    ) -> "EventFieldConfig":
        """
        构造 event_data JSON 下钻字段

        Args:
            field_name: event_data 中的 JSON key 名称
            display_name: SQL 别名
            field_type: 字段类型
            aggregate: 聚合函数
        """
        return cls(
            raw_name="event_data",
            display_name=display_name,
            field_type=field_type,
            keys=[field_name],
            aggregate=aggregate,
        )


class EventAggregateSqlBuilder:
    """
    EventAggregateSqlBuilder 用于生成事件聚合查询 SQL
    """

    TABLE_ALIAS: str = "t"

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

        self._generator = BkbaseDorisSqlGenerator(BKBaseQueryBuilder())
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

    def _build_order_field(self) -> Field:
        """构建排序字段（dtEventTimeStamp）"""
        return Field(
            table=self.TABLE_ALIAS,
            raw_name="dtEventTimeStamp",
            display_name="dtEventTimeStamp",
            field_type=FieldType.LONG,
        )

    def build_count_sql(self) -> str:
        """
        构建 COUNT(*) SQL

        COUNT(*) 不能通过普通字段机制生成（PyPika 会将 * 转义为 `t`.`*`），
        使用 generator.generate_count 专用方法。
        """
        config = SqlConfig(
            select_fields=[],
            from_table=self._table,
            where=self._base_where,
        )
        return str(self._generator.generate_count(config))

    def build_aggregate_sql(self, fields: List[Field]) -> Optional[str]:
        """
        构建聚合查询 SQL

        Args:
            fields: 字段列表（Field 或其子类，如 EventFieldConfig）

        Returns:
            SQL 字符串，或 None（字段为空时）
        """
        if not fields:
            return None

        config = SqlConfig(
            select_fields=list(fields),
            from_table=self._table,
            where=self._base_where,
            group_by=[],
        )

        return str(self._generator.generate(config))

    def build_first_sql(self, fields: List[Field]) -> Optional[str]:
        """
        构建 first 查询 SQL（ORDER BY ASC LIMIT 1）

        Args:
            fields: 字段列表

        Returns:
            SQL 字符串，或 None（字段为空时）
        """
        if not fields:
            return None

        order_by = [Order(field=self._build_order_field(), order=PypikaOrder.asc)]

        config = SqlConfig(
            select_fields=list(fields),
            from_table=self._table,
            where=self._base_where,
            order_by=order_by,
            pagination=Pagination(limit=1),
        )

        return str(self._generator.generate(config))

    def build_latest_sql(self, fields: List[Field]) -> Optional[str]:
        """
        构建 latest 查询 SQL（ORDER BY DESC LIMIT 1）

        Args:
            fields: 字段列表

        Returns:
            SQL 字符串，或 None（字段为空时）
        """
        if not fields:
            return None

        order_by = [Order(field=self._build_order_field(), order=PypikaOrder.desc)]

        config = SqlConfig(
            select_fields=list(fields),
            from_table=self._table,
            where=self._base_where,
            order_by=order_by,
            pagination=Pagination(limit=1),
        )

        return str(self._generator.generate(config))


class RiskEventAggregateSqlBuilder(EventAggregateSqlBuilder):
    """
    基于 Risk 对象的事件聚合 SQL Builder

    自动从 Risk 对象提取 strategy_id、raw_event_id、起止时间等参数，
    简化调用方代码。
    """

    STORAGE_SUFFIX: str = "doris"

    @classmethod
    def get_rt_id(cls) -> str:
        """获取事件结果表 ID（带 doris 后缀）"""

        rt_id = GlobalMetaConfig.get(
            config_key=DORIS_EVENT_BKBASE_RT_ID_KEY,
            config_level=ConfigLevelChoices.NAMESPACE.value,
            instance_key=settings.DEFAULT_NAMESPACE,
            default="",
        )
        if rt_id:
            rt_id = rt_id.strip()
        if rt_id and not rt_id.endswith(f".{cls.STORAGE_SUFFIX}"):
            rt_id = f"{rt_id}.{cls.STORAGE_SUFFIX}"
        return rt_id

    def __init__(self, risk: "Risk"):
        """
        初始化

        Args:
            risk: Risk 对象
        """
        self.risk = risk
        end_time = ceil_to_second(risk.event_end_time) if risk.event_end_time else timezone.now()

        super().__init__(
            table_name=self.get_rt_id(),
            strategy_id=risk.strategy_id,
            raw_event_id=risk.raw_event_id,
            start_time=int(risk.event_time.timestamp() * 1000),
            end_time=int(end_time.timestamp() * 1000),
        )

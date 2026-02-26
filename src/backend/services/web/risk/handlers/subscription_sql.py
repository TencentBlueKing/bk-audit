# -*- coding: utf-8 -*-
"""
Risk event subscription SQL builder.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Dict, List, Optional, Tuple

from django.conf import settings
from pydantic import BaseModel
from pydantic import Field as PydanticField
from pypika.enums import Order as PypikaOrder
from pypika.functions import Cast
from pypika.terms import ValueWrapper

from api.bk_base.constants import StorageType
from apps.meta.constants import ConfigLevelChoices
from apps.meta.models import GlobalMetaConfig
from core.sql.builder.builder import BKBaseQueryBuilder, BkBaseTable
from core.sql.builder.functions import Concat, GroupConcat
from core.sql.builder.generator import BkbaseDorisSqlGenerator
from core.sql.constants import AggregateType, FieldType, JoinType, Operator
from core.sql.model import (
    Condition,
    Field,
    JoinTable,
    LinkField,
    Order,
    Pagination,
    SqlConfig,
    Table,
    WhereCondition,
)
from services.web.databus.constants import (
    ASSET_RISK_BKBASE_RT_ID_KEY,
    ASSET_STRATEGY_BKBASE_RT_ID_KEY,
    ASSET_STRATEGY_TAG_BKBASE_RT_ID_KEY,
    DORIS_EVENT_BKBASE_RT_ID_KEY,
)
from services.web.risk.constants import RiskEventSubscriptionFieldCategory


class SubscriptionFieldConfig(BaseModel):
    """
    描述订阅 SQL 中的固定字段配置，用于统一生成 select 列及前端配置。

    Attributes:
        category: 字段所属类别，决定使用哪张底层表/别名。
        name: Doris 实际字段名。
        field_type: 字段默认的数据类型，决定 select 输出与条件解析。
        display_name: 可选的展示名称；为空时默认使用 name。
        supports_drill: 是否支持 JSON 下钻（例如 event_data）。
        drill_examples: JSON path 的示例数组，仅用于前端提示。
        default_return_type: 针对 JSON 字段，选择默认的返回类型；为空则沿用 field_type。
    """

    category: RiskEventSubscriptionFieldCategory
    name: str
    field_type: FieldType
    display_name: Optional[str] = None
    supports_drill: bool = False
    drill_examples: list[str] = PydanticField(default_factory=list)
    default_return_type: Optional[FieldType] = None

    @property
    def normalized_display_name(self) -> str:
        """返回用于 SQL 输出与前端展示的字段名。"""
        return self.display_name or self.name

    @property
    def normalized_return_type(self) -> FieldType:
        """若指定 default_return_type 则使用，否则退回 field_type。"""
        return self.default_return_type or self.field_type


@dataclass
class RiskEventSubscriptionSQLBuilder:
    """
    构造风险事件订阅查询所需的 Doris SQL。

    订阅查询固定由事件、风险、策略及策略标签四张结果表拼出一条多表 JOIN 语句，
    并以时间范围与订阅自带的筛选条件控制返回数据。相比 BaseDorisSQLBuilder，
    这里的 join 拓扑、字段模板与排序方式都是预设常量，引入父类反而会增加动态配置的复杂度，
    因此保留为独立实现，专注于风险事件订阅场景。
    """

    namespace: str
    time_range: Tuple[int, int]
    subscription_condition: Optional[WhereCondition] = None

    #: Doris 表后缀，确保查询命中 doris 存储
    STORAGE_SUFFIX: ClassVar[str] = StorageType.DORIS.value
    #: 风险事件原始表别名
    EVENT_ALIAS: ClassVar[str] = "e"
    #: 风险单据表别名
    RISK_ALIAS: ClassVar[str] = "r"
    #: 策略配置表别名
    STRATEGY_ALIAS: ClassVar[str] = "s"
    #: 策略标签聚合子查询别名
    STRATEGY_TAG_ALIAS: ClassVar[str] = "st"
    #: 外层订阅过滤子查询别名
    OUTER_ALIAS: ClassVar[str] = "t"
    #: BKBase 表配置映射
    TABLE_CONFIG_MAP: ClassVar[Dict[str, str]] = {
        "risk": ASSET_RISK_BKBASE_RT_ID_KEY,
        "strategy": ASSET_STRATEGY_BKBASE_RT_ID_KEY,
        "strategy_tag": ASSET_STRATEGY_TAG_BKBASE_RT_ID_KEY,
        "event": DORIS_EVENT_BKBASE_RT_ID_KEY,
    }

    def __post_init__(self):
        self.namespace = self.namespace or settings.DEFAULT_NAMESPACE
        self._start_time, self._end_time = self.time_range
        self._generator = BkbaseDorisSqlGenerator(BKBaseQueryBuilder())
        self._table_names = self._load_table_names()
        self._event_table = Table(table_name=self._table_names["event"], alias=self.EVENT_ALIAS)
        self._risk_table = Table(table_name=self._table_names["risk"], alias=self.RISK_ALIAS)
        self._strategy_table = Table(table_name=self._table_names["strategy"], alias=self.STRATEGY_ALIAS)
        self._strategy_tag_table = Table(
            table_name=self._build_strategy_tag_subquery(),
            alias=self.STRATEGY_TAG_ALIAS,
        )
        self._join_tables = self._build_join_tables()
        self._time_condition = self._build_time_condition()
        self._inner_select_fields = self._build_inner_select_fields()
        self._base_subquery = self._build_inner_query()
        self._outer_table = Table(table_name=self._base_subquery, alias=self.OUTER_ALIAS)
        self._select_fields = self._build_outer_select_fields()
        self._where_condition = self._normalize_subscription_condition()
        self._order_by = [
            Order(
                field=Field(
                    table=self.OUTER_ALIAS,
                    raw_name="dtEventTimeStamp",
                    display_name="dtEventTimeStamp",
                    field_type=FieldType.LONG,
                ),
                order=PypikaOrder.desc,
            )
        ]

    def build_query_sql(self, limit: int, offset: int) -> str:
        """
        构建数据查询 SQL, 应用指定的分页窗口。
        """
        config = self._build_sql_config(
            select_fields=self._select_fields,
            pagination=Pagination(limit=limit, offset=offset),
            order_by=self._order_by,
        )
        return str(self._generator.generate(config))

    def build_count_sql(self) -> str:
        """
        构建统计 SQL，只计算符合条件的事件数量。
        """
        count_field = Field(
            table=self.OUTER_ALIAS,
            raw_name="raw_event_id",
            display_name="count",
            field_type=FieldType.LONG,
            aggregate=AggregateType.COUNT,
        )
        config = self._build_sql_config(select_fields=[count_field])
        return str(self._generator.generate(config))

    def _build_sql_config(
        self,
        *,
        select_fields: Optional[list[Field]] = None,
        pagination: Optional[Pagination] = None,
        order_by: Optional[list[Order]] = None,
    ) -> SqlConfig:
        """组装统一的 SQL 配置对象。"""
        return SqlConfig(
            select_fields=select_fields or [],
            from_table=self._outer_table,
            join_tables=None,
            where=self._where_condition,
            order_by=order_by or [],
            pagination=pagination,
        )

    def _build_time_condition(self) -> WhereCondition:
        """
        依据订阅给定的时间范围，构造 BETWEEN 条件，限定 Doris 查询窗口。
        """
        field = Field(
            table=self.EVENT_ALIAS,
            raw_name="dtEventTimeStamp",
            display_name="dtEventTimeStamp",
            field_type=FieldType.LONG,
        )
        return WhereCondition(
            condition=Condition(field=field, operator=Operator.BETWEEN, filters=[self._start_time, self._end_time])
        )

    #: 固定输出字段配置，便于复用元数据
    INNER_FIELD_CONFIG: ClassVar[List[SubscriptionFieldConfig]] = [
        SubscriptionFieldConfig(
            category=RiskEventSubscriptionFieldCategory.EVENT, name="dtEventTime", field_type=FieldType.STRING
        ),
        SubscriptionFieldConfig(
            category=RiskEventSubscriptionFieldCategory.EVENT,
            name="dtEventTimeStamp",
            field_type=FieldType.LONG,
        ),
        SubscriptionFieldConfig(
            category=RiskEventSubscriptionFieldCategory.EVENT, name="event_id", field_type=FieldType.STRING
        ),
        SubscriptionFieldConfig(
            category=RiskEventSubscriptionFieldCategory.EVENT,
            name="event_content",
            field_type=FieldType.TEXT,
        ),
        SubscriptionFieldConfig(
            category=RiskEventSubscriptionFieldCategory.EVENT,
            name="raw_event_id",
            field_type=FieldType.STRING,
        ),
        SubscriptionFieldConfig(
            category=RiskEventSubscriptionFieldCategory.EVENT,
            name="strategy_id",
            field_type=FieldType.LONG,
        ),
        SubscriptionFieldConfig(
            category=RiskEventSubscriptionFieldCategory.EVENT,
            name="event_evidence",
            field_type=FieldType.TEXT,
        ),
        SubscriptionFieldConfig(
            category=RiskEventSubscriptionFieldCategory.EVENT,
            name="event_type",
            field_type=FieldType.STRING,
        ),
        SubscriptionFieldConfig(
            category=RiskEventSubscriptionFieldCategory.EVENT,
            name="event_data",
            field_type=FieldType.STRING,
            supports_drill=True,
            drill_examples=["login", "ip"],
            default_return_type=FieldType.STRING,
        ),
        SubscriptionFieldConfig(
            category=RiskEventSubscriptionFieldCategory.EVENT,
            name="event_time",
            field_type=FieldType.LONG,
        ),
        SubscriptionFieldConfig(
            category=RiskEventSubscriptionFieldCategory.EVENT,
            name="event_source",
            field_type=FieldType.STRING,
        ),
        SubscriptionFieldConfig(
            category=RiskEventSubscriptionFieldCategory.EVENT,
            name="operator",
            field_type=FieldType.STRING,
            display_name="event_operator",
        ),
        SubscriptionFieldConfig(
            category=RiskEventSubscriptionFieldCategory.RISK, name="risk_id", field_type=FieldType.STRING
        ),
        SubscriptionFieldConfig(
            category=RiskEventSubscriptionFieldCategory.RISK,
            name="event_end_time",
            field_type=FieldType.LONG,
        ),
        SubscriptionFieldConfig(
            category=RiskEventSubscriptionFieldCategory.RISK,
            name="operator",
            field_type=FieldType.STRING,
            display_name="risk_operator",
        ),
        SubscriptionFieldConfig(
            category=RiskEventSubscriptionFieldCategory.RISK,
            name="status",
            field_type=FieldType.STRING,
            display_name="risk_status",
        ),
        SubscriptionFieldConfig(
            category=RiskEventSubscriptionFieldCategory.RISK, name="rule_id", field_type=FieldType.LONG
        ),
        SubscriptionFieldConfig(
            category=RiskEventSubscriptionFieldCategory.RISK, name="rule_version", field_type=FieldType.INT
        ),
        SubscriptionFieldConfig(
            category=RiskEventSubscriptionFieldCategory.RISK,
            name="origin_operator",
            field_type=FieldType.STRING,
        ),
        SubscriptionFieldConfig(
            category=RiskEventSubscriptionFieldCategory.RISK,
            name="current_operator",
            field_type=FieldType.STRING,
        ),
        SubscriptionFieldConfig(
            category=RiskEventSubscriptionFieldCategory.RISK,
            name="notice_users",
            field_type=FieldType.STRING,
        ),
        SubscriptionFieldConfig(
            category=RiskEventSubscriptionFieldCategory.RISK,
            name="risk_label",
            field_type=FieldType.STRING,
        ),
        SubscriptionFieldConfig(
            category=RiskEventSubscriptionFieldCategory.RISK,
            name="title",
            field_type=FieldType.STRING,
            display_name="risk_title",
        ),
        SubscriptionFieldConfig(
            category=RiskEventSubscriptionFieldCategory.STRATEGY_TAG,
            name="tag_ids_json",
            field_type=FieldType.STRING,
            display_name="strategy_tag_ids",
        ),
        SubscriptionFieldConfig(
            category=RiskEventSubscriptionFieldCategory.STRATEGY,
            name="risk_level",
            field_type=FieldType.STRING,
        ),
        SubscriptionFieldConfig(
            category=RiskEventSubscriptionFieldCategory.STRATEGY, name="is_formal", field_type=FieldType.INT
        ),
        SubscriptionFieldConfig(
            category=RiskEventSubscriptionFieldCategory.STRATEGY,
            name="status",
            field_type=FieldType.STRING,
            display_name="strategy_status",
        ),
    ]

    #: 根据字段所属类别，映射到构造实际 Field 的方法，便于统一遍历生成 select 列
    CATEGORY_FIELD_BUILDERS: ClassVar[dict[str, str]] = {
        RiskEventSubscriptionFieldCategory.EVENT.value: "_event_field",
        RiskEventSubscriptionFieldCategory.RISK.value: "_risk_field",
        RiskEventSubscriptionFieldCategory.STRATEGY.value: "_strategy_field",
        RiskEventSubscriptionFieldCategory.STRATEGY_TAG.value: "_tag_field",
    }

    #: 字段类别在文档/前端展示时的中文说明
    CATEGORY_DISPLAY_NAMES: ClassVar[dict[str, str]] = {
        RiskEventSubscriptionFieldCategory.EVENT.value: str(RiskEventSubscriptionFieldCategory.EVENT.label),
        RiskEventSubscriptionFieldCategory.RISK.value: str(RiskEventSubscriptionFieldCategory.RISK.label),
        RiskEventSubscriptionFieldCategory.STRATEGY.value: str(RiskEventSubscriptionFieldCategory.STRATEGY.label),
        RiskEventSubscriptionFieldCategory.STRATEGY_TAG.value: str(
            RiskEventSubscriptionFieldCategory.STRATEGY_TAG.label
        ),
    }

    def _build_inner_select_fields(self) -> list[Field]:
        """
        构造订阅响应需要的字段列表，覆盖事件、风险、策略与标签聚合结果。
        """
        fields: list[Field] = []
        for config in self.INNER_FIELD_CONFIG:
            builder_name = self.CATEGORY_FIELD_BUILDERS[config.category.value]
            builder = getattr(self, builder_name)
            fields.append(builder(config.name, config.field_type, config.normalized_display_name))
        return fields

    @classmethod
    def get_field_metadata(cls) -> list[dict]:
        """
        返回字段元数据列表，供文档、Admin、API 复用。
        """
        metadata: list[dict] = []
        for config in cls.INNER_FIELD_CONFIG:
            category_value = config.category.value
            display = str(config.normalized_display_name)
            category_display = str(cls.CATEGORY_DISPLAY_NAMES.get(category_value, category_value))
            default_type = config.normalized_return_type
            default_type_value = default_type.value
            metadata.append(
                {
                    "name": display,
                    "raw_name": display,
                    "source_field": config.name,
                    "category": category_value,
                    "category_display": category_display,
                    "field_type": config.field_type.value,
                    "label": f"{display} ({category_display})",
                    "supports_drill": config.supports_drill,
                    "drill_examples": config.drill_examples,
                    "default_return_type": default_type_value,
                }
            )
        return metadata

    def _build_outer_select_fields(self) -> list[Field]:
        """
        将内层查询输出的列映射为外层 `t` 表字段，方便外层追加筛选。
        """
        return [
            Field(
                table=self.OUTER_ALIAS,
                raw_name=field.display_name,
                display_name=field.display_name,
                field_type=field.field_type,
            )
            for field in self._inner_select_fields
        ]

    def _build_join_tables(self) -> list[JoinTable]:
        """
        生成固定拓扑的 JOIN 关系，确保事件与风险、策略、标签在 SQL 中关联。
        """
        return [
            JoinTable(
                join_type=JoinType.INNER_JOIN,
                left_table=self._event_table,
                right_table=self._risk_table,
                link_fields=[
                    LinkField(left_field="strategy_id", right_field="strategy_id"),
                    LinkField(left_field="raw_event_id", right_field="raw_event_id"),
                ],
            ),
            JoinTable(
                join_type=JoinType.INNER_JOIN,
                left_table=self._event_table,
                right_table=self._strategy_table,
                link_fields=[LinkField(left_field="strategy_id", right_field="strategy_id")],
            ),
            JoinTable(
                join_type=JoinType.LEFT_JOIN,
                left_table=self._strategy_table,
                right_table=self._strategy_tag_table,
                link_fields=[LinkField(left_field="strategy_id", right_field="strategy_id")],
            ),
        ]

    def _build_strategy_tag_subquery(self) -> str:
        """
        构造策略标签的聚合子查询，返回 strategy_id -> tag_ids_json。
        """
        table_name = self._table_names["strategy_tag"]
        tag_table = BkBaseTable(table_name)
        group_concat = GroupConcat(Cast(tag_table.tag_id, "STRING"))
        concat = Concat(ValueWrapper("["), group_concat, ValueWrapper("]")).as_("tag_ids_json")
        query = (
            BKBaseQueryBuilder().from_(tag_table).select(tag_table.strategy_id, concat).groupby(tag_table.strategy_id)
        )
        return f"({query.get_sql()})"

    def _load_table_names(self) -> Dict[str, str]:
        """
        加载各类 BKBase 结果表名称，并统一追加 Doris 存储后缀。
        """
        names = {}
        for alias, config_key in self.TABLE_CONFIG_MAP.items():
            names[alias] = self._apply_storage_suffix(self._get_table_name(config_key))
        return names

    def _get_table_name(self, config_key: str) -> str:
        """
        读取命名空间下配置的 BKBase 表名，缺失配置则报错提醒显式配置。
        """
        return GlobalMetaConfig.get(
            config_key=config_key,
            config_level=ConfigLevelChoices.NAMESPACE.value,
            instance_key=self.namespace,
            default=None,
        )

    @classmethod
    def _apply_storage_suffix(cls, table_name: str) -> str:
        """
        统一给 BKBase 表追加 Doris 后缀，保证 SQL 查询落在 doris 存储。
        """
        cleaned = (table_name or "").strip()
        if not cleaned:
            return cleaned
        if cleaned.endswith(f".{cls.STORAGE_SUFFIX}"):
            return cleaned
        return f"{cleaned}.{cls.STORAGE_SUFFIX}"

    def _build_inner_query(self) -> str:
        """
        构造包含基础 JOIN + 时间筛选的子查询 SQL。
        """
        config = SqlConfig(
            select_fields=self._inner_select_fields,
            from_table=self._event_table,
            join_tables=self._join_tables,
            where=self._time_condition,
        )
        sql = str(self._generator.generate(config))
        return f"({sql})"

    def _normalize_subscription_condition(self) -> Optional[WhereCondition]:
        """
        将订阅条件中的表别名统一映射到外层 `t`，并根据展示名同步字段 raw_name。

        例如：`JSON_CONTAINS(st.tag_ids_json,'1')` 会被重写成 `JSON_CONTAINS(t.strategy_tag_ids,'1')`，
        方便外层 WHERE 直接引用最终的 select 别名。
        """
        if not self.subscription_condition:
            return None
        condition = self.subscription_condition.model_copy(deep=True)
        self._rewrite_condition_alias(condition)
        return condition

    def _rewrite_condition_alias(self, condition: WhereCondition) -> None:
        """
        递归遍历条件，将 Field.table 改写为 `t`，并确保 raw_name 与展示名保持一致。
        """
        if condition.condition:
            condition.condition.field.table = self.OUTER_ALIAS
            display = condition.condition.field.display_name or condition.condition.field.raw_name
            condition.condition.field.raw_name = display
        for child in condition.conditions:
            self._rewrite_condition_alias(child)

    def _build_field(
        self,
        table_alias: str,
        name: str,
        field_type: FieldType,
        display_name: Optional[str] = None,
    ) -> Field:
        """
        通用字段构造器，供各别名包装方法复用。
        """
        return Field(
            table=table_alias,
            raw_name=name,
            display_name=display_name or name,
            field_type=field_type,
        )

    def _event_field(self, name: str, field_type: FieldType, display_name: Optional[str] = None) -> Field:
        """构造事件表字段。"""
        return self._build_field(self.EVENT_ALIAS, name, field_type, display_name)

    def _risk_field(self, name: str, field_type: FieldType, display_name: Optional[str] = None) -> Field:
        """构造风险表字段。"""
        return self._build_field(self.RISK_ALIAS, name, field_type, display_name)

    def _strategy_field(self, name: str, field_type: FieldType, display_name: Optional[str] = None) -> Field:
        """构造策略表字段。"""
        return self._build_field(self.STRATEGY_ALIAS, name, field_type, display_name)

    def _tag_field(self, name: str, field_type: FieldType, display_name: Optional[str] = None) -> Field:
        """构造标签子查询字段。"""
        return self._build_field(self.STRATEGY_TAG_ALIAS, name, field_type, display_name)

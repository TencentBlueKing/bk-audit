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
"""
import json
import operator
from functools import reduce
from typing import Dict, List, Optional, Type, Union

from pypika import Table
from pypika import terms as pypika_terms
from pypika.functions import Cast, Count
from pypika.queries import QueryBuilder
from pypika.terms import BasicCriterion, EmptyCriterion, Function, Term, ValueWrapper

from core.sql.builder.builder import BkBaseTable
from core.sql.builder.functions import GetJsonObject
from core.sql.builder.terms import DorisJsonTypeExtractFunction, PypikaField
from core.sql.builder.utils import get_function, operate
from core.sql.constants import AggregateType, FieldType, FilterConnector
from core.sql.exceptions import (
    FilterValueError,
    InvalidAggregateTypeError,
    InvalidRuleConfigError,
    MissingFromOrJoinError,
    TableNotRegisteredError,
    UnsupportedJoinTypeError,
)
from core.sql.model import Condition, Field, HavingCondition, SqlConfig
from core.sql.model import Table as SqlTable
from core.sql.model import WhereCondition


class SQLGenerator:
    """SQL 生成器"""

    table_cls = Table
    field_type_cls = PypikaField
    table_map: Dict[str, Table]
    config: SqlConfig = None
    drill_function = GetJsonObject

    def __init__(
        self,
        query_builder: QueryBuilder,
        table_cls: Type[Table] = None,
        field_type_cls: Type[PypikaField] = None,
        drill_function: Type[Function] = None,
    ):
        """
        初始化生成器
        :param query_builder: PyPika 的 QueryBuilder 对象
        :param table_cls: 自定义的 Table 类
        :param field_type_cls: 自定义的字段类型类
        """
        self.query_builder = query_builder
        self.table_cls = table_cls or self.table_cls
        self.field_type_cls = field_type_cls or self.field_type_cls
        self.drill_function = drill_function or self.drill_function

    def _register_tables(self):
        """注册所有有效的表名"""
        register_tables = {}

        # 添加主表到注册表
        if self.config.from_table:
            alias = self.config.from_table.alias or self.config.from_table.table_name
            register_tables[alias] = self.config.from_table

        # 添加连接表到注册表
        for join_table in self.config.join_tables or []:
            for table in [join_table.left_table, join_table.right_table]:
                alias = table.alias or table.table_name
                register_tables[alias] = table

        # 更新 table_map 映射
        self.table_map.update(
            {alias: self.table_cls(table.table_name).as_(alias) for alias, table in register_tables.items()}
        )

    def _get_table(self, table: Union[str, SqlTable]) -> Table:
        """根据表名获取 Table 对象"""
        if isinstance(table, SqlTable):
            table = table.alias or table.table_name
        if table not in self.table_map:
            raise TableNotRegisteredError(table)
        return self.table_map[table]

    def _get_pypika_field(self, field: Field) -> PypikaField:
        """根据 Field 获取 PyPika 字段"""
        table = self._get_table(field.table)
        pypika_field = self.field_type_cls.get_field(table, field)
        # 若存在下钻字段
        if field.keys:
            pypika_field = self.drill_function(
                pypika_field,
                "$.{}".format(".".join([f"[{json.dumps(k)}]" for k in field.keys])),
                str(field.field_type).upper(),
            )
            if hasattr(pypika_field, 'cast_to'):
                pypika_field = pypika_field.cast_to()
        return pypika_field

    def generate(self, config: SqlConfig) -> QueryBuilder:
        """根据配置构建 SQL 查询"""
        self.config = config
        self.table_map = {}
        self._register_tables()
        query = self.query_builder
        query = self._build_from(query)
        query = self._build_select(query)
        query = self._build_where(query)
        query = self._build_group_by(query)
        query = self._build_having(query)
        query = self._build_order_by(query)
        query = self._build_pagination(query)
        return query

    def generate_rule_mode(self, config: SqlConfig) -> QueryBuilder:
        """
        多规则：构建 L1 条件聚合层。

        表注册：_register_tables
        from子句：_build_from
        select子句：_build_rule_mode_select
            - 维度列：策略级 select 的非聚合字段（与单规则一致）
            - 聚合列：每个聚合字段 × 每条规则展开为 AGG(CASE WHEN w_i THEN f END) AS {alias}__r{i}
            - 守卫列：每条规则生成；分组场景 COUNT(CASE WHEN w_i THEN 1 END)（零匹配稳定为 0），
        WHERE子句：_build_rule_mode_where
            OR(各规则 where) AND config.where（config.where 为 system_ids 等策略级条件；
        """
        if not config.select_fields:
            # L2 要求显式列清单、守卫/聚合展开均依赖 select 字段，空 select 无法构建
            raise InvalidRuleConfigError("策略级 select 至少需要配置一个输出字段")
        if not config.rules:
            raise InvalidRuleConfigError("至少需要配置一条发现规则")
        self.config = config
        self.table_map = {}
        self._register_tables()
        # 预计算各规则的 where criterion，L1 select / L1 where / L2 hit-case 一致消费
        self.rule_criterions: Dict[int, Term] = {}
        for idx, rule in enumerate(self.config.rules, start=1):
            criterion = self._apply_filter_conditions(rule.where) if rule.where else None
            if criterion is None or isinstance(criterion, EmptyCriterion):
                raise InvalidRuleConfigError(f"规则 {rule.rule_id} 缺少 where 过滤条件（规则 where 必填）")
            self.rule_criterions[idx] = criterion
        # 行级判定：select 无聚合字段且未显式指定 group_by -> 行级模式守卫，逐行标记0/1
        self.rule_mode_row_level = not any(f.aggregate for f in self.config.select_fields) and not self.config.group_by
        self._rule_mode_ready = True
        query = self.query_builder
        query = self._build_from(query)
        query = self._build_rule_mode_select(query)
        query = self._build_rule_mode_where(query)
        query = self._build_group_by(query)
        query = self._build_order_by(query)
        query = self._build_pagination(query)
        return query

    RULE_AGG_SUFFIX = "__r{}"
    RULE_GUARD_PREFIX = "wguard__r{}"
    RULE_HIT_FIELD = "strategy_rule_id"

    def _rule_agg_alias(self, display_name: str, rule_idx: int) -> str:
        """规则 i 的聚合列别名"""
        return f"{display_name}{self.RULE_AGG_SUFFIX.format(rule_idx)}"

    def _rule_guard_alias(self, rule_idx: int) -> str:
        """规则 i 的守卫列别名"""
        return self.RULE_GUARD_PREFIX.format(rule_idx)

    def get_rule_mode_output_columns(self) -> List[str]:
        """
        L1 全部输出列名（维度列 + 每聚合字段×每规则的展开列 + 守卫列），按生成顺序。供 L2 以显式列引用构建 SELECT
        """
        if not getattr(self, "_rule_mode_ready", False):
            raise ValueError("get_rule_mode_output_columns must be called after generate_rule_mode")
        columns = []
        for field in self.config.select_fields or []:
            if not field.aggregate:
                columns.append(field.display_name)
                continue
            for idx in range(1, len(self.config.rules) + 1):
                columns.append(self._rule_agg_alias(field.display_name, idx))
        for idx in range(1, len(self.config.rules) + 1):
            columns.append(self._rule_guard_alias(idx))
        return columns

    @staticmethod
    def aggregate_field_identity(field: Field) -> tuple:
        """
        聚合字段身份：(table, raw_name, aggregate, keys)。
        display_name 由前端拼接（如 事件ID_COUNT(event_id)），select 与 having 两处可能不一致，
        不作为关联锚点；身份元组与校验层 _check_rules 的 aggregate_identities 口径一致。
        """
        return (field.table, field.raw_name, field.aggregate, tuple(field.keys or []))

    def _build_rule_mode_select(self, query: QueryBuilder) -> QueryBuilder:
        """多规则模式 SELECT：非聚合列原样 + 聚合列按规则展开（全 CASE WHEN）+ 守卫列（每规则一条）"""
        self.rule_alias_map: Dict[tuple, str] = {}
        # config.select_fields: 用户在页面选择的select字段
        for field in self.config.select_fields:
            # 非聚合列
            if not field.aggregate:
                query = query.select(self._get_pypika_field(field).as_(field.display_name))
                continue
            # 聚合列按规则展开（规则数 * 聚合字段数）
            pypika_field = self._get_pypika_field(field)
            for idx in range(1, len(self.config.rules) + 1):
                alias = self._rule_agg_alias(field.display_name, idx)
                self.rule_alias_map[(self.aggregate_field_identity(field), idx)] = alias
                # CASE 无 ELSE：且不匹配 -> NULL -> 聚合忽略（COUNT/SUM 跳过 NULL）
                conditional = pypika_terms.Case().when(self.rule_criterions[idx], pypika_field)
                query = query.select(self._build_aggregate_term(field, conditional).as_(alias))
        # 守卫列：确保只有真实出现过该规则数据的组才能命中；否则像 COUNT(xx) < 2 这类低向阈值，会在“组存在但零匹配”（COUNT=0）时凭空满足条件而出单。
        for idx in range(1, len(self.config.rules) + 1):
            criterion = self.rule_criterions[idx]
            if self.rule_mode_row_level:
                guard = pypika_terms.Case().when(criterion, 1).else_(0)
            else:
                guard = Count(pypika_terms.Case().when(criterion, 1))
            query = query.select(guard.as_(self._rule_guard_alias(idx)))
        return query

    def _build_rule_mode_where(self, query: QueryBuilder) -> QueryBuilder:
        """
        多规则 WHERE：OR(各规则 where)  AND 策略级条件（system_ids 等）。
        """
        rules_where = reduce(operator.or_, self.rule_criterions.values())
        query = query.where(rules_where)
        if self.config.where:
            strategy_criterion = self._apply_filter_conditions(self.config.where)
            if strategy_criterion and not isinstance(strategy_criterion, EmptyCriterion):
                query = query.where(strategy_criterion)
        return query

    def build_rule_hit_case(self) -> Term:
        """
        构建多规则的 L2 命中表达式（根据L1中的守卫列和各规则聚合列结果得到strategy_rule_id列）。
        为每个规则生成一个when分支
        CASE
            WHEN wguard__r1 > 0 [AND <having'_1 按 L1 列引用求值>] THEN rule_id_1
            WHEN ... THEN ...
        END

        """
        if not getattr(self, "_rule_mode_ready", False):
            raise ValueError("build_rule_hit_case must be called after generate_rule_mode")
        case = pypika_terms.Case()
        for idx, rule in enumerate(self.config.rules, start=1):
            branch = pypika_terms.Field(self._rule_guard_alias(idx)) > 0
            if rule.having is not None:
                having_criterion = self._apply_filter_conditions(
                    rule.having, leaf_handler=lambda c, _idx=idx: self._handle_rule_having_condition(c, _idx)
                )
                if having_criterion is not None and not isinstance(having_criterion, EmptyCriterion):
                    branch = branch & having_criterion
            case = case.when(branch, ValueWrapper(rule.rule_id))
        return case

    def _handle_rule_having_condition(self, condition: Condition, rule_idx: int) -> BasicCriterion:
        """
        L2 列引用模式的 having 叶子条件：引用 L1 输出列（聚合字段 -> {alias}__r{i}；维度字段 -> md5 别名列）。
        """
        field = condition.field
        if field.aggregate:
            # 聚合字段：按身份元组查找 rule_alias_map（display_name 前端两处拼接可能不一致）
            alias = self.rule_alias_map.get((self.aggregate_field_identity(field), rule_idx))
            if alias is None:
                raise InvalidRuleConfigError(f"规则 having 引用的聚合字段 {field.display_name} 不在策略级 select 中")
            pypika_field = pypika_terms.Field(alias)
            filter_type = (field.aggregate.result_data_type or field.field_type).python_type
        else:
            # 维度字段：L1 输出列别名（display_name 已由上层映射为 md5 别名）
            dimension_columns = {f.display_name for f in self.config.select_fields if not f.aggregate}
            if field.display_name not in dimension_columns:
                raise InvalidRuleConfigError(f"规则 having 引用的维度字段 {field.display_name} 不在策略级 select 的维度列中")
            pypika_field = pypika_terms.Field(field.display_name)
            filter_type = field.field_type.python_type
        try:
            return operate(
                condition.operator,
                pypika_field,
                filter_type(condition.filter) if condition.filter not in (None, "") else None,
                [filter_type(f) for f in condition.filters],
            )
        except ValueError:
            raise FilterValueError(
                condition.field.raw_name, condition.filter or condition.filters, filter_type, condition.field.aggregate
            )

    def _build_from(self, query: QueryBuilder) -> QueryBuilder:
        """添加 FROM 子句"""
        if not (self.config.from_table or self.config.join_tables):
            raise MissingFromOrJoinError()
        from_table = self.config.join_tables[0].left_table if self.config.join_tables else self.config.from_table
        query = query.from_(self._get_table(from_table))
        if self.config.join_tables:
            query = self._build_join(self.config.from_table, query)
        return query

    def _build_join(self, from_table: Optional[str], query: QueryBuilder) -> QueryBuilder:
        """添加 JOIN 子句"""
        for join_table in self.config.join_tables:
            left_table = self._get_table(join_table.left_table)
            if not from_table:
                from_table = left_table
                query = query.from_(from_table)
            right_table = self._get_table(join_table.right_table)
            try:
                join_function = getattr(query, join_table.join_type.value.lower())
            except AttributeError:
                raise UnsupportedJoinTypeError(join_table.join_type)
            if not join_function:
                raise UnsupportedJoinTypeError(join_table.join_type)
            criterion = EmptyCriterion()
            for link_field in join_table.link_fields:
                criterion &= left_table.field(link_field.left_field) == right_table.field(link_field.right_field)
            query = join_function(right_table).on(criterion)
        return query

    def _build_select(self, query: QueryBuilder) -> QueryBuilder:
        """添加 SELECT 子句"""
        # 如果 select_fields 为空，使用 SELECT *
        if not self.config.select_fields:
            return query.select("*")

        for field in self.config.select_fields:
            if field.aggregate:
                # 如果存在聚合函数，使用 fn 调用
                pypika_field = self._build_aggregate(field)
            else:
                pypika_field = self._get_pypika_field(field)

            pypika_field = pypika_field.as_(field.display_name)
            query = query.select(pypika_field)
        return query

    def _build_aggregate(self, field: Field) -> PypikaField:
        # 如果存在聚合函数，使用 fn 调用
        pypika_field = self._get_pypika_field(field)
        aggregate_func = get_function(field.aggregate)
        if not aggregate_func:
            raise InvalidAggregateTypeError(field.aggregate)
        pypika_field = aggregate_func(pypika_field)
        return pypika_field

    def _build_aggregate_term(self, field: Field, term: Term) -> Term:
        """用于聚合函数嵌套case when（条件聚合复用 get_function 映射）"""
        aggregate_func = get_function(field.aggregate)
        if not aggregate_func:
            raise InvalidAggregateTypeError(field.aggregate)
        return aggregate_func(term)

    def _build_where(self, query: QueryBuilder) -> QueryBuilder:
        """添加 WHERE 子句"""
        if self.config.where:
            criterion = self._apply_filter_conditions(self.config.where)
            if criterion:
                query = query.where(criterion)
        return query

    def _build_having(self, query: QueryBuilder) -> QueryBuilder:
        """添加 HAVING 子句"""
        if self.config.having:
            criterion = self._apply_filter_conditions(self.config.having)
            if criterion:
                query = query.having(criterion)
        return query

    def handle_condition(self, condition: Condition) -> BasicCriterion:
        """处理条件"""
        if condition.field.aggregate:
            # 如果条件字段是聚合函数，则使用聚合函数处理
            field = self._build_aggregate(condition.field)
            # 采用聚合函数规定的类型 or 字段本身类型
            filter_type = (condition.field.aggregate.result_data_type or condition.field.field_type).python_type
        else:
            # 否则，使用普通字段处理
            field = self._get_pypika_field(condition.field)
            filter_type = condition.field.field_type.python_type
        operator = condition.operator
        try:
            return operate(
                operator,
                field,
                # 显式判空：filter=0（数值零值）是合法筛选值
                filter_type(condition.filter) if condition.filter not in (None, "") else None,
                [filter_type(f) for f in condition.filters],
            )
        except ValueError:
            raise FilterValueError(
                condition.field.raw_name, condition.filter or condition.filters, filter_type, condition.field.aggregate
            )

    def _apply_filter_conditions(
        self, condition: Union[WhereCondition, HavingCondition], leaf_handler=None
    ) -> BasicCriterion:
        """递归构建 WHERE/HAVING 子句

        :param leaf_handler: 叶子条件（Condition）处理器，默认 handle_condition；
            多规则 L2 列引用模式传入 _handle_rule_having_condition（聚合字段解析为 L1 输出列）
        """
        leaf_handler = leaf_handler or self.handle_condition
        if condition.condition:
            return leaf_handler(condition.condition)

        if condition.conditions:
            sub_criterions = []
            for sub_condition in condition.conditions:
                criterion = self._apply_filter_conditions(sub_condition, leaf_handler)
                if not isinstance(criterion, EmptyCriterion):
                    sub_criterions.append(criterion)

            if not sub_criterions:
                return EmptyCriterion()

            op = operator.and_ if condition.connector == FilterConnector.AND else operator.or_
            return reduce(op, sub_criterions)

        return EmptyCriterion()

    def _build_group_by(self, query: QueryBuilder) -> QueryBuilder:
        """添加 GROUP BY 子句"""
        if self.config.group_by:
            # 如果明确指定了 group_by 字段，则使用它们
            for field in self.config.group_by:
                query = query.groupby(self._get_pypika_field(field))
        else:
            # 检查是否存在聚合字段
            has_aggregate = any(field.aggregate for field in self.config.select_fields)
            if not has_aggregate:
                return query
            # 自动推导非聚合字段进行分组
            for field in self.config.select_fields:
                if not field.aggregate:
                    query = query.groupby(self._get_pypika_field(field))
        return query

    def _build_order_by(self, query: QueryBuilder) -> QueryBuilder:
        """添加 ORDER BY 子句"""
        if self.config.order_by:
            for order in self.config.order_by:
                pypika_field = self._get_pypika_field(order.field)
                query = query.orderby(pypika_field, order=order.order)
        return query

    def _build_pagination(self, query: QueryBuilder) -> QueryBuilder:
        """添加 LIMIT 和 OFFSET 子句"""
        if self.config.pagination:
            if self.config.pagination.limit:
                query = query.limit(self.config.pagination.limit)
            if self.config.pagination.offset:
                query = query.offset(self.config.pagination.offset)
        return query

    def generate_count(self, config: SqlConfig) -> QueryBuilder:
        """
        生成 COUNT 查询

        与 generate() 类似，但只返回 COUNT(*) 而不是实际数据。
        不包含 SELECT、GROUP BY、HAVING、ORDER BY、PAGINATION。
        """
        self.config = config
        self.table_map = {}
        self._register_tables()
        query = self.query_builder
        query = self._build_from(query)
        query = self._build_where(query)
        query = query.select(Count("*").as_("count")).limit(1)
        return query


class BkBaseComputeSqlGenerator(SQLGenerator):
    """BK-BASE 计算模块的 SQL 生成器"""

    table_cls = BkBaseTable


class BkbaseDorisSqlGenerator(BkBaseComputeSqlGenerator):
    """
    Bkbase Doris SQL 生成器；支持 Doris JSON 字段下钻。
    """

    # GROUP_CONCAT 要求参数是 STRING 类型，这些聚合类型不做 CAST
    _STRING_ONLY_AGGREGATES = {AggregateType.LIST.value, AggregateType.LIST_DISTINCT.value}

    def _get_pypika_field(self, field: Field):
        if not field.keys:
            return super()._get_pypika_field(field)

        table = self._get_table(field.table)
        base_field = self.field_type_cls.get_field(table, field)
        json_value = DorisJsonTypeExtractFunction(base_field, field.keys, FieldType.STRING)

        # GROUP_CONCAT (LIST/LIST_DISTINCT) 要求参数是 STRING，跳过 CAST
        if field.aggregate in self._STRING_ONLY_AGGREGATES:
            return json_value

        target_type = field.field_type or FieldType.STRING
        if target_type in (FieldType.STRING, FieldType.TEXT):
            return json_value
        return Cast(json_value, target_type.query_data_type)

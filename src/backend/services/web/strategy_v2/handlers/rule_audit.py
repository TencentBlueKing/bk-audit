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
from gettext import gettext
from typing import Dict, List, Optional

from bk_resource.utils.common_utils import get_md5
from django.conf import settings
from django.shortcuts import get_object_or_404
from pydantic import BaseModel
from pypika import functions as fn
from pypika import terms as pypika_terms
from pypika.terms import Function, Term, ValueWrapper

from apps.meta.utils.fields import SYSTEM_ID
from core.sql.builder.builder import BKBaseQueryBuilder
from core.sql.builder.functions import ConcatWs, GetJsonObject, JsonValue
from core.sql.builder.generator import BkBaseComputeSqlGenerator
from core.sql.constants import FilterConnector, Operator
from core.sql.model import (
    Condition,
    Field,
    HavingCondition,
    JoinTable,
    LinkField,
    RuleFilterConfig,
    SqlConfig,
    Table,
    WhereCondition,
)
from services.web.analyze.constants import FlowSQLNodeType
from services.web.risk.constants import EventMappingFields
from services.web.strategy_v2.constants import LinkTableTableType, RuleAuditConfigType
from services.web.strategy_v2.exceptions import (
    LinkTableConfigError,
    RuleAuditSqlGeneratorError,
)
from services.web.strategy_v2.models import LinkTable, Strategy, StrategyRule


class UdfBuildOriginData(Function):
    """ """

    udf_func = settings.BKBASE_UDF_BUILD_ORIGIN_DATA_FUNC

    def __init__(self, keys: Term, vals: Term):
        super().__init__(self.udf_func, keys, vals)


def make_json_expr(fields: Dict[str, Term]) -> Term:
    """
    使用 UDF 函数和分隔符构造 JSON 字段。

    Returns:
        Term: 表示最终的 JSON 表达式，作为 PyPika 的 Term 对象。
    """

    separator = settings.BKBASE_BUILD_ORIGIN_DATA_SEPERATOR

    field_keys = fields.keys()
    field_values = []

    for field in fields.values():
        field_values.extend([fn.Cast(field, "string"), separator])

    # 1. 拼接 key 部分
    keys_str = separator.join(field_keys)

    # 2. 拼接 value 部分
    value_str = ConcatWs("", *field_values[: len(field_values) - 1])

    # 3. 返回 UDF 调用表达式
    return UdfBuildOriginData(keys_str, value_str)


class FieldMap(BaseModel):
    """
    字段映射,来源字段和固定值至少设置一个,优先级：固定值>来源字段
    """

    source_field: Optional[str] = None  # 来源字段的display_name
    target_value: Optional[str] = None  # 固定值


class RuleAuditSQLBuilder:
    """
    规则审计 SQL 生成器
    """

    def __init__(self, strategy: Strategy):
        self.strategy = strategy
        self.query_builder = BKBaseQueryBuilder()
        self.display2tmp_name_map = {}

    def build_system_ids_condition(self, table_name: str, system_ids: list) -> WhereCondition:
        """
        根据给定的表 rt_id 及 system_ids 列表，构建一个 AND 条件，用于拼接到最终的 WHERE 中。
        """
        system_condition = Condition(
            field=Field(
                table=table_name,
                raw_name=SYSTEM_ID.field_name,
                display_name=SYSTEM_ID.alias_name,
                field_type=SYSTEM_ID.field_type,
            ),
            operator=Operator.INCLUDE,
            filters=system_ids,
        )
        return WhereCondition(connector=FilterConnector.AND, condition=system_condition)

    def build_single_table_config(self, data_source: dict) -> (Table, list, dict):
        """
        处理单表场景，返回:
         - from_table: 主表
         - join_tables: 空列表 (单表无 join)
         - tables_with_system_ids: {display_name: [system_ids]}
        """
        from_table = data_source["rt_id"]
        display_name = data_source.get("display_name", from_table)
        system_ids = data_source.get("system_ids", [])
        tables_with_system_ids = {display_name: system_ids}
        return Table(table_name=from_table, alias=display_name), [], tables_with_system_ids

    def build_link_table_config(self, data_source: dict) -> (Table, list, dict):
        """
        处理联表场景，从 link_table 配置中构建:
         - from_table: 主表
         - join_tables: List[JoinTable]
         - tables_with_system_ids: {rt_id: [system_ids]}
        """
        link_table_uid = data_source["link_table"]["uid"]
        link_table_version = data_source["link_table"]["version"]

        link_table_obj = get_object_or_404(LinkTable, uid=link_table_uid, version=link_table_version)
        link_config = link_table_obj.config
        links = link_config.get("links", [])

        if not links:
            raise LinkTableConfigError(data=link_config)

        # 确定主表 (from_table)
        first_link = links[0]
        from_table = first_link["left_table"]
        _from_table = Table(table_name=from_table["rt_id"], alias=from_table.get("display_name", from_table["rt_id"]))
        join_tables = []
        tables_with_system_ids = {}

        for lk in links:
            left_table = lk["left_table"]
            _left_table = Table(
                table_name=left_table["rt_id"],
                alias=left_table.get("display_name", left_table["rt_id"]),
            )
            right_table = lk["right_table"]
            _right_table = Table(
                table_name=right_table["rt_id"],
                alias=right_table.get("display_name", right_table["rt_id"]),
            )

            # 如果 left_table 或 right_table 是 EVENT_LOG，则将它们的 system_ids 收集起来
            if left_table["table_type"] == LinkTableTableType.EVENT_LOG:
                tables_with_system_ids[_left_table.alias] = left_table.get("system_ids", [])
            if right_table["table_type"] == LinkTableTableType.EVENT_LOG:
                tables_with_system_ids[_right_table.alias] = right_table.get("system_ids", [])

            # link_fields
            link_fields_list = [
                LinkField(left_field=lf["left_field"]["field_name"], right_field=lf["right_field"]["field_name"])
                for lf in lk["link_fields"]
            ]

            # 构建 JoinTable
            join_tables.append(
                JoinTable(
                    join_type=lk["join_type"],
                    link_fields=link_fields_list,
                    left_table=_left_table,
                    right_table=_right_table,
                )
            )

        return _from_table, join_tables, tables_with_system_ids

    def format(self, config_json: dict, rules: List[RuleFilterConfig]) -> SqlConfig:
        """
        将前端 JSON 配置转换为可供 SQLGenerator 使用的 SqlConfig。

        :param config_json: 策略级配置（data_source/select/system_ids 等）
        :param rules: 发现规则过滤配置（where/having 属于规则级，不读 config_json）
        """
        config_type = config_json["config_type"]
        data_source = config_json["data_source"]

        # Step A. 解析 select_fields
        select_fields = config_json.get("select", [])

        # Step B. 根据 config_type 构建 from_table, join_tables, tables_with_system_ids
        if config_type == RuleAuditConfigType.LINK_TABLE:
            from_table, join_tables, tables_with_system_ids = self.build_link_table_config(data_source)
        else:
            from_table, join_tables, tables_with_system_ids = self.build_single_table_config(data_source)

        # Step C. 构建策略级 where 条件（这里仅包含configs.data_source.system_ids,各规则的where和having条件在rules中）
        where_conditions_to_merge = []
        for table_name, system_ids in tables_with_system_ids.items():
            if not system_ids:
                continue
            where_conditions_to_merge.append(self.build_system_ids_condition(table_name, system_ids))

        final_where = None
        if where_conditions_to_merge:
            final_where = WhereCondition(connector=FilterConnector.AND, conditions=where_conditions_to_merge)

        return SqlConfig(
            select_fields=select_fields,
            from_table=from_table,
            join_tables=join_tables,
            where=final_where,
            rules=rules,
        )

    def format_alias(self, alias: str) -> str:
        r"""
        格式化别名为符合 bkbase 要求的字符串 [[A-Za-z_]\w*]
        """

        return f"u_{get_md5(alias)}"

    def _get_ordered_rules(self) -> List[StrategyRule]:
        """
        获取按匹配优先级排序的发现规则（首匹配语义：rule_order 顺序 = CASE 分支顺序）。
        """
        rules = list(StrategyRule.objects.filter(strategy=self.strategy, is_deleted=False).order_by())
        if not rules:
            return []
        rule_order = self.strategy.rule_order or []
        if rule_order:
            order_index = {rule_id: idx for idx, rule_id in enumerate(rule_order)}
            rules.sort(key=lambda r: order_index.get(r.rule_id, len(rule_order)))
        return rules

    def _build_rule_filter_configs(self, rules: List[StrategyRule]) -> List[RuleFilterConfig]:
        """
        StrategyRule（ORM）-> RuleFilterConfig（SQL 构造用）
        conditions 结构: {"where": xxx, "having": x}。
        """
        configs = []
        for rule in rules:
            conditions = rule.conditions or {}
            where_json = conditions.get("where")
            having_json = conditions.get("having")
            if not where_json:
                # 规则 where 必填（无兜底规则概念），缺失即数据异常
                raise RuleAuditSqlGeneratorError(
                    gettext("strategy %s rule %s missing where conditions" % (self.strategy.strategy_id, rule.rule_id))
                )
            configs.append(
                RuleFilterConfig(
                    rule_id=rule.rule_id,
                    where=WhereCondition(**where_json),
                    having=HavingCondition(**having_json) if having_json else None,
                )
            )
        return configs

    def build_sql(self) -> str:
        """
        将规则审计策略生成 sql
        field_mapping 中的 key 为 select 中的字段名，value 为 FieldMap 对象,用于映射字段
        """
        rules = self._get_ordered_rules()
        if not rules:
            raise RuleAuditSqlGeneratorError(
                gettext("strategy %s has no strategy rule" % self.strategy.strategy_id)
            )
        rule_configs = self._build_rule_filter_configs(rules)
        sql_config = self.format(self.strategy.configs, rules=rule_configs)
        return self._build_outer_sql(sql_config, rules=rule_configs)

    def _map_rules_having_fields(self, rules: List[RuleFilterConfig]) -> None:
        """
        用于把原有字段名跟md5别名映射，用于having在外层引用内层查询结果
        """
        alias_map = self.display2tmp_name_map

        def walk(node):
            if node.condition:
                original = node.condition.field.display_name
                if original in alias_map:
                    node.condition.field.display_name = alias_map[original]
            for sub in node.conditions:
                walk(sub)

        for rule in rules:
            if rule.having:
                walk(rule.having)

    def _build_outer_sql(self, sql_config: SqlConfig, rules: List[RuleFilterConfig]) -> str:
        """
            L1: generator.generate_rule_mode(config)  条件聚合层（核心）
            L2：_build_outer_sql  命中层   产出每行/每组命中了哪条规则
            L3：_build_outer_sql   事件映射层    产出 BKBase 事件流的最终字段
        """
        event_basic_field_configs: List[dict] = self.strategy.event_basic_field_configs
        field_mapping = {
            field["field_name"]: FieldMap(**field["map_config"])
            for field in event_basic_field_configs
            if field.get("map_config")
        }
        # 1. 生成子查询 (sub_table)
        for field in sql_config.select_fields:
            self.display2tmp_name_map[field.display_name] = self.format_alias(field.display_name)
        # 格式化别名
        for field in sql_config.select_fields:
            field.display_name = self.display2tmp_name_map[field.display_name]
        if self.strategy.sql_node_type == FlowSQLNodeType.REALTIME:
            drill_function = JsonValue
        else:
            drill_function = GetJsonObject
        # having 树聚合字段 display_name 同步替换为 md5 别名
        self._map_rules_having_fields(rules)
        # L1 条件聚合
        generator = BkBaseComputeSqlGenerator(query_builder=self.query_builder, drill_function=drill_function)
        l1_query = generator.generate_rule_mode(config=sql_config)
        # L2 命中层：显式引用 L1 全部输出列 + CASE ... END AS strategy_rule_id
        hit_case = generator.build_rule_hit_case().as_(generator.RULE_HIT_FIELD)
        l1_alias = l1_query.as_("t")
        l2_builder = BKBaseQueryBuilder().from_(l1_alias)
        for column in generator.get_rule_mode_output_columns():
            l2_builder = l2_builder.select(l1_alias.field(column))
        l2_builder = l2_builder.select(hit_case)
        sub_table = l2_builder.as_("sub_table")
        # 2. 构造 JSON_OBJECT(...) 参数
        display_names = self.display2tmp_name_map.keys()
        fields = []
        for field in sql_config.select_fields:
            if field.aggregate:
                fields.append(self._build_rule_value_case(generator, field, sub_table))
            else:
                fields.append(sub_table.field(field.display_name))
        json_obj_args = dict(zip(display_names, fields))
        # 3. 最外层 select 列表
        #    3.1 JSON_OBJECT(...) => event_data
        #    3.2 strategy_id => strategy_id
        #    3.3 strategy_rule_id => 命中规则标识
        #    3.4 其他字段 => 来自 field_mapping
        select_fields = [
            make_json_expr(json_obj_args).as_(EventMappingFields.EVENT_DATA.field_name),
            ValueWrapper(self.strategy.strategy_id, EventMappingFields.STRATEGY_ID.field_name),
            sub_table.field(generator.RULE_HIT_FIELD).as_(EventMappingFields.STRATEGY_RULE_ID.field_name),
        ]
        for display_name, map_config in field_mapping.items():
            if map_config.target_value:
                select_fields.append(ValueWrapper(map_config.target_value, display_name))
            elif map_config.source_field:
                if map_config.source_field not in self.display2tmp_name_map:
                    raise RuleAuditSqlGeneratorError(gettext("source_field %s not found" % map_config.source_field))
                # select_fields 的 display_name 已替换为 md5 别名，source_field 为前端原始名——先取 md5 再比对
                source_md5 = self.display2tmp_name_map[map_config.source_field]
                source_field = next(
                    (f for f in sql_config.select_fields if f.display_name == source_md5), None
                )
                if source_field is not None and source_field.aggregate:
                    # map_config 引用聚合字段：同样按命中规则取值
                    select_fields.append(
                        self._build_rule_value_case(
                            generator,
                            source_field,
                            sub_table,
                            alias=source_md5,
                            output_alias=display_name,
                        )
                    )
                    continue
                select_fields.append(
                    sub_table.field(self.display2tmp_name_map[map_config.source_field]).as_(display_name)
                )
        # 4. 构建最终查询: from sub_table select ...；过滤未命中（strategy_rule_id IS NULL）
        query = self.query_builder.from_(sub_table).select(*select_fields)
        query = query.where(sub_table.field(generator.RULE_HIT_FIELD).notnull())
        return str(query)

    def _build_rule_value_case(
        self,
        generator: BkBaseComputeSqlGenerator,
        field: Field,
        sub_table,
        alias: Optional[str] = None,
        output_alias: Optional[str] = None,
    ) -> Term:
        """
        聚合字段按命中规则取值：CASE strategy_rule_id WHEN r1 THEN u__r1 ... END。

        字段引用使用 md5 后的别名
        """
        alias = alias or field.display_name
        rule_hit_field = sub_table.field(generator.RULE_HIT_FIELD)
        case = pypika_terms.Case()
        for idx, rule in enumerate(generator.config.rules, start=1):
            rule_alias = generator.rule_alias_map.get((alias, idx))
            if rule_alias is None:
                # generator 对每个聚合 select 字段 × 每条规则都会注册别名，miss 即上游数据不一致
                raise RuleAuditSqlGeneratorError(
                    gettext("aggregate field %s rule %s column not found" % (alias, rule.rule_id))
                )
            case = case.when(rule_hit_field == rule.rule_id, sub_table.field(rule_alias))
        return case.as_(output_alias) if output_alias else case
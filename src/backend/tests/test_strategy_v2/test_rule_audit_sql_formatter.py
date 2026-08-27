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

from copy import deepcopy
from unittest.mock import MagicMock, patch

from services.web.analyze.constants import FlowDataSourceNodeType
from services.web.strategy_v2.constants import LinkTableTableType, RuleAuditConfigType
from services.web.strategy_v2.exceptions import LinkTableConfigError
from services.web.strategy_v2.handlers.rule_audit import RuleAuditSQLBuilder
from services.web.strategy_v2.models import Strategy, StrategyRule
from tests.base import TestCase


class TestRuleAuditSQLFormatter(TestCase):
    """
    测试 RuleAuditSQLFormatter 的 build_sql 方法, 只关注最终产出的 SQL
    """

    def setUp(self):
        self.patcher = patch(
            "services.web.strategy_v2.handlers.rule_audit.RuleAuditSQLBuilder.format_alias", side_effect=lambda x: x
        )
        self.mock_method = self.patcher.start()
        # 内存缓存已建规则：测试库连接池下同事务 create 后 filter 可能查不到（跨连接读未提交事务），
        # 不依赖查询复用，避免二次 create 撞 (strategy_id, rule_name) 唯一约束
        self._rule_cache = {}

    def tearDown(self):
        self.patcher.stop()

    def _get_or_create_rule(self, strategy: Strategy) -> StrategyRule:
        """获取或创建策略的发现规则，返回规则对象（同一 strategy_id 幂等）"""
        cached = self._rule_cache.get(strategy.strategy_id)
        if cached is not None:
            return cached
        existing = StrategyRule.objects.filter(strategy_id=strategy.strategy_id, is_deleted=False).first()
        if existing:
            self._rule_cache[strategy.strategy_id] = existing
            return existing
        configs = strategy.configs or {}
        data_source = configs.get("data_source") or {}
        config_type = configs.get("config_type")
        if config_type == "LinkTable":
            select_fields = configs.get("select") or []
            rt_id = select_fields[0].get("table") if select_fields else "default_table"
        else:
            rt_id = data_source.get("rt_id") or "default_table"
        rule = StrategyRule.objects.create(
            strategy_id=strategy.strategy_id,
            rule_name=f"rule_{strategy.strategy_id}",
            conditions={
                "where": {
                    "condition": {
                        "field": {
                            "table": rt_id,
                            "raw_name": "event_type",
                            "display_name": "event_type",
                            "field_type": "string",
                        },
                        "operator": "eq",
                        "filters": ["test"],
                    }
                },
                "having": None,
            },
        )
        self._rule_cache[strategy.strategy_id] = rule
        return rule

    def _build_and_assert_sql(self, strategy: Strategy, expected_sql: str, mock_link_table_obj=None):
        rule = self._get_or_create_rule(strategy)
        formatter = RuleAuditSQLBuilder(strategy)
        if mock_link_table_obj:
            with patch(
                "services.web.strategy_v2.handlers.rule_audit.get_object_or_404", return_value=mock_link_table_obj
            ):
                actual_sql = formatter.build_sql()
        else:
            actual_sql = formatter.build_sql()

        # 标准化 rule_id：将实际 rule_id 的全部出现形态替换为 1，消除自增差异
        # 形态：THEN <id> END（命中 CASE） / strategy_rule_id`=<id> THEN（L3 证据取值） / =<id> 之外的裸值不处理
        import re

        actual_normalized = re.sub(rf"THEN\s+{rule.rule_id}\s+END", "THEN 1 END", actual_sql)
        actual_normalized = re.sub(
            rf"`strategy_rule_id`={rule.rule_id}\s+THEN", "`strategy_rule_id`=1 THEN", actual_normalized
        )
        self.assertEqual(
            actual_normalized,
            expected_sql,
            f"\n生成的SQL 与预期不一致。\n实际:   {actual_sql}\n期望:   {expected_sql}",
        )

    def test_single_table_no_where_no_system_ids(self):
        """
        最基本的单表配置, 无where, 无system_ids, select中1列
        """
        config_json = {
            "config_type": RuleAuditConfigType.EVENT_LOG,
            "data_source": {
                "rt_id": "simple_rt",
            },
            "select": [
                {
                    "table": "simple_rt",
                    "raw_name": "fieldA",
                    "display_name": "字段A",
                    "field_type": "string",
                    "aggregate": None,
                }
            ],
            "where": None,  # 无where
        }
        event_basic_field_configs = []
        strategy = Strategy(strategy_id=200, configs=config_json, event_basic_field_configs=event_basic_field_configs)

        expected_sql = (
            "SELECT "
            "udf_build_origin_data('字段A',CONCAT_WS('',CAST(`sub_table`.`字段A` AS STRING))) "
            "`event_data`,200 `strategy_id`,`sub_table`.`strategy_rule_id` `strategy_rule_id` "
            "FROM ("
            "SELECT `t`.`字段A`,`t`.`wguard__r1`,CASE WHEN `wguard__r1`>0 THEN 1 END `strategy_rule_id` "
            "FROM ("
            "SELECT `simple_rt`.`fieldA` `字段A`,"
            "CASE WHEN `simple_rt`.`event_type`='test' THEN 1 ELSE 0 END `wguard__r1` "
            "FROM simple_rt `simple_rt` "
            "WHERE `simple_rt`.`event_type`='test') `t`) `sub_table` "
            "WHERE NOT `sub_table`.`strategy_rule_id` IS NULL"
        )
        self._build_and_assert_sql(strategy, expected_sql)

    def test_single_table_with_where_and_system_ids(self):
        """
        场景: 单表, config_type=EventLog, 前端有 where, data_source 中含 system_ids
        """
        config_json = {
            "config_type": RuleAuditConfigType.EVENT_LOG,
            "data_source": {"rt_id": "test_rt_id", "system_ids": ["sys_1", "sys_2"]},
            "select": [
                {
                    "table": "test_rt_id",
                    "raw_name": "event_id",
                    "display_name": "事件ID",
                    "field_type": "string",
                    "aggregate": None,
                }
            ],
            "where": {
                "connector": "and",
                "condition": {
                    "field": {
                        "table": "test_rt_id",
                        "raw_name": "username",
                        "display_name": "操作人",
                        "field_type": "string",
                        "aggregate": None,
                    },
                    "operator": "eq",
                    "filter": "admin",
                    "filters": [],
                },
            },
        }
        event_basic_field_configs = []
        strategy = Strategy(strategy_id=101, configs=config_json, event_basic_field_configs=event_basic_field_configs)
        expected_sql = (
            "SELECT "
            "udf_build_origin_data('事件ID',CONCAT_WS('',CAST(`sub_table`.`事件ID` AS STRING))) "
            "`event_data`,101 `strategy_id`,`sub_table`.`strategy_rule_id` `strategy_rule_id` "
            "FROM ("
            "SELECT `t`.`事件ID`,`t`.`wguard__r1`,CASE WHEN `wguard__r1`>0 THEN 1 END `strategy_rule_id` "
            "FROM ("
            "SELECT `test_rt_id`.`event_id` `事件ID`,"
            "CASE WHEN `test_rt_id`.`event_type`='test' THEN 1 ELSE 0 END `wguard__r1` "
            "FROM test_rt_id `test_rt_id` "
            "WHERE `test_rt_id`.`event_type`='test' "
            "AND `test_rt_id`.`system_id` IN ('sys_1','sys_2')) `t`) `sub_table` "
            "WHERE NOT `sub_table`.`strategy_rule_id` IS NULL"
        )
        self._build_and_assert_sql(strategy, expected_sql)

    def test_single_table_with_field_mapping(self):
        """
        单表+field_mapping, 测试 target_value / source_field。
        """
        config_json = {
            "config_type": RuleAuditConfigType.EVENT_LOG,
            "data_source": {"rt_id": "my_rt"},
            "select": [
                {
                    "table": "my_rt",
                    "raw_name": "colA",
                    "display_name": "列A",
                    "field_type": "string",
                    "aggregate": None,
                },
                {
                    "table": "my_rt",
                    "raw_name": "colB",
                    "display_name": "列B",
                    "field_type": "string",
                    "aggregate": None,
                },
            ],
            "where": None,
        }
        event_basic_field_configs = [
            {"field_name": "fixed_col", "map_config": {"target_value": "abcdef"}},
            {"field_name": "mapped_col", "map_config": {"source_field": "列B"}},
        ]
        strategy = Strategy(strategy_id=300, configs=config_json, event_basic_field_configs=event_basic_field_configs)

        expected_sql = (
            "SELECT "
            "udf_build_origin_data('列A|!@#$%^&*|列B',"
            "CONCAT_WS('',CAST(`sub_table`.`列A` AS STRING),'|!@#$%^&*|',CAST(`sub_table`.`列B` AS STRING))) "
            "`event_data`,300 `strategy_id`,"
            "`sub_table`.`strategy_rule_id` `strategy_rule_id`,"
            "'abcdef' `fixed_col`,`sub_table`.`列B` `mapped_col` "
            "FROM ("
            "SELECT `t`.`列A`,`t`.`列B`,`t`.`wguard__r1`,CASE WHEN `wguard__r1`>0 THEN 1 END `strategy_rule_id` "
            "FROM ("
            "SELECT `my_rt`.`colA` `列A`,`my_rt`.`colB` `列B`,"
            "CASE WHEN `my_rt`.`event_type`='test' THEN 1 ELSE 0 END `wguard__r1` "
            "FROM my_rt `my_rt` "
            "WHERE `my_rt`.`event_type`='test') `t`) `sub_table` "
            "WHERE NOT `sub_table`.`strategy_rule_id` IS NULL"
        )
        self._build_and_assert_sql(strategy, expected_sql)

    @patch("services.web.strategy_v2.handlers.rule_audit.get_object_or_404")
    def test_link_table_simple(self, mock_get_obj):
        """
        测试联表场景, mock 返回 LinkTable
        只关心 build_sql 的最终结果
        """
        mock_link_table_obj = MagicMock()
        mock_link_table_obj.config = {
            "links": [
                {
                    "join_type": "left_join",
                    "link_fields": [
                        {"left_field": {"field_name": "event_id"}, "right_field": {"field_name": "resource_id"}}
                    ],
                    "left_table": {
                        "rt_id": "log_rt_1",
                        "table_type": LinkTableTableType.EVENT_LOG,
                        "system_ids": ["sys_111"],
                    },
                    "right_table": {"rt_id": "asset_rt_2", "table_type": "Asset", "system_ids": []},
                }
            ]
        }
        config_json = {
            "config_type": "LinkTable",
            "data_source": {"link_table": {"uid": "demo_uid", "version": 1}},
            "select": [
                {
                    "table": "log_rt_1",
                    "raw_name": "event_id",
                    "display_name": "事件ID",
                    "field_type": "string",
                    "aggregate": None,
                }
            ],
            "where": None,
        }
        event_basic_field_configs = [
            {"field_name": "operator_name", "map_config": {"source_field": "事件ID", "target_value": None}},
            {"field_name": "bk_biz_id", "map_config": {"target_value": "123"}},
        ]
        strategy = Strategy(strategy_id=999, configs=config_json, event_basic_field_configs=event_basic_field_configs)

        expected_sql = (
            "SELECT "
            "udf_build_origin_data('事件ID',CONCAT_WS('',CAST(`sub_table`.`事件ID` AS STRING))) "
            "`event_data`,999 `strategy_id`,"
            "`sub_table`.`strategy_rule_id` `strategy_rule_id`,"
            "`sub_table`.`事件ID` `operator_name`,'123' `bk_biz_id` "
            "FROM ("
            "SELECT `t`.`事件ID`,`t`.`wguard__r1`,CASE WHEN `wguard__r1`>0 THEN 1 END `strategy_rule_id` "
            "FROM ("
            "SELECT `log_rt_1`.`event_id` `事件ID`,"
            "CASE WHEN `log_rt_1`.`event_type`='test' THEN 1 ELSE 0 END `wguard__r1` "
            "FROM log_rt_1 `log_rt_1` "
            "LEFT JOIN asset_rt_2 `asset_rt_2` "
            "ON `log_rt_1`.`event_id`=`asset_rt_2`.`resource_id` "
            "WHERE `log_rt_1`.`event_type`='test' AND `log_rt_1`.`system_id` "
            "IN ('sys_111')) `t`) `sub_table` "
            "WHERE NOT `sub_table`.`strategy_rule_id` IS NULL"
        )
        self._build_and_assert_sql(strategy, expected_sql, mock_link_table_obj=mock_link_table_obj)

    def test_link_table_config_empty_links(self):
        """
        测试当 links 为空时, build_sql 内部会调用 format => LinkTableConfigError
        """
        mock_link_table_obj = MagicMock()
        mock_link_table_obj.config = {"links": []}

        strategy = Strategy(
            strategy_id=1000,
            configs={
                "config_type": "LinkTable",
                "data_source": {"link_table": {"uid": "emptylinks_uid", "version": 1}},
                "select": [],
            },
            event_basic_field_configs=[],
        )
        # 创建 StrategyRule，避免 "has no strategy rule" 错误
        StrategyRule.objects.create(
            strategy=strategy,
            rule_name=f"rule_{strategy.strategy_id}",
            conditions={
                "where": {
                    "condition": {
                        "field": {
                            "table": "default_table",
                            "raw_name": "event_type",
                            "display_name": "event_type",
                            "field_type": "string",
                        },
                        "operator": "eq",
                        "filters": ["test"],
                    }
                },
                "having": None,
            },
        )

        with patch("services.web.strategy_v2.handlers.rule_audit.get_object_or_404", return_value=mock_link_table_obj):
            with self.assertRaises(LinkTableConfigError):
                RuleAuditSQLBuilder(strategy).build_sql()

    def test_json_with_mixed_columns_and_values(self):
        """
        测试 JSON 中既包含列值又包含固定字符串值的场景。
        """
        config_json = {
            "config_type": RuleAuditConfigType.EVENT_LOG,
            "data_source": {"rt_id": "mixed_rt"},
            "select": [
                {
                    "table": "mixed_rt",
                    "raw_name": "colA",
                    "display_name": "列A",
                    "field_type": "string",
                    "aggregate": None,
                },
                {
                    "table": "mixed_rt",
                    "raw_name": "colB",
                    "display_name": "列B",
                    "field_type": "string",
                    "aggregate": None,
                },
            ],
            "where": None,
        }
        event_basic_field_configs = [
            {"field_name": "fixed_value", "map_config": {"target_value": "固定值"}},
            {"field_name": "mapped_col", "map_config": {"source_field": "列A"}},
        ]
        strategy = Strategy(strategy_id=400, configs=config_json, event_basic_field_configs=event_basic_field_configs)

        expected_sql = (
            "SELECT "
            "udf_build_origin_data("
            "'列A|!@#$%^&*|列B',"
            "CONCAT_WS('',CAST(`sub_table`.`列A` AS STRING),'|!@#$%^&*|',CAST(`sub_table`.`列B` AS STRING))) "
            "`event_data`,400 `strategy_id`,"
            "`sub_table`.`strategy_rule_id` `strategy_rule_id`,"
            "'固定值' `fixed_value`,`sub_table`.`列A` `mapped_col` "
            "FROM ("
            "SELECT `t`.`列A`,`t`.`列B`,`t`.`wguard__r1`,CASE WHEN `wguard__r1`>0 THEN 1 END `strategy_rule_id` "
            "FROM ("
            "SELECT `mixed_rt`.`colA` `列A`,`mixed_rt`.`colB` `列B`,"
            "CASE WHEN `mixed_rt`.`event_type`='test' THEN 1 ELSE 0 END `wguard__r1` "
            "FROM mixed_rt `mixed_rt` "
            "WHERE `mixed_rt`.`event_type`='test') `t`) `sub_table` "
            "WHERE NOT `sub_table`.`strategy_rule_id` IS NULL"
        )
        self._build_and_assert_sql(strategy, expected_sql)

    def test_json_with_special_characters(self):
        """
        测试 JSON 值中包含特殊字符（如双引号和反斜杠）的情况。
        """
        config_json = {
            "config_type": RuleAuditConfigType.EVENT_LOG,
            "data_source": {"rt_id": "special_char_rt"},
            "select": [
                {
                    "table": "special_char_rt",
                    "raw_name": "colA",
                    "display_name": "列A",
                    "field_type": "string",
                    "aggregate": None,
                }
            ],
            "where": None,
        }
        event_basic_field_configs = [
            {"field_name": "fixed_col", "map_config": {"target_value": '值含"特殊字符\\"和反斜杠'}},
        ]
        strategy = Strategy(strategy_id=500, configs=config_json, event_basic_field_configs=event_basic_field_configs)

        expected_sql = (
            "SELECT "
            "udf_build_origin_data('列A',CONCAT_WS('',CAST(`sub_table`.`列A` AS STRING))) "
            "`event_data`,500 `strategy_id`,"
            "`sub_table`.`strategy_rule_id` `strategy_rule_id`,"
            "'值含\"特殊字符\\\"和反斜杠' `fixed_col` "
            "FROM ("
            "SELECT `t`.`列A`,`t`.`wguard__r1`,CASE WHEN `wguard__r1`>0 THEN 1 END `strategy_rule_id` "
            "FROM ("
            "SELECT `special_char_rt`.`colA` `列A`,"
            "CASE WHEN `special_char_rt`.`event_type`='test' THEN 1 ELSE 0 END `wguard__r1` "
            "FROM special_char_rt `special_char_rt` "
            "WHERE `special_char_rt`.`event_type`='test') `t`) `sub_table` "
            "WHERE NOT `sub_table`.`strategy_rule_id` IS NULL"
        )
        self._build_and_assert_sql(strategy, expected_sql)

    def test_nested_json_structure(self):
        """
        测试嵌套 JSON 结构的拼接。
        """
        config_json = {
            "config_type": RuleAuditConfigType.EVENT_LOG,
            "data_source": {"rt_id": "nested_rt"},
            "select": [
                {
                    "table": "nested_rt",
                    "raw_name": "colA",
                    "display_name": "列A",
                    "field_type": "string",
                    "aggregate": None,
                },
            ],
            "where": None,
        }
        event_basic_field_configs = [
            {
                "field_name": "nested_json",
                "map_config": {
                    "target_value": None,
                    "source_field": None,
                },
            }
        ]
        strategy = Strategy(strategy_id=600, configs=config_json, event_basic_field_configs=event_basic_field_configs)

        expected_sql = (
            "SELECT "
            "udf_build_origin_data('列A',CONCAT_WS('',CAST(`sub_table`.`列A` AS STRING))) "
            "`event_data`,600 `strategy_id`,`sub_table`.`strategy_rule_id` `strategy_rule_id` "
            "FROM ("
            "SELECT `t`.`列A`,`t`.`wguard__r1`,CASE WHEN `wguard__r1`>0 THEN 1 END `strategy_rule_id` "
            "FROM ("
            "SELECT `nested_rt`.`colA` `列A`,CASE WHEN `nested_rt`.`event_type`='test' THEN 1 ELSE 0 END `wguard__r1` "
            "FROM nested_rt `nested_rt` "
            "WHERE `nested_rt`.`event_type`='test') `t`) `sub_table` "
            "WHERE NOT `sub_table`.`strategy_rule_id` IS NULL"
        )
        self._build_and_assert_sql(strategy, expected_sql)

    @patch("services.web.strategy_v2.handlers.rule_audit.get_object_or_404")
    def test_complex_link_table_with_conditions(self, mock_get_obj):
        """
        测试复杂联表场景，包含多个表、多种联接类型和复杂查询条件。
        """
        mock_link_table_obj = MagicMock()
        mock_link_table_obj.config = {
            "links": [
                {
                    "join_type": "left_join",
                    "link_fields": [
                        {
                            "left_field": {"field_name": "event_id", "display_name": "event_id"},
                            "right_field": {"field_name": "resource_id", "display_name": "resource_id"},
                        }
                    ],
                    "left_table": {
                        "rt_id": "log_rt_1",
                        "table_type": LinkTableTableType.EVENT_LOG,
                        "system_ids": ["sys_111"],
                        "display_name": "a",
                    },
                    "right_table": {
                        "rt_id": "asset_rt_2",
                        "table_type": LinkTableTableType.BUILD_ID_ASSET,
                        "display_name": "b",
                    },
                },
                {
                    "join_type": "inner_join",
                    "link_fields": [
                        {
                            "left_field": {"field_name": "resource_id", "display_name": "resource_id"},
                            "right_field": {"field_name": "host_id", "display_name": "host_id"},
                        }
                    ],
                    "left_table": {
                        "rt_id": "asset_rt_2",
                        "table_type": LinkTableTableType.BUILD_ID_ASSET,
                        "display_name": "b",
                    },
                    "right_table": {"rt_id": "host_rt_3", "table_type": LinkTableTableType.BIZ_RT, "display_name": "c"},
                },
                {
                    "join_type": "left_join",
                    "link_fields": [
                        {
                            "left_field": {"field_name": "host_id", "display_name": "host_id"},
                            "right_field": {"field_name": "network_id", "display_name": "network_id"},
                        }
                    ],
                    "left_table": {"rt_id": "host_rt_3", "table_type": LinkTableTableType.BIZ_RT, "display_name": "c"},
                    "right_table": {
                        "rt_id": "network_rt_4",
                        "table_type": LinkTableTableType.BUILD_ID_ASSET,
                        "display_name": "d",
                    },
                },
            ]
        }

        # Mocking get_object_or_404
        mock_get_obj.return_value = mock_link_table_obj

        # Strategy configuration
        config_json = {
            "config_type": "LinkTable",
            "data_source": {"link_table": {"uid": "complex_uid", "version": 1}},
            "select": [
                {
                    "table": "a",
                    "raw_name": "event_id",
                    "display_name": "事件ID",
                    "field_type": "string",
                    "aggregate": None,
                },
                {
                    "table": "b",
                    "raw_name": "resource_id",
                    "display_name": "资源ID",
                    "field_type": "string",
                    "aggregate": "COUNT",
                },
                {
                    "table": "c",
                    "raw_name": "host_id",
                    "display_name": "主机ID",
                    "field_type": "string",
                    "aggregate": None,
                },
                {
                    "table": "d",
                    "raw_name": "network_name",
                    "display_name": "网络名称",
                    "field_type": "long",
                    "aggregate": "MAX",
                },
                {
                    "table": "d",
                    "raw_name": "details",
                    "display_name": "网络详情",
                    "field_type": "int",
                    "aggregate": "COUNT",
                    "keys": ["host", "type"],
                },
            ],
            "where": {
                "connector": "and",
                "conditions": [
                    {
                        "connector": "or",
                        "conditions": [],
                        "condition": {
                            "field": {
                                "table": "a",
                                "raw_name": "event_type",
                                "display_name": "事件类型",
                                "field_type": "string",
                            },
                            "operator": "eq",
                            "filter": "critical",
                            "filters": [],
                        },
                    },
                    {
                        "connector": "and",
                        "conditions": [],
                        "condition": {
                            "field": {
                                "table": "b",
                                "raw_name": "resource_status",
                                "display_name": "资源状态",
                                "field_type": "string",
                            },
                            "operator": "neq",
                            "filter": "inactive",
                            "filters": [],
                        },
                    },
                ],
            },
            "having": {
                "connector": "and",
                "conditions": [
                    {
                        "connector": "or",
                        "conditions": [],
                        "condition": {
                            "field": {
                                "table": "b",
                                "raw_name": "resource_id",
                                "display_name": "资源ID",
                                "field_type": "long",
                                "aggregate": "COUNT",
                            },
                            "operator": "gt",
                            "filter": 100,
                            "filters": [],
                        },
                    },
                    {
                        "connector": "or",
                        "conditions": [],
                        "condition": {
                            "field": {
                                "table": "d",
                                "raw_name": "details",
                                "display_name": "网络详情",
                                "field_type": "int",
                                "aggregate": "COUNT",
                                "keys": ["host", "type"],
                            },
                            "operator": "gt",
                            "filter": 300,
                            "filters": [],
                        },
                    },
                ],
            },
        }

        # Field mapping for additional fields
        event_basic_field_configs = [
            {"field_name": "operator_name", "map_config": {"source_field": "主机ID", "target_value": None}},
            {"field_name": "bk_biz_id", "map_config": {"target_value": "456"}},
        ]

        strategy = Strategy(strategy_id=888, configs=config_json, event_basic_field_configs=event_basic_field_configs)

        # Expected SQL
        expected_sql = (
            "SELECT "
            "udf_build_origin_data('事件ID|!@#$%^&*|资源ID|!@#$%^&*|主机ID|!@#$%^&*|网络名称|!@#$%^&*|网络详情',"
            "CONCAT_WS('',CAST(`sub_table`.`事件ID` AS STRING),'|!@#$%^&*|',"
            "CAST(CASE WHEN `sub_table`.`strategy_rule_id`=1 THEN `sub_table`.`资源ID__r1` END AS STRING),'|!@#$%^&*|',"
            "CAST(`sub_table`.`主机ID` AS STRING),'|!@#$%^&*|',"
            "CAST(CASE WHEN `sub_table`.`strategy_rule_id`=1 THEN `sub_table`.`网络名称__r1` END AS STRING),'|!@#$%^&*|',"
            "CAST(CASE WHEN `sub_table`.`strategy_rule_id`=1 THEN `sub_table`.`网络详情__r1` END AS STRING))) "
            "`event_data`,"
            "888 `strategy_id`,"
            "`sub_table`.`strategy_rule_id` `strategy_rule_id`,"
            "`sub_table`.`主机ID` `operator_name`,'456' `bk_biz_id` "
            "FROM ("
            "SELECT `t`.`事件ID`,`t`.`资源ID__r1`,`t`.`主机ID`,"
            "`t`.`网络名称__r1`,`t`.`网络详情__r1`,`t`.`wguard__r1`,"
            "CASE WHEN `wguard__r1`>0 THEN 1 END `strategy_rule_id` "
            "FROM ("
            "SELECT `a`.`event_id` `事件ID`,"
            "COUNT(CASE WHEN `a`.`event_type`='test' THEN `b`.`resource_id` END) `资源ID__r1`,"
            "`c`.`host_id` `主机ID`,"
            "MAX(CASE WHEN `a`.`event_type`='test' THEN `d`.`network_name` END) `网络名称__r1`,"
            "COUNT(CASE WHEN `a`.`event_type`='test' "
            "THEN CAST(GET_JSON_OBJECT(`d`.`details`,"
            "'$.[\"host\"].[\"type\"]') AS INT) END) `网络详情__r1`,"
            "COUNT(CASE WHEN `a`.`event_type`='test' THEN 1 END) `wguard__r1` "
            "FROM log_rt_1 `a` LEFT JOIN asset_rt_2 `b` ON `a`.`event_id`=`b`.`resource_id` "
            "JOIN host_rt_3 `c` ON `b`.`resource_id`=`c`.`host_id` "
            "LEFT JOIN network_rt_4 `d` ON `c`.`host_id`=`d`.`network_id` "
            "WHERE `a`.`event_type`='test' AND `a`.`system_id` IN ('sys_111') "
            "GROUP BY `a`.`event_id`,`c`.`host_id`) `t`) `sub_table` "
            "WHERE NOT `sub_table`.`strategy_rule_id` IS NULL"
        )

        # Run the test
        self._build_and_assert_sql(strategy, expected_sql, mock_link_table_obj=mock_link_table_obj)

        # 测试实时链路下的下钻sql
        config_json = deepcopy(config_json)
        config_json["data_source"]["source_type"] = FlowDataSourceNodeType.REALTIME

        strategy = Strategy(strategy_id=888, configs=config_json, event_basic_field_configs=event_basic_field_configs)

        expected_sql = (
            "SELECT "
            "udf_build_origin_data('事件ID|!@#$%^&*|资源ID|!@#$%^&*|主机ID|!@#$%^&*|网络名称|!@#$%^&*|网络详情',"
            "CONCAT_WS('',CAST(`sub_table`.`事件ID` AS STRING),'|!@#$%^&*|',"
            "CAST(CASE WHEN `sub_table`.`strategy_rule_id`=1 THEN `sub_table`.`资源ID__r1` END AS STRING),'|!@#$%^&*|',"
            "CAST(`sub_table`.`主机ID` AS STRING),'|!@#$%^&*|',"
            "CAST(CASE WHEN `sub_table`.`strategy_rule_id`=1 THEN `sub_table`.`网络名称__r1` END AS STRING),'|!@#$%^&*|',"
            "CAST(CASE WHEN `sub_table`.`strategy_rule_id`=1 THEN `sub_table`.`网络详情__r1` END AS STRING))) "
            "`event_data`,"
            "888 `strategy_id`,"
            "`sub_table`.`strategy_rule_id` `strategy_rule_id`,"
            "`sub_table`.`主机ID` `operator_name`,'456' `bk_biz_id` "
            "FROM ("
            "SELECT `t`.`事件ID`,`t`.`资源ID__r1`,`t`.`主机ID`,"
            "`t`.`网络名称__r1`,`t`.`网络详情__r1`,`t`.`wguard__r1`,"
            "CASE WHEN `wguard__r1`>0 THEN 1 END `strategy_rule_id` "
            "FROM ("
            "SELECT `a`.`event_id` `事件ID`,"
            "COUNT(CASE WHEN `a`.`event_type`='test' THEN `b`.`resource_id` END) `资源ID__r1`,"
            "`c`.`host_id` `主机ID`,"
            "MAX(CASE WHEN `a`.`event_type`='test' THEN `d`.`network_name` END) `网络名称__r1`,"
            "COUNT(CASE WHEN `a`.`event_type`='test' "
            "THEN CAST(JSON_VALUE(`d`.`details`,"
            "'$.[\"host\"].[\"type\"]') AS INT) END) `网络详情__r1`,"
            "COUNT(CASE WHEN `a`.`event_type`='test' THEN 1 END) `wguard__r1` "
            "FROM log_rt_1 `a` LEFT JOIN asset_rt_2 `b` ON `a`.`event_id`=`b`.`resource_id` "
            "JOIN host_rt_3 `c` ON `b`.`resource_id`=`c`.`host_id` "
            "LEFT JOIN network_rt_4 `d` ON `c`.`host_id`=`d`.`network_id` "
            "WHERE `a`.`event_type`='test' AND `a`.`system_id` IN ('sys_111') "
            "GROUP BY `a`.`event_id`,`c`.`host_id`) `t`) `sub_table` "
            "WHERE NOT `sub_table`.`strategy_rule_id` IS NULL"
        )

        # Run the test
        self._build_and_assert_sql(strategy, expected_sql, mock_link_table_obj=mock_link_table_obj)

        # Mock 返回值
        mock_get_obj.return_value = mock_link_table_obj

        # Strategy 配置
        config_json = {
            "config_type": "LinkTable",
            "data_source": {"link_table": {"uid": "complex_uid", "version": 1}},
            "select": [
                {
                    "table": "a",
                    "raw_name": "event_id",
                    "display_name": "事件ID",
                    "field_type": "string",
                    "aggregate": None,
                },
                {
                    "table": "b",
                    "raw_name": "resource_name",
                    "display_name": "资源名称",
                    "field_type": "string",
                    "aggregate": None,
                },
                {
                    "table": "a",
                    "raw_name": "username",
                    "display_name": "操作人",
                    "field_type": "string",
                    "aggregate": None,
                },
                {
                    "table": "b",
                    "raw_name": "status",
                    "display_name": "资源状态",
                    "field_type": "string",
                    "aggregate": None,
                },
            ],
            "where": {
                "connector": "and",
                "conditions": [
                    {
                        "connector": "or",
                        "conditions": [
                            {
                                "condition": {
                                    "field": {
                                        "table": "a",
                                        "raw_name": "username",
                                        "display_name": "操作人",
                                        "field_type": "string",
                                        "aggregate": None,
                                    },
                                    "operator": "eq",
                                    "filter": "admin",
                                },
                            },
                            {
                                "condition": {
                                    "field": {
                                        "table": "b",
                                        "raw_name": "status",
                                        "display_name": "资源状态",
                                        "field_type": "string",
                                        "aggregate": None,
                                    },
                                    "operator": "neq",
                                    "filter": "inactive",
                                },
                            },
                        ],
                    },
                    {
                        "condition": {
                            "field": {
                                "table": "c",
                                "raw_name": "region",
                                "display_name": "地区",
                                "field_type": "string",
                                "aggregate": None,
                            },
                            "operator": "eq",
                            "filter": "US",
                        },
                    },
                ],
            },
        }

        # 字段映射
        event_basic_field_configs = [
            {"field_name": "operator_name", "map_config": {"source_field": "操作人"}},
            {"field_name": "resource_status", "map_config": {"source_field": "资源状态"}},
        ]

        # Strategy
        strategy = Strategy(strategy_id=123, configs=config_json, event_basic_field_configs=event_basic_field_configs)

        # 期望 SQL（多规则三层：行级场景守卫为行指示器；configs.where 被忽略，规则级 where 生效）
        expected_sql = (
            "SELECT "
            "udf_build_origin_data('事件ID|!@#$%^&*|资源名称|!@#$%^&*|操作人|!@#$%^&*|资源状态',"
            "CONCAT_WS('',CAST(`sub_table`.`事件ID` AS STRING),'|!@#$%^&*|',"
            "CAST(`sub_table`.`资源名称` AS STRING),'|!@#$%^&*|',CAST(`sub_table`.`操作人` AS STRING),'|!@#$%^&*|',"
            "CAST(`sub_table`.`资源状态` AS STRING))) `event_data`,"
            "123 `strategy_id`,`sub_table`.`strategy_rule_id` `strategy_rule_id`,"
            "`sub_table`.`操作人` `operator_name`,`sub_table`.`资源状态` `resource_status` "
            "FROM ("
            "SELECT `t`.`事件ID`,`t`.`资源名称`,`t`.`操作人`,`t`.`资源状态`,`t`.`wguard__r1`,"
            "CASE WHEN `wguard__r1`>0 THEN 1 END `strategy_rule_id` "
            "FROM ("
            "SELECT `a`.`event_id` `事件ID`,`b`.`resource_name` `资源名称`,`a`.`username` `操作人`,`b`.`status` `资源状态`,"
            "CASE WHEN `a`.`event_type`='test' THEN 1 ELSE 0 END `wguard__r1` "
            "FROM log_rt_1 `a` LEFT JOIN asset_rt_2 `b` ON `a`.`event_id`=`b`.`resource_id` "
            "JOIN host_rt_3 `c` ON `b`.`resource_id`=`c`.`host_id` "
            "LEFT JOIN network_rt_4 `d` ON `c`.`host_id`=`d`.`network_id` "
            "WHERE `a`.`event_type`='test' AND `a`.`system_id` IN ('sys_111')) `t`) `sub_table` "
            "WHERE NOT `sub_table`.`strategy_rule_id` IS NULL"
        )

        # 断言
        self._build_and_assert_sql(strategy, expected_sql, mock_link_table_obj=mock_link_table_obj)

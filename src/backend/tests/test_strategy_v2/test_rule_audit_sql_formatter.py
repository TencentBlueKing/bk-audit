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
import unittest
from unittest.mock import MagicMock, patch

from core.sql.builder import BKBaseQueryBuilder
from core.sql.sql_builder import SQLGenerator
from services.web.strategy_v2.constants import LinkTableTableType, RuleAuditConfigType
from services.web.strategy_v2.exceptions import LinkTableConfigError
from services.web.strategy_v2.handlers.rule_audit import RuleAuditSQLFormatter
from tests.base import TestCase


class TestRuleAuditSQLFormatter(TestCase):
    """
    单元测试类，用于测试 RuleAuditSQLFormatter 的 JSON 结构和生成的 SQL 语句。
    """

    def setUp(self):
        # 实例化 RuleAuditSQLFormatter
        self.formatter = RuleAuditSQLFormatter()

    def _generate_and_validate(self, config_json, expected_json_dict, expected_sql, mock_link_table_obj=None):
        """
        辅助方法：根据配置生成 SqlConfig 和 SQL，并进行断言。

        Args:
            config_json (dict): 前端传入的配置 JSON。
            expected_json_dict (dict): 预期的 SqlConfig JSON 结构。
            expected_sql (str): 预期生成的 SQL 语句。
            mock_link_table_obj (MagicMock, optional): 模拟的 LinkTable 对象（用于联表场景）。
        """
        # 如果提供了 mock_link_table_obj，则设置 mock
        if mock_link_table_obj:
            with patch(
                "services.web.strategy_v2.handlers.rule_audit.get_object_or_404",
                return_value=mock_link_table_obj,
            ):
                sql_config = self.formatter.format(config_json)
        else:
            sql_config = self.formatter.format(config_json)

        # 序列化 SqlConfig 为 JSON 字符串，并转换为字典
        actual_json_dict = json.loads(sql_config.model_dump_json())

        # 断言 SqlConfig JSON 结构
        self.assertDictEqual(
            actual_json_dict,
            expected_json_dict,
            f"\n实际 JSON:\n{json.dumps(actual_json_dict, indent=2, ensure_ascii=False)}\n"
            f"期望 JSON:\n{json.dumps(expected_json_dict, indent=2, ensure_ascii=False)}",
        )

        # 生成 SQL
        generator = SQLGenerator(query_builder=BKBaseQueryBuilder(), config=sql_config)
        query = generator.generate()
        actual_sql = str(query)

        # 断言生成的 SQL 是否与预期一致
        self.assertEqual(
            actual_sql,
            expected_sql,
            f"\n实际 SQL:\n{actual_sql}\n期望 SQL:\n{expected_sql}",
        )

    def test_single_table_with_where_and_system_ids(self):
        """
        场景: 单表, config_type=EventLog, 前端有 where, data_source 中含 system_ids
        验证生成的 SqlConfig JSON 和 SQL 是否与预期完全匹配
        """
        config_json = {
            "config_type": RuleAuditConfigType.EVENT_LOG,  # "EventLog"
            "data_source": {"rt_id": "test_rt_id", "system_ids": ["sys_1", "sys_2"]},
            "select": [
                {
                    "rt_id": "test_rt_id",
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
                        "rt_id": "test_rt_id",
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

        expected_json_dict = {
            "select_fields": [
                {
                    "table": "test_rt_id",
                    "raw_name": "event_id",
                    "display_name": "事件ID",
                    "field_type": "string",
                    "aggregate": None,
                }
            ],
            "from_table": "test_rt_id",
            "join_tables": [],
            "where": {
                "connector": "and",
                "conditions": [
                    {
                        "connector": "and",
                        "conditions": [],
                        "condition": {
                            "field": {
                                "table": "test_rt_id",
                                "raw_name": "username",
                                "display_name": "操作人",
                                "field_type": "string",
                                "aggregate": None,
                            },
                            "operator": "eq",
                            "filters": [],
                            "filter": "admin",
                        },
                    },
                    {
                        "connector": "and",
                        "conditions": [],
                        "condition": {
                            "field": {
                                "table": "test_rt_id",
                                "raw_name": "system_id",
                                "display_name": "system_id",
                                "field_type": "string",
                                "aggregate": None,
                            },
                            "operator": "include",
                            "filters": ["sys_1", "sys_2"],
                            "filter": "",
                        },
                    },
                ],
                "condition": None,
            },
            "group_by": [],
            "order_by": [],
            "pagination": None,
        }

        expected_sql = (
            "SELECT `event_id` `事件ID` "
            "FROM `test_rt_id` "
            "WHERE `username`='admin' "
            "AND `system_id` IN ('sys_1','sys_2')"
        )
        # 调用辅助方法进行断言
        self._generate_and_validate(config_json, expected_json_dict, expected_sql)

    def test_single_table_no_where_with_system_ids(self):
        """
        场景: 单表, config_type=EventLog, 无前端 where, data_source 中含 system_ids
        只应生成一条 system_id IN(...) 的 where 条件
        """
        config_json = {
            "config_type": RuleAuditConfigType.EVENT_LOG,
            "data_source": {"rt_id": "my_single_rt", "system_ids": ["sys_a", "sys_b"]},
            "select": [
                {
                    "rt_id": "my_single_rt",
                    "raw_name": "id",
                    "display_name": "ID",
                    "field_type": "string",
                    "aggregate": None,
                }
            ],
            "where": None,
        }

        expected_json_dict = {
            "select_fields": [
                {
                    "table": "my_single_rt",
                    "raw_name": "id",
                    "display_name": "ID",
                    "field_type": "string",
                    "aggregate": None,
                }
            ],
            "from_table": "my_single_rt",
            "join_tables": [],
            "where": {
                "connector": "and",
                "conditions": [
                    {
                        "connector": "and",
                        "conditions": [],
                        "condition": {
                            "field": {
                                "table": "my_single_rt",
                                "raw_name": "system_id",
                                "display_name": "system_id",
                                "field_type": "string",
                                "aggregate": None,
                            },
                            "operator": "include",
                            "filters": ["sys_a", "sys_b"],
                            "filter": "",
                        },
                    }
                ],
                "condition": None,
            },
            "group_by": [],
            "order_by": [],
            "pagination": None,
        }

        expected_sql = (
            "SELECT `my_single_rt`.`id` AS `ID` "
            "FROM `my_single_rt` "
            "WHERE (`my_single_rt`.`system_id` IN ('sys_a','sys_b'))"
        )
        expected_sql = "SELECT `id` `ID` " "FROM `my_single_rt` " "WHERE `system_id` IN ('sys_a','sys_b')"

        # 调用辅助方法进行断言
        self._generate_and_validate(config_json, expected_json_dict, expected_sql)

    @patch("services.web.strategy_v2.handlers.rule_audit.get_object_or_404")
    def test_link_table_with_system_ids(self, mock_get_obj):
        """
        场景: 联表, 模拟 LinkTable 配置, 注入 system_ids
        这里演示1条 link, left_table=EVENT_LOG, right_table=Asset
        """
        # 模拟 get_object_or_404 返回的 LinkTable 对象
        mock_link_table_obj = MagicMock()
        mock_link_table_obj.config = {
            "links": [
                {
                    "join_type": "left_join",
                    "link_fields": [{"left_field": "event_id", "right_field": "resource_id"}],
                    "left_table": {
                        "rt_id": "log_rt_1",
                        "table_type": LinkTableTableType.EVENT_LOG,  # EVENT_LOG
                        "system_ids": ["sys_111"],
                    },
                    "right_table": {
                        "rt_id": "asset_rt_2",
                        "table_type": "Asset",
                        "system_ids": [],
                    },  # 非EVENT_LOG
                }
            ]
        }

        config_json = {
            "config_type": RuleAuditConfigType.LINK_TABLE,  # "LinkTable"
            "data_source": {"link_table": {"uid": "demo_link_uid", "version": 1}},
            "select": [
                {
                    "rt_id": "log_rt_1",
                    "raw_name": "event_id",
                    "display_name": "事件ID",
                    "field_type": "string",
                    "aggregate": None,
                }
            ],
            "where": None,  # 无前端条件
        }

        expected_json_dict = {
            "select_fields": [
                {
                    "table": "log_rt_1",
                    "raw_name": "event_id",
                    "display_name": "事件ID",
                    "field_type": "string",
                    "aggregate": None,
                }
            ],
            "from_table": "log_rt_1",
            "join_tables": [
                {
                    "join_type": "left_join",
                    "link_fields": [{"left_field": "event_id", "right_field": "resource_id"}],
                    "left_table": "log_rt_1",
                    "right_table": "asset_rt_2",
                }
            ],
            "where": {
                "connector": "and",
                "conditions": [
                    {
                        "connector": "and",
                        "conditions": [],
                        "condition": {
                            "field": {
                                "table": "log_rt_1",
                                "raw_name": "system_id",
                                "display_name": "system_id",
                                "field_type": "string",
                                "aggregate": None,
                            },
                            "operator": "include",
                            "filters": ["sys_111"],
                            "filter": "",
                        },
                    }
                ],
                "condition": None,
            },
            "group_by": [],
            "order_by": [],
            "pagination": None,
        }

        expected_sql = (
            "SELECT `log_rt_1`.`event_id` `事件ID` "
            "FROM `log_rt_1` "
            "LEFT JOIN `asset_rt_2` ON `log_rt_1`.`event_id`=`asset_rt_2`.`resource_id` "
            "WHERE `log_rt_1`.`system_id` IN ('sys_111')"
        )
        # 设置 mock 返回值
        mock_get_obj.return_value = mock_link_table_obj

        # 调用辅助方法进行断言
        self._generate_and_validate(
            config_json,
            expected_json_dict,
            expected_sql,
            mock_link_table_obj=mock_link_table_obj,
        )

    @patch("services.web.strategy_v2.handlers.rule_audit.get_object_or_404")
    def test_link_table_with_multiple_links_and_multiple_event_logs(self, mock_get_obj):
        """
        场景: 联表配置下, 存在多条 link, 其中多个表都是 EVENT_LOG, 均应注入 system_ids
        """
        # 模拟 get_object_or_404 返回的 LinkTable 对象
        mock_link_table_obj = MagicMock()
        mock_link_table_obj.config = {
            "links": [
                {
                    "join_type": "left_join",
                    "link_fields": [{"left_field": "event_id", "right_field": "id1"}],
                    "left_table": {
                        "rt_id": "log_rt_A",
                        "table_type": LinkTableTableType.EVENT_LOG,
                        "system_ids": ["sys_a1", "sys_a2"],
                    },
                    "right_table": {
                        "rt_id": "log_rt_B",
                        "table_type": LinkTableTableType.EVENT_LOG,
                        "system_ids": ["sys_b1"],
                    },
                },
                {
                    "join_type": "inner_join",
                    "link_fields": [{"left_field": "id2", "right_field": "id3"}],
                    "left_table": {
                        "rt_id": "log_rt_B",
                        "table_type": LinkTableTableType.EVENT_LOG,
                        "system_ids": ["sys_b1"],  # 同样: EVENT_LOG
                    },
                    "right_table": {
                        "rt_id": "asset_rt_C",
                        "table_type": "Asset",
                        "system_ids": [],
                    },
                },
            ]
        }

        config_json = {
            "config_type": RuleAuditConfigType.LINK_TABLE,
            "data_source": {"link_table": {"uid": "multi_link_uid", "version": 2}},
            "select": [
                {
                    "rt_id": "log_rt_B",
                    "raw_name": "event_name",
                    "display_name": "事件名称",
                    "field_type": "string",
                    "aggregate": None,
                }
            ],
            "where": None,
        }

        expected_json_dict = {
            "select_fields": [
                {
                    "table": "log_rt_B",
                    "raw_name": "event_name",
                    "display_name": "事件名称",
                    "field_type": "string",
                    "aggregate": None,
                }
            ],
            "from_table": "log_rt_A",  # 第一个 link 的 left_table
            "join_tables": [
                {
                    "join_type": "left_join",
                    "link_fields": [{"left_field": "event_id", "right_field": "id1"}],
                    "left_table": "log_rt_A",
                    "right_table": "log_rt_B",
                },
                {
                    "join_type": "inner_join",
                    "link_fields": [{"left_field": "id2", "right_field": "id3"}],
                    "left_table": "log_rt_B",
                    "right_table": "asset_rt_C",
                },
            ],
            "where": {
                "connector": "and",
                "conditions": [
                    {
                        "connector": "and",
                        "conditions": [],
                        "condition": {
                            "field": {
                                "table": "log_rt_A",
                                "raw_name": "system_id",
                                "display_name": "system_id",
                                "field_type": "string",
                                "aggregate": None,
                            },
                            "operator": "include",
                            "filters": ["sys_a1", "sys_a2"],
                            "filter": "",
                        },
                    },
                    {
                        "connector": "and",
                        "conditions": [],
                        "condition": {
                            "field": {
                                "table": "log_rt_B",
                                "raw_name": "system_id",
                                "display_name": "system_id",
                                "field_type": "string",
                                "aggregate": None,
                            },
                            "operator": "include",
                            "filters": ["sys_b1"],
                            "filter": "",
                        },
                    },
                ],
                "condition": None,
            },
            "group_by": [],
            "order_by": [],
            "pagination": None,
        }

        expected_sql = (
            "SELECT `log_rt_B`.`event_name` `事件名称` "
            "FROM `log_rt_A` "
            "LEFT JOIN `log_rt_B` ON `log_rt_A`.`event_id`=`log_rt_B`.`id1` "
            "JOIN `asset_rt_C` ON `log_rt_B`.`id2`=`asset_rt_C`.`id3` "
            "WHERE `log_rt_A`.`system_id` IN ('sys_a1','sys_a2') "
            "AND `log_rt_B`.`system_id` IN ('sys_b1')"
        )
        # 设置 mock 返回值
        mock_get_obj.return_value = mock_link_table_obj

        # 调用辅助方法进行断言
        self._generate_and_validate(
            config_json,
            expected_json_dict,
            expected_sql,
            mock_link_table_obj=mock_link_table_obj,
        )

    @patch("services.web.strategy_v2.handlers.rule_audit.get_object_or_404")
    def test_link_table_config_empty_links(self, mock_get_obj):
        """
        场景: 联表配置错误, links 为空, 应抛出 ValueError 或自定义异常
        """
        # 模拟 get_object_or_404 返回的 LinkTable 对象
        mock_link_table_obj = MagicMock()
        mock_link_table_obj.config = {"links": []}  # 空 links

        config_json = {
            "config_type": RuleAuditConfigType.LINK_TABLE,
            "data_source": {"link_table": {"uid": "uid_empty_links", "version": 1}},
            "select": [],
        }

        # 设置 mock 返回值
        mock_get_obj.return_value = mock_link_table_obj

        # 期望: 由于 links 为空, 应该抛出异常
        with self.assertRaises(LinkTableConfigError):
            self.formatter.format(config_json)


if __name__ == "__main__":
    unittest.main()

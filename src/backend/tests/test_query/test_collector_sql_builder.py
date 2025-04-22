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

from datetime import datetime
from unittest import mock

from arrow import Arrow
from django.test import TestCase
from pypika import Order

from services.web.query.constants import DATE_FORMAT
from services.web.query.serializers import CollectorSearchReqSerializer
from services.web.query.utils.doris import DorisSQLBuilder
from services.web.query.utils.search_config import QueryConditionOperator


class TestDorisSQLBuilder(TestCase):
    """DorisSQLBuilder 单元测试"""

    def setUp(self):
        # Mock GlobalMetaConfig.get 返回固定表名
        # 固定时间范围（2025-02-20 22:49:16 至 2025-02-20 23:49:16）
        start_timestamp = datetime(2025, 2, 19, 22, 0, 0).timestamp()
        end_timestamp = datetime(2025, 2, 20, 4, 0, 0).timestamp()
        self.start_time = Arrow.fromtimestamp(start_timestamp)
        self.end_time = Arrow.fromtimestamp(end_timestamp)
        self.start_timestamp = int(start_timestamp * 1000)
        self.end_timestamp = int(end_timestamp * 1000)
        self.start_date = self.start_time.strftime(DATE_FORMAT)
        self.end_date = self.end_time.strftime(DATE_FORMAT)

    def tearDown(self):
        mock.patch.stopall()

    def _get_builder(
        self,
        filters=None,
        sort_list=None,
        page=1,
        page_size=50,
    ):
        """创建 Builder 实例"""
        conditions = CollectorSearchReqSerializer._build_time_conditions(
            {
                "start_time": self.start_time,
                "end_time": self.end_time,
            }
        )
        conditions.extend(filters or [])
        return DorisSQLBuilder(
            table="test_rt.doris",
            filters=conditions or [],
            sort_list=sort_list or [],
            page=page,
            page_size=page_size,
        )

    def test_base_time_condition(self):
        """测试基础时间条件"""
        builder = self._get_builder()
        # 验证数据查询 SQL
        data_sql = builder.build_data_sql()
        count_sql = builder.build_count_sql()
        expect = (
            f"SELECT * FROM test_rt.doris WHERE `thedate`>='{self.start_date}' AND `thedate`<='{self.end_date}' "
            f"AND `dtEventTimeStamp`>={self.start_timestamp} AND `dtEventTimeStamp`<={self.end_timestamp} LIMIT 50"
        )
        self.assertEqual(data_sql, expect)
        # 验证统计 SQL
        expect = (
            f"SELECT COUNT(*) `count` FROM test_rt.doris WHERE "
            f"`thedate`>='{self.start_date}' AND `thedate`<='{self.end_date}' "
            f"AND `dtEventTimeStamp`>={self.start_timestamp} AND `dtEventTimeStamp`<={self.end_timestamp} LIMIT 1"
        )
        self.assertEqual(count_sql, expect)

    def test_multiple_filters(self):
        """测试组合过滤条件"""
        filters = [
            # IN 查询
            {
                "field_name": "system_id",
                "keys": [],
                "operator": QueryConditionOperator.INCLUDE.value,
                "filters": ["bk-audit", "bk-bscp"],
            },
            # 精确匹配
            {
                "field_name": "action_id",
                "keys": [],
                "operator": QueryConditionOperator.EQ.value,
                "filters": ["create_link_table"],
            },
            # 模糊匹配
            {
                "field_name": "instance_name",
                "keys": [],
                "operator": QueryConditionOperator.LIKE.value,
                "filters": ["123131"],
            },
            # 嵌套字段查询
            {
                "field_name": "instance_data",
                "keys": ["key1"],
                "operator": QueryConditionOperator.EQ.value,
                "filters": ["value1"],
            },
        ]
        builder = self._get_builder(filters=filters)
        data_sql = builder.build_data_sql()
        count_sql = builder.build_count_sql()
        expect = (
            f"SELECT * FROM test_rt.doris WHERE `thedate`>='{self.start_date}' AND `thedate`<='{self.end_date}' "
            f"AND `dtEventTimeStamp`>={self.start_timestamp} "
            f"AND `dtEventTimeStamp`<={self.end_timestamp} AND `system_id` "
            f"IN ('bk-audit','bk-bscp') AND `action_id`='create_link_table' AND `instance_name` "
            f"LIKE '%123131%' AND JSON_EXTRACT_STRING(`instance_data`,'$.key1')='value1' LIMIT 50"
        )
        print(data_sql)
        self.assertEqual(data_sql, expect)
        expect = (
            f"SELECT COUNT(*) `count` FROM test_rt.doris WHERE "
            f"`thedate`>='{self.start_date}' AND `thedate`<='{self.end_date}' "
            f"AND `dtEventTimeStamp`>={self.start_timestamp} AND `dtEventTimeStamp`<={self.end_timestamp} "
            f"AND `system_id` IN ('bk-audit','bk-bscp') "
            f"AND `action_id`='create_link_table' AND `instance_name` LIKE '%123131%' "
            f"AND JSON_EXTRACT_STRING(`instance_data`,'$.key1')='value1' LIMIT 1"
        )
        print(count_sql)
        self.assertEqual(count_sql, expect)

    def test_sort_logic(self):
        """测试排序逻辑"""
        sort_list = [
            {"order_field": "dtEventTimeStamp", "order_type": Order.desc},
            {"order_field": "gseIndex", "order_type": Order.asc},
        ]
        builder = self._get_builder(sort_list=sort_list)
        data_sql = builder.build_data_sql()
        count_sql = builder.build_count_sql()
        expect = (
            f"SELECT * FROM test_rt.doris WHERE `thedate`>='{self.start_date}' AND `thedate`<='{self.end_date}' "
            f"AND `dtEventTimeStamp`>={self.start_timestamp} AND `dtEventTimeStamp`<={self.end_timestamp} "
            f"ORDER BY `dtEventTimeStamp` ASC,`gseIndex` ASC LIMIT 50"
        )
        self.assertEqual(data_sql, expect)
        expect = (
            f"SELECT COUNT(*) `count` FROM test_rt.doris WHERE "
            f"`thedate`>='{self.start_date}' AND `thedate`<='{self.end_date}' "
            f"AND `dtEventTimeStamp`>={self.start_timestamp} AND `dtEventTimeStamp`<={self.end_timestamp} LIMIT 1"
        )
        self.assertEqual(count_sql, expect)

    def test_pagination(self):
        """测试分页参数"""
        builder = self._get_builder(page=2, page_size=30)
        data_sql = builder.build_data_sql()
        count_sql = builder.build_count_sql()
        expect = (
            f"SELECT * FROM test_rt.doris WHERE `thedate`>='{self.start_date}' AND `thedate`<='{self.end_date}' "
            f"AND `dtEventTimeStamp`>={self.start_timestamp} "
            f"AND `dtEventTimeStamp`<={self.end_timestamp} LIMIT 30 OFFSET 30"
        )
        self.assertEqual(data_sql, expect)
        expect = (
            f"SELECT COUNT(*) `count` FROM test_rt.doris WHERE "
            f"`thedate`>='{self.start_date}' AND `thedate`<='{self.end_date}' "
            f"AND `dtEventTimeStamp`>={self.start_timestamp} AND `dtEventTimeStamp`<={self.end_timestamp} LIMIT 1"
        )
        self.assertEqual(count_sql, expect)

    def test_match_all_operator(self):
        """测试全文检索操作符"""
        filters = [
            {
                "field_name": "log",
                "keys": [],
                "operator": QueryConditionOperator.MATCH_ALL.value,
                "filters": ["12313"],
            }
        ]
        builder = self._get_builder(filters=filters)
        data_sql = str(builder.build_data_sql())
        count_sql = str(builder.build_count_sql())
        expect = (
            f"SELECT * FROM test_rt.doris WHERE `thedate`>='{self.start_date}' AND `thedate`<='{self.end_date}' "
            f"AND `dtEventTimeStamp`>={self.start_timestamp} AND `dtEventTimeStamp`<={self.end_timestamp} AND `log` "
            f"MATCH_ALL ('12313') LIMIT 50"
        )
        self.assertEqual(expect, data_sql)
        expect = (
            f"SELECT COUNT(*) `count` FROM test_rt.doris WHERE "
            f"`thedate`>='{self.start_date}' AND `thedate`<='{self.end_date}' "
            f"AND `dtEventTimeStamp`>={self.start_timestamp} AND `dtEventTimeStamp`<={self.end_timestamp} AND `log` "
            f"MATCH_ALL ('12313') LIMIT 1"
        )
        self.assertEqual(expect, count_sql)

    def test_like_multiple_values(self):
        """测试多值模糊查询(只会有一个值生效)"""
        filters = [
            {
                "field_name": "event_content",
                "keys": [],
                "operator": QueryConditionOperator.LIKE.value,
                "filters": ["123", "456"],
            }
        ]
        builder = self._get_builder(filters=filters)
        count_sql = builder.build_count_sql()
        data_sql = builder.build_data_sql()
        expect = (
            f"SELECT * FROM test_rt.doris WHERE `thedate`>='{self.start_date}' AND `thedate`<='{self.end_date}' "
            f"AND `dtEventTimeStamp`>={self.start_timestamp} AND `dtEventTimeStamp`<={self.end_timestamp} "
            f"AND `event_content` LIKE '%123%' LIMIT 50"
        )
        self.assertEqual(data_sql, expect)
        expect = (
            f"SELECT COUNT(*) `count` FROM test_rt.doris "
            f"WHERE `thedate`>='{self.start_date}' AND `thedate`<='{self.end_date}' "
            f"AND `dtEventTimeStamp`>={self.start_timestamp} AND `dtEventTimeStamp`<={self.end_timestamp} "
            f"AND `event_content` LIKE '%123%' LIMIT 1"
        )
        self.assertEqual(count_sql, expect)

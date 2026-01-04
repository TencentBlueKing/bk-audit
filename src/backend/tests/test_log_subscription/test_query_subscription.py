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
import uuid

from django.test import TestCase

from api.bk_base.constants import StorageType
from services.web.log_subscription.exceptions import (
    DataSourceNotFound,
    DataSourceNotInSubscription,
    LogSubscriptionNotFound,
)
from services.web.log_subscription.models import (
    LogDataSource,
    LogSubscription,
    LogSubscriptionItem,
)
from services.web.log_subscription.resources.subscription import QueryLogSubscription
from services.web.query.constants import TIMESTAMP_PARTITION_FIELD


class TestQueryLogSubscription(TestCase):
    """测试日志订阅查询"""

    def setUp(self):
        """准备测试数据"""
        # 创建数据源1：审计日志
        self.data_source_audit_log = LogDataSource.objects.create(
            source_id="audit_log",
            name="审计日志",
            description="审计日志数据源",
            namespace="bkaudit",
            bkbase_table_id="5000448_bklog_bkaudit_log_20230825_2d3cda964d",
            storage_type=StorageType.DORIS.value,
            time_field=TIMESTAMP_PARTITION_FIELD,
            required_filter_fields=["namespace", "system_id"],
            is_enabled=True,
        )

        # 创建数据源2：审计事件
        self.data_source_audit_event = LogDataSource.objects.create(
            source_id="audit_event",
            name="审计事件",
            description="审计事件数据源",
            namespace="bkaudit",
            bkbase_table_id="5000448_bklog_bkaudit_event_20230825_2d3cda964d",
            storage_type=StorageType.DORIS.value,
            time_field=TIMESTAMP_PARTITION_FIELD,
            required_filter_fields=[],  # 无必须筛选字段
            is_enabled=True,
        )

        # 创建订阅配置
        self.subscription = LogSubscription.objects.create(
            name="测试订阅",
            description="测试订阅配置",
            is_enabled=True,
        )
        self.token = self.subscription.token

        # 创建配置项1：审计日志（包含必须筛选字段）
        self.item_audit_log = LogSubscriptionItem.objects.create(
            subscription=self.subscription,
            name="审计日志配置项",
            description="查询审计日志",
            order=1,
            condition={
                "connector": "and",
                "conditions": [
                    {
                        "condition": {
                            "field": {
                                "table": "t",
                                "raw_name": "namespace",
                                "display_name": "命名空间",
                                "field_type": "string",
                            },
                            "operator": "eq",
                            "filter": "bkaudit",
                        }
                    },
                    {
                        "condition": {
                            "field": {
                                "table": "t",
                                "raw_name": "system_id",
                                "display_name": "系统ID",
                                "field_type": "string",
                            },
                            "operator": "eq",
                            "filter": "bk_sops",
                        }
                    },
                    {
                        "condition": {
                            "field": {
                                "table": "t",
                                "raw_name": "action_id",
                                "display_name": "操作ID",
                                "field_type": "string",
                            },
                            "operator": "include",
                            "filters": ["create_task", "delete_task"],
                        }
                    },
                ],
            },
        )
        self.item_audit_log.data_sources.add(self.data_source_audit_log)

        # 创建配置项2：审计事件（无必须筛选字段）
        self.item_audit_event = LogSubscriptionItem.objects.create(
            subscription=self.subscription,
            name="审计事件配置项",
            description="查询审计事件",
            order=2,
            condition={
                "connector": "and",
                "conditions": [
                    {
                        "condition": {
                            "field": {
                                "table": "t",
                                "raw_name": "strategy_id",
                                "display_name": "策略ID",
                                "field_type": "int",
                            },
                            "operator": "include",
                            "filters": [1, 2, 3],
                        }
                    }
                ],
            },
        )
        self.item_audit_event.data_sources.add(self.data_source_audit_event)

        # Resource 实例
        self.resource = QueryLogSubscription()

    def test_get_subscription_success(self):
        """测试成功获取订阅配置"""
        subscription = self.resource._get_subscription(uuid.UUID(self.token))
        self.assertEqual(subscription.id, self.subscription.id)
        self.assertEqual(subscription.name, "测试订阅")

    def test_get_subscription_not_found(self):
        """测试订阅配置不存在"""
        fake_token = uuid.uuid4()
        with self.assertRaises(LogSubscriptionNotFound):
            self.resource._get_subscription(fake_token)

    def test_get_subscription_disabled(self):
        """测试订阅配置已禁用"""
        self.subscription.is_enabled = False
        self.subscription.save()

        with self.assertRaises(LogSubscriptionNotFound):
            self.resource._get_subscription(uuid.UUID(self.token))

    def test_get_subscription_deleted(self):
        """测试订阅配置已软删除"""
        self.subscription.is_deleted = True
        self.subscription.save()

        with self.assertRaises(LogSubscriptionNotFound):
            self.resource._get_subscription(uuid.UUID(self.token))

    def test_get_data_source_success(self):
        """测试成功获取数据源"""
        data_source = self.resource._get_data_source(self.subscription, "audit_log")
        self.assertEqual(data_source.source_id, "audit_log")

    def test_get_data_source_not_found(self):
        """测试数据源不存在"""
        with self.assertRaises(DataSourceNotFound):
            self.resource._get_data_source(self.subscription, "non_existent_source")

    def test_get_data_source_not_in_subscription(self):
        """测试数据源不在订阅配置中"""
        # 创建一个不在订阅中的数据源
        other_source = LogDataSource.objects.create(
            source_id="other_log",
            name="其他日志",
            namespace="other",
            bkbase_table_id="other_table",
            storage_type=StorageType.DORIS.value,
            time_field=TIMESTAMP_PARTITION_FIELD,
            is_enabled=True,
        )

        with self.assertRaises(DataSourceNotInSubscription):
            self.resource._get_data_source(self.subscription, other_source.source_id)

    def test_replace_table_name_leaf_condition(self):
        """测试替换叶子节点的表名（原地修改）"""
        from core.sql.model import Condition, Field, WhereCondition

        original_condition = WhereCondition(
            condition=Condition(
                field=Field(table="t", raw_name="user_id", display_name="用户ID", field_type="string"),
                operator="eq",
                filter="admin",
            )
        )

        # 原地修改，不返回新对象
        self.resource._replace_table_name(original_condition, "real_table")

        # 验证原对象已被修改
        self.assertEqual(original_condition.condition.field.table, "real_table")
        self.assertEqual(original_condition.condition.field.raw_name, "user_id")

    def test_replace_table_name_nested_conditions(self):
        """测试替换嵌套条件的表名（原地修改）"""
        from core.sql.model import Condition, Field, WhereCondition

        original_condition = WhereCondition(
            connector="and",
            conditions=[
                WhereCondition(
                    condition=Condition(
                        field=Field(table="t", raw_name="user_id", display_name="用户ID", field_type="string"),
                        operator="eq",
                        filter="admin",
                    )
                ),
                WhereCondition(
                    connector="or",
                    conditions=[
                        WhereCondition(
                            condition=Condition(
                                field=Field(table="t", raw_name="status", display_name="状态", field_type="int"),
                                operator="eq",
                                filter=1,
                            )
                        ),
                        WhereCondition(
                            condition=Condition(
                                field=Field(table="t", raw_name="status", display_name="状态", field_type="int"),
                                operator="eq",
                                filter=2,
                            )
                        ),
                    ],
                ),
            ],
        )

        # 原地修改，不返回新对象
        self.resource._replace_table_name(original_condition, "real_table")

        # 验证第一层条件
        self.assertEqual(original_condition.conditions[0].condition.field.table, "real_table")
        # 验证第二层嵌套条件
        self.assertEqual(original_condition.conditions[1].conditions[0].condition.field.table, "real_table")
        self.assertEqual(original_condition.conditions[1].conditions[1].condition.field.table, "real_table")

    def test_query_audit_log_sql_generation(self):
        """测试审计日志查询SQL生成（包含必须筛选字段）"""
        request_data = {
            "token": self.token,
            "source_id": "audit_log",
            "start_time": 1734589800000,  # 2024-12-19 15:50:00
            "end_time": 1734593400000,  # 2024-12-19 16:50:00
            "page": 1,
            "page_size": 10,
            "raw": True,  # 只生成SQL
        }

        validated_data = self.resource.validate_request_data(request_data)
        result = self.resource.perform_request(validated_data)

        # 验证基本结构
        self.assertEqual(result["page"], 1)
        self.assertEqual(result["page_size"], 10)
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["results"], [])

        # 验证查询SQL
        query_sql = result["query_sql"]
        expected_table = self.data_source_audit_log.get_table_name()

        # 验证SELECT *
        self.assertIn("SELECT *", query_sql)
        self.assertIn(f"FROM {expected_table}", query_sql)

        # 验证时间范围条件
        self.assertIn(
            f"`{expected_table}`.`{TIMESTAMP_PARTITION_FIELD}` BETWEEN 1734589800000 AND 1734593400000", query_sql
        )

        # 验证订阅配置的筛选条件
        self.assertIn(f"`{expected_table}`.`namespace`='bkaudit'", query_sql)
        self.assertIn(f"`{expected_table}`.`system_id`='bk_sops'", query_sql)
        self.assertIn(f"`{expected_table}`.`action_id` IN ('create_task','delete_task')", query_sql)

        # 验证排序和分页
        self.assertIn(f"ORDER BY `{expected_table}`.`{TIMESTAMP_PARTITION_FIELD}` DESC", query_sql)
        self.assertIn("LIMIT 10", query_sql)

        # 验证COUNT SQL
        count_sql = result["count_sql"]
        self.assertIn("SELECT COUNT(*) `count`", count_sql)
        self.assertIn(f"FROM {expected_table}", count_sql)
        self.assertIn("LIMIT 1", count_sql)

    def test_query_audit_event_sql_generation(self):
        """测试审计事件查询SQL生成（无必须筛选字段）"""
        request_data = {
            "token": self.token,
            "source_id": "audit_event",
            "start_time": 1734589800000,
            "end_time": 1734593400000,
            "page": 2,
            "page_size": 20,
            "raw": True,
        }

        validated_data = self.resource.validate_request_data(request_data)
        result = self.resource.perform_request(validated_data)

        query_sql = result["query_sql"]
        expected_table = self.data_source_audit_event.get_table_name()

        # 验证SELECT *
        self.assertIn("SELECT *", query_sql)
        self.assertIn(f"FROM {expected_table}", query_sql)

        # 验证时间范围
        self.assertIn(
            f"`{expected_table}`.`{TIMESTAMP_PARTITION_FIELD}` BETWEEN 1734589800000 AND 1734593400000", query_sql
        )

        # 验证订阅配置的筛选条件
        self.assertIn(f"`{expected_table}`.`strategy_id` IN (1,2,3)", query_sql)

        # 验证分页（第2页，每页20条，offset=20）
        self.assertIn("LIMIT 20 OFFSET 20", query_sql)

    def test_query_with_custom_fields(self):
        """测试自定义返回字段"""
        request_data = {
            "token": self.token,
            "source_id": "audit_log",
            "start_time": 1734589800000,
            "end_time": 1734593400000,
            "page": 1,
            "page_size": 10,
            "fields": ["namespace", "system_id", "action_id", "username"],
            "raw": True,
        }

        validated_data = self.resource.validate_request_data(request_data)
        result = self.resource.perform_request(validated_data)

        query_sql = result["query_sql"]
        expected_table = self.data_source_audit_log.get_table_name()

        # 验证SELECT指定字段（不是 SELECT *）
        self.assertNotIn("SELECT *", query_sql)
        self.assertIn(f"`{expected_table}`.`namespace`", query_sql)
        self.assertIn(f"`{expected_table}`.`system_id`", query_sql)
        self.assertIn(f"`{expected_table}`.`action_id`", query_sql)
        self.assertIn(f"`{expected_table}`.`username`", query_sql)

    def test_query_with_custom_filters(self):
        """测试自定义筛选条件"""
        request_data = {
            "token": self.token,
            "source_id": "audit_log",
            "start_time": 1734589800000,
            "end_time": 1734593400000,
            "page": 1,
            "page_size": 10,
            "filters": {
                "connector": "and",
                "conditions": [
                    {
                        "condition": {
                            "field": {
                                "table": "t",  # 会被替换
                                "raw_name": "username",
                                "display_name": "用户名",
                                "field_type": "string",
                            },
                            "operator": "eq",
                            "filter": "admin",
                        }
                    },
                    {
                        "condition": {
                            "field": {
                                "table": "t",
                                "raw_name": "result_code",
                                "display_name": "结果码",
                                "field_type": "int",
                            },
                            "operator": "eq",
                            "filter": 200,  # 使用 200 而不是 0，避免 SQL 生成器的 bool(0) == False 问题
                        }
                    },
                ],
            },
            "raw": True,
        }

        validated_data = self.resource.validate_request_data(request_data)
        result = self.resource.perform_request(validated_data)

        query_sql = result["query_sql"]
        expected_table = self.data_source_audit_log.get_table_name()

        # 验证自定义筛选条件（表名已替换）
        self.assertIn(f"`{expected_table}`.`username`='admin'", query_sql)
        self.assertIn(f"`{expected_table}`.`result_code`=200", query_sql)

        # 验证原订阅条件仍然存在
        self.assertIn(f"`{expected_table}`.`namespace`='bkaudit'", query_sql)
        self.assertIn(f"`{expected_table}`.`system_id`='bk_sops'", query_sql)

    def test_query_with_multiple_items_same_source(self):
        """测试多个配置项指向同一数据源（OR逻辑）"""
        # 创建第二个配置项，也使用 audit_log
        item2 = LogSubscriptionItem.objects.create(
            subscription=self.subscription,
            name="审计日志配置项2",
            order=3,
            condition={
                "connector": "and",
                "conditions": [
                    {
                        "condition": {
                            "field": {
                                "table": "t",
                                "raw_name": "namespace",
                                "display_name": "命名空间",
                                "field_type": "string",
                            },
                            "operator": "eq",
                            "filter": "bkaudit",
                        }
                    },
                    {
                        "condition": {
                            "field": {
                                "table": "t",
                                "raw_name": "system_id",
                                "display_name": "系统ID",
                                "field_type": "string",
                            },
                            "operator": "eq",
                            "filter": "bk_itsm",  # 不同的system_id
                        }
                    },
                ],
            },
        )
        item2.data_sources.add(self.data_source_audit_log)

        request_data = {
            "token": self.token,
            "source_id": "audit_log",
            "start_time": 1734589800000,
            "end_time": 1734593400000,
            "page": 1,
            "page_size": 10,
            "raw": True,
        }

        validated_data = self.resource.validate_request_data(request_data)
        result = self.resource.perform_request(validated_data)

        query_sql = result["query_sql"]
        expected_table = self.data_source_audit_log.get_table_name()

        # 验证OR逻辑（两个配置项的条件用OR连接）
        # 应该包含两个不同的 system_id 条件
        self.assertIn(f"`{expected_table}`.`system_id`='bk_sops'", query_sql)
        self.assertIn(f"`{expected_table}`.`system_id`='bk_itsm'", query_sql)
        self.assertIn(" OR ", query_sql)

    def test_query_pagination(self):
        """测试分页参数"""
        test_cases = [
            (1, 10, "LIMIT 10"),  # 第1页，offset=0
            (2, 10, "LIMIT 10 OFFSET 10"),  # 第2页
            (3, 20, "LIMIT 20 OFFSET 40"),  # 第3页，每页20条
            (5, 50, "LIMIT 50 OFFSET 200"),  # 第5页，每页50条
        ]

        for page, page_size, expected_limit in test_cases:
            with self.subTest(page=page, page_size=page_size):
                request_data = {
                    "token": self.token,
                    "source_id": "audit_event",
                    "start_time": 1734589800000,
                    "end_time": 1734593400000,
                    "page": page,
                    "page_size": page_size,
                    "raw": True,
                }

                validated_data = self.resource.validate_request_data(request_data)
                result = self.resource.perform_request(validated_data)

                self.assertIn(expected_limit, result["query_sql"])

    def test_time_range_validation(self):
        """测试时间范围验证"""
        from bk_resource.exceptions import ValidateException

        # 测试开始时间大于结束时间
        request_data = {
            "token": self.token,
            "source_id": "audit_log",
            "start_time": 1734593400000,  # 结束时间
            "end_time": 1734589800000,  # 开始时间（反了）
            "page": 1,
            "page_size": 10,
        }

        with self.assertRaises(ValidateException):
            self.resource.validate_request_data(request_data)

        # 测试时间范围超过30天
        request_data = {
            "token": self.token,
            "source_id": "audit_log",
            "start_time": 1734589800000,
            "end_time": 1734589800000 + 31 * 24 * 60 * 60 * 1000,  # 31天
            "page": 1,
            "page_size": 10,
        }

        with self.assertRaises(ValidateException):
            self.resource.validate_request_data(request_data)

    def test_filters_with_keys_validation(self):
        """测试自定义筛选条件包含 keys 字段的校验"""
        from bk_resource.exceptions import ValidateException

        # 测试包含 keys 字段的筛选条件
        request_data = {
            "token": self.token,
            "source_id": "audit_log",
            "start_time": 1734589800000,
            "end_time": 1734593400000,
            "page": 1,
            "page_size": 10,
            "filters": {
                "connector": "and",
                "conditions": [
                    {
                        "condition": {
                            "field": {
                                "table": "t",
                                "raw_name": "event_id",
                                "display_name": "event_id",
                                "field_type": "string",
                                "keys": ["path", "to", "value"],  # 包含 keys 字段
                            },
                            "operator": "eq",
                            "filter": "test",
                        }
                    }
                ],
            },
        }

        with self.assertRaises(ValidateException) as context:
            self.resource.validate_request_data(request_data)

        # 验证错误消息包含 keys 相关提示
        error_message = str(context.exception)
        self.assertIn("keys", error_message.lower())

    def test_filters_without_keys_validation(self):
        """测试自定义筛选条件不包含 keys 字段时正常通过"""
        # 测试不包含 keys 字段的筛选条件（应该正常通过）
        request_data = {
            "token": self.token,
            "source_id": "audit_log",
            "start_time": 1734589800000,
            "end_time": 1734593400000,
            "page": 1,
            "page_size": 10,
            "filters": {
                "connector": "and",
                "conditions": [
                    {
                        "condition": {
                            "field": {
                                "table": "t",
                                "raw_name": "event_id",
                                "display_name": "event_id",
                                "field_type": "string",
                            },
                            "operator": "eq",
                            "filter": "test",
                        }
                    }
                ],
            },
        }

        # 应该正常通过验证
        validated_data = self.resource.validate_request_data(request_data)
        self.assertIn("filters", validated_data)
        self.assertEqual(validated_data["filters"]["connector"], "and")

    def test_filters_simplified_format(self):
        """测试简化格式的筛选条件（只提供 raw_name 和 field_type）"""
        # 使用简化格式：不提供 table 和 display_name
        request_data = {
            "token": self.token,
            "source_id": "audit_log",
            "start_time": 1734589800000,
            "end_time": 1734593400000,
            "page": 1,
            "page_size": 10,
            "filters": {
                "connector": "and",
                "conditions": [
                    {
                        "condition": {
                            "field": {
                                "raw_name": "username",
                                "field_type": "string",
                            },
                            "operator": "eq",
                            "filter": "admin",
                        }
                    }
                ],
            },
            "raw": True,
        }

        # 验证通过后，检查默认值是否被正确补充
        validated_data = self.resource.validate_request_data(request_data)
        self.assertIn("filters", validated_data)

        # 验证 field 对象已被补充默认值
        field = validated_data["filters"]["conditions"][0]["condition"]["field"]
        self.assertEqual(field["table"], "t")  # 默认值
        self.assertEqual(field["display_name"], "username")  # 默认为 raw_name
        self.assertEqual(field["raw_name"], "username")
        self.assertEqual(field["field_type"], "string")

        # 验证能正常生成 SQL
        result = self.resource.perform_request(validated_data)
        query_sql = result["query_sql"]
        expected_table = self.data_source_audit_log.get_table_name()

        # 验证筛选条件已正确应用（表名已替换）
        self.assertIn(f"`{expected_table}`.`username`='admin'", query_sql)

    def test_filters_simplified_format_nested(self):
        """测试嵌套条件中的简化格式"""
        # 测试嵌套的 conditions 中也能正确处理简化格式
        request_data = {
            "token": self.token,
            "source_id": "audit_log",
            "start_time": 1734589800000,
            "end_time": 1734593400000,
            "page": 1,
            "page_size": 10,
            "filters": {
                "connector": "or",
                "conditions": [
                    {
                        "connector": "and",
                        "conditions": [
                            {
                                "condition": {
                                    "field": {
                                        "raw_name": "username",
                                        "field_type": "string",
                                    },
                                    "operator": "eq",
                                    "filter": "admin",
                                }
                            },
                            {
                                "condition": {
                                    "field": {
                                        "raw_name": "result_code",
                                        "field_type": "int",
                                    },
                                    "operator": "eq",
                                    "filter": 200,
                                }
                            },
                        ],
                    },
                    {
                        "condition": {
                            "field": {
                                "raw_name": "action_id",
                                "field_type": "string",
                            },
                            "operator": "eq",
                            "filter": "create",
                        }
                    },
                ],
            },
            "raw": True,
        }

        validated_data = self.resource.validate_request_data(request_data)

        # 验证嵌套条件中的 field 都已补充默认值
        nested_conditions = validated_data["filters"]["conditions"][0]["conditions"]
        for cond in nested_conditions:
            field = cond["condition"]["field"]
            self.assertEqual(field["table"], "t")
            self.assertEqual(field["display_name"], field["raw_name"])

        # 验证外层条件也已补充默认值
        outer_field = validated_data["filters"]["conditions"][1]["condition"]["field"]
        self.assertEqual(outer_field["table"], "t")
        self.assertEqual(outer_field["display_name"], "action_id")

        # 验证能正常生成 SQL
        result = self.resource.perform_request(validated_data)
        query_sql = result["query_sql"]
        expected_table = self.data_source_audit_log.get_table_name()

        # 验证所有筛选条件都已正确应用
        self.assertIn(f"`{expected_table}`.`username`='admin'", query_sql)
        self.assertIn(f"`{expected_table}`.`result_code`=200", query_sql)
        self.assertIn(f"`{expected_table}`.`action_id`='create'", query_sql)

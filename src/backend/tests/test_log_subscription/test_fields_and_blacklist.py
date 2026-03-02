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

from unittest.mock import patch

from django.test import TestCase

from api.bk_base.constants import StorageType
from apps.meta.models import GlobalMetaConfig
from services.web.log_subscription.constants import (
    GLOBAL_FIELD_BLACKLIST_SOURCE_ID,
    LOG_SUBSCRIPTION_FIELD_BLACKLIST_KEY,
)
from services.web.log_subscription.exceptions import FieldNotAllowed
from services.web.log_subscription.models import (
    LogDataSource,
    LogSubscription,
    LogSubscriptionItem,
)
from services.web.log_subscription.resources.subscription import QueryLogSubscription
from services.web.query.constants import TIMESTAMP_PARTITION_FIELD


class TestDataSourceFields(TestCase):
    """测试数据源 fields 字段功能"""

    def setUp(self):
        """准备测试数据"""
        self.test_user = "test_user"

        # 创建数据源：带有字段限制
        self.data_source_with_fields = LogDataSource.objects.create(
            source_id="audit_log_with_fields",
            name="带字段限制的审计日志",
            description="测试字段限制功能",
            namespace="bkaudit",
            bkbase_table_id="5000448_bklog_audit_with_fields",
            storage_type=StorageType.DORIS.value,
            time_field=TIMESTAMP_PARTITION_FIELD,
            fields=["event_id", "username", "action_id", "system_id", "start_time"],
            is_enabled=True,
            created_by=self.test_user,
            updated_by=self.test_user,
        )

        # 创建数据源：无字段限制
        self.data_source_without_fields = LogDataSource.objects.create(
            source_id="audit_log_without_fields",
            name="无字段限制的审计日志",
            description="测试无字段限制功能",
            namespace="bkaudit",
            bkbase_table_id="5000448_bklog_audit_without_fields",
            storage_type=StorageType.DORIS.value,
            time_field=TIMESTAMP_PARTITION_FIELD,
            fields=[],
            is_enabled=True,
            created_by=self.test_user,
            updated_by=self.test_user,
        )

        # 创建订阅配置
        self.subscription = LogSubscription.objects.create(
            name="测试字段限制订阅",
            description="测试字段限制功能",
            is_enabled=True,
            created_by=self.test_user,
            updated_by=self.test_user,
        )
        self.token = self.subscription.token

        # 创建配置项：关联带字段限制的数据源
        self.item_with_fields = LogSubscriptionItem.objects.create(
            subscription=self.subscription,
            name="带字段限制配置项",
            order=1,
            condition={},
            created_by=self.test_user,
            updated_by=self.test_user,
        )
        self.item_with_fields.data_sources.add(self.data_source_with_fields)

        # 创建配置项：关联无字段限制的数据源
        self.item_without_fields = LogSubscriptionItem.objects.create(
            subscription=self.subscription,
            name="无字段限制配置项",
            order=2,
            condition={},
            created_by=self.test_user,
            updated_by=self.test_user,
        )
        self.item_without_fields.data_sources.add(self.data_source_without_fields)

        # Resource 实例
        self.resource = QueryLogSubscription()

    def test_data_source_fields_default_empty(self):
        """测试数据源 fields 字段默认为空列表"""
        source = LogDataSource.objects.create(
            source_id="test_default_fields",
            name="测试默认字段",
            bkbase_table_id="test_table",
            storage_type=StorageType.DORIS.value,
            created_by=self.test_user,
            updated_by=self.test_user,
        )
        self.assertEqual(source.fields, [])

    def test_data_source_fields_with_list(self):
        """测试数据源 fields 字段配置列表"""
        self.assertEqual(
            self.data_source_with_fields.fields,
            ["event_id", "username", "action_id", "system_id", "start_time"],
        )

    def test_build_select_fields_no_custom_no_config(self):
        """测试构建字段列表：无自定义字段，数据源无字段限制 -> SELECT *"""
        fields = self.resource._build_select_fields(
            data_source=self.data_source_without_fields,
            custom_fields=None,
        )
        self.assertEqual(fields, [])

    def test_build_select_fields_no_custom_with_config(self):
        """测试构建字段列表：无自定义字段，数据源有字段限制 -> 使用数据源配置字段"""
        fields = self.resource._build_select_fields(
            data_source=self.data_source_with_fields,
            custom_fields=None,
        )
        self.assertEqual(len(fields), 5)
        field_names = [f.raw_name for f in fields]
        self.assertEqual(field_names, ["event_id", "username", "action_id", "system_id", "start_time"])

    def test_build_select_fields_custom_within_allowed(self):
        """测试构建字段列表：自定义字段在允许范围内 -> 使用自定义字段"""
        custom_fields = ["event_id", "username"]
        fields = self.resource._build_select_fields(
            data_source=self.data_source_with_fields,
            custom_fields=custom_fields,
        )
        self.assertEqual(len(fields), 2)
        field_names = [f.raw_name for f in fields]
        self.assertEqual(field_names, ["event_id", "username"])

    def test_build_select_fields_custom_not_in_allowed(self):
        """测试构建字段列表：自定义字段不在允许范围内 -> 抛出异常"""
        custom_fields = ["event_id", "secret_field", "password"]
        with self.assertRaises(FieldNotAllowed) as context:
            self.resource._build_select_fields(
                data_source=self.data_source_with_fields,
                custom_fields=custom_fields,
            )
        exc = context.exception
        self.assertEqual(set(exc.fields), {"secret_field", "password"})
        self.assertEqual(exc.source_id, "audit_log_with_fields")
        self.assertEqual(exc.allowed_fields, ["event_id", "username", "action_id", "system_id", "start_time"])

    def test_build_select_fields_custom_with_no_config(self):
        """测试构建字段列表：自定义字段，数据源无字段限制 -> 使用自定义字段"""
        custom_fields = ["any_field", "another_field"]
        fields = self.resource._build_select_fields(
            data_source=self.data_source_without_fields,
            custom_fields=custom_fields,
        )
        self.assertEqual(len(fields), 2)
        field_names = [f.raw_name for f in fields]
        self.assertEqual(field_names, ["any_field", "another_field"])

    def test_query_with_custom_fields_in_allowed(self):
        """测试查询：自定义字段在允许范围内 -> SQL 包含指定字段"""
        request_data = {
            "token": self.token,
            "source_id": "audit_log_with_fields",
            "start_time": 1734589800000,
            "end_time": 1734593400000,
            "page": 1,
            "page_size": 10,
            "fields": ["event_id", "username"],
            "raw": True,
        }

        validated_data = self.resource.validate_request_data(request_data)
        result = self.resource.perform_request(validated_data)

        query_sql = result["query_sql"]
        count_sql = result["count_sql"]

        # 验证 query_sql 结构
        self.assertTrue(query_sql.startswith("SELECT "))
        self.assertNotIn("SELECT *", query_sql)
        self.assertIn("`event_id`", query_sql)
        self.assertIn("`username`", query_sql)
        self.assertNotIn("`action_id`", query_sql.split("FROM")[0])  # 不在 SELECT 子句中
        self.assertIn("5000448_bklog_audit_with_fields.doris", query_sql)
        self.assertIn("WHERE", query_sql)
        self.assertIn("BETWEEN 1734589800000 AND 1734593400000", query_sql)
        self.assertIn("ORDER BY", query_sql)
        self.assertIn("LIMIT 10", query_sql)

        # 验证 count_sql 结构
        self.assertIn("SELECT COUNT(*)", count_sql)
        self.assertIn("5000448_bklog_audit_with_fields.doris", count_sql)
        self.assertIn("BETWEEN 1734589800000 AND 1734593400000", count_sql)

    def test_query_with_custom_fields_not_in_allowed(self):
        """测试查询：自定义字段不在允许范围内 -> 抛出 FieldNotAllowed 异常"""
        request_data = {
            "token": self.token,
            "source_id": "audit_log_with_fields",
            "start_time": 1734589800000,
            "end_time": 1734593400000,
            "page": 1,
            "page_size": 10,
            "fields": ["event_id", "secret_field"],
            "raw": True,
        }

        validated_data = self.resource.validate_request_data(request_data)
        with self.assertRaises(FieldNotAllowed) as context:
            self.resource.perform_request(validated_data)

        exc = context.exception
        self.assertEqual(exc.fields, ["secret_field"])
        self.assertEqual(exc.source_id, "audit_log_with_fields")

    def test_query_without_custom_fields_uses_config(self):
        """测试查询：无自定义字段时使用数据源配置字段 -> SQL 包含所有配置字段"""
        request_data = {
            "token": self.token,
            "source_id": "audit_log_with_fields",
            "start_time": 1734589800000,
            "end_time": 1734593400000,
            "page": 1,
            "page_size": 10,
            "raw": True,
        }

        validated_data = self.resource.validate_request_data(request_data)
        result = self.resource.perform_request(validated_data)

        query_sql = result["query_sql"]
        select_clause = query_sql.split("FROM")[0]

        # 验证 SELECT 子句包含所有配置字段
        self.assertNotIn("SELECT *", query_sql)
        self.assertIn("`event_id`", select_clause)
        self.assertIn("`username`", select_clause)
        self.assertIn("`action_id`", select_clause)
        self.assertIn("`system_id`", select_clause)
        self.assertIn("`start_time`", select_clause)

        # 验证其他 SQL 结构
        self.assertIn("5000448_bklog_audit_with_fields.doris", query_sql)
        self.assertIn("BETWEEN 1734589800000 AND 1734593400000", query_sql)

    def test_query_without_fields_config_uses_star(self):
        """测试查询：数据源无字段配置时使用 SELECT *"""
        request_data = {
            "token": self.token,
            "source_id": "audit_log_without_fields",
            "start_time": 1734589800000,
            "end_time": 1734593400000,
            "page": 1,
            "page_size": 10,
            "raw": True,
        }

        validated_data = self.resource.validate_request_data(request_data)
        result = self.resource.perform_request(validated_data)

        query_sql = result["query_sql"]
        count_sql = result["count_sql"]

        # 验证使用 SELECT *
        self.assertIn("SELECT *", query_sql)
        self.assertIn("5000448_bklog_audit_without_fields.doris", query_sql)
        self.assertIn("BETWEEN 1734589800000 AND 1734593400000", query_sql)

        # 验证 count_sql
        self.assertIn("SELECT COUNT(*)", count_sql)


class TestFieldBlacklist(TestCase):
    """测试全局字段黑名单功能"""

    def setUp(self):
        """准备测试数据"""
        self.test_user = "test_user"

        self.data_source = LogDataSource.objects.create(
            source_id="audit_log_blacklist_test",
            name="黑名单测试数据源",
            namespace="bkaudit",
            bkbase_table_id="5000448_bklog_blacklist_test",
            storage_type=StorageType.DORIS.value,
            time_field=TIMESTAMP_PARTITION_FIELD,
            is_enabled=True,
            created_by=self.test_user,
            updated_by=self.test_user,
        )

        self.subscription = LogSubscription.objects.create(
            name="测试黑名单订阅",
            is_enabled=True,
            created_by=self.test_user,
            updated_by=self.test_user,
        )
        self.token = self.subscription.token

        self.item = LogSubscriptionItem.objects.create(
            subscription=self.subscription,
            name="黑名单测试配置项",
            order=1,
            condition={},
            created_by=self.test_user,
            updated_by=self.test_user,
        )
        self.item.data_sources.add(self.data_source)

        self.resource = QueryLogSubscription()

    def test_filter_blacklist_fields_no_config(self):
        """测试黑名单过滤：无黑名单配置 -> 返回原始结果"""
        input_results = [
            {"event_id": "1", "username": "admin", "password": "secret"},
            {"event_id": "2", "username": "user", "password": "pass"},
        ]
        expected_results = [
            {"event_id": "1", "username": "admin", "password": "secret"},
            {"event_id": "2", "username": "user", "password": "pass"},
        ]

        with patch.object(GlobalMetaConfig, "get", return_value={}):
            filtered = self.resource._filter_blacklist_fields(input_results, "test_source")

        self.assertEqual(filtered, expected_results)

    def test_filter_blacklist_fields_global(self):
        """测试黑名单过滤：全局黑名单 -> 过滤全局黑名单字段"""
        input_results = [
            {"event_id": "1", "username": "admin", "snapshot_user_info": {"name": "Admin"}},
            {"event_id": "2", "username": "user", "snapshot_user_info": {"name": "User"}},
        ]
        expected_results = [
            {"event_id": "1", "username": "admin"},
            {"event_id": "2", "username": "user"},
        ]

        blacklist_config = {
            GLOBAL_FIELD_BLACKLIST_SOURCE_ID: ["snapshot_user_info"],
        }

        with patch.object(GlobalMetaConfig, "get", return_value=blacklist_config):
            filtered = self.resource._filter_blacklist_fields(input_results, "test_source")

        self.assertEqual(filtered, expected_results)

    def test_filter_blacklist_fields_source_specific(self):
        """测试黑名单过滤：数据源特定黑名单 -> 只过滤该数据源的黑名单字段"""
        input_results = [
            {"event_id": "1", "username": "admin", "secret_field": "secret1"},
            {"event_id": "2", "username": "user", "secret_field": "secret2"},
        ]
        expected_results = [
            {"event_id": "1", "username": "admin"},
            {"event_id": "2", "username": "user"},
        ]

        blacklist_config = {
            "test_source": ["secret_field"],
        }

        with patch.object(GlobalMetaConfig, "get", return_value=blacklist_config):
            filtered = self.resource._filter_blacklist_fields(input_results, "test_source")

        self.assertEqual(filtered, expected_results)

    def test_filter_blacklist_fields_combined(self):
        """测试黑名单过滤：全局 + 数据源特定黑名单 -> 两者都过滤"""
        input_results = [
            {
                "event_id": "1",
                "username": "admin",
                "snapshot_user_info": {"name": "Admin"},
                "secret_field": "secret1",
            },
        ]
        expected_results = [
            {"event_id": "1", "username": "admin"},
        ]

        blacklist_config = {
            GLOBAL_FIELD_BLACKLIST_SOURCE_ID: ["snapshot_user_info"],
            "test_source": ["secret_field"],
        }

        with patch.object(GlobalMetaConfig, "get", return_value=blacklist_config):
            filtered = self.resource._filter_blacklist_fields(input_results, "test_source")

        self.assertEqual(filtered, expected_results)

    def test_filter_blacklist_fields_missing_field(self):
        """测试黑名单过滤：数据中不存在黑名单字段 -> 不报错，保留原有字段"""
        input_results = [
            {"event_id": "1", "username": "admin"},
        ]
        expected_results = [
            {"event_id": "1", "username": "admin"},
        ]

        blacklist_config = {
            GLOBAL_FIELD_BLACKLIST_SOURCE_ID: ["snapshot_user_info", "non_existent_field"],
        }

        with patch.object(GlobalMetaConfig, "get", return_value=blacklist_config):
            filtered = self.resource._filter_blacklist_fields(input_results, "test_source")

        self.assertEqual(filtered, expected_results)

    def test_filter_blacklist_fields_other_source_not_affected(self):
        """测试黑名单过滤：其他数据源的黑名单不影响当前数据源"""
        input_results = [
            {"event_id": "1", "username": "admin", "secret_field": "secret1"},
        ]
        expected_results = [
            {"event_id": "1", "username": "admin", "secret_field": "secret1"},
        ]

        blacklist_config = {
            "other_source": ["secret_field"],
        }

        with patch.object(GlobalMetaConfig, "get", return_value=blacklist_config):
            filtered = self.resource._filter_blacklist_fields(input_results, "test_source")

        self.assertEqual(filtered, expected_results)

    def test_filter_blacklist_fields_empty_results(self):
        """测试黑名单过滤：空结果列表 -> 返回空列表"""
        input_results = []
        expected_results = []

        blacklist_config = {
            GLOBAL_FIELD_BLACKLIST_SOURCE_ID: ["snapshot_user_info"],
        }

        with patch.object(GlobalMetaConfig, "get", return_value=blacklist_config):
            filtered = self.resource._filter_blacklist_fields(input_results, "test_source")

        self.assertEqual(filtered, expected_results)


class TestFieldNotAllowedException(TestCase):
    """测试 FieldNotAllowed 异常"""

    def test_field_not_allowed_exception_attributes(self):
        """测试异常属性"""
        exc = FieldNotAllowed(
            fields=["field1", "field2"],
            source_id="test_source",
            allowed_fields=["allowed1", "allowed2"],
        )
        self.assertEqual(exc.fields, ["field1", "field2"])
        self.assertEqual(exc.source_id, "test_source")
        self.assertEqual(exc.allowed_fields, ["allowed1", "allowed2"])

    def test_field_not_allowed_exception_message(self):
        """测试异常消息格式"""
        exc = FieldNotAllowed(
            fields=["field1", "field2"],
            source_id="test_source",
            allowed_fields=["allowed1", "allowed2"],
        )
        expected_message = "[2907004] 请求字段 field1, field2 不在数据源 test_source " "允许的字段范围内，允许的字段: allowed1, allowed2"
        self.assertEqual(str(exc), expected_message)

    def test_field_not_allowed_exception_status_code(self):
        """测试异常状态码"""
        exc = FieldNotAllowed(
            fields=["field1"],
            source_id="test_source",
            allowed_fields=["allowed1"],
        )
        self.assertEqual(exc.STATUS_CODE, 400)

    def test_field_not_allowed_exception_error_code(self):
        """测试异常错误码"""
        self.assertEqual(FieldNotAllowed.ERROR_CODE, "004")


class TestBlacklistConstants(TestCase):
    """测试黑名单相关常量"""

    def test_global_blacklist_source_id_constant(self):
        """测试全局黑名单源ID常量"""
        self.assertEqual(GLOBAL_FIELD_BLACKLIST_SOURCE_ID, "__ALL__")

    def test_blacklist_config_key_constant(self):
        """测试黑名单配置键常量"""
        self.assertEqual(LOG_SUBSCRIPTION_FIELD_BLACKLIST_KEY, "log_subscription_field_blacklist")

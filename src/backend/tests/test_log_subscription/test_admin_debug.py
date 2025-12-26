# -*- coding: utf-8 -*-
"""
日志订阅 Admin 调试界面测试
"""

from django.test import TestCase
from django.urls import reverse

from services.web.log_subscription.models import (
    LogDataSource,
    LogSubscription,
    LogSubscriptionItem,
)


class LogSubscriptionAdminDebugTest(TestCase):
    """测试 Admin 调试界面"""

    def setUp(self):
        """设置测试数据"""
        self.test_user = "test_user"

        # 创建数据源
        self.source = LogDataSource.objects.create(
            source_id="test_source",
            name="测试数据源",
            bkbase_table_id="591_test_table",
            storage_type="doris",
            time_field="dtEventTimeStamp",
            is_enabled=True,
            created_by=self.test_user,
            updated_by=self.test_user,
        )

        # 创建订阅
        self.subscription = LogSubscription.objects.create(
            name="测试订阅", description="测试描述", is_enabled=True, created_by=self.test_user, updated_by=self.test_user
        )

        # 创建配置项
        self.item = LogSubscriptionItem.objects.create(
            subscription=self.subscription,
            name="配置项1",
            description="测试配置项",
            condition={
                "condition": {
                    "field": {
                        "table": "t",
                        "raw_name": "system_id",
                        "display_name": "system_id",
                        "field_type": "string",
                    },
                    "operator": "eq",
                    "filters": ["test_system"],
                }
            },
            created_by=self.test_user,
            updated_by=self.test_user,
        )
        self.item.data_sources.add(self.source)

    def test_preview_url_exists(self):
        """测试预览 URL 是否存在"""
        # 构造预览 URL
        url = reverse(
            "admin:log_subscription_logsubscription_preview_sql",
            args=[self.subscription.pk],
        )
        self.assertIsNotNone(url)
        self.assertIn("preview-sql", url)

    def test_subscription_has_data_sources(self):
        """测试订阅是否有关联的数据源"""
        data_sources = []
        for item in self.subscription.items.all():
            for source in item.data_sources.all():
                if source not in data_sources:
                    data_sources.append(source)

        self.assertEqual(len(data_sources), 1)
        self.assertEqual(data_sources[0].source_id, "test_source")

    def test_api_url_format(self):
        """测试 API URL 格式"""
        api_url = "/api/v1/log_subscription/query/"
        self.assertTrue(api_url.startswith("/api/v1/"))
        self.assertTrue(api_url.endswith("/"))

    def test_empty_required_filter_fields_no_validation(self):
        """测试：当 required_filter_fields 为空时，不校验 condition"""
        # 创建一个没有必须筛选字段的数据源
        source_no_required = LogDataSource.objects.create(
            source_id="source_no_required",
            name="无必须筛选字段数据源",
            bkbase_table_id="591_test_table_2",
            storage_type="doris",
            time_field="dtEventTimeStamp",
            required_filter_fields=[],  # 空列表
            is_enabled=True,
            created_by=self.test_user,
            updated_by=self.test_user,
        )

        # 创建一个没有筛选条件的配置项
        item_no_condition = LogSubscriptionItem.objects.create(
            subscription=self.subscription,
            name="无筛选条件配置项",
            description="测试：required_filter_fields 为空时允许不配置 condition",
            condition={},  # 空条件
            created_by=self.test_user,
            updated_by=self.test_user,
        )
        item_no_condition.data_sources.add(source_no_required)

        # 应该能够正常验证，不抛出异常
        try:
            item_no_condition.validate_condition_with_sources()
            validation_passed = True
        except Exception:
            validation_passed = False

        self.assertTrue(validation_passed, "当 required_filter_fields 为空时，应该允许不配置 condition")

    def test_nonempty_required_filter_fields_validation(self):
        """测试：当 required_filter_fields 不为空时，必须校验 condition"""
        from django.core.exceptions import ValidationError

        # 创建一个有必须筛选字段的数据源
        source_with_required = LogDataSource.objects.create(
            source_id="source_with_required",
            name="有必须筛选字段数据源",
            bkbase_table_id="591_test_table_3",
            storage_type="doris",
            time_field="dtEventTimeStamp",
            required_filter_fields=["system_id", "namespace"],  # 必须筛选字段
            is_enabled=True,
            created_by=self.test_user,
            updated_by=self.test_user,
        )

        # 创建一个没有筛选条件的配置项
        item_no_condition = LogSubscriptionItem.objects.create(
            subscription=self.subscription,
            name="缺少必须筛选字段配置项",
            description="测试：required_filter_fields 不为空时不允许空 condition",
            condition={},  # 空条件
            created_by=self.test_user,
            updated_by=self.test_user,
        )
        item_no_condition.data_sources.add(source_with_required)

        # 应该抛出 ValidationError
        with self.assertRaises(ValidationError) as context:
            item_no_condition.validate_condition_with_sources()

        self.assertIn("condition", str(context.exception))
        self.assertIn("必须筛选字段", str(context.exception))

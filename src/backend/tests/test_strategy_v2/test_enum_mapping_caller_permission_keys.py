# -*- coding: utf-8 -*-
from unittest import mock

from bk_resource import resource
from django.utils import timezone

from apps.meta.models import EnumMappingRelatedType
from core.exceptions import PermissionException
from tests.base import TestCase


class TestStrategyEnumMappingKeysWithCaller(TestCase):
    def setUp(self):
        from services.web.strategy_v2.models import Strategy

        # 创建策略并写入一组枚举集合
        self.strategy = Strategy.objects.create(namespace=self.namespace, strategy_name="s_for_enum_keys")
        self.collection_id = "status_collection_test_keys"
        self.mappings = [
            {"key": "1", "name": "未处理"},
            {"key": "2", "name": "已处理"},
        ]

        resource.meta.batch_update_enum_mappings(
            collection_id=self.collection_id,
            mappings=self.mappings,
            related_type=EnumMappingRelatedType.STRATEGY.value,
            related_object_id=self.strategy.strategy_id,
        )

    @mock.patch("services.web.risk.permissions.RiskViewPermission.has_risk_permission", return_value=True)
    def test_enum_mapping_keys_query_with_caller_allowed(self, _):
        """
        当 caller 为风险，且风险归属于当前策略时，按键查询应放行。
        """
        from services.web.risk.models import Risk

        # 创建归属于该策略的风险
        risk = Risk.objects.create(
            raw_event_id="e1",
            strategy_id=self.strategy.strategy_id,
            event_time=timezone.now(),
        )

        result = resource.strategy_v2.get_strategy_enum_mapping_by_collection_keys(
            collection_keys=[{"collection_id": self.collection_id, "key": "1"}],
            related_object_id=self.strategy.strategy_id,
            caller_resource_type="risk",
            caller_resource_id=risk.risk_id,
        )
        self.assertEqual(result, [{"collection_id": self.collection_id, "key": "1", "name": "未处理"}])

    @mock.patch("services.web.risk.permissions.RiskViewPermission.has_risk_permission", return_value=True)
    def test_enum_mapping_keys_query_with_caller_relation_mismatch(self, _):
        """
        当 caller 为风险，但该风险不属于当前策略时，应抛出归属校验错误。
        """
        from services.web.risk.models import Risk
        from services.web.strategy_v2.models import Strategy

        # 创建另一个策略与风险，使其与查询策略不匹配
        other_strategy = Strategy.objects.create(namespace=self.namespace, strategy_name="other_keys")
        other_risk = Risk.objects.create(
            raw_event_id="e2",
            strategy_id=other_strategy.strategy_id,
            event_time=timezone.now(),
        )

        with self.assertRaises(PermissionException):
            resource.strategy_v2.get_strategy_enum_mapping_by_collection_keys(
                collection_keys=[{"collection_id": self.collection_id, "key": "1"}],
                related_object_id=self.strategy.strategy_id,
                caller_resource_type="risk",
                caller_resource_id=other_risk.risk_id,
            )

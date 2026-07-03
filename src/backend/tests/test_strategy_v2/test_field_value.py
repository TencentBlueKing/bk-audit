# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
"""

from types import SimpleNamespace
from unittest import mock

from apps.meta.constants import SystemSourceTypeEnum
from apps.meta.models import Action, ResourceType, System
from services.web.strategy_v2.resources import GetStrategyFieldValue
from services.web.strategy_v2.utils.field_value import FieldValueHandler
from tests.base import TestCase


class FieldValueHandlerTest(TestCase):
    def setUp(self):
        super().setUp()
        self.system = System.objects.create(
            namespace=self.namespace,
            system_id="bk_valid",
            source_type=SystemSourceTypeEnum.IAM_V3.value,
            instance_id="bk_valid",
            name="有效系统",
        )
        ResourceType.objects.create(system_id=self.system.system_id, resource_type_id="host", name="主机")
        Action.objects.create(system_id=self.system.system_id, action_id="view_host", name="查看主机")

        ResourceType.objects.create(
            system_id="iam_v4_cmdb_inspection",
            resource_type_id="biz",
            name="业务",
        )
        Action.objects.create(
            system_id="iam_v4_cmdb_inspection",
            action_id="view_biz",
            name="查看业务",
        )

    @staticmethod
    def _child_values(values):
        return {child["value"] for group in values for child in group.get("children", [])}

    def test_resource_type_field_value_skips_orphan_system_data(self):
        values = FieldValueHandler(field_name="resource_type_id", namespace=self.namespace).values

        self.assertIn("host", self._child_values(values))
        self.assertNotIn("biz", self._child_values(values))

    def test_action_field_value_skips_orphan_system_data(self):
        values = FieldValueHandler(field_name="action_id", namespace=self.namespace).values

        self.assertIn("view_host", self._child_values(values))
        self.assertNotIn("view_biz", self._child_values(values))

    @mock.patch("services.web.strategy_v2.resources.get_local_request")
    @mock.patch("services.web.strategy_v2.resources.ActionPermission")
    def test_get_strategy_field_value_request_skips_orphan_system_data(
        self,
        mock_action_permission,
        mock_get_local_request,
    ):
        mock_action_permission.return_value.has_permission.return_value = True
        mock_get_local_request.return_value = SimpleNamespace(
            COOKIES={"bk_token": "fake"},
            user=SimpleNamespace(username="tester"),
        )

        values = GetStrategyFieldValue().request(
            {
                "namespace": self.namespace,
                "field_name": "resource_type_id",
            }
        )

        self.assertIn("host", self._child_values(values))
        self.assertNotIn("biz", self._child_values(values))

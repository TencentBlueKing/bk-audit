"""用户快照私密字段不连带遮罩上游原文，其他规则继续按原有权限执行。"""

from copy import deepcopy
from unittest import mock

from apps.meta.constants import (
    SENSITIVE_REPLACE_VALUE,
    SensitiveResourceTypeEnum,
    SensitiveUserData,
)
from apps.meta.models import SensitiveObject
from services.web.query.utils.formatter import HitsFormatter
from tests.base import TestCase


class TestUserSnapshotRawLogBoundary(TestCase):
    def setUp(self):
        self.rule = SensitiveObject(
            system_id=SensitiveUserData.SYSTEM_ID,
            resource_type=SensitiveResourceTypeEnum.RESOURCE.value,
            resource_id=SensitiveUserData.RESOURCE_ID,
            is_private=True,
            fields=[{"field_name": "snapshot_user_info.secret"}],
        )
        self.row = {
            "system_id": "example-system",
            "resource_type_id": "document",
            "snapshot_user_info": {"secret": "synthetic-private", "public": "visible"},
            "extend_data": {"secret": "business-value", "public": "visible"},
            "log": '{ "secret":"upstream-value", "action":"read" }',
        }
        # 仅替代与本次边界无关的加密运算，保留真实字段转换、规则匹配和删除。
        encrypt = mock.patch(
            "services.web.query.utils.formatter.asymmetric_cipher.encrypt", side_effect=lambda value: f"sealed:{value}"
        )
        encrypt.start()
        self.addCleanup(encrypt.stop)

    def format_row(self, row=None, rules=None):
        return HitsFormatter(deepcopy(self.row if row is None else row), [self.rule] if rules is None else rules).value

    def test_private_user_snapshot_is_removed_without_rewriting_upstream_content(self):
        """同名上游字段、纯文本及不同 JSON 结构均不属于快照规则的原文处理范围。"""
        for raw in (self.row["log"], "plain upstream text", '[{"secret":"upstream-value"}]', "", None):
            with self.subTest(raw=raw):
                result = self.format_row({**self.row, "log": raw})
                self.assertEqual(result["snapshot_user_info"], {"public": "sealed:visible"})
                self.assertEqual(result["extend_data"], {"secret": "business-value", "public": "visible"})
                self.assertEqual(result["log"], raw)

    def test_absent_snapshot_does_not_cause_global_rule_to_mask_raw_log(self):
        row = deepcopy(self.row)
        row.pop("snapshot_user_info")
        self.assertEqual(self.format_row(row), row)

    def test_private_entire_user_snapshot_does_not_mask_raw_log(self):
        self.rule.fields = [{"field_name": "snapshot_user_info"}]
        result = self.format_row()
        self.assertNotIn("snapshot_user_info", result)
        self.assertEqual(result["log"], self.row["log"])

    def test_ordinary_denied_rule_still_masks_raw_log_in_both_rule_orders(self):
        ordinary = SensitiveObject(
            system_id="example-system",
            resource_type=SensitiveResourceTypeEnum.RESOURCE.value,
            resource_id="document",
            fields=[{"field_name": "extend_data.secret", "default_value": "restricted"}],
        )
        for rules in ([ordinary, self.rule], [self.rule, ordinary]):
            with self.subTest(first=rules[0].is_private):
                result = self.format_row(rules=rules)
                self.assertEqual(result["snapshot_user_info"], {"public": "sealed:visible"})
                self.assertEqual(result["extend_data"], {"secret": "restricted", "public": "visible"})
                self.assertEqual(result["log"], SENSITIVE_REPLACE_VALUE)

    def test_authorized_ordinary_rule_preserves_raw_log_but_not_private_snapshot_field(self):
        ordinary = SensitiveObject(
            system_id=SensitiveUserData.SYSTEM_ID,
            resource_type=SensitiveResourceTypeEnum.RESOURCE.value,
            resource_id=SensitiveUserData.RESOURCE_ID,
            fields=[{"field_name": "snapshot_user_info.secret"}],
        )
        ordinary._has_permission = True
        result = self.format_row(rules=[ordinary, self.rule])
        self.assertEqual(result["snapshot_user_info"], {"public": "sealed:visible"})
        self.assertEqual(result["log"], self.row["log"])

    def test_mixed_private_rule_keeps_existing_raw_log_protection(self):
        self.rule.fields.append({"field_name": "extend_data.secret"})
        result = self.format_row()
        self.assertEqual(result["snapshot_user_info"], {"public": "sealed:visible"})
        self.assertEqual(result["extend_data"], {"public": "visible"})
        self.assertEqual(result["log"], SENSITIVE_REPLACE_VALUE)

    def test_private_rule_for_other_fields_still_masks_raw_log(self):
        for field in ("extend_data.secret", "snapshot_user_info_backup.secret", "log"):
            with self.subTest(field=field):
                self.rule.fields = [{"field_name": field}]
                result = self.format_row()
                self.assertEqual(result["log"], SENSITIVE_REPLACE_VALUE)

    def test_unmatched_private_snapshot_rule_does_not_remove_fields(self):
        self.rule.system_id = "another-system"
        self.rule.resource_id = "another-resource"
        result = self.format_row()
        self.assertEqual(
            result["snapshot_user_info"], {"secret": "sealed:synthetic-private", "public": "sealed:visible"}
        )
        self.assertEqual(result["log"], self.row["log"])

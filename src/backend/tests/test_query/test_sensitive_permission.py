# -*- coding: utf-8 -*-
from copy import deepcopy
from unittest import mock

from django.test import SimpleTestCase, override_settings

from apps.meta.constants import (
    SENSITIVE_REPLACE_VALUE,
    SensitiveResourceTypeEnum,
    SensitiveUserData,
)
from apps.meta.models import SensitiveObject
from services.web.query.resources.base import SearchDataParser
from services.web.query.utils.formatter import HitsFormatter
from tests.base import TestCase


class TestSensitiveRuleOrder(SimpleTestCase):
    """规则匹配只依赖脱敏前的行，不受其他规则遮罩或删除字段影响。"""

    def test_matching_uses_original_row_in_both_rule_orders(self):
        """条件字段被遮罩或删除后，原本命中的私密规则仍需执行。"""
        for field_name, resource_type, resource_id in (
            ("action_id", SensitiveResourceTypeEnum.ACTION.value, "view"),
            ("resource_type_id", SensitiveResourceTypeEnum.RESOURCE.value, "host"),
            ("system_id", SensitiveResourceTypeEnum.ACTION.value, "view"),
        ):
            for first_private in (False, True):
                for authorized in (False,) if first_private else (False, True):
                    for reverse in (False, True):
                        with self.subTest(
                            field=field_name, private=first_private, authorized=authorized, reverse=reverse
                        ):
                            first = SensitiveObject(
                                system_id="bk_log",
                                resource_type=SensitiveResourceTypeEnum.RESOURCE.value,
                                resource_id="host",
                                fields=[{"field_name": field_name}],
                                is_private=first_private,
                            )
                            first._has_permission = authorized
                            private = SensitiveObject(
                                system_id="bk_log",
                                resource_type=resource_type,
                                resource_id=resource_id,
                                fields=[{"field_name": "extend_data.secret"}],
                                is_private=True,
                            )
                            row = {
                                "system_id": "bk_log",
                                "resource_type_id": "host",
                                "action_id": "view",
                                "extend_data": {"secret": "raw-secret", "public": "visible"},
                                "log": "raw-secret",
                            }
                            expected = deepcopy(row)
                            expected["extend_data"] = {"public": "visible"}
                            expected["log"] = SENSITIVE_REPLACE_VALUE
                            if not authorized:
                                if first_private:
                                    expected.pop(field_name)
                                else:
                                    expected[field_name] = SENSITIVE_REPLACE_VALUE

                            rules = [private, first] if reverse else [first, private]
                            self.assertEqual(HitsFormatter(row, rules).value, expected)

    def test_masked_action_does_not_create_a_new_match(self):
        """替换值不能让原本不匹配的规则误删公开字段。"""
        first = SensitiveObject(
            system_id="bk_log",
            resource_type=SensitiveResourceTypeEnum.RESOURCE.value,
            resource_id="host",
            fields=[{"field_name": "action_id", "default_value": "other-action"}],
        )
        private = SensitiveObject(
            system_id="bk_log",
            resource_type=SensitiveResourceTypeEnum.ACTION.value,
            resource_id="other-action",
            fields=[{"field_name": "extend_data.public"}],
            is_private=True,
        )
        for rules in ([first, private], [private, first]):
            with self.subTest(order=[rule.resource_id for rule in rules]):
                result = HitsFormatter(
                    {
                        "system_id": "bk_log",
                        "resource_type_id": "host",
                        "action_id": "view",
                        "extend_data": {"public": "visible"},
                        "log": "raw-log",
                    },
                    rules,
                ).value
                self.assertEqual(
                    result,
                    {
                        "system_id": "bk_log",
                        "resource_type_id": "host",
                        "action_id": "other-action",
                        "extend_data": {"public": "visible"},
                        "log": SENSITIVE_REPLACE_VALUE,
                    },
                )


class TestSensitivePermission(TestCase):
    def test_private_sensitive_rule_removes_field_and_masks_raw_log(self):
        """私密规则删除结构化字段时，也必须隐藏可能包含原值的原始日志。"""

        SensitiveObject._objects.create(
            name="private secret",
            system_id="bk_log",
            resource_type=SensitiveResourceTypeEnum.RESOURCE.value,
            resource_id="host",
            fields=[{"field_name": "extend_data.secret"}],
            is_private=True,
        )

        result = SearchDataParser().parse_data(
            [
                {
                    "system_id": "bk_log",
                    "resource_type_id": "host",
                    "extend_data": {"secret": "raw-value", "public": "visible"},
                    "log": "payload raw-value",
                }
            ],
            username="admin",
            system_id="bk_log",
        )

        self.assertNotIn("secret", result[0]["extend_data"])
        self.assertEqual(result[0]["extend_data"]["public"], "visible")
        self.assertEqual(result[0]["log"], SENSITIVE_REPLACE_VALUE)

    def test_private_sensitive_rule_does_not_mask_unmatched_log(self):
        """私密规则不匹配当前资源时，不应扩大脱敏范围。"""

        SensitiveObject._objects.create(
            name="other resource secret",
            system_id="bk_log",
            resource_type=SensitiveResourceTypeEnum.RESOURCE.value,
            resource_id="other-resource",
            fields=[{"field_name": "extend_data.secret"}],
            is_private=True,
        )
        row = {
            "system_id": "bk_log",
            "resource_type_id": "host",
            "extend_data": {"secret": "visible"},
            "log": "payload visible",
        }

        result = SearchDataParser().parse_data([row], username="admin", system_id="bk_log")

        self.assertEqual(result[0]["extend_data"]["secret"], "visible")
        self.assertEqual(result[0]["log"], "payload visible")

    @mock.patch("services.web.query.resources.base.PermissionService")
    def test_authorized_sensitive_rule_preserves_structured_field_and_raw_log(self, mock_service):
        sensitive_object = SensitiveObject.objects.create(
            name="authorized secret",
            system_id="bk_log",
            resource_type=SensitiveResourceTypeEnum.RESOURCE.value,
            resource_id="host",
            fields=[{"field_name": "extend_data.secret"}],
        )
        mock_service.return_value.get_sensitive_object_permissions.return_value = {str(sensitive_object.id): True}

        result = SearchDataParser().parse_data(
            [
                {
                    "system_id": "bk_log",
                    "resource_type_id": "host",
                    "extend_data": {"secret": "visible"},
                    "log": "payload visible",
                }
            ],
            username="admin",
            system_id="bk_log",
        )

        self.assertEqual(result[0]["extend_data"]["secret"], "visible")
        self.assertEqual(result[0]["log"], "payload visible")

    @override_settings(IAM_PERMISSION_BACKEND="v3")
    @mock.patch("services.web.query.resources.base.get_request_username", return_value="admin")
    @mock.patch("services.web.query.resources.base.PermissionService")
    def test_sensitive_parser_uses_v3_sensitive_object_batch_permission(self, mock_service, _mock_username):
        sensitive_object = SensitiveObject.objects.create(
            name="secret_field",
            system_id="bk_log",
            resource_type=SensitiveResourceTypeEnum.RESOURCE.value,
            resource_id="host",
            fields=[{"field_name": "secret"}],
        )
        mock_service.return_value.get_sensitive_object_permissions.return_value = {str(sensitive_object.id): False}

        result = SearchDataParser().parse_data(
            [{"system_id": "bk_log", "resource_type_id": "host", "secret": "raw-value", "log": "raw-log"}]
        )

        self.assertEqual(result[0]["secret"], SENSITIVE_REPLACE_VALUE)
        self.assertEqual(result[0]["log"], SENSITIVE_REPLACE_VALUE)
        mock_service.assert_called_once_with(username="admin")
        mock_service.return_value.get_sensitive_object_permissions.assert_called_once_with([sensitive_object.id])

    @override_settings(IAM_PERMISSION_BACKEND="v4")
    @mock.patch("services.web.query.resources.base.get_request_username", return_value="admin")
    @mock.patch("services.web.query.resources.base.PermissionService")
    def test_sensitive_parser_uses_no_resource_permission_service(self, mock_service, _mock_username):
        sensitive_object = SensitiveObject.objects.create(
            name="secret_field",
            system_id="bk_log",
            resource_type=SensitiveResourceTypeEnum.RESOURCE.value,
            resource_id="host",
            fields=[{"field_name": "secret"}],
        )
        mock_service.return_value.get_sensitive_object_permissions.return_value = {str(sensitive_object.id): False}

        result = SearchDataParser().parse_data(
            [{"system_id": "bk_log", "resource_type_id": "host", "secret": "raw-value", "log": "raw-log"}]
        )

        self.assertEqual(result[0]["secret"], SENSITIVE_REPLACE_VALUE)
        self.assertEqual(result[0]["log"], SENSITIVE_REPLACE_VALUE)
        mock_service.assert_called_once_with(username="admin")
        mock_service.return_value.get_sensitive_object_permissions.assert_called_once_with([sensitive_object.id])

    @override_settings(IAM_PERMISSION_BACKEND="v3")
    @mock.patch("services.web.query.resources.base.PermissionService")
    def test_sensitive_parser_can_limit_rules_to_target_system_and_global_user_fields(self, mock_service):
        target_object = SensitiveObject.objects.create(
            name="target secret",
            system_id="bk_log",
            resource_type=SensitiveResourceTypeEnum.RESOURCE.value,
            resource_id="host",
            fields=[{"field_name": "secret"}],
        )
        global_object = SensitiveObject.objects.create(
            name="global user",
            system_id=SensitiveUserData.SYSTEM_ID,
            resource_type=SensitiveResourceTypeEnum.RESOURCE.value,
            resource_id=SensitiveUserData.RESOURCE_ID,
            fields=[{"field_name": "username"}],
        )
        other_object = SensitiveObject.objects.create(
            name="other system",
            system_id="other_system",
            resource_type=SensitiveResourceTypeEnum.RESOURCE.value,
            resource_id="host",
            fields=[{"field_name": "other_secret"}],
        )
        mock_service.return_value.get_sensitive_object_permissions.return_value = {
            str(target_object.id): False,
            str(global_object.id): False,
        }

        with self.assertNumQueries(2):
            result = SearchDataParser().parse_data(
                [
                    {
                        "system_id": "bk_log",
                        "resource_type_id": "host",
                        "username": "alice",
                        "secret": "target-value",
                        "other_secret": "other-value",
                        "log": "payload alice target-value",
                    }
                ],
                username="admin",
                system_id="bk_log",
            )

        self.assertEqual(result[0]["username"], SENSITIVE_REPLACE_VALUE)
        self.assertEqual(result[0]["secret"], SENSITIVE_REPLACE_VALUE)
        self.assertEqual(result[0]["log"], SENSITIVE_REPLACE_VALUE)
        self.assertEqual(result[0]["other_secret"], "other-value")
        permission_ids = mock_service.return_value.get_sensitive_object_permissions.call_args.args[0]
        self.assertEqual(set(permission_ids), {target_object.id, global_object.id})
        self.assertNotIn(other_object.id, permission_ids)

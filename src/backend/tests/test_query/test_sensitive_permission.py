# -*- coding: utf-8 -*-
from unittest import mock

from django.test import override_settings

from apps.meta.constants import SENSITIVE_REPLACE_VALUE, SensitiveResourceTypeEnum
from apps.meta.models import SensitiveObject
from services.web.query.resources.base import SearchDataParser
from tests.base import TestCase


class TestSensitivePermission(TestCase):
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

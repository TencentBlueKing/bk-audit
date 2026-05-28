# -*- coding: utf-8 -*-
from rest_framework import permissions

from apps.permission.handlers.actions import ActionEnum
from apps.permission.handlers.drf import AnyOfPermissions, InstanceActionPermission
from apps.permission.handlers.resource_types import ResourceEnum
from core.exceptions import PermissionException, ValidationError
from tests.base import TestCase


class DeniedPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        raise PermissionException(action_name="denied", permission={})

    def has_object_permission(self, request, view, obj):
        raise PermissionException(action_name="denied", permission={})


class CustomDeniedError(Exception):
    pass


class CustomDeniedPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        raise CustomDeniedError("custom denied")


class AllowedPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        return True

    def has_object_permission(self, request, view, obj):
        return True


class FalsePermission(permissions.BasePermission):
    def has_permission(self, request, view):
        return False

    def has_object_permission(self, request, view, obj):
        return False


class AnyOfPermissionsTest(TestCase):
    def test_has_permission_continues_after_permission_exception(self):
        permission = AnyOfPermissions(DeniedPermission(), AllowedPermission())

        self.assertTrue(permission.has_permission(None, None))

    def test_has_permission_continues_after_custom_exception(self):
        permission = AnyOfPermissions(CustomDeniedPermission(), AllowedPermission())

        self.assertTrue(permission.has_permission(None, None))

    def test_has_object_permission_continues_after_permission_exception(self):
        permission = AnyOfPermissions(DeniedPermission(), AllowedPermission())

        self.assertTrue(permission.has_object_permission(None, None, object()))

    def test_has_permission_raises_first_exception_when_all_permissions_fail(self):
        permission = AnyOfPermissions(DeniedPermission(), FalsePermission())

        with self.assertRaises(PermissionException):
            permission.has_permission(None, None)

    def test_has_permission_raises_first_custom_exception_when_all_permissions_fail(self):
        permission = AnyOfPermissions(CustomDeniedPermission(), FalsePermission())

        with self.assertRaises(CustomDeniedError):
            permission.has_permission(None, None)


class InstanceActionPermissionTest(TestCase):
    def test_has_permission_rejects_empty_instance_id(self):
        invalid_instance_ids = [None, "", "None", "null"]

        for instance_id in invalid_instance_ids:
            with self.subTest(instance_id=instance_id):
                permission = InstanceActionPermission(
                    actions=[ActionEnum.LIST_RULE],
                    resource_meta=ResourceEnum.SCENE,
                    get_instance_id=lambda instance_id=instance_id: instance_id,
                )

                with self.assertRaises(ValidationError):
                    permission.has_permission(None, None)

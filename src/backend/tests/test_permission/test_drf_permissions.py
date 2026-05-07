# -*- coding: utf-8 -*-
from rest_framework import permissions

from apps.permission.handlers.drf import AnyOfPermissions
from core.exceptions import PermissionException
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

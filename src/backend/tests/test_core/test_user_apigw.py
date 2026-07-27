# -*- coding: utf-8 -*-
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from core.permissions import UserAPIGWPermission
from core.view_sets import UserAPIGWViewSet


class TestUserAPIGWPermission(SimpleTestCase):
    def test_allows_authenticated_user_after_apigw_validation(self):
        request = SimpleNamespace(user=SimpleNamespace(is_authenticated=True))

        with mock.patch("core.permissions.get_app_info") as get_app_info:
            self.assertTrue(UserAPIGWPermission().has_permission(request, SimpleNamespace()))

        get_app_info.assert_called_once_with(request)

    def test_rejects_anonymous_user_after_apigw_validation(self):
        request = SimpleNamespace(user=SimpleNamespace(is_authenticated=False))

        with mock.patch("core.permissions.get_app_info") as get_app_info:
            self.assertFalse(UserAPIGWPermission().has_permission(request, SimpleNamespace()))

        get_app_info.assert_called_once_with(request)


class TestUserAPIGWViewSet(SimpleTestCase):
    def test_keeps_default_authenticator_and_returns_user_permission(self):
        viewset = UserAPIGWViewSet()

        self.assertIsInstance(viewset.get_permissions()[0], UserAPIGWPermission)
        self.assertNotIn("get_authenticators", UserAPIGWViewSet.__dict__)

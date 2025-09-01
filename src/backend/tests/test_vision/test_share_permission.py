# -*- coding: utf-8 -*-
from unittest import mock

from django.test import TestCase


class DummyRequest:
    def __init__(self, share_uid=None):
        self.query_params = {"share_uid": share_uid} if share_uid else {}
        self.data = {}


class TestShareDetailPermission(TestCase):
    def tearDown(self):
        mock.patch.stopall()

    def test_share_detail_permission_allowed(self):
        from services.web.vision.views import ShareDetailPermission

        with (
            mock.patch("services.web.vision.views.get_request_username", return_value="admin"),
            mock.patch("services.web.vision.views.check_bkvision_share_permission", return_value=True),
        ):
            perm = ShareDetailPermission()
            request = DummyRequest(share_uid="share-1")
            self.assertTrue(perm.has_permission(request, view=None))

    def test_share_detail_permission_denied(self):
        from services.web.tool.exceptions import BkVisionSearchPermissionProhibited
        from services.web.vision.views import ShareDetailPermission

        with (
            mock.patch("services.web.vision.views.get_request_username", return_value="admin"),
            mock.patch(
                "services.web.vision.views.check_bkvision_share_permission",
                side_effect=BkVisionSearchPermissionProhibited("admin", "share-2"),
            ),
        ):
            perm = ShareDetailPermission()
            request = DummyRequest(share_uid="share-2")
            with self.assertRaises(BkVisionSearchPermissionProhibited):
                perm.has_permission(request, view=None)

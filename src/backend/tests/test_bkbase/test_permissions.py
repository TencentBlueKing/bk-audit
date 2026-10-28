"""验证个人权限与平台权限隔离，指定负责人不被冒充。"""
from unittest import mock

from django.core.exceptions import PermissionDenied
from django.test import SimpleTestCase, override_settings

from services.web.bkbase import permissions
from services.web.bkbase.common import get_bkbase_context
from services.web.bkbase.exceptions import BKBaseCapabilityNotReady


@override_settings(BKBASE_API_VERSION="v4")
class PermissionTests(SimpleTestCase):
    def setUp(self):
        self.context = {
            "version": "v4",
            "user": "user_a",
            "request": mock.Mock(),
            "tenant": "tenant_a",
            "namespace": "audit",
        }
        self.context["request"].user.bk_username = "user_a"

    def test_platform_cannot_stand_for_personal_user(self):
        with self.assertRaises(PermissionDenied):
            permissions.check_user_rt({**self.context, "user": None}, rt_id="rt_a")

    def test_current_user_denial_not_replaced_by_platform(self):
        with mock.patch("services.web.bkbase.permissions.api.bk_base_v4.user_check", return_value={"result": False}):
            self.assertFalse(permissions.check_user_rt(self.context, rt_id="rt_denied"))

    def test_user_mine_filters_by_business(self):
        with mock.patch(
            "services.web.bkbase.permissions.api.bk_base_v4.user_result_tables",
            return_value=[{"result_table_id": "rt_a"}],
        ) as call:
            self.assertEqual(permissions.list_user_rts(self.context, bk_biz_id=7), [{"result_table_id": "rt_a"}])
            self.assertEqual(call.call_args.kwargs["bk_biz_id"], [7])

    def test_other_owner_is_explicitly_not_ready(self):
        with self.assertRaises(BKBaseCapabilityNotReady) as caught:
            permissions.check_owner_result_tables(
                self.context,
                permissions=[{"user_id": "user_b", "object_id": "rt_a", "action_id": "result_table.query_data"}],
            )
        self.assertEqual(caught.exception.blocker_id, "B11")

    def test_context_does_not_impersonate_user(self):
        with mock.patch("services.web.bkbase.common.get_local_request", return_value=None):
            with self.assertRaises(PermissionDenied):
                get_bkbase_context(user="user_a")

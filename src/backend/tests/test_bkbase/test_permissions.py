"""验证个人权限与平台权限隔离，指定负责人不被冒充。"""
from unittest import mock

from django.core.exceptions import PermissionDenied
from django.test import SimpleTestCase, override_settings

from services.web.bkbase import permissions
from services.web.bkbase.common import get_bkbase_context
from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.strategy_v2.utils.table import MineBizRtTableHandler


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
        with mock.patch.object(permissions, "list_user_rts", return_value=[]):
            self.assertFalse(permissions.check_user_rt(self.context, rt_id="rt_denied"))

    def test_user_mine_filters_by_business(self):
        namespaces = [
            {
                "kind": "Namespace",
                "metadata": {"tenant": "tenant_a", "namespace": "bkbase", "name": "project_a"},
                "spec": {"name": "project_a"},
                "status": {"phase": "Ok"},
            }
        ]
        rows = [
            {
                "dataset_name": "7_table",
                "dataset_alias": "Synthetic",
                "storage_type": "doris",
                "permissions": {"query": True},
            },
            {"dataset_name": "8_other", "storage_type": "doris", "permissions": {"query": True}},
        ]
        with mock.patch.object(
            permissions.api.bk_base_v4, "user_namespaces_list", return_value=namespaces
        ), mock.patch.object(permissions.metadata, "list_datasets", return_value=rows) as call:
            result = permissions.list_user_rts(self.context, bk_biz_id=7)
        self.assertEqual([r["result_table_id"] for r in result], ["7_table"])
        self.assertIs(call.call_args.kwargs["user_request"], self.context["request"])

    def test_other_owner_denial_is_returned_without_using_request_user(self):
        with mock.patch.object(permissions.api.bk_base_v4, "direct_auth_by_resources", return_value=[]):
            result = permissions.check_owner_result_tables(
                self.context,
                permissions=[{"user_id": "user_b", "object_id": "7_alpha", "action_id": "result_table.query_data"}],
            )
        self.assertEqual(result, [{"user_id": "user_b", "object_id": "7_alpha", "result": False}])

    def test_context_does_not_impersonate_user(self):
        with mock.patch("services.web.bkbase.common.get_local_request", return_value=None):
            with self.assertRaises(PermissionDenied):
                get_bkbase_context(user="user_a")

    def test_invalid_project_identity_fails_in_service_and_actual_menu_consumer(self):
        for rows in ([{"scope_id": "7"}], [{"kind": "Namespace", "metadata": {}, "spec": {}}]):
            with self.subTest(rows=rows), mock.patch.object(
                permissions.api.bk_base_v4, "user_namespaces_list", return_value=rows
            ), mock.patch.object(permissions, "get_bkbase_context", return_value=self.context), mock.patch(
                "services.web.strategy_v2.utils.table.get_request_username", return_value="user_a"
            ):
                with self.assertRaises(BKBaseResourceMappingError):
                    permissions.list_user_bizs(self.context)
                with self.assertRaises(BKBaseResourceMappingError):
                    MineBizRtTableHandler("MineBizRt").list_tables()

    def test_business_fields_and_empty_authorized_tables_keep_their_menu_meaning(self):
        for rows, expected in (([], []), ([{"bk_biz_id": 7}], [{"label": "Test(7)", "value": "7"}])):
            with self.subTest(rows=rows), mock.patch.object(
                permissions, "list_user_rts", return_value=rows
            ), mock.patch.object(
                permissions.resource.meta,
                "get_spaces_mine",
                return_value=[{"id": "7", "name": "Test", "space_type_id": permissions.SpaceType.BIZ.value}],
            ), mock.patch.object(
                permissions, "get_bkbase_context", return_value=self.context
            ), mock.patch(
                "services.web.strategy_v2.utils.table.get_request_username", return_value="user_a"
            ):
                self.assertEqual(MineBizRtTableHandler("MineBizRt").list_tables(), expected)

    def test_menu_consumer_propagates_mapping_failure_instead_of_successful_empty_list(self):
        with mock.patch.object(
            permissions,
            "get_bizs_list",
            side_effect=BKBaseResourceMappingError(message="Scope business fields missing"),
        ):
            with self.assertRaises(BKBaseResourceMappingError):
                MineBizRtTableHandler("MineBizRt").list_tables()

    def test_owner_permission_uses_same_application_check_when_owner_is_current_user(self):
        for owner in ("user_a", "user_b"):
            with self.subTest(owner=owner), mock.patch.object(
                permissions, "list_user_rts", return_value=[{"result_table_id": "rt_a"}]
            ) as personal, mock.patch.object(
                permissions.api.bk_base_v4,
                "direct_auth_by_resources",
                return_value=[{"resource_id": "7_alpha", "allowed": True}],
            ) as check, mock.patch.object(
                permissions.api.bk_base_v4,
                "result_table_info",
                return_value={
                    "kind": "ResultTable",
                    "metadata": {"tenant": "tenant_a", "namespace": "inputs", "name": "native_alpha"},
                    "spec": {"predefiendResultTableId": "7_alpha"},
                },
            ):
                self.assertEqual(
                    permissions.check_owner_result_tables(
                        self.context,
                        permissions=[
                            {"user_id": owner, "object_id": "7_alpha", "action_id": "result_table.query_data"}
                        ],
                    ),
                    [{"user_id": owner, "object_id": "7_alpha", "result": True}],
                )
                self.assertEqual(check.call_args.kwargs["user_id"], owner)
                personal.assert_not_called()

    def test_batch_owner_permission_never_reuses_current_user_table_list(self):
        for owner in ("user_a", "user_b"):
            with self.subTest(owner=owner), mock.patch.object(
                permissions, "get_bkbase_context", return_value=self.context
            ), mock.patch.object(
                permissions, "list_user_rts", return_value=[{"result_table_id": "rt_a"}]
            ) as personal, mock.patch.object(
                permissions.api.bk_base_v4, "direct_auth_by_resources", return_value=[]
            ):
                self.assertEqual(
                    permissions.user_auth_batch_check(
                        permissions=[{"user_id": owner, "object_id": "7_alpha", "action_id": "result_table.query_data"}]
                    ),
                    [{"user_id": owner, "object_id": "7_alpha", "result": False}],
                )
                personal.assert_not_called()

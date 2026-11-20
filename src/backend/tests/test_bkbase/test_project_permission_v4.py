"""V4 不再执行项目补授权，保留用户和场景检查。"""
from unittest import mock

from django.test import SimpleTestCase, override_settings
from rest_framework import serializers

from services.web.bkbase import permissions
from services.web.bkbase.exceptions import BKBaseCapabilityNotReady
from services.web.strategy_v2.constants import (
    LinkTableTableType,
    RuleAuditConfigType,
    StrategyType,
)
from services.web.strategy_v2.serializers import (
    LinkTableDataPermissionMixin,
    StrategySerializer,
)


class ProjectPermissionV4Tests(SimpleTestCase):
    @override_settings(BKBASE_API_VERSION="v4")
    def test_v4_skips_project_auth_without_calling_legacy_apis(self):
        for handler in (StrategySerializer(), LinkTableDataPermissionMixin()):
            with self.subTest(handler=type(handler)), mock.patch.object(
                permissions, "project_data_batch_check", side_effect=AssertionError("unexpected check")
            ), mock.patch.object(permissions, "project_data_batch_add", side_effect=AssertionError("unexpected add")):
                handler._ensure_project_permission(["11_test"])
        with self.assertRaises(BKBaseCapabilityNotReady):
            permissions.project_data_batch_check(object_ids=["11_test"])

    @override_settings(BKBASE_API_VERSION="v3", BKBASE_PROJECT_ID=1)
    def test_v3_still_checks_and_grants_project_permission(self):
        for handler in (StrategySerializer(), LinkTableDataPermissionMixin()):
            with self.subTest(handler=type(handler)), mock.patch.object(
                permissions, "project_data_batch_check", return_value={"no_permissions": ["11_test"]}
            ) as check, mock.patch.object(permissions, "project_data_batch_add") as add, mock.patch(
                "services.web.strategy_v2.serializers.bkbase_metadata.get_result_tables",
                return_value=[{"result_table_id": "11_test", "bk_biz_id": 11}],
            ):
                handler._ensure_project_permission(["11_test"])
                check.assert_called_once()
                add.assert_called_once_with(project_id=1, bk_biz_id=11, object_ids=["11_test"])

    @override_settings(BKBASE_API_VERSION="v4")
    def test_v4_link_table_still_checks_user_permission(self):
        handler = LinkTableDataPermissionMixin()
        attrs = {
            "scene_id": 1,
            "config": {
                "links": [{"left_table": {"table_type": LinkTableTableType.MINE_BIZ_RT.value, "rt_id": "11_test"}}]
            },
        }
        with mock.patch(
            "services.web.scene.data_filter.SceneDataFilter.get_table_ids", return_value=[]
        ), mock.patch.object(
            handler, "_check_user_table_permission", side_effect=serializers.ValidationError("denied")
        ) as user, mock.patch.object(
            permissions, "project_data_batch_check"
        ) as check:
            with self.assertRaises(serializers.ValidationError):
                handler._validate_link_table_data_permission(attrs)
            user.assert_called_once_with(["11_test"])
            check.assert_not_called()

    @override_settings(BKBASE_API_VERSION="v4")
    def test_v4_link_table_with_user_permission_skips_project_check(self):
        handler = LinkTableDataPermissionMixin()
        attrs = {
            "scene_id": 1,
            "config": {
                "links": [{"left_table": {"table_type": LinkTableTableType.MINE_BIZ_RT.value, "rt_id": "11_test"}}]
            },
        }
        with mock.patch(
            "services.web.scene.data_filter.SceneDataFilter.get_table_ids", return_value=[]
        ), mock.patch.object(handler, "_check_user_table_permission") as user, mock.patch.object(
            permissions, "project_data_batch_check"
        ) as check:
            handler._validate_link_table_data_permission(attrs)
        user.assert_called_once_with(["11_test"])
        check.assert_not_called()

    @override_settings(BKBASE_API_VERSION="v4")
    def test_strategy_keeps_scene_external_mine_submission_when_user_is_authorized(self):
        handler = StrategySerializer()
        attrs = {
            "scene_id": 1,
            "strategy_type": StrategyType.RULE.value,
            "configs": {"config_type": RuleAuditConfigType.MINE_BIZ_RT.value, "data_source": {"rt_id": "11_test"}},
        }
        with mock.patch.object(handler, "get_scene_id", return_value=1), mock.patch(
            "services.web.scene.data_filter.SceneDataFilter.get_table_ids", return_value=[]
        ), mock.patch.object(handler, "_check_user_table_permission") as user, mock.patch.object(
            handler,
            "_check_table_permission",
            side_effect=AssertionError("Must not tighten Mine to scene intersection"),
        ), mock.patch.object(
            permissions, "project_data_batch_check"
        ) as check:
            handler._validate_strategy_data_permission(attrs)
        user.assert_called_once_with(["11_test"])
        check.assert_not_called()

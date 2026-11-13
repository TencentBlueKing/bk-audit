"""验证V4角色名单展示降级不阻断元数据读取，且不改变权限判断。"""

from unittest import mock

from bk_resource import CacheResource
from django.test import SimpleTestCase, override_settings

from apps.meta.models import GlobalMetaConfig
from services.web.bkbase import permissions
from services.web.strategy_v2.resources import GetRTMeta


@override_settings(BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="tenant_a", BKBASE_V4_NAMESPACE="audit")
class RoleDisplayFallbackTests(SimpleTestCase):
    def test_v4_role_display_is_empty_without_calling_legacy_or_grant_apis(self):
        with mock.patch.object(permissions.api.bk_base, "get_role_users_list") as legacy:
            for role in ["result_table.manager", "result_table.viewer"]:
                with self.subTest(role=role):
                    self.assertEqual(permissions.get_role_users_list(role_id=role, scope_id="synthetic_rt"), [])
        legacy.assert_not_called()

    def test_real_metadata_resource_returns_fields_and_empty_roles_instead_of_b12(self):
        fields = [{"field_name": "raw", "field_alias": "RAW", "field_type": "string"}]
        with mock.patch.object(CacheResource, "_need_cache_wrap", return_value=False), mock.patch(
            "services.web.bkbase.metadata.get_result_table", return_value={"fields": fields}
        ), mock.patch(
            "services.web.bkbase.metadata.get_sensitivity_info_via_dataset", return_value={"level": "private"}
        ), mock.patch.object(
            GlobalMetaConfig, "get", return_value=None
        ):
            result = GetRTMeta().request(table_id="synthetic_rt")
        self.assertEqual(
            result,
            {
                "fields": fields,
                "managers": [],
                "viewers": [],
                "sensitivity_info": {"level": "private"},
                "formatted_fields": [
                    {
                        "label": "RAW",
                        "alias": "RAW",
                        "value": "raw",
                        "field_type": "string",
                        "spec_field_type": "string",
                        "property": {},
                    }
                ],
            },
        )

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_role_lists_keep_original_parameters_and_results(self):
        for role in ["result_table.manager", "result_table.viewer"]:
            for as_request_data in [False, True]:
                payload = {"role_id": role, "scope_id": "synthetic_rt"}
                with self.subTest(role=role, as_request_data=as_request_data), mock.patch.object(
                    permissions.api.bk_base, "get_role_users_list", return_value=["synthetic_member"]
                ) as legacy:
                    result = (
                        permissions.get_role_users_list(payload)
                        if as_request_data
                        else permissions.get_role_users_list(**payload)
                    )
                self.assertEqual(result, ["synthetic_member"])
                legacy.assert_called_once_with(**payload)

"""结果表元数据的字段、分页与资源归属验证。"""
from unittest import mock

from django.test import SimpleTestCase, override_settings

from services.web.bkbase import metadata
from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.strategy_v2.resources import GetRTMeta


@override_settings(BKBASE_API_VERSION="v4")
class MetadataTests(SimpleTestCase):
    def setUp(self):
        self.context = {
            "version": "v4",
            "tenant": "tenant_a",
            "namespace": "audit",
            "rt_namespaces": {"rt_a": "other_project"},
        }

    def test_batch_metadata_keeps_input_order(self):
        with mock.patch(
            "services.web.bkbase.metadata.api.bk_base_v4.result_table",
            side_effect=lambda **kw: {"result_table_id": kw["result_table_id"], "fields": [], "storages": {}},
        ):
            self.assertEqual(
                [r["result_table_id"] for r in metadata.get_result_tables(["rt_b", "rt_a"], context=self.context)],
                ["rt_b", "rt_a"],
            )

    def test_sensitivity_uses_table_namespace_and_excludes_personal_state(self):
        with mock.patch(
            "services.web.bkbase.metadata.api.bk_base_v4.dataset_detail",
            return_value={"dataset_name": "rt_a", "sensitivity": {"level": 2}, "is_favorite": True},
        ) as call:
            self.assertEqual(metadata.get_rt_sensitivity(self.context, "rt_a"), {"level": 2})
            self.assertEqual(call.call_args.kwargs["namespace"], "other_project")

    def test_unknown_namespace_is_not_defaulted(self):
        with self.assertRaises(BKBaseResourceMappingError):
            metadata.get_rt_sensitivity(self.context, "missing")

    def test_verified_private_string_maps_to_existing_level_without_fabricating_members(self):
        with mock.patch(
            "services.web.bkbase.metadata.api.bk_base_v4.dataset_detail",
            return_value={"dataset_name": "rt_a", "sensitivity": "private", "is_favorite": True},
        ):
            self.assertEqual(metadata.get_rt_sensitivity(self.context, "rt_a"), {"level": "private"})

    def test_unverified_sensitivity_values_are_not_guessed(self):
        for value in ("unknown", "public", "confidential", "", None, 1):
            with self.subTest(value=value), mock.patch(
                "services.web.bkbase.metadata.api.bk_base_v4.dataset_detail", return_value={"sensitivity": value}
            ):
                with self.assertRaises(BKBaseResourceMappingError):
                    metadata.get_rt_sensitivity(self.context, "rt_a")

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_sensitivity_keeps_existing_response(self):
        result = {"level": "private", "biz_role_memebers": ["user_a"]}
        with mock.patch.object(metadata.api.bk_base, "get_sensitivity_info_via_dataset", return_value=result) as call:
            self.assertEqual(
                metadata.get_sensitivity_info_via_dataset(data_set_type="result_table", data_set_id="rt_a"), result
            )
        call.assert_called_once_with(data_set_type="result_table", data_set_id="rt_a")

    def test_dataset_pages_num_is_total_pages(self):
        pages = [
            {"pages_num": 2, "total": 101, "list": [{"dataset_name": "a"}]},
            {"pages_num": 2, "total": 101, "list": [{"dataset_name": "b"}]},
        ]
        with mock.patch("services.web.bkbase.metadata.api.bk_base_v4.dataset_list", side_effect=pages) as call:
            self.assertEqual(metadata.list_datasets(self.context), [{"dataset_name": "a"}, {"dataset_name": "b"}])
            self.assertEqual([c.kwargs["page"] for c in call.call_args_list], [1, 2])

    @override_settings(BKBASE_V4_RESULT_TABLE_NAMESPACES={"rt_a": "other_project"})
    def test_existing_sensitivity_parameter_names(self):
        with mock.patch(
            "services.web.bkbase.metadata.api.bk_base_v4.dataset_detail", return_value={"sensitivity": {"level": 2}}
        ):
            self.assertEqual(
                metadata.get_sensitivity_info_via_dataset(data_set_type="result_table", data_set_id="rt_a"),
                {"level": 2},
            )


class MetadataCacheTests(SimpleTestCase):
    def test_v4_does_not_reuse_v3_or_other_tenant_metadata_cache(self):
        keys = []
        for version, tenant in (("v3", ""), ("v4", "tenant_a"), ("v4", "tenant_b")):
            with override_settings(BKBASE_API_VERSION=version, BKBASE_V4_TENANT=tenant):
                keys.append(GetRTMeta().cache_type.key)
        self.assertEqual(len(set(keys)), 3)

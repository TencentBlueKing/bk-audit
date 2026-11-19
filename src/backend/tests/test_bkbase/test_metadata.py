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
            "rt_namespaces": {"rt_a": "other_project", "11_a": "other_project", "11_b": "other_project"},
        }

    def test_batch_metadata_keeps_input_order(self):
        with mock.patch(
            "services.web.bkbase.metadata.api.bk_base_v4.dataset_detail",
            side_effect=lambda **kw: {"dataset_name": kw["dataset_name"], "fields": []},
        ), mock.patch(
            "services.web.bkbase.metadata.api.bk_base_v4.dataset_list",
            return_value={"pages_num": 0, "total": 0, "list": []},
        ):
            self.assertEqual(
                [r["result_table_id"] for r in metadata.get_result_tables(["11_b", "11_a"], context=self.context)],
                ["11_b", "11_a"],
            )

    def test_v4_metadata_preserves_alias_for_existing_detail_consumer(self):
        with mock.patch.object(
            metadata.api.bk_base_v4,
            "dataset_detail",
            return_value={"dataset_name": "11_a", "dataset_alias": "Synthetic dataset", "fields": []},
        ):
            result = metadata.get_result_table("11_a", related=["fields"], context=self.context)
        self.assertEqual(result["result_table_name_alias"], "Synthetic dataset")
        self.assertEqual(result["result_table_id"], "11_a")

    def test_sensitivity_uses_table_namespace_and_excludes_personal_state(self):
        with mock.patch(
            "services.web.bkbase.metadata.api.bk_base_v4.dataset_detail",
            return_value={"dataset_name": "rt_a", "sensitivity": "private", "is_favorite": True},
        ) as call:
            self.assertEqual(metadata.get_rt_sensitivity(self.context, "rt_a"), {"level": "private"})
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
        for value in ("unknown", "", None, 1):
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

    def test_dataset_total_is_record_count_not_page_count(self):
        pages = [
            {"pages_num": 101, "total": 101, "list": [{"dataset_name": str(i)} for i in range(100)]},
            {"pages_num": 101, "total": 101, "list": [{"dataset_name": "100"}]},
        ]
        with mock.patch("services.web.bkbase.metadata.api.bk_base_v4.dataset_list", side_effect=pages) as call:
            self.assertEqual(len(metadata.list_datasets(self.context)), 101)
            self.assertEqual([c.kwargs["page"] for c in call.call_args_list], [1, 2])

    def test_empty_page_before_total_and_bad_response_are_rejected(self):
        with mock.patch.object(
            metadata.api.bk_base_v4, "dataset_list", return_value={"total": 200, "list": []}
        ) as call:
            with self.assertRaises(BKBaseResourceMappingError):
                metadata.list_datasets(self.context)
            call.assert_called_once()
        for invalid in (None, {}, {"total": -1, "list": []}, {"total": True, "list": []}, {"total": 1, "list": "x"}):
            with self.subTest(invalid=invalid), mock.patch.object(
                metadata.api.bk_base_v4, "dataset_list", return_value=invalid
            ), self.assertRaises(BKBaseResourceMappingError):
                metadata.list_datasets(self.context)

    @override_settings(BKBASE_V4_RESULT_TABLE_NAMESPACES={"rt_a": "other_project"}, BKBASE_V4_TENANT="tenant_a")
    def test_existing_sensitivity_parameter_names(self):
        with mock.patch(
            "services.web.bkbase.metadata.api.bk_base_v4.dataset_detail", return_value={"sensitivity": "private"}
        ):
            self.assertEqual(
                metadata.get_sensitivity_info_via_dataset(data_set_type="result_table", data_set_id="rt_a"),
                {"level": "private"},
            )


class MetadataCacheTests(SimpleTestCase):
    def test_v4_does_not_reuse_v3_or_other_tenant_metadata_cache(self):
        keys = []
        for version, tenant in (("v3", ""), ("v4", "tenant_a"), ("v4", "tenant_b")):
            with override_settings(BKBASE_API_VERSION=version, BKBASE_V4_TENANT=tenant):
                keys.append(GetRTMeta().cache_type.key)
        self.assertEqual(len(set(keys)), 3)

"""插件自动发现必须先全范围消歧，再核正式身份/来源业务，最后本地绑定。"""
from copy import deepcopy
from types import SimpleNamespace
from unittest import mock

from bk_resource.exceptions import APIRequestError
from django.test import TestCase, override_settings

from services.web.bkbase import clean, source
from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.databus.collector_plugin.handlers import PluginEtlHandler
from services.web.databus.models import CollectorPlugin


def ref(kind, name, namespace):
    return {"kind": kind, "tenant": "tenant_a", "namespace": namespace, "name": name}


def project(name):
    return {
        "kind": "Namespace",
        "metadata": {"tenant": "tenant_a", "namespace": "bkbase", "name": name},
        "spec": {"name": name},
        "status": {"phase": "Ok"},
    }


@override_settings(
    BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="tenant_a", BKBASE_V4_NAMESPACE="audit", DEFAULT_BK_BIZ_ID=8
)
class PluginSourceDiscoveryTests(TestCase):
    def setUp(self):
        self.plugin = CollectorPlugin.objects.create(
            namespace="audit",
            collector_plugin_id=741,
            collector_plugin_name="synthetic",
            collector_plugin_name_en="audit_plugin_741",
            bkdata_biz_id=47,
            table_id=74,
            index_set_id=84,
        )
        self.handler = PluginEtlHandler(plugin=self.plugin)
        self.source_ref = ref("DataSource", "opaque_resource", "shared_project")
        self.data_ref = ref("DataId", "opaque_data", "shared_project")
        self.native = {
            "kind": "DataSource",
            "metadata": {
                **{k: self.source_ref[k] for k in ("tenant", "namespace", "name")},
                "labels": {"raw_data_id": "631"},
            },
            "spec": {
                "basic_info": {
                    "data_source_name": "opaque_resource",
                    "data_source_alias": "47_bklog_audit_plugin_741",
                    "bk_biz_id": 2,
                },
                "data_id": self.data_ref,
            },
            "status": {"phase": "Ok"},
        }
        self.data = {
            "kind": "DataId",
            "metadata": {
                **{k: self.data_ref[k] for k in ("tenant", "namespace", "name")},
                "labels": {"bk_biz_id": "47"},
            },
            "spec": {"bizId": 2, "predefined": {"dataId": 631}},
            "status": {"phase": "Ok"},
        }
        self.rows = {"audit": [], "shared_project": [self.native]}
        self.sdk = mock.Mock()
        self.sdk.namespaces_list.return_value = [project("audit"), project("shared_project")]
        self.sdk.data_source_list.side_effect = lambda tenant, namespace: deepcopy(self.rows[namespace])
        self.sdk.data_source_get.side_effect = lambda **kw: deepcopy(self.native)
        self.sdk.data_id_get.side_effect = lambda **kw: deepcopy(self.data)
        self.enterContext(mock.patch.object(source, "api", SimpleNamespace(bk_base_v4=self.sdk, bk_base=mock.Mock())))

    def test_complete_89_project_scope_is_read_before_claiming_unique(self):
        names = ["audit", *[f"empty_{i:02d}" for i in range(87)], "shared_project"]
        self.sdk.namespaces_list.return_value = [project(name) for name in names]
        self.rows = {name: [] for name in names}
        self.rows["shared_project"] = [self.native]
        self.assertEqual(self.handler.get_bk_data_id(), 631)
        self.assertEqual(self.sdk.data_source_list.call_count, 89)
        self.assertEqual(self.sdk.data_source_get.call_count, 1)
        self.assertEqual(self.sdk.data_id_get.call_count, 1)

    def test_missing_data_ref_fields_and_malformed_status_fail_with_mapping_error(self):
        self.native["spec"]["data_id"] = {"namespace": "shared_project", "name": "opaque_data"}
        with self.assertRaises(BKBaseResourceMappingError):
            self.handler.get_bk_data_id()
        self.assert_unbound()
        for kind in (None, "Clean"):
            self.native["spec"]["data_id"] = {**self.data_ref, "kind": kind}
            with self.assertRaises(BKBaseResourceMappingError):
                self.handler.get_bk_data_id()
            self.assert_unbound()
        self.native["spec"]["data_id"] = self.data_ref
        for resource in (self.native, self.data):
            for status in (None, [], {"phase": "Pending"}):
                resource["status"] = status
                with self.assertRaises(BKBaseResourceMappingError):
                    self.handler.get_bk_data_id()
                self.assert_unbound()
            resource["status"] = {"phase": "Ok"}

    def assert_unbound(self):
        self.plugin.refresh_from_db()
        self.assertEqual(self.plugin.bkbase_v4_resources, {})

    def test_alias_in_formally_enumerated_project_finds_origin_business_47_not_project_2(self):
        self.assertEqual(self.handler.get_bk_data_id(), 631)
        self.plugin.refresh_from_db()
        binding = self.plugin.bkbase_v4_resources
        self.assertEqual(binding["data_source"], self.source_ref)
        self.assertEqual(binding["data_id"], self.data_ref)
        self.assertEqual(binding["source_raw_data_id"], 631)
        self.assertEqual(binding["source_bk_biz_id"], 47)
        self.assertEqual(self.plugin.namespace, "audit")
        self.assertEqual(self.plugin.bkdata_biz_id, 47)
        self.assertEqual(
            [c.kwargs["namespace"] for c in self.sdk.data_source_list.call_args_list], ["audit", "shared_project"]
        )

    def test_metadata_name_and_basic_name_also_match_complete_plugin_identity(self):
        for field in ("metadata", "basic_info"):
            with self.subTest(field=field):
                self.native["spec"]["basic_info"]["data_source_alias"] = "unrelated"
                self.native["metadata"]["name"] = "opaque_resource"
                self.source_ref["name"] = "opaque_resource"
                if field == "metadata":
                    self.native["metadata"]["name"] = "audit_plugin_741"
                    self.source_ref["name"] = "audit_plugin_741"
                else:
                    self.native["spec"]["basic_info"]["data_source_name"] = "audit_plugin_741"
                self.assertEqual(self.handler.get_bk_data_id(), 631)
                CollectorPlugin.objects.filter(pk=self.plugin.pk).update(bkbase_v4_resources={})
                self.plugin.refresh_from_db()

    def test_larger_ascii_name_does_not_match_a_plugin_substring(self):
        for alias in ("prefixaudit_plugin_741", "audit_plugin_741_extra", "audit_plugin_7410"):
            self.native["spec"]["basic_info"]["data_source_alias"] = alias
            with self.assertRaises(BKBaseResourceMappingError):
                self.handler.get_bk_data_id()
            self.assert_unbound()

    def test_duplicate_alias_in_one_or_multiple_projects_never_selects_first(self):
        other = deepcopy(self.native)
        other["metadata"]["name"] = "other_source"
        for namespace in ("shared_project", "audit"):
            with self.subTest(namespace=namespace):
                other["metadata"]["namespace"] = namespace
                self.rows = {"audit": [], "shared_project": [self.native]}
                self.rows[namespace].append(other)
                with self.assertRaises(BKBaseResourceMappingError):
                    self.handler.get_bk_data_id()
                self.assert_unbound()
        self.sdk.data_source_get.assert_not_called()
        self.sdk.data_id_get.assert_not_called()

    def test_unready_matching_sibling_cannot_be_silently_filtered_to_claim_unique(self):
        other = deepcopy(self.native)
        other["metadata"]["name"] = "not_ready"
        other["metadata"]["labels"] = {}
        self.rows["shared_project"].append(other)
        with self.assertRaises(BKBaseResourceMappingError):
            self.handler.get_bk_data_id()
        self.assert_unbound()

    def test_missing_conflicting_or_invalid_origin_business_refuses_even_when_project_matches(self):
        self.native["spec"]["basic_info"]["bk_biz_id"] = 47
        for value in (None, "48", True, "unknown", "0"):
            with self.subTest(value=value):
                self.data["metadata"]["labels"] = {} if value is None else {"bk_biz_id": value}
                with self.assertRaises(BKBaseResourceMappingError):
                    self.handler.get_bk_data_id()
                self.assert_unbound()

    def test_invalid_or_pending_numeric_identity_cannot_bind(self):
        for value in (None, "0", "-1", "bad", "６３１", True):
            self.native["metadata"]["labels"]["raw_data_id"] = value
            with self.assertRaises(BKBaseResourceMappingError):
                self.handler.get_bk_data_id()
            self.assert_unbound()
        self.native["metadata"]["labels"]["raw_data_id"] = "631"
        self.data["spec"]["predefined"]["dataId"] = 632
        with self.assertRaises(BKBaseResourceMappingError):
            self.handler.get_bk_data_id()
        self.assert_unbound()
        self.data["spec"]["predefined"]["dataId"] = 631
        self.native["status"]["phase"] = "Pending"
        with self.assertRaises(BKBaseResourceMappingError):
            self.handler.get_bk_data_id()
        self.assert_unbound()

    def test_formal_get_must_match_list_identity_and_actual_data_ref(self):
        for change in ("source_name", "source_data_ref", "data_name", "data_number"):
            native, data = deepcopy(self.native), deepcopy(self.data)
            if change == "source_name":
                native["metadata"]["name"] = "different"
            elif change == "source_data_ref":
                native["spec"]["data_id"] = ref("DataId", "different", "shared_project")
            elif change == "data_name":
                data["metadata"]["name"] = "different"
            else:
                data["spec"]["predefined"]["dataId"] = 632
            self.sdk.data_source_get.side_effect = lambda **kw: deepcopy(native)
            self.sdk.data_id_get.side_effect = lambda **kw: deepcopy(data)
            with self.assertRaises(BKBaseResourceMappingError):
                self.handler.get_bk_data_id()
            self.assert_unbound()

    def test_missing_or_cross_tenant_project_identity_cannot_be_used(self):
        for invalid in (
            {},
            {
                **project("shared_project"),
                "metadata": {"tenant": "tenant_b", "namespace": "bkbase", "name": "shared_project"},
            },
        ):
            self.sdk.namespaces_list.return_value = [invalid]
            with self.assertRaises(BKBaseResourceMappingError):
                self.handler.get_bk_data_id()
            self.assert_unbound()
        self.sdk.data_source_list.assert_not_called()

    def test_scope_or_candidate_get_failure_is_not_skipped_to_claim_success(self):
        for endpoint in ("namespaces_list", "data_source_list", "data_source_get", "data_id_get"):
            with self.subTest(endpoint=endpoint):
                target = getattr(self.sdk, endpoint)
                previous = target.side_effect
                target.side_effect = APIRequestError("bk_base_v4", endpoint, "synthetic403")
                with self.assertRaises(APIRequestError):
                    self.handler.get_bk_data_id()
                self.assert_unbound()
                target.side_effect = previous

    def test_new_saved_binding_refuses_nonready_or_malformed_source_without_rediscovery(self):
        self.handler.get_bk_data_id()
        before = deepcopy(self.plugin.bkbase_v4_resources)
        for status in ({"phase": "Pending"}, {"phase": "Failed"}, None, [], {}, mock.sentinel.missing_status):
            with self.subTest(status=status):
                if status is mock.sentinel.missing_status:
                    self.native.pop("status", None)
                else:
                    self.native["status"] = deepcopy(status)
                self.sdk.reset_mock()
                with self.assertRaises(BKBaseResourceMappingError):
                    self.handler.get_bk_data_id()
                self.plugin.refresh_from_db()
                self.assertEqual(self.plugin.bkbase_v4_resources, before)
                self.sdk.namespaces_list.assert_not_called()
                self.sdk.data_source_list.assert_not_called()
                self.sdk.data_source_get.assert_called_once()
                self.sdk.data_id_get.assert_not_called()

    def test_nonready_saved_source_stops_before_clean_configuration(self):
        self.handler.get_bk_data_id()
        before = deepcopy(self.plugin.bkbase_v4_resources)
        self.native["status"] = {"phase": "Failed"}
        self.sdk.reset_mock()
        with mock.patch.object(self.handler, "get_fields", return_value=[]), mock.patch.object(
            self.handler, "get_clean_json_config", return_value={}
        ), mock.patch.object(clean, "configure_clean") as configure:
            with self.assertRaises(BKBaseResourceMappingError):
                self.handler.create_or_update_clean()
        configure.assert_not_called()
        self.plugin.refresh_from_db()
        self.assertEqual(self.plugin.bkbase_v4_resources, before)
        self.sdk.namespaces_list.assert_not_called()
        self.sdk.data_source_list.assert_not_called()
        self.sdk.data_source_get.assert_called_once()
        self.sdk.data_id_get.assert_not_called()

    def test_legacy_source_binding_keeps_its_existing_reentry_protocol(self):
        binding = {"data_source": self.source_ref, "data_id": self.data_ref, "source_raw_data_id": 631}
        CollectorPlugin.objects.filter(pk=self.plugin.pk).update(bkbase_v4_resources=binding)
        self.plugin.refresh_from_db()
        for status in ({"phase": "Pending"}, {"phase": "Failed"}, None, []):
            self.native["status"] = status
            self.sdk.reset_mock()
            self.assertEqual(self.handler.get_bk_data_id(), 631)
            self.plugin.refresh_from_db()
            self.assertEqual(self.plugin.bkbase_v4_resources, binding)
            self.sdk.namespaces_list.assert_not_called()
            self.sdk.data_source_list.assert_not_called()
            self.sdk.data_source_get.assert_called_once()
            self.sdk.data_id_get.assert_not_called()

    def test_saved_binding_reentry_verifies_source_and_origin_without_rediscovery(self):
        self.handler.get_bk_data_id()
        self.sdk.reset_mock()
        self.assertEqual(self.handler.get_bk_data_id(), 631)
        self.sdk.namespaces_list.assert_not_called()
        self.sdk.data_source_list.assert_not_called()
        self.sdk.data_source_get.assert_called_once()
        self.sdk.data_id_get.assert_called_once()
        self.data["metadata"]["labels"]["bk_biz_id"] = "48"
        with self.assertRaises(BKBaseResourceMappingError):
            self.handler.get_bk_data_id()
        self.plugin.refresh_from_db()
        self.assertEqual(self.plugin.bkbase_v4_resources["source_bk_biz_id"], 47)

    def test_plugin_configuration_change_before_binding_is_rejected_under_row_lock(self):
        def changed(**kwargs):
            CollectorPlugin.objects.filter(pk=self.plugin.pk).update(bkdata_biz_id=48)
            return deepcopy(self.data)

        self.sdk.data_id_get.side_effect = changed
        with self.assertRaises(BKBaseResourceMappingError):
            self.handler.get_bk_data_id()
        self.assert_unbound()

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_keeps_default_business_and_original_lookup_contract(self):
        legacy = source.api.bk_base.get_rawdata_list
        legacy.return_value = [{"id": 631}]
        self.assertEqual(self.handler.get_bk_data_id(), 631)
        legacy.assert_called_once_with(bk_biz_id=8, raw_data_name__icontains="audit_plugin_741")
        self.sdk.namespaces_list.assert_not_called()
        self.assert_unbound()

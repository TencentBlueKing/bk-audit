"""可信 DataSource/DataId 引用沿实际插件和采集项路径传递。"""
from copy import deepcopy
from types import SimpleNamespace
from unittest import mock

import requests
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.test import TestCase, override_settings

from api.bk_base_v4.default import DataIdTail, DataSourceList
from apps.exceptions import ParamsNotValid
from services.web.bkbase import clean, source
from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.databus.collector import resources as collector_resources
from services.web.databus.collector.handlers import BkBaseTailLogHandler
from services.web.databus.collector.views import DataIdsViewSet
from services.web.databus.collector_plugin.handlers import PluginEtlHandler
from services.web.databus.models import CollectorConfig, CollectorPlugin


@override_settings(BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="tenant_a", BKBASE_V4_NAMESPACE="audit")
class TrustedSourceBindingTests(TestCase):
    def setUp(self):
        self.plugin = CollectorPlugin.objects.create(
            namespace="audit",
            collector_plugin_id=9,
            collector_plugin_name="synthetic",
            collector_plugin_name_en="synthetic",
            bkdata_biz_id=1,
            table_id=1,
            index_set_id=1,
        )
        self.native = {
            "kind": "DataSource",
            "metadata": {
                "tenant": "tenant_a",
                "namespace": "audit",
                "name": "actual_source",
                "labels": {"raw_data_id": "11"},
            },
            "spec": {
                "basic_info": {
                    "data_source_name": "synthetic_source",
                    "data_source_alias": "1_bklog_synthetic",
                    "bk_biz_id": settings.DEFAULT_BK_BIZ_ID,
                },
                "data_id": {
                    "kind": "DataId",
                    "tenant": "tenant_a",
                    "namespace": "foreign_project",
                    "name": "actual_data",
                },
            },
            "status": {"phase": "Ok"},
        }
        self.src_ref = {"kind": "DataSource", "tenant": "tenant_a", "namespace": "audit", "name": "actual_source"}
        self.data_ref = {"kind": "DataId", "tenant": "tenant_a", "namespace": "foreign_project", "name": "actual_data"}
        namespaces = [
            {
                "kind": "Namespace",
                "metadata": {"tenant": "tenant_a", "namespace": "bkbase", "name": "audit"},
                "spec": {"name": "audit"},
                "status": {"phase": "Ok"},
            }
        ]
        data = {
            "kind": "DataId",
            "metadata": {
                "tenant": "tenant_a",
                "namespace": "foreign_project",
                "name": "actual_data",
                "labels": {"bk_biz_id": "1"},
            },
            "spec": {"predefined": {"dataId": 11}},
            "status": {"phase": "Ok"},
        }
        self.enterContext(mock.patch.object(source.api.bk_base_v4, "namespaces_list", return_value=namespaces))
        self.enterContext(
            mock.patch.object(source.api.bk_base_v4, "data_source_get", side_effect=lambda **kw: deepcopy(self.native))
        )
        self.enterContext(mock.patch.object(source.api.bk_base_v4, "data_id_get", return_value=data))

    def test_plugin_selection_binds_refs_before_actual_clean(self):
        handler = PluginEtlHandler(plugin=self.plugin)
        with mock.patch.object(source.api.bk_base_v4, "data_source_list", return_value=[self.native]) as listing:
            raw_id = handler.get_bk_data_id()
            self.plugin.refresh_from_db()
            self.assertEqual(raw_id, 11)
            self.assertEqual(self.plugin.bkbase_v4_resources["data_source"], self.src_ref)
            self.assertEqual(self.plugin.bkbase_v4_resources["data_id"], self.data_ref)
            params = {"raw_data_id": raw_id, "bk_biz_id": 1, "result_table_name": "synthetic", "json_config": "{}"}
            with mock.patch.object(clean, "convert_rules", return_value=[]), mock.patch.object(
                clean, "ensure_clean", return_value={}
            ) as ensure:
                clean.configure_clean(self.plugin, params, rt_owner=True)
            self.assertEqual(ensure.call_args.kwargs["rules"]["data_id"], self.data_ref)
            listing.assert_called_once()

    def test_plugin_zero_multiple_and_invalid_ids_do_not_bind(self):
        for rows in (
            [],
            [self.native, deepcopy(self.native)],
            [{**self.native, "metadata": {**self.native["metadata"], "labels": {"raw_data_id": "-1"}}}],
        ):
            with self.subTest(rows=rows), mock.patch.object(
                source.api.bk_base_v4, "data_source_list", return_value=rows
            ):
                with self.assertRaises(BKBaseResourceMappingError):
                    PluginEtlHandler(plugin=self.plugin).get_bk_data_id()
                self.plugin.refresh_from_db()
                self.assertEqual(self.plugin.bkbase_v4_resources, {})

    def test_plugin_ref_conflict_does_not_replace_existing_binding(self):
        old_ref = {**self.data_ref, "name": "older_data"}
        self.plugin.bkbase_v4_resources = {"data_id": old_ref}
        self.plugin.save(update_fields=["bkbase_v4_resources"])
        with mock.patch.object(source.api.bk_base_v4, "data_source_list", return_value=[self.native]):
            with self.assertRaises(BKBaseResourceMappingError):
                PluginEtlHandler(plugin=self.plugin).get_bk_data_id()
        self.plugin.refresh_from_db()
        self.assertEqual(self.plugin.bkbase_v4_resources, {"data_id": old_ref})

    def test_internal_log_owner_uses_dataid_without_datasource_lookup(self):
        owner = CollectorConfig.objects.create(
            system_id="synthetic",
            bk_biz_id=1,
            bk_data_id=11,
            collector_plugin_id=9,
            collector_config_id=11,
            collector_config_name="synthetic",
            bkbase_v4_resources={"data_id": self.data_ref},
        )
        with mock.patch.object(
            source.api.bk_base_v4, "data_source_list", side_effect=AssertionError("unexpected source lookup")
        ), mock.patch.object(source.api.bk_base_v4, "data_id_tail", return_value=['{"start_time":1000}']) as tail:
            handler = BkBaseTailLogHandler(owner)
            handler.load_tail_log()
        self.assertEqual(handler.tail_logs, [{"value": '{"start_time":1000}'}])
        tail.assert_called_once_with(namespace="foreign_project", name="actual_data")

    def test_tail_resource_uses_owner_after_system_permission(self):
        owner = CollectorConfig.objects.create(
            system_id="real_system",
            bk_biz_id=1,
            bk_data_id=11,
            collector_plugin_id=9,
            collector_config_id=11,
            collector_config_name="synthetic",
            bkbase_v4_resources={"data_id": self.data_ref},
        )
        request = SimpleNamespace(user=SimpleNamespace(username="synthetic", is_authenticated=True))
        permission = mock.Mock()
        permission.has_permission.return_value = True
        permissions = mock.Mock()
        permissions.generate_permission.return_value = permission
        with mock.patch.object(
            collector_resources, "get_local_request", return_value=request, create=True
        ), mock.patch.object(
            collector_resources, "SystemPermissionHandler", permissions, create=True
        ), mock.patch.object(
            source.api.bk_base_v4, "data_source_list", side_effect=AssertionError("unexpected lookup")
        ), mock.patch.object(
            source.api.bk_base_v4, "data_id_tail", return_value=["sample"]
        ) as tail:
            result = collector_resources.GetDataIdTail().request({"bk_data_id": 11, "system_id": "other_system"})
        self.assertEqual(result, [{"value": "sample"}])
        self.assertEqual(permissions.generate_permission.call_args.kwargs["get_instance_id"](), owner.system_id)
        permission.has_permission.assert_called_once_with(request, None)
        tail.assert_called_once_with(namespace="foreign_project", name="actual_data")

    def test_tail_resource_rejects_denied_owner_before_tail(self):
        CollectorConfig.objects.create(
            system_id="real_system",
            bk_biz_id=1,
            bk_data_id=11,
            collector_plugin_id=9,
            collector_config_id=11,
            collector_config_name="synthetic",
            bkbase_v4_resources={"data_id": self.data_ref},
        )
        request = SimpleNamespace(user=SimpleNamespace(username="synthetic", is_authenticated=True))
        permission = mock.Mock()
        permission.has_permission.return_value = False
        permissions = mock.Mock()
        permissions.generate_permission.return_value = permission
        with mock.patch.object(
            collector_resources, "get_local_request", return_value=request, create=True
        ), mock.patch.object(
            collector_resources, "SystemPermissionHandler", permissions, create=True
        ), mock.patch.object(
            source.api.bk_base_v4, "data_id_tail"
        ) as tail:
            with self.assertRaises(PermissionDenied):
                collector_resources.GetDataIdTail().request({"bk_data_id": 11})
        tail.assert_not_called()

    def test_tail_resource_without_live_owner_keeps_source_lookup(self):
        request = SimpleNamespace(user=SimpleNamespace(username="synthetic", is_authenticated=True))
        with mock.patch.object(
            collector_resources, "get_local_request", return_value=request, create=True
        ), mock.patch.object(
            source.api.bk_base_v4, "data_source_list", return_value=[self.native]
        ) as listing, mock.patch.object(
            source.api.bk_base_v4, "data_id_tail", return_value=["sample"]
        ):
            result = collector_resources.GetDataIdTail().request({"bk_data_id": 11})
            CollectorConfig.objects.create(
                system_id="real_system",
                bk_biz_id=1,
                bk_data_id=11,
                collector_plugin_id=9,
                collector_config_id=11,
                collector_config_name="synthetic",
                bkbase_v4_resources={"data_id": self.data_ref},
                is_deleted=True,
            )
            deleted_result = collector_resources.GetDataIdTail().request({"bk_data_id": 11})
        self.assertEqual(result, [{"value": "sample"}])
        self.assertEqual(deleted_result, [{"value": "sample"}])
        self.assertEqual(listing.call_count, 2)

    def test_tail_view_permission_scope_uses_active_owner_not_requested_system(self):
        owner = CollectorConfig.objects.create(
            system_id="real_system",
            bk_biz_id=1,
            bk_data_id=11,
            collector_plugin_id=9,
            collector_config_id=11,
            collector_config_name="synthetic",
        )
        view = DataIdsViewSet()
        view.kwargs = {"pk": "11"}
        view.request = SimpleNamespace(query_params={"system_id": "other_system"}, data={})
        self.assertEqual(view.get_system_id(), "real_system")
        owner.is_deleted = True
        owner.save(update_fields=["is_deleted"])
        self.assertEqual(view.get_system_id(), "other_system")
        view.kwargs = {"pk": "12"}
        self.assertEqual(view.get_system_id(), "other_system")

    def test_direct_resource_without_request_retains_original_lookup(self):
        CollectorConfig.objects.create(
            system_id="real_system",
            bk_biz_id=1,
            bk_data_id=11,
            collector_plugin_id=9,
            collector_config_id=11,
            collector_config_name="synthetic",
            bkbase_v4_resources={"data_id": self.data_ref},
        )
        with mock.patch.object(collector_resources, "get_local_request", return_value=None), mock.patch.object(
            source.api.bk_base_v4, "data_source_list", return_value=[self.native]
        ) as listing, mock.patch.object(source.api.bk_base_v4, "data_id_tail", return_value=["sample"]):
            result = collector_resources.GetDataIdTail().request({"bk_data_id": 11})
        self.assertEqual(result, [{"value": "sample"}])
        listing.assert_called_once()

    def test_invalid_number_cannot_be_used_to_find_synced_source(self):
        with mock.patch.object(source.api.bk_base_v4, "data_source_list") as listing:
            with self.assertRaises(BKBaseResourceMappingError):
                source.resolve_synced_source(source.get_bkbase_context(), self.plugin, raw_data_id=-1)
            listing.assert_not_called()

    def test_existing_owner_with_mismatched_raw_id_cannot_tail(self):
        owner = CollectorConfig.objects.create(
            system_id="synthetic",
            bk_biz_id=1,
            bk_data_id=11,
            collector_plugin_id=9,
            collector_config_id=11,
            collector_config_name="synthetic",
            bkbase_v4_resources={"data_id": self.data_ref, "source_raw_data_id": 12},
        )
        with mock.patch.object(source.api.bk_base_v4, "data_id_tail") as tail:
            with self.assertRaises(BKBaseResourceMappingError):
                BkBaseTailLogHandler(owner).load_tail_log()
        tail.assert_not_called()

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_log_owner_keeps_original_tail_arguments(self):
        owner = SimpleNamespace(bk_data_id=11)
        with mock.patch.object(source.api.bk_base, "get_rawdata_tail", return_value=[]) as tail:
            BkBaseTailLogHandler(owner).load_tail_log()
        tail.assert_called_once_with(bk_data_id=11)

    def test_internal_owner_tail_passes_real_resource_request(self):
        owner = CollectorConfig.objects.create(
            system_id="synthetic",
            bk_biz_id=1,
            bk_data_id=11,
            collector_plugin_id=9,
            collector_config_id=11,
            collector_config_name="synthetic",
            bkbase_v4_resources={"data_id": self.data_ref},
        )
        resource = DataIdTail()
        response = mock.Mock(spec=requests.Response)
        response.status_code = 200
        response.raise_for_status.return_value = None
        response.json.return_value = {"result": True, "code": "00", "data": ["synthetic sample"]}
        resource.session.request = mock.Mock(return_value=response)
        with mock.patch.object(resource, "build_header", return_value={}), mock.patch.object(
            source.api.bk_base_v4, "data_id_tail", resource.request
        ), mock.patch.object(
            source.api.bk_base_v4, "data_source_list", side_effect=AssertionError("unexpected lookup")
        ):
            handler = BkBaseTailLogHandler(owner)
            handler.load_tail_log()
        self.assertEqual(handler.tail_logs, [{"value": "synthetic sample"}])
        self.assertIn(
            "/namespaces/foreign_project/dataids/actual_data/tail_kafka/", resource.session.request.call_args.args[1]
        )

    def test_plugin_selection_uses_real_resource_request(self):
        resource = DataSourceList()
        response = mock.Mock(spec=requests.Response)
        response.status_code = 200
        response.raise_for_status.return_value = None
        response.json.return_value = {"result": True, "code": "00", "data": [self.native]}
        resource.session.request = mock.Mock(return_value=response)
        with mock.patch.object(resource, "build_header", return_value={}), mock.patch.object(
            source.api.bk_base_v4, "data_source_list", resource.request
        ):
            self.assertEqual(PluginEtlHandler(plugin=self.plugin).get_bk_data_id(), 11)
        self.plugin.refresh_from_db()
        self.assertEqual(self.plugin.bkbase_v4_resources["data_id"], self.data_ref)
        self.assertIn("/namespaces/audit/datasources/", resource.session.request.call_args.args[1])

    def test_apply_uses_user_scope_and_persists_verified_binding(self):
        group = collector_resources.resource.databus.collector
        self.native["spec"]["report_config"] = {"type": "log_collection"}
        request = SimpleNamespace(user=SimpleNamespace(username="synthetic_user", is_authenticated=True))
        with mock.patch.object(group, "get_my_data_id_list", return_value=[{"bk_data_id": 11}]), mock.patch.object(
            collector_resources.GlobalMetaConfig, "get", return_value=9
        ), mock.patch.object(source, "get_request_username", return_value="synthetic_user"), mock.patch(
            "services.web.bkbase.common.get_local_request", return_value=request
        ), mock.patch.object(
            source.api.bk_base_v4, "user_data_source_list", return_value=[self.native]
        ) as listing, mock.patch.object(
            source.api.bk_base_v4, "user_data_source_get", return_value=self.native
        ) as get:
            result = collector_resources.ApplyDataIdSource().request(
                {"namespace": "audit", "system_id": "synthetic", "bk_data_id": 11}
            )
        self.assertEqual(result, {"bk_data_id": 11})
        owner = CollectorConfig.objects.get(bk_data_id=11)
        self.assertEqual(owner.bkbase_v4_resources["data_id"], self.data_ref)
        self.assertEqual(owner.bkbase_v4_resources["data_source"], self.src_ref)
        self.assertGreaterEqual(listing.call_count, 1)
        self.assertIs(listing.call_args.kwargs["_request"], request)
        self.assertIs(get.call_args.kwargs["_request"], request)
        get.assert_called_once()

    def test_apply_without_user_permission_does_not_read_or_persist_binding(self):
        group = collector_resources.resource.databus.collector
        with mock.patch.object(group, "get_my_data_id_list", return_value=[]), mock.patch.object(
            collector_resources.GlobalMetaConfig, "get", return_value=9
        ), mock.patch.object(source.api.bk_base_v4, "user_data_source_get") as get:
            with self.assertRaises(ParamsNotValid):
                collector_resources.ApplyDataIdSource().request(
                    {"namespace": "audit", "system_id": "synthetic", "bk_data_id": 11}
                )
        get.assert_not_called()
        self.assertFalse(CollectorConfig.objects.filter(bk_data_id=11).exists())

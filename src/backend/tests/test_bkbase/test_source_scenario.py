"""通过个人正式 SDK 和采集项资源区分来源机制、解析类型及身份。"""
import json
from copy import deepcopy
from types import SimpleNamespace
from unittest import mock

import requests
from django.conf import settings
from django.test import TestCase, override_settings

from api.bk_base_v4.default import BkBaseV4Resource, UserBkBaseV4Resource
from apps.exceptions import ParamsNotValid
from apps.meta.constants import ConfigLevelChoices
from apps.meta.utils.fields import STANDARD_FIELDS
from services.web.bkbase import clean, source
from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.databus.collector import resources
from services.web.databus.collector.etl.etl_config_handler.bk_base_json import (
    BkBaseJsonConfig,
)
from services.web.databus.constants import (
    COLLECTOR_PLUGIN_ID,
    CustomTypeEnum,
    EtlConfigEnum,
    SourcePlatformChoices,
)
from services.web.databus.models import CollectorConfig
from tests.test_bkbase.system_snapshot_fixtures import seed_ready_system_snapshots


@override_settings(BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="default", BKBASE_V4_NAMESPACE="audit")
class SourceScenarioTests(TestCase):
    def setUp(self):
        seed_ready_system_snapshots()
        resources.GlobalMetaConfig.set(
            COLLECTOR_PLUGIN_ID, 9, config_level=ConfigLevelChoices.NAMESPACE.value, instance_key="audit"
        )
        self.request = SimpleNamespace(user=SimpleNamespace(username="synthetic_user", is_authenticated=True))
        self.data_source = {
            "kind": "DataSource",
            "metadata": {
                "tenant": "default",
                "namespace": "audit",
                "name": "synthetic_source",
                "labels": {"raw_data_id": "81"},
            },
            "spec": {
                "basic_info": {
                    "data_source_name": "synthetic_source",
                    "data_source_alias": "Synthetic",
                    "bk_biz_id": settings.DEFAULT_BK_BIZ_ID,
                },
                "data_id": {"kind": "DataId", "tenant": "default", "namespace": "audit", "name": "synthetic_data"},
                "report_config": {"type": "custom"},
            },
        }
        self.source_ref = {
            "kind": "DataSource",
            "tenant": "default",
            "namespace": "audit",
            "name": "synthetic_source",
        }
        self.detail = None
        self.calls = []
        self.enterContext(mock.patch.object(source, "get_request_username", return_value="synthetic_user"))
        self.enterContext(mock.patch("services.web.bkbase.common.get_local_request", return_value=self.request))
        self.enterContext(mock.patch.object(BkBaseV4Resource, "build_header", return_value={}))
        self.enterContext(mock.patch.object(UserBkBaseV4Resource, "build_auth_args", return_value={}))
        self.enterContext(mock.patch("requests.sessions.Session.request", side_effect=self.transport))
        self.enterContext(mock.patch.object(resources, "get_saas_url", return_value="https://synthetic.test"))

    def transport(self, method, url, **kwargs):
        self.assertEqual(method, "GET")
        self.calls.append(url)
        if url.endswith("/datasources/"):
            self.assertIn("/v4/tenants/default/namespaces/audit/datasources/", url)
            value = [self.data_source]
        else:
            source_namespace = self.data_source["metadata"]["namespace"]
            self.assertTrue(
                url.endswith(f"/v4/tenants/default/namespaces/{source_namespace}/datasources/synthetic_source/")
            )
            value = self.detail or self.data_source
        response = requests.Response()
        response.url = url
        response.status_code = 200
        response._content = json.dumps({"result": True, "code": "00", "data": value}).encode()
        return response

    def apply(self, **changes):
        return resources.ApplyDataIdSource().request(
            {"namespace": "audit", "system_id": "synthetic", "bk_data_id": 81, **changes}
        )

    def saved_collector(self, **changes):
        params = {
            "system_id": "synthetic",
            "bk_biz_id": 1,
            "bk_data_id": 81,
            "collector_plugin_id": 2,
            "collector_config_id": 3,
            "collector_config_name": "synthetic",
            "source_platform": SourcePlatformChoices.BKBASE,
            "custom_type": CustomTypeEnum.OTLP_LOG,
            "is_deleted": True,
        }
        return CollectorConfig._objects.create(**{**params, **changes})

    def test_apply_other_project_source_keeps_source_binding(self):
        self.data_source["metadata"]["namespace"] = "bklog"
        self.data_source["spec"]["data_id"]["namespace"] = "bklog"
        self.assertEqual(self.apply(), {"bk_data_id": 81})
        collector = CollectorConfig.objects.get(bk_data_id=81)
        self.assertEqual(collector.system_id, "synthetic")
        self.assertEqual(
            collector.bkbase_v4_resources,
            {
                "data_source": {
                    "kind": "DataSource",
                    "tenant": "default",
                    "namespace": "bklog",
                    "name": "synthetic_source",
                },
                "data_id": {"kind": "DataId", "tenant": "default", "namespace": "bklog", "name": "synthetic_data"},
                "source_raw_data_id": 81,
            },
        )

    def test_list_and_detail_map_only_confirmed_source_mechanisms(self):
        for mechanism, expected in (
            ("log_collection", "log"),
            ("rest_api", "http"),
            ("custom", "custom"),
            ("kafka", "kafka"),
            ("unknown", "unknown"),
            (None, None),
        ):
            with self.subTest(mechanism=mechanism):
                self.data_source["spec"]["report_config"] = {"type": mechanism}
                listed = resources.GetMyDataIdList().request({"bk_biz_id": settings.DEFAULT_BK_BIZ_ID})
                self.assertEqual(listed[0]["custom_type"], expected)
                self.assertFalse(listed[0]["is_applied"])
                detail = resources.GetDataIdDetail().request({"bk_data_id": 81})
                self.assertEqual(detail["custom_type"], expected)

    def test_confirmed_new_log_collection_uses_log_parser_and_binds_actual_refs(self):
        self.data_source["spec"]["report_config"]["type"] = "log_collection"
        self.assertEqual(self.apply(), {"bk_data_id": 81})
        owner = CollectorConfig.objects.get(bk_data_id=81)
        self.assertEqual(owner.custom_type, CustomTypeEnum.LOG)
        self.assertEqual(owner.bkbase_v4_resources["data_source"], self.source_ref)
        self.assertEqual(owner.bkbase_v4_resources["data_id"], self.data_source["spec"]["data_id"])
        self.assertEqual(sum(url.endswith("/datasources/synthetic_source/") for url in self.calls), 1)

    def test_new_sources_keep_projected_type_and_use_json_etl(self):
        for mechanism, expected in (("custom", "custom"), ("rest_api", "http"), ("kafka", "kafka")):
            with self.subTest(mechanism=mechanism):
                self.data_source["spec"]["report_config"]["type"] = mechanism
                self.assertEqual(self.apply(), {"bk_data_id": 81})
                owner = CollectorConfig.objects.get(bk_data_id=81)
                self.assertEqual(owner.custom_type, expected)
                self.assertEqual(owner.etl_config, EtlConfigEnum.BK_BASE_JSON)
                CollectorConfig._objects.filter(pk=owner.pk).delete()

    def test_missing_or_invalid_source_type_is_rejected(self):
        for mechanism in (None, "", "   ", 42, [], "x" * 31, "otlp_log", "otlp_trace"):
            with self.subTest(mechanism=mechanism):
                self.data_source["spec"]["report_config"]["type"] = mechanism
                with self.assertRaises(ParamsNotValid):
                    self.apply()
                self.assertFalse(CollectorConfig._objects.filter(bk_data_id=81).exists())

    def test_historical_types_and_clean_configuration_survive_reapplication(self):
        fields = [{"field_name": "synthetic_field", "option": {"path": ["nested", "field"]}}]
        etl_params = {"json_config": {"path": ["nested"]}}
        for old_type in ("queue", "custom", "cdc", "http", "db", "file"):
            for is_deleted in (True, False):
                with self.subTest(old_type=old_type, is_deleted=is_deleted):
                    owner = self.saved_collector(
                        custom_type=old_type, is_deleted=is_deleted, fields=fields, etl_params=etl_params
                    )
                    self.assertEqual(self.apply(), {"bk_data_id": 81})
                    owner.refresh_from_db()
                    self.assertFalse(owner.is_deleted)
                    self.assertEqual(owner.custom_type, old_type)
                    self.assertEqual(owner.fields, fields)
                    self.assertEqual(owner.etl_params, etl_params)
                    CollectorConfig._objects.filter(pk=owner.pk).delete()

    def test_historical_valid_type_survives_missing_or_invalid_current_type(self):
        owner = self.saved_collector(custom_type="queue")
        for mechanism in (None, "", "   ", 42, "x" * 31):
            with self.subTest(mechanism=mechanism):
                CollectorConfig._objects.filter(pk=owner.pk).update(is_deleted=True, bkbase_v4_resources={})
                self.data_source["spec"]["report_config"]["type"] = mechanism
                self.assertEqual(self.apply(), {"bk_data_id": 81})
                owner.refresh_from_db()
                self.assertEqual(owner.custom_type, "queue")
                self.assertFalse(owner.is_deleted)

    def test_soft_deleted_otlp_keeps_parser_when_old_bindings_are_absent(self):
        owner = self.saved_collector()
        self.assertEqual(self.apply(), {"bk_data_id": 81})
        owner.refresh_from_db()
        self.assertFalse(owner.is_deleted)
        self.assertEqual(owner.custom_type, CustomTypeEnum.OTLP_LOG)
        self.assertEqual(owner.bkbase_v4_resources["data_source"], self.source_ref)

    def test_json_rules_follow_explicit_fields_and_preserved_otlp_type(self):
        owner = self.saved_collector(custom_type="custom", is_deleted=False)
        fields = [
            {
                "field_name": "start_time",
                "field_type": "string",
                "is_time": True,
                "is_dimension": False,
                "option": {"path": "start_time"},
            },
            {
                "field_name": "payload",
                "field_type": "object",
                "is_time": False,
                "is_dimension": False,
                "option": {"path": "payload"},
            },
            {
                "field_name": "nested_text",
                "field_type": "string",
                "is_time": False,
                "is_dimension": False,
                "option": {"path": "body/text"},
            },
            {
                "field_name": "nested_object",
                "field_type": "object",
                "is_time": False,
                "is_dimension": False,
                "option": {"path": "body/object"},
            },
        ]
        for custom_type, use_json_string in (("custom", False), ("custom", True), ("otlp_log", False)):
            with self.subTest(custom_type=custom_type, use_json_string=use_json_string):
                CollectorConfig.objects.filter(pk=owner.pk).update(custom_type=custom_type)
                handler = BkBaseJsonConfig(
                    config_name="synthetic",
                    config_name_en="synthetic",
                    collector_config_id=3,
                    data_id=81,
                    fields=deepcopy(fields),
                    system_id="synthetic",
                    etl_params={"use_json_string": use_json_string},
                )
                nodes = handler.json_config["extract"]["next"]["next"]
                payload = next(node for node in nodes if node.get("key") == "payload") if use_json_string else None
                if use_json_string:
                    self.assertEqual(payload["next"]["method"], "from_json")
                else:
                    self.assertTrue(
                        any(
                            node.get("subtype") == "assign_json"
                            and any(item.get("assign_to") == "payload" for item in node.get("assign", []))
                            for node in nodes
                        )
                    )
                text_node = next(
                    node
                    for node in nodes
                    if node.get("key") == "body"
                    and node["next"].get("type") == "branch"
                    and any(child.get("subtype") == "assign_obj" for child in node["next"]["next"])
                )
                self.assertEqual(text_node["next"]["next"][0]["assign"][0]["key"], "text")
                object_node = next(
                    node for node in nodes if node.get("key") == "body" and node.get("result") == "body_json_tmp"
                )
                if custom_type == "otlp_log":
                    self.assertEqual(object_node["next"]["next"][0]["next"]["method"], "from_json")
                else:
                    self.assertEqual(object_node["next"]["subtype"], "assign_json")
                    self.assertEqual(object_node["next"]["assign"][0]["key"], "object")

    def test_api_push_is_not_imported_by_apply(self):
        owner = self.saved_collector(source_platform=SourcePlatformChoices.BKLOG, etl_config=EtlConfigEnum.BK_LOG_JSON)
        for is_deleted in (True, False):
            with self.subTest(is_deleted=is_deleted):
                CollectorConfig._objects.filter(pk=owner.pk).update(is_deleted=is_deleted)
                before = CollectorConfig._objects.values().get(pk=owner.pk)
                with self.assertRaises(ParamsNotValid):
                    self.apply()
                self.assertEqual(CollectorConfig._objects.values().get(pk=owner.pk), before)

    def test_bkbase_otlp_apply_flows_to_the_existing_data_id_etl_entry(self):
        owner = self.saved_collector()
        applied = self.apply()
        handler = resources.EtlClean.get_instance(EtlConfigEnum.BK_BASE_JSON)
        fields = [
            {**field.to_json(), "option": {"path": [field.field_name]}}
            for field in STANDARD_FIELDS
            if field.is_required and field.is_display
        ]
        with mock.patch.object(
            type(handler), "get_bkbase_etl_config", return_value={"json_config": {}}
        ), mock.patch.object(clean, "configure_clean") as configure:
            resources.DataIdEtlStorage().request({"namespace": "audit", "fields": fields, **applied})
        configure.assert_called_once()
        selected = configure.call_args.args[0]
        self.assertEqual(selected.pk, owner.pk)
        self.assertEqual(selected.collector_config_id, -81)
        self.assertEqual(selected.custom_type, CustomTypeEnum.OTLP_LOG)
        self.assertEqual(selected.bkbase_v4_resources["data_source"], self.source_ref)

    def test_matching_refs_keep_local_parser_for_existing_rest_api(self):
        saved = {
            "data_source": self.source_ref,
            "data_id": self.data_source["spec"]["data_id"],
            "source_raw_data_id": 81,
        }
        owner = self.saved_collector(bkbase_v4_resources=saved)
        self.data_source["spec"]["report_config"]["type"] = "rest_api"
        self.assertEqual(self.apply(), {"bk_data_id": 81})
        owner.refresh_from_db()
        self.assertEqual(owner.custom_type, CustomTypeEnum.OTLP_LOG)
        self.assertEqual(owner.bkbase_v4_resources, saved)

    def test_bkbase_source_cannot_be_reassigned_to_another_system(self):
        owner = self.saved_collector(collector_config_id=-81)
        for is_deleted in (True, False):
            with self.subTest(is_deleted=is_deleted):
                CollectorConfig._objects.filter(pk=owner.pk).update(is_deleted=is_deleted)
                before = CollectorConfig._objects.values().get(pk=owner.pk)
                with self.assertRaises(ParamsNotValid):
                    self.apply(system_id="other_system")
                self.assertEqual(CollectorConfig._objects.values().get(pk=owner.pk), before)

    def test_conflicting_historical_or_current_identity_never_revives_existing_collector(self):
        owner = self.saved_collector()
        for saved in (
            {"data_source": {**self.source_ref, "name": "different_source"}},
            {"data_id": {**self.data_source["spec"]["data_id"], "name": "different_data"}},
            {"source_raw_data_id": 82},
        ):
            with self.subTest(saved=saved):
                CollectorConfig._objects.filter(pk=owner.pk).update(bkbase_v4_resources=saved)
                before = CollectorConfig._objects.values().get(pk=owner.pk)
                with self.assertRaises(BKBaseResourceMappingError):
                    self.apply()
                self.assertEqual(CollectorConfig._objects.values().get(pk=owner.pk), before)
        CollectorConfig._objects.filter(pk=owner.pk).update(bkbase_v4_resources={})
        self.detail = deepcopy(self.data_source)
        self.detail["metadata"]["labels"]["raw_data_id"] = "82"
        with self.assertRaises(BKBaseResourceMappingError):
            self.apply()
        owner.refresh_from_db()
        self.assertTrue(owner.is_deleted)

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_apply_retains_the_legacy_detail_parser(self):
        group = resources.resource.databus.collector
        detail = {
            "bk_biz_id": 1,
            "raw_data_alias": "Synthetic",
            "raw_data_name": "synthetic_source",
            "custom_type": CustomTypeEnum.OTLP_LOG,
            "description": "",
        }
        with mock.patch.object(group, "get_my_data_id_list", return_value=[{"bk_data_id": 81}]), mock.patch.object(
            group, "get_data_id_detail", return_value=detail
        ):
            self.apply()
        self.assertEqual(CollectorConfig.objects.get(bk_data_id=81).custom_type, CustomTypeEnum.OTLP_LOG)
        self.assertEqual(self.calls, [])

"""验证真实快照规则可以转换为 V4 Clean 规则。"""
import json
import re
from copy import deepcopy
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase, TestCase, override_settings

from apps.meta.models import System
from apps.meta.utils.fields import STANDARD_FIELDS, START_TIME
from services.web.bkbase import clean
from services.web.databus import tasks
from services.web.databus.collector.etl.base import EtlClean
from services.web.databus.collector.resources import CollectorEtlResource
from services.web.databus.collector.snapshot.join.etl_storage import (
    AssetEtlStorageHandler,
    JoinDataEtlStorageHandler,
)
from services.web.databus.constants import (
    TRANSFER_TIME_FORMAT,
    EtlConfigEnum,
    SourcePlatformChoices,
)
from services.web.databus.models import CollectorConfig, CollectorPlugin
from tests.test_bkbase.system_snapshot_fixtures import seed_ready_system_snapshots


class SnapshotCleanRuleTests(SimpleTestCase):
    @staticmethod
    def snapshot_handler(handler_type):
        handler = handler_type(
            data_id=11,
            system=SimpleNamespace(system_id="system_a"),
            resource_type=SimpleNamespace(resource_type_id="resource_a"),
            storage_type="redis",
        )
        if handler_type is AssetEtlStorageHandler:
            handler.__dict__["schema_fields"] = []
        return handler

    def test_snapshot_producers_use_valid_v4_intermediate_names(self):
        for handler_type in (JoinDataEtlStorageHandler, AssetEtlStorageHandler):
            with self.subTest(handler=handler_type.__name__):
                handler = self.snapshot_handler(handler_type)
                config = json.loads(handler.json_config)
                rules = clean.convert_rules(config, fields=handler.result_table_fields)
                seen = {"__raw_data"}
                for rule in rules:
                    self.assertIn(rule["input_id"], seen)
                    self.assertRegex(rule["output_id"], r"^[A-Za-z_][A-Za-z0-9_]*$")
                    seen.add(rule["output_id"])
                results = next(
                    rule for rule in rules if rule["operator"].get("key_index") == [{"type": "key", "value": "results"}]
                )
                iteration = next(rule for rule in rules if rule["operator"]["type"] == "iter")
                self.assertEqual(iteration["input_id"], results["output_id"])
                self.assertIsNotNone(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", results["output_id"]))

    def test_snapshot_producers_convert_legacy_utc_time_to_v4_format(self):
        for handler_type in (JoinDataEtlStorageHandler, AssetEtlStorageHandler):
            with self.subTest(handler=handler_type.__name__):
                handler = self.snapshot_handler(handler_type)
                config = json.loads(handler.json_config)
                self.assertEqual(config["conf"]["time_format"], "yyyy-MM-dd HH:mm:ss")
                rules = clean.convert_rules(config, fields=handler.result_table_fields)
                [time_rule] = [rule for rule in rules if rule["operator"].get("is_time_field")]
                self.assertEqual(time_rule["output_id"], "utctime")
                operator = time_rule["operator"]
                self.assertEqual(operator["type"], "assign")
                self.assertEqual(operator["key_index"], "utctime")
                self.assertEqual(operator["output_type"], "string")
                self.assertEqual(operator["time_format"], {"format": "%Y-%m-%d %H:%M:%S", "zone": 0})

    def test_snapshot_scalar_assignments_use_the_entire_previous_value(self):
        for handler_type in (JoinDataEtlStorageHandler, AssetEtlStorageHandler):
            with self.subTest(handler=handler_type.__name__):
                handler = self.snapshot_handler(handler_type)
                rules = clean.convert_rules(json.loads(handler.json_config), fields=handler.result_table_fields)
                for name in ("system_id", "resource_type_id"):
                    [rule] = [rule for rule in rules if rule["input_id"] == "__" + name]
                    self.assertEqual(rule["output_id"], name)
                    self.assertEqual(rule["operator"]["output_type"], "string")
                    self.assertIsNone(rule["operator"]["key_index"])

    def test_other_time_formats_remain_unchanged(self):
        handler = self.snapshot_handler(JoinDataEtlStorageHandler)
        config = json.loads(handler.json_config)
        for time_format in ("%Y-%m-%d %H:%M:%S", "Unix Time Stamp(milliseconds)", "Unix Timestamp", "yyyy/MM/dd"):
            with self.subTest(time_format=time_format):
                config["conf"].update(time_format=time_format, timezone=8)
                rules = clean.convert_rules(config, fields=handler.result_table_fields)
                [operator] = [rule["operator"] for rule in rules if rule["operator"].get("is_time_field")]
                self.assertEqual(operator["time_format"], {"format": time_format, "zone": 8})

    def test_legacy_millisecond_alias_keeps_zone_and_long_assignment(self):
        [rule] = clean.convert_rules(
            {
                "conf": {"time_field_name": "start_time", "time_format": TRANSFER_TIME_FORMAT, "timezone": 8},
                "extract": {
                    "type": "assign",
                    "assign": [{"key": "event_ms", "assign_to": "start_time", "type": "long"}],
                },
            }
        )
        self.assertEqual(
            rule["operator"],
            {
                "type": "assign",
                "key_index": "event_ms",
                "output_type": "long",
                "is_time_field": True,
                "time_format": {"format": "Unix Time Stamp(milliseconds)", "zone": 8},
            },
        )

    def test_get_default_uses_wire_type_and_preserves_missing_strategy(self):
        for config, expected in (
            ({}, {"default": None}),
            ({"default_type": "null", "default_value": ""}, {"default": None, "missing_strategy": "default"}),
            ({"default_type": "string", "default_value": "0011"}, {"default": "0011", "missing_strategy": "default"}),
            ({"default_type": "int", "default_value": 11}, {"default": "11", "missing_strategy": "default"}),
            ({"default_type": "boolean", "default_value": True}, {"default": True, "missing_strategy": "default"}),
        ):
            with self.subTest(config=config):
                [rule] = clean.convert_rules({"extract": {"type": "access", "key": "value", **config}})
                self.assertEqual(
                    rule["operator"],
                    {"type": "get", "key_index": [{"type": "key", "value": "value"}], **expected},
                )

    def test_generated_intermediate_name_does_not_collide_with_business_field(self):
        config = {
            "extract": {
                "type": "access",
                "subtype": "access_obj",
                "key": "data",
                "result": "response_ results",
                "next": {
                    "type": "assign",
                    "assign": [{"key": "id", "assign_to": "tmp_response__results_0_9b8f5b89c2e2", "type": "string"}],
                },
            }
        }
        rules = clean.convert_rules(config)
        self.assertNotEqual(rules[0]["output_id"], rules[1]["output_id"])
        self.assertEqual(rules[1]["input_id"], rules[0]["output_id"])
        self.assertEqual(rules[1]["output_id"], "tmp_response__results_0_9b8f5b89c2e2")


@override_settings(BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="default", BKBASE_V4_NAMESPACE="audit")
class CollectorCleanTimeRuleTests(TestCase):
    def setUp(self):
        seed_ready_system_snapshots()

    def test_normal_collector_resource_reuses_formally_normalized_running_clean(self):
        system = System.objects.create(system_id="system_a", instance_id="instance_a", namespace="audit", name="Test")
        plugin = CollectorPlugin.objects.create(
            namespace="audit",
            collector_plugin_id=12,
            collector_plugin_name="Test",
            collector_plugin_name_en="test",
            bkdata_biz_id=1,
            table_id=13,
            index_set_id=14,
        )
        fields = [
            {**field.to_json(), "option": {"path": field.field_name}} for field in STANDARD_FIELDS if field.is_display
        ]

        def ref(kind, name):
            return {"kind": kind, "tenant": "default", "namespace": "audit", "name": name}

        data_ref, table_ref, clean_ref = (
            ref("DataId", "input_a"),
            ref("ResultTable", "output_a"),
            ref("Clean", "clean_a"),
        )
        self.enterContext(
            mock.patch("requests.sessions.Session.request", side_effect=AssertionError("Unexpected HTTP"))
        )
        self.enterContext(mock.patch("services.web.databus.collector.etl.base.resource_lock"))
        self.enterContext(mock.patch.object(clean, "resource_lock"))
        self.enterContext(mock.patch.object(clean, "_shared_plugin_table", return_value=("1_shared_0", table_ref)))
        for index, (source_platform, mode) in enumerate(
            (
                (SourcePlatformChoices.BKLOG, EtlConfigEnum.BK_LOG_JSON.value),
                (SourcePlatformChoices.BKBASE, EtlConfigEnum.BK_BASE_JSON.value),
            )
        ):
            with self.subTest(source_platform=source_platform):
                collector = CollectorConfig.objects.create(
                    system_id=system.system_id,
                    bk_biz_id=1,
                    bk_data_id=11 + index,
                    collector_plugin_id=plugin.collector_plugin_id,
                    collector_config_id=15 + index,
                    collector_config_name="Test",
                    collector_config_name_en="test",
                    source_platform=source_platform,
                    bkbase_v4_resources={
                        "data_id": data_ref,
                        "clean": clean_ref,
                        "clean_role": "existing",
                        "result_table": table_ref,
                        "result_table_id": "1_shared_0",
                        "source_raw_data_id": 11 + index,
                    },
                )
                request = {
                    "namespace": "audit",
                    "collector_config_id": collector.collector_config_id,
                    "etl_config": mode,
                    "etl_params": {},
                    "fields": deepcopy(fields),
                }
                validated = CollectorEtlResource().validate_request_data(deepcopy(request))
                params = EtlClean.get_instance(mode).get_bkbase_etl_config(
                    collector, validated["etl_params"], validated["fields"]
                )
                native_spec = clean.build_clean_spec(params, data_ref=data_ref, logical_id="1_shared_0", rt_owner=False)
                # GET 的正式语义：这三处标量取整个输入；iter 的 false 不回显。
                for rule in native_spec["rules"]:
                    if rule["input_id"] in ("__system_id", "__collector_config_id", "__bk_data_id"):
                        rule["operator"]["key_index"] = None
                    if rule["operator"]["type"] == "iter":
                        rule["operator"].pop("reserve_index", None)
                native_spec.update(
                    config_revision=10, deploy_revision=10, desired_status="Running", current_status="Running"
                )
                remote = {
                    "kind": "Clean",
                    "metadata": {key: clean_ref[key] for key in ("tenant", "namespace", "name")},
                    "spec": native_spec,
                    "status": {"phase": "Ok"},
                }
                with mock.patch.object(clean, "get_resource_or_none", return_value=remote), mock.patch.object(
                    clean.api.bk_base_v4, "clean_create"
                ) as create, mock.patch.object(
                    clean.api.bk_base_v4,
                    "clean_update",
                    side_effect=lambda **payload: {
                        "metadata": payload["metadata"],
                        "spec": payload["spec"],
                        "status": {"phase": "Pending"},
                    },
                ) as update, mock.patch.object(
                    clean, "ensure_clean", wraps=clean.ensure_clean
                ) as ensure:
                    CollectorEtlResource().request(deepcopy(request))
                create.assert_not_called()
                update.assert_not_called()
                emitted = ensure.call_args.kwargs["rules"]["rules"]
                for target, source, output_type in (
                    ("system_id", "__system_id", "string"),
                    ("collector_config_id", "__collector_config_id", "int"),
                    ("bk_data_id", "__bk_data_id", "int"),
                ):
                    [rule] = [rule for rule in emitted if rule["input_id"] == source]
                    self.assertEqual(
                        (rule["output_id"], rule["operator"]["key_index"], rule["operator"]["output_type"]),
                        (target, None, output_type),
                    )
                collector.refresh_from_db()
                self.assertTrue(collector.bkbase_v4_resources["clean_ready"])

    def test_field_option_alias_reaches_clean_on_submit_and_periodic_refresh(self):
        system = System.objects.create(system_id="system_a", instance_id="instance_a", namespace="audit", name="Test")
        plugin = CollectorPlugin.objects.create(
            namespace="audit",
            collector_plugin_id=12,
            collector_plugin_name="Test",
            collector_plugin_name_en="test",
            bkdata_biz_id=1,
            table_id=13,
            index_set_id=14,
        )
        data_ref = {"kind": "DataId", "tenant": "default", "namespace": "audit", "name": "input_a"}
        collector = CollectorConfig.objects.create(
            system_id=system.system_id,
            bk_biz_id=1,
            bk_data_id=11,
            collector_plugin_id=plugin.collector_plugin_id,
            collector_config_id=15,
            collector_config_name="Test",
            collector_config_name_en="test",
            bkbase_v4_resources={"data_id": data_ref},
        )
        fields = []
        for field in STANDARD_FIELDS:
            if not (field.is_required and field.is_display):
                continue
            option = {"path": field.field_name}
            if field.field_name == START_TIME.field_name:
                option.update(path="event_ms", val=1793903221000, time_format=TRANSFER_TIME_FORMAT, time_zone=0)
            fields.append({**field.to_json(), "option": option})
        table_ref = {"kind": "ResultTable", "tenant": "default", "namespace": "audit", "name": "output_a"}
        self.enterContext(mock.patch("core.lock.CacheLock")).return_value.locked = False
        with mock.patch.object(
            clean, "_shared_plugin_table", return_value=("shared_logical", table_ref)
        ), mock.patch.object(clean, "ensure_clean") as ensure_clean:
            CollectorEtlResource().request(
                {
                    "namespace": "audit",
                    "collector_config_id": collector.collector_config_id,
                    "etl_config": EtlConfigEnum.BK_LOG_JSON.value,
                    "etl_params": {},
                    "fields": fields,
                }
            )
            collector.refresh_from_db()
            [field] = [field for field in collector.fields if field["field_name"] == START_TIME.field_name]
            self.assertEqual(field["option"]["time_format"], TRANSFER_TIME_FORMAT)
            self.assertEqual(field["option"]["val"], 1793903221000)
            CollectorConfig.objects.filter(pk=collector.pk).update(storage_changed=True)
            tasks.change_storage_cluster.run()

        self.assertEqual(ensure_clean.call_count, 2)
        for call in ensure_clean.call_args_list:
            rules = call.kwargs["rules"]["rules"]
            [rule] = [rule for rule in rules if rule["operator"].get("is_time_field")]
            self.assertEqual(rule["output_id"], START_TIME.field_name)
            self.assertEqual(rule["operator"]["key_index"], "event_ms")
            self.assertEqual(rule["operator"]["output_type"], "long")
            self.assertEqual(rule["operator"]["time_format"], {"format": "Unix Time Stamp(milliseconds)", "zone": 0})
            [data_id_get] = [rule for rule in rules if rule["output_id"] == "__bk_data_id"]
            self.assertEqual(
                data_id_get["operator"],
                {
                    "type": "get",
                    "key_index": [{"type": "key", "value": "__bk_data_id"}],
                    "default": "11",
                    "missing_strategy": "default",
                },
            )
            [data_id_assign] = [rule for rule in rules if rule["input_id"] == "__bk_data_id"]
            self.assertEqual(data_id_assign["output_id"], "bk_data_id")
            self.assertEqual(data_id_assign["operator"]["output_type"], "int")
        collector.refresh_from_db()
        self.assertFalse(collector.storage_changed)

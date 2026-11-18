"""V4预期业务错误按插件持久化隔离，程序错误和V3行为保持原样。"""
from copy import deepcopy
from types import SimpleNamespace
from unittest import mock

from django.test import TransactionTestCase, override_settings

from services.web.bkbase import clean
from services.web.bkbase.common import update_owner_binding
from services.web.bkbase.constants import BKBASE_V4_MAX_POLLS, TaskState
from services.web.databus import tasks
from services.web.databus.constants import PluginSceneChoices
from services.web.databus.exceptions import MultiOrNoneRawDataError
from services.web.databus.models import CollectorPlugin


@override_settings(BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="tenant_a", BKBASE_V4_NAMESPACE="audit")
class PluginErrorIsolationTests(TransactionTestCase):
    def setUp(self):
        self.plugin = CollectorPlugin.objects.create(
            namespace="audit",
            collector_plugin_id=901,
            collector_plugin_name="synthetic bad",
            collector_plugin_name_en="synthetic_bad",
            bkdata_biz_id=7,
            table_id=71,
            index_set_id=81,
            plugin_scene=PluginSceneChoices.COLLECTOR,
            bkbase_v4_resources={"ready": True, "clean_ready": True},
        )
        self.handler = SimpleNamespace(
            plugin=self.plugin, build_clean_config=mock.Mock(side_effect=MultiOrNoneRawDataError())
        )

    def test_source_business_error_is_counted_and_invalidates_old_readiness(self):
        self.assertIsNone(clean.configure_plugin(self.handler))
        self.plugin.refresh_from_db()
        binding = self.plugin.bkbase_v4_resources
        self.assertEqual(binding["poll_count"], 1)
        self.assertFalse(binding["ready"])
        self.assertFalse(binding["clean_ready"])
        self.assertFalse(binding["blocked"])
        self.assertTrue(binding["message"])

    def test_exhausted_error_is_blocked_without_clearing_unknown_evidence(self):
        evidence = {"outcome_unknown": True, "pending_action": "configure", "writer": {"token": "synthetic"}}
        update_owner_binding(self.plugin, {**evidence, "poll_count": BKBASE_V4_MAX_POLLS - 1})
        clean.configure_plugin(self.handler)
        self.plugin.refresh_from_db()
        binding = self.plugin.bkbase_v4_resources
        self.assertEqual(binding["poll_count"], BKBASE_V4_MAX_POLLS)
        self.assertTrue(binding["blocked"])
        self.assertEqual({key: binding[key] for key in evidence}, evidence)

    def test_explicit_retry_can_recover_after_source_configuration_is_corrected(self):
        update_owner_binding(self.plugin, {"ready": False, "poll_count": BKBASE_V4_MAX_POLLS, "blocked": True})
        clean.reset_plugin_operation(self.plugin)
        ref = {"kind": "ResultTable", "tenant": "tenant_a", "namespace": "audit", "name": "known"}
        update_owner_binding(self.plugin, {"result_table_id": "7_known", "result_table": ref})
        self.handler.build_clean_config.side_effect = None
        self.handler.build_clean_config.return_value = {}
        self.handler.build_storage_config = mock.Mock(return_value=({"storage_type": "es"}, None))

        def configured(owner, *args, **kwargs):
            update_owner_binding(owner, {"clean_ready": True})
            return {"task_state": TaskState.RUNNING}

        with mock.patch.object(clean, "configure_clean", side_effect=configured), mock.patch.object(
            clean, "_verified_result_table_ref", return_value=ref
        ), mock.patch.object(
            clean.storage_service, "configure_storage", return_value={"task_state": TaskState.RUNNING}
        ):
            result = clean.configure_plugin(self.handler)
        self.plugin.refresh_from_db()
        self.assertEqual(result["task_state"], TaskState.RUNNING)
        self.assertTrue(self.plugin.bkbase_v4_resources["ready"])
        self.assertFalse(self.plugin.bkbase_v4_resources["blocked"])
        self.assertEqual(self.plugin.bkbase_v4_resources["poll_count"], 1)

    def test_batch_continues_after_expected_error_before_service_entry(self):
        good = CollectorPlugin.objects.create(
            namespace="audit",
            collector_plugin_id=902,
            collector_plugin_name="synthetic good",
            bkdata_biz_id=7,
            table_id=72,
            index_set_id=82,
            plugin_scene=PluginSceneChoices.COLLECTOR,
        )
        bad_handler = SimpleNamespace(create_or_update=mock.Mock(side_effect=MultiOrNoneRawDataError()))
        good_handler = SimpleNamespace(create_or_update=mock.Mock())
        with mock.patch.object(
            tasks.bkbase_clean, "pending_plugins", return_value=[self.plugin, good]
        ), mock.patch.object(tasks, "PluginEtlHandler", side_effect=[bad_handler, good_handler]):
            tasks.create_or_update_plugin_etl.__wrapped__.__wrapped__()
        good_handler.create_or_update.assert_called_once()
        self.plugin.refresh_from_db()
        self.assertEqual(self.plugin.bkbase_v4_resources["poll_count"], 1)
        self.assertFalse(self.plugin.bkbase_v4_resources["ready"])

    def test_batch_blocks_exhausted_bad_plugin_and_keeps_processing_good_plugin(self):
        update_owner_binding(self.plugin, {"ready": False, "poll_count": BKBASE_V4_MAX_POLLS - 1})
        good = CollectorPlugin.objects.create(
            namespace="audit",
            collector_plugin_id=903,
            collector_plugin_name="good",
            bkdata_biz_id=7,
            table_id=73,
            index_set_id=83,
            plugin_scene=PluginSceneChoices.COLLECTOR,
        )
        bad_handler = SimpleNamespace(create_or_update=mock.Mock(side_effect=MultiOrNoneRawDataError()))
        good_handler = SimpleNamespace(create_or_update=mock.Mock())
        handlers = {self.plugin.collector_plugin_id: bad_handler, good.collector_plugin_id: good_handler}
        with mock.patch.object(
            tasks, "PluginEtlHandler", side_effect=lambda collector_plugin_id: handlers[collector_plugin_id]
        ):
            tasks.create_or_update_plugin_etl.__wrapped__.__wrapped__()
            tasks.create_or_update_plugin_etl.__wrapped__.__wrapped__()
        bad_handler.create_or_update.assert_called_once()
        self.assertEqual(good_handler.create_or_update.call_count, 2)
        self.plugin.refresh_from_db()
        self.assertTrue(self.plugin.bkbase_v4_resources["blocked"])
        self.assertEqual(self.plugin.bkbase_v4_resources["poll_count"], BKBASE_V4_MAX_POLLS)

    def test_task_programming_error_is_not_swallowed_or_counted_as_business_failure(self):
        with mock.patch.object(tasks.bkbase_clean, "pending_plugins", return_value=[self.plugin]), mock.patch.object(
            tasks, "PluginEtlHandler", side_effect=TypeError("programming error")
        ):
            with self.assertRaises(TypeError):
                tasks.create_or_update_plugin_etl.__wrapped__.__wrapped__()
        self.plugin.refresh_from_db()
        self.assertNotIn("poll_count", self.plugin.bkbase_v4_resources)

    @override_settings(BKBASE_API_VERSION="v3")
    def test_task_v3_business_error_keeps_original_propagation(self):
        before = deepcopy(self.plugin.bkbase_v4_resources)
        with mock.patch.object(tasks.bkbase_clean, "pending_plugins", return_value=[self.plugin]), mock.patch.object(
            tasks, "PluginEtlHandler", side_effect=MultiOrNoneRawDataError()
        ):
            with self.assertRaises(MultiOrNoneRawDataError):
                tasks.create_or_update_plugin_etl.__wrapped__.__wrapped__()
        self.plugin.refresh_from_db()
        self.assertEqual(self.plugin.bkbase_v4_resources, before)

    def test_programming_error_is_not_swallowed(self):
        self.handler.build_clean_config.side_effect = TypeError("synthetic programming error")
        with self.assertRaises(TypeError):
            clean.configure_plugin(self.handler)

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_business_error_keeps_original_propagation(self):
        self.handler.create_or_update_clean = mock.Mock(side_effect=MultiOrNoneRawDataError())
        before = deepcopy(self.plugin.bkbase_v4_resources)
        with self.assertRaises(MultiOrNoneRawDataError):
            clean.configure_plugin(self.handler)
        self.plugin.refresh_from_db()
        self.assertEqual(self.plugin.bkbase_v4_resources, before)

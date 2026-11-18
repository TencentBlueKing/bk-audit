"""未就绪能力不能在V4部署下静默调用V3。"""

from unittest import mock

from blueapps.utils.logger import logger
from django.test import SimpleTestCase, override_settings

from services.web.bkbase import flow, permissions, source, storage
from services.web.bkbase.exceptions import (
    BKBaseCapabilityNotReady,
    BKBaseResourceMappingError,
)


class CapabilityTests(SimpleTestCase):
    @override_settings(BKBASE_API_VERSION="v4")
    def test_pending_operations_are_explicit(self):
        for module, name, blocker in [
            (permissions, "project_data_batch_check", "B07"),
            (permissions, "project_data_batch_add", "B07"),
            (permissions, "auth_tickets", "B07"),
        ]:
            with self.subTest(operation=name):
                with self.assertRaises(BKBaseCapabilityNotReady) as caught:
                    getattr(module, name)()
                self.assertEqual(caught.exception.blocker_id, blocker)
        with self.assertRaises(BKBaseResourceMappingError):
            source.create_deploy_plan()
        with self.assertRaises(BKBaseResourceMappingError):
            flow.dataflow_batch_status_list()
        for operation, blocker in ((flow.require_batch_history, "B09"),):
            with self.subTest(blocker=blocker), self.assertRaises(BKBaseCapabilityNotReady) as caught:
                operation()
            self.assertEqual(caught.exception.blocker_id, blocker)
        self.assertIsNone(source.require_new_pull_sensitivity())

    @override_settings(BKBASE_API_VERSION="v4")
    def test_invalid_redis_registration_does_not_fall_back_to_v3(self):
        with mock.patch.object(storage.api.bk_base, "create_resource_set") as legacy:
            with self.assertRaises(BKBaseResourceMappingError):
                storage.create_resource_set({"resource_name": "synthetic_redis"})
        legacy.assert_not_called()

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_redis_registration_keeps_legacy_payload(self):
        payload = {"resource_name": "synthetic_redis"}
        with mock.patch.object(storage.api.bk_base, "create_resource_set", return_value={"resource_id": 7}) as legacy:
            self.assertEqual(storage.create_resource_set(payload), {"resource_id": 7})
        legacy.assert_called_once_with(**payload)

    @override_settings(BKBASE_API_VERSION="v4")
    def test_v4_redis_update_is_logged_and_skipped_without_exposing_connection_info(self):
        payload = {
            "resource_set_id": "synthetic_redis",
            "connection_info": {
                "host": "redis.changed.synthetic.test",
                "port": 6380,
                "password": "synthetic_changed_secret",
            },
        }
        with mock.patch.object(storage.api.bk_base, "update_resource_set") as legacy:
            for as_request in [True, False]:
                with self.subTest(as_request=as_request), self.assertLogs(logger, level="WARNING") as emitted:
                    result = (
                        storage.update_resource_set(payload) if as_request else storage.update_resource_set(**payload)
                    )
                self.assertIsNone(result)
                logs = "\n".join(emitted.output)
                self.assertIn("跳过", logs)
                for private in ["synthetic_changed_secret", "redis.changed.synthetic.test", "connection_info"]:
                    self.assertNotIn(private, logs)
        legacy.assert_not_called()

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_redis_update_keeps_original_call_and_return_value(self):
        payload = {"resource_set_id": "synthetic_redis", "connection_info": {"host": "synthetic_host"}}
        for as_request in [True, False]:
            with self.subTest(as_request=as_request), mock.patch.object(
                storage.api.bk_base, "update_resource_set", return_value={"updated": True}
            ) as legacy:
                result = storage.update_resource_set(payload) if as_request else storage.update_resource_set(**payload)
                self.assertEqual(result, {"updated": True})
                legacy.assert_called_once_with(**payload)

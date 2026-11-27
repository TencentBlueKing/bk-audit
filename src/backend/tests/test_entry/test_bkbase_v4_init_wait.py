from unittest import mock

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings

from api.bk_base_v4 import default as sdk
from services.web.entry.init import v4_wait


class V4InitWaitTests(SimpleTestCase):
    def setUp(self):
        self.now = 0.0
        self.sleeps = []
        self.enterContext(mock.patch.object(v4_wait, "monotonic", side_effect=lambda: self.now))
        self.enterContext(mock.patch.object(v4_wait, "sleep", side_effect=self.sleep))

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds

    @override_settings(BKBASE_V4_INIT_TIMEOUT_SECONDS="300")
    def test_shared_deadline_is_not_reset_between_stages(self):
        budget = v4_wait.V4InitWait.from_settings()

        def finish_first():
            self.now = 298
            return {}

        budget.until_ready("redis", finish_first)
        with self.assertRaisesRegex(v4_wait.BKBaseV4InitTimeout, "DataSource"):
            budget.until_ready("snapshot", lambda: {"action": "DataSource"})
        self.assertEqual(self.sleeps, [2])
        self.assertIsNone(sdk.INIT_DEADLINE.get())

    def test_sleep_is_capped_at_deadline(self):
        with self.assertRaises(v4_wait.BKBaseV4InitTimeout):
            v4_wait.V4InitWait(7).until_ready("snapshot", lambda: {"action": "DataConn"})
        self.assertEqual(self.sleeps, [5, 2])

    def test_ready_at_or_after_deadline_is_rejected(self):
        for finished_at in (2, 3):
            with self.subTest(finished_at=finished_at):
                self.now = 0

                def finish_check():
                    self.now = finished_at
                    return {}

                with self.assertRaises(v4_wait.BKBaseV4InitTimeout):
                    v4_wait.V4InitWait(2).until_ready("snapshot", finish_check)
                self.assertEqual(self.sleeps, [])

    @override_settings(BKBASE_V4_INIT_TIMEOUT_SECONDS="0")
    def test_invalid_timeout_is_rejected(self):
        with self.assertRaisesRegex(ImproperlyConfigured, "BKAPP_BKBASE_V4_INIT_TIMEOUT_SECONDS"):
            v4_wait.V4InitWait.from_settings()

    def test_terminal_error_never_sleeps(self):
        def fail():
            raise ValueError("synthetic configuration error")

        with self.assertRaisesRegex(ValueError, "configuration error"):
            v4_wait.V4InitWait(300).until_ready("redis", fail)
        self.assertEqual(self.sleeps, [])

    def test_sdk_write_does_not_start_after_deadline(self):
        resource = sdk.DataSourceUpdate()
        token = sdk.INIT_DEADLINE.set(5)
        try:
            with mock.patch.object(sdk, "monotonic", return_value=5):
                with self.assertRaises(sdk.InitDeadlineBeforeSend):
                    resource.before_request({"json": {"desired_status": "Running"}})
        finally:
            sdk.INIT_DEADLINE.reset(token)

"""未就绪能力不能在V4部署下静默调用V3。"""

from django.test import SimpleTestCase, override_settings

from services.web.bkbase import clean, flow, permissions, source, storage
from services.web.bkbase.exceptions import BKBaseCapabilityNotReady


class CapabilityTests(SimpleTestCase):
    @override_settings(BKBASE_API_VERSION="v4")
    def test_pending_operations_are_explicit(self):
        for module, name, blocker in [
            (storage, "create_resource_set", "B05"),
            (storage, "update_resource_set", "B05"),
            (source, "create_deploy_plan", "B04"),
            (source, "update_deploy_plan", "B04"),
            (clean, "clean_preview", "B06"),
            (flow, "dataflow_batch_status_list", "B09"),
            (permissions, "get_project_data", "B07"),
            (permissions, "project_data_batch_check", "B07"),
            (permissions, "project_data_batch_add", "B07"),
            (permissions, "auth_tickets", "B07"),
            (permissions, "get_role_users_list", "B12"),
            (flow, "get_alert_configs", "B13"),
            (flow, "edit_alert_configs", "B13"),
        ]:
            with self.subTest(operation=name):
                with self.assertRaises(BKBaseCapabilityNotReady) as caught:
                    getattr(module, name)()
                self.assertEqual(caught.exception.blocker_id, blocker)

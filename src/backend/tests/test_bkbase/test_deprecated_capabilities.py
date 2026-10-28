"""V4模型退役不会泄漏旧接口请求，共用项目权限仍独立处理。"""
from unittest import mock

from django.test import SimpleTestCase, override_settings

from services.web.bkbase import deprecated
from services.web.bkbase.exceptions import BKBaseCapabilityDeprecated


class DeprecatedTests(SimpleTestCase):
    @override_settings(BKBASE_API_VERSION="v4")
    def test_model_capability_disabled(self):
        self.assertFalse(deprecated.model_supported())
        self.assertFalse(deprecated.check_aiops())
        with self.assertRaises(BKBaseCapabilityDeprecated):
            deprecated.get_plan_detail(plan_id=1)

    @override_settings(BKBASE_API_VERSION="v3")
    def test_old_deployment_retains_model_probe(self):
        with mock.patch("services.web.bkbase.deprecated.api.bk_base.check_aiops", return_value=True):
            self.assertTrue(deprecated.check_aiops())

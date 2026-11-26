import os
import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase


class TenantSettingsTest(SimpleTestCase):
    def load_tenant_id(self, **overrides):
        # 独立进程按传入环境加载真实设置，不修改当前测试进程的 Django 配置。
        env = os.environ.copy()
        env.pop("BKPAAS_APP_TENANT_ID", None)
        env.pop("BKAPP_AUDIT_INSTANCE_TENANT_ID", None)
        env.update(DJANGO_SETTINGS_MODULE="settings", BKPAAS_MULTI_TENANT_MODE="false")
        env.update(overrides)
        return subprocess.run(
            [sys.executable, "-c", "from django.conf import settings; print(settings.BK_TENANT_ID)"],
            cwd=Path(__file__).resolve().parents[2],
            env=env,
            capture_output=True,
            text=True,
            timeout=20,
        )

    def assert_tenant_id(self, expected, **overrides):
        result = self.load_tenant_id(**overrides)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines()[-1], expected)

    def test_single_tenant_keeps_legacy_default_when_paas_tenant_is_missing_or_empty(self):
        for overrides in ({}, {"BKPAAS_APP_TENANT_ID": ""}):
            with self.subTest(overrides=overrides):
                self.assert_tenant_id("tencent", **overrides)

    def test_single_tenant_prefers_paas_tenant_over_instance_variable(self):
        self.assert_tenant_id(
            "legacy-tenant", BKPAAS_APP_TENANT_ID="legacy-tenant", BKAPP_AUDIT_INSTANCE_TENANT_ID="system"
        )

    def test_multi_tenant_uses_instance_tenant(self):
        self.assert_tenant_id(
            "tencent",
            BKPAAS_MULTI_TENANT_MODE="true",
            BKAPP_AUDIT_INSTANCE_TENANT_ID="tencent",
            BKPAAS_APP_TENANT_ID="system",
        )

    def test_multi_tenant_never_falls_back_to_paas_tenant(self):
        result = self.load_tenant_id(BKPAAS_MULTI_TENANT_MODE="true", BKPAAS_APP_TENANT_ID="system")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("实例绑定租户未设置", result.stderr)

"""Snapshot 管理表单的 V4 敏感级别边界。"""
import json
from unittest import mock

from django.contrib import admin
from django.forms import JSONField, SplitDateTimeWidget
from django.test import RequestFactory, TestCase, override_settings

from services.web.databus.models import Snapshot


class SnapshotAdminSensitivityTests(TestCase):
    def setUp(self):
        self.snapshot = Snapshot.objects.create(
            system_id="admin_test",
            resource_type_id="asset",
            bkbase_data_id=11,
            pull_config={"period": 1},
            bkbase_v4_resources={
                "data_source": {"kind": "DataSource", "tenant": "default", "namespace": "project_a", "name": "source_a"}
            },
        )
        self.request = RequestFactory().get("/admin/databus/snapshot/")
        self.request.user = mock.Mock(is_active=True, is_staff=True, is_superuser=True)
        self.request.user.has_perm.return_value = True
        self.model_admin = admin.site._registry[Snapshot]

    def form(self, value):
        form_class = self.model_admin.get_form(self.request, obj=self.snapshot)
        original = form_class(instance=self.snapshot)
        data = {}
        for name, field in original.fields.items():
            initial = original.initial.get(name, field.initial)
            if isinstance(field, JSONField):
                data[name] = json.dumps(value if name == "pull_config" else initial)
            elif isinstance(field.widget, SplitDateTimeWidget) and initial is not None:
                data[name + "_0"] = initial.strftime("%Y-%m-%d")
                data[name + "_1"] = initial.strftime("%H:%M:%S")
            elif initial is not None:
                data[name] = initial
        return form_class(data=data, instance=self.snapshot)

    @override_settings(BKBASE_API_VERSION="v4")
    def test_changed_sensitivity_is_allowed(self):
        form = self.form({"period": 1, "sensitivity": "public"})
        self.assertTrue(form.is_valid(), form.errors)

    @override_settings(BKBASE_API_VERSION="v4")
    def test_same_effective_value_and_other_fields_are_allowed(self):
        for value in ({"period": 5}, {"period": 5, "sensitivity": "private"}):
            with self.subTest(value=value):
                form = self.form(value)
                self.assertTrue(form.is_valid(), form.errors)
                self.assertNotIn("bkbase_v4_resources", form.fields)
                self.assertIn("bkbase_v4_resources", self.model_admin.readonly_fields)

    @override_settings(BKBASE_API_VERSION="v4")
    def test_null_and_missing_sensitivity_are_allowed(self):
        form = self.form({"sensitivity": None})
        self.assertTrue(form.is_valid(), form.errors)
        self.snapshot.refresh_from_db()
        self.snapshot.pull_config = {"sensitivity": None}
        self.snapshot.save(update_fields=["pull_config"])
        same = self.form({"sensitivity": None, "period": 2})
        self.assertTrue(same.is_valid(), same.errors)
        removed = self.form({"period": 2})
        self.assertTrue(removed.is_valid(), removed.errors)

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_sensitivity_change_allowed(self):
        form = self.form({"sensitivity": "public", "period": 5})
        self.assertTrue(form.is_valid(), form.errors)

    @override_settings(BKBASE_API_VERSION="v4")
    def test_v4_rejects_non_object_pull_config(self):
        for value in (["broken"], "broken"):
            with self.subTest(value=value):
                form = self.form(value)
                self.assertFalse(form.is_valid())
                self.assertIn("pull_config", form.errors)

    @override_settings(BKBASE_API_VERSION="v4")
    def test_v4_allows_null_pull_config(self):
        form = self.form(None)
        self.assertTrue(form.is_valid(), form.errors)

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_does_not_add_object_validation(self):
        form = self.form(["legacy"])
        self.assertTrue(form.is_valid(), form.errors)

"""新装默认审批套餐只绑定本实例场景，不替换历史套餐。"""
import json
import os
from types import SimpleNamespace
from unittest import mock

from django.test import TestCase, override_settings

from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.risk.handlers.ticket import ForApprove
from services.web.risk.models import ProcessApplication
from services.web.scene.constants import DEFAULT_SCENE_NAME
from services.web.scene.models import ResourceBinding, ResourceBindingScene, Scene


@override_settings(BKAPP_ENABLE_ITSM_V4=True)
class InitItsmApprovalTests(TestCase):
    package = {
        "uuid": "00000000000000000000000000000001",
        "name": "默认审批",
        "sops_template_id": 9,
        "workflow_key": "published_workflow",
    }

    def setUp(self):
        self.enterContext(
            mock.patch.dict(
                os.environ, {"BKAPP_INIT_ITSM_APPROVAL_CONFIG": json.dumps({"default_package": self.package})}
            )
        )
        self.enterContext(
            mock.patch("requests.sessions.Session.request", side_effect=AssertionError("Unexpected HTTP"))
        )
        Scene._objects.filter(scene_id=1).update(name=DEFAULT_SCENE_NAME, status="enabled", is_deleted=False)
        if not Scene.objects.filter(scene_id=1).exists():
            Scene.objects.create(scene_id=1, name=DEFAULT_SCENE_NAME)

    def run_init(self):
        from services.web.entry.init.itsm_approval import (
            init_itsm_approval,
            validate_itsm_approval,
        )

        init_itsm_approval(validate_itsm_approval())

    def test_fresh_v4_install_seeds_default_package_at_system_scene_one(self):
        self.run_init()
        package = ProcessApplication.objects.get(uniq_id=self.package["uuid"])
        self.assertEqual(package.approve_config, {})
        self.assertEqual(package.approve_service_id, "published_workflow")
        self.assertEqual(
            list(
                ResourceBindingScene.objects.filter(binding__resource_id=str(package.id)).values_list(
                    "scene_id", flat=True
                )
            ),
            [1],
        )

    def test_wrong_disabled_or_missing_scene_one_never_binds(self):
        for values in ({"name": "other"}, {"status": "disabled"}, {"is_deleted": True}):
            with self.subTest(values=values):
                Scene._objects.filter(scene_id=1).update(
                    name=DEFAULT_SCENE_NAME,
                    status="enabled",
                    is_deleted=False,
                    **{k: v for k, v in values.items() if k not in ("name", "status", "is_deleted")}
                )
                Scene._objects.filter(scene_id=1).update(**values)
                with self.assertRaises(BKBaseResourceMappingError):
                    self.run_init()
                self.assertFalse(ProcessApplication.objects.exists())

    def test_same_uuid_is_idempotent_and_same_name_not_adopted(self):
        self.run_init()
        self.run_init()
        self.assertEqual(ProcessApplication.objects.count(), 1)
        config = {**self.package, "uuid": "00000000000000000000000000000002"}
        os.environ["BKAPP_INIT_ITSM_APPROVAL_CONFIG"] = json.dumps({"default_package": config})
        with self.assertRaises(BKBaseResourceMappingError):
            self.run_init()
        self.assertEqual(ProcessApplication.objects.count(), 1)

    def test_existing_package_and_legacy_migration_unchanged(self):
        self.run_init()
        package = ProcessApplication.objects.get()
        package.approve_config = {"risk_level": {"value": "high"}}
        package.save()
        self.run_init()
        package.refresh_from_db()
        self.assertEqual(package.approve_config, {"risk_level": {"value": "high"}})
        with override_settings(BKAPP_ENABLE_ITSM_V4=False), mock.patch.dict(
            os.environ, {"BKAPP_INIT_ITSM_APPROVAL_CONFIG": "invalid"}
        ):
            self.run_init()
        self.assertEqual(ProcessApplication.objects.count(), 1)

    def test_default_package_handles_non_builtin_approval_field(self):
        self.run_init()
        handler = ForApprove.__new__(ForApprove)
        handler.process_application = ProcessApplication.objects.get()
        handler.risk = SimpleNamespace(risk_id="risk", operator=["test"], risk_level="high", get_tag_names=lambda: [])
        with mock.patch("services.web.risk.handlers.ticket.get_saas_url", return_value="https://audit.example"):
            self.assertEqual(
                handler._build_approve_form_data({"fields": [{"key": "ticket__risk_level"}]}),
                {"ticket__risk_level": "high"},
            )

    def test_invalid_input_and_existing_wrong_binding_fail_without_overwrite(self):
        self.run_init()
        package = ProcessApplication.objects.get()
        ResourceBinding.objects.filter(resource_id=str(package.id), resource_type="process_application").delete()
        with self.assertRaises(BKBaseResourceMappingError):
            self.run_init()
        os.environ["BKAPP_INIT_ITSM_APPROVAL_CONFIG"] = json.dumps(
            {"default_package": {**self.package, "approve_config": {}}}
        )
        with self.assertRaises(BKBaseResourceMappingError):
            self.run_init()

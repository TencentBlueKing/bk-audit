"""旧队列控制器写任务不能在切换 BKBase 协议后重新解释。"""
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase, override_settings

from services.web.analyze.constants import BaseControlTypeChoices
from services.web.analyze.controls.base import BkbaseFlowController
from services.web.analyze.tasks import call_controller


class ControllerTaskVersionTests(SimpleTestCase):
    def test_cross_version_queued_writes_are_rejected_before_loading_controller(self):
        for current, queued in (("v4", None), ("v4", "v3"), ("v3", "v4")):
            with self.subTest(current=current, queued=queued), override_settings(BKBASE_API_VERSION=current):
                with mock.patch("services.web.analyze.controls.rule_audit.RuleAuditController") as cls:
                    kwargs = {} if queued is None else {"bkbase_version": queued}
                    call_controller("create", 1, BaseControlTypeChoices.RULE_AUDIT, **kwargs)
                cls.assert_not_called()

    def test_current_version_direct_invocations_preserve_arguments(self):
        for current in ("v3", "v4"):
            with self.subTest(current=current), override_settings(BKBASE_API_VERSION=current):
                with mock.patch("services.web.analyze.controls.rule_audit.RuleAuditController") as cls:
                    call_controller(
                        "update",
                        1,
                        BaseControlTypeChoices.RULE_AUDIT,
                        "fixture",
                        bkbase_version=current,
                        status="updating",
                    )
                    cls.assert_called_once_with(strategy_id=1)
                    cls.return_value.update.assert_called_once_with("fixture", status="updating")
        with override_settings(BKBASE_API_VERSION="v3"):
            with mock.patch("services.web.analyze.controls.rule_audit.RuleAuditController") as cls:
                call_controller("create", 1, BaseControlTypeChoices.RULE_AUDIT)
                cls.return_value.create.assert_called_once_with()

    def test_async_producer_freezes_the_current_version(self):
        for version in ("v3", "v4"):
            with self.subTest(version=version), override_settings(BKBASE_API_VERSION=version):
                controller = SimpleNamespace(
                    strategy=mock.Mock(strategy_id=42),
                    base_control_type=BaseControlTypeChoices.RULE_AUDIT,
                    _update_or_create=SimpleNamespace(__name__="_update_or_create"),
                )
                with mock.patch(
                    "services.web.analyze.controls.base.bkbase_flow.prepare_controller_update", return_value=False
                ), mock.patch("services.web.analyze.controls.base.call_controller.delay") as delay:
                    BkbaseFlowController.update_or_create(controller, "updating")
                if version == "v4":
                    self.assertEqual(delay.call_args.kwargs["bkbase_version"], version)
                else:
                    self.assertNotIn("bkbase_version", delay.call_args.kwargs)

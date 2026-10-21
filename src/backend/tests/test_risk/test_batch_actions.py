"""批量处理预览 & 批量接口集成测试"""

from types import SimpleNamespace
from unittest import mock

from bk_resource import resource

from services.web.risk.constants import RiskDisplayStatus, RiskLabel, RiskStatus
from services.web.risk.exceptions import BulkSelectionOverLimit
from services.web.risk.models import Risk
from services.web.risk.resources.risk import (
    _build_batch_actions_preview,
    _selection_token,
)
from services.web.risk.serializers import (
    BULK_ACTION_MAX_RISK_IDS,
    BULK_AUTO_PROCESS_MAX_RISK_IDS,
    BatchActionsPreviewReqSerializer,
    BatchConfirmRiskRequestSerializer,
    BulkAutoProcessReqSerializer,
)
from services.web.strategy_v2.models import Strategy
from tests.base import TestCase as BaseTestCase

_USERNAME = "tester"

_DISPLAY_BY_STATUS = {
    RiskStatus.NEW: RiskDisplayStatus.NEW,
    RiskStatus.PENDING_CONFIRM: RiskDisplayStatus.PENDING_CONFIRM,
    RiskStatus.AWAIT_PROCESS: RiskDisplayStatus.AWAIT_PROCESS,
    RiskStatus.FOR_APPROVE: RiskDisplayStatus.FOR_APPROVE,
    RiskStatus.AUTO_PROCESS: RiskDisplayStatus.AUTO_PROCESS,
    RiskStatus.CLOSED: RiskDisplayStatus.CLOSED,
}


def _stub(display_status, status, strategy_id=1, scene_id=1, risk_label=RiskLabel.NORMAL):
    return SimpleNamespace(
        display_status=display_status,
        status=status,
        strategy_id=strategy_id,
        scene_id=scene_id,
        risk_label=risk_label,
    )


class TestBatchActionsPreview(BaseTestCase):
    def setUp(self):
        super().setUp()
        patcher = mock.patch("services.web.risk.resources.risk.get_request_username", return_value=_USERNAME)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.strategy = Strategy.objects.create(
            strategy_id=99,
            strategy_name="预览策略",
            strategy_type="model",
            namespace=self.namespace,
            status="running",
        )

    def _mk(self, idx, status, operator=("tester",), display_status=None, scene_id=1, strategy=None):
        return Risk.objects.create(
            risk_id=f"preview_risk_{idx}",
            strategy=strategy or self.strategy,
            status=status,
            display_status=display_status or _DISPLAY_BY_STATUS[status],
            scene_id=scene_id,
            event_time="2024-01-01T00:00:00Z",
            raw_event_id=f"pe_{idx}",
            current_operator=list(operator),
        )

    def test_await_process_uniform(self):
        r1 = self._mk(1, RiskStatus.AWAIT_PROCESS)
        r2 = self._mk(2, RiskStatus.AWAIT_PROCESS)
        resp = resource.risk.batch_actions_preview(risk_ids=[r1.risk_id, r2.risk_id])
        self.assertTrue(resp["actions"]["trans"]["enabled"])
        self.assertTrue(resp["actions"]["close"]["enabled"])
        self.assertTrue(resp["actions"]["misreport"]["enabled"])
        self.assertTrue(resp["actions"]["auto_process"]["enabled"])
        self.assertFalse(resp["actions"]["confirm"]["enabled"])
        self.assertEqual(resp["actions"]["confirm"]["disabled_reason"], "所选风险包含待处理，不支持风险确认")
        self.assertTrue(resp["batch_enabled"])
        self.assertEqual(resp["batch_disabled_reason"], "")
        self.assertEqual(resp["unique_strategy_id"], self.strategy.strategy_id)
        self.assertEqual(resp["scene_id"], 1)
        self.assertEqual(resp["selected_count"], 2)

    def test_pending_confirm_uniform_enables_confirm(self):
        r1 = self._mk(1, RiskStatus.PENDING_CONFIRM)
        r1.confirmer = [_USERNAME]
        r1.display_status = RiskDisplayStatus.PENDING_CONFIRM
        r1.save(update_fields=["confirmer", "display_status"])
        resp = resource.risk.batch_actions_preview(risk_ids=[r1.risk_id])
        self.assertTrue(resp["actions"]["confirm"]["enabled"])
        # PENDING_CONFIRM 关单不可用，但确认仍可用，整批不关闭
        self.assertFalse(resp["actions"]["close"]["enabled"])
        self.assertEqual(resp["actions"]["close"]["disabled_reason"], "所选风险包含待确认，不支持人工关单")
        self.assertTrue(resp["batch_enabled"])
        self.assertEqual(resp["batch_disabled_reason"], "")

    def test_mixed_status_disables_trans(self):
        r1 = self._mk(1, RiskStatus.NEW)
        r2 = self._mk(2, RiskStatus.AWAIT_PROCESS)
        resp = resource.risk.batch_actions_preview(risk_ids=[r1.risk_id, r2.risk_id])
        self.assertFalse(resp["batch_enabled"])
        self.assertFalse(resp["actions"]["trans"]["enabled"])
        self.assertEqual(resp["batch_disabled_reason"], "所选风险包含新、待处理，不支持批量处理")
        self.assertEqual(resp["actions"]["trans"]["disabled_reason"], "所选风险包含新，不支持转单")
        self.assertEqual(resp["actions"]["close"]["disabled_reason"], "所选风险包含新，不支持人工关单")

    def test_blocking_status_disables_batch(self):
        r1 = self._mk(1, RiskStatus.FOR_APPROVE)
        resp = resource.risk.batch_actions_preview(risk_ids=[r1.risk_id])
        self.assertFalse(resp["batch_enabled"])
        self.assertIn("自动处理审批中", resp["batch_disabled_reason"])
        self.assertFalse(any(item["enabled"] for item in resp["actions"].values()))

    def test_closed_only_enables_misreport(self):
        r1 = self._mk(1, RiskStatus.CLOSED)
        resp = resource.risk.batch_actions_preview(risk_ids=[r1.risk_id])
        self.assertTrue(resp["batch_enabled"])
        self.assertEqual(resp["batch_disabled_reason"], "")
        self.assertTrue(resp["actions"]["misreport"]["enabled"])
        self.assertFalse(resp["actions"]["close"]["enabled"])
        self.assertIn("已关单", resp["actions"]["close"]["disabled_reason"])
        self.assertFalse(resp["actions"]["trans"]["enabled"])
        self.assertFalse(resp["actions"]["confirm"]["enabled"])

    def test_closed_misreport_label_disables_misreport(self):
        """标记误报关单的单子 risk_label=misreport，不能再批量误报，但可解除误报"""
        r1 = self._mk(1, RiskStatus.CLOSED)
        Risk.objects.filter(risk_id=r1.risk_id).update(risk_label=RiskLabel.MISREPORT)
        resp = resource.risk.batch_actions_preview(risk_ids=[r1.risk_id])
        self.assertTrue(resp["batch_enabled"])
        self.assertEqual(resp["batch_disabled_reason"], "")
        self.assertFalse(resp["actions"]["misreport"]["enabled"])
        self.assertEqual(resp["actions"]["misreport"]["disabled_reason"], "所选风险包含已误报，不支持误报")
        self.assertTrue(resp["actions"]["unmisreport"]["enabled"])
        self.assertEqual(resp["actions"]["unmisreport"]["disabled_reason"], "")

    def test_closed_only_disables_unmisreport(self):
        """普通关单（未标记误报）不可解除误报"""
        r1 = self._mk(1, RiskStatus.CLOSED)
        resp = resource.risk.batch_actions_preview(risk_ids=[r1.risk_id])
        self.assertFalse(resp["actions"]["unmisreport"]["enabled"])
        self.assertEqual(resp["actions"]["unmisreport"]["disabled_reason"], "所选风险包含已关单，不支持解除误报")

    def test_await_process_disables_unmisreport(self):
        r1 = self._mk(1, RiskStatus.AWAIT_PROCESS)
        resp = resource.risk.batch_actions_preview(risk_ids=[r1.risk_id])
        self.assertTrue(resp["batch_enabled"])
        self.assertFalse(resp["actions"]["unmisreport"]["enabled"])
        self.assertEqual(resp["actions"]["unmisreport"]["disabled_reason"], "所选风险包含待处理，不支持解除误报")

    def test_mixed_closed_normal_and_misreport_disables_misreport(self):
        risks = [
            _stub(RiskDisplayStatus.CLOSED, RiskStatus.CLOSED),
            _stub(RiskDisplayStatus.CLOSED, RiskStatus.CLOSED, risk_label=RiskLabel.MISREPORT),
        ]
        resp = _build_batch_actions_preview(risks)
        # 正常关单只有误报、已误报只有解除误报，交集为空
        self.assertFalse(resp["batch_enabled"])
        self.assertEqual(resp["batch_disabled_reason"], "所选风险包含已关单、已误报，不支持批量处理")
        self.assertFalse(resp["actions"]["misreport"]["enabled"])
        self.assertEqual(resp["actions"]["misreport"]["disabled_reason"], "所选风险包含已误报，不支持误报")
        self.assertFalse(resp["actions"]["unmisreport"]["enabled"])
        self.assertEqual(resp["actions"]["unmisreport"]["disabled_reason"], "所选风险包含已关单，不支持解除误报")

    def test_over_limit_returns_reason(self):
        with self.assertRaises(BulkSelectionOverLimit) as caught:
            resource.risk.batch_actions_preview(risk_ids=[f"over-{idx}" for idx in range(BULK_ACTION_MAX_RISK_IDS + 1)])
        self.assertEqual(caught.exception.STATUS_CODE, 400)
        self.assertIn("超过上限", str(caught.exception.message))

    def test_filters_are_resolved(self):
        risk = self._mk(1, RiskStatus.AWAIT_PROCESS)
        with mock.patch(
            "services.web.risk.resources.risk._load_bulk_selection",
            return_value=SimpleNamespace(risks=[risk], error=None),
        ) as loader:
            resp = resource.risk.batch_actions_preview(filters={})
        loader.assert_called_once()
        self.assertTrue(resp["actions"]["close"]["enabled"])


class TestBulkCloseRisk(BaseTestCase):
    def setUp(self):
        super().setUp()
        patcher = mock.patch("services.web.risk.resources.risk.get_request_username", return_value=_USERNAME)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.strategy = Strategy.objects.create(
            strategy_id=100,
            strategy_name="关单策略",
            strategy_type="model",
            namespace=self.namespace,
            status="running",
        )

    def _mk(self, idx, status, display_status=None):
        return Risk.objects.create(
            risk_id=f"close_risk_{idx}",
            strategy=self.strategy,
            status=status,
            display_status=display_status or _DISPLAY_BY_STATUS[status],
            scene_id=1,
            event_time="2024-01-01T00:00:00Z",
            raw_event_id=f"ce_{idx}",
            current_operator=["tester"],
        )

    @mock.patch("services.web.risk.resources.risk.CustomCloseRisk.perform_request")
    def test_close_all_success(self, mock_perform):
        mock_perform.return_value = None
        risks = [self._mk(i, RiskStatus.AWAIT_PROCESS) for i in range(1, 3)]
        resp = resource.risk.bulk_close_risk(risk_ids=[r.risk_id for r in risks], description="批量关单")
        self.assertEqual(resp["success_count"], 2)
        self.assertEqual(mock_perform.call_count, 2)

    def test_pending_confirm_rejected(self):
        r = self._mk(1, RiskStatus.PENDING_CONFIRM)
        resp = resource.risk.bulk_close_risk(risk_ids=[r.risk_id], description="批量关单")
        self.assertEqual(resp["success_count"], 0)
        self.assertEqual(len(resp["failed"]), 1)

    def test_auto_approve_rejected(self):
        r = self._mk(1, RiskStatus.FOR_APPROVE)
        resp = resource.risk.bulk_close_risk(risk_ids=[r.risk_id], description="批量关单")
        self.assertEqual(resp["success_count"], 0)
        self.assertIn("自动处理审批中", resp["failed"][0]["reason"])


class TestBatchActionRules(BaseTestCase):
    def test_selection_token_blanks_are_not_the_same(self):
        self.assertEqual(_selection_token([None]), (True, None))
        self.assertEqual(_selection_token([None, None]), (False, None))
        self.assertEqual(_selection_token([1, " 1 "]), (True, "1"))
        self.assertEqual(_selection_token([1, None]), (False, None))

    def test_mixed_confirm_and_processing_only_misreport(self):
        risks = [
            _stub(RiskDisplayStatus.PENDING_CONFIRM, RiskStatus.PENDING_CONFIRM),
            _stub(RiskDisplayStatus.PROCESSING, RiskStatus.AWAIT_PROCESS),
        ]
        resp = _build_batch_actions_preview(risks)
        self.assertTrue(resp["batch_enabled"])
        self.assertTrue(resp["actions"]["misreport"]["enabled"])
        self.assertEqual(resp["actions"]["misreport"]["disabled_reason"], "")
        self.assertEqual(resp["actions"]["confirm"]["disabled_reason"], "所选风险包含处理中，不支持风险确认")
        self.assertEqual(resp["actions"]["close"]["disabled_reason"], "所选风险包含待确认，不支持人工关单")
        self.assertEqual(resp["actions"]["trans"]["disabled_reason"], "所选风险包含待确认，不支持转单")
        self.assertEqual(resp["actions"]["auto_process"]["disabled_reason"], "所选风险包含待确认，不支持处理套餐")
        self.assertEqual(resp["batch_disabled_reason"], "")

    def test_strategy_mismatch_disables_only_package(self):
        risks = [
            _stub(RiskDisplayStatus.AWAIT_PROCESS, RiskStatus.AWAIT_PROCESS, strategy_id=1, scene_id=8),
            _stub(RiskDisplayStatus.AWAIT_PROCESS, RiskStatus.AWAIT_PROCESS, strategy_id=2, scene_id=8),
        ]
        resp = _build_batch_actions_preview(risks)
        self.assertTrue(resp["batch_enabled"])
        self.assertTrue(resp["actions"]["close"]["enabled"])
        self.assertFalse(resp["actions"]["auto_process"]["enabled"])
        self.assertEqual(resp["actions"]["auto_process"]["disabled_reason"], "所选风险策略不同/场景不同，不支持批量处理套餐")
        self.assertEqual(resp["actions"]["confirm"]["disabled_reason"], "所选风险包含待处理，不支持风险确认")
        self.assertEqual(resp["batch_disabled_reason"], "")
        self.assertIsNone(resp["unique_strategy_id"])

    def test_scene_mismatch_disables_only_package(self):
        risks = [
            _stub(RiskDisplayStatus.PROCESSING, RiskStatus.AWAIT_PROCESS, strategy_id=3, scene_id=1),
            _stub(RiskDisplayStatus.AWAIT_PROCESS, RiskStatus.AWAIT_PROCESS, strategy_id=3, scene_id=2),
        ]
        resp = _build_batch_actions_preview(risks)
        self.assertTrue(resp["actions"]["trans"]["enabled"])
        self.assertFalse(resp["actions"]["auto_process"]["enabled"])
        self.assertIn("场景不同", resp["actions"]["auto_process"]["disabled_reason"])
        self.assertIsNone(resp["scene_id"])

    def test_strategy_and_scene_reasons_are_joined(self):
        risks = [
            _stub(RiskDisplayStatus.AWAIT_PROCESS, RiskStatus.AWAIT_PROCESS, strategy_id=1, scene_id=1),
            _stub(RiskDisplayStatus.AWAIT_PROCESS, RiskStatus.AWAIT_PROCESS, strategy_id=2, scene_id=2),
        ]
        resp = _build_batch_actions_preview(risks)
        self.assertTrue(resp["batch_enabled"])
        self.assertEqual(resp["batch_disabled_reason"], "")
        self.assertEqual(
            resp["actions"]["auto_process"]["disabled_reason"],
            "所选风险策略不同/场景不同，不支持批量处理套餐",
        )

    def test_blocking_statuses_are_joined(self):
        risks = [
            _stub(RiskDisplayStatus.FOR_APPROVE, RiskStatus.FOR_APPROVE),
            _stub(RiskDisplayStatus.AUTO_PROCESS, RiskStatus.AUTO_PROCESS),
            _stub(RiskDisplayStatus.AWAIT_PROCESS, RiskStatus.AWAIT_PROCESS),
        ]
        resp = _build_batch_actions_preview(risks)
        self.assertFalse(resp["batch_enabled"])
        self.assertEqual(
            resp["batch_disabled_reason"],
            "所选风险包含自动处理审批中、套餐处理中，不支持批量处理",
        )
        self.assertEqual(resp["actions"]["close"]["disabled_reason"], resp["batch_disabled_reason"])

    def test_package_over_limit_keeps_other_actions(self):
        risks = [_stub(RiskDisplayStatus.AWAIT_PROCESS, RiskStatus.AWAIT_PROCESS) for _ in range(101)]
        resp = _build_batch_actions_preview(risks)
        self.assertTrue(resp["batch_enabled"])
        self.assertTrue(resp["actions"]["close"]["enabled"])
        self.assertFalse(resp["actions"]["auto_process"]["enabled"])
        self.assertIn("超过上限", resp["actions"]["auto_process"]["disabled_reason"])

    def test_preview_rejects_ids_and_filters_together(self):
        serializer = BatchActionsPreviewReqSerializer(data={"risk_ids": ["r1"], "filters": {}})
        self.assertFalse(serializer.is_valid())

    def test_batch_confirm_rejects_over_limit(self):
        serializer = BatchConfirmRiskRequestSerializer(
            data={
                "risk_ids": [f"r{idx}" for idx in range(BULK_ACTION_MAX_RISK_IDS + 1)],
                "description": "确认",
            }
        )
        with self.assertRaises(BulkSelectionOverLimit) as caught:
            serializer.is_valid()
        self.assertEqual(caught.exception.STATUS_CODE, 400)

    def test_bulk_auto_process_rejects_over_package_limit(self):
        serializer = BulkAutoProcessReqSerializer(
            data={
                "risk_ids": [f"r{idx}" for idx in range(BULK_AUTO_PROCESS_MAX_RISK_IDS + 1)],
                "pa_id": 1,
                "pa_params": {},
            }
        )
        with self.assertRaises(BulkSelectionOverLimit) as caught:
            serializer.is_valid()
        self.assertEqual(caught.exception.STATUS_CODE, 400)


class TestBulkMisreportDispatch(BaseTestCase):
    def setUp(self):
        super().setUp()
        patcher = mock.patch("services.web.risk.resources.risk.get_request_username", return_value=_USERNAME)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.strategy = Strategy.objects.create(
            strategy_id=101,
            strategy_name="误报策略",
            strategy_type="model",
            namespace=self.namespace,
            status="running",
        )

    @mock.patch("services.web.risk.resources.risk.MisReport")
    @mock.patch("services.web.risk.resources.risk.ConfirmAsMisReportResource.perform_request")
    def test_dispatch_by_display_status(self, mock_confirm, mock_misreport):
        mock_confirm.return_value = {"success": True}
        mock_misreport.return_value.run.return_value = None
        pending = Risk.objects.create(
            risk_id="mis_pending",
            strategy=self.strategy,
            status=RiskStatus.PENDING_CONFIRM,
            display_status=RiskDisplayStatus.PENDING_CONFIRM,
            scene_id=1,
            event_time="2024-01-01T00:00:00Z",
            raw_event_id="mis_pending_event",
            current_operator=["tester"],
        )
        processing = Risk.objects.create(
            risk_id="mis_processing",
            strategy=self.strategy,
            status=RiskStatus.AWAIT_PROCESS,
            display_status=RiskDisplayStatus.PROCESSING,
            scene_id=1,
            event_time="2024-01-01T00:00:00Z",
            raw_event_id="mis_processing_event",
            current_operator=["tester"],
        )
        resp = resource.risk.bulk_misreport(risk_ids=[pending.risk_id, processing.risk_id], description="标记误报")
        self.assertEqual(resp["success_count"], 2)
        self.assertEqual(mock_confirm.call_args[0][0]["risk_id"], pending.risk_id)
        self.assertEqual(mock_misreport.call_args.kwargs["risk_id"], processing.risk_id)


class TestBulkAutoProcessGuard(BaseTestCase):
    def setUp(self):
        super().setUp()
        patcher = mock.patch("services.web.risk.resources.risk.get_request_username", return_value=_USERNAME)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.strategy = Strategy.objects.create(
            strategy_id=102,
            strategy_name="套餐策略",
            strategy_type="model",
            namespace=self.namespace,
            status="running",
        )
        self.other = Strategy.objects.create(
            strategy_id=103,
            strategy_name="另一策略",
            strategy_type="model",
            namespace=self.namespace,
            status="running",
        )

    def _mk(self, idx, strategy, status=RiskStatus.AWAIT_PROCESS):
        return Risk.objects.create(
            risk_id=f"pa_risk_{idx}",
            strategy=strategy,
            status=status,
            display_status=_DISPLAY_BY_STATUS[status],
            scene_id=1,
            event_time="2024-01-01T00:00:00Z",
            raw_event_id=f"pa_event_{idx}",
            current_operator=["tester"],
        )

    @mock.patch("services.web.risk.resources.risk.CustomAutoProcess.perform_request")
    def test_different_strategy_fails_whole_batch(self, mock_perform):
        first = self._mk(1, self.strategy)
        second = self._mk(2, self.other)
        resp = resource.risk.bulk_auto_process(
            risk_ids=[first.risk_id, second.risk_id],
            pa_id=1,
            pa_params={},
            auto_close_risk=False,
        )
        self.assertEqual(resp["success_count"], 0)
        self.assertEqual(len(resp["failed"]), 2)
        self.assertIn("策略不同", resp["failed"][0]["reason"])
        mock_perform.assert_not_called()

    @mock.patch("services.web.risk.resources.risk.CustomAutoProcess.perform_request")
    def test_strategy_and_scene_reasons_are_joined_on_execute(self, mock_perform):
        first = self._mk(1, self.strategy)
        second = self._mk(2, self.other)
        second.scene_id = 2
        second.save(update_fields=["scene_id"])
        resp = resource.risk.bulk_auto_process(
            risk_ids=[first.risk_id, second.risk_id],
            pa_id=1,
            pa_params={},
            auto_close_risk=False,
        )
        self.assertEqual(
            resp["failed"][0]["reason"],
            "所选风险策略不同/场景不同，不支持批量处理套餐",
        )
        mock_perform.assert_not_called()

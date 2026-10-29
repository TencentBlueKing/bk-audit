"""批量处理预览 & 批量接口集成测试"""

from types import SimpleNamespace
from unittest import mock

from bk_resource import resource

from apps.permission.handlers.actions import ActionEnum
from apps.permission.handlers.drf import IAMPermission
from services.web.risk.constants import RiskDisplayStatus, RiskLabel, RiskStatus
from services.web.risk.exceptions import AutoProcessParamsError, BulkSelectionOverLimit
from services.web.risk.models import ProcessApplication, Risk
from services.web.risk.permissions import (
    BatchRiskTicketPermission,
    RiskConfirmPermission,
    RiskTicketPermission,
)
from services.web.risk.resources.risk import (
    _build_batch_actions_preview,
    _load_bulk_selection,
    _selection_token,
    resolve_bulk_risk_ids,
)
from services.web.risk.serializers import (
    BULK_ACTION_MAX_RISK_IDS,
    BULK_AUTO_PROCESS_MAX_RISK_IDS,
    BatchActionsPreviewReqSerializer,
    BatchConfirmRiskRequestSerializer,
    BulkAutoProcessReqSerializer,
)
from services.web.risk.views import RisksViewSet
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

    @mock.patch("services.web.risk.resources.risk.UpdateRiskLabel.request")
    def test_misreport_uses_single_audit_entry(self, mock_request):
        # request() 才会带上 PROCESS_RISK 审计；直接 run() 成功但事件为零。
        mock_request.return_value = None
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
        self.assertEqual(resp["failed"], [])
        labels = {call.args[0]["risk_id"]: call.args[0]["risk_label"] for call in mock_request.call_args_list}
        self.assertEqual(labels, {pending.risk_id: RiskLabel.MISREPORT, processing.risk_id: RiskLabel.MISREPORT})

    @mock.patch("services.web.risk.resources.risk.UpdateRiskLabel.request")
    def test_unmisreport_uses_single_audit_entry(self, mock_request):
        mock_request.return_value = None
        risk = Risk.objects.create(
            risk_id="unmis_closed",
            strategy=self.strategy,
            status=RiskStatus.CLOSED,
            display_status=RiskDisplayStatus.CLOSED,
            risk_label=RiskLabel.MISREPORT,
            scene_id=1,
            event_time="2024-01-01T00:00:00Z",
            raw_event_id="unmis_closed_event",
            current_operator=["tester"],
        )
        resp = resource.risk.bulk_unmisreport(risk_ids=[risk.risk_id], new_operators=["alice"])
        self.assertEqual(resp["success_count"], 1)
        self.assertEqual(resp["failed"], [])
        payload = mock_request.call_args.args[0]
        self.assertEqual(payload["risk_id"], risk.risk_id)
        self.assertEqual(payload["risk_label"], RiskLabel.NORMAL)
        self.assertEqual(payload["new_operators"], ["alice"])


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


class TestResolveBulkRiskIds(BaseTestCase):
    """权限阶段的 risk_ids 归一化必须与执行阶段（FlexibleListField + 去重排序）一致，否则会漏校验。"""

    def test_single_string_is_wrapped_not_split_to_chars(self):
        # 旧实现 list("r1") 会变成 ['r','1']，权限查询命中空集合而直接放行（越权）。
        self.assertEqual(resolve_bulk_risk_ids({"risk_ids": "r1"}, _USERNAME), ["r1"])

    def test_comma_string_is_split(self):
        self.assertEqual(resolve_bulk_risk_ids({"risk_ids": "r1,r2"}, _USERNAME), ["r1", "r2"])

    def test_whitespace_is_stripped_and_deduped(self):
        self.assertEqual(
            resolve_bulk_risk_ids({"risk_ids": [" r1 ", "r1", "r2 "]}, _USERNAME),
            ["r1", "r2"],
        )

    def test_list_is_sorted_and_deduped(self):
        self.assertEqual(resolve_bulk_risk_ids({"risk_ids": ["r2", "r1", "r1"]}, _USERNAME), ["r1", "r2"])

    def test_empty_falls_through_to_filters_branch(self):
        # 没有 risk_ids 且有 filters 时交给筛选分支；两者皆无返回空（请求会被序列化拦截）。
        self.assertEqual(resolve_bulk_risk_ids({}, _USERNAME), [])

    def test_filter_execution_reuses_permission_ids(self):
        # 权限和执行各查一次时，中间新增的风险会绕过处理权限。执行必须沿用第一次的 ID。
        request = SimpleNamespace()
        calls = []

        def fake_load(self, validated_request_data, username, risk_limit):
            calls.append(risk_limit)
            return ["r_checked"] if len(calls) == 1 else ["r_new"]

        with mock.patch("blueapps.utils.request_provider.get_local_request", return_value=request), mock.patch(
            "services.web.risk.resources.risk.ListRisk.load_filter_risk_ids", fake_load
        ), mock.patch("services.web.risk.resources.risk.Risk.objects.filter") as filt:
            filt.return_value = [SimpleNamespace(risk_id="r_checked")]
            self.assertEqual(resolve_bulk_risk_ids({"filters": {"title": "x"}}, _USERNAME), ["r_checked"])
            pick = _load_bulk_selection({"filters": {"title": "x"}}, 500)
        self.assertEqual(calls, [501])
        self.assertEqual(pick.risk_ids, ["r_checked"])


class TestBatchPermissionNormalization(BaseTestCase):
    """权限校验必须基于归一化后的实际执行目标，未授权用户不能因 ID 集合不一致而越权。"""

    def setUp(self):
        super().setUp()
        patcher = mock.patch("services.web.risk.resources.risk.get_request_username", return_value=_USERNAME)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.strategy = Strategy.objects.create(
            strategy_id=105,
            strategy_name="权限策略",
            strategy_type="model",
            namespace=self.namespace,
            status="running",
        )

    def _mk(self, idx):
        return Risk.objects.create(
            risk_id=f"perm_risk_{idx}",
            strategy=self.strategy,
            status=RiskStatus.AWAIT_PROCESS,
            display_status=RiskDisplayStatus.AWAIT_PROCESS,
            scene_id=1,
            event_time="2024-01-01T00:00:00Z",
            raw_event_id=f"pe_{idx}",
            current_operator=["legit_owner"],
        )

    def test_unauthorized_risk_is_denied_with_normalized_ids(self):
        risk = self._mk(1)
        user = SimpleNamespace(username="attacker")
        request = SimpleNamespace(user=user, data={"risk_ids": risk.risk_id})
        view = mock.MagicMock()

        perm = BatchRiskTicketPermission(
            get_risk_ids=lambda: resolve_bulk_risk_ids({"risk_ids": risk.risk_id}, "attacker")
        )
        with mock.patch.object(IAMPermission, "has_permission", return_value=False):
            self.assertFalse(perm.has_permission(request, view))


class TestRiskConfirmPermission(BaseTestCase):
    """确认风险只允许确认人或平台管理员，不沿用处理人权限。"""

    def setUp(self):
        super().setUp()
        self.strategy = Strategy.objects.create(
            strategy_id=106,
            strategy_name="确认权限策略",
            strategy_type="model",
            namespace=self.namespace,
            status="running",
        )

    def _mk(self, idx, confirmer):
        return Risk.objects.create(
            risk_id=f"confirm_perm_{idx}",
            strategy=self.strategy,
            status=RiskStatus.PENDING_CONFIRM,
            display_status=RiskDisplayStatus.PENDING_CONFIRM,
            scene_id=1,
            event_time="2024-01-01T00:00:00Z",
            raw_event_id=f"ce_{idx}",
            current_operator=["processor"],
            confirmer=confirmer,
        )

    def test_confirmer_passes_without_platform_admin(self):
        risk = self._mk(1, ["confirmer"])
        request = SimpleNamespace(user=SimpleNamespace(username="confirmer"), data={}, query_params={})
        view = SimpleNamespace(kwargs={"pk": risk.risk_id})
        perm = RiskConfirmPermission()
        with mock.patch.object(IAMPermission, "has_permission", return_value=False) as iam:
            self.assertTrue(perm.has_permission(request, view))
            iam.assert_not_called()

    def test_processor_is_not_enough(self):
        risk = self._mk(2, ["confirmer"])
        request = SimpleNamespace(user=SimpleNamespace(username="processor"), data={}, query_params={})
        view = SimpleNamespace(kwargs={"pk": risk.risk_id})
        perm = RiskConfirmPermission()
        with mock.patch.object(IAMPermission, "has_permission", return_value=False) as iam:
            self.assertFalse(perm.has_permission(request, view))
            iam.assert_called_once()

    def test_batch_requires_confirmer_on_every_risk(self):
        owned = self._mk(3, ["confirmer"])
        other = self._mk(4, ["someone_else"])
        request = SimpleNamespace(user=SimpleNamespace(username="confirmer"), data={})
        view = mock.MagicMock()
        perm = RiskConfirmPermission(get_risk_ids=lambda: [owned.risk_id, other.risk_id])
        with mock.patch.object(IAMPermission, "has_permission", return_value=False) as iam:
            self.assertFalse(perm.has_permission(request, view))
            iam.assert_called_once()

    def test_batch_confirmer_of_all_passes(self):
        first = self._mk(5, ["confirmer"])
        second = self._mk(6, ["confirmer", "other"])
        request = SimpleNamespace(user=SimpleNamespace(username="confirmer"), data={})
        view = mock.MagicMock()
        perm = RiskConfirmPermission(get_risk_ids=lambda: [first.risk_id, second.risk_id])
        with mock.patch.object(IAMPermission, "has_permission", return_value=False) as iam:
            self.assertTrue(perm.has_permission(request, view))
            iam.assert_not_called()


class TestBatchActionsPermissions(BaseTestCase):
    """预览接口的 action 名为 batch_actions/preview，权限分支必须与之对齐。"""

    def test_preview_action_uses_batch_permission(self):
        view = RisksViewSet()
        view.action = "batch_actions/preview"
        perms = view.get_permissions()
        self.assertEqual(len(perms), 1)
        self.assertIsInstance(perms[0], BatchRiskTicketPermission)

    def test_wrong_preview_name_is_not_matched(self):
        # 旧名称 batch_actions_preview 不会再命中批量处理权限分支。
        view = RisksViewSet()
        view.action = "batch_actions_preview"
        self.assertEqual(view.get_permissions(), [])

    def test_confirm_actions_use_confirm_permission(self):
        for action in ("confirm", "confirm_as_misreport"):
            view = RisksViewSet()
            view.action = action
            perms = view.get_permissions()
            self.assertEqual(len(perms), 1)
            self.assertIsInstance(perms[0], RiskConfirmPermission)
            self.assertEqual(perms[0].actions, [ActionEnum.MANAGE_PLATFORM])

    def test_batch_confirm_actions_use_confirm_permission(self):
        for action in ("batch_confirm", "batch_confirm_as_misreport"):
            view = RisksViewSet()
            view.action = action
            perms = view.get_permissions()
            self.assertEqual(len(perms), 1)
            self.assertIsInstance(perms[0], RiskConfirmPermission)
            self.assertEqual(perms[0].actions, [ActionEnum.MANAGE_PLATFORM])

    def test_process_actions_stay_on_ticket_permission(self):
        view = RisksViewSet()
        view.action = "close"
        self.assertIsInstance(view.get_permissions()[0], RiskTicketPermission)
        view.action = "bulk_close"
        self.assertIsInstance(view.get_permissions()[0], BatchRiskTicketPermission)


class TestAutoProcessParamValidation(BaseTestCase):
    """提交（创建审批单或发起处理任务）前必须校验处理套餐必填参数，覆盖审批与非审批路径。"""

    _TEMPLATE_REQUIRED = {
        "pipeline_tree": {
            "constants": {
                "${mandatory}": {
                    "key": "${mandatory}",
                    "show_type": "show",
                    "source_type": "custom",
                    "is_condition_hide": False,
                }
            }
        }
    }

    def setUp(self):
        super().setUp()
        patcher = mock.patch("services.web.risk.resources.risk.get_request_username", return_value=_USERNAME)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.strategy = Strategy.objects.create(
            strategy_id=106,
            strategy_name="参数策略",
            strategy_type="model",
            namespace=self.namespace,
            status="running",
        )
        ProcessApplication.objects.create(id=1, name="套餐", sops_template_id=1)

    def _mk(self, idx, status=RiskStatus.AWAIT_PROCESS):
        return Risk.objects.create(
            risk_id=f"pa_risk_{idx}",
            strategy=self.strategy,
            status=status,
            display_status=_DISPLAY_BY_STATUS[status],
            scene_id=1,
            event_time="2024-01-01T00:00:00Z",
            raw_event_id=f"pa_event_{idx}",
            current_operator=["tester"],
        )

    @mock.patch("services.web.risk.handlers.ticket.api.bk_sops.get_template_info")
    def test_single_missing_params_raises(self, mock_template):
        mock_template.return_value = self._TEMPLATE_REQUIRED
        risk = self._mk(1)
        with self.assertRaises(AutoProcessParamsError):
            resource.risk.custom_auto_process(risk_id=risk.risk_id, pa_id=1, pa_params={}, auto_close_risk=False)

    @mock.patch("services.web.risk.handlers.ticket.api.bk_sops.get_template_info")
    def test_single_provided_params_passes_validation(self, mock_template):
        mock_template.return_value = self._TEMPLATE_REQUIRED
        # 提供必填变量后不应在提交阶段抛缺参错误（此处由下游逻辑决定成败）。
        from services.web.risk.handlers.ticket import validate_auto_process_params

        # 不应抛异常
        validate_auto_process_params(1, {"${mandatory}": {"value": "x"}})

    @mock.patch("services.web.risk.resources.risk.CustomAutoProcess.perform_request")
    @mock.patch("services.web.risk.handlers.ticket.api.bk_sops.get_template_info")
    def test_bulk_missing_params_fails_whole_batch(self, mock_template, mock_perform):
        mock_template.return_value = self._TEMPLATE_REQUIRED
        first = self._mk(1)
        resp = resource.risk.bulk_auto_process(risk_ids=[first.risk_id], pa_id=1, pa_params={}, auto_close_risk=False)
        self.assertEqual(resp["success_count"], 0)
        self.assertEqual(len(resp["failed"]), 1)
        self.assertIn("缺少模板变量", resp["failed"][0]["reason"])
        mock_perform.assert_not_called()

    @mock.patch("services.web.risk.resources.risk.CustomAutoProcess.perform_request")
    @mock.patch("services.web.risk.handlers.ticket.api.bk_sops.get_template_info")
    def test_bulk_provided_params_does_not_fail_on_params(self, mock_template, mock_perform):
        mock_template.return_value = self._TEMPLATE_REQUIRED
        first = self._mk(1)
        resp = resource.risk.bulk_auto_process(
            risk_ids=[first.risk_id],
            pa_id=1,
            pa_params={"${mandatory}": {"value": "x"}},
            auto_close_risk=False,
        )
        # 参数齐全时不会因缺参进入 failed；此处 mock 掉真实执行，success 由 build 阶段决定。
        self.assertNotIn("缺少模板变量", str(resp))
        # 因执行被 mock，success_count 取决于 mock 返回值；只要没把整批标为缺参失败即可。
        self.assertEqual([f["reason"] for f in resp["failed"]], [])

    @mock.patch("services.web.risk.handlers.ticket.api.bk_sops.get_template_info")
    def test_empty_direct_value_rejected(self, mock_template):
        # 映射存在但值为空白时，审批路径不能建成审批单并计为成功。
        mock_template.return_value = self._TEMPLATE_REQUIRED
        with self.assertRaises(AutoProcessParamsError):
            resource.risk.custom_auto_process(
                risk_id=self._mk(1).risk_id,
                pa_id=1,
                pa_params={"${mandatory}": {"value": ""}},
                auto_close_risk=False,
            )

    @mock.patch("services.web.risk.handlers.ticket.api.bk_sops.get_template_info")
    def test_empty_field_reference_rejected(self, mock_template):
        mock_template.return_value = self._TEMPLATE_REQUIRED
        from services.web.risk.handlers.ticket import validate_auto_process_params

        with self.assertRaises(AutoProcessParamsError):
            validate_auto_process_params(1, {"${mandatory}": {"field": "  ", "value": ""}})

    @mock.patch("services.web.risk.handlers.ticket.api.bk_sops.get_template_info")
    def test_zero_false_and_field_reference_pass(self, mock_template):
        mock_template.return_value = self._TEMPLATE_REQUIRED
        from services.web.risk.handlers.ticket import validate_auto_process_params

        validate_auto_process_params(1, {"${mandatory}": {"value": 0}})
        validate_auto_process_params(1, {"${mandatory}": {"value": False}})
        validate_auto_process_params(1, {"${mandatory}": {"field": "risk_id", "value": ""}})

    @mock.patch("services.web.risk.handlers.ticket.api.bk_sops.get_template_info")
    def test_hidden_condition_empty_mapping_skipped(self, mock_template):
        mock_template.return_value = {
            "pipeline_tree": {
                "constants": {
                    "${mandatory}": {
                        "key": "${mandatory}",
                        "show_type": "show",
                        "source_type": "custom",
                        "is_condition_hide": False,
                    },
                    "${hidden}": {
                        "key": "${hidden}",
                        "show_type": "show",
                        "source_type": "custom",
                        "is_condition_hide": True,
                    },
                }
            }
        }
        from services.web.risk.handlers.ticket import validate_auto_process_params

        validate_auto_process_params(1, {"${mandatory}": {"value": "x"}, "${hidden}": {"value": ""}})

    @mock.patch("services.web.risk.resources.risk.CustomAutoProcess.perform_request")
    @mock.patch("services.web.risk.handlers.ticket.api.bk_sops.get_template_info")
    def test_bulk_empty_value_fails_whole_batch(self, mock_template, mock_perform):
        mock_template.return_value = self._TEMPLATE_REQUIRED
        first = self._mk(1)
        resp = resource.risk.bulk_auto_process(
            risk_ids=[first.risk_id],
            pa_id=1,
            pa_params={"${mandatory}": {"value": "  "}},
            auto_close_risk=False,
        )
        self.assertEqual(resp["success_count"], 0)
        self.assertIn("缺少模板变量", resp["failed"][0]["reason"])
        mock_perform.assert_not_called()

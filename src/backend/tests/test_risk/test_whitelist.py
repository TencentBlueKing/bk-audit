# -*- coding: utf-8 -*-
import datetime
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.db.models import Q
from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from services.web.risk.resources.whitelist import (
    BatchCreateRiskWhitelist,
    CreateRiskWhitelist,
    RiskWhitelistCallback,
)
from services.web.risk.whitelist.constants import (
    HitAction,
    WhitelistStatus,
    WhitelistType,
)
from services.web.risk.whitelist.models import RiskWhitelist
from services.web.risk.whitelist.service import (
    _node_payload,
    _submit_itsm_ticket,
    _ticket_on_rule,
    assert_can_manage_scene,
    build_hit_event_fields,
    create_itsm_ticket,
    expire_at_from,
    flow_of,
    format_snapshot_value,
    get_rule_for_admin,
    intercept_whitelist,
    renew_whitelist,
    resolve_duration,
    resolve_expire_at,
    review_whitelist,
    submit_whitelist,
    submitted_at_of,
    validity_text,
)
from services.web.scene.constants import ITSMV4TicketStatus


def _fmt(value):
    """复用 service 的格式化，保证断言口径和实现一致。"""

    from services.web.risk.whitelist.service import _format_dt

    return _format_dt(value)


def _scope():
    return {
        "connector": "and",
        "conditions": [
            {
                "condition": {
                    "field": {
                        "table": "event",
                        "raw_name": "operator",
                        "display_name": "operator",
                        "field_type": "string",
                    },
                    "operator": "eq",
                    "filter": "alice",
                }
            }
        ],
    }


class WhitelistCreateTests(SimpleTestCase):
    @patch("services.web.risk.whitelist.service._pass_if_admin")
    @patch("services.web.risk.whitelist.service.create_itsm_ticket")
    @patch("services.web.risk.whitelist.service.write_whitelist_nodes")
    @patch("services.web.risk.whitelist.service.RiskWhitelist.objects.create")
    @patch("services.web.risk.whitelist.service.Scene.objects.filter")
    def test_single_risk_stores_token_and_eq_fields(self, scene_filter, create, write_nodes, create_ticket, admin_pass):
        scene_filter.return_value.exists.return_value = True
        created = {}

        holder = {}

        def _create(**kwargs):
            created.update(kwargs)
            rule = SimpleNamespace(id=1, itsm_ticket_id="", itsm_sn="", itsm_ticket_url="", **kwargs)
            rule.refresh_from_db = lambda: None
            holder["rule"] = rule
            return rule

        def _create_ticket(rule_id):
            holder["rule"].itsm_ticket_id = "ticket-1"
            holder["rule"].itsm_sn = "SN1"
            holder["rule"].itsm_ticket_url = "http://itsm/ticket-1"

        create.side_effect = _create
        create_ticket.side_effect = _create_ticket
        risk = SimpleNamespace(strategy_id=9, raw_event_id="evt-1", risk_id="risk-1", scene_id=1, current_operator=[])
        submit_whitelist(
            scene_id=1,
            match_scope=_scope(),
            whitelist_type=WhitelistType.RISK_ACCEPTANCE,
            reason="接受一段时间",
            duration_days=15,
            risks=[risk],
            username="alice",
        )
        self.assertEqual(len(created["callback_token"]), 32)
        self.assertEqual(created["risk_id"], "risk-1")
        fields = {
            item["condition"]["field"]["raw_name"]: item["condition"] for item in created["match_scope"]["conditions"]
        }
        self.assertEqual(fields["strategy_id"]["operator"], "eq")
        self.assertEqual(fields["strategy_id"]["filter"], "9")
        self.assertEqual(fields["raw_event_id"]["operator"], "eq")
        self.assertEqual(fields["raw_event_id"]["filter"], "evt-1")
        self.assertNotIn("risk_id", fields)
        write_nodes.assert_called_once()
        self.assertEqual(write_nodes.call_args.args[0].itsm_ticket_id, "ticket-1")
        self.assertEqual(write_nodes.call_args.args[0].itsm_ticket_url, "http://itsm/ticket-1")
        create_ticket.assert_called_once_with(1)
        admin_pass.assert_called_once()

    @patch("services.web.risk.whitelist.service._pass_if_admin")
    @patch("services.web.risk.whitelist.service.create_itsm_ticket")
    @patch("services.web.risk.whitelist.service.write_whitelist_nodes")
    @patch("services.web.risk.whitelist.service.RiskWhitelist.objects.create")
    @patch("services.web.risk.whitelist.service.Scene.objects.filter")
    def test_batch_creates_one_rule_per_risk(self, scene_filter, create, write_nodes, create_ticket, admin_pass):
        scene_filter.return_value.exists.return_value = True
        created = []

        rules_by_id = {}

        def _create(**kwargs):
            created.append(kwargs)
            rule = SimpleNamespace(
                id=len(created),
                itsm_ticket_id="",
                itsm_sn="",
                itsm_ticket_url="",
                **kwargs,
            )
            rule.refresh_from_db = lambda: None
            rules_by_id[rule.id] = rule
            return rule

        def _create_ticket(rule_id):
            rules_by_id[rule_id].itsm_ticket_id = f"ticket-{rule_id}"
            rules_by_id[rule_id].itsm_sn = f"SN{rule_id}"
            rules_by_id[rule_id].itsm_ticket_url = f"http://itsm/ticket-{rule_id}"

        create.side_effect = _create
        create_ticket.side_effect = _create_ticket
        risks = [
            SimpleNamespace(strategy_id=9, raw_event_id="evt-1", risk_id="risk-1", scene_id=3, current_operator=[]),
            SimpleNamespace(strategy_id=9, raw_event_id="evt-2", risk_id="risk-2", scene_id=3, current_operator=[]),
        ]
        rules = submit_whitelist(
            scene_id=3,
            match_scope=_scope(),
            whitelist_type=WhitelistType.RISK_ACCEPTANCE,
            reason="批量接受",
            duration_days=15,
            risks=risks,
            username="alice",
        )
        self.assertEqual(len(rules), 2)
        self.assertEqual([item["risk_id"] for item in created], ["risk-1", "risk-2"])
        first_fields = {
            item["condition"]["field"]["raw_name"]: item["condition"]["filter"]
            for item in created[0]["match_scope"]["conditions"]
        }
        second_fields = {
            item["condition"]["field"]["raw_name"]: item["condition"]["filter"]
            for item in created[1]["match_scope"]["conditions"]
        }
        self.assertEqual(first_fields["strategy_id"], "9")
        self.assertEqual(second_fields["strategy_id"], "9")
        self.assertEqual(first_fields["raw_event_id"], "evt-1")
        self.assertEqual(second_fields["raw_event_id"], "evt-2")
        self.assertNotIn("risk_id", first_fields)
        self.assertNotIn("risk_id", second_fields)
        self.assertEqual(write_nodes.call_count, 2)
        self.assertEqual(create_ticket.call_count, 2)
        self.assertEqual(admin_pass.call_count, 2)

    @patch("services.web.risk.whitelist.service.create_itsm_ticket")
    @patch("services.web.risk.whitelist.service.write_whitelist_nodes")
    @patch("services.web.risk.whitelist.service.RiskWhitelist.objects.create")
    @patch("services.web.risk.whitelist.service.Scene.objects.filter")
    def test_admin_passes_before_node_is_written(self, scene_filter, create, write_nodes, create_ticket):
        scene_filter.return_value.exists.return_value = True
        holder = {}
        order = []

        def _create(**kwargs):
            rule = SimpleNamespace(id=1, itsm_ticket_id="", itsm_sn="", itsm_ticket_url="", **kwargs)
            rule.refresh_from_db = lambda: None
            holder["rule"] = rule
            return rule

        def _create_ticket(rule_id):
            order.append("ticket")
            holder["rule"].itsm_ticket_id = "ticket-1"

        def _pass(rule, username):
            order.append("pass")
            self.assertEqual(username, "alice")
            rule.status = WhitelistStatus.ACTIVE

        create.side_effect = _create
        create_ticket.side_effect = _create_ticket
        risk = SimpleNamespace(strategy_id=9, raw_event_id="evt-1", risk_id="risk-1", scene_id=1, current_operator=[])
        with patch("services.web.risk.whitelist.service._pass_if_admin", side_effect=_pass):
            submit_whitelist(
                scene_id=1,
                match_scope=_scope(),
                whitelist_type=WhitelistType.RISK_ACCEPTANCE,
                reason="接受一段时间",
                duration_days=15,
                risks=[risk],
                username="alice",
            )
        self.assertEqual(order, ["ticket", "pass"])
        self.assertEqual(write_nodes.call_args.args[0].status, WhitelistStatus.ACTIVE)

    def test_node_ticket_follows_callback_status(self):
        fields = {
            "itsm_ticket_id": "ticket-1",
            "itsm_sn": "SN1",
            "itsm_ticket_url": "http://itsm/ticket-1",
        }
        pending = _ticket_on_rule(SimpleNamespace(status=WhitelistStatus.PENDING, **fields))
        self.assertNotIn("approve_result", pending)
        active = _ticket_on_rule(SimpleNamespace(status=WhitelistStatus.ACTIVE, **fields))
        self.assertEqual(active["status"], ITSMV4TicketStatus.FINISHED)
        self.assertTrue(active["approve_result"])

    def test_active_rule_node_ignores_running_ticket(self):
        from services.web.risk.whitelist.service import refresh_whitelist_nodes

        rule = SimpleNamespace(
            id=1,
            risk_id="risk-1",
            status=WhitelistStatus.ACTIVE,
            itsm_ticket_id="ticket-1",
            itsm_sn="SN1",
            itsm_ticket_url="http://itsm/1",
            match_scope={},
            created_by="alice",
            whitelist_type=WhitelistType.RISK_ACCEPTANCE,
            reason="接受",
            created_at=None,
            is_permanent=False,
            expire_at=None,
        )
        node = SimpleNamespace(
            extra={"whitelist": {"rule_id": "1", "itsm_status": WhitelistStatus.PENDING, "itsm_status_display": "待审批"}},
            process_result={"ticket": {"status": WhitelistStatus.PENDING, "status_display": "待审批"}},
        )
        node.save = lambda update_fields=None: None
        with patch("services.web.risk.models.TicketNode") as ticket_node:
            ticket_node.objects.filter.return_value = [node]
            refresh_whitelist_nodes(rule, {"id": "ticket-1", "status": "running", "status_display": "审批中"})
        self.assertEqual(node.extra["whitelist"]["itsm_status"], WhitelistStatus.ACTIVE)
        self.assertEqual(node.extra["whitelist"]["itsm_status_display"], "生效中")
        self.assertNotIn("status", node.process_result["ticket"])
        self.assertNotIn("status_display", node.process_result["ticket"])


class WhitelistTicketCreateTests(SimpleTestCase):
    @patch("services.web.risk.whitelist.service._scene_display", return_value="梯阵(1)")
    @patch("services.web.risk.whitelist.service._abort_whitelist")
    @patch("services.web.risk.whitelist.service.RISK_WHITELIST_WORKFLOW_KEY", "workflow-key")
    @patch("services.web.risk.whitelist.service.api.bk_itsm_v4.ticket_create", side_effect=RuntimeError("boom"))
    @patch("services.web.risk.whitelist.service.RiskWhitelist.objects.filter")
    def test_ticket_create_failure_raises(self, query, ticket_create, abort, _display):
        rule = SimpleNamespace(
            id=1,
            itsm_ticket_id="",
            created_by="alice",
            scene_id=1,
            whitelist_type=WhitelistType.RISK_ACCEPTANCE,
            reason="接受一段时间",
            match_scope=_scope(),
            risk_id="risk-1",
            callback_token="token",
        )
        query.return_value.first.return_value = rule
        with self.assertRaises(ValidationError):
            create_itsm_ticket(1)
        abort.assert_called_once_with(rule)

    @patch("services.web.risk.whitelist.service.Scene.objects.filter")
    @patch("services.web.risk.whitelist.service.RISK_WHITELIST_WORKFLOW_KEY", "workflow-key")
    @patch("services.web.risk.whitelist.service.api.bk_itsm_v4.ticket_create", return_value={"id": "ticket-1"})
    def test_ticket_create_passes_scene_admins_only(self, ticket_create, scene_filter):
        from services.web.scene.models import Scene

        scene_filter.return_value.first.return_value = Scene(scene_id=3, managers=["scene-admin"])
        # _scene_display 走 values_list("name").first()，这里补上场景名供展示断言
        scene_filter.return_value.values_list.return_value.first.return_value = "梯阵"
        rule = SimpleNamespace(
            id=1,
            scene_id=3,
            whitelist_type=WhitelistType.FALSE_POSITIVE,
            reason="误报",
            match_scope=_scope(),
            risk_id="risk-1",
            created_by="alice",
            is_permanent=True,
            expire_at=None,
        )
        _submit_itsm_ticket(rule, operator="alice", callback_token="token")
        form_data = ticket_create.call_args.kwargs["form_data"]
        self.assertEqual(form_data["approver"], ["scene-admin"])
        # 工单里的匹配范围给人看：压成一行可读文案，而不是 JSON 条件树
        self.assertEqual(form_data["match_scope"], "责任人 = alice")
        # 工单只改展示：场景带名称与 ID、加白类型用中文、有效期有值；入库的 scene_id / 枚举值不受影响
        self.assertEqual(form_data["scene_id"], "梯阵(3)")
        self.assertEqual(form_data["whitelist_type"], "误报加白")
        self.assertEqual(form_data["validity"], "永久")

    @patch("services.web.risk.whitelist.service._whitelist_approvers", return_value=[])
    @patch("services.web.risk.whitelist.service._scene_display", return_value="梯阵(4)")
    @patch("services.web.risk.whitelist.service.RISK_WHITELIST_WORKFLOW_KEY", "workflow-key")
    @patch("services.web.risk.whitelist.service.api.bk_itsm_v4.ticket_create", return_value={"id": "ticket-1"})
    def test_ticket_create_displays_chinese_type_and_validity(self, ticket_create, _display, _approvers):
        # 冒险加白 + 本次传入 duration_days 算出的到期时间：工单展示中文类型和算好的有效期，
        # 且不把内存覆盖的到期时间写回 rule（提单不落库，创建流程随后自行保存）
        import datetime

        from django.utils import timezone

        resolved = (timezone.now() + datetime.timedelta(days=15)).replace(microsecond=0)
        rule = SimpleNamespace(
            id=2,
            scene_id=4,
            whitelist_type=WhitelistType.RISK_ACCEPTANCE,
            reason="接受风险",
            match_scope=_scope(),
            risk_id="risk-2",
            created_by="bob",
            is_permanent=False,
            expire_at=None,
        )
        _submit_itsm_ticket(rule, operator="bob", callback_token="token", expire_override=(False, resolved))
        form_data = ticket_create.call_args.kwargs["form_data"]
        self.assertEqual(form_data["whitelist_type"], "冒险加白")
        self.assertEqual(form_data["validity"], _fmt(resolved))
        # 内存覆盖只服务展示：rule 原始 expire_at 保持 None，避免误落库
        self.assertIsNone(rule.expire_at)

    @patch("services.web.risk.whitelist.service._whitelist_approvers", return_value=[])
    @patch("services.web.risk.whitelist.service._scene_display", return_value="梯阵(4)")
    @patch("services.web.risk.whitelist.service.RISK_WHITELIST_WORKFLOW_KEY", "workflow-key")
    @patch("services.web.risk.whitelist.service.api.bk_itsm_v4.ticket_create", return_value={"id": "ticket-1"})
    def test_ticket_create_match_scope_uppercase_connector(self, ticket_create, _display, _approvers):
        # 匹配范围连接符大写展示，和 SaaS 里的 AND 对齐（存储仍是小写 and）
        scope = _tree_scope(_tree_leaf("a", "1"), _tree_leaf("b", "2"))
        rule = SimpleNamespace(
            id=3,
            scene_id=4,
            whitelist_type=WhitelistType.FALSE_POSITIVE,
            reason="误报",
            match_scope=scope,
            risk_id="risk-3",
            created_by="bob",
            is_permanent=True,
            expire_at=None,
        )
        _submit_itsm_ticket(rule, operator="bob", callback_token="token")
        form_data = ticket_create.call_args.kwargs["form_data"]
        self.assertEqual(form_data["match_scope"], "a = 1 AND b = 2")

    @patch("services.web.risk.whitelist.service.apply_whitelist_result")
    @patch("services.web.risk.whitelist.service.api.bk_itsm_v4.ticket_detail")
    @patch("services.web.risk.whitelist.service.operate_itsm")
    @patch("services.web.risk.whitelist.service.is_scene_admin", return_value=True)
    def test_admin_handle_success_writes_active(self, is_admin, operate, ticket_detail, apply_result):
        from services.web.risk.whitelist.service import _pass_if_admin

        operate.return_value = {"success": True, "message": "操作成功"}
        rule = SimpleNamespace(id=1, scene_id=3, itsm_ticket_id="ticket-1", status=WhitelistStatus.PENDING)
        _pass_if_admin(rule, "alice")
        operate.assert_called_once_with(rule, "approve", "alice")
        ticket_detail.assert_not_called()
        apply_result.assert_called_once_with(
            rule,
            {"id": "ticket-1", "status": ITSMV4TicketStatus.FINISHED, "approve_result": True},
        )

    @patch("services.web.risk.whitelist.service.apply_whitelist_result")
    @patch("services.web.risk.whitelist.service.api.bk_itsm_v4.ticket_detail")
    @patch("services.web.risk.whitelist.service.operate_itsm")
    @patch("services.web.risk.whitelist.service.is_scene_admin", return_value=True)
    def test_admin_handle_failure_still_writes_active(self, is_admin, operate, ticket_detail, apply_result):
        from services.web.risk.whitelist.service import _pass_if_admin

        operate.side_effect = Exception("操作未找到")
        rule = SimpleNamespace(id=1, scene_id=3, itsm_ticket_id="ticket-1", status=WhitelistStatus.PENDING)
        _pass_if_admin(rule, "alice")
        ticket_detail.assert_not_called()
        apply_result.assert_called_once_with(
            rule,
            {"id": "ticket-1", "status": ITSMV4TicketStatus.FINISHED, "approve_result": True},
        )

    @patch("services.web.risk.whitelist.service.operate_itsm")
    @patch("services.web.risk.whitelist.service.is_scene_admin", return_value=False)
    def test_scene_manager_without_iam_stays_pending(self, is_admin, operate):
        from services.web.risk.whitelist.service import _pass_if_admin

        rule = SimpleNamespace(id=1, scene_id=3, itsm_ticket_id="ticket-1", status=WhitelistStatus.PENDING)
        _pass_if_admin(rule, "alice")
        operate.assert_not_called()

    def test_batch_requires_same_strategy_and_scene(self):
        risks = [
            SimpleNamespace(strategy_id=9, raw_event_id="evt-1", risk_id="risk-1", scene_id=3),
            SimpleNamespace(strategy_id=8, raw_event_id="evt-2", risk_id="risk-2", scene_id=3),
        ]
        with self.assertRaises(ValidationError):
            submit_whitelist(
                scene_id=3,
                match_scope=_scope(),
                whitelist_type=WhitelistType.RISK_ACCEPTANCE,
                reason="批量接受",
                duration_days=15,
                risks=risks,
                username="alice",
            )


class WhitelistCallbackTests(SimpleTestCase):
    def _rule(self):
        return SimpleNamespace(
            callback_token="stored-token",
            status=WhitelistStatus.PENDING,
            itsm_ticket_id="ticket-1",
        )

    @patch("services.web.risk.resources.whitelist.apply_whitelist_result")
    @patch("services.web.risk.resources.whitelist.RiskWhitelist.objects.filter")
    def test_callback_rejects_unknown_token(self, query, apply_result):
        query.return_value.first.return_value = self._rule()
        result = RiskWhitelistCallback().perform_request(
            {
                "callback_token": "wrong",
                "ticket": {"id": "ticket-1", "status": "finished", "approve_result": True},
            }
        )
        self.assertFalse(result["result"])
        apply_result.assert_not_called()

    @patch("services.web.risk.resources.whitelist.apply_whitelist_result")
    @patch("services.web.risk.resources.whitelist.RiskWhitelist.objects.filter")
    def test_callback_with_stored_token_applies_ticket(self, query, apply_result):
        rule = self._rule()
        query.return_value.first.return_value = rule
        result = RiskWhitelistCallback().perform_request(
            {
                "callback_token": "stored-token",
                "ticket": {
                    "id": "ticket-1",
                    "status": ITSMV4TicketStatus.FINISHED,
                    "approve_result": True,
                    "comment": "",
                },
            }
        )
        self.assertTrue(result["result"])
        apply_result.assert_called_once_with(
            rule,
            {"id": "ticket-1", "status": ITSMV4TicketStatus.FINISHED, "approve_result": True, "comment": ""},
        )


class WhitelistDurationTests(SimpleTestCase):
    def test_defaults_and_custom_days(self):
        self.assertEqual(resolve_duration(WhitelistType.FALSE_POSITIVE), (True, None))
        self.assertEqual(resolve_duration(WhitelistType.RISK_ACCEPTANCE), (False, 30))
        self.assertEqual(resolve_duration(WhitelistType.RISK_ACCEPTANCE, duration_days=45), (False, 45))
        base = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
        self.assertIsNone(expire_at_from(True, None, base))
        self.assertEqual(expire_at_from(False, 15, base), base + datetime.timedelta(days=15))
        fractional = datetime.datetime(2026, 12, 11, 8, 33, 41, 289366, tzinfo=datetime.timezone.utc)
        self.assertEqual(expire_at_from(False, 0, fractional), fractional.replace(microsecond=0))
        rule = SimpleNamespace(is_permanent=False, expire_at=fractional)
        self.assertEqual(validity_text(rule), "2026-12-11 16:33:41")

    def test_node_keeps_ticket_after_approve(self):
        expire = datetime.datetime(2026, 12, 11, 8, 33, 41, 289366, tzinfo=datetime.timezone.utc)
        submitted = datetime.datetime(2026, 11, 11, 8, 33, 41, 289366, tzinfo=datetime.timezone.utc)
        rule = SimpleNamespace(
            id=1,
            is_permanent=False,
            expire_at=expire,
            match_scope={},
            created_by="admin",
            whitelist_type=WhitelistType.RISK_ACCEPTANCE,
            reason="接受",
            created_at=submitted,
            updated_at=None,
            itsm_ticket_id="102026111108334100059701",
            itsm_sn="DE2026111100000001",
            itsm_ticket_url="http://itsm/1",
        )
        payload = _node_payload(
            rule,
            {
                "status": ITSMV4TicketStatus.FINISHED,
                "approve_result": True,
                "current_processors": [{"processor": "admin"}],
                "current_steps": [{"name": "审批"}],
            },
        )
        self.assertEqual(payload["validity_text"], "2026-12-11 16:33:41")
        self.assertEqual(payload["rule_id"], "1")
        self.assertEqual(payload["itsm_ticket_id"], "102026111108334100059701")
        self.assertEqual(payload["itsm_sn"], "DE2026111100000001")
        self.assertEqual(payload["itsm_status"], WhitelistStatus.ACTIVE)
        self.assertEqual(payload["itsm_status_display"], "生效中")
        # 纯创建：更新时间未晚于创建时间，提交时间取创建时间
        self.assertEqual(payload["submitted_at"], "2026-11-11 16:33:41")
        rule.status = WhitelistStatus.PENDING
        rule.itsm_ticket_url = "http://itsm/1"
        rule.updated_by = ""
        rule.reject_reason = ""
        rule.updated_at = None
        flow = flow_of(
            rule,
            {"current_processors": payload["current_processors"], "current_steps": payload["current_steps"]},
        )
        self.assertEqual(flow["itsm_sn"], "DE2026111100000001")
        self.assertEqual(flow["current_processors"], [{"processor": "admin"}])
        self.assertEqual(flow["current_steps"], [{"name": "审批"}])

    @patch("services.web.risk.whitelist.service.api.bk_itsm_v4.ticket_detail")
    def test_detail_echoes_itsm_ticket(self, ticket_detail):
        from services.web.risk.whitelist.service import _load_ticket_detail

        ticket_detail.return_value = {
            "id": "102026111108334100059701",
            "sn": "DE2026111108334100059701",
            "frontend_url": "http://itsm/1",
            "status": "running",
            "status_display": "审批中",
            "approve_result": None,
            "current_processors": [],
            "current_steps": [{"name": "审批"}],
        }
        rule = SimpleNamespace(
            id=1,
            status=WhitelistStatus.PENDING,
            itsm_ticket_id="102026111108334100059701",
            itsm_sn="",
            itsm_ticket_url="",
            updated_by="",
            reject_reason="",
            updated_at=None,
        )
        echoed = _load_ticket_detail(rule)
        flow = flow_of(rule, echoed)
        ticket_detail.assert_called_once_with(id="102026111108334100059701")
        self.assertEqual(flow["itsm_sn"], "DE2026111108334100059701")
        self.assertEqual(flow["itsm_url"], "http://itsm/1")
        self.assertEqual(flow["status"], WhitelistStatus.PENDING)
        self.assertEqual(flow["status_display"], "待审批")
        self.assertEqual(flow["current_processors"], [])
        self.assertEqual(flow["current_steps"], [{"name": "审批"}])

    @patch("services.web.risk.whitelist.service.apply_whitelist_result")
    @patch("services.web.risk.whitelist.service.api.bk_itsm_v4.ticket_detail")
    def test_detail_is_read_only_when_ticket_is_finished(self, ticket_detail, apply_result):
        """详情回显只读：工单已终态也不改状态，状态推进交给回调和轮询。"""

        from services.web.risk.whitelist.service import _load_ticket_detail

        ticket_detail.return_value = {"id": "ticket-1", "status": "finished", "approve_result": True}
        rule = SimpleNamespace(
            id=1,
            pk=1,
            status=WhitelistStatus.PENDING,
            itsm_ticket_id="ticket-1",
            reject_reason="",
            risk_id="",
        )
        _load_ticket_detail(rule)
        apply_result.assert_not_called()
        self.assertEqual(rule.status, WhitelistStatus.PENDING)

    @patch("services.web.risk.whitelist.service.api.bk_itsm_v4.ticket_detail")
    def test_detail_loads_single_ticket_once(self, ticket_detail):
        from services.web.risk.whitelist.service import _load_ticket_detail

        ticket_detail.return_value = {"id": "ticket-1", "status": "running"}
        pending = SimpleNamespace(id=1, status=WhitelistStatus.PENDING, itsm_ticket_id="ticket-1")
        found = _load_ticket_detail(pending)
        self.assertEqual(found["id"], "ticket-1")
        ticket_detail.assert_called_once_with(id="ticket-1")

    @patch("services.web.risk.whitelist.service._close_source_risk")
    @patch("services.web.risk.whitelist.service.RiskWhitelist.objects")
    @patch("services.web.risk.whitelist.service.apply_whitelist_result", side_effect=RuntimeError("db"))
    def test_flow_active_is_written_when_apply_fails(self, apply_result, objects, close_risk):
        objects.filter.return_value.values_list.return_value.first.return_value = None
        objects.filter.return_value.update.return_value = 1
        rule = SimpleNamespace(id=28, pk=28, status=WhitelistStatus.PENDING, reject_reason="", risk_id="")
        ticket = {"id": "102026111607182800062501", "status": "finished", "approve_result": True}
        from services.web.risk.whitelist.service import _write_terminal_status

        _write_terminal_status(rule, ticket)
        self.assertEqual(rule.status, WhitelistStatus.ACTIVE)
        self.assertEqual(objects.filter.return_value.update.call_args.kwargs["status"], WhitelistStatus.ACTIVE)

    def test_custom_time_is_the_expire_at(self):
        from django.utils import timezone

        text = "2026-12-31 18:00:00"
        permanent, expire_at = resolve_expire_at(WhitelistType.RISK_ACCEPTANCE, duration_days="custom", expire_at=text)
        self.assertFalse(permanent)
        self.assertEqual(timezone.localtime(expire_at).strftime("%Y-%m-%d %H:%M:%S"), text)
        with self.assertRaises(ValidationError):
            resolve_expire_at(WhitelistType.RISK_ACCEPTANCE, duration_days="custom")
        with self.assertRaises(ValidationError):
            resolve_expire_at(WhitelistType.RISK_ACCEPTANCE, duration_days="custom", expire_at="2020-01-01 00:00:00")

    def test_one_month_uses_a_calendar_month(self):
        base = datetime.datetime(2026, 1, 31, 8, 33, 41, tzinfo=datetime.timezone.utc)
        permanent, expire_at = resolve_expire_at(WhitelistType.RISK_ACCEPTANCE, duration_days="1m", base=base)
        self.assertFalse(permanent)
        self.assertEqual(expire_at, datetime.datetime(2026, 2, 28, 8, 33, 41, tzinfo=datetime.timezone.utc))
        _, mid_month = resolve_expire_at(
            WhitelistType.RISK_ACCEPTANCE,
            duration_days="1M",
            base=datetime.datetime(2026, 3, 15, 10, 0, 0, tzinfo=datetime.timezone.utc),
        )
        self.assertEqual(mid_month, datetime.datetime(2026, 4, 15, 10, 0, 0, tzinfo=datetime.timezone.utc))

    def test_permanent_duration(self):
        permanent, expire_at = resolve_expire_at(WhitelistType.FALSE_POSITIVE, duration_days="permanent")
        self.assertTrue(permanent)
        self.assertIsNone(expire_at)
        with self.assertRaises(ValidationError):
            resolve_expire_at(WhitelistType.RISK_ACCEPTANCE, duration_days="permanent")

    def test_risk_acceptance_cannot_be_permanent(self):
        with self.assertRaises(ValidationError):
            resolve_expire_at(WhitelistType.RISK_ACCEPTANCE, duration_days="permanent")

    def test_submitted_at_uses_created_at_until_renewed(self):
        created = datetime.datetime(2026, 11, 11, 8, 33, 41, tzinfo=datetime.timezone.utc)
        renewed = datetime.datetime(2026, 12, 1, 9, 0, 0, tzinfo=datetime.timezone.utc)
        # 纯创建：更新时间为空或与创建时间一致，提交时间取创建时间
        pure_created = SimpleNamespace(created_at=created, updated_at=None)
        self.assertEqual(submitted_at_of(pure_created), _fmt(created))
        same_time = SimpleNamespace(created_at=created, updated_at=created)
        self.assertEqual(submitted_at_of(same_time), _fmt(created))
        # 续期重建单据：更新时间晚于创建时间，提交时间取更新时间
        renewed_rule = SimpleNamespace(created_at=created, updated_at=renewed)
        self.assertEqual(submitted_at_of(renewed_rule), _fmt(renewed))


class _Rule:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.id = 1
        self.pk = 1
        self.itsm_ticket_id = ""
        self.itsm_sn = ""
        self.itsm_ticket_url = ""
        self.expire_at = kwargs.get("expire_at")
        self.reject_reason = ""
        self.updated_at = None
        self.created_at = None

    def save(self, update_fields=None):
        return None

    def refresh_from_db(self):
        return None


class _WhitelistQuery:
    def __init__(self, rules, kwargs):
        self.rules = rules
        self.kwargs = kwargs

    def _matched(self):
        matched = []
        for rule in self.rules:
            if "pk" in self.kwargs and self.kwargs["pk"] != rule.id:
                continue
            if "itsm_ticket_id" in self.kwargs and self.kwargs["itsm_ticket_id"] != rule.itsm_ticket_id:
                continue
            if "callback_token" in self.kwargs and self.kwargs["callback_token"] != rule.callback_token:
                continue
            if "status" in self.kwargs and self.kwargs["status"] != rule.status:
                continue
            if "scene_id" in self.kwargs and self.kwargs["scene_id"] != rule.scene_id:
                continue
            matched.append(rule)
        return matched

    def first(self):
        matched = self._matched()
        return matched[0] if matched else None

    def only(self, *fields):
        return self

    def __iter__(self):
        return iter(self._matched())


class _WhitelistManager:
    def __init__(self):
        self.rules = []

    def create(self, **kwargs):
        rule = _Rule(**kwargs)
        self.rules.append(rule)
        return rule

    def filter(self, **kwargs):
        return _WhitelistQuery(self.rules, kwargs)

    def select_for_update(self):
        return self

    def get(self, pk):
        return next(rule for rule in self.rules if rule.pk == pk)


@contextmanager
def _noop_atomic():
    yield


class WhitelistFlowTests(SimpleTestCase):
    @patch("services.web.risk.whitelist.service.refresh_whitelist_nodes")
    @patch("services.web.risk.whitelist.service._find_converged_risk", return_value=None)
    @patch("services.web.risk.whitelist.service.RiskWhitelistHit.objects.bulk_create")
    @patch("services.web.risk.whitelist.service.is_scene_admin", return_value=False)
    @patch("services.web.risk.whitelist.service.RISK_WHITELIST_WORKFLOW_KEY", "workflow-key")
    @patch("services.web.risk.whitelist.service.api.bk_itsm_v4.ticket_create")
    @patch("services.web.risk.whitelist.service.transaction.atomic", _noop_atomic)
    @patch("services.web.risk.whitelist.service.write_whitelist_nodes")
    @patch("services.web.risk.whitelist.service.Scene.objects.filter")
    def test_create_callback_then_intercept(
        self,
        scene_filter,
        write_nodes,
        ticket_create,
        is_admin,
        bulk_create,
        find_risk,
        refresh_nodes,
    ):
        manager = _WhitelistManager()
        scene_filter.return_value.exists.return_value = True

        def _ticket_create(**kwargs):
            rule = manager.rules[0]
            self.assertEqual(kwargs["callback_token"], rule.callback_token)
            self.assertIn("/risk_whitelist_callback/callback/", kwargs["callback_url"])
            return {
                "id": "ticket-1",
                "sn": "SN1",
                "frontend_url": "http://itsm/ticket-1",
                "status": "running",
            }

        ticket_create.side_effect = _ticket_create
        risk = SimpleNamespace(strategy_id=9, raw_event_id="evt-1", risk_id="risk-1", scene_id=3, current_operator=[])
        with patch.object(RiskWhitelist, "objects", manager):
            rule = submit_whitelist(
                scene_id=3,
                match_scope=_scope(),
                whitelist_type=WhitelistType.RISK_ACCEPTANCE,
                reason="接受一段时间",
                duration_days=15,
                risks=[risk],
                username="alice",
            )
            self.assertEqual(rule.status, WhitelistStatus.PENDING)
            self.assertEqual(rule.itsm_ticket_id, "ticket-1")
            self.assertEqual(rule.itsm_sn, "SN1")
            self.assertEqual(rule.itsm_ticket_url, "http://itsm/ticket-1")
            self.assertEqual(rule.risk_id, "risk-1")
            with patch("services.web.risk.whitelist.service._close_source_risk") as close_risk:
                result = RiskWhitelistCallback().perform_request(
                    {
                        "callback_token": rule.callback_token,
                        "ticket": {
                            "id": "ticket-1",
                            "status": ITSMV4TicketStatus.FINISHED,
                            "approve_result": True,
                            "comment": "",
                        },
                    }
                )
            self.assertTrue(result["result"])
            self.assertEqual(rule.status, WhitelistStatus.ACTIVE)
            close_risk.assert_called_once()
            self.assertEqual(close_risk.call_args.args[0].risk_id, "risk-1")
            self.assertIsNotNone(rule.expire_at)
            event = {
                "strategy_id": "9",
                "raw_event_id": "evt-1",
                "risk_id": "risk-1",
                "operator": "alice",
            }
            self.assertTrue(intercept_whitelist(event, {}, 3))
            hit = bulk_create.call_args.args[0][0]
            self.assertEqual(hit.action, HitAction.SUPPRESS_NEW)
            self.assertEqual(hit.risk_id, "")
            self.assertFalse(intercept_whitelist({**event, "operator": "bob"}, {}, 3))

    @patch("services.web.risk.whitelist.service.api.bk_itsm_v4.ticket_detail")
    @patch("services.web.risk.whitelist.service.refresh_whitelist_nodes")
    @patch("services.web.risk.whitelist.service._close_source_risk")
    @patch("services.web.risk.whitelist.service.transaction.atomic", _noop_atomic)
    def test_callback_writes_active_from_callback_ticket(self, close_risk, refresh_nodes, ticket_detail):
        rule = _Rule(status=WhitelistStatus.PENDING, callback_token="token", risk_id="")
        rule.itsm_ticket_id = "ticket-1"
        manager = _WhitelistManager()
        manager.rules.append(rule)
        with patch.object(RiskWhitelist, "objects", manager):
            result = RiskWhitelistCallback().perform_request(
                {
                    "callback_token": "token",
                    "ticket": {"id": "ticket-1", "status": "FINISHED", "approve_result": True},
                }
            )
        self.assertTrue(result["result"])
        self.assertEqual(rule.status, WhitelistStatus.ACTIVE)
        close_risk.assert_called_once()
        ticket_detail.assert_not_called()

    @patch("services.web.risk.whitelist.service.refresh_whitelist_nodes")
    @patch("services.web.risk.whitelist.service._close_source_risk")
    @patch("services.web.risk.whitelist.service.transaction.atomic", _noop_atomic)
    def test_callback_before_ticket_id_is_saved_still_writes_active(self, close_risk, refresh_nodes):
        rule = _Rule(status=WhitelistStatus.PENDING, callback_token="token", risk_id="")
        rule.itsm_ticket_id = ""
        manager = _WhitelistManager()
        manager.rules.append(rule)
        with patch.object(RiskWhitelist, "objects", manager):
            result = RiskWhitelistCallback().perform_request(
                {
                    "callback_token": "token",
                    "ticket": {"id": "ticket-9", "sn": "SN9", "status": "finished", "approve_result": True},
                }
            )
        self.assertTrue(result["result"])
        self.assertEqual(rule.itsm_ticket_id, "ticket-9")
        self.assertEqual(rule.itsm_sn, "SN9")
        self.assertEqual(rule.status, WhitelistStatus.ACTIVE)
        close_risk.assert_called_once()

    @patch("services.web.risk.resources.whitelist.refresh_whitelist_nodes")
    @patch("services.web.risk.resources.whitelist.apply_whitelist_result")
    def test_finished_callback_repairs_node_when_already_active(self, apply_result, refresh_nodes):
        rule = _Rule(status=WhitelistStatus.ACTIVE, callback_token="token", risk_id="risk-1")
        rule.itsm_ticket_id = "ticket-1"
        manager = _WhitelistManager()
        manager.rules.append(rule)
        ticket = {"id": "ticket-1", "status": "finished", "approve_result": True}
        with patch.object(RiskWhitelist, "objects", manager):
            result = RiskWhitelistCallback().perform_request({"callback_token": "token", "ticket": ticket})
        self.assertTrue(result["result"])
        self.assertEqual(rule.status, WhitelistStatus.ACTIVE)
        apply_result.assert_not_called()
        refresh_nodes.assert_called_once_with(rule, ticket)

    @patch("services.web.risk.whitelist.service.api.bk_itsm_v4.ticket_logs")
    @patch("services.web.risk.whitelist.service.refresh_whitelist_nodes")
    @patch("services.web.risk.whitelist.service._close_source_risk")
    @patch("services.web.risk.whitelist.service.transaction.atomic", _noop_atomic)
    def test_finished_without_approve_result_is_rejected(self, close_risk, refresh_nodes, ticket_logs):
        ticket_logs.return_value = {
            "items": [
                {
                    "action": "refuse",
                    "extra": [{"type": "name_value", "name": "审批意见", "value": "不是误报"}],
                }
            ]
        }
        rule = _Rule(status=WhitelistStatus.PENDING, callback_token="token", risk_id="risk-1")
        rule.itsm_ticket_id = "ticket-1"
        manager = _WhitelistManager()
        manager.rules.append(rule)
        with patch.object(RiskWhitelist, "objects", manager):
            result = RiskWhitelistCallback().perform_request(
                {"callback_token": "token", "ticket": {"id": "ticket-1", "status": "finished"}}
            )
        self.assertTrue(result["result"])
        self.assertEqual(result["status"], WhitelistStatus.REJECTED)
        self.assertEqual(rule.status, WhitelistStatus.REJECTED)
        self.assertEqual(rule.reject_reason, "不是误报")
        close_risk.assert_not_called()
        refresh_nodes.assert_called()
        ticket_logs.assert_called_once_with(ticket_id="ticket-1")


class WhitelistPollTests(SimpleTestCase):
    @patch("services.web.risk.whitelist.service.apply_whitelist_result")
    @patch("services.web.risk.whitelist.service.api.bk_itsm_v4.ticket_logs")
    def test_finished_logs_are_written_active(self, ticket_logs, apply_result):
        from services.web.risk.whitelist.service import _poll_whitelist_ticket

        ticket_logs.return_value = {
            "items": [
                {"activity_type": "APPROVE_TASK", "action": "approve"},
                {"action": "end"},
            ]
        }
        rule = SimpleNamespace(id=7, status=WhitelistStatus.PENDING, itsm_ticket_id="ticket-1", risk_id="")
        _poll_whitelist_ticket(rule)
        ticket = apply_result.call_args.args[1]
        self.assertEqual(ticket["status"], ITSMV4TicketStatus.FINISHED)
        self.assertTrue(ticket["approve_result"])


class WhitelistRenewTests(SimpleTestCase):
    @patch("services.web.risk.whitelist.service._pass_if_admin")
    @patch("services.web.risk.whitelist.service.refresh_whitelist_nodes")
    @patch(
        "services.web.risk.whitelist.service._submit_itsm_ticket",
        return_value={"id": "ticket-2", "sn": "SN2", "frontend_url": "http://itsm/ticket-2"},
    )
    @patch("services.web.risk.whitelist.service.validate_match_scope", return_value="")
    def test_false_positive_duration_clears_permanent(self, validate_scope, submit, refresh_nodes, admin_pass):
        saved = {}
        rule = _Rule(
            status=WhitelistStatus.ACTIVE,
            whitelist_type=WhitelistType.FALSE_POSITIVE,
            is_permanent=True,
            expire_at=None,
            match_scope=_scope(),
            reason="永久误报",
            scene_id=1,
            callback_token="old-token",
        )

        def save(update_fields=None):
            saved["fields"] = list(update_fields or [])

        rule.itsm_ticket_id = "ticket-old"
        rule.itsm_sn = "SN-OLD"
        rule.itsm_ticket_url = "http://itsm/old"
        rule.save = save
        renew_whitelist(
            rule,
            match_scope=_scope(),
            reason="改成三十天",
            duration_days=30,
            expire_at=None,
            username="alice",
        )
        self.assertFalse(rule.is_permanent)
        self.assertIsNotNone(rule.expire_at)
        self.assertEqual(rule.status, WhitelistStatus.PENDING)
        self.assertEqual(rule.itsm_ticket_id, "ticket-2")
        self.assertEqual(rule.itsm_sn, "SN2")
        self.assertEqual(rule.itsm_ticket_url, "http://itsm/ticket-2")
        self.assertNotEqual(rule.callback_token, "old-token")
        self.assertIn("is_permanent", saved["fields"])
        self.assertIn("expire_at", saved["fields"])
        self.assertIn("itsm_sn", saved["fields"])
        self.assertIn("itsm_ticket_id", saved["fields"])
        admin_pass.assert_called_once_with(rule, "alice")

    @patch("services.web.risk.whitelist.service._pass_if_admin")
    @patch("services.web.risk.whitelist.service.refresh_whitelist_nodes")
    @patch("services.web.risk.whitelist.service.validate_match_scope", return_value="")
    def test_callback_during_submit_keeps_active(self, validate_scope, refresh_nodes, admin_pass):
        rule = _Rule(
            status=WhitelistStatus.ACTIVE,
            whitelist_type=WhitelistType.RISK_ACCEPTANCE,
            is_permanent=False,
            match_scope=_scope(),
            reason="原来的原因",
            scene_id=1,
            callback_token="old-token",
        )
        rule.itsm_ticket_id = "ticket-old"

        def _submit(*args, **kwargs):
            rule.status = WhitelistStatus.ACTIVE
            rule.reject_reason = ""
            return {"id": "ticket-2", "sn": "SN2", "frontend_url": "http://itsm/ticket-2"}

        with patch("services.web.risk.whitelist.service._submit_itsm_ticket", side_effect=_submit):
            renewed = renew_whitelist(
                rule,
                match_scope=_scope(),
                reason="续期",
                duration_days=30,
                expire_at=None,
                username="alice",
            )
        self.assertEqual(renewed.status, WhitelistStatus.ACTIVE)
        self.assertEqual(renewed.itsm_ticket_id, "ticket-2")
        admin_pass.assert_not_called()

    @patch(
        "services.web.risk.whitelist.service._submit_itsm_ticket",
        side_effect=ValidationError("ITSM 工单创建失败"),
    )
    @patch("services.web.risk.whitelist.service.validate_match_scope", return_value="")
    def test_ticket_create_failure_keeps_original_term(self, validate_scope, submit):
        expire_at = datetime.datetime(2026, 12, 1, tzinfo=datetime.timezone.utc)
        rule = _Rule(
            status=WhitelistStatus.ACTIVE,
            whitelist_type=WhitelistType.RISK_ACCEPTANCE,
            is_permanent=False,
            expire_at=expire_at,
            match_scope=_scope(),
            reason="原来的原因",
            scene_id=1,
            callback_token="old-token",
        )
        rule.itsm_ticket_id = "ticket-old"
        rule.itsm_sn = "SN-OLD"
        rule.itsm_ticket_url = "http://itsm/old"
        with self.assertRaises(ValidationError):
            renew_whitelist(
                rule,
                match_scope=_scope(),
                reason="改期",
                duration_days=30,
                expire_at=None,
                username="alice",
            )
        self.assertEqual(rule.status, WhitelistStatus.ACTIVE)
        self.assertEqual(rule.expire_at, expire_at)
        self.assertEqual(rule.itsm_sn, "SN-OLD")
        self.assertEqual(rule.itsm_ticket_id, "ticket-old")
        self.assertEqual(rule.reason, "原来的原因")

    @patch("services.web.risk.whitelist.service._pass_if_admin")
    @patch("services.web.risk.whitelist.service.refresh_whitelist_nodes")
    @patch(
        "services.web.risk.whitelist.service._submit_itsm_ticket",
        return_value={"id": "ticket-2", "sn": "SN2", "frontend_url": "http://itsm/ticket-2"},
    )
    @patch("services.web.risk.whitelist.service.validate_match_scope", return_value="")
    def test_change_type_reopens_same_rule(self, validate_scope, submit, refresh_nodes, admin_pass):
        rule = _Rule(
            status=WhitelistStatus.ACTIVE,
            whitelist_type=WhitelistType.FALSE_POSITIVE,
            is_permanent=True,
            expire_at=None,
            match_scope=_scope(),
            reason="误报",
            scene_id=1,
            callback_token="old-token",
        )
        rule.itsm_ticket_id = "ticket-old"
        renewed = renew_whitelist(
            rule,
            match_scope=_scope(),
            reason="改成冒险加白",
            duration_days=None,
            expire_at=None,
            username="alice",
            whitelist_type=WhitelistType.RISK_ACCEPTANCE,
        )
        self.assertIs(renewed, rule)
        self.assertEqual(rule.whitelist_type, WhitelistType.RISK_ACCEPTANCE)
        self.assertFalse(rule.is_permanent)
        self.assertIsNotNone(rule.expire_at)
        self.assertEqual(rule.status, WhitelistStatus.PENDING)
        self.assertEqual(rule.itsm_ticket_id, "ticket-2")
        self.assertEqual(submit.call_args.args[0].whitelist_type, WhitelistType.RISK_ACCEPTANCE)
        validate_scope.assert_called_with(_scope(), WhitelistType.RISK_ACCEPTANCE)
        admin_pass.assert_called_once_with(rule, "alice")

    @patch(
        "services.web.risk.whitelist.service._submit_itsm_ticket",
        side_effect=ValidationError("ITSM 工单创建失败"),
    )
    @patch("services.web.risk.whitelist.service.validate_match_scope", return_value="")
    def test_type_change_failure_keeps_original_type(self, validate_scope, submit):
        rule = _Rule(
            status=WhitelistStatus.ACTIVE,
            whitelist_type=WhitelistType.FALSE_POSITIVE,
            is_permanent=True,
            match_scope=_scope(),
            reason="误报",
            scene_id=1,
            callback_token="old-token",
        )
        rule.itsm_ticket_id = "ticket-old"
        with self.assertRaises(ValidationError):
            renew_whitelist(
                rule,
                match_scope=_scope(),
                reason="改成冒险加白",
                duration_days=None,
                expire_at=None,
                username="alice",
                whitelist_type=WhitelistType.RISK_ACCEPTANCE,
            )
        self.assertEqual(rule.whitelist_type, WhitelistType.FALSE_POSITIVE)
        self.assertEqual(rule.status, WhitelistStatus.ACTIVE)
        self.assertEqual(rule.itsm_ticket_id, "ticket-old")


class WhitelistListQueryTests(SimpleTestCase):
    def test_status_type_and_sort_accept_multiple_values(self):
        from services.web.risk.whitelist.serializers import (
            ListRiskWhitelistReqSerializer,
        )

        serializer = ListRiskWhitelistReqSerializer(
            data={
                "scene_id": 1,
                "status": "active,disabled",
                "whitelist_type": ["false_positive", "risk_acceptance"],
                "updated_by": ["alice", "bob"],
                "sort": ["-updated_at", "hit_count"],
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["status"], ["active", "disabled"])
        self.assertEqual(
            serializer.validated_data["whitelist_type"],
            ["false_positive", "risk_acceptance"],
        )
        self.assertEqual(serializer.validated_data["order_fields"], ["-updated_at", "hit_count"])

    def test_expire_sort_puts_permanent_first_when_descending(self):
        from services.web.risk.whitelist.service import order_whitelist_queryset

        class _Query:
            def annotate(self, **kwargs):
                return self

            def order_by(self, *fields):
                self.fields = fields
                return self

        # 倒序（默认列表方向）永久置顶；正序沿用 NULL 语义，永久垫底
        descending = order_whitelist_queryset(_Query(), ["-expire_at"])
        self.assertEqual(descending.fields, ("-expire_is_permanent", "-expire_at"))
        ascending = order_whitelist_queryset(_Query(), ["expire_at"])
        self.assertEqual(ascending.fields, ("expire_is_permanent", "expire_at"))

    def test_callback_save_keeps_updated_by(self):
        from services.web.risk.whitelist.service import _save_rule

        rule = SimpleNamespace(updated_by="", created_by="alice", updated_at=None)
        saved = {}

        def save(update_fields=None):
            saved["update_fields"] = set(update_fields or [])

        rule.save = save
        # 回调没有登录用户：把 updated_by 一并写回，避免基类将更新人保存成空
        with patch("services.web.risk.whitelist.service.get_request_username", return_value=""):
            _save_rule(rule, ["status"])
        self.assertIn("updated_by", saved["update_fields"])

    def test_expire_whitelists_keeps_original_updated_by(self):
        from services.web.risk.whitelist.service import expire_whitelists

        with patch("services.web.risk.whitelist.service.RiskWhitelist.objects") as objects:
            expire_whitelists()
        fields = objects.filter.return_value.update.call_args.kwargs
        # 到期 Celery 没有登录用户：跳过 updated_by，保留各行原更新人，不写成创建人或后台账号
        self.assertTrue(fields["skip_update_user"])
        self.assertNotIn("updated_by", fields)

    def test_match_scope_filter_accepts_field_label_or_value(self):
        from services.web.risk.whitelist.serializers import (
            ListRiskWhitelistReqSerializer,
        )

        serializer = ListRiskWhitelistReqSerializer(
            data={"scene_id": 1, "match_scope": ["存储", "原始事件ID(event_id)", "命中策略(ID)(strategy_id)"]}
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(
            serializer.validated_data["match_scope"],
            ["存储", "原始事件ID(event_id)", "命中策略(ID)(strategy_id)"],
        )

    def test_default_sort_is_rule_id_desc(self):
        from services.web.risk.whitelist.serializers import (
            ListRiskWhitelistReqSerializer,
        )

        serializer = ListRiskWhitelistReqSerializer(data={"scene_id": 1})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["order_fields"], ["-id"])

    def test_contains_fields_filter_accepts_arbitrary_names(self):
        from services.web.risk.whitelist.serializers import (
            ListRiskWhitelistReqSerializer,
        )

        serializer = ListRiskWhitelistReqSerializer(
            data={"scene_id": 1, "contains_fields": ["strategy_id", "raw_event_id"]}
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["contains_fields"], ["strategy_id", "raw_event_id"])


def _group_leaf(name, value, operator="eq", field_name=None):
    return {"field": name, "field_name": field_name or name, "operator": operator, "value": value}


def _group_scope(*items):
    return {"connector": "and", "groups": [{"connector": "and", "conditions": list(items)}]}


def _tree_leaf(name, value, operator="eq"):
    field = {"table": "event", "raw_name": name, "display_name": name, "field_type": "string"}
    return {"condition": {"field": field, "operator": operator, "filter": value}}


def _tree_scope(*nodes):
    return {"connector": "and", "conditions": list(nodes)}


class WhitelistScopeFieldNamesTests(SimpleTestCase):
    def test_group_scope_collects_fields_with_value(self):
        from services.web.risk.whitelist.match import scope_field_names

        scope = _group_scope(
            _group_leaf("strategy_id", "9"),
            _group_leaf("operator", ""),
            _group_leaf("raw_event_id", [], operator="in"),
        )
        # 值为空的条件不算包含，和 append_risk_match_fields 的写入口径一致
        self.assertEqual(scope_field_names(scope), {"strategy_id"})

    def test_tree_scope_keeps_neq_and_supports_group_scope(self):
        from services.web.risk.whitelist.match import scope_field_names

        neq = _tree_scope(_tree_leaf("raw_event_id", "keep", operator="neq"))
        # 任意 operator 都算包含，neq 条件同样能筛出
        self.assertEqual(scope_field_names(neq), {"raw_event_id"})
        self.assertEqual(
            scope_field_names(_group_scope(_group_leaf("strategy_id", "9", operator="neq"))),
            {"strategy_id"},
        )

    def test_tree_scope_requires_value(self):
        from services.web.risk.whitelist.match import scope_field_names

        empty = _tree_scope(_tree_leaf("strategy_id", ""))
        self.assertEqual(scope_field_names(empty), set())
        self.assertEqual(scope_field_names({}), set())
        self.assertEqual(scope_field_names({"connector": "and", "conditions": "坏数据"}), set())


class WhitelistScopeReadableTests(SimpleTestCase):
    def test_group_scope_prefers_frontend_field_name(self):
        from services.web.risk.whitelist.match import format_scope_readable

        scope = _group_scope(
            _group_leaf("strategy_id", "9", field_name="命中策略(ID)"),
            _group_leaf("operator", ["alice", "bob"], operator="include"),
        )
        # 前端 field_name 优先；没带中文名的走标准字段兜底；连接符大写展示（与 SaaS 一致）
        self.assertEqual(format_scope_readable(scope), "命中策略(ID) = 9 AND 责任人 in alice、bob")

    def test_tree_scope_falls_back_to_standard_names(self):
        from services.web.risk.whitelist.match import format_scope_readable

        # append_risk_match_fields 补的条件 display_name 就是 raw_name，走兜底中文名
        scope = _tree_scope(_tree_leaf("strategy_id", "9"), _tree_leaf("raw_event_id", "e-1"))
        self.assertEqual(format_scope_readable(scope), "命中策略(ID) = 9 AND 原始事件ID = e-1")
        # 未知字段（如 event_data 自定义列）兜底不到，回退 raw_name
        self.assertEqual(
            format_scope_readable(_tree_scope(_tree_leaf("cost_center", "x", operator="neq"))),
            "cost_center != x",
        )

    def test_nested_connector_groups_add_brackets(self):
        from services.web.risk.whitelist.match import format_scope_readable

        scope = _tree_scope(
            _tree_scope(_tree_leaf("strategy_id", "9")),
            _tree_leaf("raw_event_id", "keep", operator="neq"),
        )
        scope = {"connector": "or", "conditions": scope["conditions"]}
        self.assertEqual(format_scope_readable(scope), "(命中策略(ID) = 9) OR 原始事件ID != keep")

    def test_invalid_scope_falls_back_to_json(self):
        import json

        from services.web.risk.whitelist.match import format_scope_readable

        self.assertEqual(format_scope_readable({}), "{}")
        broken = {"connector": "and", "conditions": "坏数据"}
        # 审批信息不能缺失：解析失败降级为原 JSON
        self.assertEqual(format_scope_readable(broken), json.dumps(broken, ensure_ascii=False))


class WhitelistContainsFieldsFilterTests(SimpleTestCase):
    def test_filters_rows_by_field_names(self):
        from services.web.risk.resources.whitelist import _filter_contains_fields

        scopes = {
            1: _group_scope(_group_leaf("strategy_id", "9")),
            2: _tree_scope(_tree_leaf("operator", "alice")),
            3: _group_scope(_group_leaf("raw_event_id", "")),
        }
        queryset = MagicMock()
        pruned = queryset.filter.return_value
        pruned.values_list.return_value = [(1, scopes[1]), (2, scopes[2])]
        # 只有 1 的匹配范围真的包含该字段；icontains 剪枝命中 2 也会被剔除
        result = _filter_contains_fields(queryset, ["strategy_id"])
        self.assertEqual(result, queryset.filter.return_value)
        queryset.filter.assert_any_call(Q(match_scope__icontains='"strategy_id"'))
        queryset.filter.assert_called_with(pk__in=[1])

    def test_empty_values_skip_filtering(self):
        from services.web.risk.resources.whitelist import _filter_contains_fields

        queryset = MagicMock()
        self.assertIs(_filter_contains_fields(queryset, None), queryset)
        self.assertIs(_filter_contains_fields(queryset, ["", None]), queryset)
        queryset.filter.assert_not_called()


class WhitelistScopeFieldOptionsTests(SimpleTestCase):
    def test_group_scope_pairs_field_with_field_name(self):
        from services.web.risk.whitelist.match import scope_field_options

        scope = _group_scope(
            _group_leaf("strategy_id", "9", field_name="命中策略(ID)"),
            _group_leaf("operator", ""),
            _group_leaf("raw_event_id", "e-1"),
        )
        # 带值才算包含；field_name 缺失走标准字段中文名兜底，兜底不到回退 field
        self.assertEqual(
            scope_field_options(scope),
            [("strategy_id", "命中策略(ID)"), ("raw_event_id", "原始事件ID")],
        )

    def test_tree_scope_falls_back_to_standard_field_name(self):
        from services.web.risk.whitelist.match import scope_field_options

        # append 补的条件 display_name 就是 raw_name，走标准字段中文名兜底
        scope = _tree_scope(_tree_leaf("strategy_id", "9"), _tree_leaf("cost_center", "x", operator="neq"))
        self.assertEqual(
            scope_field_options(scope),
            [("strategy_id", "命中策略(ID)"), ("cost_center", "cost_center")],
        )

    def test_dedupe_keeps_first_non_empty_field_name(self):
        from services.web.risk.whitelist.match import scope_field_options

        scope = _group_scope(
            _group_leaf("operator", "a", field_name="操作人"),
            _group_leaf("operator", "b", field_name="处理人"),
        )
        # 同一 field 去重，field_name 取首次出现的非空展示名
        self.assertEqual(scope_field_options(scope), [("operator", "操作人")])

    def test_empty_scope_returns_empty(self):
        from services.web.risk.whitelist.match import scope_field_options

        self.assertEqual(scope_field_options({}), [])
        self.assertEqual(scope_field_options({"connector": "and", "conditions": "坏数据"}), [])


class WhitelistContainsFieldsEnumTests(SimpleTestCase):
    # 场景管理权限已移到 viewset InstanceActionPermission(MANAGE_SCENE)，资源层不再校验
    @patch("services.web.risk.resources.whitelist.RiskWhitelist.objects")
    def test_aggregates_and_dedupes_fields_by_scene(self, objects):
        from services.web.risk.resources.whitelist import ListWhitelistContainsFields

        objects.filter.return_value.values_list.return_value = [
            _group_scope(_group_leaf("strategy_id", "9", field_name="命中策略(ID)")),
            _tree_scope(_tree_leaf("strategy_id", "9"), _tree_leaf("operator", "alice")),
            _group_scope(_group_leaf("raw_event_id", "")),
        ]
        result = ListWhitelistContainsFields().perform_request({"scene_id": 1})
        # 跨行按 field 去重、排序；空值条件不计入
        self.assertEqual(
            result,
            {
                "results": [
                    {"field": "operator", "field_name": "责任人"},
                    {"field": "strategy_id", "field_name": "命中策略(ID)"},
                ]
            },
        )
        objects.filter.assert_called_once_with(scene_id=1)

    def test_serializer_requires_scene_id(self):
        from services.web.risk.whitelist.serializers import (
            ListWhitelistContainsFieldsReqSerializer,
        )

        self.assertFalse(ListWhitelistContainsFieldsReqSerializer(data={}).is_valid())
        self.assertTrue(ListWhitelistContainsFieldsReqSerializer(data={"scene_id": 1}).is_valid())


class WhitelistDetailTests(SimpleTestCase):
    @patch("services.web.risk.resources.whitelist.serialize_rule")
    @patch("services.web.risk.resources.whitelist._load_ticket_detail")
    @patch("services.web.risk.resources.whitelist.RiskWhitelistHit.objects")
    @patch("services.web.risk.resources.whitelist.RiskWhitelist.objects")
    @patch("services.web.risk.resources.whitelist.get_request_username", return_value="tester")
    def test_detail_pulls_ticket_once_and_marks_admin(self, _user, objects, hits, load_detail, serialize):
        from services.web.risk.resources.whitelist import RetrieveRiskWhitelist

        rule = SimpleNamespace(id=7, scene_id=3, status=WhitelistStatus.PENDING, itsm_ticket_id="ticket-1")
        objects.filter.return_value.first.return_value = rule
        hits.filter.return_value.count.return_value = 5
        load_detail.return_value = {"id": "ticket-1", "current_steps": [{"name": "审批"}]}
        serialize.return_value = {"id": "7"}

        result = RetrieveRiskWhitelist().perform_request({"id": 7, "scene_id": 3})

        self.assertEqual(result, {"id": "7"})
        load_detail.assert_called_once_with(rule)
        # 详情回显实时 flow，且能进来即场景管理员（is_admin=True）
        kwargs = serialize.call_args.kwargs
        self.assertEqual(kwargs["progress"], {"id": "ticket-1", "current_steps": [{"name": "审批"}]})
        self.assertTrue(kwargs["is_admin"])
        self.assertEqual(serialize.call_args.args[1], 5)

    @patch("services.web.risk.resources.whitelist.serialize_rule")
    @patch("services.web.risk.resources.whitelist._load_ticket_detail")
    @patch("services.web.risk.resources.whitelist.RiskWhitelistHit.objects")
    @patch("services.web.risk.resources.whitelist.RiskWhitelist.objects")
    @patch("services.web.risk.resources.whitelist.get_request_username", return_value="tester")
    def test_detail_skips_ticket_for_active(self, _user, objects, hits, load_detail, serialize):
        from services.web.risk.resources.whitelist import RetrieveRiskWhitelist

        rule = SimpleNamespace(id=8, scene_id=3, status=WhitelistStatus.ACTIVE, itsm_ticket_id="ticket-1")
        objects.filter.return_value.first.return_value = rule
        hits.filter.return_value.count.return_value = 0
        serialize.return_value = {"id": "8"}

        RetrieveRiskWhitelist().perform_request({"id": 8, "scene_id": 3})

        # 生效中没有流转可回显，不外呼工单详情
        load_detail.assert_not_called()
        self.assertEqual(serialize.call_args.kwargs["progress"], {})

    @patch("services.web.risk.resources.whitelist.RiskWhitelist.objects")
    def test_detail_missing_raises(self, objects):
        from core.exceptions import ValidationError as CoreValidationError
        from services.web.risk.resources.whitelist import RetrieveRiskWhitelist

        objects.filter.return_value.first.return_value = None
        with self.assertRaises(CoreValidationError):
            RetrieveRiskWhitelist().perform_request({"id": 404, "scene_id": 3})

    @patch("services.web.risk.whitelist.service.list_actions", return_value=[])
    def test_serialize_rule_include_flow_controls_flow_key(self, _actions):
        from services.web.risk.whitelist.service import serialize_rule

        rule = SimpleNamespace(
            id=1,
            scene_id=3,
            risk_id="",
            match_scope={},
            whitelist_type="false_positive",
            is_permanent=False,
            expire_at=None,
            status=WhitelistStatus.ACTIVE,
            reason="",
            updated_by="",
            created_by="",
            updated_at=None,
            created_at=None,
            itsm_ticket_id="",
            itsm_sn="",
            itsm_ticket_url="",
            reject_reason="",
        )
        with_flow = serialize_rule(rule, username="tester", is_admin=True)
        no_flow = serialize_rule(rule, username="tester", is_admin=True, include_flow=False)
        self.assertIn("flow", with_flow)
        self.assertNotIn("flow", no_flow)


class WhitelistApproveCloseTests(SimpleTestCase):
    @patch("services.web.risk.models.Risk.objects")
    @patch("services.web.risk.handlers.ticket.CloseRisk")
    def test_approved_whitelist_closes_risk_from_create(self, close_cls, objects):
        from services.web.risk.constants import RiskStatus
        from services.web.risk.whitelist.service import _close_source_risk

        objects.filter.return_value.first.return_value = SimpleNamespace(
            risk_id="risk-1", status=RiskStatus.AWAIT_PROCESS
        )
        _close_source_risk(SimpleNamespace(id=7, risk_id="risk-1", updated_by="alice", created_by="bob"))
        close_cls.assert_called_once_with(risk_id="risk-1", operator="alice")
        close_cls.return_value.run.assert_called_once_with(description="白名单审批通过，关闭风险单")

    @patch("services.web.risk.models.Risk.objects")
    @patch("services.web.risk.handlers.ticket.CloseRisk")
    def test_already_closed_risk_is_skipped(self, close_cls, objects):
        from services.web.risk.constants import RiskStatus
        from services.web.risk.whitelist.service import _close_source_risk

        objects.filter.return_value.first.return_value = SimpleNamespace(risk_id="risk-1", status=RiskStatus.CLOSED)
        _close_source_risk(SimpleNamespace(id=7, risk_id="risk-1", updated_by="alice", created_by="bob"))
        close_cls.assert_not_called()

    def test_create_without_risk_does_not_close(self):
        from services.web.risk.whitelist.service import _close_source_risk

        with patch("services.web.risk.handlers.ticket.CloseRisk") as close_cls:
            _close_source_risk(SimpleNamespace(id=7, risk_id="", updated_by="alice", created_by="alice"))
        close_cls.assert_not_called()


class WhitelistReviewTests(SimpleTestCase):
    def test_scene_admin_is_scene_manager(self):
        from apps.permission.handlers.actions import ActionEnum
        from services.web.risk.whitelist.service import (
            is_scene_admin,
            managed_scene_ids,
        )

        with patch("services.web.risk.whitelist.service._scene_admin_usernames", return_value=["alice"]):
            self.assertTrue(is_scene_admin("alice", 3))
            self.assertFalse(is_scene_admin("root", 3))

        with patch("services.web.risk.whitelist.service.ScopePermission") as scope_cls:
            scope_cls.return_value.get_scene_ids.return_value = [3]
            self.assertEqual(managed_scene_ids("alice"), [3])
            self.assertEqual(scope_cls.return_value.get_scene_ids.call_args.args[1], ActionEnum.MANAGE_SCENE)

    def test_platform_admin_same_actions_as_scene_admin(self):
        from services.web.risk.whitelist.service import is_scene_admin, list_actions

        active = SimpleNamespace(status=WhitelistStatus.ACTIVE, scene_id=3, expire_at="2026-12-01 00:00:00")
        pending = SimpleNamespace(status=WhitelistStatus.PENDING, scene_id=3, expire_at=None)
        disabled = SimpleNamespace(status=WhitelistStatus.DISABLED, scene_id=3, expire_at=None)
        with patch("services.web.risk.whitelist.service._scene_admin_usernames", return_value=["alice"]):
            self.assertFalse(is_scene_admin("root", 3))
            self.assertTrue(is_scene_admin("alice", 3))
        # 平台管理员不再受限：与场景管理员一样可编辑、启停、删除，并通过 / 驳回待审批白名单
        with patch("services.web.risk.whitelist.service._can_manage_whitelist", return_value=True):
            self.assertEqual(list_actions(active, "root"), ["edit", "renew", "disable", "hits"])
            self.assertEqual(list_actions(pending, "root"), ["approve", "reject"])
            self.assertEqual(list_actions(disabled, "root"), ["edit", "enable", "hits", "delete"])

    def test_anyone_can_apply_renew(self):
        from services.web.risk.whitelist.service import list_actions

        active = SimpleNamespace(status=WhitelistStatus.ACTIVE, scene_id=3, expire_at="2026-12-01 00:00:00")
        permanent = SimpleNamespace(status=WhitelistStatus.ACTIVE, scene_id=3, expire_at=None)
        with patch("services.web.risk.whitelist.service.is_platform_admin", return_value=False):
            self.assertEqual(list_actions(active, "bob", is_admin=False), ["renew"])
            self.assertEqual(list_actions(permanent, "bob", is_admin=False), [])

    def test_pending_approve_actions_only_for_scene_admin(self):
        from services.web.risk.whitelist.service import list_actions

        rule = SimpleNamespace(status=WhitelistStatus.PENDING, scene_id=3, expire_at=None)
        with patch("services.web.risk.whitelist.service.is_scene_admin", return_value=False), patch(
            "services.web.risk.whitelist.service.is_platform_admin", return_value=False
        ):
            self.assertEqual(list_actions(rule, "bob"), [])
        with patch("services.web.risk.whitelist.service.is_scene_admin", return_value=True):
            self.assertEqual(list_actions(rule, "alice"), ["approve", "reject"])

    @patch("services.web.risk.whitelist.service.is_scene_admin", return_value=False)
    def test_non_admin_cannot_approve_or_reject(self, is_admin):
        rule = SimpleNamespace(id=1, itsm_ticket_id="ticket-1", scene_id=3, status=WhitelistStatus.PENDING)
        with self.assertRaises(ValidationError):
            review_whitelist(rule, "approve", "bob")
        with self.assertRaises(ValidationError):
            review_whitelist(rule, "refuse", "bob", reject_reason="不准")

    @patch("services.web.risk.whitelist.service.is_scene_admin", return_value=True)
    @patch("services.web.risk.whitelist.service.apply_whitelist_result", side_effect=lambda rule, ticket: ticket)
    @patch(
        "services.web.risk.whitelist.service.api.bk_itsm_v4.ticket_handle",
        return_value={"success": True, "message": "操作成功"},
    )
    def test_success_true_updates_status(self, ticket_handle, apply_result, is_admin):
        rule = SimpleNamespace(id=1, itsm_ticket_id="ticket-1", scene_id=3)
        review_whitelist(rule, "approve", "alice")
        self.assertTrue(apply_result.call_args.args[1]["approve_result"])
        review_whitelist(rule, "refuse", "alice", reject_reason="不准")
        self.assertFalse(apply_result.call_args.args[1]["approve_result"])
        self.assertEqual(apply_result.call_args.args[1]["comment"], "不准")
        self.assertEqual(ticket_handle.call_count, 2)

    @patch("services.web.risk.whitelist.service.is_scene_admin", return_value=True)
    @patch("services.web.risk.whitelist.service.apply_whitelist_result")
    @patch(
        "services.web.risk.whitelist.service.api.bk_itsm_v4.ticket_handle",
        return_value={"success": False, "message": "操作失败"},
    )
    def test_success_false_keeps_status(self, ticket_handle, apply_result, is_admin):
        rule = SimpleNamespace(id=1, itsm_ticket_id="ticket-1", scene_id=3)
        returned = review_whitelist(rule, "approve", "alice")
        self.assertIs(returned, rule)
        apply_result.assert_not_called()
        ticket_handle.assert_called_once()


class WhitelistSnapshotTimeTests(SimpleTestCase):
    def test_event_time_millis_becomes_datetime_string(self):
        shown = format_snapshot_value("event_time", 1731902400000)
        self.assertEqual(shown, "2024-11-18 12:00:00")
        self.assertEqual(format_snapshot_value("strategy_id", 9), 9)
        self.assertEqual(format_snapshot_value("event_time", "2024-11-18 12:00:00"), "2024-11-18 12:00:00")


class WhitelistHitEventFieldNameTests(SimpleTestCase):
    def test_field_name_uses_existing_event_field_config(self):
        strategy = SimpleNamespace(
            event_data_field_configs=[{"field_name": "username", "display_name": "操作人用户名"}],
            event_evidence_field_configs=[],
        )
        with patch("services.web.strategy_v2.models.Strategy.objects") as objects:
            objects.filter.return_value.first.return_value = strategy
            fields = build_hit_event_fields({"strategy_id": "9", "operator": "alice", "username": "alice"})

        names = {item["field"]: item["field_name"] for item in fields}
        self.assertEqual(names["strategy_id"], "命中策略(ID)")
        self.assertEqual(names["operator"], "责任人")
        self.assertEqual(names["username"], "操作人用户名")


class WhitelistCreateRiskLabelTests(SimpleTestCase):
    """带 risk_id 的加白只发起白名单审批，不直接改风险状态。

    PRD 口径：「误报加白」与「冒险加白」关单语义一致，审批通过后由回调关单；
    提交即误报关单只属于「标记误报同时加白」（UpdateRiskLabel 链路）。
    """

    def _rule(self):
        created = datetime.datetime(2024, 11, 1, 12, 0, 0)
        return SimpleNamespace(
            id=1,
            scene_id=1,
            risk_id="whitelist_fp_risk",
            match_scope=_scope(),
            whitelist_type=WhitelistType.FALSE_POSITIVE,
            expire_at=None,
            is_permanent=True,
            status=WhitelistStatus.PENDING,
            reason="误报加白不直接关单",
            updated_by="tester",
            updated_at=created,
            created_at=created,
            created_by="tester",
            itsm_ticket_id="",
            itsm_sn="",
            itsm_ticket_url="",
            callback_token="t",
            renewed_at=None,
        )

    @patch("services.web.risk.whitelist.service.is_scene_admin", return_value=True)
    @patch("services.web.risk.whitelist.service._pass_if_admin")
    @patch("services.web.risk.whitelist.service.create_itsm_ticket")
    @patch("services.web.risk.whitelist.service.write_whitelist_nodes")
    @patch("services.web.risk.whitelist.service.RiskWhitelist.objects.create")
    @patch("services.web.risk.whitelist.service.Scene.objects.filter")
    @patch("services.web.risk.resources.whitelist.Risk.objects.filter")
    @patch("services.web.risk.resources.whitelist.get_request_username", return_value="tester")
    def test_false_positive_with_risk_id_does_not_misreport(self, _username, risk_filter, *_service_mocks):
        risk = SimpleNamespace(
            risk_id="whitelist_fp_risk", strategy_id=9, raw_event_id="fp_evt_1", scene_id=1, current_operator=[]
        )
        risk_filter.return_value = [risk]
        rule = self._rule()
        rule.refresh_from_db = lambda: None
        with patch("services.web.risk.whitelist.service.RiskWhitelist.objects.create", return_value=rule), patch(
            "services.web.risk.resources.risk.UpdateRiskLabel.request"
        ) as update_label:
            CreateRiskWhitelist().request(
                {
                    "risk_id": risk.risk_id,
                    "match_scope": _scope(),
                    "whitelist_type": WhitelistType.FALSE_POSITIVE,
                    "reason": "误报加白不直接关单",
                }
            )
        update_label.assert_not_called()

    @patch("services.web.risk.whitelist.service.is_scene_admin", return_value=True)
    @patch("services.web.risk.whitelist.service._pass_if_admin")
    @patch("services.web.risk.whitelist.service.create_itsm_ticket")
    @patch("services.web.risk.whitelist.service.write_whitelist_nodes")
    @patch("services.web.risk.whitelist.service.RiskWhitelist.objects.create")
    @patch("services.web.risk.whitelist.service.Scene.objects.filter")
    @patch("services.web.risk.resources.whitelist.get_request_username", return_value="tester")
    def test_batch_false_positive_does_not_misreport(self, _username, *_service_mocks):
        risk = SimpleNamespace(
            risk_id="whitelist_fp_risk", strategy_id=9, raw_event_id="fp_evt_1", scene_id=1, current_operator=[]
        )
        rule = self._rule()
        rule.refresh_from_db = lambda: None
        with patch(
            "services.web.risk.resources.risk._load_bulk_selection",
            return_value=SimpleNamespace(risk_ids=[risk.risk_id], risks=[risk], risk_map={}, error=None),
        ), patch("services.web.risk.whitelist.service.RiskWhitelist.objects.create", return_value=rule), patch(
            "services.web.risk.resources.risk.UpdateRiskLabel.request"
        ) as update_label:
            BatchCreateRiskWhitelist().request(
                {
                    "risk_ids": [risk.risk_id],
                    "match_scope": _scope(),
                    "whitelist_type": WhitelistType.FALSE_POSITIVE,
                    "reason": "批量误报加白不直接关单",
                }
            )
        update_label.assert_not_called()


class WhitelistPermissionTests(SimpleTestCase):
    """白名单写权限口径：场景管理员与有该场景管理权限的平台管理员完全一致。

    创建 / 批量创建、编辑 / 删除 / 启停 / 续期、通过 / 驳回：
    命中场景管理员，或平台管理员且该场景在其可管理范围内，任一即可。
    """

    @patch("services.web.risk.whitelist.service.managed_scene_ids", return_value=[])
    @patch("services.web.risk.whitelist.service.is_platform_admin", return_value=False)
    @patch("services.web.risk.whitelist.service.is_scene_admin", return_value=True)
    def test_create_allows_scene_admin(self, _scene, _platform, _managed):
        # 场景管理员直接放行，不因非平台管理员被拒
        assert_can_manage_scene("alice", 1)

    @patch("services.web.risk.whitelist.service.managed_scene_ids", return_value=[1, 2])
    @patch("services.web.risk.whitelist.service.is_platform_admin", return_value=True)
    @patch("services.web.risk.whitelist.service.is_scene_admin", return_value=False)
    def test_create_allows_platform_admin_on_managed_scene(self, _scene, _platform, _managed):
        # 平台管理员且该场景在其可管理范围内放行（scene_id 做字符串归一比较）
        assert_can_manage_scene("bob", "1")

    @patch("services.web.risk.whitelist.service.managed_scene_ids", return_value=[3])
    @patch("services.web.risk.whitelist.service.is_platform_admin", return_value=True)
    @patch("services.web.risk.whitelist.service.is_scene_admin", return_value=False)
    def test_create_denies_platform_admin_outside_scene(self, _scene, _platform, _managed):
        with self.assertRaises(ValidationError):
            assert_can_manage_scene("bob", 1)

    @patch("services.web.risk.whitelist.service.managed_scene_ids", return_value=[])
    @patch("services.web.risk.whitelist.service.is_platform_admin", return_value=False)
    @patch("services.web.risk.whitelist.service.is_scene_admin", return_value=False)
    def test_create_denies_normal_user(self, _scene, _platform, _managed):
        with self.assertRaises(ValidationError):
            assert_can_manage_scene("carol", 1)

    @patch("services.web.risk.whitelist.service.is_scene_admin", return_value=False)
    def test_platform_admin_allows_all_whitelist_ops_on_managed_scene(self, _scene):
        # 平台管理员可管理该场景：与场景管理员一样可读写、通过 / 驳回
        rule = SimpleNamespace(scene_id=1)
        with patch("services.web.risk.whitelist.service.RiskWhitelist.objects.filter") as query, patch(
            "services.web.risk.whitelist.service.is_platform_admin", return_value=True
        ), patch("services.web.risk.whitelist.service.managed_scene_ids", return_value=[1]):
            query.return_value.first.return_value = rule
            self.assertIs(get_rule_for_admin(1, "bob"), rule)

    @patch("services.web.risk.whitelist.service.is_scene_admin", return_value=False)
    def test_no_permission_denied(self, _scene):
        # 非场景管理员且非平台管理员应被拒
        rule = SimpleNamespace(scene_id=1)
        with patch("services.web.risk.whitelist.service.RiskWhitelist.objects.filter") as query, patch(
            "services.web.risk.whitelist.service.is_platform_admin", return_value=False
        ), patch("services.web.risk.whitelist.service.managed_scene_ids", return_value=[]):
            query.return_value.first.return_value = rule
            with self.assertRaises(ValidationError):
                get_rule_for_admin(1, "carol")

    @patch("services.web.risk.whitelist.service.is_scene_admin", return_value=False)
    def test_approve_reject_allows_platform_admin(self, _scene):
        # 通过 / 驳回：去掉平台管理员限制，可管理该场景的平台管理员同等放行
        rule = SimpleNamespace(scene_id=1)
        with patch("services.web.risk.whitelist.service.RiskWhitelist.objects.filter") as query, patch(
            "services.web.risk.whitelist.service.is_platform_admin", return_value=True
        ), patch("services.web.risk.whitelist.service.managed_scene_ids", return_value=[1]):
            query.return_value.first.return_value = rule
            self.assertIs(get_rule_for_admin(1, "bob"), rule)

# -*- coding: utf-8 -*-
import datetime
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from services.web.risk.resources.whitelist import RiskWhitelistCallback
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
    create_itsm_ticket,
    expire_at_from,
    flow_of,
    intercept_whitelist,
    progress_map,
    renew_whitelist,
    resolve_duration,
    resolve_expire_at,
    review_whitelist,
    submit_whitelist,
    validity_text,
)
from services.web.scene.constants import ITSMV4TicketStatus


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
    @patch("services.web.risk.whitelist.service.create_itsm_ticket")
    @patch("services.web.risk.whitelist.service.write_whitelist_nodes")
    @patch("services.web.risk.whitelist.service.RiskWhitelist.objects.create")
    @patch("services.web.risk.whitelist.service.Scene.objects.filter")
    def test_single_risk_stores_token_and_eq_fields(self, scene_filter, create, write_nodes, create_ticket):
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

    @patch("services.web.risk.whitelist.service.create_itsm_ticket")
    @patch("services.web.risk.whitelist.service.write_whitelist_nodes")
    @patch("services.web.risk.whitelist.service.RiskWhitelist.objects.create")
    @patch("services.web.risk.whitelist.service.Scene.objects.filter")
    def test_batch_creates_one_rule_per_risk(self, scene_filter, create, write_nodes, create_ticket):
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
    @patch("services.web.risk.whitelist.service._abort_whitelist")
    @patch("services.web.risk.whitelist.service.RISK_WHITELIST_WORKFLOW_KEY", "workflow-key")
    @patch("services.web.risk.whitelist.service.api.bk_itsm_v4.ticket_create", side_effect=RuntimeError("boom"))
    @patch("services.web.risk.whitelist.service.RiskWhitelist.objects.filter")
    def test_ticket_create_failure_raises(self, query, ticket_create, abort):
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
        rule = SimpleNamespace(
            id=1,
            scene_id=3,
            whitelist_type=WhitelistType.FALSE_POSITIVE,
            reason="误报",
            match_scope=_scope(),
            risk_id="risk-1",
            created_by="alice",
        )
        _submit_itsm_ticket(rule, operator="alice", callback_token="token")
        form_data = ticket_create.call_args.kwargs["form_data"]
        self.assertEqual(form_data["approver"], ["scene-admin"])

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
    def test_admin_handle_failure_does_not_read_ticket_detail(self, is_admin, operate, ticket_detail, apply_result):
        from services.web.risk.whitelist.service import _pass_if_admin

        operate.side_effect = Exception("操作未找到")
        rule = SimpleNamespace(id=1, scene_id=3, itsm_ticket_id="ticket-1", status=WhitelistStatus.PENDING)
        _pass_if_admin(rule, "alice")
        ticket_detail.assert_not_called()
        apply_result.assert_not_called()

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
        rule = SimpleNamespace(
            id=1,
            is_permanent=False,
            expire_at=expire,
            match_scope={},
            created_by="admin",
            whitelist_type=WhitelistType.RISK_ACCEPTANCE,
            reason="接受",
            created_at=expire,
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
    def test_list_echoes_itsm_ticket(self, ticket_detail):
        ticket_detail.return_value = {
            "id": "102026111108334100059701",
            "sn": "DE2026111100000001",
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
        echoed = progress_map([rule])["1"]
        flow = flow_of(rule, echoed)
        ticket_detail.assert_called_once_with(id="102026111108334100059701")
        self.assertEqual(flow["itsm_sn"], "DE2026111100000001")
        self.assertEqual(flow["itsm_url"], "http://itsm/1")
        self.assertEqual(flow["status"], WhitelistStatus.PENDING)
        self.assertEqual(flow["status_display"], "待审批")
        self.assertEqual(flow["current_processors"], [])
        self.assertEqual(flow["current_steps"], [{"name": "审批"}])

    @patch("services.web.risk.whitelist.service.apply_whitelist_result")
    @patch("services.web.risk.whitelist.service.api.bk_itsm_v4.ticket_detail")
    def test_list_writes_active_when_ticket_is_finished(self, ticket_detail, apply_result):
        ticket_detail.return_value = {"id": "ticket-1", "status": "finished", "approve_result": True}
        apply_result.return_value = SimpleNamespace(status=WhitelistStatus.ACTIVE, reject_reason="")
        rule = SimpleNamespace(
            id=1,
            pk=1,
            status=WhitelistStatus.PENDING,
            itsm_ticket_id="ticket-1",
            reject_reason="",
            risk_id="",
        )
        progress_map([rule])
        apply_result.assert_called_once()
        self.assertEqual(rule.status, WhitelistStatus.ACTIVE)

    @patch("services.web.risk.whitelist.service._write_terminal_status")
    @patch("services.web.risk.whitelist.service.api.bk_itsm_v4.ticket_detail")
    def test_list_loads_pending_and_rejected_tickets_together(self, ticket_detail, write_status):
        ticket_detail.side_effect = lambda id: {"id": id, "status": "running"}
        pending = SimpleNamespace(id=1, status=WhitelistStatus.PENDING, itsm_ticket_id="ticket-1")
        rejected = SimpleNamespace(id=2, status=WhitelistStatus.REJECTED, itsm_ticket_id="ticket-2")
        active = SimpleNamespace(id=3, status=WhitelistStatus.ACTIVE, itsm_ticket_id="ticket-3")
        found = progress_map([pending, rejected, active])
        self.assertEqual(set(found), {"1", "2"})
        self.assertEqual(ticket_detail.call_count, 2)
        write_status.assert_called_once()

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

    @patch("services.web.risk.whitelist.service._ticket_from_logs")
    @patch("services.web.risk.whitelist.service._load_ticket_detail", return_value={})
    @patch("services.web.risk.whitelist.service.refresh_whitelist_nodes")
    @patch("services.web.risk.whitelist.service._close_source_risk")
    @patch("services.web.risk.whitelist.service.transaction.atomic", _noop_atomic)
    def test_callback_without_approve_result_reads_logs_and_returns_active(
        self, close_risk, refresh_nodes, ticket_detail, ticket_logs
    ):
        ticket_logs.return_value = {
            "id": "ticket-1",
            "status": ITSMV4TicketStatus.FINISHED,
            "approve_result": True,
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
        self.assertEqual(result["status"], WhitelistStatus.ACTIVE)
        self.assertEqual(rule.status, WhitelistStatus.ACTIVE)
        close_risk.assert_called_once()
        refresh_nodes.assert_called()


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


class WhitelistListQueryTests(SimpleTestCase):
    def test_status_type_and_sort_accept_multiple_values(self):
        from services.web.risk.whitelist.serializers import (
            ListRiskWhitelistReqSerializer,
        )

        serializer = ListRiskWhitelistReqSerializer(
            data={
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

    def test_match_scope_filter_accepts_field_label_or_value(self):
        from services.web.risk.whitelist.serializers import (
            ListRiskWhitelistReqSerializer,
        )

        serializer = ListRiskWhitelistReqSerializer(
            data={"match_scope": ["存储", "原始事件ID(event_id)", "命中策略(ID)(strategy_id)"]}
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

        serializer = ListRiskWhitelistReqSerializer(data={})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["order_fields"], ["-id"])


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
    def test_pending_approve_actions_only_for_scene_admin(self):
        from services.web.risk.whitelist.service import list_actions

        rule = SimpleNamespace(status=WhitelistStatus.PENDING, scene_id=3, expire_at=None)
        with patch("services.web.risk.whitelist.service.is_scene_admin", return_value=False):
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
